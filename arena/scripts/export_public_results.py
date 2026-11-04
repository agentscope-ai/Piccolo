#!/usr/bin/env python3
"""Read public result APIs and export portable, allow-listed result snapshots.

No model requests are made. Raw responses, model endpoints and local paths are
never written. Use --check to validate an existing export without networking.
"""
from __future__ import annotations

import argparse
import json
import ipaddress
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blink_arena.schemas import LeaderboardDocument  # noqa: E402
from blink_arena.paths import leaderboard_directory  # noqa: E402

BENCHMARKS = ('jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench')
ENGLISH_AXES = {
    'adequacy': 'Adequacy', 'adversarial': 'Adversarial judgment',
    'ambiguous': 'Ambiguity', 'extraction': 'Extraction', 'fact': 'Facts',
    'intent': 'Intent', 'judge_hard': 'Hard judgment', 'long_policy': 'Long policy',
    'multi_hop': 'Multi-hop reasoning', 'ordinal': 'Ordinal scoring',
    'policy': 'Policy', 'probability': 'Probability', 'routing': 'Routing',
    'routing_hard': 'Hard routing', 'temporal_numeric': 'Time and numbers',
    'tool_selection': 'Tool selection', 'tradeoff': 'Trade-offs', 'trap': 'Trap detection',
    'knowledge': 'Knowledge and reasoning', 'language': 'Language comprehension',
    'retrieval': 'Retrieval and classification', 'tools': 'Tools and automation',
    'arts': 'Arts and aesthetics',
}
METRICS = (
    'accuracy', 'acc', 'brier', 'ece', 'accuracy_n', 'correct', 'accuracy_missing',
    'brier_n', 'ece_n', 'ece_bins', 'calibration_n', 'calibration_observed',
    'calibration_estimated', 'calibration_missing',
)
ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$')
PRIVATE = re.compile(r'(?:/(?:mnt|root|home|tmp|var|data|Users)/|[A-Za-z]:\\|(?:https?|cpfs|oss|file|s3)://|'
                     r'\bcpfs\b|sk-[A-Za-z0-9]{12,}|Bearer\s+\S+|\b(?:AKIA[A-Z0-9]{16}|LTAI[A-Za-z0-9]{16,})\b|'
                     r'\blocalhost\b|\b[\w.-]+\.dsw-gateway-[\w.-]+\b|\b[\w.-]+\.(?:internal|local)\b)', re.I)
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
IPV6 = re.compile(r'(?<![A-Za-z0-9])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?![A-Za-z0-9])')
SECRET_KEYS = {'api_key', 'token', 'access_token', 'access_key', 'secret_key', 'authorization',
               'credential', 'credentials', 'endpoint', 'password', 'model_path', 'served_model',
               'tokenizer_path', 'source_url', 'source_path', 'source_root', 'source_files',
               'checkpoint_path', 'runner_pid', 'username', 'user_name'}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def public_text(value, default=''):
    if not isinstance(value, str):
        return default
    if PRIVATE.search(value):
        raise ValueError('private location or credential-like text in a public field')
    for match in [*IPV4.finditer(value), *IPV6.finditer(value)]:
        try:
            ipaddress.ip_address(match.group())
        except ValueError:
            continue
        raise ValueError('network address in a public field')
    return value


def ident(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('invalid public identifier')
    return value


def clean_scalars(source, fields):
    result = {}
    for key in fields:
        if key not in source:
            continue
        value = source[key]
        if isinstance(value, str):
            result[key] = public_text(value)
        elif value is None or type(value) is bool or finite(value):
            result[key] = value
        else:
            raise ValueError('unexpected non-scalar public field: ' + key)
    return result


def assert_public(value):
    """Fail closed after the allow-list projection; do not silently redact results."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                raise ValueError('private field in export')
            assert_public(item)
    elif isinstance(value, list):
        for item in value:
            assert_public(item)
    elif isinstance(value, str):
        public_text(value)
    elif type(value) in (int, float) and not finite(value):
        raise ValueError('non-finite public result')


def export_benchmark(benchmark):
    benchmark_id = ident(benchmark['id'])
    if benchmark_id not in BENCHMARKS:
        raise ValueError('unknown benchmark')
    source_rows = benchmark.get('display_rows', [])
    first = next(iter(source_rows), {})
    rows = []
    for source in source_rows:
        original_status = source.get('status', 'pending')
        complete = original_status in ('complete', 'complete_with_errors')
        status = 'complete' if complete else ('error' if original_status in ('error', 'failed', 'blocked')
                                             else 'pending' if original_status in ('pending', 'queued') else 'running')
        metrics = {}
        if complete:
            display = source.get('display_metrics') or {}
            metrics = {key: display[key] for key in METRICS if finite(display.get(key))}
            calibration = source.get('calibration') or {}
            if benchmark_id == 'jevbench':
                if source.get('metric') == 'accuracy' and finite(source.get('score')):
                    metrics['accuracy'] = source['score']
                for key in ('brier', 'ece'):
                    if finite(calibration.get(key)):
                        metrics[key] = calibration[key]
                        if finite(calibration.get('questions')):
                            metrics[key + '_n'] = calibration['questions']
        radar = source.get('radar') or {}
        axes = []
        for axis in radar.get('axes', []):
            axis_id = ident(axis['id'])
            axes.append({
                'id': axis_id,
                'label_en': public_text(axis.get('label_en')) or ENGLISH_AXES.get(axis_id, axis_id.replace('_', ' ').capitalize()),
                'label_zh': public_text(axis.get('label_zh') or axis.get('label')) or axis_id,
                'score': axis.get('score') if complete else None,
                'metric': public_text(axis.get('metric') or radar.get('metric')) or None,
                'samples': axis.get('samples'),
            })
        notes = ['Imported public aggregate results; no evaluation is started by this snapshot.']
        if original_status == 'complete_with_errors':
            notes.append('Evaluation completed with errors; failed questions remain in the planned denominator.')
        if not complete:
            notes.append('Evaluation incomplete: final score, calibration metrics and dimension scores are withheld.')
        probability_source = public_text(source.get('probability_source'))
        if probability_source:
            notes.append('Probability source: ' + probability_source)
        if benchmark_id == 'decisionindex':
            notes.append('Native quick-subset index (0–100); classification ACC is separate. Brier/ECE use available single-label classification distributions.')
        if benchmark_id == 'harnessjevbench':
            notes.append('Hard score: native task-weighted mean across two views. ACC: both views fully correct. Soft radar axis: 1 − TV; excluded from the Hard total.')
        rows.append({
            'model_id': ident(source['model_key']),
            'model_name': public_text(source.get('model')) or source['model_key'],
            'score': source.get('score') if complete else None,
            'status': status,
            'metrics': metrics,
            'axes': axes,
            'samples': source.get('samples', 0),
            'errors': source.get('errors', 0),
            'evaluated_at': public_text(source.get('evaluated_at')) or None,
            'protocol': public_text(source.get('runtime_protocol')) or 'imported',
            'notes': notes,
        })
    document = LeaderboardDocument.model_validate({
        'schema_version': 'jev.leaderboard.v1', 'benchmark_id': benchmark_id,
        'title': public_text(benchmark.get('title')) or benchmark_id,
        'version': public_text(benchmark.get('version') or first.get('benchmark_version')) or 'unregistered',
        'metric': public_text(first.get('metric')) or 'score',
        'score_scale': first.get('score_scale', [0, 1]),
        'higher_is_better': True,
        'axis_scale': (first.get('radar') or {}).get('scale', [0, 1]),
        'rows': rows,
    }).model_dump(mode='json')
    assert_public(document)
    return document


STABILITY = ('decisions', 'probability_decisions', 'probability_coverage', 'agreement_rate',
             'unanimous_rate', 'mean_probability_variance', 'mean_js_distance', 'probability_stability')
PARTICIPANT = ('id', 'name', 'provider', 'policy')
GAME = ('id', 'name', 'mode', 'engine_supported')
RANK = ('id', 'name', 'rating', 'coverage', 'required_games', 'coverage_complete',
        'overall_eligible', 'played', 'wins', 'draws', 'losses', 'errors', 'provisional', 'rank')
FIXTURE = ('ordinal', 'kind', 'seed', 'a', 'b', 'leg', 'a_side', 'mode')
MATCH = FIXTURE + ('status', 'score_a', 'winner', 'steps', 'seconds', 'finished_at')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def check(output):
    for benchmark in BENCHMARKS:
        document = json.loads((output / (benchmark + '.json')).read_text())
        assert_public(document)
        model = LeaderboardDocument.model_validate(document)
        if model.benchmark_id != benchmark:
            raise ValueError('benchmark ID and filename differ')
        for row in model.rows:
            if row.status != 'complete' and (row.score is not None or any(axis.score is not None for axis in row.axes)):
                raise ValueError('unfinished evaluation exposes a final score')
        print(f'{benchmark}: {len(model.rows)} models; schema and public-field checks passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-root', help='Public API root including any route prefix, ending in /api')
    parser.add_argument('--leaderboard-dir', '--output', dest='output', type=Path,
                        help='统一榜单目录，默认 JEV_LEADERBOARD_DIR 或仓库 leaderboard/（--output 为兼容别名）')
    parser.add_argument('--check', action='store_true', help='Validate saved snapshots without making any requests')
    args = parser.parse_args()
    args.output = leaderboard_directory(args.output)
    if args.check:
        check(args.output)
        return
    address = urlsplit(args.api_root or '')
    if address.scheme not in ('http', 'https') or not address.netloc or address.username or address.password or address.query or address.fragment:
        parser.error('--api-root must be an HTTP(S) API URL without credentials, query or fragment')
    def get(endpoint):
        with urlopen(args.api_root.rstrip('/') + '/' + endpoint, timeout=30) as response:
            return json.loads(response.read(32 * 1024 * 1024))
    source = get('leaderboard')
    documents = {b['id']: export_benchmark(b) for b in source['benchmarks'] if b.get('id') in BENCHMARKS}
    if set(documents) != set(BENCHMARKS):
        raise ValueError('source is missing a requested benchmark')
    # Project and validate every response before writing any export.
    for benchmark, document in documents.items():
        write_json(args.output / (benchmark + '.json'), document)
    check(args.output)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Response bodies and request URLs must not leak via chained exceptions.
        print('Export failed: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
