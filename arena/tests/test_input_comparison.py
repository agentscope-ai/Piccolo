import importlib.util
import json
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location('input_comparison',
    Path(__file__).resolve().parents[1] / 'scripts/compare_model_inputs.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_completed_baseline_denominator_and_retry_errors_are_visible():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); baseline = root / 'baseline'; baseline.mkdir()
        out = root / 'new'; (out / 'episodes-run').mkdir(parents=True)
        game = {'game': 'mario_platformer', 'planned': 8, 'finished': 3, 'wins': 1,
                'pending': 5, 'success_rate': 1 / 8, 'errors': 0, 'http_errors': 2}
        (baseline / 'summary.json').write_text(json.dumps({'status': 'stopped', 'concurrency': 2, 'games': [game]}))
        (out / 'episodes-run/summary.json').write_text(json.dumps({'status': 'complete',
            'games': [{**game, 'planned': 3, 'pending': 0, 'http_errors': 1}]}))
        # A successful service may omit usage; no fake token estimate is added.
        samples = [{'game': 'mario_platformer', 'format': 'compact', 'status': 'ok', 'seconds': 2}]
        result = comparison.report(baseline, out, ['mario_platformer'], samples, completed_only=True)
        row = result['games'][0]
        assert row['original']['planned'] == 3
        assert row['original']['success_rate'] == 1 / 3
        assert row['same_input']['compact']['input_tokens'] is None
        assert result['status'] == 'complete'
        assert '0/0 | 2/1' in (out / 'comparison.md').read_text()
        assert json.loads((baseline / 'summary.json').read_text())['games'][0]['planned'] == 8
