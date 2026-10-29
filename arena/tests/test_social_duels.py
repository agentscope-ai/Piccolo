import asyncio
import copy

import pytest

from blink_arena.social_duels import SocialDuel, KINDS
from blink_arena.engine import get_engine
import jev_eval_social_opponents as opponents
import jev_social_games as social


@pytest.mark.parametrize('kind', sorted(KINDS))
def test_duel_turns_preserve_native_engine_settlement(kind):
    async def run():
        engine=get_engine(kind);duel=SocialDuel(engine.reset(42))
        seen=set()
        for outer in range(10):
            if duel.world.get('outcome'):break
            base=copy.deepcopy(duel.world)
            options=duel.record()['questions']['decision']['criteria']
            action=next((a for a in ('call','raise','next','skip','roll') if a in options),next(iter(options)))
            seen.add(duel.actor)
            if kind=='doudizhu':
                expected=copy.deepcopy(base)
                if expected['turn']==0:expected['steps']+=1
                social.dzplay(expected,expected['turn'],action);expected['history']=expected['history'][-12:]
                await duel.step(action)
                assert duel.world==expected
            else:
                responses=[]
                async def choose(record,ordinal):
                    opts=record['questions']['decision']['criteria']
                    a=next((a for a in ('call','check','buy','skip') if a in opts),next(iter(opts)))
                    responses.append(a);return a
                expected,_=await opponents.step(base,action,choose)
                await duel.step(action)
                for answer in responses:
                    assert duel.actor==1
                    seen.add(duel.actor)
                    assert duel.public()['observation'] is None if duel.handoff else True
                    duel.handoff=False
                    await duel.step(answer)
                assert duel.world==expected
                assert duel.pending is None
            if duel.handoff:
                assert not duel.payload()['choices'] and duel.payload()['input'] is None
                duel.handoff=False
        assert 0 in seen
        if kind!='zha_jin_hua':assert 1 in seen
    asyncio.run(run())


def test_farmer_prompt_does_not_contain_other_hands():
    async def run():
        duel=SocialDuel(get_engine('doudizhu').reset(42))
        await duel.step(next(iter(duel.record()['questions']['decision']['criteria'])))
        assert duel.actor==1 and duel.handoff
        duel.handoff=False
        record=duel.record();obs=record['state']['observation']
        assert obs['hand']==duel.world['hands'][1]
        assert 'hands' not in obs and 'deck' not in obs and 'other_hand_counts' in obs
    asyncio.run(run())


@pytest.mark.parametrize('kind', sorted(KINDS))
def test_table_is_a_private_read_only_projection(kind):
    duel = SocialDuel(get_engine(kind).reset(42))
    before = copy.deepcopy(duel.world)
    decision = duel.record()
    table = duel.public()['table']
    assert table['kind'] == kind and table['view_seat'] == 0
    assert not {'hands', 'deck', 'seed', '_hand_card_ids'} & table.keys()
    assert 'opponent_hand' not in table
    assert duel.world == before and duel.record() == decision
    if kind in ('doudizhu', 'texas_holdem'):
        assert table['hand'] == before['hands'][0]
    elif kind == 'zha_jin_hua':
        assert table['hand'] is None
    duel.handoff = True
    hidden = duel.payload()
    assert hidden['input'] is None and not hidden['choices']
    assert not hidden['world']['table'].get('hand')
    assert 'hand_card_ids' not in hidden['world']['table']


def test_doudizhu_table_rotates_seats_and_preserves_physical_cards():
    async def run():
        duel = SocialDuel(get_engine('doudizhu').reset(42))
        for actor in range(3):
            assert duel.actor == actor
            duel.handoff = False
            table = duel.table()
            assert table['hand'] == duel.world['hands'][actor]
            assert table['hand_card_ids'] == duel.world['_hand_card_ids'][actor]
            assert table['opponent_counts'] == [len(duel.world['hands'][(actor+i)%3]) for i in (1,2)]
            options = duel.record()['questions']['decision']['criteria']
            action = next((a for a in sorted(options, key=lambda a:(len(a),a)) if a != 'pass'), 'pass')
            ranks = [] if action == 'pass' else list(map(int, action.split(',')))
            available = list(table['hand_card_ids'])
            selected = []
            for rank in ranks:
                card = next(c for c in available if social.dzcardrank(c) == rank)
                selected.append(card); available.remove(card)
            await duel.step(action, card_ids=selected if action != 'pass' else None)
            hidden = duel.table()
            assert hidden['hand'] == [] and 'hand_card_ids' not in hidden
            if action != 'pass':assert hidden['last_card_ids'] == selected
            assert hidden['history'][-1]['player'] == 2
            if action != 'pass':assert hidden['leader'] == 2
    asyncio.run(run())


def test_invalid_physical_card_selection_does_not_change_duel():
    async def run():
        duel = SocialDuel(get_engine('doudizhu').reset(42))
        before = copy.deepcopy(duel.world)
        action = next(iter(duel.record()['questions']['decision']['criteria']))
        with pytest.raises(ValueError):
            await duel.step(action, card_ids=[duel.world['_hand_card_ids'][1][0]])
        assert duel.world == before and duel.actor == 0
    asyncio.run(run())


def test_poker_pending_table_uses_new_public_board_and_current_chips():
    async def run():
        duel = SocialDuel(get_engine('texas_holdem').reset(42))
        await duel.step('call')
        assert duel.actor == 1 and duel.handoff
        assert duel.world['board'] == []  # Native callback has not committed yet.
        hidden = duel.table()
        assert len(hidden['board']) == 3 and hidden['hand'] == []
        duel.handoff = False
        obs = duel.record()['state']['observation']
        table = duel.table()
        assert table['board'] == obs['board']
        assert table['opponent_last'] == '跟注' and table['event'] == ''
        assert table['stacks'] == [obs['own_stack'], obs['player_stack']]
        assert table['pot'] == obs['pot'] and table['hand'] == obs['own_hand']
        assert 'opponent_hand' not in table
        await duel.step('bet20')
        assert duel.actor == 0 and duel.handoff
        assert duel.table()['to_call'] == 20
        duel.handoff = False
        await duel.step('fold')
        assert duel.world['outcome'] and 'opponent_hand' not in duel.table()
    asyncio.run(run())


def test_poker_showdown_reveals_both_hands():
    async def run():
        duel = SocialDuel(get_engine('texas_holdem').reset(42))
        for _ in range(12):
            if duel.world['outcome']:break
            duel.handoff = False
            options = duel.record()['questions']['decision']['criteria']
            await duel.step('check' if 'check' in options else 'call')
        table = duel.table()
        assert table['showdown'] and len(table['board']) == 5
        assert table['hand'] == duel.world['hands'][0]
        assert table['opponent_hand'] == duel.world['hands'][1]
    asyncio.run(run())


def test_property_pending_table_rotates_current_public_position():
    async def run():
        duel = SocialDuel(get_engine('property_tycoon').reset(42))
        for _ in range(30):
            options = duel.record()['questions']['decision']['criteria']
            await duel.step(next((a for a in ('roll','skip','next') if a in options),next(iter(options))))
            if duel.pending:break
        assert duel.pending
        obs = duel.record()['state']['observation']
        table = duel.table()
        assert table['positions'][0] == obs['position']
        assert table['cash'] == list(reversed(obs['cash']))
        assert table['owners'] == {key:1-owner for key,owner in obs['owners'].items()}
    asyncio.run(run())


def test_duel_http_forwards_selected_suits_and_rejects_other_cards():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import jev_demo_showcases as facade
    async def unused(*args):raise AssertionError('No model call is needed')
    app = FastAPI()
    facade.install(app, '', lambda seq: None, unused, None)
    with TestClient(app) as client:
        state = client.post('/api/showcases/new', json={'kind':'doudizhu','seed':42,'duel':True}).json()
        table = state['world']['table']
        rank = min(table['hand']); ids = table['hand_card_ids']
        chosen = next(c for c in reversed(ids) if social.dzcardrank(c) == rank)
        move = {'session_id':state['session_id'],'revision':state['revision'],'action':str(rank)}
        foreign = next(c for c in range(54) if c not in ids)
        assert client.post('/api/showcases/step',json={**move,'card_ids':[foreign]}).status_code == 422
        response = client.post('/api/showcases/step',json={**move,'card_ids':[chosen]})
        assert response.status_code == 200
        after = response.json()
        assert after['world']['table']['last_card_ids'] == [chosen]
        assert after['world']['table']['hand'] == [] and after['input'] is None
        assert after['revision'] == state['revision']+1


def test_three_card_pending_and_showdown_views():
    async def run():
        duel = SocialDuel(get_engine('zha_jin_hua').reset(42))
        assert duel.table()['hand'] is None
        await duel.step('peek')
        assert duel.table()['hand'] == duel.world['hands'][0]
        await duel.step('call')
        assert duel.pending and duel.table()['hand'] is None
        duel.handoff = False
        obs = duel.record()['state']['observation']
        table = duel.table()
        assert table['hand'] == obs['own_hand'] and 'opponent_hand' not in table
        assert table['pot'] == obs['pot'] and table['stacks'][0] == obs['own_stack']
        await duel.step('call')
        duel.handoff = False
        await duel.step('compare')
        table = duel.table()
        assert table['showdown'] and table['opponent_hand'] == duel.world['hands'][1]
    asyncio.run(run())
