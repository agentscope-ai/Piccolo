"""The legacy showcase facade must dispatch active and archived chess correctly."""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from blink_arena.engine import get_engine, get_archived_engine
import jev_demo_showcases as facade
import jev_chess as chess


def client_for(predict=None):
    async def unused(*args):
        raise AssertionError('This test must not call a model')
    app = FastAPI()
    facade.install(app, '', lambda seq: None, predict or unused, None)
    return TestClient(app)


def new(client, **kwargs):
    response = client.post('/api/showcases/new', json={'kind': 'chess', 'seed': 0, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def act(client, state, **kwargs):
    return client.post('/api/showcases/step', json={
        'session_id': state['session_id'], 'revision': state['revision'], **kwargs})


def test_facade_uses_registered_chess_without_card_none_and_keeps_controller():
    state = facade.fresh('chess', 0, 'rule')
    assert state['engine_revision'] == chess.REVISION and state['opponent'] == 'rule'
    before = deepcopy(state)
    after = facade.step(state, 'e2e4', controller='human')
    assert state == before and after['history'][-1]['controller'] == 'human'
    assert facade._step(state, 'e2e4', controller='human') == after
    assert facade.choices(state) == get_engine('chess').legal_actions(state)


def test_archived_chess_layout_still_dispatches_to_archived_rules():
    state = get_archived_engine('chess').reset(0, {'opponent': 'human'})
    assert '_moves' in state and 'engine_revision' not in state
    after = facade.step(state, 'e2e4')
    assert '_moves' in after and 'engine_revision' not in after
    assert get_engine('chess', after).archived
    assert get_engine('chess', after).public(after)['current_player'] == 1


def test_legacy_http_manual_reference_and_model_use_one_shared_core():
    records = []
    async def predict(record, qid):
        records.append(deepcopy(record))
        action = next(iter(record['questions'][qid]['criteria']))
        return {'value': action, 'latency_seconds': 0., 'fixture': True}
    with client_for(predict) as client:
        state = new(client)
        response = act(client, state, action='e2e4')
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['actor_label'] == '白方' and state['controller'] == 'human'
        assert state['world']['current_player'] == 1
        assert state['world']['history'][-1]['controller'] == 'human'
        response = act(client, state, reference=True)
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['actor_label'] == '黑方' and state['controller'] == 'rule_engine'
        assert state['world']['history'][-1]['strategy_origin'] == 'rule_opponent'
        assert state['world']['controller_counts']['rule_takeover_count'] == 0
        response = act(client, state, model=True)
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['world']['history'][-1]['controller'] == 'model'
        assert state['result']['fixture'] and len(records) == 1
        assert state['previous_input']['state'] == records[0]['state']
        assert state['previous_input']['option'] == records[0]['questions']['decision']['criteria']


def test_illegal_and_ambiguous_http_requests_do_not_advance_state():
    with client_for() as client:
        state = new(client)
        assert act(client, state, action='e2e5').status_code == 422
        assert act(client, state, model=True, reference=True).status_code == 422
        assert act(client, state, action='e2e4', card_ids=[1]).status_code == 422
        response = act(client, state, action='e2e4')
        assert response.status_code == 200 and response.json()['world']['steps'] == 1


def test_unique_legal_http_model_step_is_marked_b_without_inference(monkeypatch):
    fixture = chess.fresh(fen='7k/8/6K1/8/8/8/8/7R b - - 0 1')
    original = facade.fresh
    monkeypatch.setattr(facade, 'fresh', lambda kind, seed, opponent='human':
                        deepcopy(fixture) if kind == 'chess' else original(kind, seed, opponent))
    with client_for() as client:
        state = new(client)
        response = act(client, state, model=True)
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['forced'] and state['result'] is None
        assert state['controller'] == 'deterministic_execution'
        assert state['world']['history'][-1]['policy_decision_class'] == 'B'


def test_explicit_draw_claim_is_a_first_class_http_action(monkeypatch):
    fixture = chess.fresh(fen='7k/8/8/8/8/8/8/R3K3 w - - 100 51')
    original = facade.fresh
    monkeypatch.setattr(facade, 'fresh', lambda kind, seed, opponent='human':
                        deepcopy(fixture) if kind == 'chess' else original(kind, seed, opponent))
    with client_for() as client:
        state = new(client)
        response = act(client, state, action='claim_draw:fifty_moves')
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['world']['outcome'] == 'draw' and state['choices'] == {}
        assert state['world']['termination'] == 'claimed_fifty_moves'


@pytest.mark.parametrize('kind', ['liars_dice', 'goofspiel'])
def test_old_private_agent_handoff_and_redaction_survive(kind):
    with client_for() as client:
        response = client.post('/api/showcases/new', json={'kind': kind, 'seed': 42})
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['world']['handoff'] and state['choices'] == {} and state['input'] is None
        response = client.post('/api/showcases/reveal', json={
            'session_id': state['session_id'], 'revision': state['revision']})
        assert response.status_code == 200, response.text
        state = response.json()
        response = act(client, state, action=next(iter(state['choices'])))
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['world']['handoff'] and state['choices'] == {}
        assert state['previous_input'] is None and state['input'] is None
        if kind == 'goofspiel': assert state['action'] is None and state['result'] is None


def test_doudizhu_specific_card_identity_still_reaches_native_engine():
    import jev_social_games as cards
    raw = facade.fresh('doudizhu', 42)
    action, ranks = next((action, data[3]) for action, data in cards.dzoptions(raw, 0).items()
                         if data is not None and len(data[3]) == 1)
    card = next(card for card in raw['_hand_card_ids'][0] if cards.dzcardrank(card) == ranks[0])
    with client_for() as client:
        response = client.post('/api/showcases/new', json={'kind': 'doudizhu', 'seed': 42})
        assert response.status_code == 200, response.text
        state = response.json()
        response = act(client, state, action=action, card_ids=[card])
        assert response.status_code == 200, response.text
        state = response.json()
        assert card not in state['world']['hand_card_ids']
        assert state['world']['history'][0]['card_ids'] == [card]
