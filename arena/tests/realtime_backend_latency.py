"""Real ticket durability, cancellation, immutable CPU work and replay checks."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from jev_engine_rollout_backend import RolloutBackend, PolicyBridge
from tests.rollout_backend_regression import answer_for


class AsyncHotPathTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='jev-latency-test-')
        self.addCleanup(self.folder.cleanup)
        from jev_engine_registry import get_engine
        engine=get_engine('jump_jump')
        self.record=engine.observe(engine.reset(42))
        self.job={'episode_id':'latency-fixture','game':'jump_jump','seed':42,
                  'policy_version':'fixture-v1','request_token':'latency-start'}
        self.applied=[]
        async def runner(proxy,job):
            action,_=await proxy.policy_action(self.record,job['episode_id'],0)
            self.applied.append(action)
            proxy.journal(job,'executed',{'ordinal':0,'action':action})
            return {'status':'error','error_type':'fixture_finished'}
        self.backend=RolloutBackend(runner,storage_dir=self.folder.name,decision_timeout=2.)
        self.addAsyncCleanup(self.backend.close)

    async def wait_thread(self,event):
        for _ in range(100):
            if event.is_set():return
            await asyncio.sleep(.005)
        self.fail('worker did not start')

    async def test_captured_ticket_is_not_exposed_before_durable_write_and_loop_moves(self):
        entered,release=threading.Event(),threading.Event()
        self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='decision_captured':
                entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            ident=(await self.backend.start(self.job))['rollout_id']
            await self.wait_thread(entered)
            started=time.monotonic()
            result=await self.backend.next_decision(ident,timeout=.04)
            self.assertIsNone(result['ticket'])
            self.assertLess(time.monotonic()-started,.2)
            release.set()
            ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
            rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{ident}.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['event']=='decision_captured' and x['value']['ticket_id']==ticket['ticket_id'] for x in rows))

    async def test_cancelled_start_caller_retains_owned_initialization_and_retry(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='started':entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            starting=asyncio.create_task(self.backend.start(self.job))
            await self.wait_thread(entered)
            session=next(iter(self.backend.sessions.values()))
            starting.cancel()
            with self.assertRaises(asyncio.CancelledError):await starting
            retry=asyncio.create_task(self.backend.start(self.job))
            await asyncio.sleep(.02)
            self.assertFalse(retry.done());self.assertFalse(session.initialization_task.done())
            self.assertIsNone(session.task)
            release.set()
            duplicate=await retry
        self.assertTrue(duplicate['duplicate']);self.assertEqual(duplicate['rollout_id'],session.ident)
        self.assertIsNotNone(session.task)
        ticket=(await self.backend.next_decision(session.ident,timeout=1))['ticket']
        self.assertIsNotNone(ticket)
        await self.backend.answer(session.ident,answer_for(ticket))
        await self.backend.next_decision(session.ident,after=0,timeout=1)
        self.assertEqual(len(self.applied),1)
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{session.ident}.jsonl').read_text().splitlines()]
        self.assertEqual(sum(row['event']=='started' for row in rows),1)

    async def test_close_during_started_write_settles_without_entering_runner(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='started':entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            starting=asyncio.create_task(self.backend.start(self.job))
            await self.wait_thread(entered)
            session=next(iter(self.backend.sessions.values()))
            closing=asyncio.create_task(self.backend.close())
            await asyncio.sleep(.03)
            self.assertFalse(closing.done());self.assertIsNone(session.task)
            release.set();await starting;await closing
        self.assertTrue(self.backend._closed);self.assertEqual(session.status,'cancelled')
        self.assertIsNone(session.task);self.assertEqual(self.applied,[])
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{session.ident}.jsonl').read_text().splitlines()]
        self.assertEqual([row['event'] for row in rows],['started'])
        self.assertTrue(session.persisted);self.assertFalse(session.result['on_policy'])

    async def test_cancelled_start_caller_with_failed_durable_write_retains_error(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def failed(ident,row):
            if row['event']=='started':
                entered.set();release.wait(2);raise OSError('fixture startup write failed')
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=failed):
            starting=asyncio.create_task(self.backend.start(self.job))
            await self.wait_thread(entered)
            session=next(iter(self.backend.sessions.values()))
            starting.cancel()
            with self.assertRaises(asyncio.CancelledError):await starting
            release.set()
            duplicate=await self.backend.start(self.job)
        result=await self.backend.result(session.ident)
        self.assertTrue(duplicate['duplicate']);self.assertEqual(result['status'],'error')
        self.assertTrue(result['counts_in_denominator']);self.assertFalse(result['on_policy'])
        self.assertIsNone(session.task);self.assertTrue(session.persisted)
        self.assertEqual(self.applied,[])

    async def test_duplicate_answers_wait_for_one_durable_commit(self):
        ident=(await self.backend.start(self.job))['rollout_id']
        ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='policy_answer':entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            a=asyncio.create_task(self.backend.answer(ident,answer_for(ticket)))
            await self.wait_thread(entered)
            b=asyncio.create_task(self.backend.answer(ident,answer_for(ticket)))
            await asyncio.sleep(.03)
            self.assertFalse(a.done());self.assertFalse(b.done());self.assertEqual(self.applied,[])
            release.set()
            replies=await asyncio.gather(a,b)
            self.assertEqual([x['duplicate'] for x in replies],[False,True])
        await self.backend.next_decision(ident,after=0,timeout=1)
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{ident}.jsonl').read_text().splitlines()]
        self.assertEqual([r['event'] for r in rows],['started','decision_captured','policy_answer','executed'])
        self.assertEqual(len(self.applied),1)

    async def test_close_drains_cancelled_capture_writer_before_releasing_store(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='decision_captured':entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            ident=(await self.backend.start(self.job))['rollout_id']
            await self.wait_thread(entered)
            captured_ticket=self.backend.sessions[ident].tickets[0]
            closing=asyncio.create_task(self.backend.close())
            await asyncio.sleep(.03)
            self.assertFalse(closing.done());self.assertFalse(self.backend._closed)
            release.set();await closing
        self.assertTrue(self.backend._closed)
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{ident}.jsonl').read_text().splitlines()]
        self.assertEqual([x['event'] for x in rows],['started','decision_captured'])
        self.assertEqual(self.applied,[])
        self.assertEqual(captured_ticket.status,'cancelled')
        self.assertTrue(captured_ticket.future.cancelled())

    async def test_answer_admitted_before_deadline_waits_for_durability_after_deadline(self):
        self.backend.decision_timeout=.12
        ident=(await self.backend.start(self.job))['rollout_id']
        ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='policy_answer':time.sleep(.18)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            started=time.monotonic()
            reply=await self.backend.answer(ident,answer_for(ticket))
            self.assertGreaterEqual(time.monotonic()-started,.17)
            self.assertTrue(reply['accepted'])
        await self.backend.next_decision(ident,after=0,timeout=1)
        self.assertEqual(len(self.applied),1)

    async def test_cancel_during_answer_write_never_resolves_cancelled_future(self):
        ident=(await self.backend.start(self.job))['rollout_id']
        ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def delayed(ident,row):
            if row['event']=='policy_answer':entered.set();release.wait(2)
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=delayed):
            answering=asyncio.create_task(self.backend.answer(ident,answer_for(ticket)))
            await self.wait_thread(entered)
            cancelling=asyncio.create_task(self.backend.cancel(ident))
            await asyncio.sleep(.03)
            self.assertFalse(cancelling.done());self.assertEqual(self.applied,[])
            self.assertEqual(self.backend._journal_slot._value,0)
            release.set()
            from jev_engine_rollout_backend import RolloutError
            with self.assertRaises(RolloutError) as rejected:await answering
            self.assertEqual(rejected.exception.status_code,409)
            result=await cancelling
        self.assertEqual(result['status'],'cancelled');self.assertFalse(result['on_policy'])
        self.assertEqual(self.applied,[])
        await self.backend._workers_idle.wait()
        self.assertEqual(self.backend._journal_slot._value,1)

    async def test_failed_inflight_writer_releases_only_on_real_completion(self):
        ident=(await self.backend.start(self.job))['rollout_id']
        ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        original=self.backend.store.append_journal
        def failed(ident,row):
            if row['event']=='policy_answer':
                entered.set();release.wait(2);raise OSError('fixture fsync failed')
            return original(ident,row)
        with patch.object(self.backend.store,'append_journal',side_effect=failed):
            answering=asyncio.create_task(self.backend.answer(ident,answer_for(ticket)))
            await self.wait_thread(entered);answering.cancel()
            with self.assertRaises(asyncio.CancelledError):await answering
            self.assertEqual(self.backend._journal_slot._value,0)
            release.set()
            await self.backend._workers_idle.wait()
            await asyncio.sleep(.01)
            self.assertEqual(self.backend._journal_slot._value,1)
            self.assertEqual(self.applied,[])
            result=await self.backend.cancel(ident)
        self.assertEqual(result['status'],'error');self.assertFalse(result['on_policy'])

    async def test_partial_durable_answer_failure_is_retained_and_never_retried_as_success(self):
        from jev_engine_rollout_backend import RolloutError
        ident=(await self.backend.start(self.job))['rollout_id']
        ticket=(await self.backend.next_decision(ident,timeout=1))['ticket']
        original=self.backend.store.append_journal
        def partial_failure(ident,row):
            original(ident,row)
            if row['event']=='policy_answer':raise OSError('fixture error after durable append')
        with patch.object(self.backend.store,'append_journal',side_effect=partial_failure):
            with self.assertRaises(RolloutError) as first:
                await self.backend.answer(ident,answer_for(ticket))
        self.assertEqual(first.exception.status_code,503)
        with self.assertRaises(RolloutError) as retry:
            await self.backend.answer(ident,answer_for(ticket))
        self.assertEqual(retry.exception.status_code,503)
        result=await self.backend.cancel(ident)
        self.assertEqual(result['status'],'error');self.assertFalse(result['on_policy'])
        self.assertTrue(result['counts_in_denominator']);self.assertEqual(self.applied,[])
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{ident}.jsonl').read_text().splitlines()]
        self.assertEqual([row['event'] for row in rows],['started','decision_captured','policy_answer'])
        self.assertTrue(self.backend.sessions[ident].persisted)

    async def test_queued_runner_audit_owns_immutable_value(self):
        ident=(await self.backend.start(self.job))['rollout_id']
        await self.backend.next_decision(ident,timeout=1)
        session=self.backend.sessions[ident]
        value={'ordinal':0,'mutable':[1]}
        PolicyBridge(self.backend,session).journal(self.job,'snapshot',value)
        value['mutable'].append(2)
        await self.backend._drain_journal(session)
        rows=[json.loads(line) for line in (Path(self.folder.name)/'journals'/f'{ident}.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['value']['mutable'],[1])

    async def test_cpu_job_snapshot_and_cancellation_keep_real_slot_until_finished(self):
        ident=(await self.backend.start(self.job))['rollout_id']
        await self.backend.next_decision(ident,timeout=1)
        bridge=PolicyBridge(self.backend,self.backend.sessions[ident])
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        def work(value):entered.set();release.wait(2);return value
        value={'x':[1]}
        task=asyncio.create_task(bridge.compute_record(work,value))
        await self.wait_thread(entered);value['x'].append(2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.backend._decision_slot._value,1)
        self.assertGreater(self.backend._worker_count,0)
        release.set();await self.backend._workers_idle.wait()
        self.assertEqual(self.backend._decision_slot._value,2)
        result,timing=await bridge.compute_record(lambda x:x,{'x':[1]})
        self.assertEqual(result,{'x':[1]});self.assertGreaterEqual(timing['record_cpu_seconds'],0)


class ProjectionPrefixTests(unittest.TestCase):
    def test_shared_prefixes_match_independent_physics_for_every_candidate(self):
        import jev_tetris_realtime as game
        from jev_tetris_projection import candidate_predictions,project_candidate
        for revision in [game.REVISION,game.LEGACY_PERSISTENT_REVISION]:
            for seed in [18,41,77]:
                state=game.advance_idle(game.step(game.fresh(seed,revision=revision),'0:0'),2.7)
                public=game.public(state);original=copy.deepcopy(public)
                actual=candidate_predictions(public)
                for action,values in actual.items():
                    for prediction in [values['immediate'],values['delayed'],*values.get('latency_scenarios',[])]:
                        expected=project_candidate(public,action,response_delay=prediction['response_delay_seconds'])
                        self.assertEqual(prediction,expected)
                self.assertEqual(public,original)


class BudgetBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_clock_catchup_spawning_new_piece_cannot_request_budget_plus_one(self):
        import jev_tetris_rl as rl
        calls=[];clock_calls=0
        class Policy:
            async def policy_action(self,record,episode_id,ordinal):
                calls.append(ordinal)
                if ordinal:raise AssertionError('requested past budget')
                return '0:0',{'origin':'offline_test_controller'}
        def clock():
            nonlocal clock_calls
            clock_calls+=1
            return 0. if clock_calls<=7 else 10.
        async def no_sleep(_):pass
        job={'seed':18,'episode_id':'budget-catchup-fixture','max_decisions':1}
        with patch.object(rl.time,'monotonic',side_effect=clock),patch.object(rl.asyncio,'sleep',side_effect=no_sleep):
            initial,final,trace,outcome,extra=await rl.play(Policy(),job)
        self.assertEqual(calls,[0]);self.assertEqual(len(trace),1)
        self.assertEqual(final['failure_reason'],'decision_budget_exhausted')
        self.assertGreaterEqual(final['steps'],1)
        self.assertTrue(rl.verify(job,initial,final,extra))


if __name__=='__main__':unittest.main()
