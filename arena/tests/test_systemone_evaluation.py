import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from argparse import Namespace
import asyncio
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('systemone_evaluation',
    Path(__file__).resolve().parents[1] / 'scripts/evaluate_systemone.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class EvaluationReportingTests(unittest.TestCase):
    def test_interrupted_comparison_keeps_exact_completed_seeds_only(self):
        # Stop at client construction: test the real CLI planning path without
        # inference traffic or replacing the engine/opponent.
        class PlanCaptured(Exception):
            pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); baseline = root / 'baseline'; baseline.mkdir()
            (baseline / 'episodes').mkdir()
            jobs = [{'id': f'merge_2048-{seed}', 'game': 'merge_2048', 'seed': seed}
                    for seed in (910, 911, 912)]
            plan = {'model': 'jev-policy', 'endpoint': 'http://model/v1/systemone',
                    'concurrency': 2, 'jobs': jobs}
            (baseline / 'plan.json').write_text(json.dumps(plan))
            (baseline / 'episodes' / (jobs[0]['id'] + '.json')).write_text('{"status":"complete","outcome":"loss"}')
            (baseline / 'episodes' / (jobs[1]['id'] + '.json')).write_text('{"status":"error"}')
            args = Namespace(out=str(root / 'new'), model=plan['model'], endpoint=plan['endpoint'],
                games=['merge_2048'], episodes=8, seed_base=42, concurrency=2,
                input_format='intent-v2', baseline_plan=str(baseline / 'plan.json'), completed_baseline_only=True)
            with patch.dict(evaluation.os.environ), patch.object(evaluation, 'SystemOneClient', side_effect=PlanCaptured), self.assertRaises(PlanCaptured):
                asyncio.run(evaluation.run(args))
            actual = json.loads((root / 'new/plan.json').read_text())
            self.assertEqual(actual['jobs'], jobs[:1])
            self.assertEqual(actual['episodes_by_game'], {'merge_2048': 1})
            self.assertIsNone(actual['episodes_per_game'])
            self.assertEqual(json.loads((baseline / 'plan.json').read_text()), plan)
            self.assertEqual(actual['prompt_config'], json.loads((root / 'new/prompt-config.json').read_text()))

    def test_mismatched_checkpoint_rejected_before_any_episode(self):
        import httpx
        args=Namespace(model='jev-v9a17-input',endpoint='http://fixture/v1/systemone',
                       games=['uno'],episodes=8,seed_base=42,concurrency=2,
                       expected_model_path='/expected/checkpoint')
        async def get_health(self, url):
            return httpx.Response(200,json={'model':args.model,'model_path':'/wrong/checkpoint',
                'mode':'direct','attention_mode':'bidirectional_prompt'},request=httpx.Request('GET',url))
        with tempfile.TemporaryDirectory() as folder, patch.dict(evaluation.os.environ), \
             patch.object(evaluation.httpx.AsyncClient,'get',get_health), \
             patch.object(evaluation,'SystemOneClient') as model_client:
            args.out=folder
            with self.assertRaisesRegex(ValueError,'checkpoint_service_identity_mismatch'):
                asyncio.run(evaluation.run(args))
            model_client.assert_not_called()
            self.assertFalse((Path(folder)/'plan.json').exists())

    def test_response_percentiles_exclude_errors_but_count_them(self):
        result = evaluation.latency_stats([
            {'status': 'ok', 'seconds': 1}, {'status': 'ok', 'seconds': 3},
            {'status': 'error', 'seconds': 90, 'code': 'timeout'}])
        self.assertEqual(result['count'], 3)
        self.assertEqual(result['errors'], {'timeout': 1})
        self.assertEqual(result['mean_seconds'], 2)
        self.assertEqual(result['p50_seconds'], 2)
        self.assertAlmostEqual(result['p95_seconds'], 2.9)
        self.assertEqual(result['max_seconds'], 3)

    def test_no_successful_responses_have_null_latency(self):
        result = evaluation.latency_stats([{'status': 'error', 'seconds': 1, 'code': 'http_503'}])
        self.assertIsNone(result['mean_seconds'])
        self.assertIsNone(result['p95_seconds'])

    def test_full_planned_denominator_and_separate_error_levels(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'episodes').mkdir()
            plan = {'model': 'jev-policy', 'endpoint': 'http://model/v1/systemone',
                    'concurrency': 2, 'games': ['merge_2048'],
                    'jobs': [{'id': str(i), 'game': 'merge_2048'} for i in range(8)]}
            rows = [
                {'status': 'complete', 'outcome': 'win', 'seconds': 8,
                 'timings': {'http': [{'status': 'ok', 'seconds': .5},
                                      {'status': 'error', 'seconds': .1, 'code': 'http_503'}],
                             'request': [{'status': 'ok', 'seconds': 2}],
                             'decision': [{'status': 'ok', 'seconds': 4}]}},
                {'status': 'error', 'outcome': 'error', 'seconds': 4,
                 'error_info': {'code': 'invalid_response'}},
                {'status': 'complete', 'outcome': 'budget_exhausted', 'seconds': 2}]
            for i, row in enumerate(rows):
                (out / 'episodes' / f'{i}.json').write_text(json.dumps(row))
            result = evaluation.report(out, plan)
            game = result['games'][0]
            self.assertEqual(game['success_rate'], 1 / 8)
            self.assertEqual(game['pending'], 5)
            self.assertEqual(game['errors'], 1)
            self.assertEqual(game['budget_exhausted'], 1)
            self.assertEqual(game['http_errors'], 1)
            self.assertEqual(game['error_counts'], {'invalid_response': 1})
            self.assertEqual(game['http_mean_seconds'], .5)
            self.assertEqual(game['request_mean_seconds'], 2)
            self.assertEqual(game['decision_mean_seconds'], 4)
            self.assertEqual(result['status'], 'running')
