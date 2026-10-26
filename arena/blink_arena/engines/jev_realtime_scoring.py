"""Completion-first, measured-time scores shared by realtime RL and Arena.

Arena compares ``comparison_key`` lexicographically: completion, native
progress, then less elapsed time. RL uses the bounded continuous utility. Its
unfinished time term is smaller than one published progress increment, so an
early failure cannot buy back lost progress. Zero progress earns no speed bonus.

This module never reconstructs old timing from decision counts or API latency.
Browser worlds require an explicitly measured active wall clock; racing, Snake
and Tetris use authoritative clocks starting on the first actual input.
"""
from __future__ import annotations

import math

SCORING_REVISION = 'realtime-completion-progress-time-v1'
REALTIME_KINDS = frozenset(('mario_platformer', 'terraria_survival',
                            'racing_sprint', 'snake_navigation', 'tetris_placement'))
# Browser worlds have an action budget, not an engine wall-time deadline.
# The scale makes the speed component dimensionless; it is not a new timeout.
TIME_SCALES = {'mario_platformer': 300., 'terraria_survival': 600.,
               'racing_sprint': 300., 'snake_navigation': 240., 'tetris_placement': 240.}


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('realtime_score_missing_' + label)
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        raise ValueError('realtime_score_invalid_' + label)
    return result


def score_episode(kind, final_state, outcome, *, elapsed_seconds=None):
    """Score a newly observed terminal episode; missing timing fails closed.

    ``outcome`` is the evaluator's observed result (including budget exhaustion),
    not a score-derived success guess. Terra's world resets immediately on a
    win, so its caller must determine this from the observed increase in wins.
    """
    if kind not in REALTIME_KINDS:
        raise ValueError('unsupported_realtime_score_kind')
    if not isinstance(final_state, dict):
        raise ValueError('realtime_score_missing_final_state')
    if outcome not in ('win', 'loss', 'draw', 'budget_exhausted',
                       'no_legal_actions', 'timeout', 'error'):
        raise ValueError('realtime_score_unknown_outcome')
    completed = outcome == 'win'
    time_limit = None
    if kind in ('racing_sprint', 'snake_navigation', 'tetris_placement'):
        if kind == 'tetris_placement':
            from jev_tetris_realtime import is_realtime
            if not is_realtime(final_state):
                raise ValueError('realtime_score_requires_current_tetris_engine')
        # Ignore caller episode/setup duration: these engine clocks exclude the
        # free pre-start wait and include all wall-time physics after launch.
        elapsed = _number(final_state.get('elapsed'), 'elapsed_seconds')
        time_source = 'engine_elapsed_after_first_input'
        default_limit = 300. if kind == 'racing_sprint' else 240.
        time_limit = _number(final_state.get('time_limit', default_limit), 'time_limit', positive=True)
    else:
        elapsed = _number(elapsed_seconds if elapsed_seconds is not None
                          else final_state.get('real_time_seconds'), 'elapsed_seconds')
        time_source = 'active_wall_clock_including_inference'
    if kind == 'racing_sprint':
        native_progress = _number(final_state.get('score', final_state.get('z')), 'distance')
        target = _number(final_state.get('finish_distance', 900.), 'finish_distance', positive=True)
        progress = min(1., native_progress / target)
    elif kind == 'snake_navigation':
        native_progress = _number(final_state.get('score'), 'foods_eaten')
        target = _number(final_state.get('food_target', final_state.get('target_food')), 'food_target', positive=True)
        progress = min(1., native_progress / target)
    elif kind == 'tetris_placement':
        native_progress = _number(final_state.get('lines'), 'lines_cleared')
        target = _number(final_state.get('line_target', 4.), 'line_target', positive=True)
        progress = min(1., native_progress / target)
    elif kind == 'mario_platformer':
        native_progress = _number(final_state.get('progress'), 'progress_percent')
        progress = min(1., native_progress / 100.)
    else:
        x = _number(final_state.get('player', {}).get('x'), 'player_x')
        # The production 240-column world spawns at 5*16+2 px and places
        # the gate at column 237. Coordinates in public snapshots are tiles.
        native_progress = max(0., x - 5.125)
        progress = min(1., native_progress / (237. - 5.125))
    if completed:
        progress = 1.
    if elapsed == 0 and (completed or progress > 0):
        raise ValueError('realtime_score_progress_without_elapsed_time')
    efficiency = TIME_SCALES[kind] / (TIME_SCALES[kind] + elapsed)
    utility = (.8 + .2 * efficiency if completed else
               .69999999 * progress + 1e-8 * progress * efficiency)
    time_tiebreak = -elapsed if completed or progress > 0 else 0.
    return {'utility': utility, 'terminal_reward': 2. * utility - 1.,
            'progress': progress, 'native_progress': native_progress,
            'elapsed_seconds': elapsed, 'time_limit': time_limit,
            'time_scale_seconds': TIME_SCALES[kind], 'time_source': time_source,
            'completed': completed, 'time_tiebreak': time_tiebreak,
            'comparison_key': [int(completed), 1. if completed else native_progress,
                               time_tiebreak],
            'scoring_revision': SCORING_REVISION}
