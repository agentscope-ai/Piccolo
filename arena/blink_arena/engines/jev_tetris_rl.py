"""Full-game Tetris episodes with advancing gravity and exact clock receipts.

Only executed inputs enter training credit. A response belongs to the piece
observed at request time, and can never control a later piece. Waiting and
clearing phases stay in the preceding actually executed input's owned interval.
"""
import asyncio
import copy
import math
import time
from jev_inference_clock import paused, contract, record_for_clock, verify_clock, policy_timeout

import jev_tetris_realtime as game
from jev_tetris_runtime import (CLOCK_CONTRACT, MIN_DECISION_SECONDS,
                                MODEL_TIMEOUT_SECONDS, discard_reason)

CREDIT_REVISION = 'tetris-executed-input-ownership-v1'


def rebuild_credit(initial, trace, final, extra):
    trace, extra = copy.deepcopy(trace), dict(extra)
    applied = [event for event in extra['replay_events'] if event.get('action_applied')]
    if [row['ordinal'] for row in trace] != [event['ordinal'] for event in applied]:
        raise ValueError('training trace does not match applied tetris inputs')
    for index, (row, event) in enumerate(zip(trace, applied)):
        row['credit_before_state'] = copy.deepcopy(event['arrival_state'])
        row['credit_after_state'] = copy.deepcopy(
            applied[index + 1]['arrival_state'] if index + 1 < len(applied) else final)
        row['credit_revision'] = CREDIT_REVISION
        if initial.get('engine_revision')==game.REVISION:
            before,after=row['credit_before_state'],row['credit_after_state']
            owner=event['arrival_state']['active']['piece_id']
            locked=list(range(before['steps']+1,after['steps']+1))
            uncontrolled=[piece for piece in locked if piece!=owner]
            row['control_ownership']={
                'revision':'tetris-piece-owned-interval-v1','owner_piece_id':owner,
                'next_applied_ordinal':applied[index+1]['ordinal'] if index+1<len(applied) else None,
                'credit_locked_piece_ids':locked,'controlled_piece_locks':int(owner in locked),
                'uncontrolled_piece_locks':len(uncontrolled),'uncontrolled_piece_ids':uncontrolled,
                'credit_scope':'includes_uncontrolled_waiting_cost_not_immediate_candidate_consequence',
                'terminal_cost_preserved':True,'strategy_origin':'A','current_piece_execution_origin':'B'}
    first_owned = applied[0]['arrival_state'] if applied else final
    extra.update(credit_revision=CREDIT_REVISION,
                 unattributed_initial_seconds=first_owned['elapsed'] - initial['elapsed'])
    return trace, extra


def _force_failure(state, reason):
    state = copy.deepcopy(state)
    if not state['outcome']:
        state.update(outcome='loss', event='model_error', failure_reason=reason)
    return state


def idle_segments(event):
    """Exact clock calls inside one compact B interval; old receipts stay valid."""
    segments = event.get('idle_segments')
    if segments is None:
        segments = [[0., event.get('idle_seconds', 0.)]]
    if not isinstance(segments, list) or not segments or len(segments) > 10000:
        raise ValueError('invalid tetris idle segments')
    for index, segment in enumerate(segments):
        if (not isinstance(segment, list) or len(segment) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) or
                    x < 0 or x > game.TIME_LIMIT + 60 for x in segment) or
                index == 0 and segment[0] != 0):
            raise ValueError('invalid tetris idle segments')
    if 'idle_segments' in event and (not game.persistent(event['before_state']) or
            event.get('coalesced_wait_count') != len(segments) or
            not math.isclose(event.get('idle_seconds', -1),
                             sum(sum(x) for x in segments), abs_tol=1e-9)):
        raise ValueError('tetris idle segment total mismatch')
    return segments


def append_idle_event(events, event):
    # Preserve every physical advance call (including trace-ring boundaries)
    # while storing only the interval's two full states, rather than 20/second.
    if not game.persistent(event['before_state']):
        events.append(event)
        return
    prior = events[-1] if events else None
    if (prior and prior.get('no_request') and prior['ordinal'] == event['ordinal']
            and prior.get('no_request_reason') == event.get('no_request_reason')):
        prior['idle_segments'].append([event['pre_decision_seconds'], event['idle_seconds']])
        prior['idle_seconds'] += event['pre_decision_seconds'] + event['idle_seconds']
        prior['coalesced_wait_count'] += 1
        prior['after_state'] = event['after_state']
    else:
        event.update(idle_segments=[[0., event['idle_seconds']]], coalesced_wait_count=1)
        events.append(event)


async def play(sampler, job):
    clock_contract = contract(job, CLOCK_CONTRACT)
    state = game.fresh(job['seed'])
    initial, trace, events = copy.deepcopy(state), [], []
    clock_at, status, error, ordinal = time.monotonic(), 'complete', None, 0
    decision_limit = job.get('max_decisions', game.LIMIT)
    if type(decision_limit) is not int or not 1 <= decision_limit <= game.LIMIT:
        raise ValueError('invalid tetris decision budget')
    while not state['outcome'] and (ordinal < decision_limit or
            game.persistent(state) and not game.needs_decision(state)):
        captured_at = time.monotonic()
        pre = captured_at - clock_at
        previous_state = state
        state = game.advance_idle(state, pre)
        before = copy.deepcopy(state)
        if ordinal >= decision_limit and game.needs_decision(state):
            # The loop admitted only the previous piece's continuing B intent.
            # A lock during clock catch-up must not request budget+1 for a new
            # piece. Keep that exact clock interval in replay before settling.
            append_idle_event(events, {'ordinal': ordinal, 'pre_decision_seconds': 0.,
                'before_state': copy.deepcopy(previous_state), 'action_applied': False,
                'no_request': True, 'idle_seconds': pre,
                'no_request_reason': game.decision_reason(previous_state),
                'policy_request': False, 'strategy_origin': 'A', 'execution_origin': 'B',
                'after_state': copy.deepcopy(state), 'clock_contract': clock_contract})
            break
        if not game.needs_decision(state):
            # Completed target / mechanical intent waits are B execution of
            # the last A choice, not more policy calls or artificial actions.
            wait = 0.
            if not state['outcome']:
                await asyncio.sleep(.05)
                wait = time.monotonic() - captured_at
                state = game.advance_idle(state, wait)
            append_idle_event(events, {'ordinal': ordinal, 'pre_decision_seconds': pre,
                           'before_state': before, 'action_applied': False,
                           'no_request': True, 'idle_seconds': wait,
                           **({'no_request_reason':game.decision_reason(before),'policy_request':False,
                               'strategy_origin':'A','execution_origin':'B'} if game.persistent(before) else {}),
                           'after_state': copy.deepcopy(state), 'clock_contract': clock_contract})
            clock_at = captured_at + wait
            continue
        record_started = time.monotonic()
        if hasattr(sampler, 'compute_record'):
            record, latency = await sampler.compute_record(game.as_record, before)
        else:
            record, latency = game.as_record(before), {}
        record = record_for_clock(record, job)
        record_ready = time.monotonic()
        latency.update(capture_to_record_ready_seconds=record_ready-captured_at,
                       record_preparation_seconds=record_ready-record_started)
        action, policy, request_error = None, None, None
        try:
            action, policy = await asyncio.wait_for(
                sampler.policy_action(record, job['episode_id'], ordinal), policy_timeout(job, MODEL_TIMEOUT_SECONDS))
            if action not in record['questions']['decision']['criteria']:
                raise ValueError('model_action_not_in_captured_candidates')
        except Exception as exc:
            request_error = type(exc).__name__
            status = 'timeout' if isinstance(exc, TimeoutError) else 'error'
        response_at = time.monotonic()
        latency['record_ready_to_response_seconds'] = response_at-record_ready
        wall_waiting = response_at - captured_at
        waiting = 0. if paused(job) else wall_waiting
        arrived = game.advance_idle(before, waiting)
        reason = discard_reason(before, arrived, action)
        applied = request_error is None and reason is None
        state = game.step(arrived, action) if applied else arrived
        if applied:
            await asyncio.sleep(max(0., MIN_DECISION_SECONDS - (time.monotonic() - (response_at if paused(job) else captured_at))))
        completed_at = time.monotonic()
        post = completed_at - response_at
        state = game.advance_idle(state, post)
        if request_error and not arrived['outcome']:
            error = request_error
            state = _force_failure(state, 'model_timeout' if status == 'timeout' else 'model_error')
        elif arrived['outcome']:
            # The actual engine terminal predates this reply, including timeouts.
            # Keep its measured terminal time and natural result unchanged.
            status = 'complete'
        event = {'ordinal': ordinal, 'record': record, 'action': action, 'policy': policy,
                 'pre_decision_seconds': pre, 'before_state': before,
                 'waiting_seconds': waiting, 'wall_waiting_seconds': wall_waiting, 'arrival_state': arrived,
                 'action_applied': applied, 'post_action_seconds': post,
                 'reason': reason, 'after_state': copy.deepcopy(state),
                 'clock_contract': clock_contract, 'error_type': request_error,
                 'status': status, 'latency_breakdown': latency}
        events.append(event)
        if applied:
            trace.append(copy.deepcopy(event))
        clock_at, ordinal = completed_at, ordinal + 1
        if hasattr(sampler, 'journal'):
            sampler.journal(job, 'executed_realtime', event)
        if error:
            break
    if not state['outcome']:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if trace:
        trace[-1]['after_state'] = copy.deepcopy(state)
        trace[-1]['terminal_wait_after_response'] = not events[-1].get('action_applied', False)
    extra = {'clock_contract': clock_contract, 'replay_events': events,
             'real_time_seconds': state['elapsed'], 'inference_world_paused': paused(job),
             'rule_takeover_count': 0, 'status': status, 'error_type': error,
             'decision_limit': decision_limit,
             'inference_waiting_seconds': sum(event.get('wall_waiting_seconds', event.get('waiting_seconds', 0.)) for event in events)}
    trace, extra = rebuild_credit(initial, trace, state, extra)
    return initial, state, trace, state['outcome'], extra


def verify(job, initial, final, extra):
    state = game.fresh(job['seed'], revision=initial.get('engine_revision'))
    # Physics did not change in v2; preserve the captured v1 prompt/record when
    # replaying an archived real-time episode instead of silently rewriting it.
    if state != initial:
        raise ValueError('tetris initial state mismatch')
    verify_clock(job, extra, CLOCK_CONTRACT)
    requests = 0
    for event in extra['replay_events']:
        state = game.advance_idle(state, event.get('pre_decision_seconds', 0.))
        if state != event['before_state']:
            raise ValueError('tetris captured state mismatch')
        if event.get('no_request'):
            if event.get('action_applied') or any(event.get(k) is not None for k in ('action','record','policy')):
                raise ValueError('tetris nondecision action ownership mismatch')
            if event['ordinal'] != requests:
                raise ValueError('tetris nondecision ordinal mismatch')
            for index, (pre_seconds, wait_seconds) in enumerate(idle_segments(event)):
                if index:
                    state = game.advance_idle(state, pre_seconds)
                if game.needs_decision(state):
                    raise ValueError('tetris actionable phase omitted a decision')
                if game.persistent(state) and event.get('no_request_reason') != game.decision_reason(state):
                    raise ValueError('tetris nondecision event mismatch')
                state = game.advance_idle(state, wait_seconds)
            if state != event['after_state']:
                raise ValueError('tetris idle phase state mismatch')
            continue
        if not game.needs_decision(state) or event['ordinal'] != requests or record_for_clock(game.as_record(state), job) != event['record']:
            raise ValueError('tetris captured model input mismatch')
        requests += 1
        before = copy.deepcopy(state)
        state = game.advance_idle(state, event['waiting_seconds'])
        if state != event['arrival_state']:
            raise ValueError('tetris arrival state mismatch')
        reason = discard_reason(before, state, event['action'])
        expected_applied = not event.get('error_type') and reason is None
        if event['action_applied'] != expected_applied or event.get('reason') != reason:
            raise ValueError('tetris action ownership mismatch')
        terminal_at_arrival = bool(state['outcome'])
        if expected_applied:
            state = game.step(state, event['action'])
        state = game.advance_idle(state, event['post_action_seconds'])
        if event.get('error_type') and not terminal_at_arrival:
            state = _force_failure(state, 'model_timeout' if event['status'] == 'timeout' else 'model_error')
        if state != event['after_state']:
            raise ValueError('tetris after-state mismatch')
    decision_limit = job.get('max_decisions', game.LIMIT)
    if extra.get('decision_limit') != decision_limit:
        raise ValueError('tetris decision budget mismatch')
    if not state['outcome'] and requests >= decision_limit:
        state.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    if state != final or extra.get('real_time_seconds') != final['elapsed']:
        raise ValueError('tetris final state mismatch')
    return True
