"""Fixed-clock Snake. Decisions change heading; the clock moves the body.

The old turn-based snake remains in jev_showcase_games for archived episodes.
No route planner, pause while thinking, or automatic collision avoidance runs here.
"""
import copy
import math
import random
from collections import deque

KIND = 'snake_navigation'
REVISION = 'snake-realtime-v1-six-apples'
SEED_REVISION = 'snake-realtime-initial-v1'
GOAL = '实时前进，避开墙、石块和身体，吃到 6 个苹果'
N = 14
INITIAL_LENGTH = 5
OBSTACLES = 14
FOOD_TARGET = 6
TIME_LIMIT = 240.
MOVE_LIMIT = 220
LIMIT = 240
DIRS = {'up': (0, -1), 'right': (1, 0), 'down': (0, 1), 'left': (-1, 0)}
REVERSE = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
LABELS = {'up': '向上', 'right': '向右', 'down': '向下', 'left': '向左'}
RULES = ('实时贪吃蛇，坐标[x,y]原点左上、x向右、y向下。首个方向输入后开始，随后自动前进；'
         '推理、等待网络和没有输入时都沿当前方向继续走，不会暂停。每格间隔最初1.20秒，每吃一颗苹果缩短0.05秒，最低0.95秒。'
         '方向输入只设置下一次移动方向，不会立刻移动或重置移动时钟；不能反向。最多缓存一个方向，以最新合法输入为准。'
         '撞边界、石块或身体即失败。不进食时尾部同一步前移，可走入腾出的尾格；进食时增长一格，尾部不动。'
         '吃到6颗苹果获胜；240秒或220格内未完成失败。吃掉后在可达空格重新随机生成一颗苹果，未来位置不可见。'
         'grid中H=头、S=身体、F=苹果、#=石块、.=空格。seconds_to_next_move显示下一次移动的剩余时间；'
         '回复到达时蛇可能已向前多格，动作才开始生效。candidate_next_cells仅为当前快照下一格的几何，不是延迟后的保证。')
PROMPT = ('目标是实时安全吃到6颗苹果。先核对当前头、朝向、移动倒计时、身体与障碍；'
          '推理期间仍前进，提前转弯，优先保留可继续前进的宽阔通道。'
          '不要仅看苹果方向而撞上墙或身体；考虑蛇尾移动和吃完后能否脱身。按当前回答格式返回所选方向对应的选项标签。')


def interval(g):
    return round(max(.95, 1.20 - .05 * g['score']), 2)


def is_realtime(g):
    return g.get('kind') == KIND and g.get('engine_revision') == REVISION


def _reachable(start, blocked, n=N):
    queue = deque([tuple(start)])
    distances = {tuple(start): 0}
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRS.values():
            p = x + dx, y + dy
            if 0 <= p[0] < n and 0 <= p[1] < n and p not in blocked and p not in distances:
                distances[p] = distances[(x, y)] + 1
                queue.append(p)
    return distances


def fresh(seed=0):
    from jev_environment_seeds import validate_seed
    validate_seed(seed)
    rng = random.Random(f'{SEED_REVISION}/{seed}')
    cells = [(x, y) for y in range(N) for x in range(N)]
    for _ in range(256):
        direction = rng.choice(list(DIRS))
        dx, dy = DIRS[direction]
        starts = [(x, y) for x, y in cells if 2 <= x < N - 2 and 2 <= y < N - 2
                  and 0 <= x - (INITIAL_LENGTH - 1) * dx < N
                  and 0 <= y - (INITIAL_LENGTH - 1) * dy < N
                  and 0 <= x + 4 * dx < N and 0 <= y + 4 * dy < N]
        x, y = rng.choice(starts)
        body = [(x - i * dx, y - i * dy) for i in range(INITIAL_LENGTH)]
        protected = set(body) | {(x + k * dx, y + k * dy) for k in range(1, 5)}
        protected |= {(x + ax, y + ay) for ax, ay in DIRS.values()}
        obstacles = set(rng.sample([p for p in cells if p not in protected], OBSTACLES))
        if len(_reachable((x, y), obstacles)) != N * N - OBSTACLES:
            continue
        reachable = _reachable((x, y), obstacles | set(body[1:]))
        food_cells = [p for p, distance in reachable.items() if distance >= 5]
        if not food_cells:
            continue
        g = {'kind': KIND, 'engine_revision': REVISION, '_seed': seed,
             'n': N, 'body': [list(p) for p in body], 'direction': direction,
             'pending_direction': direction, 'food': list(rng.choice(food_cells)),
             'obstacles': [list(p) for p in sorted(obstacles)], 'steps': 0,
             'decisions': 0, 'max_model_decisions': LIMIT, 'score': 0, 'food_target': FOOD_TARGET, 'target_food': FOOD_TARGET, 'outcome': None,
             'started': False, 'elapsed': 0., 'move_clock': 0.,
             'move_interval': 1.2, 'time_limit': TIME_LIMIT, 'max_steps': MOVE_LIMIT,
             'event': 'ready', 'failure_reason': None}
        g['execution_trace'] = {'version': 1, 'frames': [_frame(g)]}
        return g
    raise ValueError('无法生成可达的实时贪吃蛇开局')


def choices(g):
    if g.get('outcome'):
        return {}
    return {action: LABELS[action] for action in DIRS if action != REVERSE[g['direction']]}


def next_cell(g, action):
    dx, dy = DIRS[action]
    head = [g['body'][0][0] + dx, g['body'][0][1] + dy]
    eating = head == g['food']
    body = [head] + g['body'][:len(g['body']) if eating else -1]
    collision = (not (0 <= head[0] < g['n'] and 0 <= head[1] < g['n'])
                 or head in body[1:] or head in g['obstacles'])
    return head, body, eating, collision


def _frame(g):
    return {key: copy.deepcopy(g[key]) for key in (
        'body', 'direction', 'pending_direction', 'food', 'score', 'steps',
        'elapsed', 'move_clock', 'move_interval', 'started', 'outcome', 'event')}


def _trace(g):
    frames = g.setdefault('execution_trace', {'version': 1, 'frames': []})['frames']
    frames.append(_frame(g))
    del frames[:-32]


def step(g, action, controller='model'):
    if action not in choices(g):
        raise ValueError('非法方向或本局已结束')
    s = copy.deepcopy(g)
    s.update(pending_direction=action, started=True, decisions=g['decisions'] + 1,
             event='steering', controller=controller)
    return s


def _move(g):
    action = g['pending_direction']
    if action == REVERSE[g['direction']]:
        action = g['direction']
    head, body, eating, collision = next_cell(g, action)
    g.update(direction=action, pending_direction=action, steps=g['steps'] + 1)
    if collision:
        # Keep the visible head on the last valid cell; mark the contact cell.
        g.update(outcome='loss', event='collision', collision_cell=head, failure_reason='collision')
    else:
        g['body'] = body
        g['event'] = 'moving'
        if eating:
            g['score'] += 1
            g['event'] = 'apple'
            if g['score'] >= FOOD_TARGET:
                g.update(outcome='win', event='complete')
            else:
                reachable = _reachable(head, set(map(tuple, g['obstacles'] + body[1:])), g['n'])
                free = sorted(p for p in reachable if list(p) not in body)
                if not free:
                    # A trapped snake still needs to escape; never award a win
                    # before six apples merely because its body encloses space.
                    free = [(x, y) for y in range(g['n']) for x in range(g['n'])
                            if [x, y] not in body + g['obstacles']]
                if free:
                    rng = random.Random(f'{SEED_REVISION}/{g["_seed"]}/apple/{g["score"]}')
                    g['food'] = list(rng.choice(free))
        if g['steps'] >= MOVE_LIMIT and not g['outcome']:
            g.update(outcome='loss', event='move_limit', failure_reason='move_limit')
    g['move_interval'] = interval(g)
    _trace(g)


def advance_idle(g, seconds):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('elapsed seconds must be finite and nonnegative')
    s = copy.deepcopy(g)
    if not s['started'] or s['outcome']:
        return s
    remaining = min(float(seconds), TIME_LIMIT - s['elapsed'])
    while remaining > 1e-10 and not s['outcome']:
        gap = max(0., interval(s) - s['move_clock'])
        amount = min(remaining, gap)
        s['elapsed'] = round(s['elapsed'] + amount, 9)
        s['move_clock'] = round(s['move_clock'] + amount, 9)
        remaining -= amount
        if s['move_clock'] + 1e-8 >= interval(s):
            s['move_clock'] = 0.
            _move(s)
    if s['elapsed'] + 1e-8 >= TIME_LIMIT and not s['outcome']:
        s.update(outcome='loss', event='time_limit', failure_reason='time_limit')
        _trace(s)
    return s


def public(g, include_trace=False):
    s = {key: copy.deepcopy(value) for key, value in g.items()
         if not key.startswith('_') and (include_trace or key != 'execution_trace')}
    s['seconds_to_next_move'] = round(max(0., interval(g) - g['move_clock']), 3)
    return s


def as_record(g):
    from jev_showcase_common import record
    state = public(g)
    grid = [['.'] * g['n'] for _ in range(g['n'])]
    for x, y in g['obstacles']:
        grid[y][x] = '#'
    for x, y in g['body'][1:]:
        grid[y][x] = 'S'
    fx, fy = g['food']
    grid[fy][fx] = 'F'
    hx, hy = g['body'][0]
    grid[hy][hx] = 'H'
    state.update(rules=RULES, grid=[''.join(row) for row in grid], foods_eaten=g['score'])
    state['candidate_next_cells'] = {
        a: {'head': head, 'collision': collision, 'eats_food': eating}
        for a in choices(g) for head, body, eating, collision in [next_cell(g, a)]}
    state['timing'] = {'mode': 'realtime_wall_clock', 'continues_during_inference': True,
                       'seconds_to_next_move': state['seconds_to_next_move'],
                       'move_interval': interval(g), 'automatic_actions': 0}
    r = record(KIND, state, PROMPT, choices(g), '', g['decisions'])
    r['labels'] = {}
    r['provenance']['source_revision'] = REVISION
    r['metadata']['difficulty'] = 'L2'
    from jev_game_prompt_calibration import apply as calibrate_prompt
    return calibrate_prompt(r)
