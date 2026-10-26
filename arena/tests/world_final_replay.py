"""Read-only regression replay of real trajectories; never model scores.

Set JEV_FINAL_REPLAY_FAILED_JOURNAL to a rejected final-reply journal and
JEV_FINAL_REPLAY_RECEIPTS to a JSON array of historical completed receipts.
The large original journals stay outside this portable repository.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import blink_arena
from jev_gameplay_reward_contract import default_config, validate_episode
from jev_world_core import WorldCoreDriver
from jev_world_realtime_rl import _same
import jev_world_core_rl as rl
from jev_world_replay_validation import ReplayValidation


def events_at(path):
    with Path(path).open() as stream:
        for line in stream:
            entry = json.loads(line)
            if entry['event'] == 'executed_realtime':
                yield entry['value']


class FinalReplayTests(unittest.IsolatedAsyncioTestCase):
    def test_semantic_tolerance_is_small_explicit_and_never_reward_state(self):
        state = {'player': {'x': 10., 'y': 2., 'hp': 100., 'vx': .1},
                 'enemies': [{'x': 20., 'hp': 10.}], 'deaths': 0, 'wins': 0,
                 'equipment': {'pick': 1}, 'objective': {'gate_unlocked': False},
                 'known_guardians': [{'id': 7, 'x': 30., 'last_seen_frame': 10}]}
        for path, value in [('geometry', 20.0000001), ('memory', 100)]:
            altered = copy.deepcopy(state)
            if path == 'geometry': altered['enemies'][0]['x'] = value
            else: altered['known_guardians'][0]['last_seen_frame'] = value
            self.assertFalse(ReplayValidation('strict').same(altered, state, 'final'))
            check = ReplayValidation('semantic-v1')
            self.assertTrue(check.same(altered, state, 'final'))
            self.assertEqual(check.proof()['relaxed_count'], 1)
            self.assertFalse(check.proof()['strict_match'])
            if path == 'memory':
                self.assertFalse(ReplayValidation('semantic-v1').same(altered, state, 'observation'))
        mutations = [('player', 'x', 10.0000001), ('player', 'hp', 100.0000001),
                     ('equipment', 'pick', 2), ('objective', 'gate_unlocked', True)]
        for section, key, value in mutations:
            altered = copy.deepcopy(state); altered[section][key] = value
            self.assertFalse(ReplayValidation('semantic-v1').same(altered, state, 'final'))
        for key in ('deaths', 'wins'):
            altered = copy.deepcopy(state); altered[key] += 1
            self.assertFalse(ReplayValidation('semantic-v1').same(altered, state, 'final'))
        altered = copy.deepcopy(state); altered['enemies'][0]['x'] += .01
        self.assertFalse(ReplayValidation('semantic-v1').same(altered, state, 'final'))
        altered = copy.deepcopy(state); altered['known_guardians'][0]['id'] += 1
        self.assertFalse(ReplayValidation('semantic-v1').same(altered, state, 'final'))

    @unittest.skipUnless(os.environ.get('JEV_FINAL_REPLAY_FAILED_JOURNAL'),
                         'Real failed journal is external to the package')
    async def test_last_rejected_reply_does_not_create_a_new_observation(self):
        path = Path(os.environ['JEV_FINAL_REPLAY_FAILED_JOURNAL'])
        before = path.stat()
        events = list(events_at(path))
        self.assertEqual(len(events), 300)
        self.assertFalse(events[-1]['action_applied'])
        self.assertEqual(events[-1]['discard_reason'], 'death_or_respawn')
        async with WorldCoreDriver('terraria_survival', 1204110047,
                                   replay=True, options={'generator_revision': 'world-seed-v1'}) as driver:
            for event in events:
                observed = await driver.call('replayObserve', frame=event['before_state']['frame'])
                self.assertTrue(_same(observed, event['before_state']), event['ordinal'])
                self.assertEqual(rl._record(rl.get_engine('terraria_survival').observe, observed),
                                 event['record'])
                result = await driver.call('replayEvent', event=event)
                self.assertEqual(result['verdict'], event['arrival_check'])
                self.assertTrue(_same(result['arrival'], event['arrival_state']))
                self.assertTrue(_same(result['after'], event['after_state']))
            expected = events[-1]['after_state']
            self.assertTrue(expected['timing']['awaiting_model'])
            self.assertTrue(expected['known_guardians'])
            final = await driver.call('replayFinal', frame=expected['frame'], awaiting=True)
            self.assertTrue(_same(final, expected))
            changed = copy.deepcopy(expected)
            changed['known_guardians'][0]['x'] += 1
            self.assertFalse(_same(final, changed))
        self.assertEqual(path.stat().st_size, before.st_size)
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)

    @unittest.skipUnless(os.environ.get('JEV_FINAL_REPLAY_RECEIPTS'),
                         'Historical receipt paths are external to the package')
    async def test_completed_mario_and_terra_preserve_exact_replay_and_rewards(self):
        for name in json.loads(os.environ['JEV_FINAL_REPLAY_RECEIPTS']):
            path = Path(name)
            before = path.stat()
            receipt = json.loads(path.read_text())
            with self.subTest(episode=receipt['episode_id']):
                self.assertEqual(receipt['status'], 'complete')
                journal = path.parent.parent / 'journals' / (receipt['rollout_id'] + '.jsonl')
                extra = {**receipt, 'replay_events': list(events_at(journal))}
                await rl.verify({'kind': receipt['kind'], 'seed': receipt['seed']},
                                receipt['initial_state'], receipt['final_state'], extra)
                validate_episode(receipt, default_config([receipt['kind']]))
                self.assertEqual(path.stat().st_size, before.st_size)
                self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)

    @unittest.skipUnless(os.environ.get('JEV_FINAL_REPLAY_SEMANTIC_RECEIPT'),
                         'Real semantic-mode receipt is external to the package')
    async def test_semantic_real_trajectory_preserves_inputs_and_rejects_critical_changes(self):
        path = Path(os.environ['JEV_FINAL_REPLAY_SEMANTIC_RECEIPT'])
        receipt = json.loads(path.read_text())
        events = list(events_at(path.parent.parent / 'journals' / (receipt['rollout_id'] + '.jsonl')))
        job = {'kind': receipt['kind'], 'seed': receipt['seed']}
        extra = {**receipt, 'replay_events': events}
        changed_final = copy.deepcopy(receipt['final_state'])
        self.assertTrue(changed_final['known_guardians'])
        changed_final['known_guardians'][0]['last_seen_frame'] += 1
        with patch.dict(os.environ, {'JEV_WORLD_REPLAY_MODE': 'semantic-v1'}):
            proof = await rl.verify(job, receipt['initial_state'], changed_final, extra)
            self.assertEqual(proof['relaxed_count'], 1)
            self.assertTrue(proof['model_input_exact'])
            changed_final['deaths'] += 1
            with self.assertRaisesRegex(ValueError, 'final_did_not_replay'):
                await rl.verify(job, receipt['initial_state'], changed_final, extra)
            tampered = copy.deepcopy(extra)
            tampered['replay_events'][0]['record']['state']['rules'] += ' tampered'
            with self.assertRaisesRegex(ValueError, 'observation_did_not_replay'):
                await rl.verify(job, receipt['initial_state'], receipt['final_state'], tampered)
            tampered = copy.deepcopy(extra)
            tampered['replay_events'][0]['arrival_check']['valid'] = not events[0]['arrival_check']['valid']
            with self.assertRaisesRegex(ValueError, 'arrival_check_did_not_replay'):
                await rl.verify(job, receipt['initial_state'], receipt['final_state'], tampered)


if __name__ == '__main__':
    unittest.main()
