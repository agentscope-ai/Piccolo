"""Native episode scores for same-game, same-seed Arena comparisons.

The caller owns admission, persistent receipts, caching and concurrency. This
module only reuses the production evaluator and exports observed final scores;
it does not infer a terminal score from an API error or import archived runs.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import time

from jev_demo_decision_stability import (REVISION as STABILITY_REVISION,
    POLICY_REVISION, REALTIME_GAME_KINDS, decision_policy)
from jev_demo_game_evaluation import EVALUATION_REVISION, WORLD, GAME_ENGINE_REVISIONS
from jev_realtime_scoring import score_episode, SCORING_REVISION

REVISION = 'jev-arena-native-episode-scores-v3-realtime-time'
DECISION_POLICY = POLICY_REVISION
CAPTURE_REVISION = 'jev-arena-final-state-v1'

_SPECS = {
    'chess': ('native_goal_result', '原生国际象棋终局胜负', ['outcome']),
    'jump_jump': ('platforms_reached', '已落平台数', ['score']),
    'snake_navigation': ('foods_eaten', '已吃食物数', ['score']),
    'tetris_placement': ('lines_cleared', '累计消除行数', ['lines']),
    'merge_2048': ('merge_points', '原生合并积分', ['score']),
    'sokoban_puzzle': ('boxes_on_targets', '已到目标格箱数', ['score']),
    'racing_sprint': ('distance_metres', '实际行驶距离（米）', ['score', 'health']),
    'mario_platformer': ('progress_percent', '最终关卡进度（%）', ['progress', 'score']),
    'terraria_survival': ('gates_reached', '本局到达终点次数', ['wins_delta', 'player.x']),
    'blackjack': ('native_return', '原生庄家对局结算收益', ['terminal_returns[model_player]']),
    # Available for fixed-rule-opponent cohorts. The current Arena may instead
    # schedule these games as direct model duels.
    'texas_holdem': ('chip_profit', '终局筹码净收益（起始1000）', ['stacks[model_player]-1000']),
    'zha_jin_hua': ('chip_profit', '终局筹码净收益（起始200）', ['stacks[model_player]-200']),
    'property_tycoon': ('total_assets', '终局现金与地产总资产', ['cash+property_value']),
    'pig_dice': ('banked_points', '终局已收下点数', ['scores[model_player]']),
    'doudizhu': ('terminal_result', '原生胜平负：胜1／平0.5／负0', ['outcome']),
}
from jev_selected_games import GAMES as SELECTED_GAMES
_SPECS.update({kind: ('native_goal_result', '原生终局胜负', ['outcome']) for kind in SELECTED_GAMES})

GOAL_ENVIRONMENTS = frozenset(('jump_jump', 'snake_navigation', 'tetris_placement',
    'merge_2048', 'sokoban_puzzle', 'racing_sprint', 'mario_platformer', 'terraria_survival'))


def comparison_spec(kind):
    if kind not in _SPECS:
        raise ValueError('unsupported_paired_episode_kind')
    metric, label, fields = _SPECS[kind]
    fields = (['natural_success'] if kind in GOAL_ENVIRONMENTS else []) + fields
    if kind in REALTIME_GAME_KINDS:
        fields = ['natural_success', 'completed_or_native_progress', 'time_tiebreak']
        if kind == 'racing_sprint':
            fields.append('health')
        elif kind == 'mario_platformer':
            fields.append('score')
    fixed_opponent = (kind in SELECTED_GAMES and SELECTED_GAMES[kind][4]>1) or kind in ('chess', 'blackjack', 'texas_holdem', 'zha_jin_hua',
                              'property_tycoon', 'pig_dice', 'doudizhu')
    return {'revision': REVISION, 'kind': kind, 'metric': metric, 'score_label': label,
            'score_fields': list(fields), 'higher_is_better': True,
            'comparison': 'lexicographic' if len(fields) > 1 else 'scalar',
            'comparison_rule': ('通关优先；未完成先比较实际进度；同完成程度用时较短优先；零进度不奖励早结束'
                                if kind in REALTIME_GAME_KINDS else
                                '通关优先；再比较' + label
                                if kind in GOAL_ENVIRONMENTS else label),
            'opponent_policy': 'native-fixed-rule-opponent-v1' if fixed_opponent else 'native-environment-v1',
            'seat_rule': 'existing_game_evaluator_seed_seat_v1',
            'engine_revision': EVALUATION_REVISION, 'decision_policy': decision_policy(kind),
            **({'game_engine_revision': GAME_ENGINE_REVISIONS[kind]} if kind in GAME_ENGINE_REVISIONS else {}),
            **({'time_scoring_revision': SCORING_REVISION} if kind in REALTIME_GAME_KINDS else {}),
            'budget_rule': 'record observed final state at fixed decision budget; never claim natural termination'}


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('native_score_missing_or_nonfinite')
    return value


def _identity(evaluator, model):
    ident, spec = evaluator.model_spec(model)
    if ident != model:
        raise ValueError('registered_model_identity_mismatch')
    provider = spec.get('provider', 'local')
    if provider in ('dashscope', 'decision', 'openai') and isinstance(spec.get('served_model'), str):
        return {'id': model, 'provider': provider, 'served_model': spec['served_model']}
    if provider == 'local' and spec.get('path'):
        return {'id': model, 'provider': provider, 'model_path': str(Path(spec['path']).resolve())}
    raise ValueError('unsupported_episode_model_identity')


def _budget_stop(kind, result):
    final = result.get('final_state') or {}
    return (result.get('outcome') == 'budget_exhausted' or kind in ('racing_sprint', 'snake_navigation', 'tetris_placement')
            and (final.get('failure_reason') or result.get('failure_reason')) == 'decision_budget_exhausted')


def _termination(kind, result, evidence):
    final = result['final_state']
    if (result.get('error_type') or any(reason in ('model_error', 'model_timeout')
            for reason in (result.get('failure_reason'), final.get('failure_reason')))):
        raise ValueError('native_episode_inference_failed')
    if result.get('outcome') not in ('win', 'draw', 'loss', 'budget_exhausted'):
        raise ValueError('invalid_native_episode_outcome')
    final_outcome = final.get('outcome')
    if (kind in SELECTED_GAMES or kind == 'chess') and final_outcome == 'budget_exhausted': final_outcome = None
    if final_outcome not in (None, 'win', 'loss', 'draw'):
        raise ValueError('invalid_native_terminal_outcome')
    budget = _budget_stop(kind, result)
    terminal = (final_outcome is not None or kind == 'terraria_survival'
                and evidence['natural_success']) and not budget
    if not budget and not terminal:
        raise ValueError('native_terminal_state_missing')
    if result['outcome'] == 'budget_exhausted' and final_outcome is not None:
        raise ValueError('native_outcome_terminal_mismatch')
    if (kind == 'terraria_survival' and evidence['final_wins'] > evidence['initial_wins']
            and result['outcome'] != 'win'):
        raise ValueError('native_goal_outcome_mismatch')
    if kind != 'terraria_survival' and terminal:
        expected = ({'win': 'loss', 'loss': 'win'}.get(final_outcome, final_outcome)
                    if result.get('model_player') in (1, 2) else final_outcome)
        if expected != result['outcome']:
            raise ValueError('native_model_perspective_mismatch')
    return budget, terminal


def _score(kind, result):
    final = result.get('final_state')
    if not isinstance(final, dict):
        raise ValueError('native_final_state_missing')
    side = result.get('model_player', 0)
    if side is None and kind in WORLD:
        side = 0  # Browser environment episodes have one controller, no opponent seat.
    if type(side) is not int or side not in (0, 1, 2):
        raise ValueError('native_model_seat_missing')
    evidence = {'model_player': side}
    if kind in SELECTED_GAMES or kind == 'chess':
        score = {'win': 1., 'draw': .5, 'loss': 0., 'budget_exhausted': 0.}[result['outcome']]
        key = [score]
        evidence['outcome'] = result['outcome']
    elif kind == 'terraria_survival':
        initial = result.get('initial_state')
        if not isinstance(initial, dict):
            raise ValueError('native_initial_state_missing')
        score = _number(final.get('wins'))-_number(initial.get('wins'))
        if score < 0:
            raise ValueError('world_reset_during_episode')
        x = _number(final.get('player', {}).get('x'))
        key = [score, x]
        evidence.update(initial_wins=initial['wins'], final_wins=final['wins'], final_x=x,
                        deaths=final.get('deaths'))
    elif kind == 'mario_platformer':
        score = _number(final.get('progress'))
        points = _number(final.get('score'))
        key = [score, points]
        evidence.update(progress=score, native_points=points)
    elif kind == 'blackjack':
        returns = result.get('terminal_returns')
        if not isinstance(returns, list) or side >= len(returns) or not final.get('outcome'):
            raise ValueError('native_terminal_payout_missing')
        score = _number(returns[side]);key = [score]
        evidence['terminal_returns'] = list(returns)
    elif kind in ('texas_holdem', 'zha_jin_hua'):
        stacks = final.get('stacks')
        if not isinstance(stacks, list) or side >= len(stacks):
            raise ValueError('native_stacks_missing')
        initial_chips = 1000 if kind == 'texas_holdem' else 200
        score = _number(stacks[side])-initial_chips;key = [score]
        evidence.update(final_chips=stacks[side], initial_chips=initial_chips)
    elif kind == 'property_tycoon':
        cash, owners, prices, levels = (final.get(key) for key in ('cash', 'owners', 'prices', 'levels'))
        if not isinstance(cash, list) or side >= len(cash) or not all(isinstance(x, dict) for x in (owners, prices, levels)):
            raise ValueError('native_property_assets_missing')
        property_value = sum(_number(prices.get(str(square), prices.get(int(square)))) *
                             (1+.5*_number(levels.get(str(square), levels.get(int(square), 0))))
                             for square, owner in owners.items() if owner == side)
        score = _number(cash[side])+property_value;key = [score]
        evidence.update(cash=cash[side], property_value=property_value)
    elif kind == 'pig_dice':
        scores = final.get('scores')
        if not isinstance(scores, list) or side >= len(scores):
            raise ValueError('native_banked_points_missing')
        score = _number(scores[side]);key = [score]
        evidence['banked_points'] = score
    elif kind == 'doudizhu':
        if result.get('outcome') not in ('win', 'draw', 'loss') or not final.get('outcome'):
            raise ValueError('native_terminal_result_missing')
        score = {'win': 1, 'draw': .5, 'loss': 0}[result['outcome']];key = [score]
        evidence['outcome'] = result['outcome']
    else:
        field = 'lines' if kind == 'tetris_placement' else 'score'
        score = _number(final.get(field));key = [score]
        evidence[field] = score
        if kind == 'merge_2048':
            board = final.get('board')
            if not isinstance(board, list) or not board or not all(isinstance(row, list) and row for row in board):
                raise ValueError('native_2048_board_missing')
            evidence['max_tile'] = max(_number(value) for row in board for value in row)
        elif kind == 'racing_sprint':
            health = _number(final.get('health'))
            key.append(health)
            evidence['health'] = health
    if kind in GOAL_ENVIRONMENTS:
        success = (score > 0 if kind == 'terraria_survival' else final.get('outcome') == 'win') and not _budget_stop(kind, result)
        key.insert(0, int(success))
        evidence['natural_success'] = bool(success)
    if kind in REALTIME_GAME_KINDS:
        timing = score_episode(kind, final, 'win' if evidence['natural_success'] else result['outcome'],
                               elapsed_seconds=result.get('real_time_seconds'))
        key = list(timing['comparison_key'])
        if kind == 'racing_sprint':
            key.append(evidence['health'])
        elif kind == 'mario_platformer':
            key.append(evidence['native_points'])
        evidence['time_score'] = timing
    return score, key, evidence


async def run_episode(evaluator, kind, seed, model, browser=None):
    """Run one native episode; the caller persists/cache-binds the returned row.

    ``evaluator.predict`` uses one probe for real-time games and three otherwise. Local
    prediction keeps its existing per-call /model_info checkpoint validation.
    Exceptions retain ``episode_trace`` containing completed model decisions.
    """
    spec = comparison_spec(kind)
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError('invalid_episode_seed')
    identity = _identity(evaluator, model)
    runner = copy.copy(evaluator)
    runner.capture_final_state = True
    original_predict = evaluator.predict
    trace = []
    began = time.monotonic()

    async def predict(record, qid, model=None):
        if model != identity['id'] or _identity(evaluator, model) != identity:
            raise ValueError('episode_model_registration_changed')
        result = await original_predict(record, qid, model=model)
        if result.get('model') != identity['id']:
            raise ValueError('episode_response_model_mismatch')
        expected_served = identity.get('served_model', identity.get('model_path'))
        if (identity['provider'] in ('dashscope', 'decision', 'openai') and result.get('served_model') != expected_served
                or identity['provider'] == 'local' and result.get('served_model') not in (None, expected_served)):
            raise ValueError('episode_served_model_mismatch')
        stability = result.get('decision_stability')
        if kind in REALTIME_GAME_KINDS:
            if result.get('decision_policy') != decision_policy(kind) or stability is not None:
                raise ValueError('single_realtime_decision_required')
            samples = []
        else:
            if (not isinstance(stability, dict) or stability.get('revision') != STABILITY_REVISION
                    or stability.get('repeat_count') != 3 or len(stability.get('samples', [])) != 3):
                raise ValueError('three_decision_samples_required')
            samples = stability['samples']
        for sample in samples:
            if (sample.get('model') != identity['id'] or identity['provider'] in ('dashscope', 'decision', 'openai')
                    and sample.get('served_model') != expected_served):
                raise ValueError('episode_sample_model_mismatch')
        trace.append({'ordinal': len(trace), 'player': identity['id'], 'model': identity['id'],
                      'served_model': expected_served, 'action': result.get('value'),
                      'latency_seconds': result.get('latency_seconds'),
                      'decision_policy': decision_policy(kind),
                      **({'decision_stability': copy.deepcopy(stability)} if stability else {})})
        return result

    runner.predict = predict
    try:
        if kind in WORLD:
            from jev_engine_registry import get_engine
            if get_engine(kind).backend == 'browser' and browser is None:
                raise ValueError('world_episode_requires_browser')
            native = await runner._world(browser, kind, seed, model)
        else:
            native = await runner._python(None, kind, seed, 'rule_engine', model)
        if (native.get('status', 'complete') != 'complete' or native.get('error_type')
                or native.get('outcome') not in ('win', 'draw', 'loss', 'budget_exhausted')):
            raise ValueError('native_episode_failed')
        if kind != 'racing_sprint' and native.get('capture_revision') != CAPTURE_REVISION:
            raise ValueError('native_final_state_capture_missing')
        if native.get('model_calls') != len(trace):
            raise ValueError('native_decision_trace_incomplete')
        score, key, evidence = _score(kind, native)
        budget, terminal = _termination(kind, native, evidence)
        return {**{key: value for key, value in native.items() if key != 'trace'},
                'status': 'complete', 'episode_revision': REVISION, 'engine_revision': EVALUATION_REVISION,
                'decision_policy': decision_policy(kind), 'kind': kind, 'seed': seed, 'model': model,
                'model_identity': identity, 'comparison_spec': spec, 'terminal': terminal,
                'budget_exhausted': budget, 'natural_success': evidence.get('natural_success'),
                'score': score, 'score_label': spec['score_label'], 'higher_is_better': True,
                'comparison_key': key, 'score_evidence': evidence, 'trace': trace,
                **({'time_score': evidence['time_score']} if 'time_score' in evidence else {}),
                'native_trace': native.get('trace'), 'seconds': round(time.monotonic()-began, 3),
                'opponent_policy': spec['opponent_policy'],
                'model_player': evidence['model_player']}
    except BaseException as error:
        error.episode_trace = copy.deepcopy(trace)
        raise


def compare_results(a, b):
    """Return A's Elo result (1/.5/0) using the bound goal-first native key."""
    spec = comparison_spec(a.get('kind'))
    for result in (a, b):
        if (result.get('status') != 'complete' or result.get('episode_revision') != REVISION
                or result.get('engine_revision') != EVALUATION_REVISION
                or result.get('decision_policy') != decision_policy(a['kind']) or result.get('comparison_spec') != spec
                or result.get('kind') != a.get('kind') or result.get('seed') != a.get('seed')
                or result.get('higher_is_better') is not True):
            raise ValueError('incompatible_native_episode_results')
        key = result.get('comparison_key')
        if not isinstance(key, list) or len(key) != len(spec['score_fields']):
            raise ValueError('native_comparison_key_missing')
        for value in key:
            _number(value)
        score, observed_key, evidence = _score(a['kind'], result)
        if result.get('score') != score or key != observed_key:
            raise ValueError('native_score_evidence_mismatch')
        if a['kind'] in REALTIME_GAME_KINDS:
            if result.get('time_score') != evidence['time_score']:
                raise ValueError('native_time_score_evidence_mismatch')
        budget, terminal = _termination(a['kind'], result, evidence)
        if (result.get('budget_exhausted') != budget or result.get('terminal') != terminal
                or result.get('natural_success') != evidence.get('natural_success')):
            raise ValueError('native_termination_evidence_mismatch')
    left, right = tuple(a['comparison_key']), tuple(b['comparison_key'])
    return 1. if left > right else 0. if left < right else .5
