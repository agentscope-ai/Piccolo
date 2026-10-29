"""Real native rule turns through the public API, with no provider or fixture server."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.engine import get_engine
from blink_arena.schemas import AppConfig
from blink_arena.social_duels import SocialDuel


def test_doudizhu_rule_only_uses_current_hand_and_public_cards():
    game = SocialDuel(get_engine('doudizhu').reset(42))
    for seat in range(3):
        game.world['turn'] = seat
        # Each leading seat has the same legal opening before and after we
        # replace the other players' hidden cards.
        game.world['leader'] = seat
        expected = game.rule_action()
        other = SocialDuel(deepcopy(game.world))
        for index in range(3):
            if index != seat:
                other.world['hands'][index] = [17] * len(game.world['hands'][index])
        assert other.rule_action() == expected


@pytest.mark.parametrize('kind', ['doudizhu','texas_holdem','zha_jin_hua','property_tycoon',
                                 'checkers','xiangqi','uno','liars_dice','chess',
                                 'othello_6x6','hex_7x7','dots_and_boxes_3x3'])
def test_rule_seats_progress_without_any_model_connection(kind, tmp_path):
    app = create_app(data=tmp_path, seed=tmp_path/'missing', config=AppConfig(),
                     leaderboard_dir=tmp_path/'leaderboard')
    async def forbidden(*args, **kwargs):
        raise AssertionError('Rule seats must not call the hosted model')
    app.state.providers.server_relays['oneshot-hosted'] = forbidden
    board = get_engine(kind).family == 'board'
    prefix = '/api/game' if board else '/api/showcases'
    with TestClient(app) as client:
        response = client.post(prefix+'/new',json={'kind':kind,'seed':42,'duel':True,'opponent':'human'})
        assert response.status_code == 200, response.text
        state = response.json()
        initial = deepcopy(state)
        rejected = client.post(prefix+('/move' if board else '/step'),json={
            'session_id':state['session_id'],'revision':state['revision'],'model':True,'reference':True})
        assert rejected.status_code == 422
        seen = set()
        for _ in range(18):
            world = state['game' if board else 'world']
            if world.get('winner') or world.get('outcome'):break
            if world.get('handoff'):
                state = client.post('/api/showcases/reveal',json={
                    'session_id':state['session_id'],'revision':state['revision']}).json()
                world = state['world']
            seen.add(world.get('current_player',world.get('player',world.get('turn'))))
            revision = state['revision']
            response = client.post(prefix+('/move' if board else '/step'),json={
                'session_id':state['session_id'],'revision':revision,'reference':True})
            assert response.status_code == 200, (kind,response.text)
            state = response.json()
            assert state['controller'] == 'rule_engine'
            assert state['result'] is None
            assert state['revision'] == revision+1
            assert state['action'] is not None
            if state.get('world',{}).get('handoff'):
                assert state['input'] is None and state['previous_input'] is None
        assert state['revision'] > initial['revision']
        if kind == 'doudizhu':assert seen == {0,1,2}
        elif kind not in ('zha_jin_hua',):assert len(seen) == 2, (kind,seen)
