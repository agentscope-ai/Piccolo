import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from blink_arena.public_models import PublicClients, decode, load_credentials, AccessError, clean

spec = importlib.util.spec_from_file_location('public_eval', Path(__file__).resolve().parents[1]/'scripts/evaluate_public.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(ident):
    return {'id': ident, 'name': ident, 'access_id': ident, 'role': 'baseline', 'enabled': True,
            'config': {'adapter': 'http_decisions', 'endpoint': 'http://fixture/v1/systemone',
                       'model_id': ident, 'expected_returned_models': [ident+'-v1']}}


RECORD = {'state': {'visible': 1}, 'questions': {'decision': {
    'type': 'choice', 'instructions': 'Choose.', 'criteria': {'a': 'A', 'b': 'B'}, 'option_order': ['b', 'a']}}}


class PublicEvaluationTests(unittest.TestCase):
    def test_single_checkpoint_independent_run_constructs_without_a_duel_opponent(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            roster={'a':row('a')}
            plan=module.schedule([module.participant(roster['a'])],list(module.KINDS),8,42,'independent')
            (out/'plan.json').write_text(json.dumps(plan))
            contract={'roster':{'models':roster},'games':list(module.KINDS),'seeds':8,'seed_base':42,
                      'cohort_mode':'independent','per_model_concurrency':5,'max_games':20}
            arena=module.PublicArena(out,contract,SimpleNamespace(),{'a'})
            arena._validate_plan(plan)
            self.assertEqual(len(plan['schedule']),176)
            self.assertEqual(set(arena.registered),{'a'})

    def test_independent_cohort_is_exactly_one_episode_per_model_game_seed(self):
        players = [module.participant(row(str(i))) for i in range(9)]
        plan = module.schedule(players, list(module.KINDS), 8, 42, 'independent')
        self.assertEqual(len(plan['schedule']), 1584)
        keys = {(f['kind'], f['seed'], f['a']) for f in plan['schedule']}
        self.assertEqual(len(keys), 1584)
        self.assertTrue(all(f['b'] == 'rule-engine-v1' and f['leg'] == 0 for f in plan['schedule']))
        self.assertTrue(all(module.independent.fixture_models(f) == [f['a']] for f in plan['schedule']))

    def test_independent_report_keeps_fixed_denominator_and_inherited_latency_separate(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            plan = module.schedule([module.participant(row('a'))], ['blackjack'], 8, 42, 'independent')
            receipts = [dict(plan['schedule'][i], status=status, outcome=outcome, seconds=2)
                        for i, (status, outcome) in enumerate([('complete', 'win'), ('complete', 'loss'), ('error', None)])]
            requests = [dict(game='blackjack', model='a', status='ok', seconds=seconds, runtime_generation=gen)
                        for seconds, gen in [(10, 'independent-inherited'), (2, module.REVISION)]]
            summary = module.independent.report(out, plan, receipts, requests, module.stats)
            metric = summary['metrics'][0]
            self.assertEqual(metric['success_rate'], 1/8)
            self.assertEqual(metric['success_rate_valid'], .5)
            self.assertEqual((metric['errors'], metric['pending']), (1, 5))
            self.assertEqual((metric['http_current_mean_seconds'], metric['http_inherited_requests']), (2, 1))
            self.assertNotIn('rating', summary['overall'][0])

    def test_independent_board_terminal_uses_native_winner_and_model_seat(self):
        from jev_demo_arena_episodes import _termination
        for winner, side, outcome in [('X', 0, 'win'), ('O', 0, 'loss'),
                                      ('X', 1, 'loss'), ('O', 1, 'win'), ('draw', 1, 'draw')]:
            self.assertEqual(_termination('hex_7x7', {'final_state': {'winner': winner},
                'model_player': side, 'outcome': outcome}, {}), (False, True))
        with self.assertRaisesRegex(ValueError, 'perspective_mismatch'):
            _termination('hex_7x7', {'final_state': {'winner': 'X'}, 'model_player': 1, 'outcome': 'win'}, {})

    def test_independent_enrollment_adds_only_176_episodes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            players = [module.participant(row(str(i))) for i in range(9)]
            contract = {'cohort_mode': 'independent', 'games': list(module.KINDS),
                        'seeds': 8, 'seed_base': 42, 'roster': {'models': {str(i):row(str(i)) for i in range(9)}}}
            old = module.schedule(players, contract['games'], 8, 42, 'independent')
            module._write(root/'plan.json', old)
            self.assertEqual(module.append_enrollment(root, contract, row('new-rl')), 176)
            new = module._read(root/'plan.json')
            self.assertEqual(new['schedule'][:1584], old['schedule'])
            self.assertEqual(len(new['schedule']), 1760)

    def test_independent_inheritance_validates_score_and_filters_other_model_requests(self):
        from jev_demo_arena_episodes import comparison_spec, REVISION
        from jev_demo_decision_stability import decision_policy
        with tempfile.TemporaryDirectory() as d:
            source, out = Path(d)/'old', Path(d)/'new'
            players = [module.participant(row(m)) for m in ('a', 'b')]
            contract = {'games': ['blackjack'], 'seeds': 1, 'seed_base': 42,
                        'prompt': {}, 'scope': {}, 'engine_sources': {}}
            old = module.schedule(players, ['blackjack'], 1, 42)
            new = module.schedule(players, ['blackjack'], 1, 42, 'independent')
            module._write(source/'contract.json', contract)
            module._write(source/'plan.json', old)
            module._write(out/'plan.json', new)
            arena = module.PublicArena.__new__(module.PublicArena)
            arena._load = lambda: (out, new)
            good = {'status': 'complete', 'kind': 'blackjack', 'seed': 42, 'model': 'a',
                'episode_id': 'blackjack-42-a', 'episode_revision': REVISION,
                'engine_revision': module.EVALUATION_REVISION, 'decision_policy': decision_policy('blackjack'),
                'comparison_spec': comparison_spec('blackjack'), 'higher_is_better': True,
                'comparison_key': [1.], 'score': 1., 'model_player': 0, 'outcome': 'win',
                'final_state': {'outcome': 'win'}, 'initial_state': {'outcome': None},
                'terminal_returns': [1., -1.], 'budget_exhausted': False, 'terminal': True,
                'natural_success': None, 'trace': [], 'model_identity': {k:v for k,v in players[0].items() if k!='name'},
                'binding': arena._episode_binding('blackjack', 42, 'a'), 'seconds': 2}
            for model, episode in [('a', good), ('b', dict(kind='blackjack', seed=42, model='b', status='error'))]:
                name = module.GameArena._episode_name('blackjack', 42, model)
                module._write(source/'episodes'/name, episode)
                module._write(source/'episode_summaries'/name, module.GameArena._episode_summary(episode))
            (source/'requests').mkdir()
            (source/'requests/0.jsonl').write_text(''.join(json.dumps(dict(model=m, status='ok', seconds=1))+'\n' for m in ('a','b')))
            receipt = module.independent.inherit(out, source, contract)
            self.assertEqual((receipt['episodes'], receipt['requests'], receipt['duel_results_imported']), (1,1,0))
            self.assertEqual(len(receipt['requeued_errors']), 1)
            self.assertEqual(json.loads((out/'requests/0.jsonl').read_text())['model'], 'a')
            good['terminal_returns'] = [-1., 1.]
            module._write(source/'episodes/blackjack-42-a.json', good)
            with self.assertRaisesRegex(ValueError, 'native_score_evidence_mismatch'):
                module.independent.inherit(out, source, contract)

    def test_compact_episode_keeps_native_evidence_for_actual_comparison(self):
        from jev_demo_arena_episodes import comparison_spec, compare_results, REVISION
        from jev_demo_decision_stability import decision_policy
        row = {'status': 'complete', 'kind': 'blackjack', 'seed': 42, 'episode_revision': REVISION,
               'engine_revision': module.EVALUATION_REVISION, 'decision_policy': decision_policy('blackjack'),
               'comparison_spec': comparison_spec('blackjack'), 'higher_is_better': True,
               'comparison_key': [1.], 'score': 1., 'model_player': 0, 'outcome': 'win',
               'final_state': {'outcome': 'win'}, 'initial_state': {'outcome': None},
               'terminal_returns': [1., -1.], 'budget_exhausted': False, 'terminal': True,
               'natural_success': None, 'trace': [{'private_replay': True}]}
        compact = module.PublicArena._comparison_evidence(row)
        self.assertNotIn('trace', compact)
        self.assertEqual(compare_results(compact, compact), .5)
        compact['terminal_returns'] = [-1., 1.]
        with self.assertRaisesRegex(ValueError, 'native_score_evidence_mismatch'):
            compare_results(compact, compact)

    def test_slow_reporting_allows_another_live_game_to_continue(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                progressed = threading.Event()
                arena = module.PublicArena.__new__(module.PublicArena)
                arena.clients = SimpleNamespace(blocked={}, peak=2)
                arena.ready_ids = arena.registered = {'a', 'b'}
                arena.concurrency = 2
                arena.games = module.GameAdmission(2, {'a': 5, 'b': 5})
                arena.episode_tasks = {}
                arena.pause_requested = False
                arena._state = lambda *a, **kw: None
                async def play(folder, fixture, browser):
                    if fixture['ordinal'] == 1:
                        await asyncio.sleep(.05)
                        progressed.set()
                    else:
                        await asyncio.sleep(.001)
                def slow_report(out):
                    if not progressed.wait(2):
                        raise RuntimeError('report_blocked_live_game')
                arena._persist_fixture = play
                plan = {'kinds': ['blackjack'], 'schedule': [
                    {'ordinal': n, 'kind': 'blackjack', 'a': 'a', 'b': 'b'} for n in (0, 1)]}
                with patch.object(module, 'report', slow_report):
                    await arena._fixtures(Path(d), plan, None)
                self.assertTrue(progressed.is_set())
        asyncio.run(run())

    def test_slow_disk_journal_does_not_block_decision_and_keeps_fixture_context(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                release = threading.Event()
                started = threading.Event()
                original = module.request_log
                def slow_write(out, event, context):
                    started.set()
                    if not release.wait(3):
                        raise RuntimeError('event_loop_was_blocked')
                    original(out, event, context)
                with patch.object(module, 'request_log', slow_write):
                    journal = module.RequestJournal(root)
                    token = module.CONTEXT.set({'ordinal': 7, 'kind': 'mario_platformer'})
                    try:
                        journal({'model': 'a', 'status': 'ok', 'seconds': .1})
                    finally:
                        module.CONTEXT.reset(token)
                    try:
                        self.assertTrue(await asyncio.to_thread(started.wait, 1))
                        self.assertFalse((root/'requests/7.jsonl').exists())
                    finally:
                        release.set()
                        await journal.close()
                saved = json.loads((root/'requests/7.jsonl').read_text())
                self.assertEqual((saved['fixture_ordinal'], saved['game']), (7, 'mario_platformer'))
        asyncio.run(run())

    def test_strict_identity_and_probability_support(self):
        body = {'model': 'm-v1', 'answers': {'decision': {'type': 'choice', 'choice': 'b', 'probabilities': {'b': .8, 'a': .2}}}}
        self.assertEqual(decode(row('m'), RECORD, 'decision', body)['value'], 'b')
        body['model'] = 'different-version'
        with self.assertRaisesRegex(AccessError, 'returned_model_version_changed'):
            decode(row('m'), RECORD, 'decision', body)
        body['model'] = 'm-v1'
        body['answers']['decision']['probabilities'] = {'b': .8}
        with self.assertRaises(AccessError):
            decode(row('m'), RECORD, 'decision', body)

    def test_only_small_roundoff_is_corrected_and_audited(self):
        body = {'model': 'm-v1', 'answers': {'decision': {'type': 'choice', 'choice': 'b', 'probabilities': {'b': .8, 'a': .2000001}}}}
        result = decode(row('m'), RECORD, 'decision', body)
        self.assertTrue(result['probability_roundoff']['normalized'])
        self.assertAlmostEqual(sum(p['probability'] for p in result['distribution']), 1.)
        body['answers']['decision']['probabilities']['a'] = .21
        with self.assertRaises(AccessError):
            decode(row('m'), RECORD, 'decision', body)

    def test_public_rounding_band_preserves_relative_native_probabilities(self):
        model = row('m')
        model['config']['probability_policy'] = 'public-compatible'
        body = {'model': 'm-v1', 'answers': {'decision': {'type': 'choice', 'choice': 'b',
                'probabilities': {'b': .8, 'a': .19}}}}
        result = decode(model, RECORD, 'decision', body)
        self.assertAlmostEqual(result['distribution'][0]['probability'], .8/.99)
        self.assertAlmostEqual(result['probability_roundoff']['original_sum'], .99)
        self.assertEqual(body['answers']['decision']['probabilities']['a'], .19)
        body['answers']['decision']['probabilities']['a'] = .1
        with self.assertRaisesRegex(AccessError, 'invalid_probability_sum'):
            decode(model, RECORD, 'decision', body)

    def test_public_choice_uses_native_probability_argmax_and_audits_api_choice(self):
        model = row('m')
        body = {'model': 'm-v1', 'answers': {'decision': {'type': 'choice', 'choice': 'a',
                'probabilities': {'b': .8, 'a': .2}}}}
        with self.assertRaisesRegex(AccessError, 'choice_not_argmax'):
            decode(model, RECORD, 'decision', body)
        model['config']['probability_policy'] = 'public-compatible'
        result = decode(model, RECORD, 'decision', body)
        self.assertEqual(result['value'], 'b')
        self.assertEqual(result['probability_roundoff']['original_choice'], 'a')
        self.assertTrue(result['probability_roundoff']['choice_corrected'])
        body['answers']['decision']['probabilities'] = {'b': .5, 'a': .5}
        self.assertEqual(decode(model, RECORD, 'decision', body)['value'], 'a')

    def test_live_game_and_model_limits_are_atomic_for_direct_duels(self):
        async def run():
            admission = module.GameAdmission(20, {str(i): 5 for i in range(10)})
            async def play(i):
                async with admission.slot([str(i % 10), str((i+1) % 10)]):
                    await asyncio.sleep(.01)
            await asyncio.gather(*(play(i) for i in range(100)))
            self.assertEqual(admission.peak, 20)
            self.assertTrue(all(v <= 5 for v in admission.model_peak.values()))
            self.assertEqual(admission.active, 0)
            self.assertTrue(all(v == 0 for v in admission.by_model.values()))
        asyncio.run(run())

    def test_episode_queue_does_not_consume_execution_timeout_and_work_is_shared(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                arena = module.PublicArena.__new__(module.PublicArena)
                arena.games = module.GameAdmission(1, {'a': 1})
                arena.contract = {'game_execution_timeout_seconds': .05}
                arena.episode_tasks = {}
                arena.existing_episodes = set()
                calls = 0
                async def play(*args):
                    nonlocal calls
                    calls += 1
                    await asyncio.sleep(.01)
                    return {'status': 'complete', 'score': 1, 'trace': []}
                with patch.object(module.GameArena, '_episode', play):
                    async with arena.games.slot(['a']):
                        task = asyncio.create_task(arena._episode(Path(d), 'blackjack', 42, 'a', None))
                        shared = asyncio.create_task(arena._episode(Path(d), 'blackjack', 42, 'a', None))
                        await asyncio.sleep(.08)
                        self.assertFalse(task.done())
                    results = await asyncio.gather(task, shared)
                    self.assertTrue(all(r['status'] == 'complete' for r in results))
                    self.assertEqual(calls, 1)
        asyncio.run(run())

    def test_inheritance_keeps_valid_turn_based_results_and_reruns_realtime(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/'old', Path(d)/'new'
            contract = {'games': ['blackjack', 'snake_navigation'], 'seeds': 1, 'seed_base': 42,
                        'prompt': {}, 'scope': {}, 'concurrency': 2, 'engine_sources': {}}
            plan = module.schedule([module.participant(row(m)) for m in ('a', 'b')], contract['games'], 1, 42)
            module._write(source/'contract.json', contract)
            module._write(source/'plan.json', plan)
            module._write(source/'status.json', {'state': 'paused'})
            module._write(target/'plan.json', plan)
            for fixture in plan['schedule']:
                receipt = {**fixture, 'status': 'complete', 'score_a': .5}
                name = f"{fixture['ordinal']:05d}.json"
                module._write(source/'matches'/name, receipt)
                module._write(source/'summaries'/name, module.GameArena._summary_receipt(receipt))
            receipt = module.inherit_completed(target, source, contract)
            self.assertEqual(receipt['matches'], 1)
            imported = [json.loads(p.read_text()) for p in (target/'matches').glob('*.json')]
            self.assertEqual([r['kind'] for r in imported], ['blackjack'])
            self.assertEqual(len(list((source/'matches').glob('*.json'))), 2)

    def test_native_replicas_route_independently_without_parallel_gpu_calls(self):
        import httpx
        async def run():
            model = row('a')
            model['config'].update(adapter='clef', endpoints=['http://r1/v1/systemone', 'http://r2/v1/systemone'])
            clients = PublicClients({'models': {'a': model, 'future': {'role': 'awaiting_rl_checkpoint'}}})
            active, peak = {}, {}
            async def handler(request):
                host = request.url.host
                active[host] = active.get(host, 0)+1
                peak[host] = max(peak.get(host, 0), active[host])
                await asyncio.sleep(.01)
                active[host] -= 1
                return httpx.Response(200, json={'model': 'a-v1', 'answers': {'decision': {
                    'type': 'choice', 'choice': 'b', 'probabilities': {'a': .1, 'b': .9}}}})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                await asyncio.gather(*(clients.predict(RECORD, 'decision', model='a') for _ in range(10)))
                self.assertEqual(peak, {'r1': 1, 'r2': 1})
                self.assertEqual(clients.model_peak['a'], 2)
                self.assertFalse((await clients.health('future'))['ready'])
            finally:
                await clients.close()
        asyncio.run(run())

    def test_requests_run_across_models_with_maximum_five_per_model(self):
        import httpx
        async def run():
            clients = PublicClients({'models': {m: row(m) for m in ('a', 'b', 'c', 'd')}},
                                    concurrency=20, per_model_concurrency=5)
            async def handler(request):
                body = json.loads(request.content)
                await asyncio.sleep(.02)
                return httpx.Response(200, json={'model': body['model']+'-v1', 'answers': {'decision': {
                    'type': 'choice', 'choice': 'b', 'probabilities': {'a': .1, 'b': .9}}}})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                await asyncio.gather(*(clients.predict(RECORD, 'decision', model=m)
                    for m in ('a', 'b', 'c', 'd') for _ in range(15)))
                self.assertEqual(clients.peak, 20)
                self.assertEqual(set(clients.model_peak.values()), {5})
            finally:
                await clients.close()
        asyncio.run(run())

    def test_529_retries_and_cancellation_is_not_an_unknown_error(self):
        import httpx
        async def run():
            events = []
            clients = PublicClients({'models': {'a': row('a')}}, on_request=events.append)
            count = 0
            async def handler(request):
                nonlocal count
                count += 1
                if count == 1:
                    return httpx.Response(529, json={'error': 'overloaded'})
                return httpx.Response(200, json={'model': 'a-v1', 'answers': {'decision': {
                    'type': 'choice', 'choice': 'b', 'probabilities': {'a': .1, 'b': .9}}}})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                with patch('blink_arena.public_models.asyncio.sleep', return_value=None):
                    await clients.predict(RECORD, 'decision', model='a')
                self.assertEqual([e['status'] for e in events], ['error', 'ok'])
                self.assertEqual(events[0]['error'], 'http_529')
                async def cancelled(request):
                    raise asyncio.CancelledError()
                await clients.http.aclose()
                clients.http = httpx.AsyncClient(transport=httpx.MockTransport(cancelled))
                with self.assertRaises(asyncio.CancelledError):
                    await clients.predict(RECORD, 'decision', model='a')
                self.assertEqual(events[-1]['error'], 'request_cancelled')
                self.assertEqual(events[-1]['status'], 'cancelled')
                self.assertEqual(clients.active, 0)
            finally:
                await clients.close()
        asyncio.run(run())

    def test_eight_seeds_and_swapped_seats(self):
        players = [module.participant(row(m)) for m in ('a', 'b', 'c')]
        plan = module.schedule(players, ['othello_6x6', 'blackjack'], 8, 42)
        self.assertEqual(len(plan['schedule']), 72)
        self.assertEqual({f['seed'] for f in plan['schedule']}, set(range(42, 50)))
        counts = {}
        for f in plan['schedule']:
            counts.setdefault((f['kind'], f['seed'], f['a'], f['b']), []).append(f['leg'])
        for (game, *_), legs in counts.items():
            self.assertEqual(legs, [0, 1] if game == 'othello_6x6' else [0])

    def test_error_receipts_are_not_wins_or_draws(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = module.schedule([module.participant(row(m)) for m in ('a', 'b')], ['blackjack'], 8, 42)
            module._write(root/'plan.json', plan)
            module._write(root/'summaries/00000.json', {**plan['schedule'][0], 'status': 'error', 'score_a': None})
            result = module.report(root)
            self.assertEqual(result['errors'], 1)
            for r in result['metrics']:
                self.assertEqual((r['wins'], r['draws'], r['errors'], r['pending']), (0, 0, 1, 7))

    def test_credentials_are_allowlisted_and_provider_echo_is_scrubbed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'private.env'
            p.write_text('FAKE_TEST_KEY=secret-fixture\nUNRELATED=ignore-me\n')
            self.assertEqual(load_credentials(p, {'FAKE_TEST_KEY'}), {'FAKE_TEST_KEY': 'secret-fixture'})
            self.assertEqual(clean({'authorization': 'secret-fixture', 'error': 'echo secret-fixture'}, ['secret-fixture']), {'error': 'echo [REDACTED]'})

    def test_enrollment_appends_without_changing_old_fixtures(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = {m: row(m) for m in ('a', 'b')}
            contract = {'roster': {'models': rows}, 'games': ['blackjack', 'othello_6x6'],
                        'seeds': 8, 'seed_base': 42}
            old = module.schedule([module.participant(v) for v in rows.values()], contract['games'], 8, 42)
            module._write(root/'plan.json', old)
            added = module.append_enrollment(root, contract, row('oneshot-rl-step1'))
            new = module._read(root/'plan.json')
            self.assertEqual(new['schedule'][:len(old['schedule'])], old['schedule'])
            self.assertEqual(added, 48)
            self.assertEqual(module.effective_contract(root, contract)['roster']['models']['oneshot-rl-step1'], row('oneshot-rl-step1'))
            arena = module.PublicArena.__new__(module.PublicArena)
            arena.contract = contract
            arena.registered = {p['id']: p for p in new['participants']}
            arena._validate_plan(new)
            new['schedule'][0]['seed'] += 1
            with self.assertRaisesRegex(ValueError, 'saved_schedule_changed'):
                arena._validate_plan(new)
            with self.assertRaisesRegex(ValueError, 'already_registered'):
                module.append_enrollment(root, contract, row('oneshot-rl-step1'))

    def test_environment_success_excludes_errors_and_keeps_pending_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = module.schedule([module.participant(row(m)) for m in ('a', 'b')], ['blackjack'], 8, 42)
            module._write(root/'plan.json', plan)
            for seed, status, outcome in [(42, 'complete', 'win'), (43, 'complete', 'loss'), (44, 'error', None)]:
                module._write(root/'episode_summaries'/module.GameArena._episode_name('blackjack', seed, 'a'),
                              {'status': status, 'outcome': outcome})
            result = module.report(root)['metrics'][0]
            self.assertEqual(result['environment_errors'], 1)
            self.assertEqual(result['environment_pending'], 5)
            self.assertEqual(result['environment_success_rate_completed'], .5)
            self.assertEqual(result['environment_success_rate_lower_bound'], .125)

    def test_access_failure_opens_circuit_before_more_requests(self):
        import httpx
        async def run():
            clients = PublicClients({'models': {'a': row('a')}})
            seen = []
            async def handler(request):
                seen.append(request)
                return httpx.Response(401, json={'error': 'unauthorized'})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                with self.assertRaisesRegex(AccessError, 'http_401'):
                    await clients.predict(RECORD, 'decision', model='a')
                with self.assertRaisesRegex(AccessError, 'model_access_circuit_open'):
                    await clients.predict(RECORD, 'decision', model='a')
                self.assertFalse((await clients.health('a'))['ready'])
                self.assertEqual(len(seen), 1)
            finally:
                await clients.close()
        asyncio.run(run())

    def test_global_http_concurrency_and_original_candidate_order(self):
        import httpx
        async def run():
            roster = {'models': {i: row(i) for i in ('a', 'b', 'c')}}
            clients = PublicClients(roster, concurrency=2)
            seen = []
            async def handler(request):
                body = json.loads(request.content)
                seen.append(list(body['questions']['decision']['criteria']))
                await asyncio.sleep(.01)
                return httpx.Response(200, json={'model': body['model']+'-v1', 'answers': {'decision': {
                    'type': 'choice', 'choice': 'b', 'probabilities': {'a': .1, 'b': .9}}}})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                await asyncio.gather(*(clients.predict(RECORD, 'decision', model=m) for m in ('a', 'b', 'c')*3))
                self.assertEqual(clients.peak, 2)
                self.assertTrue(all(order == ['b', 'a'] for order in seen))
            finally:
                await clients.close()
        asyncio.run(run())

    def test_state_serialization_preserves_values_arrays_and_candidate_order(self):
        import httpx
        async def run():
            clients = PublicClients({'models': {'a': row('a')}})
            record = json.loads(json.dumps(RECORD))
            record['state'] = {'z': [{'b': 2, 'a': 1}, 3, 2, 1], 'a': {'y': True, 'x': None}}
            async def handler(request):
                body = json.loads(request.content)
                self.assertEqual(body['state'], record['state'])
                self.assertEqual(list(body['state']), ['a', 'z'])
                self.assertEqual(list(body['state']['z'][0]), ['a', 'b'])
                self.assertEqual(list(body['questions']['decision']['criteria']), ['b', 'a'])
                return httpx.Response(200, json={'model': 'a-v1', 'answers': {'decision': {
                    'type': 'choice', 'choice': 'b', 'probabilities': {'a': .1, 'b': .9}}}})
            await clients.http.aclose()
            clients.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                await clients.predict(record, 'decision', model='a')
            finally:
                await clients.close()
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
