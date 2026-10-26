"""Real CPU worker/receipt boundary checks for the new control revision."""
import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import blink_arena
from jev_world_core import WorldCoreDriver
from jev_world_realtime_rl import rebuild_credit
import jev_world_core_rl as rl
from blink_arena.rollouts import Rollouts

class ControlRPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_guard_strictly_replays_and_input_is_exact(self):
        class Controller:
            seen=[]
            async def policy_action(self, record, episode_id, ordinal):
                self.seen.append(copy.deepcopy(record))
                await asyncio.sleep(.1)
                action='cross_right_guard' if ordinal==0 else 'wait'
                self.assert_choice = action in record['questions']['decision']['criteria']
                return action, {'origin':'offline_test_controller', 'on_policy':False}
        controller=Controller();job={'kind':'mario_platformer','seed':0,'episode_id':'guard-rpc-regression'}
        from jev_engine_rollout_backend import RolloutBackend,PolicyBridge
        cpu_backend=RolloutBackend(lambda *_:None)
        self.addAsyncCleanup(cpu_backend.close)
        controller.compute_record=PolicyBridge(cpu_backend,None).compute_record
        with patch.dict(rl.LIMITS,{'mario_platformer':2}):
            initial,final,trace,outcome,extra=await rl.play(controller,job)
        await rl.verify_with_trace(controller,job,initial,final,trace,extra)
        self.assertEqual([e['record'] for e in extra['replay_events']],controller.seen)
        self.assertTrue(all(e['latency_breakdown']['record_cpu_seconds']>=0 for e in extra['replay_events']))
        self.assertTrue(any(e['action']=='cross_right_guard' for e in trace))
        guarded_records=[record for record in controller.seen if (record['state']['observation']['action_execution'].get('landing_guard') or {}).get('status')=='active']
        self.assertTrue(guarded_records)
        for record in guarded_records:
            self.assertEqual(record['state']['control']['subgoal'],'cross_right_guard')
            self.assertEqual(record['state']['control']['status'],'defending_while_awaiting_model')
            self.assertGreater(record['state']['control']['deadline'],0)
            self.assertEqual(record['state']['control']['fallback_actions'],0)
        for row in trace:
            self.assertEqual(row['control_ownership']['model_intent'],row['action'])
            self.assertTrue(row['control_ownership']['terminal_cost_preserved'])
            self.assertEqual(row['control_ownership']['credit_total_frames'],row['credit_after_state']['frame']-row['credit_before_state']['frame'])

    async def test_tetris_control_ownership_survives_durable_backend_receipt(self):
        directory=Path(tempfile.mkdtemp(prefix='jev-tetris-latency-receipt-'))
        host=Rollouts(directory,'http://must-not-be-requested.invalid',decision_timeout=5.)
        try:
            created=await host.start({'episode_id':'tetris-credit-regression','game':'tetris_placement','seed':18,'policy_version':'cpu-test-controller','request_token':'start','max_decisions':1})
            ident=created['rollout_id']
            ticket=(await host.next_decision(ident,timeout=8.))['ticket'];self.assertIsNotNone(ticket)
            values=ticket['candidate_values'];action='0:0';index=values.index(action)
            answer={'ticket_id':ticket['ticket_id'],'request_token':ticket['request_token'],'policy_version':ticket['policy_version'],'action':action,'policy':{'candidate_values':values,'selected_index':index,'old_probabilities':[1/len(values)]*len(values)}}
            self.assertTrue((await host.answer(ident,answer))['accepted'])
            await asyncio.wait_for(host.backend.sessions[ident].task,15.)
            receipt=await host.result(ident)
            self.assertEqual(receipt['status'],'complete',receipt.get('error_type'))
            self.assertTrue(receipt['replay_verified'])
            self.assertEqual(receipt['trace'][0]['record'],ticket['record'])
            self.assertEqual(receipt['trace'][0]['control_ownership']['owner_piece_id'],1)
            self.assertEqual(receipt['trace'][0]['control_ownership']['controlled_piece_locks'],1)
            self.assertTrue(receipt['trace'][0]['control_ownership']['terminal_cost_preserved'])
            self.assertGreaterEqual(receipt['trace'][0]['latency_breakdown']['record_cpu_seconds'],0)
            self.assertEqual(receipt['backend_timing']['revision'],'jev.backend-latency.v1')
            self.assertTrue(any(r['event']=='policy_answer' for r in receipt['backend_timing']['journal_writes']))
        finally:await host.close()

if __name__=='__main__':unittest.main()
