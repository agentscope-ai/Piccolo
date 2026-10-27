"""Verify the actual public showcase and reject a forged win or changed action."""
import copy
import json
import os
from pathlib import Path
import unittest

from scripts.export_home_decision import verify_completed


class CompletedHomeReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('JEV_HOME_REPLAY',
                    Path(__file__).resolve().parents[1] / 'web/playground/data/home-decision.json'))
        cls.archive = json.loads(path.read_text())

    def test_every_selected_episode_replays_to_a_natural_win(self):
        self.assertGreater(verify_completed(self.archive), 50)

    def test_budget_exhaustion_cannot_be_published_as_a_win(self):
        changed = copy.deepcopy(self.archive)
        changed['clips'][0]['result']['budget_exhausted'] = True
        with self.assertRaises(AssertionError):
            verify_completed(changed)

    def test_changed_tile_or_action_is_rejected(self):
        for field in ('tile', 'action'):
            changed = copy.deepcopy(self.archive)
            clip = next(c for c in changed['clips'] if c['game'] == 'merge_2048')
            if field == 'tile':
                clip['steps'][0]['after']['board'][0][0] += 2
            else:
                clip['steps'][0]['action'] = 'invented-move'
            with self.subTest(field=field), self.assertRaises(AssertionError):
                verify_completed(changed)

    def test_opponent_and_automatic_steps_are_not_model_decisions(self):
        for clip in self.archive['clips']:
            controlled = [step for step in clip['steps'] if step['model_call']]
            self.assertEqual(len(controlled), clip['model_calls'])
            for step in clip['steps']:
                if step['model_call']:
                    self.assertEqual(step['model_id'], clip['models'][0]['id'])
                    self.assertIsInstance(step['latency_seconds'], (float, int))
                else:
                    self.assertIsNone(step['model_id'])
                if step['execution'].get('no_request'):
                    self.assertIsNone(step['action'])
                    self.assertEqual(step['candidates'], [])


if __name__ == '__main__':
    unittest.main()
