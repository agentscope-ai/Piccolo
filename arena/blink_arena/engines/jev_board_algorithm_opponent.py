"""Deterministic, observation-safe algorithm opponent for the seven Jev boards.

The existing Jev board engine remains the sole authority for legality and wins.
This module only ranks the *same candidate actions* shown to the Qwen opponent.
"""
from __future__ import annotations

from collections import deque
import math
import random

import jev_demo_games as board


def _connection_cost(game, side):
    n = game['n']; cells = game['board']
    if game['game'] != 'hex_7x7':
        return 0.0
    other = 'O' if side == 'X' else 'X'
    starts = [(r, 0) for r in range(n)] if side == 'X' else [(0, c) for c in range(n)]
    distance = [[math.inf] * n for _ in range(n)]
    queue = deque()
    for r, c in starts:
        if cells[r][c] == other:
            continue
        cost = 0 if cells[r][c] == side else 1
        distance[r][c] = cost
        (queue.appendleft if cost == 0 else queue.append)((r, c))
    while queue:
        r, c = queue.popleft(); here = distance[r][c]
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, -1), (-1, 1)):
            rr, cc = r + dr, c + dc
            if not (0 <= rr < n and 0 <= cc < n) or cells[rr][cc] == other:
                continue
            cost = 0 if cells[rr][cc] == side else 1
            if here + cost < distance[rr][cc]:
                distance[rr][cc] = here + cost
                (queue.appendleft if cost == 0 else queue.append)((rr, cc))
    result = min((distance[r][n-1] for r in range(n)), default=math.inf) if side == 'X' else min(distance[n-1])
    return result if math.isfinite(result) else n + 2


def _line_value(game, side):
    kind = game['game']; n = game['n']; grid = game['board']
    if kind not in ('tic_tac_toe', 'connect_four', 'gomoku_19x19'):
        return 0.0
    needed = 3 if kind == 'tic_tac_toe' else 4 if kind == 'connect_four' else 5
    other = 'O' if side == 'X' else 'X'
    total = 0.0
    for row in range(len(grid)):
        for col in range(n):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = row + (needed-1)*dr, col + (needed-1)*dc
                if not (0 <= end_r < len(grid) and 0 <= end_c < n):
                    continue
                cells = [grid[row+i*dr][col+i*dc] for i in range(needed)]
                own, foe = cells.count(side), cells.count(other)
                if own and foe:
                    continue
                if own:
                    total += (4.0 ** own) / needed
                elif foe:
                    total -= (4.5 ** foe) / needed
    return total


def _score(game, side):
    winner = game.get('winner')
    if winner == side:
        return 1_000_000.0
    if winner == ('O' if side == 'X' else 'X'):
        return -1_000_000.0
    kind = game['game']
    if kind == 'hex_7x7':
        other = 'O' if side == 'X' else 'X'
        return 12.0 * (_connection_cost(game, other) - _connection_cost(game, side))
    if kind == 'dots_and_boxes_3x3':
        own = sum(v == side for v in game['boxes'].values())
        foe = sum(v not in (side, '?') for v in game['boxes'].values())
        gifted = 0
        for r in range(1, 4):
            for c in range(1, 4):
                if f'{r},{c}' not in game['boxes'] and sum(e in game['edges'] for e in board.box_edges(r, c)) == 3:
                    gifted += 1
        return 20.0 * (own - foe) - (9.0 if game['turn'] != side else -9.0) * gifted
    if kind.startswith('othello'):
        own = sum(row.count(side) for row in game['board'])
        other = 'O' if side == 'X' else 'X'
        foe = sum(row.count(other) for row in game['board'])
        corners = ((0, 0), (0, game['n']-1), (game['n']-1, 0), (game['n']-1, game['n']-1))
        corner = sum(1 if game['board'][r][c] == side else -1 if game['board'][r][c] == other else 0 for r, c in corners)
        return own - foe + 15.0 * corner
    return _line_value(game, side)


def choose(game, candidates, seed, turn):
    """Choose a legal action using one-ply ranking and a bounded reply check."""
    options = list(candidates)
    legal = set(board.legal(game))
    if not options or any(action not in legal for action in options):
        raise ValueError('Board opponent received missing or illegal candidates')
    side = game['turn']
    rng = random.Random(f'jev-board-algorithm-v1/{game["game"]}/{seed}/{turn}')
    scored = []
    for action in options:
        after = board.move(game, action)
        score = _score(after, side)
        if game['game'] == 'connect_four' and action.startswith('C'):
            score += 0.25 * (3 - abs(int(action[1:]) - 4))
        if game['game'] == 'gomoku_19x19':
            r, c = board.coord(game, action)
            score += 0.003 * (18 - abs(r - 9) - abs(c - 9))
        scored.append((score, rng.random(), action, after))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    # Small tactical check: never miss an immediate win and avoid a direct
    # opponent win when the same public candidate set offers an alternative.
    if scored[0][0] >= 1_000_000:
        return scored[0][2]
    if game['game'] in ('tic_tac_toe', 'connect_four', 'othello_6x6', 'othello_8x8', 'dots_and_boxes_3x3'):
        checked = []
        for score, tie, action, after in scored[:min(16, len(scored))]:
            replies = board.legal(after)
            reply_wins = 0
            if after['turn'] != side:
                for reply in replies:
                    if board.move(after, reply)['winner'] == after['turn']:
                        reply_wins += 1
            checked.append((score - 100_000.0 * reply_wins, tie, action))
        checked.sort(key=lambda item: (-item[0], item[1], item[2]))
        return checked[0][2]
    return scored[0][2]
