"""Local imports validate before writing and never echo rejected input values."""
import json
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'import_leaderboard.py'


def document(score=0.8):
    return {
        'schema_version': 'jev.leaderboard.v1', 'benchmark_id': 'jevbench',
        'title': 'JevBench', 'version': 'test-v1', 'metric': 'accuracy',
        'rows': [{'model_id': 'fixture-model', 'model_name': 'Fixture', 'score': score,
                  'metrics': {'accuracy': score, 'brier': None, 'ece': None}}],
    }


def invoke(tmp_path, body):
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(body), encoding='utf-8')
    target = tmp_path / 'data'
    result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--leaderboard-dir', str(target)],
                            cwd=tmp_path, capture_output=True, text=True)
    return result, target


def test_cli_import_and_archive(tmp_path):
    first, target = invoke(tmp_path, document(0.8))
    assert first.returncode == 0, first.stderr
    result_path = target / 'jevbench.json'
    assert json.loads(result_path.read_text())['rows'][0]['score'] == 0.8
    second, _ = invoke(tmp_path, document(0.9))
    assert second.returncode == 0, second.stderr
    assert json.loads(result_path.read_text())['rows'][0]['score'] == 0.9
    archives = list((target / 'history').glob('jevbench-*.json'))
    assert any(json.loads(p.read_text())['rows'][0]['score'] == 0.8 for p in archives)


def test_cli_rejects_unknown_fields_without_echoing_input(tmp_path):
    body = document()
    marker = 'invalid-private-value-for-redaction-test'
    body['api_key'] = marker
    result, target = invoke(tmp_path, body)
    assert result.returncode == 2
    assert marker not in result.stdout + result.stderr
    assert 'extra_forbidden' in result.stderr
    assert not (target / 'jevbench.json').exists()


def test_cli_invalid_score_preserves_existing_result(tmp_path):
    first, target = invoke(tmp_path, document(0.7))
    assert first.returncode == 0, first.stderr
    previous = (target / 'jevbench.json').read_bytes()
    failed, _ = invoke(tmp_path, document(4.2))
    assert failed.returncode == 2
    assert (target / 'jevbench.json').read_bytes() == previous
