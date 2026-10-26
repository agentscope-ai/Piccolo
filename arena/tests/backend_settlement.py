"""Terminal CPU work must not steal another live world's policy deadline."""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from jev_engine_rollout_backend import RolloutBackend, RolloutError
from jev_engine_registry import get_engine
from rollout_backend_regression import answer_for

class DeadlineSettlementTests(unittest.IsolatedAsyncioTestCase):
    async def fixture(self, timeout=.1, folder=None):
        applied=[]
        record=get_engine('jump_jump').observe(get_engine('jump_jump').reset(1))
        async def runner(proxy,job):
            action,policy=await proxy.policy_action(record,job['episode_id'],0)
            applied.append((job['episode_id'],action))
            return {'status':'error','error_type':'fixture_done'}
        backend=RolloutBackend(runner,decision_timeout=timeout,storage_dir=folder)
        self.addAsyncCleanup(backend.close)
        return backend,applied

    async def start(self,b,name='test'):
        item=await b.start({'episode_id':name,'game':'jump_jump','seed':1,
            'policy_version':'fixture','request_token':name})
        rid=item['rollout_id']
        return rid,(await b.next_decision(rid,timeout=2))['ticket']

    async def test_terminal_status_freezes_before_settlement_task_is_scheduled(self):
        async def runner(proxy,job):return {'status':'error','error_type':'fixture_done'}
        b=RolloutBackend(runner);self.addAsyncCleanup(b.close)
        started=await b.start({'episode_id':'terminal-race','game':'jump_jump','seed':1,
            'policy_version':'fixture','request_token':'terminal-race'})
        session=b.sessions[started['rollout_id']]
        await asyncio.sleep(0)
        self.assertEqual(session.status,'settling')
        await session.task

    async def test_timely_durable_answer_survives_delayed_waiter(self):
        b,applied=await self.fixture(timeout=.05)
        rid,ticket=await self.start(b)
        await b.answer(rid,answer_for(ticket))
        # Intentionally reproduce the measured wait_for(shield()) callback race.
        time.sleep(.09)
        await b.sessions[rid].task
        self.assertEqual(applied,[("test",ticket['candidate_values'][0])])
        self.assertNotIn('decision_expired',[r['event'] for r in b.sessions[rid].journals])
        self.assertLess(b.sessions[rid].tickets[0].accepted_at,b.sessions[rid].tickets[0].expires_at)

    async def test_late_answer_rejected_even_before_timer_callback_runs(self):
        b,applied=await self.fixture(timeout=.05)
        rid,ticket=await self.start(b)
        time.sleep(.09)
        with self.assertRaises(RolloutError) as error:
            await b.answer(rid,answer_for(ticket))
        self.assertEqual(error.exception.status_code,409)
        await b.sessions[rid].task
        self.assertEqual(applied,[])
        self.assertEqual((await b.result(rid))['status'],'timeout')

    async def test_slow_terminal_publication_does_not_block_other_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            b,applied=await self.fixture(timeout=.15,folder=folder)
            rid,first=await self.start(b,'first')
            publishing=threading.Event()
            original=b.store.publish_result
            def slow(*args,**kw):
                publishing.set();time.sleep(.3)
                return original(*args,**kw)
            with patch.object(b.store,'publish_result',side_effect=slow):
                await b.answer(rid,answer_for(first))
                for _ in range(100):
                    if publishing.is_set():break
                    await asyncio.sleep(.005)
                self.assertTrue(publishing.is_set())
                second,ticket=await self.start(b,'second')
                t=time.monotonic();await b.answer(second,answer_for(ticket))
                self.assertLess(time.monotonic()-t,.1)
                tasks=[s.task for s in list(b.sessions.values()) if s.task]
                await asyncio.gather(*tasks)
            self.assertEqual({x[0] for x in applied},{'first','second'})
            self.assertTrue((await b.result(rid))['counts_in_denominator'])
            await b.close()

    async def test_cancel_waiting_cpu_caller_keeps_slot_and_close_drains(self):
        b,_=await self.fixture()
        started=threading.Event();release=threading.Event();entered=[]
        def blocked():
            entered.append('first');started.set();release.wait(2);return 'done'
        first=asyncio.create_task(b._cpu(blocked))
        while not started.is_set():await asyncio.sleep(.005)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):await first
        second=asyncio.create_task(b._cpu(lambda:entered.append('second')))
        await asyncio.sleep(.03);self.assertEqual(entered,['first'])
        release.set();await second
        await b.close();self.assertEqual(entered,['first','second'])

    async def test_http_result_does_not_queue_behind_terminal_worker(self):
        b,_=await self.fixture()
        started=threading.Event();release=threading.Event()
        def terminal():started.set();release.wait(2)
        blocked=asyncio.create_task(b._cpu(terminal))
        while not started.is_set():await asyncio.sleep(.005)
        try:
            response=await asyncio.wait_for(b.encode_response({'status':'complete'}),.1)
            self.assertEqual(json.loads(response.body),{'status':'complete'})
            self.assertFalse(blocked.done())
        finally:
            release.set();await blocked

    async def test_close_drains_response_waiters_and_closes_new_admission(self):
        with tempfile.TemporaryDirectory() as folder:
            b,_=await self.fixture(folder=folder)
            began=threading.Event();release=threading.Event();closed_when_finished=[]
            def first():began.set();release.wait(2)
            def second():
                time.sleep(.07);closed_when_finished.append(b.store.closed)
            one=asyncio.create_task(b._response_cpu(first))
            while not began.is_set():await asyncio.sleep(.005)
            two=asyncio.create_task(b._response_cpu(second))
            await asyncio.sleep(0)
            closing=asyncio.create_task(b.close())
            await asyncio.sleep(.01)
            self.assertFalse(closing.done())
            with self.assertRaises(RolloutError) as denied:
                await b.encode_response({'extra':'late'})
            self.assertEqual(denied.exception.status_code,503)
            release.set();await asyncio.gather(one,two,closing)
            self.assertEqual(closed_when_finished,[False])
            self.assertEqual(b._worker_count,0)
            self.assertTrue(b.store.closed)

    async def test_http_encoder_is_off_loop_and_json_exact(self):
        from fastapi.responses import JSONResponse
        b,_=await self.fixture()
        parent=threading.get_ident();threads=[]
        original=JSONResponse.render
        def render(self,value):
            threads.append(threading.get_ident());time.sleep(.08)
            return original(self,value)
        heartbeat=asyncio.create_task(asyncio.sleep(.02))
        with patch.object(JSONResponse,'render',render):
            response=asyncio.create_task(b.encode_response({'中文':[1,2,3]}))
            await heartbeat
            self.assertFalse(response.done())
            result=await response
        self.assertEqual(json.loads(result.body),{'中文':[1,2,3]})
        self.assertTrue(all(x!=parent for x in threads))

if __name__=='__main__':unittest.main()
