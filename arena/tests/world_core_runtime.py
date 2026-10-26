"""Real Node RPC / RL integration; controller tests, never model scores.

Runs the exact shared engines without HTML, DOM, Playwright, HTTP, model or GPU.
Historical replay reads immutable receipt/journal files and never rewrites them.
"""
from __future__ import annotations
import asyncio
import copy
import json
import os
import tempfile
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import blink_arena
from jev_engine_registry import get_engine
from jev_gameplay_reward_contract import default_config, settle_episode, terminal_objective, validate_episode
from jev_realtime_scoring import score_episode
from jev_world_core import WorldCoreDriver, asset_directory
import jev_world_core_rl as rl

EVIDENCE=Path(os.environ.get('JEV_CORE_TEST_EVIDENCE', str(Path(tempfile.gettempdir()) / 'jev-core-tests'))) / 'integration'
HISTORICAL=Path(os.environ.get('JEV_CORE_HISTORICAL_MARIO', str(Path(__file__).parent / 'fixtures' / 'historical-mario.json')))
KINDS=('mario_platformer','terraria_survival')

class Controller:
    """Explicitly off-policy deterministic legal choices for plumbing checks."""
    args=SimpleNamespace(frontend='http://must-not-be-requested.invalid')
    def __init__(self):self.seen=[];self.journals=[]
    @property
    def browser(self):raise AssertionError('RL must not use a browser')
    async def policy_action(self,record,episode_id,ordinal):
        await asyncio.sleep(.09)
        options=record['questions']['decision']['criteria']
        action='wait' if 'wait' in options else next(iter(options))
        self.seen.append(copy.deepcopy(record))
        return action,{'origin':'test_controller','on_policy':False,'probabilities':{k:1/len(options) for k in options}}
    def journal(self,job,event,value):self.journals.append((event,copy.deepcopy(value)))

class CoreRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):EVIDENCE.mkdir(parents=True,exist_ok=True)

    async def test_visible_intent_zero_frame_abort_replays_without_extra_physics(self):
        script=[(0,154,194,'cross_right'),(195,256,281,'cross_right'),
                (282,346,431,'cross_visible_right:gap:14:17:17:11'),
                (432,498,509,'cross_visible_right:pipe:25:27:25:9')]
        async with WorldCoreDriver('mario_platformer',2480010158,replay=True,
                options={'generator_revision':'mario-map-v2-curriculum'}) as driver:
            for before,arrival,after,action in script:
                observed=await driver.call('replayObserve',frame=before)
                result=await driver.call('replayEvent',event={'before_state':observed,
                    'arrival_state':{'frame':arrival},'after_state':{'frame':after,
                    'action_execution':{'remaining_frames':0}},'action':action})
                self.assertTrue(result['verdict']['valid'])
                self.assertEqual(result['after']['frame'],after)
            state=result['after']
            self.assertEqual(state['recent_player_positions'][-1],[579.2,322])
            self.assertEqual(state['action_execution']['status'],'idle')
            self.assertEqual(state['action_execution']['recent_effects'][-1]['failure_reason'],
                             'visible_danger_on_selected_approach')

        # A genuinely unfinished action cannot be forced to complete at an
        # earlier frame merely by claiming that its execution is finished.
        async with WorldCoreDriver('mario_platformer',2480010158,replay=True,
                options={'generator_revision':'mario-map-v2-curriculum'}) as driver:
            observed=await driver.call('replayObserve',frame=0)
            with self.assertRaisesRegex(RuntimeError,'requires_physics'):
                await driver.call('replayEvent',event={'before_state':observed,
                    'arrival_state':{'frame':154},'after_state':{'frame':160,
                    'action_execution':{'remaining_frames':0}},'action':'cross_right'})

    async def short_episode(self,kind):
        job={'kind':kind,'seed':0,'episode_id':'core-integration-'+kind}
        sampler=Controller()
        with patch.dict(rl.LIMITS,{kind:2}),patch('playwright.async_api.async_playwright',side_effect=AssertionError('browser forbidden')),patch('socket.create_connection',side_effect=AssertionError('HTTP forbidden')):
            result=await rl.play(sampler,job)
            await rl.verify_with_trace(sampler,job,*result[:3],result[4])
        return sampler,job,result

    async def test_true_node_play_full_replay_both_games_and_inference_wait(self):
        reports=[]
        for kind in KINDS:
            with self.subTest(kind=kind):
                sampler,job,(initial,final,trace,outcome,extra)=await self.short_episode(kind)
                self.assertEqual(get_engine(kind).backend,'worker')
                self.assertEqual(extra['engine_runtime'],'jev.shared-core.node.v1')
                self.assertTrue(extra['replay_events'])
                self.assertGreater(final['frame'],initial['frame'])
                self.assertEqual(outcome,'budget_exhausted')
                self.assertFalse(extra['inference_world_paused'])
                self.assertEqual(len(sampler.seen),2)
                self.assertEqual(len(trace),sum(e['action_applied'] for e in extra['replay_events']))
                for e in extra['replay_events']:
                    self.assertGreater(e['arrival_state']['frame'],e['before_state']['frame'])
                    self.assertGreater(e['waiting_seconds'],.07)
                    self.assertEqual(e['record'],sampler.seen[e['ordinal']])
                    self.assertEqual(e['policy']['origin'],'test_controller')
                reports.append({'kind':kind,'seed':0,'frames':final['frame']-initial['frame'],'events':len(extra['replay_events']),'verified':True,'teacher_calls':0,'model_score':False})
        (EVIDENCE/'real-node-play-verify.json').write_text(json.dumps(reports,indent=2)+'\n')

    async def test_replay_rejects_frame_model_input_arrival_verdict_and_reward_credit_tampering(self):
        kind=KINDS[0];sampler,job,(initial,final,trace,outcome,extra)=await self.short_episode(kind)
        mutations=[]
        x=copy.deepcopy(extra);x['replay_events'][0]['after_state']['frame']+=1;mutations.append(('frame',x))
        x=copy.deepcopy(extra);x['replay_events'][0]['record']['state']['observation']['player']['x']+=1;mutations.append(('model_input',x))
        x=copy.deepcopy(extra);x['replay_events'][0]['arrival_check']['valid']=False;mutations.append(('arrival',x))
        for name,x in mutations:
            with self.subTest(tampering=name),self.assertRaises((ValueError,RuntimeError)):
                await rl.verify(job,initial,final,x)
        changed=copy.deepcopy(trace);changed[0]['credit_after_state']['player']['x']+=1
        with self.assertRaisesRegex(ValueError,'credit'):
            await rl.verify_with_trace(sampler,job,initial,final,changed,extra)
        score=score_episode(kind,final,outcome,elapsed_seconds=extra['real_time_seconds'])
        rewards=settle_episode(kind,initial,trace,terminal_objective(kind,outcome,score),default_config([kind]),final_state=final)
        episode={'kind':kind,'initial_state':initial,'final_state':final,'trace':trace,'outcome':outcome,'realtime_score':score,'real_time_seconds':extra['real_time_seconds'],**rewards}
        validate_episode(episode,default_config([kind]))
        episode['process_rewards'][0]+=.1
        with self.assertRaisesRegex(ValueError,'reward contract'):
            validate_episode(episode,default_config([kind]))
        (EVIDENCE/'tamper-tests.json').write_text(json.dumps({'passed':True,'rejected':['frame','model_input','arrival_verdict','executed_credit','reward_value']},indent=2)+'\n')

    async def test_same_seed_reproducible_and_stale_jump_rejected_without_substitute(self):
        for kind in KINDS:
            async with WorldCoreDriver(kind,3,replay=True) as first,WorldCoreDriver(kind,3,replay=True) as second:
                self.assertEqual(first.initial['state'],second.initial['state'])
                for frame in (20,40,120):
                    a=await first.call('replayObserve',frame=frame);b=await second.call('replayObserve',frame=frame)
                    self.assertEqual(a,b)
        async with WorldCoreDriver('mario_platformer',3,replay=True) as driver:
            observed=(await driver.capture())['state']
            event={'action':'jump','before_state':observed,'arrival_state':{'frame':observed['frame']},'after_state':{'frame':observed['frame']+10}}
            result=await driver.call('replayEvent',event=event)
            self.assertFalse(result['after']['player']['on_ground'])
            decisions=result['after']['decisions']
            rejected=await driver.call('commit',action='jump_right',observed=observed)
            self.assertEqual(rejected['reason'],'jump_state_changed')
            self.assertEqual(rejected['after_state']['decisions'],decisions)
            feedback=rejected['after_state']['decision_arrival']['recent_rejections'][-1]
            self.assertIsNone(feedback['automatic_action'])
            self.assertEqual(feedback['rule_takeover_actions'],0)
            self.assertFalse(feedback['action_applied'])

    async def test_runtime_starts_from_js_only_assets_with_browser_and_network_forbidden(self):
        target=EVIDENCE/('js-only-assets-'+str(time.time_ns()));target.mkdir()
        for name in ('world-core-worker.cjs','world-seed.js','world-arrival.js','mario-core.js','terraria-core.js'):
            shutil.copyfile(asset_directory()/name,target/name)
        (target/'deny-network.cjs').write_text("for(const name of ['node:http','node:https'])require(name).request=()=>{throw Error('network forbidden')};require('node:net').Socket.prototype.connect=function(){throw Error('network forbidden')};\n")
        self.assertFalse(list(target.glob('*.html')))
        with patch.dict('os.environ',{'NODE_OPTIONS':'--require='+str(target/'deny-network.cjs')}),patch('playwright.async_api.async_playwright',side_effect=AssertionError('browser forbidden')),patch('socket.create_connection',side_effect=AssertionError('network forbidden')):
            for kind in KINDS:
                async with WorldCoreDriver(kind,0,assets=target) as driver:
                    before=(await driver.capture())['state'];await asyncio.sleep(.16);after=(await driver.capture())['state']
                    self.assertGreater(after['frame'],before['frame'])

    async def test_timeout_kills_worker_and_cannot_consume_stale_reply(self):
        driver=WorldCoreDriver('mario_platformer',0,replay=True)
        try:
            state=(await driver.start())['state'];process=driver.process
            # An act in replay mode waits for explicit frames; no scheduler runs.
            with self.assertRaises(TimeoutError):
                await driver.call('commit',action='wait',observed=state,timeout=.03)
            await asyncio.wait_for(process.wait(),2)
            with self.assertRaisesRegex(RuntimeError,'not_running'):
                await driver.call('capture')
        finally:await driver.close()
        self.assertIsNotNone(process.returncode)
        self.assertIsNone(driver.process)

    async def test_cancelled_operation_cleans_child_process(self):
        driver=WorldCoreDriver('mario_platformer',0,replay=True)
        try:
            state=(await driver.start())['state'];process=driver.process
            task=asyncio.create_task(driver.call('commit',action='wait',observed=state))
            await asyncio.sleep(.03);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        finally:await driver.close()
        self.assertIsNotNone(process.returncode)
        self.assertIsNone(driver.process)


    async def test_full_backend_ticket_runner_reward_and_durable_receipt_both_games(self):
        from blink_arena.rollouts import Rollouts
        reports=[]
        for kind in KINDS:
            directory=EVIDENCE/('ticket-backend-'+kind+'-'+str(time.time_ns()))
            host=Rollouts(directory,'http://must-not-be-requested.invalid',decision_timeout=5.)
            tickets=[]
            try:
                with patch.dict(rl.LIMITS,{kind:2}),patch.object(host,'_browser',side_effect=AssertionError('browser forbidden')):
                    created=await host.start({'episode_id':'controller-test-'+kind,'game':kind,'seed':0,'policy_version':'test-controller-not-training','request_token':'test-start','max_decisions':2})
                    ident=created['rollout_id'];sequence=-1
                    for _ in range(2):
                        ticket=(await host.next_decision(ident,after=sequence,timeout=8.))['ticket']
                        self.assertIsNotNone(ticket)
                        tickets.append(ticket);sequence=ticket['sequence'];values=ticket['candidate_values']
                        action='wait' if 'wait' in values else 'recover' if 'recover' in values else values[0]
                        self.assertFalse(ticket['inference_pauses_environment'])
                        await asyncio.sleep(.09)
                        answer={'ticket_id':ticket['ticket_id'],'request_token':ticket['request_token'],'policy_version':ticket['policy_version'],'action':action,'policy':{'candidate_values':values,'selected_index':values.index(action),'old_probabilities':[1/len(values)]*len(values)}}
                        self.assertTrue((await host.answer(ident,answer))['accepted'])
                    await asyncio.wait_for(host.backend.sessions[ident].task,12.)
                    receipt=await host.result(ident)
                    self.assertEqual(receipt['status'],'complete',receipt.get('error_type'))
                    self.assertTrue(receipt['replay_verified'])
                    self.assertTrue(receipt['counts_in_denominator'])
                    self.assertEqual(receipt['engine_runtime'],'jev.shared-core.node.v1')
                    self.assertEqual(receipt['engine']['backend'],'worker')
                    self.assertTrue(receipt['replay_validation']['verified'])
                    self.assertEqual(receipt['replay_validation']['mode'],
                                     os.environ.get('JEV_WORLD_REPLAY_MODE', 'strict'))
                    self.assertEqual(receipt['replay_validation']['relaxed_count'], 0)
                    self.assertEqual(receipt['rule_takeover_count'],0)
                    self.assertEqual(len(receipt['trace']),2)
                    self.assertEqual(len(receipt['process_rewards']),2)
                    for row,ticket in zip(receipt['trace'],tickets):
                        self.assertEqual(row['record'],ticket['record'])
                        self.assertEqual(row['policy']['candidate_values'],ticket['candidate_values'])
                        self.assertEqual(row['action'],ticket['candidate_values'][row['policy']['selected_index']])
                    validate_episode(receipt,default_config([kind]))
                    persisted=json.loads((directory/'episodes'/f'{ident}.json').read_text())
                    self.assertEqual(receipt,persisted)
                    self.assertIsNone(host.browser);self.assertIsNone(host.playwright)
                    reports.append({'kind':kind,'tickets':2,'receipt_complete':True,'replay_verified':True,'reward_recomputed':True,'policy_inputs_preserved':True,'test_only':True,'real_model_calls':0,'training_enqueued':False,'directory':str(directory)})
            finally:await host.close()
        (EVIDENCE/'full-ticket-backend.json').write_text(json.dumps(reports,indent=2)+'\n')

    @unittest.skipUnless(HISTORICAL.is_file(),'Historical N6 receipt is not bundled in portable package')
    async def test_historical_actual_mario_win_exact_full_replay_and_reward(self):
        receipt=json.loads(HISTORICAL.read_text());stat=HISTORICAL.stat()
        journal=HISTORICAL.parent.parent/'journals'/f"{receipt['rollout_id']}.jsonl"
        with journal.open() as source:
            events=[json.loads(line)['value'] for line in source if json.loads(line)['event']=='executed_realtime']
        extra={**receipt,'replay_events':events}
        await rl.verify({'kind':receipt['kind'],'seed':receipt['seed']},receipt['initial_state'],receipt['final_state'],extra)
        validate_episode(receipt,default_config([receipt['kind']]))
        self.assertEqual(receipt['outcome'],'win');self.assertEqual(len(events),25)
        self.assertEqual(HISTORICAL.stat().st_size,stat.st_size)
        self.assertEqual(HISTORICAL.stat().st_mtime_ns,stat.st_mtime_ns)

if __name__=='__main__':unittest.main()
