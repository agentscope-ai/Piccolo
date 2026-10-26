"""Shared production Terra map generation/replay regression, no model/GPU calls.

Fixtures are off-policy plumbing evidence, never model capability scores.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / 'blink_arena/engines'), str(PACKAGE)]
import jev_world_core_rl as rl
from jev_world_core import WorldCoreDriver

CORE = PACKAGE / 'web/playground/terraria-core.js'
REVISION = 'terramai-map-v2-diverse'


def node(script, *args):
    result = subprocess.run(['node', '-e', script, str(CORE), *map(str, args)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def assert_public(case, value):
    hidden = {'seed', 'generator_version', 'generator_revision', 'profile',
              'environment_generation', 'surface', 'enemySites', 'caveCount'}
    if isinstance(value, dict):
        case.assertFalse(hidden.intersection(value), hidden.intersection(value))
        for child in value.values():
            assert_public(case, child)
    elif isinstance(value, list):
        for child in value:
            assert_public(case, child)


class TerraSeededCurriculumTests(unittest.IsolatedAsyncioTestCase):
    def test_64_real_maps_unique_deterministic_and_geometry_safe(self):
        result = node(r'''
          const assert=require('node:assert/strict'),core=require(process.argv[1]);
          const seedSource=require(require('node:path').join(require('node:path').dirname(process.argv[1]),'world-seed.js'));
          const worlds=new Set(),surfaces=new Set(),observations=new Set(),counts={};
          let privateUnknown=0;
          const rows=[];
          for(let seed=0;seed<64;seed++){
            const layout=seedSource.terramaiLayout(seed),api=core.create({seed,now:()=>0});
            const snapshot=api.snapshot(),state=api.renderState(),condition=api.condition();
            const tiles=Array.from(state.world),at=(x,y)=>tiles[y*240+x];
            api.reset(seed);assert.deepEqual(api.snapshot(),snapshot);assert.deepEqual(api.renderState(),state);
            assert.equal(tiles.length,240*100);
            assert(tiles.every(t=>Number.isInteger(t)&&t>=0&&t<=15));
            for(let x=0;x<240;x++){assert.equal(at(x,98),11);assert.equal(at(x,99),11);}
            const sx=Math.floor(state.spawn.x/16),ground=state.surf[sx];
            assert.equal(at(sx,ground),2);assert.equal(at(sx+1,ground),2);
            for(let y=ground-5;y<ground;y++){assert.equal(at(sx,y),0);assert.equal(at(sx+1,y),0);}
            assert.equal(at(state.goal.x,state.goal.y),12);assert.equal(at(state.goal.x,state.goal.y-1),12);
            const guardian=state.enemies.filter(e=>e.gateGuardian);
            assert.equal(guardian.length,1);assert.equal(guardian[0].lv,10);assert(guardian[0].hp>0);
            assert.equal(snapshot.objective.gate_unlocked,false);
            for(const p of layout.platforms)for(let x=p.x;x<p.x+p.width;x++)assert.equal(at(x,p.y),2);
            for(let y=0;y<snapshot.map.tiles.length;y++)for(let x=0;x<snapshot.map.tiles[y].length;x++){
              const value=snapshot.map.tiles[y][x],tx=snapshot.map.origin[0]+x,ty=snapshot.map.origin[1]+y;
              if(value!==-1)assert.equal(value,at(tx,ty)); else privateUnknown++;
            }
            worlds.add(JSON.stringify(tiles));surfaces.add(JSON.stringify(state.surf));observations.add(JSON.stringify(snapshot));
            const c={pits:layout.pits.length,platforms:layout.platforms.length,caves:layout.caveCount,
              trees:tiles.filter(t=>t===9).length,ore:tiles.filter(t=>t>=4&&t<=8).length,
              food:state.items.length,chests:state.chests.length,
              ordinary:state.enemies.filter(e=>!e.boss).length};
            for(const [key,value] of Object.entries(c))(counts[key]||(counts[key]=new Set())).add(value);
            rows.push({seed,condition,snapshot,counts:c});
          }
          console.log(JSON.stringify({unique_worlds:worlds.size,unique_surfaces:surfaces.size,
            unique_observations:observations.size,private_unknown:privateUnknown,
            count_values:Object.fromEntries(Object.entries(counts).map(([k,v])=>[k,[...v].sort((a,b)=>a-b)])),rows}));
        ''')
        self.assertEqual(result['unique_worlds'], 64)
        self.assertEqual(result['unique_surfaces'], 64)
        self.assertGreater(result['unique_observations'], 32)
        self.assertGreater(result['private_unknown'], 0)
        self.assertTrue(all(len(values) > 1 for values in result['count_values'].values()))
        for row in result['rows']:
            self.assertEqual(row['condition']['generator_revision'], REVISION)
            assert_public(self, row['snapshot'])
            assert_public(self, rl.get_engine('terraria_survival').observe(row['snapshot']))
        evidence = os.environ.get('JEV_TERRA_SEED_EVIDENCE')
        if evidence:
            output = Path(evidence); output.mkdir(parents=True, exist_ok=True)
            (output / '64-seed-census.json').write_text(json.dumps({
                k: v for k, v in result.items() if k != 'rows'}, indent=2) + '\n')

    def test_legacy_full_state_matches_before_change_baseline(self):
        baseline = os.environ.get('JEV_TERRA_LEGACY_BASELINE')
        if not baseline:
            self.skipTest('set JEV_TERRA_LEGACY_BASELINE to immutable pre-change evidence')
        expected = json.loads(Path(baseline).read_text())
        actual = node(r'''
          const core=require(process.argv[1]),seeds=JSON.parse(process.argv[2]);
          console.log(JSON.stringify(seeds.map(seed=>{
            const api=core.create({seed,now:()=>0,generationOptions:{generator_revision:'world-seed-v1'}});
            return {seed,snapshot:api.snapshot(),render:api.renderState()};
          })));
        ''', json.dumps([row['seed'] for row in expected]))
        self.assertEqual(actual, expected)

    def test_invalid_revision_rejected_before_pending_action_mutates(self):
        result = node(r'''
          const core=require(process.argv[1]),api=core.create({seed:5,now:()=>0});
          api.activate(true);api.prepare({clock:'realtime'});api.act('explore_right');
          const invalid=[[-1,{}],[1.5,{}],[4294967296,{}],['1',{}],
            [1,{generator_revision:'unknown'}],[1,{profile:'easy'}],[1,null],[1,[]]];
          const results=invalid.map(([seed,options])=>{
            const before=JSON.stringify([api.snapshot(),api.renderState(),api.condition()]);
            let rejected=false;try{api.reset(seed,options)}catch(e){rejected=true;}
            return {rejected,unchanged:before===JSON.stringify([api.snapshot(),api.renderState(),api.condition()])};
          });
          api.activate(false);console.log(JSON.stringify(results));
        ''')
        self.assertTrue(all(row['rejected'] and row['unchanged'] for row in result))

    async def test_realtime_short_episodes_strict_replay_new_and_legacy(self):
        records = []
        async def policy(record, episode_id, ordinal):
            assert_public(self, record)
            records.append(copy.deepcopy(record))
            await asyncio.sleep(.09)
            return 'explore_right', {'origin': 'test-controller', 'on_policy': False}
        sampler = SimpleNamespace(policy_action=policy)
        with patch.dict(rl.LIMITS, {'terraria_survival': 2}), patch.dict(
                os.environ, {'JEV_WORLD_REPLAY_MODE': 'strict'}):
            for seed, revision in [(0, None), (31, None), (1014, 'world-seed-v1')]:
                job = {'kind': 'terraria_survival', 'seed': seed, 'episode_id': f'map-v2-fixture-{seed}'}
                if revision:
                    job['generator_revision'] = revision
                initial, final, trace, outcome, extra = await rl.play(sampler, job)
                self.assertEqual(extra['environment_generation']['generator_revision'], revision or REVISION)
                self.assertFalse(extra['inference_world_paused'])
                self.assertGreater(final['frame'], initial['frame'])
                self.assertTrue(all(e['arrival_state']['frame'] > e['before_state']['frame']
                                    for e in extra['replay_events']))
                await rl.verify_with_trace(sampler, job, initial, final, trace, extra)
                if revision:
                    old_extra = copy.deepcopy(extra); old_extra.pop('environment_generation')
                    await rl.verify_with_trace(sampler, job, initial, final, trace, old_extra)
                changed = copy.deepcopy(extra)
                changed['environment_generation']['generator_revision'] = (
                    REVISION if revision else 'world-seed-v1')
                with self.assertRaisesRegex(ValueError, 'initial_did_not_replay|generation'):
                    await rl.verify(job, initial, final, changed)


if __name__ == '__main__':
    unittest.main()
