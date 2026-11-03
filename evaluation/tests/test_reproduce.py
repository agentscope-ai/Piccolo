"""Validate reproducible command plans and failure handling without model calls."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'reproduce.py'
spec = importlib.util.spec_from_file_location('reproduce', SCRIPT)
reproduce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproduce)


class ReproductionTests(unittest.TestCase):
    def test_all_official_commands_are_planned_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'run'
            with patch.dict('os.environ', {'PICCOLO_API_KEY': 'private-fixture-value'}):
                result = subprocess.run([sys.executable, SCRIPT, '--base-url', 'http://127.0.0.1:18604',
                                         '--model', 'Piccolo-4B', '--output', out, '--dry-run'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads((out / 'plan.json').read_text())
            self.assertEqual({x['benchmark'] for x in plan}, set(reproduce.SOURCES))
            self.assertTrue(all(len(item['revision']) == 40 for item in plan))
            text = '\n'.join(p.read_text() for p in out.rglob('*.json')) + result.stdout
            self.assertNotIn('private-fixture-value', text)
            self.assertIn('PICCOLO_API_KEY', text)
            jev = next(x for x in plan if x['benchmark'] == 'jevbench')['commands'][0]
            tasks = jev[jev.index('--tasks') + 1]
            self.assertTrue(all(name in tasks for name in ('original.jsonl', 'easy.jsonl', 'hard.jsonl')))

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'keep.json'
            target.write_text('existing results')
            result = subprocess.run([sys.executable, SCRIPT, '--base-url', 'http://127.0.0.1:18604',
                                     '--model', 'Piccolo-4B', '--output', temp, '--dry-run'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), 'existing results')

    def test_endpoint_rejects_path_and_inline_credentials(self):
        for origin in ('http://user:secret@localhost:9000', 'http://localhost:9000/v1/systemone'):
            result = subprocess.run([sys.executable, SCRIPT, '--base-url', origin, '--model', 'Piccolo-4B', '--dry-run'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_prediction_errors_fail_the_run(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            with self.assertRaises(RuntimeError):
                reproduce.validate_run('data', output)
            (output / 'results.jsonl').write_text(json.dumps({'status': 'error', 'error': 'timeout'}) + '\n')
            with self.assertRaises(RuntimeError):
                reproduce.validate_run('data', output)
            (output / 'results.jsonl').write_text(json.dumps({'ok': True, 'answer': 'A'}) + '\n')
            reproduce.validate_run('data', output)

    def test_harness_question_failure_is_not_a_completed_evaluation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / 'predictions-hard.jsonl').write_text(json.dumps({
                'id': 'fixture', 'question_results': {'review': {'status': 'failed'}}}) + '\n')
            with self.assertRaises(RuntimeError):
                reproduce.validate_run('harness', output)

    def test_harness_hard_and_soft_use_their_official_output_shapes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / 'predictions-hard.jsonl').write_text(json.dumps({
                'id': 'hard', 'question_results': {'decision': {'status': 'valid'}}}) + '\n')
            soft = output / 'predictions-soft.jsonl'
            soft.write_text(json.dumps({'task_id': 'soft', 'observation': {'status': 'valid'}}) + '\n')
            reproduce.validate_run('harness', output)
            soft.write_text(json.dumps({'task_id': 'soft', 'observation': {'status': 'failed'}}) + '\n')
            with self.assertRaises(RuntimeError):
                reproduce.validate_run('harness', output)


if __name__ == '__main__':
    unittest.main()
