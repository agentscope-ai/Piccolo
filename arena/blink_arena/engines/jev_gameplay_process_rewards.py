"""Auditable, bounded process rewards from actual Mario/Terramai engine states.

These are training rewards, never observations or reference actions. A running
maximum prevents left-right motion and respawns from repeatedly earning progress.
"""
from __future__ import annotations

import math

REVISION = 'pixel-engine-process-reward-v1'
DISCOUNT = 0.997


def _number(value):
    number = float(value or 0)
    if not math.isfinite(number):
        raise ValueError('nonfinite game counter')
    return number


def process_rewards(kind, initial, transitions):
    if kind not in ('mario_platformer', 'terraria_survival'):
        return [0.0] * len(transitions)
    result = []
    if kind == 'mario_platformer':
        start_progress = _number(initial.get('progress'))
        peak = start_progress
        start_coins = _number(initial.get('collected'))
        start_powerups = _number(initial.get('powerups_collected'))
        paid_coins = paid_powerups = 0.0
        for transition in transitions:
            after = transition['after_state']
            next_peak = max(peak, min(100.0, _number(after.get('progress'))))
            progress = 0.30 * (next_peak - peak) / max(1.0, 100.0 - start_progress)
            peak = next_peak
            coin_total = min(6.0, max(0.0, _number(after.get('collected')) - start_coins))
            coins = 0.025 * max(0.0, coin_total - paid_coins)
            paid_coins = max(paid_coins, coin_total)
            powerup_total = min(2.0, max(0.0, _number(after.get('powerups_collected')) - start_powerups))
            powerups = 0.03 * max(0.0, powerup_total - paid_powerups)
            paid_powerups = max(paid_powerups, powerup_total)
            result.append(round(progress + coins + powerups, 9))
    else:
        start_x = _number(initial.get('player', {}).get('x'))
        peak = start_x
        start_ore = _number(initial.get('stats', {}).get('ore'))
        start_gear = sum(_number(initial.get('equipment', {}).get(k)) for k in ('pick', 'sword', 'armor'))
        start_deaths = _number(initial.get('deaths'))
        paid_ore = paid_gear = paid_deaths = 0.0
        for transition in transitions:
            after = transition['after_state']
            next_peak = max(peak, min(230.0, _number(after.get('player', {}).get('x'))))
            progress = 0.35 * (next_peak - peak) / max(1.0, 230.0 - start_x)
            peak = next_peak
            ore_total = min(10.0, max(0.0, _number(after.get('stats', {}).get('ore')) - start_ore))
            gear_total = min(5.0, max(0.0, sum(_number(after.get('equipment', {}).get(k)) for k in ('pick', 'sword', 'armor')) - start_gear))
            death_total = min(2.0, max(0.0, _number(after.get('deaths')) - start_deaths))
            ore = 0.01 * max(0.0, ore_total - paid_ore)
            gear = 0.02 * max(0.0, gear_total - paid_gear)
            death = -0.05 * max(0.0, death_total - paid_deaths)
            paid_ore, paid_gear, paid_deaths = max(paid_ore, ore_total), max(paid_gear, gear_total), max(paid_deaths, death_total)
            result.append(round(progress + ore + gear + death, 9))
    return result


def returns_to_go(rewards, terminal_reward):
    if terminal_reward not in (0, 1):
        raise ValueError('terminal reward must be an engine win flag')
    future = float(terminal_reward)
    returns = [0.0] * len(rewards)
    for index in range(len(rewards) - 1, -1, -1):
        future = float(rewards[index]) + DISCOUNT * future
        returns[index] = future
    return returns


def potential(kind, state, initial):
    """Bounded objective potential from observable, executed state only."""
    if kind == 'tetris_placement':
        from jev_showcase_games import metrics
        board = state['board']
        holes, height, bump = metrics(board)
        maximum = max(len(board)-next((y for y,row in enumerate(board) if row[x]), len(board))
                      for x in range(len(board[0])))
        return max(-.25, -.025*holes-.008*maximum-.001*bump)+.04*min(4, state['lines'])
    if kind == 'mario_platformer':
        return .25*min(100., _number(state.get('progress')))/100.
    if kind == 'terraria_survival':
        player = state['player']
        anchor = state.get('last_known_surface')
        if not anchor:
            return 0.
        depth = max(0., _number(player['y'])-anchor[1]+2)
        progress = max(0., _number(player['x'])-_number(initial['player']['x']))
        # Underground horizontal mining cannot earn surface progress.
        return (.25*min(1., progress/max(1., 230.-_number(initial['player']['x'])))
                if depth <= 2 else -min(.15, depth*.01))
    if kind == 'sokoban_puzzle':
        from itertools import permutations
        boxes, goals = state['boxes'], state['targets']
        distance = min(sum(abs(b[0]-g[0])+abs(b[1]-g[1]) for b,g in zip(boxes, order))
                       for order in permutations(goals))
        placed = len({tuple(p) for p in boxes}&{tuple(p) for p in goals})
        return max(-.2, .05*placed-.01*distance)
    return 0.


def executed_process_rewards(kind, initial, trace):
    if kind not in ('tetris_placement','mario_platformer','terraria_survival','sokoban_puzzle'):
        return None
    rewards = []
    for transition in trace:
        before = transition.get('credit_before_state', transition['before_state'])
        after = transition.get('credit_after_state', transition['after_state'])
        # An absorbing state has zero potential, so failed progress is paid back.
        terminal = bool(after.get('outcome')) or (kind=='terraria_survival' and after.get('wins',0)>initial.get('wins',0))
        newer = 0. if terminal else potential(kind, after, initial)
        value = DISCOUNT*newer-potential(kind, before, initial)
        if kind == 'terraria_survival':
            value -= .1*max(0., _number(after.get('deaths'))-_number(before.get('deaths')))
        rewards.append(value)
    # Budget exhaustion is an absorbing outcome too, despite engines that
    # leave outcome unset. Remove the tail potential at the last action.
    tail = trace[-1].get('credit_after_state', trace[-1]['after_state']) if trace else None
    if tail and not tail.get('outcome') and not (kind=='terraria_survival' and tail.get('wins',0)>initial.get('wins',0)):
        rewards[-1] -= DISCOUNT*potential(kind, tail, initial)
    return rewards
