"""The active chess catalog uses the same core in evaluation and replay."""
import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest

import blink_arena.engine  # Install bundled import path.
from jev_engine_registry import get_engine, _ENGINES
from jev_demo_game_evaluation import GameEvaluator, _seat, _modes
from jev_demo_decision_stability import repeated_predict
from jev_demo_arena_episodes import run_episode, comparison_spec
from jev_demo_arena_replay_native import native_frames
from jev_chess_rl import verify


def evaluator(tmp_path, actions=None):
    async def predict_once(record, qid, model=None):
        question = record['questions'][qid]
        options = question['criteria']
        ordinal = record['state']['observation']['steps']
        action = actions[ordinal] if actions else sorted(options)[0]
        return {'model': model, 'served_model': 'fixture', 'value': action,
            'label': options[action], 'latency_seconds': 0.,
            'distribution': [{'value': key, 'label': value, 'probability': float(key == action)}
                             for key, value in options.items()],
            'probability_coverage': {'complete': True}}

    async def predict(record, qid, model=None):
        return await repeated_predict(predict_once, record, qid, model=model)

    result = GameEvaluator(predict, lambda: 'fixture',
        lambda model: (model, {'provider': 'decision', 'served_model': 'fixture'}),
        'http://127.0.0.1:1', out=tmp_path)

    async def opponent(pool, kind, seed, ordinal, record):
        assert kind == 'chess'
        return actions[ordinal] if actions else sorted(record['questions']['decision']['criteria'])[0]

    result._qwen = opponent
    return result


def test_chess_evaluator_has_balanced_seats_and_explicit_opponents():
    modes = _modes('chess', 8)
    conditions = [(mode, _seat('chess', seed, mode)) for seed, mode in enumerate(modes)]
    assert all(conditions.count((mode, side)) == 2 for mode in ('qwen3.8-max', 'rule_engine') for side in (0, 1))


def test_actual_evaluator_detects_checkmate_and_cannot_export_rl(tmp_path):
    runner = evaluator(tmp_path, ['f2f3', 'e7e5', 'g2g4', 'd8h4'])
    result = asyncio.run(runner._python(None, 'chess', 0, 'qwen3.8-max', 'fixture'))
    assert result['outcome'] == 'loss' and result['model_player'] == 0
    assert result['final_state']['termination'] == 'checkmate' and result['replay_verified']
    assert result['model_calls'] == 2 and len(result['evaluation_extra']['events']) == 4
    assert result['evaluation_only'] and not result['on_policy'] and result['reward_export_prohibited']
    assert all(row['policy']['origin'] == 'evaluation_model' and 'old_probabilities' not in row['policy'] for row in result['trace'])
    with pytest.raises(ValueError):
        verify(result['evaluation_job'], result['initial_state'], result['final_engine_state'],
               result['evaluation_extra'], trace=result['trace'])
    frames = native_frames({**result, 'kind': 'chess', 'seed': 0})
    assert [frame['action'] for frame in frames] == ['f2f3', 'e7e5', 'g2g4', 'd8h4']
    assert [frame['model_call'] for frame in frames] == [True, False, True, False]


def test_chess_arena_scores_budget_as_incomplete_and_replays_all_seats(tmp_path, monkeypatch):
    engine = get_engine('chess')
    monkeypatch.setitem(_ENGINES, 'chess', replace(engine, limit=8))
    result = asyncio.run(run_episode(evaluator(tmp_path), 'chess', 0, 'fixture'))
    assert result['kind'] == 'chess' and result['model_player'] == 1
    assert result['outcome'] == 'budget_exhausted' and result['score'] == 0
    assert result['budget_exhausted'] and not result['terminal']
    assert result['comparison_spec'] == comparison_spec('chess')
    assert len(result['trace']) == 4 and len(result['native_trace']) == 4
    frames = native_frames(result)
    assert len(frames) == 8 and sum(frame['model_call'] for frame in frames) == 4
    assert {frame['actor'] for frame in frames} == {0, 1}
    assert all(frame['controller'] == 'rule_engine' for frame in frames if not frame['model_call'])
    for field in ['final_state', 'evaluation_extra', 'trace']:
        changed = deepcopy(result)
        if field == 'final_state': changed[field]['current_player'] = 1 - changed[field]['current_player']
        elif field == 'evaluation_extra': changed[field]['events'][1]['actor'] = 1 - changed[field]['events'][1]['actor']
        else: changed[field][0]['action'] = 'invalid'
        with pytest.raises(ValueError): native_frames(changed)
