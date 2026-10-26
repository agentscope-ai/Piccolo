"""A narrow public rule-state exception to cancellation, NEVER to training.

Only standard Tetris before its first locked piece or at the exact public
spawn immediately after one legal first placement, standard Goofspiel
before the first sealed round resolves, and the exact initial blind Zha Jin Hua
view are recognized. The independent frozen-condition guard must still accept the
whole episode. When a recognized input hits the protected-state index, keep
every action/reward in the trajectory and RTG but exclude that input from ALL
losses (including reference KL). Unprotected training inputs remain eligible.
V4 consequences
are checked with the shared current-piece projection of validated public facts;
no seed, private RNG, future spawn, evaluation answer or condition catalogue is read.
"""
from __future__ import annotations

import math
import re

REVISION = 'jev.shared-rule-opening.tetris-first-piece-v2-latency'

# Fixed PUBLIC shape/rotation contract of tetris-realtime-v1. This validates
# visible cells, not an engine, action planner or hidden piece sequence.
_SHAPES = {
    'I': (((0, 0), (1, 0), (2, 0), (3, 0)), ((0, 0), (0, 1), (0, 2), (0, 3))),
    'O': (((0, 0), (0, 1), (1, 0), (1, 1)),),
    'T': (((0, 0), (1, 0), (1, 1), (2, 0)), ((0, 1), (1, 0), (1, 1), (1, 2)),
          ((0, 1), (1, 0), (1, 1), (2, 1)), ((0, 0), (0, 1), (0, 2), (1, 1))),
    'S': (((0, 1), (1, 0), (1, 1), (2, 0)), ((0, 0), (0, 1), (1, 1), (1, 2))),
    'Z': (((0, 0), (1, 0), (1, 1), (2, 1)), ((0, 1), (0, 2), (1, 0), (1, 1))),
    'J': (((0, 0), (0, 1), (1, 1), (2, 1)), ((0, 0), (0, 1), (0, 2), (1, 0)),
          ((0, 0), (1, 0), (2, 0), (2, 1)), ((0, 2), (1, 0), (1, 1), (1, 2))),
    'L': (((0, 1), (1, 1), (2, 0), (2, 1)), ((0, 0), (0, 1), (0, 2), (1, 2)),
          ((0, 0), (0, 1), (1, 0), (2, 0)), ((0, 0), (1, 0), (1, 1), (1, 2))),
}
_FIELDS = frozenset(('kind', 'engine_revision', 'width', 'height', 'board', 'lines', 'line_target',
    'steps', 'max_steps', 'score', 'decisions', 'max_model_decisions', 'started', 'elapsed', 'time_limit',
    'simulation_clock', 'simulation_ticks', 'outcome', 'failure_reason', 'piece', 'next_piece', 'active',
    'phase', 'gravity_clock', 'lock_clock', 'clear_clock', 'clearing_rows', 'pending_intent',
    'input_clock', 'event', 'ghost_cells', 'gravity_interval', 'lock_delay', 'clear_delay',
    'seconds_to_next_fall', 'seconds_to_lock', 'rules', 'grid', 'timing'))
_EVENTS = {'ready', 'input', 'intent_reached', 'intent_input', 'intent_blocked', 'falling', 'locking', 'intent_deadline_risk'}
_LATENCY_REVISION = 'tetris-realtime-v4-latency-contract'
_PERSISTENT_REVISIONS = {'tetris-realtime-v3-persistent-intent', _LATENCY_REVISION}
_TETRIS_REVISIONS = {'tetris-realtime-v1', 'tetris-realtime-v2-visible-consequences', *_PERSISTENT_REVISIONS}
_CONSEQUENCE_SUFFIX = re.compile(
    r'｜即时情景：消行[0-4]；孔洞\d+→\d+（新增\d+/解除\d+）；'
    r'最高列\d+；起伏\d+；深井\d+；顶部连通空格\d+；预告出生(?:未知|通畅|被堵)；'
    r'目标(?:已达|受阻|未达)；本块(?:已锁定|未锁定)；结算约\d+(?:\.\d+)?秒｜'
    r'延迟1.5秒情景：(?:过期或终止，未施加|消行[0-4]/孔洞\d+/目标(?:已达|未达))；非概率')


def _result(recognized, reason, evidence=None):
    return {'schema_version': REVISION, 'recognized': recognized,
        'allow_execution_only': recognized, 'exclude_from_training': recognized,
        # "execution only" distinguishes rollout from loss export. The
        # meaningful action is STILL selected by student strategy A; this flag
        # never selects a deterministic B action or permits C takeover.
        'strategy_origin': 'A' if recognized else None,
        'student_policy_action_required': recognized,
        'condition_guard_required': True, 'protected_condition_exemption': False,
        'reason': reason, 'public_evidence': evidence or {}}


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value < high


def _request_pause_clock(timing):
    """Accept only the exact visible pause mode; bool/int lookalikes deny."""
    return (type(timing) is dict and
            type(timing.get('control_clock_mode')) is str and
            timing['control_clock_mode'] == 'request_pause' and
            type(timing.get('mode')) is str and
            timing['mode'] == 'request_paused_simulation' and
            timing.get('continues_during_inference') is False and
            timing.get('request_wait_advances_world') is False)


def _matches_timing_contract(actual, realtime_expected):
    # The original realtime comparison is intentionally unchanged. A paused
    # record must match the full expected mapping with exact types and keys.
    if _request_pause_clock(actual):
        expected = {**realtime_expected, 'mode': 'request_paused_simulation',
            'continues_during_inference': False, 'control_clock_mode': 'request_pause',
            'request_wait_advances_world': False}
        return _typed_public_equal(actual, expected)
    return actual == realtime_expected


def classify_shared_rule_opening(record):
    """Explicit execution-only whitelist; all unrecognized contracts deny."""
    if not isinstance(record, dict) or record.get('schema_version') != 'jev.training.v1':
        return _result(False, 'unsupported_record_schema')
    state = record.get('state')
    metadata = record.get('metadata')
    if isinstance(metadata, dict) and metadata.get('sub_domain') == 'goofspiel':
        return _classify_goofspiel(record)
    if isinstance(metadata, dict) and metadata.get('sub_domain') == 'zha_jin_hua':
        return _classify_zha_blind_opening(record)
    if not isinstance(state, dict) or state.get('kind') != 'tetris_placement':
        return _result(False, 'unsupported_kind')
    metadata, provenance = record.get('metadata'), record.get('provenance')
    latency_contract = state.get('engine_revision') == _LATENCY_REVISION
    expected_fields = _FIELDS | ({'placement_plan'} if state.get('engine_revision') in _PERSISTENT_REVISIONS else set())
    if (not isinstance(metadata, dict) or not isinstance(provenance, dict) or
            state.get('engine_revision') not in _TETRIS_REVISIONS or
            set(state) not in (expected_fields, expected_fields | {'controller'}) or
            metadata.get('sub_domain') != 'tetris_placement' or
            provenance.get('source_revision') != state.get('engine_revision') or
            record.get('labels') != {}):
        return _result(False, 'unrecognized_public_contract')
    if latency_contract and type(state.get('steps')) is int and state['steps'] == 1:
        return _classify_tetris_first_placement(record)
    try:
        constants = {'width': 10, 'height': 12, 'line_target': 4, 'max_steps': 40,
            'max_model_decisions': 320, 'time_limit': 240., 'gravity_interval': .8,
            'lock_delay': .46, 'clear_delay': .22}
        if (any(state[key] != value for key, value in constants.items()) or
                state['phase'] not in ('falling', 'locking') or state['event'] not in _EVENTS):
            return _result(False, 'different_rule_budget_or_phase')
        # In this exact engine revision, _lock increments steps, and _spawn
        # assigns piece_id = steps + 1. Their public combination rules out later
        # cleared boards as well as any previously locked block.
        if (state['outcome'] is not None or state['failure_reason'] is not None or
                state['clearing_rows'] != [] or state['clear_clock'] != 0 or
                any(type(state[key]) is not int or state[key] != 0 for key in ('steps', 'lines', 'score'))):
            return _result(False, 'already_locked_or_not_first_piece')
        board = state['board']
        if (not isinstance(board, list) or len(board) != 12 or
                any(not isinstance(row, list) or len(row) != 10 or
                    any(type(cell) is not int or cell != 0 for cell in row) for row in board)):
            return _result(False, 'nonempty_or_nonstandard_board')
        piece, preview = state['piece'], state['next_piece']
        if piece not in _SHAPES or preview not in _SHAPES or piece == preview:
            return _result(False, 'invalid_visible_first_bag_piece')
        active = state['active']
        if (not isinstance(active, dict) or
                set(active) != {'piece', 'piece_id', 'x', 'y', 'rotation', 'cells'} or
                active['piece'] != piece or type(active['piece_id']) is not int or active['piece_id'] != 1 or
                any(type(active[key]) is not int for key in ('x', 'y', 'rotation')) or
                not 0 <= active['rotation'] < len(_SHAPES[piece])):
            return _result(False, 'not_visible_first_piece')
        x, y, rotation = active['x'], active['y'], active['rotation']
        cells = [[x + cx, y + cy] for cx, cy in _SHAPES[piece][rotation]]
        if active['cells'] != cells or any(not (0 <= cx < 10 and 0 <= cy < 12) for cx, cy in cells):
            return _result(False, 'inconsistent_or_unreachable_visible_cells')
        grid = [['.'] * 10 for _ in range(12)]
        for cx, cy in cells:
            grid[cy][cx] = '@'
        drop = 11 - max(cy for _, cy in cells)
        if (state['grid'] != [''.join(row) for row in grid] or
                state['ghost_cells'] != [[cx, cy + drop] for cx, cy in cells]):
            return _result(False, 'inconsistent_visible_board_facts')
        if (type(state['started']) is not bool or type(state['decisions']) is not int or
                not 0 <= state['decisions'] <= 320 or type(state['simulation_ticks']) is not int or
                state['simulation_ticks'] < 0 or not _number(state['elapsed'], 0, 240) or
                not _number(state['simulation_clock'], 0, .02) or
                not _number(state['gravity_clock'], 0, .8) or not _number(state['lock_clock'], 0, .46) or
                not _number(state['input_clock'], 0, .08) or
                abs(state['elapsed'] - state['simulation_ticks'] * .02 - state['simulation_clock']) > 1e-7 or
                state['seconds_to_next_fall'] != round(.8 - state['gravity_clock'], 3) or
                state['seconds_to_lock'] != round(.46 - state['lock_clock'], 3)):
            return _result(False, 'inconsistent_first_piece_clock')
        timing = {'mode': 'realtime_wall_clock', 'continues_during_inference': True,
            'seconds_to_next_fall': state['seconds_to_next_fall'],
            'seconds_to_lock': state['seconds_to_lock'], 'gravity_interval': .8,
            'automatic_actions': 0, 'placement_input_interval': .08}
        if latency_contract:
            window = state['timing']['control_window']
            expected_window = {'piece_id', 'binding', 'prediction_type', 'new_piece_control_authorized',
                'latency_scenarios_seconds', 'uncertainty', 'seconds_to_lock_without_new_input',
                'clock_starts_on_first_applied_input'} | ({'ends_by'} if state['started'] else set())
            if (not isinstance(window, dict) or set(window) != expected_window or
                    type(window['piece_id']) is not int or window['piece_id'] != 1 or
                    window['binding'] != 'current_piece_only' or
                    window['prediction_type'] != 'deterministic_visible_physics_without_new_input' or
                    window['new_piece_control_authorized'] is not False or
                    window['clock_starts_on_first_applied_input'] is not (not state['started']) or
                    not isinstance(window['latency_scenarios_seconds'], list) or
                    window['latency_scenarios_seconds'] != [3.2, 7.] or
                    any(type(n) not in (int, float) for n in window['latency_scenarios_seconds']) or
                    window['uncertainty'] != 'new input may change landing; service delay unknown; no future piece simulated' or
                    (state['started'] and (not _number(window['seconds_to_lock_without_new_input'], 0, 240) or
                                          window['ends_by'] not in ('piece_lock', 'terminal'))) or
                    (not state['started'] and window['seconds_to_lock_without_new_input'] is not None)):
                return _result(False, 'nonstandard_first_piece_latency_window')
            timing['control_window'] = window
        if not _matches_timing_contract(state['timing'], timing):
            return _result(False, 'nonstandard_clock_contract')
        if state['started']:
            if state.get('controller') != 'model' or state['decisions'] < 1 or state['event'] == 'ready':
                return _result(False, 'not_current_student_execution')
        else:
            spawn_x = (9 - max(cx for cx, _ in _SHAPES[piece][0])) // 2
            if (state['event'] != 'ready' or state['phase'] != 'falling' or
                    (x, y, rotation) != (spawn_x, 0, 0) or state['pending_intent'] is not None or
                    'controller' in state or any(state[key] != 0 for key in
                        ('decisions', 'elapsed', 'simulation_clock', 'simulation_ticks',
                         'gravity_clock', 'lock_clock', 'input_clock'))):
                return _result(False, 'not_standard_first_spawn')
        questions = record['questions']
        if set(questions) != {'decision'} or questions['decision']['type'] != 'choice':
            return _result(False, 'not_single_joint_choice')
        decision = questions['decision']
        expected = {f'{rot}:{column}' for rot, shape in enumerate(_SHAPES[piece])
                    for column in range(10 - max(cx for cx, _ in shape))}
        order = decision['option_order']
        if (set(decision['criteria']) != expected or not isinstance(order, list) or
                len(order) != len(expected) or set(order) != expected):
            return _result(False, 'nonstandard_candidate_set')
        if state['engine_revision'] in ('tetris-realtime-v2-visible-consequences','tetris-realtime-v3-persistent-intent'):
            if provenance.get('candidate_revision') != 'tetris-visible-intent-consequences-v1':
                return _result(False, 'unrecognized_visible_consequence_contract')
            for action, description in decision['criteria'].items():
                candidate_rotation, candidate_column = map(int, action.split(':'))
                prefix = f'旋转 {candidate_rotation}，左侧第 {candidate_column + 1} 列'
                if (not isinstance(description, str) or not description.startswith(prefix) or
                        not _CONSEQUENCE_SUFFIX.fullmatch(description[len(prefix):])):
                    return _result(False, 'nonstandard_visible_consequence_description')
        if state['engine_revision'] in _PERSISTENT_REVISIONS:
            plan=state['placement_plan']
            if plan is not None:
                if (not isinstance(plan,dict) or set(plan)!={'rotation','column','piece_id','decision','status','reason',
                        'strategy_origin','execution_origin','expires_on','absolute_time_limit'} or
                        any(type(plan[k]) is not int for k in ('rotation','column','piece_id','decision')) or
                        plan['piece_id']!=1 or plan['decision']!=state['decisions'] or not state['started'] or
                        f"{plan['rotation']}:{plan['column']}" not in expected or
                        plan['strategy_origin']!='A' or plan['execution_origin']!='B' or
                        plan['expires_on']!='current_piece_lock_or_terminal' or plan['absolute_time_limit']!=240. or
                        (plan['status'],plan['reason']) not in {('executing','selected_intent'),
                            ('holding','target_reached_waiting_for_gravity'),('blocked','intent_blocked'),
                            ('danger','contact_window_shorter_than_minimum_inputs')}):
                    return _result(False,'nonstandard_persistent_first_piece_plan')
                if plan['status']=='holding' and (plan['rotation']!=rotation or plan['column']!=x):
                    return _result(False,'inconsistent_completed_first_piece_target')
        intent = state['pending_intent']
        if intent is not None and (not isinstance(intent, dict) or
                set(intent) != {'rotation', 'column', 'piece_id'} or
                any(type(intent[key]) is not int for key in intent) or intent['piece_id'] != 1 or
                f"{intent['rotation']}:{intent['column']}" not in expected):
            return _result(False, 'nonstandard_pending_intent')
        if latency_contract:
            if provenance.get('candidate_revision') != 'tetris-visible-intent-consequences-v2-latency':
                return _result(False, 'unrecognized_visible_consequence_contract')
            # All first-piece/geometry/clock/plan checks precede recomputation.
            # This shared helper strips presentation, rejects private fields and
            # stops before the next spawn. It never calls fresh/reset or a policy.
            from jev_tetris_projection import choice_descriptions, control_window
            if state['timing']['control_window'] != control_window(state):
                return _result(False, 'inconsistent_first_piece_latency_window')
            if decision['criteria'] != choice_descriptions(state):
                return _result(False, 'nonstandard_visible_consequence_description')
    except (KeyError, TypeError, ValueError, AttributeError):
        return _result(False, 'malformed_public_facts')
    return _result(True, 'universal_tetris_first_piece_execution_only', {
        'kind': 'tetris_placement', 'engine_revision': state['engine_revision'],
        'board_dimensions': [12, 10], 'occupied_cells': 0, 'placed_pieces': state['steps'],
        'decisions': state['decisions'], 'elapsed': state['elapsed'], 'started': state['started'],
        'active_piece_id': 1, 'lines': 0, 'score': 0, 'visible_piece': piece,
        'visible_next_piece': preview, 'active_pose': {'x': x, 'y': y, 'rotation': rotation},
        'line_target': 4, 'first_piece_proof': 'v1 _lock increments steps; _spawn piece_id=steps+1',
        'policy': 'student executes; this whole observation is excluded from every loss',
        'seed_or_hidden_sequence_read': False})


def _classify_tetris_first_placement(record):
    """A finite rule prefix, not a blanket exception for protected board states.

    Four bottom-supported cells must be exactly one public tetromino. The
    second piece must still be at its untouched standard spawn. Recreate the
    complete record from these public facts; do not reset an environment or
    inspect a seed, future bag, evaluation catalogue or label. The caller has
    already checked the exact public field set and version. If the observation
    hits the protected-state index, every loss masks it. The independent episode
    condition guard remains mandatory.
    """
    def result(ok, reason, evidence=None):
        return {**_result(ok, reason, evidence),
                'schema_version': 'jev.shared-rule-opening.tetris-first-placement-v1'}
    try:
        import jev_tetris_realtime as game
        state = record['state']
        fixed = {'kind': 'tetris_placement', 'engine_revision': _LATENCY_REVISION,
                 'width': 10, 'height': 12, 'line_target': 4, 'max_steps': 40,
                 'max_model_decisions': 320, 'time_limit': 240., 'gravity_interval': .8,
                 'lock_delay': .46, 'clear_delay': .22, 'steps': 1, 'lines': 0,
                 'score': 0, 'started': True, 'phase': 'falling', 'event': 'spawn',
                 'outcome': None, 'failure_reason': None, 'clearing_rows': [],
                 'clear_clock': 0., 'lock_clock': 0., 'placement_plan': None,
                 'pending_intent': None, 'controller': 'model'}
        if any(not _typed_public_equal(state.get(key), value) for key, value in fixed.items()):
            return result(False, 'not_exact_second_piece_spawn_contract')
        board = state['board']
        if (not isinstance(board, list) or len(board) != 12 or
                any(not isinstance(row, list) or len(row) != 10 or
                    any(type(cell) is not int or cell not in (0, 1) for cell in row) for row in board)):
            return result(False, 'nonstandard_first_placement_board')
        occupied = {(x, y) for y, row in enumerate(board) for x, cell in enumerate(row) if cell}
        if len(occupied) != 4:
            return result(False, 'not_exactly_one_locked_tetromino')
        piece, preview = state['piece'], state['next_piece']
        if piece not in _SHAPES or preview not in _SHAPES or piece == preview:
            return result(False, 'invalid_public_first_bag')
        matches = []
        for prior_piece, shapes in _SHAPES.items():
            if prior_piece in (piece, preview):
                continue  # Three distinct visible shapes in the first seven-bag.
            for rotation, shape in enumerate(shapes):
                bottom_y = 11 - max(y for _, y in shape)
                for column in range(10 - max(x for x, _ in shape)):
                    if occupied == {(column + x, bottom_y + y) for x, y in shape}:
                        matches.append({'piece': prior_piece, 'rotation': rotation, 'column': column})
        if not matches:
            return result(False, 'not_a_legal_empty_board_first_placement')
        spawn_x = (9 - max(x for x, _ in _SHAPES[piece][0])) // 2
        active = {'piece': piece, 'piece_id': 2, 'x': spawn_x, 'y': 0, 'rotation': 0,
                  'cells': [[spawn_x + x, y] for x, y in _SHAPES[piece][0]]}
        if not _typed_public_equal(state['active'], active):
            return result(False, 'second_piece_already_moved')
        if (type(state['decisions']) is not int or not 1 <= state['decisions'] <= 320 or
                type(state['simulation_ticks']) is not int or state['simulation_ticks'] < 1 or
                # No soft/hard drop is in the model's placement Choice. On
                # the empty 12-row board, the first natural lock is between
                # 6.84 and 9.24 seconds; less than .8 seconds can then pass
                # before the untouched second piece falls its first cell.
                not _number(state['elapsed'], 6.8, 10.1) or
                not _number(state['simulation_clock'], 0, .02) or
                not _number(state['gravity_clock'], 0, .8) or
                not _number(state['input_clock'], 0, .08) or
                abs(state['elapsed'] - state['simulation_ticks'] * .02 - state['simulation_clock']) > 1e-7):
            return result(False, 'inconsistent_first_placement_clock')
        # Standard pose at y=0 and event=spawn excludes every second-piece input
        # or gravity step. Rebuild all grid/ghost/timing/option/prompt facts. This
        # public-only call cannot spawn a new piece or read a seed.
        expected_record = game.as_record(state)
        if _request_pause_clock(state.get('timing')):
            # Rebuild the complete paused record through the production clock
            # producer, including its prompt/candidate wording. Never strip or
            # normalize fields from the actual protected observation.
            from jev_engine_snapshot import control_record
            expected_record = control_record(expected_record, 'request_pause')
        if not _typed_public_equal(record, expected_record):
            return result(False, 'inconsistent_first_placement_public_record')
    except (KeyError, TypeError, ValueError, AttributeError):
        return result(False, 'malformed_first_placement_public_facts')
    return result(True, 'universal_tetris_first_placement_execution_only', {
        'kind': 'tetris_placement', 'engine_revision': _LATENCY_REVISION,
        'occupied_cells': 4, 'placed_pieces': 1, 'active_piece_id': 2,
        'active_at_standard_spawn': True, 'legal_first_placements': matches,
        'visible_piece': piece, 'visible_next_piece': preview,
        'policy': 'student executes; this whole observation is excluded from every loss',
        'seed_hidden_sequence_evaluation_answer_read': False})


_GOOF_REVISION = 'jev.shared-rule-opening.goofspiel-first-round-v1'
_GOOF_RULES = ('双方各有 1–7 的七张牌。每轮翻出一张随机奖分牌，双方密封选择一张未用手牌，同时揭示。'
    '出牌较大者获得奖分；相同则该奖分作废。手牌各用一次，最后只剩一张时自动出牌。'
    '七轮后总分高者胜。对手剩余手牌公开，当轮密封出牌不可见。')
_GOOF_FIELDS = {'kind', 'steps', 'history', 'last_move', 'rounds', 'current_player', 'players',
    'rules', 'outcome', 'hands', 'points', 'prize', 'remaining'}
_GOOF_CONTROL = {'revision': 'visible-intent-executor-v2', 'goal': '', 'subgoal': None,
    'status': 'awaiting_decision', 'recent_effects': [], 'no_progress_count': 0,
    'repeated_action_count': 0, 'events': [], 'execution_origin': 'B', 'strategy_origin': 'A',
    'fallback_actions': 0, 'deadline': 1, 'deadline_unit': 'selected_action',
    'abort_on': ['blocked', 'landed', 'danger_changed', 'expired', 'terminal']}


def _classify_goofspiel(record):
    def result(ok, reason, evidence=None):
        return {**_result(ok, reason, evidence), 'schema_version': _GOOF_REVISION}
    try:
        state, provenance = record['state'], record['provenance']
        if (not isinstance(state, dict) or set(state) != {'role', 'observation', 'control'} or
                not isinstance(provenance, dict) or provenance.get('data_source') != 'jev_live_agent_games' or
                provenance.get('source_revision') != '20261009-v1' or record['labels'] != {}):
            return result(False, 'unrecognized_goofspiel_public_contract')
        observed = state['observation']
        if (not isinstance(observed, dict) or set(observed) != _GOOF_FIELDS or
                observed['kind'] != 'goofspiel' or observed['rules'] != _GOOF_RULES or
                observed['players'] != ['玩家一', '玩家二'] or state['control'] != _GOOF_CONTROL):
            return result(False, 'nonstandard_goofspiel_rules_or_control')
        actor, steps = observed['current_player'], observed['steps']
        if (type(actor) is not int or actor not in (0, 1) or type(steps) is not int or steps != actor or
                state['role'] != f'你正在替玩家{"一" if actor == 0 else "二"}行动。只能依据本方可见观测，选择一个合法动作。'):
            return result(False, 'not_first_sealed_round_actor')
        if (observed['history'] != [] or observed['rounds'] != [] or observed['last_move'] is not None or
                observed['outcome'] is not None or observed['hands'] != [list(range(1,8)), list(range(1,8))] or
                observed['points'] != [0,0] or
                any(type(value) is not int for hand in observed['hands'] for value in hand) or
                any(type(value) is not int for value in observed['points'])):
            return result(False, 'goofspiel_round_already_resolved_or_custom_hands')
        prize = observed['prize']
        if (type(prize) is not int or prize not in range(1,8) or
                observed['remaining'] != [x for x in range(1,8) if x != prize] or
                any(type(value) is not int for value in observed['remaining'])):
            return result(False, 'nonstandard_public_prize_set')
        questions = record['questions']
        if not isinstance(questions, dict) or set(questions) != {'decision'}:
            return result(False, 'not_single_joint_choice')
        question = questions['decision']
        criteria = {str(i): f'密封出牌 · {i+1}' for i in range(7)}
        order = question.get('option_order')
        if (question.get('type') != 'choice' or question.get('criteria') != criteria or
                not isinstance(order, list) or len(order) != 7 or set(order) != set(criteria)):
            return result(False, 'nonstandard_goofspiel_candidate_semantics')
    except (KeyError, TypeError, ValueError, AttributeError):
        return result(False, 'malformed_goofspiel_public_facts')
    return result(True, 'universal_goofspiel_first_sealed_round_execution_only', {
        'kind': 'goofspiel', 'source_revision': '20261009-v1',
        'control_revision': 'visible-intent-executor-v2', 'current_player': actor, 'steps': steps,
        'visible_prize': prize, 'full_public_hands': True, 'scores': [0,0], 'resolved_rounds': 0,
        'first_round_proof': 'steps is 0 for player 0 or 1 for player 1; both full hands and no revealed history',
        'policy': 'student executes; this whole observation is excluded from every loss',
        'seed_hidden_bid_or_future_prize_order_read': False})


_ZHA_REVISION = 'jev.shared-rule-opening.zha-initial-blind-v1'
_ZHA_RULES = ('双人三张牌、虚拟筹码各 200，双方先各付 10。自建固定规则：豹子 > 顺金 > 金花 > 顺子 > 对子 > 单张；'
    'A23 是最小顺子。同牌由主动比牌者负。闷牌下注额为当前档位，看牌后为两倍；可跟注或加注至最多 40。'
    '至少跟注一轮后可付费比牌，第五轮或筹码耗尽时自动摊牌。对手底牌在摊牌前不可见；'
    'random_hand_equity 仅是对随机三张牌的精确胜率，不代表对该对手的胜率。')
_ZHA_OBSERVATION = {'kind': 'zha_jin_hua', 'steps': 0, 'stacks': [190, 190],
    'pot': 20, 'stake': 10, 'round': 0, 'seen': False, 'opponent_seen': False,
    'showdown': False, 'outcome': None, 'score': 0,
    'event': '双方各投入 10 筹码；可以闷牌或先看牌。', 'history': [],
    'hand': None, 'opponent_hand': None,
    'card_encoding': '0..12=♠2..A,13..25=♥2..A,26..38=♣2..A,39..51=♦2..A'}
_ZHA_QUESTION = {'type': 'choice',
    'instructions': ('目标是赢得本手底池。根据手牌信息、底池赔率、已投入筹码和剩余轮数选择；'
        '闷牌时不得假设自己或对手的隐藏牌。看牌后可使用随机手牌胜率作参考，并留意看牌后的双倍下注成本。'
        '只输出合法动作 ID。'),
    'criteria': {'fold': '弃牌', 'peek': '看自己的三张牌（此后下注额翻倍）',
                 'call': '跟注 10', 'raise': '加注至 20'},
    'option_order': ['fold', 'peek', 'call', 'raise']}


def _classify_zha_blind_opening(record):
    """Exact seed-independent public prefix, never a revealed card layout.

    The current probability-game record has no separate source_revision; bind
    its versioned data_source plus the COMPLETE public state and Choice text.
    Unknown fields or semantics deny. Never inspect hidden hands or a seed.
    """
    def result(ok, reason, evidence=None):
        return {**_result(ok, reason, evidence), 'schema_version': _ZHA_REVISION}
    expected_state = {'role': '玩家0', 'rules': _ZHA_RULES,
        'observation': _ZHA_OBSERVATION,
        'control': {**_GOOF_CONTROL, 'goal': _ZHA_RULES[:180]}}
    try:
        # Typed public comparison rejects bool-as-int, tuple-as-list, extra
        # fields and NaN instead of Python's loose True == 1 equivalence.
        if (record.get('labels') != {} or
                record.get('provenance') != {'data_source': 'cues_probability_games_v1',
                    'source_id': 'live', 'source_split': 'demo'} or
                not _typed_public_equal(record['state'], expected_state) or
                not _typed_public_equal(record['questions'], {'decision': _ZHA_QUESTION})):
            return result(False, 'not_exact_standard_zha_initial_blind_public_contract')
    except (KeyError, TypeError, ValueError):
        return result(False, 'malformed_zha_public_facts')
    return result(True, 'universal_zha_initial_blind_execution_only', {
        'kind': 'zha_jin_hua', 'data_source': 'cues_probability_games_v1',
        'control_revision': 'visible-intent-executor-v2', 'actor': 0, 'steps': 0,
        'round': 0, 'hand_visible': False, 'opponent_hand_visible': False,
        'candidate_values': ['fold', 'peek', 'call', 'raise'],
        'public_prefix_proof': 'fixed initial ante/stacks; neither player has looked; no public history',
        'policy': 'student A chooses all four strategies; no forced peek; exclude this entire input from every loss',
        'initial_fold_effect': 'real terminal loss and denominator retained; zero-PG episode excludes its group',
        'seed_hidden_cards_or_teacher_answers_read': False})


def _typed_public_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _typed_public_equal(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _typed_public_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected
