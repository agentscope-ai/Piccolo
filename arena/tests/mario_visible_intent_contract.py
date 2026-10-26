"""Bound target Choices share the frontend/RL contract; no model scores."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

import blink_arena
from jev_mario_contract import as_record, VISIBLE_INTENT_REVISION

ROOT = Path(__file__).resolve().parents[1]
ACTION = 'cross_visible_right:gap:10:12:12:11'


def observation():
    landing = {'column': 12, 'support_row': 11, 'left': 384, 'right': 416, 'top': 352}
    facts = {
        'intent': {'revision': 'visible-crossing-intent-v1',
                   'obstacle': {'kind': 'gap', 'left_col': 10, 'right_col': 12,
                                'left': 320, 'right': 384},
                   'landing_region': landing,
                   'launch_window': {'minimum_x': 272, 'maximum_x': 288,
                                     'selected_x': 278.4, 'approach_frames': 17},
                   'deadline_frames': 300, 'max_wait_frames': 180, 'one_jump': True,
                   'strategy_origin': 'A', 'execution_origin': 'B'},
        'predicted_player': {'x': 392, 'y': 322, 'on_ground': True}, 'landed': True,
        'visible_pit_fall': False, 'plant_or_enemy_risk': False,
        'head_collision': False, 'unknown_terrain': False,
        'certainty': 'visible_geometry; dynamic_risk_is_estimate',
        'continuation': {'prediction_type': 'deterministic_visible_geometry_only',
                         'available': True,
                         'visible_forward_landing_regions': [{**landing, 'left': 512, 'right': 544}],
                         'visible_retreat_landing_regions': [], 'headroom_pixels': 95,
                         'unknown_frontier': True,
                         'dynamic_safety': 'not_estimated; geometry_only_no_enemy_or_plant_guarantee'},
    }
    return {'player': {'x': 224, 'y': 322, 'width': 23, 'height': 30, 'on_ground': True, 'vy': 0},
            'map': {'tile_size': 32, 'origin': [0, 0],
                    'tiles': [[int(row >= 11) for _ in range(30)] for row in range(14)]},
            'candidate_effects': {ACTION: facts}, 'action_execution': {'current_goal': 'flag'},
            'timing': {'clock_contract': 'realtime-v1', 'inference_world_paused': False,
                       'action_frames_by_action': {'right': 12, 'jump_right': 60}}, 'frame': 0}


class VisibleIntentContractTests(unittest.TestCase):
    def test_target_is_one_choice_with_explicit_execution_and_visible_consequences(self):
        state = observation()
        untouched = copy.deepcopy(state)
        record = as_record(state)
        question = record['questions']['decision']
        self.assertEqual(list(record['questions']), ['decision'])
        self.assertEqual(question['type'], 'choice')
        self.assertEqual(question['option_order'], list(question['criteria']))
        self.assertEqual(question['option_order'].count(ACTION), 1)
        self.assertEqual(record['state']['prompt_revision'], VISIBLE_INTENT_REVISION)
        text = question['criteria'][ACTION]
        for fact in ('[320,384]', 'x=[384,416]', '300帧', '180帧', '向前=[[512, 544, 352]]', '退路=[]', '95', '未知边界=True'):
            self.assertIn(fact, text)
        self.assertIn('B执行', record['state']['rules'])
        self.assertIn('不是未来动态安全保证', record['state']['rules'])
        self.assertEqual(state, untouched)

    def test_each_visible_landing_remains_a_distinct_strategy_choice(self):
        state = observation()
        other = ACTION.replace(':12:11', ':13:11')
        state['candidate_effects'][other] = copy.deepcopy(state['candidate_effects'][ACTION])
        state['candidate_effects'][other]['intent']['landing_region'].update(column=13, left=416, right=448)
        question = as_record(state)['questions']['decision']
        self.assertIn(ACTION, question['criteria'])
        self.assertIn(other, question['criteria'])
        self.assertNotEqual(question['criteria'][ACTION], question['criteria'][other])

    def test_required_target_contract_cannot_be_replaced_by_unbound_direction(self):
        state = observation()
        del state['candidate_effects'][ACTION]['intent']['landing_region']
        with self.assertRaises(KeyError):
            as_record(state)

    def test_source_mirror_matches_canonical_record(self):
        path = ROOT.parent / 'CuES-plus/src/tools/jev_mario_contract.py'
        if not path.is_file():
            self.skipTest('Standalone package has no source mirror')
        spec = importlib.util.spec_from_file_location('source_mario_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.as_record(observation()), as_record(observation()))

    def test_legacy_observation_unchanged_when_frozen_contract_provided(self):
        path = os.environ.get('JEV_MARIO_PRE_INTENT_CONTRACT')
        if not path:
            self.skipTest('Set frozen pre-intent contract for legacy equality check')
        spec = importlib.util.spec_from_file_location('legacy_mario_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        state = observation()
        state['candidate_effects'] = {}
        self.assertEqual(as_record(state), module.as_record(state))

    def test_node_and_browser_arrival_bind_same_target_and_reject_remapping(self):
        code = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=process.argv[1],api=require(path),observed=JSON.parse(fs.readFileSync(0,'utf8'));
const action=Object.keys(observed.candidate_effects)[0];
const browser={};vm.runInNewContext(fs.readFileSync(path,'utf8'),browser);
function check(state){const a=api.check('mario_platformer',action,observed,state);
  assert.deepEqual(JSON.parse(JSON.stringify(browser.JevWorldArrival.check('mario_platformer',action,observed,state))),a);return a;}
assert.equal(check(structuredClone(observed)).valid,true);
const moved=structuredClone(observed);moved.candidate_effects[action].intent.launch_window.selected_x+=3.2;
assert.equal(check(moved).valid,true);
const changed=structuredClone(observed);changed.candidate_effects[action].intent.landing_region.left+=1;
assert.equal(check(changed).reason,'action_target_changed');
const removed=structuredClone(observed);delete removed.candidate_effects[action];
assert.equal(check(removed).valid,false);
const forged=structuredClone(observed);forged.candidate_effects[action].intent.landing_region.column=13;
assert.equal(check(forged).reason,'action_target_unavailable');
const danger=structuredClone(observed);danger.candidate_effects[action].plant_or_enemy_risk=true;
assert.equal(check(danger).reason,'visible_danger_changed');
assert.equal(api.check('mario_platformer','right',observed,structuredClone(observed)).valid,true);
assert.equal(api.check('mario_platformer',action,null,observed).valid,false);
console.log(JSON.stringify({passed:true,cases:8,browser_node_same:true}));
'''
        result = subprocess.run(['node', '-e', code, str(ROOT / 'web/playground/world-arrival.js')],
                                input=json.dumps(observation()), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['browser_node_same'])


if __name__ == '__main__':
    unittest.main()
