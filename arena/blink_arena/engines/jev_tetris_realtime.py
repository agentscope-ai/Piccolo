"""Deterministic, fixed-clock falling Tetris for the live frontend and RL.

The archived placement puzzle in jev_showcase_games is deliberately unchanged.
An explicit placement intent only sends bounded rotate/move inputs; gravity and
the finite contact lock timer keep running, even while a policy is thinking.
"""
import copy
import math
import random
from functools import lru_cache

from jev_showcase_games import rotations as _shape_rotations

KIND = 'tetris_placement'
REVISION = 'tetris-realtime-v4-latency-contract'
LEGACY_PERSISTENT_REVISION = 'tetris-realtime-v3-persistent-intent'
VISIBLE_REVISION = 'tetris-realtime-v2-visible-consequences'
PHYSICS_REVISION = 'tetris-realtime-v1'
SEED_REVISION = 'tetris-realtime-seven-bag-v1'
WIDTH, HEIGHT = 10, 12
LINE_TARGET = 4
PIECE_LIMIT = 40
TIME_LIMIT = 240.
LIMIT = 320
TICK = .02
INPUT_INTERVAL = .08
LOCK_DELAY = .46
CLEAR_DELAY = .22
PIECES = ('I', 'O', 'T', 'S', 'Z', 'J', 'L')
LABELS = {'left': '左移一格', 'right': '右移一格', 'rotate_cw': '顺时针旋转',
          'rotate_ccw': '逆时针旋转', 'soft_drop': '下降一格',
          'hard_drop': '硬降并锁定', 'wait': '保持当前操作'}
GOAL = '实时下落，在 240 秒和 40 块内消除 4 行，避免堆顶'
RULES = ('实时俄罗斯方块，棋盘12行10列，坐标[x,y]原点左上，x向右、y向下。'
         '首个操作开始计时，之后重力在思考、等待网络和没有新输入时持续生效。'
         '每格重力间隔最初0.80秒，每消一行减少0.04秒，最低0.56秒。'
         '落地累计接触0.46秒后锁定；横移、旋转和新输入不会清零重力或接触计时。'
         '消行动画持续0.22秒，然后生成下一块；方块采用确定性的七袋序列，只展示下一块。'
         '动作rotation:column是明确目标旋转和左侧列：每0.08秒执行一次旋转或横移，'
         '不会瞬移到落点、自动硬降、规划绕障或控制下一块；受阻则停止此意图。'
         '旋转只尝试当前位置及左右一格的固定墙踢，不进行向上踢。'
         '模型响应到达时若原方块已锁定，该响应必须丢弃。'
         '消除4行获胜；堆顶、40块或240秒耗尽而未达目标则失败。'
         'grid中#为已锁方块、@为正在下落的方块、.为空；ghost_cells只显示当前姿态的直线落点。')
PROMPT = ('尽快消除4行并避免堆顶。检查当前下落块的位置、旋转、重力倒计时、接触锁定时间及下方空洞。'
          '选择本块的目标旋转与左侧列；操作和推理期间仍会自然下落，请提前决定。'
          '优先完成整行，避免封住空洞或制造高柱。目标意图只机械执行旋转与横移，不会替你调整策略。')


@lru_cache(maxsize=7)
def rotations(piece):
    # Shared immutable geometry; projection and live ticks use identical shapes.
    return tuple(tuple(shape) for shape in _shape_rotations(piece))


def is_realtime(g):
    return g.get('kind') == KIND and g.get('engine_revision') in (REVISION, LEGACY_PERSISTENT_REVISION, VISIBLE_REVISION, PHYSICS_REVISION)


def persistent(g):
    return g.get('engine_revision') in (REVISION, LEGACY_PERSISTENT_REVISION)


def decision_reason(g):
    """Policy events, separate from the complete legal keyboard action set."""
    if g.get('outcome'):
        return 'terminal'
    if not g.get('active'):
        return 'clearing'
    plan = g.get('placement_plan') if persistent(g) else None
    if not plan or plan['piece_id'] != g['active']['piece_id']:
        return 'new_piece_or_manual_override'
    if plan['status'] in ('blocked', 'danger'):
        return plan['status']
    return 'continuing_intent'


def needs_decision(g):
    return decision_reason(g) not in ('terminal', 'clearing', 'continuing_intent')


def gravity_interval(g):
    return round(max(.56, .80 - .04 * g['lines']), 2)


def _piece(seed, index):
    bag = list(PIECES)
    random.Random(f'{SEED_REVISION}/{seed}/bag/{index // 7}').shuffle(bag)
    return bag[index % 7]


def cells(active):
    if not active:
        return []
    return [[active['x'] + x, active['y'] + y]
            for x, y in rotations(active['piece'])[active['rotation']]]


def _fits(g, active):
    return all(0 <= x < WIDTH and 0 <= y < HEIGHT and not g['board'][y][x]
               for x, y in cells(active))


def _moved(active, dx=0, dy=0, rotation=None):
    candidate = dict(active, x=active['x'] + dx, y=active['y'] + dy)
    if rotation is not None:
        candidate['rotation'] = rotation
    return candidate


def ghost_cells(g):
    active = g.get('active')
    if not active:
        return []
    while _fits(g, _moved(active, dy=1)):
        active = _moved(active, dy=1)
    return cells(active)


def _frame(g):
    keys = ('board', 'active', 'piece', 'next_piece', 'started', 'elapsed',
            'gravity_clock', 'lock_clock', 'clear_clock', 'phase', 'clearing_rows',
            'lines', 'steps', 'score', 'decisions', 'outcome', 'event', 'pending_intent')
    frame = {key: copy.deepcopy(g[key]) for key in keys}
    if persistent(g):
        frame['placement_plan'] = copy.deepcopy(g.get('placement_plan'))
    if frame['active']:
        frame['active']['cells'] = cells(g['active'])
    frame.update(ghost_cells=ghost_cells(g), gravity_interval=gravity_interval(g),
                 lock_delay=LOCK_DELAY, clear_delay=CLEAR_DELAY)
    return frame


def _trace(g):
    if g.get('_projection_stop_after_piece'):
        return
    frames = g.setdefault('execution_trace', {'version': 1, 'frames': []})['frames']
    frame = _frame(g)
    if not frames or frames[-1] != frame:
        frames.append(frame)
        del frames[:-64]


def _finish(g, outcome, reason):
    g.update(outcome=outcome, event=reason, failure_reason=None if outcome == 'win' else reason,
             pending_intent=None)
    _trace(g)


def _spawn(g):
    piece = _piece(g['_seed'], g['steps'])
    shape = rotations(piece)[0]
    active = {'piece': piece, 'piece_id': g['steps'] + 1,
              'x': (WIDTH - 1 - max(x for x, y in shape)) // 2, 'y': 0, 'rotation': 0}
    g.update(piece=piece, next_piece=_piece(g['_seed'], g['steps'] + 1), active=active,
             phase='falling', gravity_clock=0., lock_clock=0., clear_clock=0.,
             clearing_rows=[], pending_intent=None, input_clock=0., event='spawn')
    if persistent(g):
        g['placement_plan'] = None
    if not _fits(g, active):
        _finish(g, 'loss', 'top_out')
    _trace(g)


def fresh(seed=0, *, revision=None):
    from jev_environment_seeds import validate_seed
    validate_seed(seed)
    revision = REVISION if revision is None else revision
    if revision not in (REVISION, LEGACY_PERSISTENT_REVISION, VISIBLE_REVISION, PHYSICS_REVISION):
        raise ValueError('unknown tetris engine revision')
    g = {'kind': KIND, 'engine_revision': revision, '_seed': seed,
         'width': WIDTH, 'height': HEIGHT, 'board': [[0] * WIDTH for _ in range(HEIGHT)],
         'lines': 0, 'line_target': LINE_TARGET, 'steps': 0, 'max_steps': PIECE_LIMIT,
         'score': 0, 'decisions': 0, 'max_model_decisions': LIMIT,
         'started': False, 'elapsed': 0., 'time_limit': TIME_LIMIT,
         'simulation_clock': 0., 'simulation_ticks': 0,
         'outcome': None, 'failure_reason': None}
    _spawn(g)
    g['event'] = 'ready'
    g['execution_trace'] = {'version': 1, 'frames': [_frame(g)]}
    return g


def placement_choices(g):
    if g.get('outcome'):
        return {}
    if not g.get('active'):
        return {}
    result = {}
    for rotation, shape in enumerate(rotations(g['piece'])):
        for column in range(WIDTH - max(x for x, y in shape)):
            result[f'{rotation}:{column}'] = f'旋转 {rotation}，左侧第 {column + 1} 列'
    return result


def choices(g):
    if g.get('outcome'):
        return {}
    if not g.get('active'):
        return {}
    # A blocked key is still a valid input, as on a keyboard. It can start the
    # clock but cannot move through settled cells or reset a running clock.
    return {**LABELS, **placement_choices(g)}


def _shift(g, dx=0, dy=0):
    candidate = _moved(g['active'], dx=dx, dy=dy)
    if _fits(g, candidate):
        g['active'] = candidate
        return True
    return False


def _rotate(g, direction):
    active = g['active']
    target = (active['rotation'] + direction) % len(rotations(active['piece']))
    for dx in (0, -1, 1):
        candidate = _moved(active, dx=dx, rotation=target)
        if _fits(g, candidate):
            g['active'] = candidate
            return True
    return False


def _lock(g):
    if g.get('_projection_stop_after_piece'):
        g['_projection_landing'] = {'cells': cells(g['active']),
            **{key:g['active'][key] for key in ('x','y','rotation')}}
    for x, y in cells(g['active']):
        g['board'][y][x] = 1
    g['steps'] += 1
    if persistent(g) and g.get('placement_plan'):
        g['placement_plan'].update(status='completed', reason='piece_locked')
    g.update(active=None, pending_intent=None, clearing_rows=[
        y for y, row in enumerate(g['board']) if all(row)])
    if g['clearing_rows']:
        g.update(phase='clearing', clear_clock=0., event='line_clear')
    elif g['steps'] >= PIECE_LIMIT:
        _finish(g, 'loss', 'piece_limit')
    elif g.get('_projection_stop_after_piece'):
        g.update(phase='projection_complete', _projection_complete=True)
    else:
        _spawn(g)
    _trace(g)


def step(g, action, controller='model'):
    if action not in choices(g):
        raise ValueError('illegal tetris input or episode already finished')
    s = copy.deepcopy(g)
    s.update(started=True, decisions=s['decisions'] + 1, controller=controller, event='input')
    if action == 'wait' or not s.get('active'):
        if persistent(s):
            s['placement_plan'] = None
        _trace(s)
        return s
    if ':' in action:
        rotation, column = map(int, action.split(':'))
        s['pending_intent'] = {'rotation': rotation, 'column': column,
                               'piece_id': s['active']['piece_id']}
        if persistent(s):
            s['placement_plan'] = {'rotation':rotation,'column':column,
                'piece_id':s['active']['piece_id'],'decision':s['decisions'],
                'status':'executing','reason':'selected_intent',
                'strategy_origin':'A','execution_origin':'B',
                'expires_on':'current_piece_lock_or_terminal','absolute_time_limit':TIME_LIMIT}
        # Start mechanical input on the next fixed input tick, without touching
        # either gravity or lock timing. Repeated commands do not delay gravity.
        s['input_clock'] = 0.
    else:
        s['pending_intent'] = None
        if persistent(s):
            s['placement_plan'] = None
        if action == 'left':
            _shift(s, dx=-1)
        elif action == 'right':
            _shift(s, dx=1)
        elif action == 'rotate_cw':
            _rotate(s, 1)
        elif action == 'rotate_ccw':
            _rotate(s, -1)
        elif action == 'soft_drop':
            _shift(s, dy=1)
        elif action == 'hard_drop':
            while _shift(s, dy=1):
                pass
            # Record the landing before locking so the frontend/replay can draw
            # a real hard-drop transition instead of only the settled board.
            s['event'] = 'hard_drop'
            _trace(s)
            _lock(s)
    _trace(s)
    return s


def _intent_tick(g):
    intent = g.get('pending_intent')
    if not intent:
        return
    active = g['active']
    if intent['piece_id'] != active['piece_id']:
        g['pending_intent'] = None
        return
    if active['rotation'] != intent['rotation']:
        count = len(rotations(active['piece']))
        clockwise = (intent['rotation'] - active['rotation']) % count
        moved = _rotate(g, 1 if clockwise <= count / 2 else -1)
    elif active['x'] != intent['column']:
        moved = _shift(g, dx=1 if active['x'] < intent['column'] else -1)
    else:
        g['pending_intent'] = None
        g['event'] = 'intent_reached'
        if persistent(g) and g.get('placement_plan'):
            g['placement_plan'].update(status='holding',reason='target_reached_waiting_for_gravity')
        _trace(g)
        return
    g['event'] = 'intent_input' if moved else 'intent_blocked'
    if not moved:
        g['pending_intent'] = None
        if persistent(g) and g.get('placement_plan'):
            g['placement_plan'].update(status='blocked',reason='intent_blocked')
        if g.get('_projection_stop_after_piece'):
            g['_projection_intent_blocked'] = True
    _trace(g)


def _tick(g):
    g['simulation_ticks'] += 1
    if g['phase'] == 'clearing':
        g['clear_clock'] = round(g['clear_clock'] + TICK, 9)
        if g['clear_clock'] + 1e-9 >= CLEAR_DELAY:
            cleared = len(g['clearing_rows'])
            if g.get('_projection_stop_after_piece'):
                g['_projection_cleared_rows'] = list(g['clearing_rows'])
            g['board'] = [[0] * WIDTH for _ in range(cleared)] + [
                row for y, row in enumerate(g['board']) if y not in g['clearing_rows']]
            g['lines'] += cleared
            g['score'] += (0, 100, 300, 500, 800)[cleared]
            g['clearing_rows'] = []
            if g['lines'] >= LINE_TARGET:
                g['phase'] = 'complete'
                _finish(g, 'win', 'complete')
            elif g['steps'] >= PIECE_LIMIT:
                _finish(g, 'loss', 'piece_limit')
            elif g.get('_projection_stop_after_piece'):
                g.update(phase='projection_complete', _projection_complete=True)
            else:
                _spawn(g)
        return
    g['input_clock'] = round(g['input_clock'] + TICK, 9)
    if g['input_clock'] + 1e-9 >= INPUT_INTERVAL:
        g['input_clock'] = round(g['input_clock'] - INPUT_INTERVAL, 9)
        _intent_tick(g)
    g['gravity_clock'] = round(g['gravity_clock'] + TICK, 9)
    if g['gravity_clock'] + 1e-9 >= gravity_interval(g):
        g['gravity_clock'] = round(g['gravity_clock'] - gravity_interval(g), 9)
        if _shift(g, dy=1):
            g['event'] = 'falling'
            _trace(g)
    grounded = not _fits(g, _moved(g['active'], dy=1))
    phase = 'locking' if grounded else 'falling'
    if g['phase'] != phase:
        g.update(phase=phase, event=phase)
        _trace(g)
    if grounded:
        # Cumulative ground contact, never reset by rotate/shift/repeated intent.
        # A piece may leave a ledge, but it cannot get an unlimited fresh delay.
        g['lock_clock'] = round(g['lock_clock'] + TICK, 9)
        plan = g.get('placement_plan') if persistent(g) else None
        if plan and plan['status'] == 'executing':
            count = len(rotations(g['piece']))
            turns = (plan['rotation'] - g['active']['rotation']) % count
            turns = min(turns, count-turns)
            # Each rotation can wall-kick at most one column. This is a
            # conservative LOWER bound on remaining inputs, never a planner.
            inputs = turns + max(0, abs(plan['column']-g['active']['x'])-turns)
            minimum = max(0., inputs*INPUT_INTERVAL-g['input_clock'])
            if inputs and minimum > LOCK_DELAY-g['lock_clock']+1e-9:
                plan.update(status='danger',reason='contact_window_shorter_than_minimum_inputs')
                g['event'] = 'intent_deadline_risk'
        if g['lock_clock'] + 1e-9 >= LOCK_DELAY:
            _lock(g)


def _advance_in_place(s, seconds):
    """One physics implementation for live catch-up and public projections."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('elapsed seconds must be finite and nonnegative')
    if not s['started'] or s['outcome']:
        return s
    remaining = min(float(seconds), max(0., TIME_LIMIT - s['elapsed']))
    while remaining > 1e-9 and not s['outcome'] and not s.get('_projection_complete'):
        amount = min(remaining, TICK - s['simulation_clock'])
        s['elapsed'] = round(s['elapsed'] + amount, 9)
        s['simulation_clock'] = round(s['simulation_clock'] + amount, 9)
        remaining = round(remaining - amount, 9)
        if s['simulation_clock'] + 1e-9 >= TICK:
            s['simulation_clock'] = 0.
            _tick(s)
    if s['elapsed'] + 1e-8 >= TIME_LIMIT and not s['outcome']:
        _finish(s, 'loss', 'time_limit')
    _trace(s)
    return s


def advance_idle(g, seconds):
    return _advance_in_place(copy.deepcopy(g), seconds)


def public(g, include_trace=False):
    state = {key: copy.deepcopy(value) for key, value in g.items()
             if not key.startswith('_') and (include_trace or key != 'execution_trace')}
    state.update({key: value for key, value in _frame(g).items() if key in (
        'active', 'ghost_cells', 'gravity_interval', 'lock_delay', 'clear_delay')})
    state['seconds_to_next_fall'] = round(max(0., gravity_interval(g) - g['gravity_clock']), 3)
    state['seconds_to_lock'] = round(max(0., LOCK_DELAY - g['lock_clock']), 3)
    return state


def as_record(g):
    from jev_showcase_common import record
    state = public(g)
    grid = [['#' if cell else '.' for cell in row] for row in g['board']]
    for x, y in cells(g.get('active')):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            grid[y][x] = '@'
    state.update(rules=RULES, grid=[''.join(row) for row in grid])
    state['timing'] = {'mode': 'realtime_wall_clock', 'continues_during_inference': True,
                       'seconds_to_next_fall': state['seconds_to_next_fall'],
                       'seconds_to_lock': state['seconds_to_lock'],
                       'gravity_interval': gravity_interval(g), 'automatic_actions': 0,
                       'placement_input_interval': INPUT_INTERVAL}
    options, prompt = placement_choices(g), PROMPT
    if g.get('engine_revision') in (REVISION,LEGACY_PERSISTENT_REVISION,VISIBLE_REVISION) and options:
        from jev_tetris_projection import choice_descriptions, PREDICTION_NOTE, LEGACY_NOTE, control_window
        options = choice_descriptions(state)
        prompt += PREDICTION_NOTE if g.get('engine_revision') == REVISION else LEGACY_NOTE
        if g.get('engine_revision') == REVISION:
            state['timing']['control_window'] = control_window(state)
    if persistent(g):
        prompt += ('选定本块落点后，意图持续执行至锁块；到达目标后保持列和旋转等待原重力。'
                   '只有新块、真实受阻或接触锁定窗口不足才重新请求决策。placement_plan记录当前目标、A策略/B执行和本块期限。')
    result = record(KIND, state, prompt, options, '', g['decisions'])
    result['labels'] = {}
    result['provenance']['source_revision'] = g['engine_revision']
    if g.get('engine_revision') in (REVISION,LEGACY_PERSISTENT_REVISION,VISIBLE_REVISION):
        from jev_tetris_projection import REVISION as CANDIDATE_REVISION
        result['provenance']['candidate_revision'] = CANDIDATE_REVISION if g.get('engine_revision') == REVISION else 'tetris-visible-intent-consequences-v1'
    result['metadata']['difficulty'] = 'L2'
    from jev_game_prompt_calibration import apply as calibrate_prompt
    return calibrate_prompt(result)
