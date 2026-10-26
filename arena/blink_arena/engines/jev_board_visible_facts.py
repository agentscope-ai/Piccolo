"""Exact short-horizon consequences computed solely from the public board."""
import copy


def _run(grid, row, col, side, dr, dc):
    total = 1
    ends = 0
    for sign in (-1, 1):
        rr, cc = row + sign * dr, col + sign * dc
        while 0 <= rr < len(grid) and 0 <= cc < len(grid[0]) and grid[rr][cc] == side:
            total += 1
            rr, cc = rr + sign * dr, cc + sign * dc
        ends += int(0 <= rr < len(grid) and 0 <= cc < len(grid[0]) and grid[rr][cc] == '.')
    return total, ends


def _line_win(grid, row, col, side, needed):
    return any(_run(grid, row, col, side, dr, dc)[0] >= needed
               for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)))


def _cells(grid, kind):
    if kind == 'connect_four':
        return [(next(r for r in range(len(grid)-1, -1, -1) if grid[r][c] == '.'), c)
                for c in range(len(grid[0])) if grid[0][c] == '.']
    return [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == '.']


def enrich(board, game, record, actions):
    kind, side, grid = game['game'], game['turn'], game['board']
    other = 'O' if side == 'X' else 'X'
    state = record['state']
    effects = {}
    if kind in ('tic_tac_toe', 'connect_four', 'gomoku_19x19'):
        needed = {'tic_tac_toe': 3, 'connect_four': 4, 'gomoku_19x19': 5}[kind]
        threats = [board.key(game, r, c) for r, c in _cells(grid, kind)
                   if _line_win(grid, r, c, other, needed)]
        state['opponent_immediate_winning_moves'] = threats
        for action in actions:
            r, c = board.coord(game, action)
            win = _line_win(grid, r, c, side, needed)
            after = [row[:] for row in grid]
            after[r][c] = side
            replies = [] if win else [board.key(game, rr, cc) for rr, cc in _cells(after, kind)
                if _line_win(after, rr, cc, other, needed)]
            effects[action] = {'source': 'exact_public_geometry', 'landing_row': r,
                'landing_col': c, 'wins_now': win,
                'opponent_immediate_winning_replies': replies,
                'max_own_contiguous_line_after': max(_run(after, r, c, side, dr, dc)[0]
                    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)))}
            record['questions']['decision']['criteria'][action] = (
                f'{action}：实际落点行{r}/列{c}(0起)，本步获胜={win}；'
                f'未终局时对方下一手可直接获胜的合法着数={len(replies)}；'
                f'本方相连最长={effects[action]["max_own_contiguous_line_after"]}')
    elif kind.startswith('othello'):
        before_own = sum(row.count(side) for row in grid)
        before_other = sum(row.count(other) for row in grid)
        corners = {(0, 0), (0, game['n']-1), (game['n']-1, 0), (game['n']-1, game['n']-1)}
        for action in actions:
            after = board.move(game, action)
            own = sum(row.count(side) for row in after['board'])
            enemy = sum(row.count(other) for row in after['board'])
            mobility = {}
            for actor in (side, other):
                view = copy.deepcopy(after)
                view['turn'] = actor
                mobility[actor] = len([a for a in board.legal(view) if a != 'pass'])
            effects[action] = {'source': 'exact_public_rules', 'own_disc_delta': own-before_own,
                'opponent_disc_delta': enemy-before_other, 'own_discs_after': own,
                'opponent_discs_after': enemy, 'own_legal_placements_if_turn': mobility[side],
                'opponent_legal_placements_if_turn': mobility[other],
                'occupies_corner': action != 'pass' and board.coord(game, action) in corners,
                'terminal_winner': after['winner']}
            record['questions']['decision']['criteria'][action] = (
                f'{action}：己方子数变化{own-before_own:+d}，对方{enemy-before_other:+d}；'
                f'落后双方子数{own}/{enemy}，双方若轮到各自可下位置数{mobility[side]}/{mobility[other]}；'
                f'占角={effects[action]["occupies_corner"]}，终局胜者={after["winner"]}')
    elif kind == 'hex_7x7':
        from jev_board_algorithm_opponent import _connection_cost
        for action in actions:
            after = board.move(game, action)
            own_cost, other_cost = _connection_cost(after, side), _connection_cost(after, other)
            replies = [] if after['winner'] else [reply for reply in board.legal(after)
                if board.move(after, reply)['winner'] == other]
            effects[action] = {'source': 'exact_public_geometry', 'wins_now': after['winner'] == side,
                'own_min_empty_cells_to_connection': own_cost,
                'opponent_min_empty_cells_to_connection': other_cost,
                'opponent_immediate_winning_replies': replies,
                'connection_cost_scope': 'current_board_lower_bound_ignores_future_contesting'}
            record['questions']['decision']['criteria'][action] = (
                f'{action}：本步连通获胜={effects[action]["wins_now"]}；'
                f'当前双方连接所需最少空格={own_cost}/{other_cost}（不保证未来可达）；'
                f'对方下一手直接获胜着数={len(replies)}')
    elif kind == 'dots_and_boxes_3x3':
        effects = copy.deepcopy(state['candidate_box_effects'])
        for action, fact in effects.items():
            fact['source'] = 'exact_public_edges'
            record['questions']['decision']['criteria'][action] = (
                f'{action}：本步完成{fact["boxes_completed"]}盒；'
                f'新造只差一边的盒数={fact["three_edge_boxes_created"]}；完成盒后继续行动')
    if effects:
        state['candidate_consequences'] = effects
        state['consequence_scope'] = ('公开局面下的确定规则/几何计算；下一手直接胜利计数不是整局胜率。'
            '不预测对手实际选择，不执行箱子/棋局求解方案；几何连接空格数不保证未来可达。')
        record['questions']['decision']['instructions'] += (
            ' option 已列当前公开局面的实际后果；先考虑本步获胜和避免对方立即获胜，再选择整局策略。')
    return record


# Qualified 50-game Othello 6x6 facts; all other families use v14.
_enrich_v14 = enrich


def _corner_anchor_edges(grid, actor):
    """Edge prefixes connected to owned corners cannot be bracketed."""
    n = len(grid)
    cells = set()
    for r, c, dr, dc in ((0,0,0,1),(0,0,1,0),(0,n-1,0,-1),(0,n-1,1,0),
                         (n-1,0,0,1),(n-1,0,-1,0),(n-1,n-1,0,-1),(n-1,n-1,-1,0)):
        while 0 <= r < n and 0 <= c < n and grid[r][c] == actor:
            cells.add((r,c))
            r,c = r+dr,c+dc
    return cells


def enrich(board, game, record, actions):
    record = _enrich_v14(board, game, record, actions)
    kind, side, grid = game['game'], game['turn'], game['board']
    other = 'O' if side == 'X' else 'X'
    facts = record['state'].get('candidate_consequences', {})
    if kind == 'othello_6x6':
        n = game['n']
        corners = {(0,0),(0,n-1),(n-1,0),(n-1,n-1)}
        for action in actions:
            after = board.move(game,action)
            empty_corners = {(r,c) for r,c in corners if after['board'][r][c] == '.'}
            actual_next_opponent_corners = []
            if not after['winner'] and after['turn'] == other:
                actual_next_opponent_corners = [a for a in board.legal(after)
                    if a != 'pass' and board.coord(after,a) in corners]
            x_cells = {(r + (1 if r == 0 else -1), c + (1 if c == 0 else -1))
                       for r,c in empty_corners}
            c_cells = {(r,c + (1 if c == 0 else -1)) for r,c in empty_corners} | {
                (r + (1 if r == 0 else -1),c) for r,c in empty_corners}
            near_x = sum(after['board'][r][c] == side for r,c in x_cells)
            near_c = sum(after['board'][r][c] == side for r,c in c_cells)
            anchored = [len(_corner_anchor_edges(after['board'], actor)) for actor in (side,other)]
            facts[action].update(opponent_actual_next_corner_moves=actual_next_opponent_corners,
                own_x_squares_next_to_empty_corners=near_x,
                own_c_squares_next_to_empty_corners=near_c,
                corner_anchored_stable_edge_discs=anchored,
                extra_consequence_scope='下一轮实际轮到对手时合法占角位置为确定规则事实；空角邻位计数仅几何风险，非整局胜率；连己方角的连续边线棋子是保证不被夹翻的边子子集。')
            record['questions']['decision']['criteria'][action] += (
                f'；对手下一轮可直接占角数={len(actual_next_opponent_corners)}，空角旁本方X/C格数={near_x}/{near_c}；'
                f'双方连角稳定边子数={anchored[0]}/{anchored[1]}（稳定子子集，非整局估值）')
        record['questions']['decision']['instructions'] += (
            ' 依据公开占角机会、空角邻位和稳定边子选择长期策略；早中盘翻子数量本身不代表终局优势，空角邻位计数也不是禁止落子规则。')
    if kind == 'othello_6x6':
        record['state']['visible_consequence_revision'] = 'candidate-public-strategy-facts-v15-prototype'
    return record
