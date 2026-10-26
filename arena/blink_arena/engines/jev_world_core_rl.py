"""Realtime RL and exact replay over the shared frontend JS physics core."""
from __future__ import annotations

import asyncio
import copy
import time

from jev_engine_registry import get_engine
from jev_inference_clock import paused, contract, record_for_clock, verify_clock
from jev_inference_clock import simulated, frozen_wait, wait_seconds, observation_for_clock, SIMULATED_REVISION
from jev_world_core import WorldCoreDriver, RUNTIME_REVISION
from jev_world_realtime_rl import (
    LIMITS, _record, _terminal, _same, rebuild_credit, CLOCK_CONTRACT,
)


async def play(sampler, job):
    kind = job['kind']
    engine = get_engine(kind)
    options = ({'generator_revision': job['generator_revision']}
               if kind in ('mario_platformer', 'terraria_survival') and 'generator_revision' in job else None)
    clock_contract = contract(job, CLOCK_CONTRACT)
    driver = WorldCoreDriver(kind, job['seed'], options=options, inference_world_paused=frozen_wait(job))
    trace, events = [], []
    try:
        created = await driver.start()
        initial = state = created['state']
        generation = created['condition'] if kind in ('mario_platformer', 'terraria_survival') else None
        for ordinal in range(LIMITS[kind]):
            captured = await driver.capture()
            observation = state = captured['state']
            if _terminal(kind, state, initial):
                break
            record_started = time.monotonic()
            if hasattr(sampler, 'compute_record'):
                record, latency = await sampler.compute_record(_record, engine.observe, observation_for_clock(observation, job))
            else:
                record, latency = _record(engine.observe, observation_for_clock(observation, job)), {}
            record = record_for_clock(record, job)
            record_ready = time.monotonic()
            latency['record_preparation_seconds'] = record_ready-record_started
            action, policy = await sampler.policy_action(record, job['episode_id'], ordinal)
            latency['record_ready_to_response_seconds'] = time.monotonic()-record_ready
            if action not in record['questions']['decision']['criteria']:
                raise ValueError('world_action_not_in_captured_candidates')
            if hasattr(sampler, 'journal'):
                sampler.journal(job, 'decision', {'ordinal': ordinal, 'record': record,
                                                'action': action, 'policy': policy})
            simulated_seconds = wait_seconds(job, ordinal, 0.) if simulated(job) else None
            if simulated(job):
                await driver.call('advanceInferenceWait', frames=round(simulated_seconds * 60))
            execution = await driver.call('commit', action=action, observed=observation)
            state = execution['after_state']
            event = {'ordinal': ordinal, 'record': record, 'action': action,
                     'policy': policy, 'before_state': observation,
                     'arrival_state': execution['arrival_state'], 'after_state': state,
                     'action_applied': execution['reason'] is None,
                     'discard_reason': execution['reason'],
                     'arrival_check': execution['arrival_check'],
                     'waiting_seconds': simulated_seconds if simulated(job) else 0. if paused(job) else execution['arrival_seconds'] - captured['seconds'],
                     **({'sampling_clock_source': SIMULATED_REVISION} if simulated(job) else {}),
                     'wall_waiting_seconds': execution['arrival_seconds'] - captured['seconds'],
                     'arrival_wall_seconds': execution['arrival_seconds'],
                     'real_time_seconds': execution['real_time_seconds'],
                     'clock_contract': clock_contract, 'latency_breakdown': latency}
            events.append(event)
            if event['action_applied']:
                trace.append(copy.deepcopy(event))
            if hasattr(sampler, 'journal'):
                sampler.journal(job, 'executed_realtime', event)
            if _terminal(kind, state, initial):
                break
        finished = await driver.call('finish')
        if not _terminal(kind, state, initial):
            state = finished['state']
        outcome = ('win' if kind == 'terraria_survival' and state.get('wins', 0) > initial.get('wins', 0)
                   else state.get('outcome') or 'budget_exhausted')
        trace, credit = rebuild_credit(kind, initial, trace, state, events)
        extra = {**credit,
            **({'environment_generation': {k: generation[k] for k in
                ('seed', 'generator_revision', 'profile')}} if generation else {}),
            'opponent': 'environment', 'clock_contract': clock_contract,
            'engine_runtime': RUNTIME_REVISION, 'inference_world_paused': paused(job),
            **({'inference_simulated_wait': True, 'sampling_clock_source': SIMULATED_REVISION} if simulated(job) else {}),
            'engine_viewport': {'width': driver.viewport_width, 'height': driver.viewport_height},
            'real_time_seconds': finished['terminalClock']['elapsed_seconds'],
            'terminal_clock': finished['terminalClock'],
            'simulation_seconds': max(0, state['frame'] - initial['frame']) / 60.,
            'discarded_replies': sum(not e['action_applied'] for e in events),
            'replay_events': events}
        return initial, state, trace, outcome, extra
    except Exception as error:
        if hasattr(sampler, 'journal'):
            failure = {'error_type': type(error).__name__,
                       'initial_state': locals().get('initial'),
                       'before_state': locals().get('observation'),
                       'ordinal': locals().get('ordinal'), 'engine_runtime': RUNTIME_REVISION}
            sampler.journal(job, 'failed_realtime', failure)
        raise
    finally:
        await driver.close()


async def verify(job, initial, final, extra):
    """Advance original physics to every recorded event, without wall-clock waits."""
    from jev_world_replay_validation import ReplayValidation
    validation = ReplayValidation()
    verify_clock(job, extra, CLOCK_CONTRACT)
    kind = job['kind']
    engine = get_engine(kind)
    options = None
    if kind in ('mario_platformer', 'terraria_survival'):
        generation = extra.get('environment_generation')
        if generation is not None and generation.get('seed') != job['seed']:
            raise ValueError('world_replay_generation_seed_mismatch')
        options = {'generator_revision': generation['generator_revision']
                   if generation is not None else 'world-seed-v1'}
    viewport = extra.get('engine_viewport', {})
    async with WorldCoreDriver(kind, job['seed'], replay=True, options=options,
                               frame=initial['frame'], viewport_width=viewport.get('width'),
                               viewport_height=viewport.get('height'), inference_world_paused=frozen_wait(job)) as driver:
        current = await driver.call('snapshot')
        if kind in ('mario_platformer', 'terraria_survival') and extra.get('environment_generation') is not None:
            actual = await driver.call('condition')
            if any(actual.get(k) != value for k, value in extra['environment_generation'].items()):
                raise ValueError('world_replay_generation_did_not_replay')
        if not validation.same(current, initial, 'initial'):
            raise ValueError('realtime_world_initial_did_not_replay')
        for event in extra['replay_events']:
            observation = await driver.call('replayObserve', frame=event['before_state']['frame'])
            # Record formatting is versioned independently of unchanged physics.
            # Rebuild old Terra inputs exactly; new v19 inputs also compare strictly.
            observe = engine.observe
            if kind == 'terraria_survival':
                from jev_terraria_contract import record_for_revision
                revision = event['record']['state'].get('prompt_revision')
                observe = lambda state: record_for_revision(state, revision)
            if not validation.same(observation, event['before_state'], 'observation') or record_for_clock(_record(observe, observation_for_clock(observation, job)), job) != event['record']:
                raise ValueError('realtime_world_observation_did_not_replay')
            result = await driver.call('replayEvent', event=event)
            if result['verdict'] != event['arrival_check'] or result['verdict']['valid'] != event['action_applied']:
                raise ValueError('realtime_world_arrival_check_did_not_replay')
            if not validation.same(result['arrival'], event['arrival_state'], 'arrival') or not validation.same(result['after'], event['after_state'], 'after'):
                differing = [phase + ':' + key for phase, expected in (
                    ('arrival', event['arrival_state']), ('after', event['after_state']))
                    for key, value in expected.items() if result[phase].get(key) != value]
                raise ValueError('realtime_world_action_did_not_replay:' + kind + ':' + ','.join(differing))
        current = await driver.call('replayFinal', frame=final['frame'],
                                   awaiting=final.get('timing', {}).get('awaiting_model'))
        if not validation.same(current, final, 'final'):
            raise ValueError('realtime_world_final_did_not_replay')
    extra['replay_validation'] = validation.proof()
    return extra['replay_validation']


async def verify_with_trace(sampler, job, initial, final, trace, extra):
    rebuilt, credit = rebuild_credit(job['kind'], initial, trace, final, extra['replay_events'])
    if rebuilt != trace or any(extra.get(k) != value for k, value in credit.items()):
        raise ValueError('world_executed_credit_did_not_replay')
    return await verify(job, initial, final, extra)
