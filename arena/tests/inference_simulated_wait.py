"""Synthetic realtime waits keep native hazards, clocks, and replay evidence."""
import asyncio
import copy
import unittest
from unittest.mock import patch

import blink_arena
import jev_snake_rl as snake
import jev_world_core_rl as world
from jev_inference_clock import (wait_seconds, simulated, record_for_clock,
    policy_timeout, observation_for_clock, SIMULATED_REVISION)
from jev_terraria_contract import compact_record, expand_record, _as_record_v18
from jev_world_core import WorldCoreDriver


class Teacher:
    def __init__(self, delay): self.delay = delay
    async def policy_action(self, record, *args):
        await asyncio.sleep(self.delay)
        clock = record['state']['sampling_clock']
        assert clock['mode'] == 'realtime' and clock['waiting_seconds_bounds'] == [2, 4]
        assert 'waiting_seconds' not in clock and 'sampled_frames' not in clock
        options = record['questions']['decision']['criteria']
        return ('wait' if 'wait' in options else next(iter(options))), {'origin': 'test_controller', 'forced': False}


def job(kind, seed=18):
    return {'kind': kind, 'seed': seed, 'episode_id': 'sim-test', 'inference_simulated_wait': True}


class ClockTests(unittest.TestCase):
    def test_wait_is_deterministic_bounded_varied_and_independent_of_wall_latency(self):
        j = job('snake_navigation')
        values = [wait_seconds(j, i, 0) for i in range(500)]
        self.assertTrue(all(2 <= v <= 4 for v in values))
        self.assertGreater(len(set(values)), 100)
        self.assertEqual(values, [wait_seconds(j, i, 300) for i in range(500)])
        self.assertEqual(values, [wait_seconds({**j, 'model': 'different'}, i, .01) for i in range(500)])
        self.assertNotEqual(values, [wait_seconds({**j, 'seed': 19}, i, 0) for i in range(500)])
        self.assertEqual(wait_seconds({}, 0, 7), 7)
        self.assertEqual(wait_seconds({'inference_world_paused': True}, 0, 7), 0)
        self.assertEqual(policy_timeout({**j, 'simulated_policy_timeout_seconds': 900}, 90), 900)

    def test_incompatible_flags_and_unapproved_games_are_rejected(self):
        for j in ({**job('snake_navigation'), 'inference_world_paused': True}, job('tetris_placement'),
                  {**job('snake_navigation'), 'inference_simulated_wait': 'true'}):
            with self.assertRaises(ValueError): simulated(j)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_death_during_virtual_wait_discards_the_late_action(self):
        j = job('snake_navigation')
        with patch.object(snake.game, 'LIMIT', 12):
            initial, final, trace, outcome, extra = await snake.play(Teacher(0), j)
            snake.verify(j, initial, final, extra)
        terminal = extra['replay_events'][-1]
        self.assertEqual(outcome, 'loss')
        self.assertEqual(terminal['reason'], 'game_finished_while_waiting')
        self.assertFalse(terminal['action_applied'])
        self.assertNotIn(terminal['ordinal'], [r['ordinal'] for r in trace])

    async def test_snake_outcome_is_independent_of_actual_response_time(self):
        results = []
        for delay in (.001, .15):
            j = job('snake_navigation')
            with patch.object(snake.game, 'LIMIT', 2):
                initial, final, trace, outcome, extra = await snake.play(Teacher(delay), j)
                snake.verify(j, initial, final, extra)
                broken = copy.deepcopy(extra)
                broken['replay_events'][0]['waiting_seconds'] = 0
                with self.assertRaisesRegex(ValueError, 'simulated'):
                    snake.verify(j, initial, final, broken)
            # Native Snake starts only on its first input; later waits move it.
            self.assertFalse(extra['replay_events'][0]['arrival_state']['started'])
            self.assertGreater(extra['replay_events'][1]['arrival_state']['elapsed'], initial['elapsed'])
            results.append(final)
        self.assertEqual(*results)

    async def test_worlds_advance_native_physics_and_replay_the_same_wait(self):
        for kind in ('mario_platformer', 'terraria_survival'):
            j = job(kind, 0)
            results = []
            for delay in (.001, .15):
                with patch.dict(world.LIMITS, {kind: 2}):
                    initial, final, trace, outcome, extra = await world.play(Teacher(delay), j)
                await world.verify_with_trace(Teacher(0), j, initial, final, trace, extra)
                self.assertTrue(extra['replay_validation']['strict_match'])
                for event in extra['replay_events']:
                    self.assertGreater(event['arrival_state']['frame'], event['before_state']['frame'])
                    self.assertEqual(event['waiting_seconds'], wait_seconds(j, event['ordinal'], 100))
                    self.assertEqual(event['sampling_clock_source'], SIMULATED_REVISION)
                    timing = event['record']['state'].get('observation', {}).get('timing', {})
                    if timing: self.assertFalse(timing['inference_world_paused'])
                bad = copy.deepcopy(extra);bad['replay_events'][0]['waiting_seconds'] = 0
                with self.assertRaisesRegex(ValueError, 'simulated'):
                    await world.verify(j, initial, final, bad)
                results.append(final)
            self.assertEqual(*results, kind)

    async def test_terra_compaction_preserves_public_clock_prior(self):
        j = job('terraria_survival', 0)
        async with WorldCoreDriver(j['kind'], j['seed'], inference_world_paused=True) as driver:
            obs = observation_for_clock(driver.initial['state'], j)
        raw = _as_record_v18(obs)
        self.assertEqual(expand_record(record_for_clock(compact_record(raw), j)), record_for_clock(raw, j))


if __name__ == '__main__': unittest.main()
