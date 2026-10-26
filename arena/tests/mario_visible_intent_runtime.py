"""Real-clock shared worker intent/replay smoke; fixture policy, never a model win."""
from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import blink_arena
from jev_engine_registry import get_engine
import jev_world_core_rl as rl
from jev_world_core import WorldCoreDriver


class VisibleIntentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_worker_executes_one_bound_choice_then_replays_exact_input_and_credit(self):
        seen = []

        class FixturePolicy:
            async def policy_action(self, record, episode_id, ordinal):
                values = record['questions']['decision']['option_order']
                targets = [v for v in values if v.startswith('cross_visible_right:')]
                if not targets:
                    raise AssertionError('seed fixture must offer a visible target')
                action = targets[0]
                seen.append(copy.deepcopy(record))
                await asyncio.sleep(.04)
                return action, {'origin': 'test_reference_controller', 'on_policy': False,
                                'candidate_values': values, 'selected_index': values.index(action),
                                'old_probabilities': [1 / len(values)] * len(values)}

        job = {'kind': 'mario_platformer', 'seed': 2,
               'episode_id': 'visible-target-worker-reference-fixture'}
        with patch.dict(rl.LIMITS, {'mario_platformer': 1}):
            initial, final, trace, outcome, extra = await rl.play(FixturePolicy(), job)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(extra['replay_events']), 1)
        event = extra['replay_events'][0]
        self.assertEqual(event['record'], seen[0])
        self.assertFalse(initial['timing']['inference_world_paused'])
        self.assertGreater(final['frame'], initial['frame'])
        self.assertGreater(extra['real_time_seconds'], 0)
        self.assertEqual(event['policy']['candidate_values'][event['policy']['selected_index']], event['action'])
        self.assertTrue(event['action_applied'], event['discard_reason'])
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]['record'], seen[0])
        self.assertEqual(trace[0]['control_ownership']['strategy_origin'], 'A')
        self.assertEqual(trace[0]['control_ownership']['selected_execution_origin'], 'B')
        self.assertEqual(final['action_execution']['rule_takeover_count'], 0)
        effect = final['action_execution']['recent_effects'][-1]
        self.assertEqual(effect['jumps_started'], 1)
        self.assertEqual(effect['event'], 'landed')
        self.assertGreater(effect['approach_frames'], 0)
        proof = await rl.verify_with_trace(None, job, initial, final, trace, extra)
        self.assertTrue(proof['strict_match'])
        changed = copy.deepcopy(extra)
        changed['replay_events'][0]['record']['questions']['decision']['criteria'][event['action']] += ' changed'
        with self.assertRaisesRegex(ValueError, 'observation_did_not_replay'):
            await rl.verify(job, initial, final, changed)
        path = os.environ.get('JEV_MARIO_INTENT_RUNTIME_EVIDENCE')
        if path:
            report = {'passed': True, 'real_model_calls': 0, 'training_rows_enqueued': 0,
                      'policy_origin': 'test_reference_controller', 'episode_outcome': outcome,
                      'this_is_not_a_model_win': True, 'event': event, 'execution_effect': effect,
                      'credit': trace[0]['control_ownership'], 'strict_replay': proof,
                      'real_time_seconds': extra['real_time_seconds']}
            Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    async def test_baseline_features_are_unchanged_by_new_candidate_descriptions(self):
        source = Path(__file__).resolve().parents[2] / 'CuES-plus/src/tools/jev_state_baseline.py'
        if not source.is_file():
            self.skipTest('Standalone package does not bundle the training value estimator')
        spec = importlib.util.spec_from_file_location('mario_baseline_probe', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        visible_features = module.visible_features
        async with WorldCoreDriver('mario_platformer', 2, replay=True) as driver:
            state = driver.initial['state']
        record = get_engine('mario_platformer').observe(state)
        stripped = copy.deepcopy(record)
        stripped['state'].pop('prompt_revision', None)
        stripped['state']['observation'].pop('candidate_effects', None)
        stripped['questions']['decision']['criteria'] = {'right': '旧原子动作'}
        stripped['questions']['decision']['option_order'] = ['right']
        self.assertEqual(visible_features(record), visible_features(stripped))


if __name__ == '__main__':
    unittest.main()
