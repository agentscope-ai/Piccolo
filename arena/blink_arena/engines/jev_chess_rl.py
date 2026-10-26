"""Seat-aware chess RL through the same registered frontend environment.

Only actual student choices enter the trace. Forced continuations and explicit
opponents remain execution events. The chess core alone adjudicates the game;
material, opponent heuristics and training budgets never manufacture a win.
"""
from __future__ import annotations

from copy import deepcopy
import math

import jev_chess as chess
from jev_engine_registry import get_engine

REVISION = 'chess-standard-seat-rollout-v1'
CREDIT_REVISION = 'chess-controlled-turn-interval-v1'


def _settings(job):
    if (job.get('kind', job.get('game')) != 'chess'
            or any(job[key] != 'chess' for key in ('kind', 'game') if key in job)):
        raise ValueError('chess_runner_requires_chess_kind')
    if any(key in job for key in ('fen', 'initial_fen', 'opening_moves')):
        raise ValueError('chess_rl_requires_registered_seed_reset')
    engine = get_engine('chess')
    side, mode = job.get('side', 0), job.get('mode', engine.opponent_modes[0])
    if type(side) is not int or side not in (0, 1):
        raise ValueError('chess_controlled_side_must_be_white_0_or_black_1')
    if mode not in ('rule_engine', 'qwen3.8-max') or mode not in engine.opponent_modes:
        raise ValueError('chess_requires_explicit_opponent_mode')
    budget = job.get('max_decisions', engine.limit)
    if type(budget) is not int or not 1 <= budget <= engine.limit:
        raise ValueError('invalid_chess_decision_budget')
    return engine, side, mode, budget


def _student_policy(record, action, policy):
    """Fail closed for callbacks used outside the standard ticket validator."""
    question = record['questions']['decision']
    order = list(question.get('option_order', question['criteria']))
    if not isinstance(policy, dict) or policy.get('origin') != 'student_model' or policy.get('forced'):
        raise ValueError('chess_student_choice_requires_actual_student_policy')
    index, probabilities = policy.get('selected_index'), policy.get('old_probabilities')
    if (policy.get('candidate_values') != order or type(index) is not int or
            not 0 <= index < len(order) or order[index] != action or
            not isinstance(probabilities, list) or len(probabilities) != len(order) or
            any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                for p in probabilities) or
            not math.isclose(math.fsum(probabilities), 1., rel_tol=0., abs_tol=1e-5) or
            probabilities[index] <= 0):
        raise ValueError('chess_student_behavior_mapping_mismatch')


def _policy(record, action, policy, evaluation, teacher=False):
    if teacher:
        prohibited = {'old_probabilities', 'input_token_ids', 'candidate_token_ids',
                      'selected_index', 'sampling_epsilon', 'sampling_temperature'}
        if (evaluation or not isinstance(policy, dict) or policy.get('origin') != 'teacher'
                or policy.get('forced') or policy.get('on_policy', False)
                or policy.get('student_training_sample', False) or prohibited.intersection(policy)
                or not isinstance(policy.get('teacher_model'), str) or not policy['teacher_model']
                or policy.get('served_model') != policy['teacher_model']
                or action not in record['questions']['decision']['criteria']):
            raise ValueError('chess_teacher_requires_actual_off_policy_teacher_evidence')
        return
    if not evaluation:
        return _student_policy(record, action, policy)
    prohibited = {'old_probabilities', 'input_token_ids', 'candidate_token_ids',
                  'selected_index', 'sampling_epsilon', 'sampling_temperature'}
    if (not isinstance(policy, dict) or policy.get('origin') != 'evaluation_model'
            or policy.get('forced') or policy.get('on_policy', False)
            or policy.get('student_training_sample', False) or prohibited.intersection(policy)):
        raise ValueError('chess_evaluation_requires_nontraining_model_evidence')
    if action not in record['questions']['decision']['criteria']:
        raise ValueError('illegal_chess_evaluation_action')


def _credit(trace, final):
    for index, row in enumerate(trace):
        row['credit_before_state'] = deepcopy(row['before_state'])
        row['credit_after_state'] = deepcopy(trace[index + 1]['before_state']
            if index + 1 < len(trace) else final)
        row['credit_revision'] = CREDIT_REVISION
    return trace


def _journal(sampler, job, name, value):
    if hasattr(sampler, 'journal'):
        sampler.journal(job, name, value)


async def _play(sampler, job, *, evaluation, teacher=False):
    engine, side, mode, budget = _settings(job)
    initial = engine.reset(job['seed'], {'opponent': mode, 'max_plies': engine.limit})
    state, trace, events = deepcopy(initial), [], []
    student_calls = qwen_calls = forced_student = forced_opponent = rule_calls = 0
    for ordinal in range(engine.limit):
        if engine.outcome(state, side):
            break
        actor = chess.actor(state)
        options = engine.legal_actions(state)
        if not options:
            raise ValueError('nonterminal_chess_position_has_no_legal_action')
        controlled = actor == side
        forced = len(options) == 1
        # Let the opponent and forced continuations settle the last selected
        # intent; stop only before requesting an additional student choice.
        if controlled and not forced and student_calls >= budget:
            break
        record = engine.observe(state)
        policy = None
        if forced:
            action = next(iter(options))
            controller, event_type = 'deterministic_execution', 'deterministic'
            forced_student += int(controlled)
            forced_opponent += int(not controlled)
        elif controlled:
            captured = deepcopy(record)
            action, policy = await sampler.policy_action(captured, job['episode_id'], ordinal)
            if captured != record:
                raise ValueError('chess_policy_modified_captured_record')
            _policy(record, action, policy, evaluation, teacher)
            student_calls += 1
            controller, event_type = 'model', 'policy'
        elif mode == 'qwen3.8-max':
            captured = deepcopy(record)
            action, _ = await sampler.qwen('chess', job['seed'], ordinal, captured)
            if captured != record:
                raise ValueError('chess_opponent_modified_captured_record')
            qwen_calls += 1
            controller, event_type = 'qwen3.8-max', 'opponent'
        else:
            action = chess.rule_action(state, ordinal)
            rule_calls += 1
            controller, event_type = 'rule_engine', 'opponent'
        if action not in options:
            raise ValueError('illegal_chess_action')
        before = deepcopy(state)
        state = engine.step(state, action, controller=controller)
        event = {'type': event_type, 'ordinal': ordinal, 'actor': actor,
            'controlled': controlled, 'controller': controller,
            'execution_origin': 'B' if forced else 'A' if controlled else 'opponent',
            'record': deepcopy(record), 'action': action, 'before_state': before,
            'after_state': deepcopy(state)}
        if controlled and not forced:
            event['policy'] = deepcopy(policy)
            row = {key: deepcopy(event[key]) for key in
                ('ordinal', 'actor', 'record', 'action', 'before_state', 'after_state', 'policy')}
            row.update(applied=True, action_applied=True)
            trace.append(row)
            _journal(sampler, job, 'decision', {key: deepcopy(row[key])
                for key in ('ordinal', 'record', 'action', 'policy')})
            _journal(sampler, job, 'executed', row)
        else:
            _journal(sampler, job, 'deterministic_execution' if forced else 'opponent_execution', event)
        events.append(event)
    outcome = engine.outcome(state, side) or 'budget_exhausted'
    extra = {'chess_rollout_revision': REVISION, 'chess_engine_revision': chess.REVISION,
        'events': events, 'controlled_side': side, 'opponent': mode,
        'decision_limit': budget, 'ply_limit': engine.limit,
        ('teacher_policy_requests' if teacher else 'student_policy_requests'): student_calls, 'qwen_calls': qwen_calls,
        'rule_opponent_actions': rule_calls, 'deterministic_student_actions': forced_student,
        'deterministic_opponent_actions': forced_opponent, 'rule_takeover_count': 0,
        'verified_outcome': outcome, 'native_outcome': engine.outcome(state, side),
        'budget_exhausted': outcome == 'budget_exhausted', 'credit_revision': CREDIT_REVISION,
        'evaluation_only': evaluation, 'reward_export_prohibited': evaluation or teacher}
    if evaluation:
        extra.update(on_policy=False, policy_origin='evaluation')
    if teacher:
        extra.update(on_policy=False, policy_origin='teacher', teacher_distillation=True)
    return initial, state, _credit(trace, state), outcome, extra


async def play(sampler, job):
    return await _play(sampler, job, evaluation=False)


async def play_evaluation(sampler, job):
    """Same engine/choices; explicitly excludes evaluator outputs from RL."""
    return await _play(sampler, job, evaluation=True)


async def play_teacher(sampler, job):
    """Full native games for supervised distillation, never policy-gradient data."""
    return await _play(sampler, job, evaluation=False, teacher=True)


def _verify(job, initial, final, extra, trace=None, *, evaluation, teacher=False):
    """Replay all seats/forced moves and bind every PG row to its exact action."""
    engine, side, mode, budget = _settings(job)
    state = engine.reset(job['seed'], {'opponent': mode, 'max_plies': engine.limit})
    if (state != initial or extra.get('controlled_side') != side or extra.get('opponent') != mode
            or extra.get('chess_rollout_revision') != REVISION
            or extra.get('chess_engine_revision') != chess.REVISION
            or extra.get('decision_limit') != budget or extra.get('ply_limit') != engine.limit
            or extra.get('evaluation_only') is not evaluation
            or extra.get('reward_export_prohibited') is not (evaluation or teacher)
            or extra.get('teacher_distillation', False) is not teacher
            or teacher and (extra.get('on_policy') is not False or extra.get('policy_origin') != 'teacher')
            or evaluation and (extra.get('on_policy') is not False or extra.get('policy_origin') != 'evaluation')):
        raise ValueError('chess_replay_identity_changed')
    events = extra.get('events')
    if not isinstance(events, list) or len(events) > engine.limit or trace is None:
        raise ValueError('chess_replay_requires_all_events_and_student_trace')
    reconstructed = []
    student_calls = qwen_calls = forced_student = forced_opponent = rule_calls = 0
    for ordinal, event in enumerate(events):
        if engine.outcome(state, side):
            raise ValueError('chess_action_after_terminal')
        actor, options = chess.actor(state), engine.legal_actions(state)
        controlled, forced = actor == side, len(options) == 1
        if not options or controlled and not forced and student_calls >= budget:
            raise ValueError('chess_action_after_decision_budget')
        controller = ('deterministic_execution' if forced else 'model' if controlled
                      else mode)
        event_type = 'deterministic' if forced else 'policy' if controlled else 'opponent'
        if (event.get('ordinal') != ordinal or event.get('actor') != actor
                or event.get('controlled') is not controlled or event.get('controller') != controller
                or event.get('type') != event_type
                or event.get('execution_origin') != ('B' if forced else 'A' if controlled else 'opponent')
                or event.get('before_state') != state or event.get('record') != engine.observe(state)
                or event.get('action') not in options):
            raise ValueError('chess_replay_observation_actor_or_action_changed')
        action = event['action']
        if forced:
            if 'policy' in event or action != next(iter(options)):
                raise ValueError('chess_forced_execution_cannot_claim_policy')
            forced_student += int(controlled)
            forced_opponent += int(not controlled)
        elif controlled:
            _policy(event['record'], action, event.get('policy'), evaluation, teacher)
            student_calls += 1
        elif mode == 'qwen3.8-max':
            if 'policy' in event:
                raise ValueError('chess_opponent_cannot_claim_student_policy')
            qwen_calls += 1
        else:
            if 'policy' in event or chess.rule_action(state, ordinal) != action:
                raise ValueError('chess_rule_opponent_replay_changed')
            rule_calls += 1
        state = engine.step(state, action, controller=controller)
        if state != event.get('after_state'):
            raise ValueError('chess_replay_transition_changed')
        if controlled and not forced:
            row = {key: deepcopy(event[key]) for key in
                ('ordinal', 'actor', 'record', 'action', 'before_state', 'after_state', 'policy')}
            row.update(applied=True, action_applied=True)
            reconstructed.append(row)
    native_outcome = engine.outcome(state, side)
    if not native_outcome and len(events) < engine.limit:
        if not (chess.actor(state) == side and len(engine.legal_actions(state)) > 1 and student_calls == budget):
            raise ValueError('chess_replay_ended_before_terminal_or_budget')
    expected = {('teacher_policy_requests' if teacher else 'student_policy_requests'): student_calls, 'qwen_calls': qwen_calls,
        'rule_opponent_actions': rule_calls, 'deterministic_student_actions': forced_student,
        'deterministic_opponent_actions': forced_opponent, 'rule_takeover_count': 0,
        'verified_outcome': native_outcome or 'budget_exhausted', 'native_outcome': native_outcome,
        'budget_exhausted': (native_outcome or 'budget_exhausted') == 'budget_exhausted',
        'credit_revision': CREDIT_REVISION}
    if any(extra.get(key) != value for key, value in expected.items()):
        raise ValueError('chess_replay_terminal_or_ownership_counts_changed')
    if state != final or _credit(reconstructed, final) != trace:
        raise ValueError('chess_replay_final_or_student_trace_changed')
    return True


def verify(job, initial, final, extra, trace=None):
    return _verify(job, initial, final, extra, trace, evaluation=False)


def verify_evaluation(job, initial, final, extra, trace=None):
    return _verify(job, initial, final, extra, trace, evaluation=True)


def verify_teacher(job, initial, final, extra, trace=None):
    return _verify(job, initial, final, extra, trace, evaluation=False, teacher=True)
