"""Playground targets change real terminals, leaving fixed engine baselines intact."""
from copy import deepcopy
import pytest

from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.engine import get_engine
from blink_arena.schemas import AppConfig
import jev_snake_realtime as snake


def test_third_apple_wins_only_the_three_apple_episode():
    small=snake.fresh(101,food_target=3)
    small.update(score=2,body=[[8-i,7] for i in range(7)],food=[9,7],obstacles=[],
                 direction='right',pending_direction='right',started=True)
    before=deepcopy(small)
    record=snake.as_record(small)
    assert '3颗' in record['state']['rules'] and '3 apples' in record['questions']['decision']['instructions']
    won=snake.advance_idle(small,1.1)
    assert small==before
    assert won['score']==3 and won['outcome']=='win' and not snake.choices(won)
    old=deepcopy(small);old.update(food_target=6,target_food=6,engine_revision=snake.REVISION)
    continued=snake.advance_idle(old,1.1)
    assert continued['score']==3 and continued['outcome'] is None
    assert snake.fresh(101)['food_target']==6


def test_xiangqi_can_play_beyond_old_400_ply_cap():
    engine=get_engine('xiangqi');state=engine.reset(101,{'max_steps':500})
    # Legal horse development/retreat cycles, exercising the native journal.
    moves=['(9,1)-(7,2)','(0,1)-(2,2)','(7,2)-(9,1)','(2,2)-(0,1)']
    for index in range(401):
        action=next(a for a,label in engine.legal_actions(state).items() if label.endswith(moves[index%4]))
        state=engine.raw_step(state,action)
        if index==399:
            assert engine.outcome(state) is None
            old=deepcopy(state);old.pop('max_steps')
            assert engine.outcome(old)=='budget_exhausted'
    assert state['steps']==401 and engine.outcome(state) is None
    assert engine.public(state)['max_steps']==500
    assert engine.limit==400


@pytest.mark.parametrize('limit,previous',[(480,240),(960,480)])
def test_sudoku_can_play_beyond_previous_action_cap_without_changing_puzzle(limit,previous):
    engine=get_engine('sudoku')
    state=engine.reset(101,{'max_steps':limit})
    original=engine.reset(101,{})
    assert engine.public(state)['board']==engine.public(original)['board']
    cell=next(iter(engine.legal_actions(state)))
    for index in range(previous+1):
        state=engine.raw_step(state,cell if index%2==0 else 'back')
        if index==previous-1:
            old=deepcopy(state);old['max_steps']=previous
            assert engine.outcome(old)=='budget_exhausted'
    assert state['steps']==previous+1 and engine.outcome(state) is None
    assert engine.public(state)['max_steps']==limit and engine.limit==240


def test_http_playground_sessions_and_model_observations_agree(tmp_path):
    app=create_app(data=tmp_path,config=AppConfig())
    with TestClient(app) as client:
        response=client.post('/api/showcases/new',json={'kind':'snake_navigation','seed':101})
        assert response.status_code==200
        game=response.json()
        assert game['world']['food_target']==3 and '3 个' in game['goal']
        assert game['input']['state']['food_target']==3
        response=client.post('/api/v1/sessions',json={'game':'snake_navigation','seed':101})
        assert response.status_code==201
        game=response.json()
        assert game['state']['food_target']==game['decision']['observation']['food_target']==3
        assert '3 个' in game['engine']['goal']
        assert '3 apples' in game['decision']['question']['instructions']
        for route in ('/api/engines/snake_navigation','/api/v1/games'):
            descriptor=client.get(route).json()
            if 'games' in descriptor:descriptor=next(e for e in descriptor['games'] if e['kind']=='snake_navigation')
            assert '3 个' in descriptor['goal']
        response=client.post('/api/showcases/new',json={'kind':'xiangqi','seed':101})
        assert response.status_code==200
        game=response.json()
        assert game['world']['max_steps']==500
        assert game['input']['state']['observation']['max_steps']==500
        response=client.post('/api/showcases/new',json={'kind':'sudoku','seed':101})
        assert response.status_code==200
        game=response.json()
        assert game['world']['max_steps']==960
        assert game['input']['state']['observation']['max_steps']==960
        response=client.post('/api/v1/sessions',json={'game':'sudoku','seed':101})
        assert response.status_code==201
        assert response.json()['state']['max_steps']==response.json()['engine']['limit']==960
        response=client.post('/api/v1/sessions',json={'game':'chess','seed':101})
        assert response.status_code==201
        game=response.json()
        assert game['state']['max_plies']==512 and game['engine']['limit']==512
        assert get_engine('chess').limit==256
        for route,field in (('/api/showcases','kind'),('/api/v1/games','kind'),('/api/engines','kind')):
            response=client.get(route)
            assert response.status_code==200
            data=response.json()
            items=data if isinstance(data,list) else data.get('games',data.get('engines'))
            limits={item[field]:item['engine']['limit'] if 'engine' in item else item['limit'] for item in items}
            assert limits['sudoku']==960 and limits['terraria_survival']==1200
        assert get_engine('sudoku').limit==240
        assert get_engine('terraria_survival').limit==300
