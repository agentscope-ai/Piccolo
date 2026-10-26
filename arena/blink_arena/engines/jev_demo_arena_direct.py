"""Two registered models acting through existing native non-board engines.

The logical side 0 is the landlord for Dou Dizhu; side 1 controls each farmer
independently using only that farmer's own observation. The caller schedules a
second leg with models swapped. Chance, forced actions, wagers, turns and
settlement remain the existing frontend engine's rules.
"""
from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import jev_agent_games as agent
import jev_demo_showcases as showcases
import jev_eval_social_opponents as social_opponents
import jev_game_seat_control as seat_control
import jev_probability_games as probability
import jev_social_games as social
from jev_demo_game_evaluation import LIMITS

DIRECT_KINDS = frozenset(social.SCENES) | frozenset(probability.SCENES) | {'liars_dice', 'goofspiel'}
REVISION = 'native-two-model-actors-v1'


def _seats(fixture):
    if fixture.get('kind') not in DIRECT_KINDS:
        raise ValueError('unsupported_native_direct_game')
    if (fixture.get('leg') not in (0, 1)
            or fixture.get('a_side') != ('X' if fixture['leg'] == 0 else 'O')):
        raise ValueError('native_direct_seat_mismatch')
    a,b=fixture.get('a'),fixture.get('b')
    if (not isinstance(a,str) or not a or not isinstance(b,str) or not b
            or a==b or 'rule-engine-v1' in (a,b)):
        raise ValueError('native_direct_requires_two_models')
    seats={0:a,1:b} if fixture['leg']==0 else {0:b,1:a}
    if fixture['kind']=='doudizhu':seats[2]=seats[1]
    return seats


def _actor0_record(game):
    record=showcases.as_record(game)
    if game['kind']=='texas_holdem':
        # The shared training contract describes the historical random opponent.
        # This match instead routes its existing check/bet choices to model B.
        record['state']['rules']=record['state']['rules'].replace(
            '对手后续下注金额随机取0/10/20/40，不超筹码。',
            '对手由另一模型控制，在原生过牌/下注0/10/20/40选项中决策，不超筹码。')
    return record


def _public(game):
    if game['kind'] in agent.SCENES:return agent.public(game)
    if game['kind'] in social.SCENES:return social.public(game)
    return probability.public(game)


async def play_direct(predict, fixture):
    """Return an actual terminal match, or raise with completed decision trace.

    predict(record, qid, model=...) is the Arena's identity-checked, three-probe
    predictor. No generic Qwen endpoint or rule policy is selected here.
    """
    seats=_seats(fixture)
    kind,seed=fixture['kind'],fixture['seed']
    trace=[]

    async def choose(record, actor, native_ordinal):
        # Native callbacks can contain tuple card patterns or integer board
        # keys. Match the frontend JSON boundary before schema validation.
        record=seat_control.wire_value(record)
        options=record['questions']['decision']['criteria']
        if len(options)==1:return next(iter(options)),{'forced':True,'origin':'forced_legal'}
        player=seats[actor]
        result=await predict(copy.deepcopy(record),'decision',model=player)
        if not isinstance(result,dict) or result.get('model')!=player:
            raise ValueError('native_direct_model_identity_mismatch')
        action=result.get('value')
        if not isinstance(action,str) or action not in options:
            raise ValueError('native_direct_illegal_action')
        stability=result.get('decision_stability') or {}
        if stability.get('repeat_count')!=3 or len(stability.get('samples',[]))!=3:
            raise ValueError('native_direct_three_samples_required')
        receipt={'ordinal':len(trace),'native_ordinal':native_ordinal,
                 'actor':actor,'player':player,'action':action,
                 'origin':'model','model_call':True,'model':player,
                 'served_model':result.get('served_model'),
                 'latency_seconds':result.get('latency_seconds'),
                 'decision_stability':copy.deepcopy(stability),
                 'input':copy.deepcopy(record)}
        trace.append(receipt)
        return action,{'forced':False,'origin':'model','decision_stability':copy.deepcopy(stability)}

    try:
        if kind in ('liars_dice','goofspiel'):
            game=agent.fresh(kind,seed,'human')
            initial=_public(game)
            for ordinal in range(LIMITS[kind]):
                if agent.finished(game):break
                if game['handoff']:game=agent.reveal(game)
                options=agent.choices(game)
                if not options:raise ValueError('nonterminal_native_game_without_actions')
                actor=agent.actor(game)
                if len(options)==1:action=next(iter(options))
                else:action,_=await choose(showcases.as_record(game),actor,ordinal)
                game=await asyncio.to_thread(agent.step,game,action)
            outcome=agent.public(game).get('outcome')
            extra={'role_asymmetry':'sealed_simultaneous_bids' if kind=='goofspiel' else 'alternating_private_dice',
                   'native_actor_control':True}
        else:
            native=SimpleNamespace(fresh=showcases.fresh,choices=showcases.choices,
                as_record=_actor0_record,step=showcases.step,social=social,
                probability=probability,social_opponents=social_opponents,LIMITS=LIMITS)
            class Models:
                async def policy_action(self,record,episode_id,ordinal):
                    return await choose(record,0,ordinal)
                async def qwen(self,_kind,_seed,ordinal,record):
                    # In this reused adapter the name `qwen` denotes the native
                    # opponent callback, not the provider or selected model.
                    observation=record.get('state',{}).get('observation',{})
                    actor=int(observation.get('turn',1)) if kind=='doudizhu' else 1
                    return await choose(record,actor,ordinal)
                def journal(self,*args):pass
            initial_game,game,_,outcome,extra=await seat_control.play(Models(),native,
                {'kind':kind,'seed':seed,'mode':'qwen3.8-max','side':0,
                 'episode_id':f"arena-direct-{kind}-{seed}-{fixture['leg']}"})
            initial=_public(initial_game)
        if outcome not in ('win','loss','draw'):
            raise ValueError('native_direct_nonterminal_budget_exhausted')
        score0={'win':1.,'draw':.5,'loss':0.}[outcome]
        score_a=score0 if fixture['leg']==0 else 1.-score0
        return {'score_a':score_a,'native_outcome':outcome,
                'outcome_a':'draw' if score_a==.5 else 'win' if score_a==1. else 'loss',
                'winner_side':None if outcome=='draw' else 0 if outcome=='win' else 1,
                'winner':None if outcome=='draw' else seats[0 if outcome=='win' else 1],
                'steps':game['steps'],'seats':seats,'initial_state':initial,
                'final_state':_public(game),'trace':trace,'native_actor_control':True,
                'direct_revision':REVISION,'role_asymmetry':extra.get('role_asymmetry'),
                'rule_takeover_C':0}
    except BaseException as exc:
        # Timeouts/cancellation retain completed paid probes without inventing
        # a terminal winner or retrying earlier decisions under a new opponent.
        exc.match_trace=copy.deepcopy(trace)
        raise
