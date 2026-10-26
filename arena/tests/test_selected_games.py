"""Native engines, hidden-information boundaries, HTTP and RL for selected games."""
import asyncio
from copy import deepcopy
import json
import random
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from blink_arena.engine import get_engine, list_engines, Environment
from blink_arena.app import create_app
from blink_arena.schemas import AppConfig
import jev_selected_games as games
from jev_selected_games_rl import play, verify
from jev_gameplay_reward_contract import default_config, validate_episode

KINDS = tuple(games.GAMES)

@pytest.mark.parametrize('kind', KINDS)
def test_native_six_methods_json_choice_seed_and_no_mutation(kind):
    engine=get_engine(kind);assert isinstance(engine.environment,Environment)
    state=engine.reset(42);before=deepcopy(state);record=engine.observe(state)
    assert record==json.loads(json.dumps(record,ensure_ascii=False))
    assert record['questions']['decision']['criteria']==engine.legal_actions(state)
    assert record['questions']['decision']['option_order']==list(engine.legal_actions(state))
    assert 1<=len(engine.legal_actions(state))<=254
    assert engine.public(state)==engine.public(engine.reset(42))
    assert '_seed' not in json.dumps(record['state']) and '_history' not in json.dumps(record['state'])
    with pytest.raises(ValueError):engine.step(state,'not-an-action')
    after=engine.step(state,next(iter(engine.legal_actions(state))))
    assert state==before and after['steps']==state['steps']+1
    assert engine.public(after)==engine.public(engine.step(json.loads(json.dumps(state)),next(iter(engine.legal_actions(state)))))
    assert engine.rl_runner and engine.rl_verify and not engine.sft_export_prohibited


def test_no_additional_collected_games_are_registered():
    assert {e.kind for e in list_engines() if e.family=='selected'}==set(KINDS)
    assert len(list_engines())==35


def test_rng_restoration_and_concurrent_seeds():
    from concurrent.futures import ThreadPoolExecutor
    before=random.getstate()
    def run(seed):
        engine=get_engine('guess_the_number');s=engine.reset(seed)
        return engine.public(engine.step(s,'[10]'))
    expected=[run(seed) for seed in range(10)]
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(run,range(10)))==expected
    assert random.getstate()==before


@pytest.mark.parametrize('kind', ['guess_the_number','minesweeper'])
def test_initial_hidden_targets_never_change_candidates_or_observation(kind):
    engine=get_engine(kind)
    a,b=engine.reset(42),engine.reset(43)
    assert engine.observe(a)['state']==engine.observe(b)['state']
    assert engine.legal_actions(a)==engine.legal_actions(b)


def test_sudoku_candidates_ignore_solution_and_require_explicit_cell(monkeypatch):
    e=get_engine('sudoku');s=e.reset(42)
    cell=next(iter(e.legal_actions(s)));s=e.step(s,cell)
    native,selected,rng=games._load(s);fake=deepcopy(native);fake.full_grid=[[9]*9 for _ in range(9)]
    before=e.legal_actions(s);view=e.observe(s)['state']
    monkeypatch.setattr(games,'_runtime',lambda *args:(fake,selected,rng))
    assert before==e.legal_actions(s) and view==e.observe(s)['state']
    assert all(k=='back' or k.startswith('fill:') for k in before)


def test_uno_opponent_hand_and_deck_do_not_enter_observation(monkeypatch):
    e=get_engine('uno');s=e.reset(42);native,selected,rng=games._load(s)
    before=e.observe(s);fake=deepcopy(native)
    fake.game.players[1].hand[0],fake.game.dealer.deck[0]=fake.game.dealer.deck[0],fake.game.players[1].hand[0]
    monkeypatch.setattr(games,'_runtime',lambda *args:(fake,selected,rng))
    assert e.observe(s)==before


@pytest.mark.parametrize('color',('r','g','b','y'))
def test_uno_wild_public_color_agrees_with_native_rules(color):
    e=get_engine('uno');s=e.reset(42)
    label=color+'-wild'
    action=next(a for a,value in e.legal_actions(s).items() if value==label)
    s=e.environment.reveal(e.step(s,action))
    native,_,_=games._load(s)
    assert e.public(s)['target']==label==native.game.round.target.get_str()
    assert e.observe(s)['state']['observation']['target']==label
    for value in e.legal_actions(s).values():
        assert value=='draw' or 'wild' in value or value.startswith(color+'-')


def test_removed_rps_is_not_registered(tmp_path):
    assert 'iterated_rps' not in games.GAMES
    with pytest.raises((KeyError, ValueError)):
        get_engine('iterated_rps')
    with TestClient(create_app(data=tmp_path,config=AppConfig())) as client:
        assert 'iterated_rps' not in {g['kind'] for g in client.get('/api/v1/games').json()['games']}
        for path,body in (('/api/showcases/new',{'kind':'iterated_rps','seed':42}),
                          ('/api/v1/sessions',{'game':'iterated_rps','seed':42})):
            assert client.post(path,json=body).status_code in (400,404,422)


@pytest.mark.parametrize('kind', KINDS)
def test_frontend_http_and_versioned_session_contract(tmp_path,kind):
    with TestClient(create_app(data=tmp_path,config=AppConfig())) as c:
        listing=c.get('/api/v1/games').json()['games'];assert kind in {x['kind'] for x in listing}
        r=c.post('/api/showcases/new',json={'kind':kind,'seed':42});assert r.status_code==200,r.text
        s=r.json();a=next(iter(s['choices']))
        moved=c.post('/api/showcases/step',json={'session_id':s['session_id'],'revision':s['revision'],'action':a});assert moved.status_code==200,moved.text
        moved=moved.json()
        if kind in games.PRIVATE:
            assert moved['world']['handoff'] and moved['choices']=={} and moved['input'] is None and moved['previous_input'] is None
            assert 'hand' not in moved['world']
            shown=c.post('/api/showcases/reveal',json={'session_id':moved['session_id'],'revision':moved['revision']});assert shown.status_code==200 and shown.json()['choices']
        r=c.post('/api/v1/sessions',json={'game':kind,'seed':42});assert r.status_code==201,r.text
        s=r.json();a=next(iter(s['legal_actions']))
        r=c.post('/api/v1/sessions/'+s['session_id']+'/steps',json={'revision':0,'action':a});assert r.status_code==200,r.text
        if kind in games.PRIVATE:
            r=c.post('/api/v1/sessions/'+s['session_id']+'/steps',json={'revision':1,'reveal':True});assert r.status_code==200 and r.json()['legal_actions']


class Policy:
    def __init__(self):self.records=[]
    async def policy_action(self,record,*args):
        self.records.append(deepcopy(record));values=list(record['questions']['decision']['criteria'])
        action=values[-1] if record['metadata']['sub_domain']=='go' else values[0]
        return action,{'forced':False,'origin':'student_model','candidate_values':values,
                       'old_probabilities':[1/len(values)]*len(values),'selected_index':values.index(action)}
    async def qwen(self,kind,seed,ordinal,record):return await self.policy_action(record)
    def journal(self,*args):pass


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('side',[0,1])
def test_rl_seat_control_exact_replay_and_trace_tampering(kind,side):
    e=get_engine(kind)
    if side>=e.seat_count:return
    async def run():
        p=Policy();job={'kind':kind,'seed':42,'side':side,'mode':e.opponent_modes[0],
                        'episode_id':'fixture-'+kind,'max_decisions':4}
        initial,final,trace,outcome,extra=await play(p,job)
        assert trace and all(row['actor']==side for row in trace)
        assert verify(job,initial,final,extra,trace)
        assert verify(job,*json.loads(json.dumps([initial,final,extra,trace])))
        changed=deepcopy(trace);changed[0]['record']['state']['rules']='tampered'
        with pytest.raises(ValueError):verify(job,initial,final,extra,changed)
        assert outcome in ('win','loss','draw','budget_exhausted')
    asyncio.run(run())


@pytest.mark.parametrize('kind',KINDS)
def test_full_rl_rpc_reward_settlement_and_replay(tmp_path,kind):
    e=get_engine(kind)
    with TestClient(create_app(data=tmp_path,config=AppConfig(),rollout_options={'decision_timeout':10})) as c:
        start=c.post('/api/v1/rollouts',json={'episode_id':'fixture-'+kind,'game':kind,'seed':42,
            'policy_version':'fixture-only','request_token':'test-'+kind,'max_decisions':3,
            'mode':e.opponent_modes[0],'side':0})
        assert start.status_code==201,start.text
        ident=start.json()['rollout_id'];after=-1;seen=[]
        for _ in range(10):
            reply=c.get(f'/api/v1/rollouts/{ident}/next-decision',params={'after':after,'timeout':5})
            assert reply.status_code==200,reply.text
            reply=reply.json();ticket=reply.get('ticket')
            if ticket is None:
                assert reply.get('result_available');break
            values=ticket['candidate_values'];action=values[0]
            answer={'ticket_id':ticket['ticket_id'],'request_token':ticket['request_token'],
                'policy_version':ticket['policy_version'],'action':action,
                'policy':{'origin':'student_model','forced':False,'candidate_values':values,
                          'old_probabilities':[1/len(values)]*len(values),'selected_index':0,
                          'sampling_epsilon':0.,'sampling_temperature':1.}}
            response=c.post(f'/api/v1/rollouts/{ident}/answers',json=answer);assert response.status_code==200,response.text
            seen.append(ticket);after=ticket['sequence']
        result=c.get(f'/api/v1/rollouts/{ident}/result');assert result.status_code==200,result.text
        row=result.json();assert row['status']=='complete',row
        assert row['replay_verified'] and row['on_policy'] and row['policy_origin']=='student'
        assert len(seen)==sum(not t['policy'].get('forced') for t in row['trace'])
        validate_episode(row,default_config([kind]))



def test_cold_replay_rejects_invalid_native_journal_and_handles_long_games():
    e=get_engine('sudoku');s=e.reset(42)
    while not e.outcome(s):
        options=e.legal_actions(s)
        s=e.step(s,'back' if 'back' in options else next(iter(options)))
    assert s['steps']==240 and e.outcome(s)=='budget_exhausted'
    visible=e.public(s)
    with games._LOCK:games._CACHE.clear()
    assert e.public(json.loads(json.dumps(s)))==visible
    for kind in ('checkers','uno'):
        e=get_engine(kind);bad=e.reset(42)
        bad.update(_history=['invalid'],steps=1)
        with pytest.raises(ValueError):e.public(bad)


def test_go_reaches_native_terminal_through_both_seats():
    async def run():
        for kind in ('go',):
            policy=Policy();job={'kind':kind,'seed':42,'side':0,'mode':'qwen3.8-max','episode_id':'natural-'+kind}
            initial,final,trace,outcome,extra=await play(policy,job)
            assert games._terminal(final)
            assert outcome in ('win','loss','draw')
            assert verify(job,initial,final,extra,trace)
            if kind=='go':assert final['steps']==2
    asyncio.run(run())


def test_public_only_fixture_solves_guess_number_and_sudoku():
    def solve(board):
        board=deepcopy(board)
        def visit():
            empty=next(((r,c) for r in range(9) for c in range(9) if board[r][c]==0),None)
            if empty is None:return True
            r,c=empty
            used=set(board[r])|{board[x][c] for x in range(9)}|{board[x][y] for x in range(r//3*3,r//3*3+3) for y in range(c//3*3,c//3*3+3)}
            for n in range(1,10):
                if n not in used:
                    board[r][c]=n
                    if visit():return True
            board[r][c]=0;return False
        assert visit();return board
    for kind in ('guess_the_number','sudoku'):
        e=get_engine(kind);state=e.reset(42);solution=solve(e.public(state)['board']) if kind=='sudoku' else None
        while not e.outcome(state):
            view=e.observe(state)['state']['observation'];options=e.legal_actions(state)
            if kind=='sudoku':
                action=next(iter(options)) if view['selected'] is None else 'fill:'+str(solution[view['selected'][0]][view['selected'][1]])
            else:
                lo,hi=view['minimum'],view['maximum']
                for guess,hint in view['history']:
                    if hint=='higher':lo=max(lo,guess+1)
                    else:hi=min(hi,guess-1)
                action=f'[{(lo+hi)//2}]'
            state=e.step(state,action)
        assert e.outcome(state)=='win'


def test_frontend_full_episode_evaluator_scores_selected_games(tmp_path):
    from jev_demo_game_evaluation import GameEvaluator
    from jev_demo_arena_episodes import comparison_spec,_score,_termination
    async def predict(record,qid,model=None):
        return {'value':next(iter(record['questions'][qid]['criteria']))}
    async def run():
        evaluator=GameEvaluator(predict,lambda:'fixture',lambda x:(x,{}),'http://127.0.0.1',out=tmp_path)
        for kind in ('guess_the_number','go'):
            result=await evaluator._python(None,kind,42,'rule_engine','fixture')
            assert result['replay_verified']
            assert comparison_spec(kind)['metric']=='native_goal_result'
            score,key,evidence=_score(kind,result)
            _termination(kind,result,evidence)
            assert 0<=score<=1
    asyncio.run(run())
