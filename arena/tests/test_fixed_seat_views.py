"""Seat orientation is display state, independent from the native acting seat."""
import asyncio
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from blink_arena.engine import get_engine
from blink_arena.private_views import fixed_view
from blink_arena.social_duels import SocialDuel
import jev_demo_showcases as facade


@pytest.mark.parametrize('seat', [0, 1, 2])
def test_doudizhu_fixed_seats_keep_hands_and_public_play_positions(seat):
    async def run():
        duel = SocialDuel(get_engine('doudizhu').reset(42))
        order = [seat, (seat+1)%3, (seat+2)%3]
        for actor in range(3):
            duel.handoff = False
            before, record = deepcopy(duel.world), deepcopy(duel.record())
            table = duel.table(seat)
            assert table['view_seat'] == seat and table['active_seat'] == actor
            assert table['seat_ids'] == order
            assert table['hand'] == before['hands'][seat]
            assert table['hand_card_ids'] == before['_hand_card_ids'][seat]
            assert table['opponent_counts'] == [len(before['hands'][i]) for i in order[1:]]
            assert duel.world == before and duel.record() == record
            action = duel.rule_action()
            await duel.step(action)
            table = duel.table(seat)
            assert table['seat_ids'] == order
            assert table['history'][-1]['player'] == order.index(actor)
            if seat != duel.actor:
                assert table['hand'] == duel.world['hands'][seat]
            assert 'hands' not in table and 'deck' not in table
    asyncio.run(run())


@pytest.mark.parametrize('seat', [0, 1])
def test_poker_pending_callback_does_not_rotate_fixed_view(seat):
    async def run():
        duel = SocialDuel(get_engine('texas_holdem').reset(42))
        original = deepcopy(duel.table(seat)['hand'])
        await duel.step('call')
        duel.handoff = False
        obs = duel.record()['state']['observation']
        table = duel.table(seat)
        assert table['hand'] == original
        assert table['board'] == obs['board'] and len(table['board']) == 3
        assert table['stacks'] == [obs['player_stack'],obs['own_stack']][::1 if seat==0 else -1]
        assert table['active_seat'] == 1 and table['view_seat'] == seat
        assert table['seat_ids'] == [seat,1-seat] and 'opponent_hand' not in table
        await duel.step('bet20')
        duel.handoff = False
        assert duel.table(seat)['hand'] == original
        assert duel.table(seat)['view_seat'] == seat and duel.table(seat)['active_seat'] == 0
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['uno','liars_dice'])
@pytest.mark.parametrize('seat', [0,1])
def test_native_private_view_stays_on_requested_seat(kind, seat):
    engine = get_engine(kind)
    world = engine.reset(42,{'opponent':'human'})
    if world.get('handoff'):
        import jev_agent_games
        world = jev_agent_games.reveal(world)
    original = fixed_view(world,seat)
    own_key = 'hand' if kind=='uno' else 'dice'
    before = deepcopy(world)
    decision = deepcopy(engine.observe(world))
    assert original['seat'] == seat and len(original[own_key]) > 0
    assert {k:v for k,v in world.items() if k!='_rng'} == {k:v for k,v in before.items() if k!='_rng'}
    if '_rng' in world:assert world['_rng'].getstate() == before['_rng'].getstate()
    assert engine.observe(world) == decision
    # Advance the other seat, then prove the observer's private items did not
    # become the acting player's private items. Draw keeps UNO's other hand intact.
    action = next((a for a,v in engine.legal_actions(world).items() if v=='draw'), next(iter(engine.legal_actions(world))))
    after = engine.step(world, action)
    if isinstance(after, tuple):after = after[0]
    after = engine.environment.reveal(after) if after.get('handoff') and kind=='uno' else after
    if kind=='liars_dice' and after.get('handoff'):
        import jev_agent_games
        after = jev_agent_games.reveal(after)
    view = fixed_view(after,seat)
    assert view['seat'] == seat and len(view[own_key]) > 0
    if seat == 1:assert view[own_key] == original[own_key]


@pytest.mark.parametrize('kind', ['doudizhu','texas_holdem','zha_jin_hua','property_tycoon','uno','liars_dice'])
def test_fixed_view_http_persists_and_can_be_changed_without_playing(kind):
    async def unused(*args):raise AssertionError('No model needed')
    app=FastAPI();facade.install(app,'',lambda seq:None,unused,None)
    with TestClient(app) as client:
        response=client.post('/api/showcases/new',json={'kind':kind,'seed':42,'duel':True,'opponent':'human','view_seat':1})
        assert response.status_code==200,response.text
        state=response.json()
        def view(s):
            return s['world'].get('table',s['world'].get('fixed_view'))
        def seat(s):return view(s).get('view_seat',view(s).get('seat'))
        assert seat(state)==1
        for _ in range(4):
            if state['world'].get('outcome'):break
            base={'session_id':state['session_id'],'revision':state['revision']}
            if state['world'].get('handoff'):
                state=client.post('/api/showcases/reveal',json=base).json()
                base['revision']=state['revision']
            response=client.post('/api/showcases/step',json={**base,'reference':True})
            assert response.status_code==200,response.text
            state=response.json();assert seat(state)==1
        base={'session_id':state['session_id'],'revision':state['revision']}
        invalid=client.post('/api/showcases/view',json={**base,'view_seat':3 if kind=='doudizhu' else 2})
        assert invalid.status_code==422
        response=client.post('/api/showcases/view',json={**base,'view_seat':0})
        assert response.status_code==200,response.text
        switched=response.json()
        assert seat(switched)==0 and switched['revision']==state['revision']
        assert switched['choices']==state['choices'] and switched['input']==state['input']
