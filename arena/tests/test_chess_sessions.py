"""Exercise chess through the production session API and browser relay seam."""
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.engine import get_engine
from blink_arena.schemas import AppConfig, DecisionOutput


def new(client, seed=0):
    response = client.post('/api/v1/sessions', json={'game': 'chess', 'seed': seed})
    assert response.status_code == 201, response.text
    return response.json()


def advance(client, session, **action):
    return client.post('/api/v1/sessions/' + session['session_id'] + '/steps',
                       json={'revision': session['revision'], **action})


def model(client, app, *, illegal=False):
    response = client.post('/api/v1/connections', json={'model_id': 'chess-fixture',
        'name': 'Chess test fixture', 'served_model': 'fixture',
        'adapter': 'decision', 'transport': 'browser'})
    assert response.status_code == 201, response.text
    calls = []

    async def decide(request):
        calls.append(request.model_dump(mode='json'))
        options = request.question.options
        action = 'a1a8' if illegal else ('e2e4' if any(o.id == 'e2e4' for o in options) else options[0].id)
        return DecisionOutput(request_id=request.request_id, model=request.model, action=action,
            probabilities=None if illegal else {o.id: float(o.id == action) for o in options})

    app.state.providers.browser_relays['chess-fixture'] = decide
    return calls


def test_registry_remains_lazy_and_legacy_chess_replay_remains_available():
    script = 'import sys, blink_arena.engine; assert "chess" not in sys.modules; assert "pyspiel" not in sys.modules'
    subprocess.run([sys.executable, '-c', script], check=True)
    engine = get_engine('chess')
    assert not engine.internal and engine.family == 'strategy' and engine.renderer == 'chess'
    assert engine.rl_runner == 'jev_chess_rl:play' and engine.rl_verify == 'jev_chess_rl:verify'
    from jev_engine_registry import get_archived_engine
    archived = get_archived_engine('chess')
    old = archived.reset(0)
    assert archived.archived and get_engine('chess', old) is archived
    assert archived.step(old, 'e2e4')['_moves'] == ['e2e4']


def test_chess_model_preserves_actual_input_probabilities_and_action_ownership(tmp_path):
    app = create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        calls = model(client, app)
        initial = new(client)
        assert len(initial['legal_actions']) == 20 and initial['state']['current_player'] == 0
        response = advance(client, initial, model_id='chess-fixture')
        assert response.status_code == 200, response.text
        moved = response.json()
        assert moved['action'] == 'e2e4' and moved['controller'] == 'model' and not moved['forced']
        assert moved['state']['current_player'] == 1 and moved['state']['history'][-1]['controller'] == 'model'
        assert moved['previous_decision'] == initial['decision']
        assert moved['previous_input']['option'] == initial['legal_actions']
        assert calls and all(c['observation'] == initial['decision']['observation'] for c in calls)
        expected = list(initial['legal_actions'])
        # The frontend intentionally probes three shuffled option orders. Each
        # probe keeps the same UCI/label mapping and reports its actual input.
        assert len(calls) == 3
        assert all({o['id']: o['label'] for o in c['question']['options']} == initial['legal_actions'] for c in calls)
        result = moved['result']
        assert result['value'] == 'e2e4' and result['probability_coverage']['complete']
        assert {r['value'] for r in result['distribution']} == set(expected)
        assert sum(r['probability'] for r in result['distribution']) == 1
        assert result['model_input']['schema_input']['observation'] == initial['decision']['observation']
        assert result['model_input']['schema_input'] in calls
        assert initial['state']['fen'] != moved['state']['fen']
        replay = client.get('/api/v1/sessions/' + initial['session_id'] + '/replay').json()
        assert replay['steps'][0]['decision'] == initial['decision']
        assert replay['steps'][0]['controller'] == 'model'


def test_chess_explicit_rule_opponent_never_calls_model_or_records_student_action(tmp_path):
    app = create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        calls = model(client, app)
        initial = new(client)
        response = advance(client, initial, reference=True)
        assert response.status_code == 200, response.text
        moved = response.json()
        assert calls == [] and moved['result'] is None and moved['controller'] == 'reference'
        assert moved['action'] in initial['legal_actions']
        assert moved['state']['history'][-1]['controller'] == 'rule_engine'
        assert moved['state']['controller_counts']['rule_opponent_moves'] == 1
        assert moved['state']['controller_counts']['model_decisions'] == 0
        assert moved['state']['controller_counts']['rule_takeover_count'] == 0
        assert advance(client, moved, reference=True, action='e7e5').status_code == 422
        assert advance(client, moved, reference=True, model_id='chess-fixture').status_code == 422
        assert advance(client, moved, reference=True, reveal=True).status_code == 422


def test_chess_invalid_model_response_is_not_replaced_by_rule_action(tmp_path):
    app = create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        calls = model(client, app, illegal=True)
        initial = new(client)
        response = advance(client, initial, model_id='chess-fixture')
        assert response.status_code == 502 and calls
        current = client.get('/api/v1/sessions/' + initial['session_id']).json()
        assert current['revision'] == initial['revision'] and current['state'] == initial['state']
        replay = client.get('/api/v1/sessions/' + initial['session_id'] + '/replay').json()
        assert replay['steps'] == []


def test_chess_seed_conditions_and_mate_via_actual_http_actions(tmp_path):
    with TestClient(create_app(data=tmp_path, config=AppConfig())) as client:
        initial = new(client)
        alternate = new(client, 42)
        assert initial['state']['fen'] != alternate['state']['fen']
        assert alternate['state'] == new(client, 42)['state']
        state = initial
        for action in ['f2f3', 'e7e5', 'g2g4', 'd8h4']:
            response = advance(client, state, action=action)
            assert response.status_code == 200, response.text
            state = response.json()
        assert state['terminal'] and state['state']['outcome'] == 'loss'
        assert state['state']['termination'] == 'checkmate' and state['state']['result'] == '0-1'
        assert state['decision'] is None and state['legal_actions'] == {}
        assert advance(client, state, action='e2e4').status_code == 409


def test_unsupported_reference_action_is_rejected_without_affecting_other_game(tmp_path):
    with TestClient(create_app(data=tmp_path, config=AppConfig())) as client:
        initial = client.post('/api/v1/sessions', json={'game': 'jump_jump', 'seed': 42}).json()
        assert advance(client, initial, reference=True).status_code == 422
        current = client.get('/api/v1/sessions/' + initial['session_id']).json()
        assert current == initial


@pytest.mark.parametrize('kind', ['uno'])
def test_previous_chess_input_fields_cannot_disclose_private_game_handoff(tmp_path, kind):
    app=create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        initial=client.post('/api/v1/sessions',json={'game':kind,'seed':42}).json()
        action=next(iter(initial['legal_actions']))
        response=advance(client,initial,action=action)
        assert response.status_code==200,response.text
        moved=response.json()
        assert moved['state']['handoff']
        assert moved['previous_input'] is None and moved['previous_decision'] is None
        assert moved['result'] is None
        replay=client.get('/api/v1/sessions/'+initial['session_id']+'/replay').json()
        assert replay['private_history_redacted']
        assert replay['steps'][0]['decision'] is None and replay['steps'][0]['before_state'] is None
        # Internal audit remains complete; only the public shared-seat projection
        # is redacted. RL tickets use their separate captured-input protocol.
        assert app.state.sessions.items[initial['session_id']]['trace'][0]['decision'] is not None
