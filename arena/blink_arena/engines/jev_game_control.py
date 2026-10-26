"""Visible geometry and deterministic execution of model-selected intents."""
from collections import deque
import copy

REVISION = 'visible-intent-executor-v2'
GOALS = {'tetris_placement': '40块内消4行并避免堵顶',
         'sokoban_puzzle': '80个实际移动内把所有箱子推到目标',
         'mario_platformer': '活着抵达右侧旗杆',
         'terramai_directional': '采矿和战斗成长，玩家参与击败指定守门Boss，再活着进入右侧地表胜利门'}


def tetris_facts(g, action):
    from jev_showcase_games import landing, metrics, rotations, SHAPES
    board, cleared, cells = landing(g, action)
    h, w = len(board), len(board[0])
    heights = [h-next((y for y in range(h) if board[y][x]), h) for x in range(w)]
    def hole_cells(b):
        result = set()
        for x in range(len(b[0])):
            covered = False
            for y in range(len(b)):
                covered = covered or bool(b[y][x])
                if covered and not b[y][x]:
                    result.add((x, y))
        return result
    old_cells = hole_cells(g['board'])
    raw = copy.deepcopy(g['board'])
    for x, y in cells:
        raw[y][x] = 1
    cleared_rows = {y for y, row in enumerate(raw) if all(row)}
    # A surviving cell moves down once for each cleared row beneath it.
    # Compare cell identities through that movement: net counts alone hide a
    # placement that fills one old hole while creating a different one.
    mapped_old = {p: (p[0], p[1] + sum(y > p[1] for y in cleared_rows))
                  for p in old_cells if p[1] not in cleared_rows}
    post_cells = hole_cells(board)
    removed = old_cells - {p for p, mapped in mapped_old.items() if mapped in post_cells}
    added = post_cells - set(mapped_old.values())
    old_holes = len(old_cells)
    holes, aggregate, bump = metrics(board)
    wells = [max(0, min(heights[x-1] if x else h,
                       heights[x+1] if x+1 < w else h)-heights[x]) for x in range(w)]
    # Hypothetical shapes quantify geometric room, never a future random draw.
    slots = {}
    for name in SHAPES:
        slots[name] = sum(all(0 <= col+x < w and y < h and
                              all(not board[entry_y][col+x] for entry_y in range(y+1))
                              for x,y in shape)
                          for shape in rotations(name) for col in range(w-max(x for x,y in shape)))
    return {'certainty': 'deterministic_visible_board', 'lines_cleared': cleared,
            'holes': holes, 'holes_added': len(added), 'holes_removed': len(removed),
            'new_hole_cells_after_clear': [list(p) for p in sorted(added)],
            'resolved_hole_cells_before_clear': [list(p) for p in sorted(removed)],
            'cleared_row_indices_before_clear': sorted(cleared_rows),
            'holes_net_added': max(0, holes-old_holes),
            'holes_net_removed': max(0, old_holes-holes), 'max_height': max(heights),
            'column_heights': heights, 'aggregate_height': aggregate,
            'surface_bumpiness': bump, 'deepest_well': max(wells),
            'top_free_cells': sum(not v for row in board[:4] for v in row),
            'hypothetical_spawn_slots': slots, 'landing_cells': [list(p) for p in cells],
            'future_piece': 'unknown; shape counts are geometric possibilities'}


def tetris_description(g, action):
    f = tetris_facts(g, action)
    return (f'旋转:列={action}；消{f["lines_cleared"]}行；落后空洞{f["holes"]}'
            f'（新增{f["holes_added"]}/解除{f["holes_removed"]}，消行后按格追踪）；'
            f'最高列{f["max_height"]}，表面起伏{f["surface_bumpiness"]}，'
            f'最深井{f["deepest_well"]}，顶部4行空格{f["top_free_cells"]}；'
            f'各假设形状仍可从顶部进入的列数{f["hypothetical_spawn_slots"]}。确定性；下一块未知。')


def walking_paths(g):
    from jev_showcase_games import DIRS
    blocked = {tuple(p) for p in g['walls']+g['boxes']}
    start = tuple(g['player'])
    paths = {start: []}
    queue = deque([start])
    while queue:
        x,y = queue.popleft()
        for action,(dx,dy) in DIRS.items():
            p = x+dx,y+dy
            if 0 <= p[0] < g['width'] and 0 <= p[1] < g['height'] and p not in blocked and p not in paths:
                paths[p] = paths[(x,y)]+[action]
                queue.append(p)
    return paths


def sokoban_condition(seed):
    """Generate solvable layouts by reverse moves, outside the policy interface.

    No solution plan is exposed or executed. The same two-box goal and 80
    physical-move budget apply to all layouts.
    """
    import random
    rng=random.Random(f'sokoban-layout-v2/{seed}')
    boundary=[[x,y] for y in range(8) for x in range(8) if x in (0,7) or y in (0,7)]
    for attempt in range(80):
        inner=rng.sample([[x,y] for y in range(2,6) for x in range(2,6)],rng.randint(2,4))
        free=[[x,y] for y in range(1,7) for x in range(1,7) if [x,y] not in inner]
        goals=rng.sample([p for p in free if 1<p[0]<6 and 1<p[1]<6],2)
        g={'width':8,'height':8,'walls':boundary+inner,'boxes':copy.deepcopy(goals),
           'targets':goals,'player':rng.choice([p for p in free if p not in goals])}
        visited_boxes={tuple(sorted(map(tuple,g['boxes'])))}
        reverse_cost=0
        for _ in range(rng.randint(10,16)):
            paths=walking_paths(g);walls={tuple(p) for p in g['walls']};boxes={tuple(p) for p in g['boxes']}
            candidates=[]
            for box in boxes:
                for dx,dy in ((0,-1),(1,0),(0,1),(-1,0)):
                    stand=(box[0]-dx,box[1]-dy);back=(box[0]-2*dx,box[1]-2*dy)
                    if stand in paths and back not in walls|boxes and 0<back[0]<7 and 0<back[1]<7:
                        configuration=tuple(sorted((boxes-{box})|{stand}))
                        cost=len(paths[stand])+1
                        if configuration not in visited_boxes and reverse_cost+cost<=60:
                            candidates.append((box,stand,back,cost))
            if not candidates:break
            box,stand,back,cost=rng.choice(candidates)
            g['boxes']=[list(p) for p in sorted((boxes-{box})|{stand})];g['player']=list(back)
            visited_boxes.add(tuple(sorted(map(tuple,g['boxes']))));reverse_cost+=cost
        distance=min(sum(abs(b[0]-q[0])+abs(b[1]-q[1]) for b,q in zip(g['boxes'],order))
                     for order in (goals,list(reversed(goals))))
        distinct_pushes = {tuple(v['box']) + (v['direction'],) for v in push_intents(g).values()}
        if not (set(map(tuple,g['boxes']))&set(map(tuple,goals))) and distance>=4 and reverse_cost>=16 and len(distinct_pushes)>=2:
            g['recent_positions']=[copy.deepcopy(g['player'])]
            return g
    raise ValueError('could not generate an independent solvable layout')


def push_intents(g):
    from jev_showcase_games import DIRS
    paths = walking_paths(g)
    boxes = {tuple(p) for p in g['boxes']}
    walls = {tuple(p) for p in g['walls']}
    goals = {tuple(p) for p in g['targets']}
    intents = {}
    for x,y in sorted(boxes):
        for direction,(dx,dy) in DIRS.items():
            stand, target = (x-dx,y-dy),(x+dx,y+dy)
            if stand not in paths or target in boxes|walls or not (0 <= target[0] < g['width'] and 0 <= target[1] < g['height']):
                continue
            corner = target not in goals and any((target[0]+a,target[1]) in walls and
                       (target[0],target[1]+b) in walls for a in (-1,1) for b in (-1,1))
            remaining_moves = max(0, 80-g.get('steps', 0))
            required_moves = len(paths[stand])+1
            goal_change = int(target in goals)-int((x,y) in goals)
            for goal in sorted(goals):
                action = f'push:{x}:{y}:{direction}:{goal[0]}:{goal[1]}'
                box_id=g.get('box_ids',{}).get(f'{x},{y}',f'box@{x},{y}')
                intents[action] = {'box': [x,y], 'box_id':box_id,'goal':list(goal), 'direction': direction, 'stand': list(stand),
                'target': list(target), 'walk': paths[stand], 'execution_moves': len(paths[stand])+1,
                'on_goal_after': target in goals, 'static_corner_deadlock': corner,
                'leaves_goal': (x,y) in goals and target not in goals,
                'boxes_on_goals_change': goal_change,
                'remaining_physical_moves': remaining_moves,
                'completes_within_budget': required_moves <= remaining_moves,
                'goal_occupied_by_other_box':goal in boxes and goal!=(x,y),
                'goal_distance_after':abs(target[0]-goal[0])+abs(target[1]-goal[1]),
                'certainty': 'deterministic_visible_map',
                'description': f'{box_id}在[{x},{y}]；选定最终目标{list(goal)}，本次向{direction}推到{list(target)}；先走{len(paths[stand])}步到站位{list(stand)}；'
                    f'推后在任一目标={target in goals}，目标上箱数变化{goal_change:+d}，非目标墙角死锁={corner}；'
                    f'所选目标被其他箱占据={goal in boxes and goal!=(x,y)}，推后到所选目标曼哈顿距离{abs(target[0]-goal[0])+abs(target[1]-goal[1])}（不保证可达）；'
                    f'执行需{required_moves}步/剩余{remaining_moves}步，预算内可完成={required_moves<=remaining_moves}；箱子后续路线由你规划'}
    return intents


def sokoban_motion_frame(g):
    """A receipt of a completed physical move, for frontend playback only."""
    return {'player': list(g['player']), 'boxes': copy.deepcopy(g['boxes']),
            'steps': g['steps'],
            'score': len(set(map(tuple, g['boxes'])) & set(map(tuple, g['targets'])))}


def execute_push(g, action):
    from jev_showcase_games import sokoban_move
    selected = push_intents(g).get(action)
    if selected is None:
        raise ValueError('selected box/stand intent is blocked or expired')
    s = copy.deepcopy(g)
    moves = 0
    frames = [sokoban_motion_frame(g)]
    interruption = None
    for micro in selected['walk']+[selected['direction']]:
        if s['steps'] >= 80:
            interruption = 'budget_exhausted'
            break
        result = sokoban_move(s, micro)
        if result is None:
            interruption = 'blocked'
            break
        player, boxes = result
        removed=set(map(tuple,s['boxes']))-set(boxes)
        added=set(boxes)-set(map(tuple,s['boxes']))
        if removed and added:
            source=next(iter(removed));dest=next(iter(added))
            mapping=s.setdefault('box_ids',{})
            mapping[f'{dest[0]},{dest[1]}']=mapping.pop(f'{source[0]},{source[1]}',selected['box_id'])
        s.update(player=list(player), boxes=[list(p) for p in boxes], steps=s['steps']+1)
        moves += 1
        frames.append({**sokoban_motion_frame(s), 'action': micro})
    # One selected intent remains one policy decision. These are execution
    # receipts, not additional choices, labels or policy-gradient samples.
    s['execution_trace'] = {'version': 1, 'frames': frames}
    s['execution'] = {'origin': 'B', 'strategy_origin': 'A', 'intent': action,
                      'subgoal': {k: selected[k] for k in ('box','box_id','goal','stand','target')},
                      'mechanical_moves': moves, 'deadline_moves': selected['execution_moves'],
                      'status': 'completed' if interruption is None else 'blocked' if interruption == 'blocked' else 'expired',
                      'event': interruption or 'push_complete',
                      'fallback_actions': 0}
    return s


def control_view(state, family):
    obs = state.get('observation', state)
    stored = state.get('control') or obs.get('control') or {}
    result = {'revision': REVISION, 'goal': GOALS.get(family, state.get('rules', '')[:180]),
            'subgoal': stored.get('subgoal'), 'status': stored.get('status', 'awaiting_decision'),
            'recent_effects': stored.get('recent_effects', []),
            'no_progress_count': stored.get('no_progress_count', 0),
            'repeated_action_count': stored.get('repeated_action_count', 0),
            'events': stored.get('events', []), 'execution_origin': 'B',
            'strategy_origin': 'A', 'fallback_actions': stored.get('fallback_actions', 0),
            'deadline': obs.get('timing', {}).get('action_frames', 1),
            'deadline_unit': 'physics_frames' if 'timing' in obs else 'selected_action',
            'abort_on': ['blocked', 'landed', 'danger_changed', 'expired', 'terminal']}
    execution = obs.get('action_execution') or {}
    if family == 'mario_platformer' and execution.get('revision') == 'selected-visible-landing-v6-explicit-guard':
        guard = execution.get('landing_guard') or {}
        guarding = guard.get('status') == 'active'
        result.update(revision='visible-intent-executor-v3-guard-aware',
            subgoal=execution.get('selected_intent'),
            status='defending_while_awaiting_model' if guarding else execution.get('status', 'idle'),
            recent_effects=copy.deepcopy(execution.get('recent_effects', [])),
            no_progress_count=execution.get('no_progress_count', 0),
            events=[guard['last_event']] if guarding and guard.get('last_event') else [],
            deadline=max(0, guard['deadline_frame']-obs['frame']) if guarding else execution.get('remaining_frames', 0),
            deadline_unit='physics_frames',
            selected_landing_guard=copy.deepcopy(guard) if guard else None,
            fallback_actions=execution.get('rule_takeover_count', 0))
    return result


def remember_effect(before, after, action, before_record, after_record):
    # Compare only public observations; never store private engine dictionaries.
    def observable(r):
        transient={'control','steps','decisions','frame','tick','last_actions','recent_positions',
                   'recent_player_positions','recent_player_tiles','execution','timing'}
        def strip(value):
            if isinstance(value,dict):return {k:strip(v) for k,v in value.items() if k not in transient}
            if isinstance(value,list):return [strip(v) for v in value]
            return value
        return strip(r['state'])
    a,b = observable(before_record),observable(after_record)
    changed = a != b
    previous = before.get('control', {})
    effects = previous.get('recent_effects', [])
    outcome = after.get('outcome')
    terminal_reason = None
    if outcome:
        terminal_reason = 'terminal_' + outcome
        if outcome == 'loss' and after.get('kind') == 'tetris_placement':
            from jev_showcase_games import choices
            terminal_reason = 'top_out' if not choices({**after, 'outcome': None}) else 'budget_exhausted'
        elif outcome == 'loss' and after.get('kind') == 'sokoban_puzzle':
            terminal_reason = 'budget_exhausted' if after['steps'] >= 80 else 'deadlock'
    entry = {'action': action, 'changed_visible_state': changed,
             'event': terminal_reason or after.get('execution', {}).get('event') or ('state_changed' if changed else 'no_progress'),
             'failure_reason': terminal_reason if outcome == 'loss' else None if changed else 'no_visible_effect',
             'mechanical_moves': after.get('execution', {}).get('mechanical_moves', 1)}
    status = after.get('execution', {}).get('status', 'completed')
    if outcome == 'loss':
        status = 'expired' if terminal_reason == 'budget_exhausted' else 'failed'
    after['control'] = {'subgoal': after.get('execution', {}).get('subgoal', action),
        'status': status,
        'recent_effects': (effects+[entry])[-6:], 'events': [entry['event']]+(['terminal'] if outcome else []),
        'no_progress_count': 0 if changed else previous.get('no_progress_count',0)+1,
        'repeated_action_count': previous.get('repeated_action_count',0)+1 if effects and effects[-1]['action']==action else 0,
        'fallback_actions': previous.get('fallback_actions',0)}
    return after
