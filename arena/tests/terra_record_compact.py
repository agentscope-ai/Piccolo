"""Reversible public-record compaction; no model/GPU scores or input rewrites."""
from __future__ import annotations
import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import blink_arena
import jev_gameplay_contract as adapter
from jev_engine_registry import get_engine,list_engines
from jev_control_scope import active_games
from jev_terraria_contract import (
 COMPACT_PROMPT_REVISION,COMPACT_RECORD_FORMAT,LEGACY_PROMPT_REVISION,
 compact_record,expand_record,record_for_revision,_as_record_v18,
)
from jev_world_core import WorldCoreDriver
import jev_world_core_rl as rl

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=Path(__file__).with_name('fixtures')/'terra_compact_public_states.json'
CASES=json.loads(FIXTURE.read_text())['cases']
OUT=Path(os.environ['JEV_TERRA_COMPACT_AUDIT_DIR']) if os.environ.get('JEV_TERRA_COMPACT_AUDIT_DIR') else Path(tempfile.mkdtemp(prefix='jev-terra-compact-v19-'))
HIST=Path(os.environ.get('JEV_CORE_HISTORICAL_TERRA',str(ROOT/'tests/fixtures/historical-terra.json')))

class CompactRecordTests(unittest.TestCase):
 def test_paused_clock_roundtrip_retains_exact_notice_and_rejects_tampering(self):
  from jev_inference_clock import record_for_clock
  job={'inference_world_paused':True}
  old=CASES[0]['legacy_v18_record']
  packed=record_for_clock(compact_record(old),job)
  self.assertEqual(expand_record(packed),record_for_clock(old,job))
  for change in ('notice','marker','missing'):
   broken=copy.deepcopy(packed)
   if change=='notice':broken['questions']['decision']['instructions']+='changed'
   elif change=='marker':broken['state']['sampling_clock']['waiting_advances_world']=True
   else:broken['state'].pop('sampling_clock')
   with self.subTest(change=change),self.assertRaises(ValueError):expand_record(broken)

 def test_real_state_records_expand_exactly_to_frozen_v18_including_candidates(self):
  for case in CASES:
   observation=copy.deepcopy(case['observation']);before=copy.deepcopy(observation)
   old=case['legacy_v18_record'];new=get_engine('terraria_survival').observe(observation)
   self.assertEqual(observation,before)
   self.assertEqual(new['state']['prompt_revision'],COMPACT_PROMPT_REVISION)
   self.assertEqual(new['state']['record_format'],COMPACT_RECORD_FORMAT)
   self.assertEqual(expand_record(new),old)
   self.assertEqual(record_for_revision(observation,LEGACY_PROMPT_REVISION),old)
   self.assertEqual(record_for_revision(observation,COMPACT_PROMPT_REVISION),new)
   self.assertEqual(new['questions']['decision']['option_order'],old['questions']['decision']['option_order'])
   self.assertEqual(set(new['questions']['decision']['criteria']),set(old['questions']['decision']['criteria']))
   self.assertEqual(adapter.adapt_record(copy.deepcopy(old)),old)

 def test_compaction_and_shared_adapter_are_idempotent(self):
  for case in CASES:
   raw=_as_record_v18(case['observation']);raw['state']['prompt_revision']=COMPACT_PROMPT_REVISION
   once=adapter.adapt_record(raw)
   self.assertEqual(adapter.adapt_record(once),once)
   self.assertEqual(compact_record(once),once)
   self.assertEqual(expand_record(expand_record(once)),expand_record(once))

 def test_missing_or_unresolvable_reference_and_invalid_table_fail_closed(self):
  original=compact_record(CASES[0]['legacy_v18_record'])
  for reference in ('/observation/nonexistent','/private_seed','/control/recent_effects'):
   changed=copy.deepcopy(original);changed['state']['control']['recent_effects']={'$ref':reference}
   with self.subTest(reference=reference),self.assertRaises(ValueError):expand_record(changed)
  changed=copy.deepcopy(original);changed['state']['observation']['control']['recent_effects']={'$ref':'/observation/control/recent_effects'}
  with self.assertRaisesRegex(ValueError,'cyclic'):expand_record(changed)
  changed=copy.deepcopy(original);changed['state']['observation']['known_surface_route']['rows'][0].append(9)
  with self.assertRaises(ValueError):expand_record(changed)
  changed=copy.deepcopy(original);changed['questions']['decision']['instructions']+='changed'
  with self.assertRaises(ValueError):expand_record(changed)

 def test_empty_history_is_not_replaced_by_a_longer_reference(self):
  old=copy.deepcopy(CASES[0]['legacy_v18_record'])
  for container,key in ((old['state']['control'],'recent_effects'),(old['state']['observation']['control'],'recent_effects'),(old['state']['navigation'],'recent_actual_effects'),(old['state']['observation'],'last_effects')):container[key]=[]
  changed=compact_record(old)
  self.assertEqual(changed['state']['control']['recent_effects'],[])
  self.assertEqual(changed['state']['navigation']['recent_actual_effects'],[])
  self.assertEqual(expand_record(changed),old)

 def test_route_differing_certainty_and_extra_fields_are_preserved(self):
  for mode in ('certainty','extra'):
   old=copy.deepcopy(CASES[0]['legacy_v18_record']);route=old['state']['observation']['known_surface_route']
   if mode=='certainty':route[0]['certainty']='different observed uncertainty'
   else:route[0]['new_public_field']='keep'
   packed=compact_record(old)
   self.assertIsInstance(packed['state']['observation']['known_surface_route'],list)
   self.assertEqual(expand_record(packed),old)

 def test_source_mirror_compacts_and_expands_the_same_complete_records(self):
  source=ROOT.parent/'CuES-plus'
  if not(source/'src/tools').is_dir():self.skipTest('Standalone package has no legacy source mirror')
  code='''import json,sys
from jev_terraria_contract import compact_record,expand_record
cases=json.load(open(sys.argv[1]))['cases']
for c in cases:assert expand_record(compact_record(c['legacy_v18_record']))==c['legacy_v18_record']
print('source-mirror-roundtrip-ok')'''
  done=subprocess.run([sys.executable,'-c',code,str(FIXTURE)],cwd=source,env={**os.environ,'PYTHONPATH':'src/tools'},text=True,capture_output=True)
  self.assertEqual(done.returncode,0,done.stderr);self.assertIn('roundtrip-ok',done.stdout)

class CompactEngineTests(unittest.IsolatedAsyncioTestCase):
 async def test_other_twenty_live_games_records_are_unchanged(self):
  import importlib.util
  before=Path(os.environ.get('JEV_TERRA_COMPACT_BEFORE_ADAPTER',str(ROOT/'tests/fixtures/pre_compact_gameplay_contract.py')))
  if not before.exists():self.skipTest('Independent pre-change adapter evidence not bundled')
  spec=importlib.util.spec_from_file_location('pre_compact_gameplay_contract',before)
  old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);seen=[]
  for engine in list_engines(include_internal=False):
   if engine.kind=='terraria_survival' or not active_games([engine.kind]):continue
   if engine.family=='world':
    async with WorldCoreDriver(engine.kind,0,replay=True) as driver:state=driver.initial['state']
   else:
    state=engine.reset(42,{'opponent':'rule'} if engine.family=='agent' else None)
    # Sole legal rule steps are mechanical B execution, not test policies.
    for _ in range(32):
     choices=engine.legal_actions(state)
     if len(choices)!=1:break
     state=engine.step(state,next(iter(choices)))
   with patch.object(adapter,'adapt_record',old.adapt_record):expected=engine.observe(copy.deepcopy(state))
   actual=engine.observe(copy.deepcopy(state))
   self.assertEqual(expected,actual,engine.kind);seen.append(engine.kind)
  self.assertEqual(len(seen),20)
  OUT.mkdir(parents=True,exist_ok=True)
  (OUT/'non-terra-20-records.json').write_text(json.dumps({'passed':True,'games':seen,'records_exactly_unchanged':True},indent=2)+'\n')

 async def test_new_compact_play_replays_strictly_and_equivalent_expanded_value_is_rejected(self):
  class Controller:
   async def policy_action(self,record,*args):
    await asyncio.sleep(.05)
    action=next(iter(record['questions']['decision']['criteria']))
    return action,{'origin':'test_controller','on_policy':False}
  job={'kind':'terraria_survival','seed':0,'episode_id':'compact-format-controller-not-model-score'}
  with patch.dict(rl.LIMITS,{'terraria_survival':1}):
   initial,final,trace,outcome,extra=await rl.play(Controller(),job)
  await rl.verify(job,initial,final,extra)
  self.assertEqual(extra['replay_events'][0]['record']['state']['prompt_revision'],COMPACT_PROMPT_REVISION)
  changed=copy.deepcopy(extra);record=changed['replay_events'][0]['record'];good=extra['replay_events'][0]['record']
  self.assertIn('$ref',record['state']['navigation']['objective'])
  record['state']['navigation']['objective']=copy.deepcopy(record['state']['observation']['objective'])
  self.assertEqual(expand_record(record),expand_record(good))
  with self.assertRaisesRegex(ValueError,'observation_did_not_replay'):
   await rl.verify(job,initial,final,changed)
  (OUT/'new-v19-strict-replay.json').write_text(json.dumps({'passed':True,'new_record_revision':COMPACT_PROMPT_REVISION,'semantic_equivalence_does_not_bypass_strict_input_check':True,'frames':final['frame']-initial['frame'],'new_model_calls':0},indent=2)+'\n')

 @unittest.skipUnless(HIST.exists(),'Historical native receipt is not bundled')
 async def test_old_v18_actual_99_event_win_replays_without_changing_original_file(self):
  episode=json.loads(HIST.read_text());stat=HIST.stat()
  await rl.verify({'kind':episode['kind'],'seed':episode['seed']},episode['initial_state'],episode['final_state'],episode)
  self.assertEqual(len(episode['replay_events']),99)
  self.assertEqual(HIST.stat().st_size,stat.st_size);self.assertEqual(HIST.stat().st_mtime_ns,stat.st_mtime_ns)
  self.assertEqual(episode['outcome'],'win')
  (OUT/'historical-v18-99-events.json').write_text(json.dumps({'passed':True,'source':str(HIST),'events':99,'source_bytes':stat.st_size,'source_mtime_ns':stat.st_mtime_ns,'original_inputs_unchanged':True,'new_model_win':False},indent=2)+'\n')

if __name__=='__main__':unittest.main()
