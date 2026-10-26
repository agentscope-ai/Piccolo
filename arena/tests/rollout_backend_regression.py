"""Real native realtime receipts through external policy tickets, without models."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jev_engine_rollout_backend import RolloutBackend, RolloutError


def answer_for(ticket, action=None):
    values = ticket['candidate_values']
    action = action or values[0]
    index = values.index(action)
    return {'ticket_id': ticket['ticket_id'], 'request_token': ticket['request_token'],
            'policy_version': ticket['policy_version'], 'action': action,
            'policy': {'candidate_values': values, 'selected_index': index,
                       'old_probabilities': [1. / len(values)] * len(values)}}


class RealtimeTicketTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_snake_ticket_keeps_real_clock_and_never_applies_late_action(self):
        from jev_snake_rl import play, verify
        from jev_gameplay_reward_contract import default_config, settle_episode, terminal_objective
        from jev_realtime_scoring import score_episode, SCORING_REVISION
        observed = {}

        async def existing_runner(proxy, job):
            initial, final, trace, outcome, extra = await play(proxy, job)
            verify(job, initial, final, extra)
            observed.update(initial=initial, final=final, trace=trace, extra=extra)
            score = score_episode(job['kind'], final, outcome)
            reward = settle_episode(job['kind'], initial, trace,
                terminal_objective(job['kind'], outcome, score), default_config([job['kind']]))
            return {**job, **extra, 'initial_state': initial, 'final_state': final,
                    'trace': trace, 'outcome': outcome, **reward,
                    'replay_verified': True, 'realtime_score': score,
                    'scoring_revision': SCORING_REVISION}

        backend = RolloutBackend(existing_runner, decision_timeout=.4)
        self.addAsyncCleanup(backend.close)
        started = await backend.start({'episode_id': 'snake-ticket-fixture', 'game': 'snake_navigation',
            'seed': 31, 'policy_version': 'fixture-v1', 'request_token': 'start-fixture'})
        ident = started['rollout_id']
        first = (await backend.next_decision(ident, timeout=3))['ticket']
        heading = first['record']['state']['direction']
        self.assertFalse(first['record']['state']['candidate_next_cells'][heading]['collision'])
        await backend.answer(ident, answer_for(first, heading))
        second = (await backend.next_decision(ident, after=first['sequence'], timeout=3))['ticket']
        self.assertIsNotNone(second)
        self.assertFalse(second['inference_pauses_environment'])
        captured = second['record']['state']
        await asyncio.sleep(.45)
        with self.assertRaises(RolloutError) as rejected:
            await backend.answer(ident, answer_for(second))
        self.assertEqual(rejected.exception.status_code, 409)
        await backend.next_decision(ident, after=second['sequence'], timeout=3)
        result = await backend.result(ident)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(result['counts_in_denominator'])
        self.assertTrue(result['replay_verified'])
        self.assertFalse(result['on_policy'])
        self.assertEqual(len(result['trace']), 1)
        self.assertGreater(result['final_state']['elapsed'], captured['elapsed'])
        self.assertGreater(result['final_state']['steps'], captured['steps'])
        expired = observed['extra']['replay_events'][-1]
        self.assertFalse(expired['action_applied'])
        self.assertIsNone(expired['action'])
        self.assertGreaterEqual(expired['waiting_seconds'], .39)
        self.assertEqual(result['trace'][0]['policy']['old_probabilities'],
                         answer_for(first, heading)['policy']['old_probabilities'])

    async def test_immediate_cancel_still_has_an_attempt_receipt(self):
        async def never_needed(proxy, job):
            # Durable startup is an owned task; the runner may enter before the
            # HTTP reply arrives, but cancelling must prevent further actions.
            await asyncio.Event().wait()
            self.fail('cancelled runner must not resume')
        backend = RolloutBackend(never_needed)
        started = await backend.start({'episode_id': 'cancel-fixture', 'game': 'jump_jump',
            'seed': 1, 'policy_version': 'fixture-v1', 'request_token': 'cancel-start'})
        result = await backend.cancel(started['rollout_id'])
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['counts_in_denominator'])
        self.assertFalse(result['on_policy'])
        self.assertIsNone(result['terminal_utility'])


class AuditFailureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='jev-rollout-audit-test-')
        self.addCleanup(self.folder.cleanup)

    @staticmethod
    def job():
        return {'episode_id': 'audit-fixture', 'game': 'jump_jump', 'seed': 1,
                'policy_version': 'fixture-v1', 'request_token': 'audit-start'}

    async def test_disk_audit_does_not_retain_private_state_copy(self):
        async def never_started(proxy, job):
            await asyncio.Event().wait()
            self.fail('cancelled runner must not resume')
        backend = RolloutBackend(never_started, storage_dir=self.folder.name)
        self.addAsyncCleanup(backend.close)
        started = await backend.start(self.job())
        session = backend.sessions[started['rollout_id']]
        backend._journal(session, 'executed', {'before_state': {'hidden_cards': [1, 2]}})
        backend._journal(session, 'attempt_finished', {'error': 'private-provider-details'})
        self.assertEqual(session.journals, [])
        content = (Path(self.folder.name) / 'journals' / (session.ident + '.jsonl')).read_text()
        self.assertIn('hidden_cards', content)
        self.assertNotIn('private-provider-details', content)
        self.assertIn('runner_error', content)
        await backend.cancel(started['rollout_id'])

    async def test_start_audit_failure_is_a_retained_error_attempt(self):
        async def never_started(proxy, job):
            self.fail('audit failure must prevent engine execution')
        backend = RolloutBackend(never_started)
        with patch.object(backend, '_journal', side_effect=OSError('fixture storage failure')):
            started = await backend.start(self.job())
        result = await backend.result(started['rollout_id'])
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'OSError')
        self.assertTrue(result['counts_in_denominator'])
        self.assertFalse(result['on_policy'])
        self.assertIsNone(backend.sessions[started['rollout_id']].task)

    async def test_answer_audit_failure_does_not_resolve_or_execute_ticket(self):
        from jev_engine_registry import get_engine
        engine = get_engine('jump_jump')
        record = engine.observe(engine.reset(1))
        applied = []
        async def callback_fixture(proxy, job):
            action, policy = await proxy.policy_action(record, job['episode_id'], 0)
            applied.append(action)
            return {'status': 'error', 'error_type': 'fixture_finished'}
        backend = RolloutBackend(callback_fixture)
        self.addAsyncCleanup(backend.close)
        ident = (await backend.start(self.job()))['rollout_id']
        ticket = (await backend.next_decision(ident, timeout=1))['ticket']
        with patch.object(backend, '_journal', side_effect=OSError('fixture storage failure')):
            with self.assertRaises(RolloutError) as rejected:
                await backend.answer(ident, answer_for(ticket))
        self.assertEqual(rejected.exception.status_code, 503)
        pending = backend.sessions[ident].tickets[0]
        self.assertIsNone(pending.answer)
        self.assertFalse(pending.future.done())
        self.assertEqual(applied, [])
        # A filesystem exception may follow a partial durable write. Do not
        # clear the audit failure and execute on a later retry of this ticket.
        with self.assertRaises(RolloutError) as retried:
            await backend.answer(ident, answer_for(ticket))
        self.assertEqual(retried.exception.status_code, 503)
        self.assertEqual(applied, [])
        result = await backend.cancel(ident)
        self.assertEqual(result['status'], 'error')
        self.assertFalse(result['on_policy'])

    async def test_receipt_write_failure_cannot_report_on_policy_success(self):
        async def never_started(proxy, job):
            await asyncio.Event().wait()
            self.fail('cancelled runner must not resume')
        backend = RolloutBackend(never_started, storage_dir=self.folder.name)
        self.addAsyncCleanup(backend.close)
        ident = (await backend.start(self.job()))['rollout_id']
        with patch.object(backend.store, 'publish_result', side_effect=OSError('fixture storage failure')):
            receipt = await backend.cancel(ident)
        self.assertEqual(receipt['status'], 'error')
        self.assertEqual(receipt['persistence_error_type'], 'OSError')
        self.assertTrue(receipt['counts_in_denominator'])
        self.assertFalse(receipt['on_policy'])


async def native_storage_runner(proxy, job):
    """Exercise the shared native execution, exact replay and reward settlement."""
    from jev_engine_episode_runner import EngineEpisodeRunner
    from jev_gameplay_reward_contract import default_config, settle_episode, terminal_objective
    runner = EngineEpisodeRunner.__new__(EngineEpisodeRunner)
    runner.args = SimpleNamespace(model_url='fixture-callback')
    runner.policy_action, runner.journal = proxy.policy_action, proxy.journal
    initial, final, trace, outcome, extra = await runner.python_episode(job)
    await runner.verify_python_replay(job, initial, final, extra)
    reward = settle_episode(job['kind'], initial, trace,
        terminal_objective(job['kind'], outcome), default_config([job['kind']]))
    return {**job, **extra, 'status': 'complete', 'outcome': outcome, 'trace': trace,
            'initial_state': initial, 'final_state': final, **reward,
            'replay_verified': True, 'policy_origin': 'student', 'on_policy': True}


class DurableStorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='jev-rollout-storage-test-')
        self.addCleanup(self.folder.cleanup)

    def backend(self, **kwargs):
        backend = RolloutBackend(native_storage_runner, storage_dir=self.folder.name, **kwargs)
        self.addAsyncCleanup(backend.close)
        return backend

    @staticmethod
    def job(index=0):
        return {'episode_id': 'storage-fixture-' + str(index), 'game': 'jump_jump', 'seed': 42,
                'policy_version': 'fixture-v1', 'request_token': 'start-' + str(index)}

    async def complete(self, backend, index=0, owner='local', expected_status='complete'):
        job = self.job(index)
        ident = (await backend.start(job, owner))['rollout_id']
        after, answers = -1, []
        for _ in range(8):
            polled = await backend.next_decision(ident, owner, after=after, timeout=2)
            ticket = polled.get('ticket')
            if ticket is None:
                break
            facts = ticket['record']['state']['candidate_landings']
            action = max(ticket['candidate_values'], key=lambda value: facts[value]['distance_to_center'])
            body = answer_for(ticket, action)
            await backend.answer(ident, body, owner)
            answers.append(body)
            after = ticket['sequence']
        result = await backend.result(ident, owner)
        self.assertEqual(result['status'], expected_status)
        self.assertTrue(result['replay_verified'])
        return ident, job, answers, result

    async def test_cache_eviction_disk_result_pagination_and_duplicate_answer(self):
        backend = self.backend(completed_cache_size=2)
        rows = [await self.complete(backend, index) for index in range(7)]
        self.assertEqual(len(backend.sessions), 2)
        self.assertEqual(backend.cache_info()['completed'], 2)
        self.assertTrue(all(not session.tickets and not session.journals
                            for session in backend.sessions.values()))
        first, job, answers, expected = rows[0]
        self.assertNotIn(first, backend.sessions)
        self.assertEqual(await backend.result(first), expected)
        self.assertEqual(len(backend.sessions), 2)
        self.assertTrue((await backend.answer(first, answers[0]))['duplicate'])
        altered = json.loads(json.dumps(answers[0]))
        altered['policy']['sampling_epsilon'] = .2
        with self.assertRaises(RolloutError) as conflict:
            await backend.answer(first, altered)
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertTrue((await backend.start(job))['duplicate'])
        page1 = await backend.list_results(limit=3)
        page2 = await backend.list_results(cursor=page1['next_cursor'], limit=3)
        page3 = await backend.list_results(cursor=page2['next_cursor'], limit=3)
        listed = page1['items'] + page2['items'] + page3['items']
        self.assertEqual(page1['total'], 7)
        self.assertEqual({row['rollout_id'] for row in listed}, {row[0] for row in rows})
        self.assertIsNone(page3['next_cursor'])
        self.assertTrue(all('trace' not in row and 'owner' not in row for row in listed))

    async def test_zero_cache_restart_owner_isolation_and_private_permissions(self):
        backend = self.backend(completed_cache_size=0)
        a = await self.complete(backend, owner='owner-a')
        b = await self.complete(backend, owner='owner-b')
        self.assertEqual(backend.sessions, {})
        self.assertEqual(backend.identities, {})
        for path in Path(self.folder.name).rglob('*'):
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600, str(path))
        await backend.close()
        read_text = Path.read_text
        def lazy_read(path, *args, **kwargs):
            self.assertNotEqual(path.parent.name, 'episodes', 'restart must not eagerly load all historic receipts')
            return read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', lazy_read):
            restored = self.backend(completed_cache_size=0)
        self.assertEqual(restored.recovery_summary, {'restored': 2, 'interrupted': 0})
        self.assertEqual(await restored.result(a[0], 'owner-a'), a[3])
        self.assertTrue((await restored.answer(a[0], a[2][0], 'owner-a'))['duplicate'])
        self.assertEqual((await restored.start(a[1], 'owner-a'))['rollout_id'], a[0])
        with self.assertRaises(RolloutError) as hidden:
            await restored.result(a[0], 'owner-b')
        self.assertEqual(hidden.exception.status_code, 404)
        page = await restored.list_results('owner-b')
        self.assertEqual([item['rollout_id'] for item in page['items']], [b[0]])
        self.assertEqual(restored.sessions, {})

    async def test_single_writer_and_index_rebuild_from_immutable_files(self):
        backend = self.backend(completed_cache_size=1)
        with self.assertRaisesRegex(RuntimeError, 'already_owned'):
            RolloutBackend(native_storage_runner, storage_dir=self.folder.name)
        ident, job, answers, result = await self.complete(backend)
        await backend.close()
        with tempfile.TemporaryDirectory(prefix='jev-rollout-rebuild-test-') as copy:
            for name in ('sessions', 'episodes', 'journals'):
                shutil.copytree(Path(self.folder.name) / name, Path(copy) / name)
            restored = RolloutBackend(native_storage_runner, storage_dir=copy, completed_cache_size=0)
            try:
                self.assertEqual(await restored.result(ident), result)
                self.assertTrue((await restored.answer(ident, answers[0]))['duplicate'])
                self.assertTrue((await restored.start(job))['duplicate'])
            finally:
                await restored.close()

    async def test_memory_byte_cap_evicts_oversized_receipt(self):
        backend = self.backend(completed_cache_size=100, completed_cache_bytes=1)
        ident, _, _, expected = await self.complete(backend)
        self.assertEqual(backend.cache_info()['serialized_bytes'], 0)
        self.assertEqual(await backend.result(ident), expected)
        self.assertEqual(backend.sessions, {})

    async def test_legacy_without_owner_is_preserved_but_not_assigned_to_local(self):
        folder = Path(self.folder.name) / 'episodes'
        folder.mkdir()
        ident = 'a' * 32
        legacy = folder / (ident + '.json')
        original = '{"status":"complete","private_legacy_field":"kept"}\n'
        legacy.write_text(original)
        backend = self.backend()
        self.assertEqual((await backend.list_results())['total'], 0)
        with self.assertRaises(RolloutError) as denied:
            await backend.result(ident)
        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(legacy.read_text(), original)

    async def test_public_write_then_index_failure_recovers_error_without_overwrite(self):
        backend = self.backend(completed_cache_size=0)
        original = backend.store._index_receipt
        calls = []
        def fail_once(*args):
            calls.append(True)
            if len(calls) == 1:
                raise OSError('fixture index commit failure')
            return original(*args)
        with patch.object(backend.store, '_index_receipt', side_effect=fail_once):
            ident, _, _, error = await self.complete(backend, expected_status='error')
        self.assertFalse(error['on_policy'])
        self.assertTrue(error['counts_in_denominator'])
        public = Path(self.folder.name) / 'episodes' / (ident + '.json')
        old_bytes = public.read_bytes()
        self.assertEqual(json.loads(old_bytes)['status'], 'complete')
        await backend.close()
        restored = self.backend(completed_cache_size=0)
        self.assertEqual(await restored.result(ident), error)
        self.assertEqual(public.read_bytes(), old_bytes)
        self.assertEqual((await restored.list_results())['items'][0]['status'], 'error')

    async def test_unpersisted_failure_blocks_new_admission_and_stays_in_memory(self):
        backend = self.backend(completed_cache_size=0)
        with patch.object(backend.store, 'publish_result', side_effect=OSError('fixture disk failure')), \
             patch.object(backend.store, 'publish_failure', side_effect=OSError('fixture disk failure')):
            ident, _, _, receipt = await self.complete(backend, expected_status='error')
        self.assertFalse(receipt['on_policy'])
        self.assertTrue(backend.cache_info()['storage_fault'])
        self.assertIn(ident, backend.sessions)
        with self.assertRaises(RolloutError) as stopped:
            await backend.start(self.job(1))
        self.assertEqual(stopped.exception.status_code, 503)
        page = await backend.list_results()
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['items'][0]['status'], 'error')
        await backend.close()
        restored = self.backend(completed_cache_size=0)
        self.assertEqual((await restored.result(ident))['error_type'], 'backend_interrupted')
        self.assertEqual((await restored.list_results())['total'], 1)

    async def test_http_history_is_owner_scoped_and_fetches_evicted_results(self):
        import httpx
        from fastapi import FastAPI
        from jev_engine_rollout_backend import install
        backend = self.backend(completed_cache_size=0)
        first = await self.complete(backend, owner='alpha')
        await self.complete(backend, owner='beta')
        app = FastAPI()
        install(app, '/fixture', backend, owner_resolver=lambda request: request.headers['x-fixture-owner'])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture',
                                     headers={'x-fixture-owner': 'alpha'}) as client:
            base = '/fixture/api/v1/rollouts'
            page = await client.get(base, params={'limit': 1})
            self.assertEqual(page.status_code, 200)
            self.assertEqual([row['rollout_id'] for row in page.json()['items']], [first[0]])
            fetched = await client.get(base + '/' + first[0] + '/result')
            self.assertEqual(fetched.json(), first[3])
            denied = await client.get(base + '/' + first[0] + '/result', headers={'x-fixture-owner': 'beta'})
            self.assertEqual(denied.status_code, 404)
            invalid = await client.get(base, params={'limit': 0})
            self.assertEqual(invalid.status_code, 422)
        self.assertEqual(backend.sessions, {})

    async def test_crash_after_durable_answer_recovers_error_without_reexecution(self):
        child = r'''
import asyncio,json,os,sys
from jev_engine_rollout_backend import RolloutBackend
from rollout_backend_regression import answer_for,DurableStorageTests
from jev_engine_registry import get_engine
async def runner(proxy,job):
    engine=get_engine(job['kind'])
    await proxy.policy_action(engine.observe(engine.reset(job['seed'])),job['episode_id'],0)
    await asyncio.Event().wait()
async def main():
    backend=RolloutBackend(runner,storage_dir=sys.argv[1])
    job=DurableStorageTests.job()
    ident=(await backend.start(job,owner='crashed-owner'))['rollout_id']
    ticket=(await backend.next_decision(ident,owner='crashed-owner',timeout=2))['ticket']
    answer=answer_for(ticket)
    await backend.answer(ident,answer,owner='crashed-owner')
    pending=(await backend.start(DurableStorageTests.job(1),owner='crashed-owner'))['rollout_id']
    pending_ticket=(await backend.next_decision(pending,owner='crashed-owner',timeout=2))['ticket']
    print(json.dumps({'ident':ident,'job':job,'answer':answer,
                     'pending':pending,'pending_answer':answer_for(pending_ticket)}),flush=True)
    os._exit(17)
asyncio.run(main())
'''
        environment = {**os.environ, 'PYTHONPATH': str(Path(__file__).parent) + os.pathsep + os.environ.get('PYTHONPATH', '')}
        process = subprocess.run([sys.executable, '-c', child, self.folder.name], env=environment,
                                 text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 17, process.stderr)
        saved = json.loads(process.stdout)
        async def forbidden_runner(proxy, job):
            self.fail('restoring an interrupted episode must never execute its runner')
        backend = RolloutBackend(forbidden_runner, storage_dir=self.folder.name, completed_cache_size=0)
        self.addAsyncCleanup(backend.close)
        self.assertEqual(backend.recovery_summary, {'restored': 0, 'interrupted': 2})
        receipt = await backend.result(saved['ident'], 'crashed-owner')
        self.assertEqual(receipt['status'], 'error')
        self.assertEqual(receipt['error_type'], 'backend_interrupted')
        self.assertEqual(receipt['decision_requests'], 1)
        self.assertFalse(receipt['on_policy'])
        self.assertTrue(receipt['counts_in_denominator'])
        self.assertTrue((await backend.start(saved['job'], 'crashed-owner'))['duplicate'])
        self.assertTrue((await backend.answer(saved['ident'], saved['answer'], 'crashed-owner'))['duplicate'])
        with self.assertRaises(RolloutError) as expired:
            await backend.answer(saved['pending'], saved['pending_answer'], 'crashed-owner')
        self.assertEqual(expired.exception.status_code, 409)
        changed_job = {**saved['job'], 'seed': 1}
        with self.assertRaises(RolloutError) as conflict:
            await backend.start(changed_job, 'crashed-owner')
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual((await backend.list_results('crashed-owner'))['total'], 2)


if __name__ == '__main__':
    unittest.main()
