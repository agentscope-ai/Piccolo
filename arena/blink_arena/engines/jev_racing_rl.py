"""Real-time adapter for the existing sampler, with replay of every clock interval.

Each record is the observation captured BEFORE candidate construction/inference.
CPU work, provider queueing, inference and pacing all consume the same wall clock.
Unapplied late responses and failed requests remain events, never policy actions.
"""
import asyncio
import copy
import time
import jev_racing_game as game
from jev_racing_runtime import CLOCK_CONTRACT, MIN_DECISION_SECONDS, MODEL_TIMEOUT_SECONDS

CREDIT_REVISION = 'racing-intent-ownership-v2'

def rebuild_credit(initial, trace, final, extra):
    """Assign physics to the intent actually executing, without editing raw events.

    Capturing/inference does not transfer ownership. Only a new applied action
    does. Initial default driving belongs to no model action.
    """
    trace = copy.deepcopy(trace)
    extra = dict(extra)
    applied = [event for event in extra['replay_events'] if event.get('action_applied')]
    if [t['ordinal'] for t in trace] != [t['ordinal'] for t in applied]:
        raise ValueError('training trace does not match applied racing actions')
    for index, (row, event) in enumerate(zip(trace, applied)):
        row['credit_before_state'] = copy.deepcopy(event['arrival_state'])
        row['credit_after_state'] = copy.deepcopy(applied[index+1]['arrival_state'] if index+1 < len(applied) else final)
        row['credit_revision'] = CREDIT_REVISION
    first_owned = applied[0]['arrival_state'] if applied else final
    potential = lambda state: .2*min(game.LENGTH,max(0,state['z']))/game.LENGTH-.15*(100-state['health'])/100
    extra.update(credit_revision=CREDIT_REVISION,
                 unattributed_initial_process_reward=potential(first_owned)-potential(initial),
                 unattributed_initial_seconds=first_owned['elapsed']-initial['elapsed'])
    return trace, extra


def _force_failure(state, reason):
    state = copy.deepcopy(state)
    state.update(outcome='loss', event='模型响应失败，本局计为失败', failure_reason=reason)
    return state


async def play(sampler, job):
    from jev_control_scope import require_active_game
    require_active_game('racing_sprint')
    state = game.fresh(job['seed'])
    initial = copy.deepcopy(state)
    trace, events = [], []
    clock_at = time.monotonic()
    status, error = 'complete', None
    for ordinal in range(game.LIMIT):
        if state['outcome']:
            break
        captured_at = time.monotonic()
        pre = captured_at - clock_at
        state = game.advance_idle(state, pre)
        if state['outcome']:
            events.append({'ordinal': ordinal, 'pre_decision_seconds': pre,
                           'before_state': copy.deepcopy(state), 'action_applied': False,
                           'no_request': True, 'after_state': copy.deepcopy(state),
                           'clock_contract': CLOCK_CONTRACT})
            break
        before = copy.deepcopy(state)
        # The clock starts before as_record, so computing candidates is not free.
        record = game.as_record(before)
        action, policy = None, None
        try:
            action, policy = await asyncio.wait_for(
                sampler.policy_action(record, job['episode_id'], ordinal), MODEL_TIMEOUT_SECONDS)
            if action not in record['questions']['decision']['criteria']:
                raise ValueError('model_action_not_in_captured_candidates')
        except Exception as exc:
            status = 'timeout' if isinstance(exc, TimeoutError) else 'error'
            error = type(exc).__name__
        response_at = time.monotonic()
        waiting = response_at - captured_at
        arrived = game.advance_idle(before, waiting)
        applied = error is None and not arrived['outcome']
        state = game.step(arrived, action) if applied else arrived
        if error is None and applied:
            await asyncio.sleep(max(0., MIN_DECISION_SECONDS - (time.monotonic() - captured_at)))
        # Includes engine application and sleep scheduling CPU costs as well.
        completed_at = time.monotonic()
        post = completed_at - response_at
        state = game.advance_idle(state, post)
        if error:
            state = _force_failure(state, 'model_timeout' if status == 'timeout' else 'model_error')
        transition = {'ordinal': ordinal, 'record': record, 'action': action, 'policy': policy,
                      'pre_decision_seconds': pre, 'before_state': before,
                      'waiting_seconds': waiting, 'arrival_state': arrived,
                      'action_applied': applied, 'post_action_seconds': post,
                      'after_state': copy.deepcopy(state), 'clock_contract': CLOCK_CONTRACT,
                      'error_type': error, 'status': status}
        events.append(transition)
        if applied:
            trace.append(copy.deepcopy(transition))
        clock_at = completed_at
        if hasattr(sampler, 'journal'):
            sampler.journal(job, 'executed_realtime', transition)
        if error:
            break
    if not state['outcome']:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if trace:
        # Carry terminal physics after the last applied intent into its outcome.
        # This MUST NOT alias replay_events, which retain exact transition bounds.
        trace[-1]['after_state'] = copy.deepcopy(state)
        trace[-1]['terminal_wait_after_response'] = not events[-1].get('action_applied', False)
    extra = {
        'clock_contract': CLOCK_CONTRACT, 'replay_events': events,
        'rule_takeover_count': state['rule_takeover_count'], 'real_time_seconds': state['elapsed'],
        'inference_waiting_seconds': sum(t.get('waiting_seconds', 0.) for t in events),
        'status': status, 'error_type': error}
    trace, extra = rebuild_credit(initial, trace, state, extra)
    return initial, state, trace, state['outcome'], extra


def verify(job, initial, final, extra):
    state = game.fresh(job['seed'])
    if state != initial:
        raise ValueError('racing initial state mismatch')
    for event in extra['replay_events']:
        state = game.advance_idle(state, event.get('pre_decision_seconds', 0.))
        if state != event['before_state']:
            raise ValueError('racing captured state mismatch')
        if event.get('no_request'):
            if state != event['after_state'] or not state['outcome']:
                raise ValueError('racing terminal pre-decision state mismatch')
            continue
        if game.as_record(state) != event['record']:
            raise ValueError('racing captured model input mismatch')
        state = game.advance_idle(state, event['waiting_seconds'])
        if state != event['arrival_state']:
            raise ValueError('racing arrival state mismatch')
        if event['action_applied']:
            if state['outcome']:
                raise ValueError('racing action applied after terminal')
            state = game.step(state, event['action'])
        state = game.advance_idle(state, event['post_action_seconds'])
        if event.get('error_type'):
            state = _force_failure(state, 'model_timeout' if event['status'] == 'timeout' else 'model_error')
        if state != event['after_state']:
            raise ValueError('racing after-state mismatch')
    if not state['outcome'] and len(extra['replay_events']) >= game.LIMIT:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if state != final:
        raise ValueError('racing final state mismatch')
    return True
