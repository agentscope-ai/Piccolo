"""Realtime browser rollouts and exact frame replay for Mario and Terramai.

The same frontend engine runs during inference. A returned choice is applied
atomically with its public arrival check; a terminal, respawn, or changed-hazard
invalidated choice is only an audit event and triggers a fresh observation. Replay disables animation scheduling and advances the original
physics to the recorded frame boundaries, including all inference waiting.
"""
from __future__ import annotations

import asyncio
import copy
import time

from jev_engine_registry import get_engine
from jev_gameplay_process_rewards import potential
from jev_world_episode_clock import install_episode_clock
from jev_world_replay_hooks import MARIO_HOOK, TERRA_HOOK

CLOCK_CONTRACT = 'realtime-world-wall-clock-arrival-guard-frame-replay-v2'
ARRIVAL_REVISION = 'visible-arrival-guard-v1'
CREDIT_REVISION = 'world-executed-intent-through-next-arrival-v1'


class _DecisionLimits(dict):
    """Legacy diagnostic overrides, with live registry defaults."""
    def __missing__(self, kind):
        return get_engine(kind).limit


LIMITS = _DecisionLimits()


def _terminal(kind, state, initial):
    return bool(state.get('outcome')) or (kind == 'terraria_survival'
             and state.get('wins', 0) > initial.get('wins', 0))


def _record(record_fn, snapshot):
    record = copy.deepcopy(record_fn(snapshot))
    # Keep all captured clock fields; only clockless legacy inputs default to step.
    record['state']['observation']['timing'] = copy.deepcopy(snapshot['timing'])
    return record


def rebuild_credit(kind, initial, trace, final, events):
    """The previous applied action owns physics until the next applied action."""
    applied = [event for event in events if event['action_applied']]
    if [row['ordinal'] for row in trace] != [event['ordinal'] for event in applied]:
        raise ValueError('world_credit_trace_does_not_match_executed_actions')
    credited = copy.deepcopy(trace)
    for index, (row, event) in enumerate(zip(credited, applied)):
        row['credit_before_state'] = copy.deepcopy(event['arrival_state'])
        row['credit_after_state'] = copy.deepcopy(applied[index+1]['arrival_state']
                                                  if index+1 < len(applied) else final)
        row['credit_revision'] = CREDIT_REVISION
        if kind == 'mario_platformer' and initial.get('action_execution', {}).get('revision') == 'selected-visible-landing-v6-explicit-guard':
            before, after = row['credit_before_state'], row['credit_after_state']
            owner = event['arrival_state']['decisions'] + 1
            guard = after.get('action_execution', {}).get('landing_guard') or {}
            guard_frames = guard.get('executed_frames', 0) if guard.get('owner_decision') == owner else 0
            execution_frames = event['after_state']['frame'] - event['arrival_state']['frame']
            interval_frames = after['frame'] - before['frame']
            row['control_ownership'] = {
                'revision': 'mario-explicit-intent-interval-v1', 'owner_engine_decision': owner,
                'model_intent': event['action'], 'strategy_origin': 'A', 'selected_execution_origin': 'B',
                'selected_execution_frames': execution_frames, 'selected_guard_frames': guard_frames,
                'waiting_frames_without_selected_guard': max(0, interval_frames-execution_frames-guard_frames),
                'selected_guard_defensive_jumps': guard.get('defensive_jumps', 0) if guard.get('owner_decision') == owner else 0,
                'credit_total_frames': interval_frames,
                'credit_scope': 'includes_waiting_cost_not_only_immediate_candidate_consequence',
                'terminal_cost_preserved': True}
    first_owned = applied[0]['arrival_state'] if applied else final
    return credited, {'credit_revision': CREDIT_REVISION,
        'unattributed_initial_frames': max(0, first_owned['frame']-initial['frame']),
        'unattributed_initial_seconds': (applied[0].get('arrival_wall_seconds') if applied else
                                         events[-1].get('real_time_seconds') if events else None),
        'unattributed_initial_potential_change': potential(kind, first_owned, initial)-potential(kind, initial, initial)}


async def play(sampler, job):
    if get_engine(job['kind']).backend == 'worker':
        from jev_world_core_rl import play as core_play
        return await core_play(sampler, job)
    kind = job['kind']
    engine = get_engine(kind)
    filename, bridge, record_fn = engine.browser_page, engine.browser_bridge, engine.observe
    page = await sampler.browser.new_page(viewport={'width': 920, 'height': 700})
    trace, events = [], []
    try:
        await install_episode_clock(page, kind)
        await page.goto(sampler.args.frontend.rstrip('/') + '/playground/' + filename + '.html')
        await page.wait_for_function('!!window.' + bridge + '?.snapshot')
        if await page.evaluate('b=>window[b].arrival_contract_revision', bridge) != ARRIVAL_REVISION:
            raise ValueError('world_arrival_contract_unavailable')
        initial = await page.evaluate('''([b,seed,options])=>{
          const api=window[b];api.reset(seed,options||undefined);api.activate(true);
          const snapshot=api.prepare({clock:'realtime'});
          window.__JevEpisodeStartedAt=window.__JevEpisodeClock.start();return snapshot;
        }''', [bridge, job['seed'], ({'generator_revision': job['generator_revision']}
                                   if kind in ('mario_platformer', 'terraria_survival') and 'generator_revision' in job else None)])
        # Generation identity belongs to the episode receipt, never the model
        # observation. Old completed rollouts must replay with their old map.
        generation = (await page.evaluate('b=>window[b].condition()', bridge)
                      if kind in ('mario_platformer', 'terraria_survival') else None)
        state = initial
        for ordinal in range(LIMITS[kind]):
            captured = await page.evaluate('''b=>({state:window[b].prepare({clock:'realtime'}),
              seconds:(performance.now()-window.__JevEpisodeStartedAt)/1000})''', bridge)
            observation = captured['state']
            state = observation
            if _terminal(kind, state, initial):
                break
            record = _record(record_fn, observation)
            action, policy = await sampler.policy_action(record, job['episode_id'], ordinal)
            if action not in record['questions']['decision']['criteria']:
                raise ValueError('world_action_not_in_captured_candidates')
            if hasattr(sampler, 'journal'):
                sampler.journal(job, 'decision', {'ordinal': ordinal, 'record': record,
                                                  'action': action, 'policy': policy})
            # Keep the arrival check and act() in one browser task: there is no
            # unrecorded physics tick between deciding validity and executing.
            execution = await page.evaluate('''async ([b,a,observation])=>{
              const api=window[b],arrival=structuredClone(api.snapshot()),arrivalSeconds=(performance.now()-window.__JevEpisodeStartedAt)/1000;
              const verdict=api.checkActionArrival(a,observation,arrival),reason=verdict.reason;
              const after=reason?api.rejectActionArrival(a,observation,arrival,verdict):await api.act(a);
              return {arrival_state:arrival,after_state:after,reason,arrival_check:verdict,arrival_seconds:arrivalSeconds,
                real_time_seconds:(performance.now()-window.__JevEpisodeStartedAt)/1000};
            }''', [bridge, action, observation])
            state = execution['after_state']
            event = {'ordinal': ordinal, 'record': record, 'action': action,
                     'policy': policy, 'before_state': observation,
                     'arrival_state': execution['arrival_state'], 'after_state': state,
                     'action_applied': execution['reason'] is None,
                     'discard_reason': execution['reason'],
                     'arrival_check': execution['arrival_check'],
                     'waiting_seconds': execution['arrival_seconds']-captured['seconds'],
                     'arrival_wall_seconds': execution['arrival_seconds'],
                     'real_time_seconds': execution['real_time_seconds'],
                     'clock_contract': CLOCK_CONTRACT}
            events.append(event)
            if event['action_applied']:
                trace.append(copy.deepcopy(event))
            if hasattr(sampler, 'journal'):
                sampler.journal(job, 'executed_realtime', event)
            if _terminal(kind, state, initial):
                break
        # Stop clock ownership at the final observed state, before verification.
        # Preserve the snapshot's realtime metadata when deactivating the page.
        finished = await page.evaluate('''b=>{
          const api=window[b],state=api.snapshot(),seconds=(performance.now()-window.__JevEpisodeStartedAt)/1000;
          const terminalClock=window.__JevEpisodeClock.finish();
          api.activate(false);return {state,seconds,terminalClock};
        }''', bridge)
        # A terminal returned by act() is already settled. Do not replace it
        # with a later automatically regenerated Terra world.
        if not _terminal(kind, state, initial):
            state = finished['state']
        elapsed = finished['terminalClock']['elapsed_seconds']
        outcome = ('win' if kind == 'terraria_survival' and state.get('wins', 0) > initial.get('wins', 0)
                   else state.get('outcome') or 'budget_exhausted')
        trace, credit = rebuild_credit(kind, initial, trace, state, events)
        return initial, state, trace, outcome, {**credit,
            **({'environment_generation': {k: generation[k] for k in
                ('seed', 'generator_revision', 'profile')}} if generation else {}),
            'opponent': 'environment', 'clock_contract': CLOCK_CONTRACT,
            'inference_world_paused': False, 'real_time_seconds': elapsed,
            'terminal_clock': finished['terminalClock'],
            'simulation_seconds': max(0, state['frame']-initial['frame'])/60.,
            'discarded_replies': sum(not e['action_applied'] for e in events),
            'replay_events': events,
        }
    except Exception as error:
        if hasattr(sampler, 'journal'):
            failure = {'error_type': type(error).__name__,
                       'initial_state': locals().get('initial'),
                       'before_state': locals().get('observation'),
                       'ordinal': locals().get('ordinal')}
            try:
                failure['final_state'] = await page.evaluate('b=>window[b].snapshot()', bridge)
                failure['terminal_clock'] = await page.evaluate('window.__JevEpisodeClock.finish()')
            except Exception as capture_error:
                failure['capture_error_type'] = type(capture_error).__name__
            sampler.journal(job, 'failed_realtime', failure)
        raise
    finally:
        await page.close()


def _hook(kind):
    # Reuse the existing original-engine replay hook, with the RL frontend's
    # longer visible-intent executor where that engine exposes one.
    if kind == 'mario_platformer':
        old = 'if(remaining>0){physics(command.direction,command.jump&&remaining===12);'
        if old not in MARIO_HOOK:
            raise ValueError('world_replay_mario_hook_changed')
        return MARIO_HOOK.replace(old,
            "if(remaining>0&&typeof advanceSelectedAction==='function')advanceSelectedAction();\n      "
            "else if(remaining>0&&typeof advanceAction==='function')advanceAction();\n      else " + old)
    old = """if(jevFrames>0&&jevAction){keys={};jevKeys[jevAction].forEach(k=>keys[k]=1);}
      update(1);
      if(jevFrames>0&&--jevFrames<=0)jevFinish();"""
    if old not in TERRA_HOOK:
        raise ValueError('world_replay_terra_hook_changed')
    return TERRA_HOOK.replace(old, "if(typeof jevAdvance==='function')jevAdvance();\n      else {" + old + "}")


def _same(left, right):
    # The hook adds replay-only render geometry. All actual observed engine
    # fields, including timing mode and control effects, must still agree.
    return {k:v for k,v in left.items() if k != 'replay_scene'} == {
        k:v for k,v in right.items() if k != 'replay_scene'}


async def verify(sampler, job, initial, final, extra, trace=None):
    if get_engine(job['kind']).backend == 'worker':
        from jev_world_core_rl import verify as core_verify, verify_with_trace
        return (await verify_with_trace(sampler, job, initial, final, trace, extra)
                if trace is not None else await core_verify(job, initial, final, extra))
    if trace is not None:
        rebuilt, credit = rebuild_credit(job['kind'], initial, trace, final, extra['replay_events'])
        if rebuilt != trace or any(extra.get(k) != v for k, v in credit.items()):
            raise ValueError('world_executed_credit_did_not_replay')
    engine = get_engine(job['kind'])
    filename, bridge, record_fn = engine.browser_page, engine.browser_bridge, engine.observe
    page = await sampler.browser.new_page(viewport={'width': 920, 'height': 700})

    async def script(route):
        response = await route.fetch()
        source = await response.text()
        marker = source.rfind('})();')
        if marker < 0:
            raise ValueError('unknown_world_script_shape')
        await route.fulfill(response=response, body=source[:marker]+_hook(job['kind'])+source[marker:])

    try:
        await page.add_init_script('window.requestAnimationFrame=()=>0;window.cancelAnimationFrame=()=>{};')
        await page.route(f'**/{filename}.js*', script)
        # Replay needs the original scripts and bridge, not render-only fonts or
        # images. Keep one 30s initialization deadline and verify readiness
        # explicitly; rAF polling cannot run after replay disables animation.
        started = time.monotonic()
        phase = 'domcontentloaded'
        try:
            async with asyncio.timeout(30.0):
                await page.goto(sampler.args.frontend.rstrip('/')+'/playground/'+filename+'.html',
                                wait_until='domcontentloaded', timeout=30000)
                phase = 'engine_ready'
                await page.wait_for_function('''b=>{
                  const api=window[b];
                  return typeof window.__ArenaReplay?.advance==='function' && !!api &&
                    ['reset','activate','snapshot','prepare','act','checkActionArrival',
                     'rejectActionArrival'].every(method=>typeof api[method]==='function');
                }''', arg=bridge, polling=100, timeout=30000)
        except Exception as error:
            raise RuntimeError('world_replay_initialization_failed:phase='+phase+
                               ':elapsed_seconds='+format(time.monotonic()-started, '.3f')+
                               ':error_type='+type(error).__name__) from error
        if await page.evaluate('b=>window[b].arrival_contract_revision', bridge) != ARRIVAL_REVISION:
            raise ValueError('world_arrival_contract_unavailable')
        reset_options = None
        if job['kind'] in ('mario_platformer', 'terraria_survival'):
            generation = extra.get('environment_generation')
            if generation is not None and generation.get('seed') != job['seed']:
                raise ValueError('world_replay_generation_seed_mismatch')
            reset_options = {'generator_revision': (generation['generator_revision']
                             if generation is not None else 'world-seed-v1')}
        current = await page.evaluate('''([b,seed,target,options])=>{
          const api=window[b];api.reset(seed,options||undefined);api.activate(true);
          window.__ArenaReplay.advance(target,false);api.prepare({clock:'realtime'});
          return api.snapshot();
        }''', [bridge, job['seed'], initial['frame'], reset_options])
        if job['kind'] in ('mario_platformer', 'terraria_survival') and extra.get('environment_generation') is not None:
            actual_generation = await page.evaluate('b=>window[b].condition()', bridge)
            if any(actual_generation.get(k) != v for k, v in extra['environment_generation'].items()):
                raise ValueError('world_replay_generation_did_not_replay')
        if not _same(current, initial):
            raise ValueError('realtime_world_initial_did_not_replay')
        for event in extra['replay_events']:
            observation = await page.evaluate('''([b,frame])=>{
              window.__ArenaReplay.advance(frame,false);
              return window[b].prepare({clock:'realtime'});
            }''', [bridge, event['before_state']['frame']])
            if not _same(observation, event['before_state']) or _record(record_fn, observation) != event['record']:
                raise ValueError('realtime_world_observation_did_not_replay')
            result = await page.evaluate('''([b,e])=>{
              const replay=window.__ArenaReplay,api=window[b];
              replay.advance(e.arrival_state.frame,false);const arrival=api.snapshot();
              const verdict=api.checkActionArrival(e.action,e.before_state,arrival);
              if(verdict.valid)api.act(e.action);
              else api.rejectActionArrival(e.action,e.before_state,arrival,verdict);
              replay.advance(e.after_state.frame,false);
              return {arrival,after:api.snapshot(),verdict};
            }''', [bridge, event])
            if result['verdict'] != event['arrival_check'] or result['verdict']['valid'] != event['action_applied']:
                raise ValueError('realtime_world_arrival_check_did_not_replay')
            if not _same(result['arrival'], event['arrival_state']) or not _same(result['after'], event['after_state']):
                differing = [phase+':'+key for phase, expected in (
                    ('arrival', event['arrival_state']), ('after', event['after_state']))
                    for key, value in expected.items() if result[phase].get(key) != value]
                raise ValueError('realtime_world_action_did_not_replay:'+job['kind']+':'+','.join(differing))
        current = await page.evaluate('''([b,frame,awaiting])=>{
          window.__ArenaReplay.advance(frame,false);
          if(awaiting)window[b].prepare({clock:'realtime'});
          return window[b].snapshot();
        }''', [bridge, final['frame'], final.get('timing', {}).get('awaiting_model')])
        if not _same(current, final):
            raise ValueError('realtime_world_final_did_not_replay')
    finally:
        await page.close()
