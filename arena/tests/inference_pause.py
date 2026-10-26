"""The fallback pauses inference only, with exact replay and honest clocks."""
import asyncio
import copy
import unittest
from unittest.mock import patch

import blink_arena
import jev_snake_rl as snake
import jev_tetris_rl as tetris
import jev_world_core_rl as world
from jev_world_core import WorldCoreDriver


class Teacher:
    async def policy_action(self, record, episode_id, ordinal):
        await asyncio.sleep(.12)
        options = record['questions']['decision']['criteria']
        action = 'wait' if 'wait' in options else next(iter(options))
        return action, {'origin': 'test_controller', 'forced': False}


class PauseTests(unittest.IsolatedAsyncioTestCase):
    async def test_longer_request_budget_is_paused_only_and_strictly_replayable(self):
        for kind, runner in (('snake_navigation', snake), ('tetris_placement', tetris)):
            for is_paused in (False, True):
                with self.subTest(kind=kind, paused=is_paused):
                    job={'kind':kind,'seed':18,'episode_id':'slow-budget',
                         'inference_world_paused':is_paused,'paused_policy_timeout_seconds':.5,
                         'max_decisions':1}
                    with patch.object(runner,'MODEL_TIMEOUT_SECONDS',.02), patch.object(snake.game,'LIMIT',1):
                        initial,final,trace,outcome,extra=await runner.play(Teacher(),job)
                        runner.verify(job,initial,final,extra)
                    if is_paused:
                        self.assertTrue(trace)
                        self.assertNotEqual(extra['status'],'timeout')
                        event=extra['replay_events'][0]
                        self.assertEqual(event['waiting_seconds'],0)
                        self.assertEqual(event['before_state'],event['arrival_state'])
                    else:
                        self.assertEqual(extra['status'],'timeout')
                        self.assertFalse(trace)

    async def test_paused_request_budget_rejects_unbounded_values(self):
        from jev_inference_clock import policy_timeout
        self.assertEqual(policy_timeout({'inference_world_paused':True},90),90)
        for value in (None,True,0,-1,float('inf'),float('nan'),3601):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy_timeout({'inference_world_paused':True,'paused_policy_timeout_seconds':value},90)

    async def test_shared_cores_freeze_wait_but_execute_and_strictly_replay(self):
        for kind in ('mario_platformer', 'terraria_survival'):
            with self.subTest(kind=kind):
                job = {'kind':kind, 'seed':0, 'episode_id':'paused-'+kind, 'inference_world_paused':True}
                with patch.dict(world.LIMITS, {kind:2}):
                    initial, final, trace, outcome, extra = await world.play(Teacher(), job)
                await world.verify_with_trace(Teacher(), job, initial, final, trace, extra)
                self.assertTrue(extra['replay_validation']['strict_match'])
                self.assertGreater(final['frame'], initial['frame'])
                self.assertTrue(extra['inference_world_paused'])
                for event in extra['replay_events']:
                    self.assertEqual(event['before_state']['frame'], event['arrival_state']['frame'])
                    self.assertEqual(event['waiting_seconds'], 0)
                    self.assertGreater(event['wall_waiting_seconds'], .1)
                    self.assertEqual(event['record']['state']['sampling_clock']['mode'], 'inference_paused')
                with self.assertRaisesRegex(ValueError, 'clock'):
                    await world.verify({**job,'inference_world_paused':False}, initial, final, extra)

    async def test_python_wait_freezes_and_execution_keeps_gravity_movement(self):
        for kind, runner in (('snake_navigation', snake), ('tetris_placement', tetris)):
            with self.subTest(kind=kind):
                job = {'kind':kind, 'seed':18, 'episode_id':'paused-'+kind,
                       'inference_world_paused':True, 'max_decisions':1}
                with patch.object(snake.game, 'LIMIT', 3):
                    initial, final, trace, outcome, extra = await runner.play(Teacher(), job)
                    runner.verify(job, initial, final, extra)
                    self.assertGreater(final['steps'], initial['steps'])
                    self.assertGreater(final['elapsed'], initial['elapsed'])
                    for event in extra['replay_events']:
                        if event.get('no_request'): continue
                        self.assertEqual(event['before_state'], event['arrival_state'])
                        self.assertEqual(event['waiting_seconds'], 0)
                        self.assertGreater(event['wall_waiting_seconds'], .1)
                    forged = copy.deepcopy(extra)
                    forged['replay_events'][0]['waiting_seconds'] = 1.
                    with self.assertRaisesRegex(ValueError, 'paused'):
                        runner.verify(job, initial, final, forged)

    async def test_default_world_clock_still_advances_while_waiting(self):
        for kind in ('mario_platformer','terraria_survival'):
            async with WorldCoreDriver(kind, 0) as driver:
                before = (await driver.capture())['state']
                await asyncio.sleep(.16)
                after = (await driver.capture())['state']
                self.assertGreater(after['frame'], before['frame'])


if __name__ == '__main__': unittest.main()
