"""Snake policy episodes on the same advancing wall clock as the live game.

Observation construction, inference and pacing consume time. Directions are
applied only after catching up that time; a late reply cannot revive a dead snake.
Every interval and executed movement is retained for deterministic verification.
"""
import asyncio
import copy
import time
from jev_inference_clock import paused, contract, record_for_clock, verify_clock, policy_timeout
from jev_inference_clock import simulated, wait_seconds, SIMULATED_REVISION

import jev_snake_realtime as game
from jev_snake_runtime import CLOCK_CONTRACT, MIN_DECISION_SECONDS, MODEL_TIMEOUT_SECONDS

CREDIT_REVISION = 'snake-direction-ownership-v1'


def rebuild_credit(initial, trace, final, extra):
    """Keep pending-request latency attached to the already executing input."""
    trace = copy.deepcopy(trace)
    extra = dict(extra)
    applied = [event for event in extra['replay_events'] if event.get('action_applied')]
    if [row['ordinal'] for row in trace] != [event['ordinal'] for event in applied]:
        raise ValueError('training trace does not match applied snake actions')
    for index, (row, event) in enumerate(zip(trace, applied)):
        row['credit_before_state'] = copy.deepcopy(event['arrival_state'])
        row['credit_after_state'] = copy.deepcopy(
            applied[index+1]['arrival_state'] if index+1 < len(applied) else final)
        row['credit_revision'] = CREDIT_REVISION
    first_owned = applied[0]['arrival_state'] if applied else final
    initial_apples = first_owned['score'] - initial['score']
    extra.update(credit_revision=CREDIT_REVISION,
                 unattributed_initial_apples=initial_apples,
                 unattributed_initial_process_reward=.05 * initial_apples,
                 unattributed_initial_seconds=first_owned['elapsed'] - initial['elapsed'])
    return trace, extra


def process_rewards(initial, trace):
    """Reward apples only to the direction whose owned interval collected them."""
    if not game.is_realtime(initial):
        raise ValueError('snake realtime reward requires realtime engine state')
    rewards = []
    for row in trace:
        if row.get('credit_revision') != CREDIT_REVISION:
            raise ValueError('snake reward requires executed direction credit')
        before, after = row['credit_before_state'], row['credit_after_state']
        gained = after['score'] - before['score']
        if gained < 0 or after['elapsed'] < before['elapsed']:
            raise ValueError('snake credited state moved backwards')
        rewards.append(.05 * gained)
    total = sum(rewards)
    return [value * min(1., .25 / total) for value in rewards] if total else rewards


def _force_failure(state, reason):
    state = copy.deepcopy(state)
    state.update(outcome='loss', event='模型响应失败，本局计为失败', failure_reason=reason)
    return state


async def play(sampler, job):
    clock_contract = contract(job, CLOCK_CONTRACT)
    state = game.fresh(job['seed'])
    initial = copy.deepcopy(state)
    trace, events = [], []
    clock_at = time.monotonic()
    status, error = 'complete', None
    for ordinal in range(game.LIMIT):
        if state['outcome']:
            break
        captured_at = time.monotonic()
        pre = 0. if simulated(job) else captured_at - clock_at
        state = game.advance_idle(state, pre)
        if state['outcome']:
            events.append({'ordinal': ordinal, 'pre_decision_seconds': pre,
                           'before_state': copy.deepcopy(state), 'action_applied': False,
                           'no_request': True, 'after_state': copy.deepcopy(state),
                           'clock_contract': clock_contract})
            break
        before = copy.deepcopy(state)
        record = record_for_clock(game.as_record(before), job)
        action, policy = None, None
        try:
            action, policy = await asyncio.wait_for(
                sampler.policy_action(record, job['episode_id'], ordinal), policy_timeout(job, MODEL_TIMEOUT_SECONDS))
            if action not in record['questions']['decision']['criteria']:
                raise ValueError('model_action_not_in_captured_candidates')
        except Exception as exc:
            status = 'timeout' if isinstance(exc, TimeoutError) else 'error'
            error = type(exc).__name__
        response_at = time.monotonic()
        wall_waiting = response_at - captured_at
        waiting = wait_seconds(job, ordinal, wall_waiting)
        arrived = game.advance_idle(before, waiting)
        applied = error is None and not arrived['outcome'] and action in game.choices(arrived)
        state = game.step(arrived, action) if applied else arrived
        if applied and not simulated(job):
            await asyncio.sleep(max(0., MIN_DECISION_SECONDS - (time.monotonic() - (response_at if paused(job) else captured_at))))
        completed_at = time.monotonic()
        # The virtual 2–4s already exceeds the realtime minimum decision period.
        post = 0. if simulated(job) else completed_at - response_at
        state = game.advance_idle(state, post)
        if error:
            state = _force_failure(state, 'model_timeout' if status == 'timeout' else 'model_error')
        event = {'ordinal': ordinal, 'record': record, 'action': action, 'policy': policy,
                 'pre_decision_seconds': pre, 'before_state': before,
                 'waiting_seconds': waiting, 'wall_waiting_seconds': wall_waiting, 'arrival_state': arrived,
                 'action_applied': applied, 'post_action_seconds': post,
                 'reason': ('game_finished_while_waiting' if arrived['outcome'] else
                            'direction_changed_while_waiting' if error is None and not applied else None),
                 'after_state': copy.deepcopy(state), 'clock_contract': clock_contract,
                 **({'sampling_clock_source': SIMULATED_REVISION} if simulated(job) else {}),
                 'error_type': error, 'status': status}
        events.append(event)
        if applied:
            trace.append(copy.deepcopy(event))
        clock_at = completed_at
        if hasattr(sampler, 'journal'):
            sampler.journal(job, 'executed_realtime', event)
        if error:
            break
    if not state['outcome']:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if trace:
        trace[-1]['after_state'] = copy.deepcopy(state)
        trace[-1]['terminal_wait_after_response'] = not events[-1].get('action_applied', False)
    extra = {
        'clock_contract': clock_contract, 'replay_events': events,
        'real_time_seconds': state['elapsed'], 'inference_world_paused': paused(job),
        **({'inference_simulated_wait': True, 'sampling_clock_source': SIMULATED_REVISION} if simulated(job) else {}),
        'rule_takeover_count': 0, 'status': status, 'error_type': error,
        'inference_waiting_seconds': sum(event.get('wall_waiting_seconds', event.get('waiting_seconds', 0.)) for event in events)}
    trace, extra = rebuild_credit(initial, trace, state, extra)
    return initial, state, trace, state['outcome'], extra


def verify(job, initial, final, extra):
    state = game.fresh(job['seed'])
    if state != initial:
        raise ValueError('snake initial state mismatch')
    verify_clock(job, extra, CLOCK_CONTRACT)
    for event in extra['replay_events']:
        state = game.advance_idle(state, event.get('pre_decision_seconds', 0.))
        if state != event['before_state']:
            raise ValueError('snake captured state mismatch')
        if event.get('no_request'):
            if state != event['after_state'] or not state['outcome']:
                raise ValueError('snake terminal pre-decision state mismatch')
            continue
        if record_for_clock(game.as_record(state), job) != event['record']:
            raise ValueError('snake captured model input mismatch')
        state = game.advance_idle(state, event['waiting_seconds'])
        if state != event['arrival_state']:
            raise ValueError('snake arrival state mismatch')
        if event['action_applied']:
            if state['outcome']:
                raise ValueError('snake action applied after terminal')
            state = game.step(state, event['action'])
        elif not event.get('error_type') and not state['outcome'] and event['action'] in game.choices(state):
            raise ValueError('snake legal live action was discarded without reason')
        state = game.advance_idle(state, event['post_action_seconds'])
        if event.get('error_type'):
            state = _force_failure(state, 'model_timeout' if event['status'] == 'timeout' else 'model_error')
        if state != event['after_state']:
            raise ValueError('snake after-state mismatch')
    if not state['outcome'] and len(extra['replay_events']) >= game.LIMIT:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if state != final:
        raise ValueError('snake final state mismatch')
    return True
