"""Actual browser curriculum/legacy replay checks; zero model/API/GPU calls.

Test-controller episodes are deliberately off-policy and never model scores.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / 'blink_arena/engines'), str(PACKAGE)]
from tests import world_arrival as arrival
import jev_world_realtime_rl as world


class MarioCurriculumTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = arrival.ArrivalTests.asyncSetUp
    asyncTearDown = arrival.ArrivalTests.asyncTearDown
    page = arrival.ArrivalTests.page

    def assert_public(self, value):
        hidden = {'seed', 'condition_seed', 'generator_version', 'generator_revision',
                  'profile', 'environment_generation', 'mushrooms', 'pitWidths',
                  'brickLengths', 'plantOffsets', 'patrols', 'pits'}
        if isinstance(value, dict):
            self.assertFalse(hidden.intersection(value), hidden.intersection(value))
            for child in value.values():
                self.assert_public(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_public(child)

    async def test_real_maps_consume_lengths_counts_and_keep_observations_local(self):
        page = await self.page()
        cases = await page.evaluate('''()=>{
          JevMario.activate(false);
          return Array.from({length:32},(_,seed)=>{
            const layout=JevWorldSeed.marioLayout(seed),snapshot=JevMario.reset(seed);
            const state=JevMario.inspectWorld(),condition=JevMario.condition();
            const again=JevMario.reset(seed);
            return {seed,layout,snapshot,state,condition,
              deterministic:JSON.stringify(snapshot)===JSON.stringify(again)&&
                JSON.stringify(state)===JSON.stringify(JevMario.inspectWorld())};
          });
        }''')
        geometries = set()
        counts = {k: set() for k in ('width', 'pits', 'pipes', 'patrols', 'mushrooms', 'brickLengths')}
        for case in cases:
            with self.subTest(seed=case['seed']):
                layout, state, snapshot = case['layout'], case['state'], case['snapshot']
                self.assertTrue(case['deterministic'])
                expected = [[0] * layout['width'] for _ in range(14)]
                for x in range(layout['width']):
                    for y in range(11, 14):
                        expected[y][x] = 1
                for x, length in zip(layout['pits'], layout['pitWidths']):
                    for dx in range(length):
                        for y in range(11, 14):
                            expected[y][x+dx] = 0
                for x in layout['pipes']:
                    for dx in range(2):
                        for y in (9, 10):
                            expected[y][x+dx] = 3
                for x, length in zip(layout['bricks'], layout['brickLengths']):
                    for dx in range(length):
                        expected[7][x+dx] = 4 if dx == 1 else 2
                self.assertEqual(state['tiles'], expected)
                self.assertEqual(state['mushrooms'], layout['mushrooms'])
                self.assertEqual([[e['x']//32, e['min']//32, e['max']//32]
                                  for e in state['enemies']], layout['patrols'])
                self.assertEqual([p['offset'] for p in state['plants']], layout['plantOffsets'])
                self.assertEqual(snapshot['goal_x'], layout['goalColumn']*32)
                self.assertEqual(case['condition']['profile'], layout['profile'])
                self.assertEqual(case['condition']['generator_revision'], 'mario-map-v2-curriculum')
                visible_width = len(snapshot['map']['tiles'][0])
                self.assertLess(visible_width, layout['width'])
                self.assertEqual(snapshot['map']['tiles'], [row[:visible_width] for row in expected])
                self.assert_public(snapshot)
                self.assert_public(world.get_engine('mario_platformer').observe(snapshot))
                geometries.add(json.dumps(state, sort_keys=True))
                for name in counts:
                    counts[name].add(layout[name] if name == 'width' else
                                     tuple(layout[name]) if name == 'brickLengths' else len(layout[name]))
        self.assertEqual(len(geometries), 32)
        self.assertTrue(all(len(values) > 1 for values in counts.values()))

    async def test_explicit_v1_and_legacy_profile_are_identical_real_worlds(self):
        page = await self.page()
        result = await page.evaluate('''()=>{
          JevMario.activate(false);
          return [3,7,11,15,19,23,27,31,4294967295].map(seed=>{
            const current=JevMario.reset(seed),a=JevMario.inspectWorld();
            const old=JevMario.reset(seed,{generator_revision:'world-seed-v1'}),b=JevMario.inspectWorld();
            return {seed,current,old,a,b,condition:JevMario.condition()};
          });
        }''')
        for case in result:
            with self.subTest(seed=case['seed']):
                self.assertEqual(case['current'], case['old'])
                self.assertEqual(case['a'], case['b'])
                self.assertEqual(len(case['b']['tiles'][0]), 96)
                self.assertEqual(case['old']['goal_x'], 91*32)
                self.assertEqual(case['condition']['generator_revision'], 'world-seed-v1')

    async def test_invalid_reset_preserves_pending_action_and_condition(self):
        page = await self.page()
        result = await page.evaluate('''()=>{
          const api=JevMario;api.reset(0);api.activate(true);api.prepare({clock:'realtime'});
          const pending=api.act('cross_right');
          const invalid=[[-1,{}],[.5,{}],[4294967296,{}],['0',{}],
            [1,{generator_revision:'unknown'}],[1,{profile:'easy'}],[1,null],[1,[]]];
          const results=invalid.map(([seed,options])=>{
            const before=JSON.stringify([api.snapshot(),api.inspectWorld(),api.condition()]);
            let rejected=false;try{api.reset(seed,options)}catch(e){rejected=true}
            return {rejected,unchanged:before===JSON.stringify([api.snapshot(),api.inspectWorld(),api.condition()]),
              selected:api.snapshot().action_execution.selected_intent};
          });
          api.activate(false);return results;
        }''')
        self.assertEqual(len(result), 8)
        self.assertTrue(all(r['rejected'] and r['unchanged'] for r in result))
        self.assertTrue(all(r['selected'] == 'cross_right' for r in result))

    async def test_realtime_play_replay_all_profiles_and_v1_fallback(self):
        async def policy(record, episode_id, ordinal):
            self.assert_public(record)
            await asyncio.sleep(.12)
            return ('right' if ordinal == 0 else 'wait'), {'origin': 'test-controller', 'on_policy': False}
        sampler = SimpleNamespace(browser=self.browser, args=SimpleNamespace(frontend=self.url), policy_action=policy)
        previous = world.LIMITS.get('mario_platformer')
        world.LIMITS['mario_platformer'] = 2
        try:
            for seed, revision in [(0, None), (1, None), (2, None), (3, None), (0, 'world-seed-v1')]:
                with self.subTest(seed=seed, revision=revision):
                    job = {'kind': 'mario_platformer', 'seed': seed, 'episode_id': f'curriculum-fixture-{seed}-{revision}'}
                    if revision:
                        job['generator_revision'] = revision
                    initial, final, trace, outcome, extra = await world.play(sampler, job)
                    self.assertEqual(len(trace), 2)
                    self.assertEqual(outcome, 'budget_exhausted')
                    self.assertTrue(all(e['arrival_state']['frame'] > e['before_state']['frame']
                                        for e in extra['replay_events']))
                    self.assertFalse(extra['inference_world_paused'])
                    self.assertEqual(extra['environment_generation'], {
                        'seed': seed, 'generator_revision': revision or 'mario-map-v2-curriculum',
                        'profile': 'legacy' if revision else ['easy', 'medium', 'hard', 'legacy'][seed]})
                    self.assertTrue(all(not t['policy']['on_policy'] for t in trace))
                    self.assertEqual(final['action_execution']['rule_takeover_count'], 0)
                    await world.verify(sampler, job, initial, final, extra, trace)
                    changed = copy.deepcopy(extra)
                    changed['environment_generation']['seed'] += 1
                    with self.assertRaisesRegex(ValueError, 'generation_seed_mismatch'):
                        await world.verify(sampler, job, initial, final, changed, trace)
                    if revision:
                        legacy_extra = copy.deepcopy(extra)
                        legacy_extra.pop('environment_generation')
                        await world.verify(sampler, job, initial, final, legacy_extra, trace)
                    elif seed == 0:
                        changed = copy.deepcopy(extra)
                        changed['environment_generation']['profile'] = 'hard'
                        with self.assertRaisesRegex(ValueError, 'generation_did_not_replay'):
                            await world.verify(sampler, job, initial, final, changed, trace)
                        changed = copy.deepcopy(extra)
                        changed.pop('environment_generation')
                        with self.assertRaisesRegex(ValueError, 'initial_did_not_replay'):
                            await world.verify(sampler, job, initial, final, changed, trace)
        finally:
            if previous is None:
                world.LIMITS.pop('mario_platformer')
            else:
                world.LIMITS['mario_platformer'] = previous


if __name__ == '__main__':
    unittest.main()
