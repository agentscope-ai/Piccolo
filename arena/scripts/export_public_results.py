#!/usr/bin/env python3
"""Read public result APIs and export portable, allow-listed result snapshots.

No model requests are made. Raw responses, model endpoints and local paths are
never written. Use --check to validate an existing export without networking.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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


def comparison(source):
    if not isinstance(source, dict):
        return None
    result = clean_scalars(source, ('revision', 'kind', 'metric', 'score_label', 'higher_is_better',
        'comparison', 'comparison_rule', 'opponent_policy', 'seat_rule', 'engine_revision',
        'time_scoring_revision', 'budget_rule', 'label'))
    result['score_fields'] = [public_text(x) for x in source.get('score_fields', [])]
    result['decision_policy'] = clean_scalars(source.get('decision_policy') or {},
        ('revision', 'repeat_count', 'option_order', 'reason'))
    return result


def game_row(source):
    return {**clean_scalars(source, GAME), 'comparison': comparison(source.get('comparison'))}


def episode_result(source):
    result = clean_scalars(source, ('score', 'outcome', 'score_label', 'higher_is_better',
        'terminal', 'budget_exhausted', 'reused', 'episode_id'))
    if 'comparison_key' in source:
        if not all(finite(v) for v in source['comparison_key']):
            raise ValueError('invalid comparison key')
        result['comparison_key'] = source['comparison_key']
    time_score = source.get('time_score')
    if isinstance(time_score, dict):
        result['time_score'] = clean_scalars(time_score, ('utility', 'terminal_reward', 'progress',
            'native_progress', 'elapsed_seconds', 'time_limit', 'time_scale_seconds',
            'time_source', 'completed', 'time_tiebreak', 'scoring_revision'))
    return result


def ranked_row(source):
    result = clean_scalars(source, RANK)
    result['stability'] = clean_scalars(source.get('stability') or {}, STABILITY)
    return result


def match_row(source):
    result = clean_scalars(source, MATCH)
    result['seats'] = {public_text(k): ident(v) for k, v in (source.get('seats') or {}).items()}
    result['stability'] = {ident(k): clean_scalars(v, STABILITY) for k, v in (source.get('stability') or {}).items()}
    if isinstance(source.get('comparison'), dict):
        result['comparison'] = comparison(source['comparison'])
    for key in ('result_a', 'result_b'):
        if isinstance(source.get(key), dict):
            result[key] = episode_result(source[key])
    # Paired games expose only scalar outcomes, never execution receipts or traces.
    for side in ('a_score', 'b_score'):
        if finite(source.get(side)):
            result[side] = source[side]
    return result


def export_arena(source, exported_at):
    result = clean_scalars(source, ('state', 'updated_at', 'run_id', 'completed', 'planned', 'scored'))
    result.update({'schema_version': 'jev.arena.snapshot.v1', 'archived_protocol': True,
                   'managed_externally': False, 'controls_available': False})
    protocol = source.get('protocol') or {}
    result['protocol'] = clean_scalars(protocol, (
        'revision', 'engine_revision', 'seeds', 'seed_base', 'initial_rating', 'k',
        'rating_rule', 'paired_rule', 'board_rule', 'execution_order', 'arena_revision',
        'decision_policy', 'episode_revision', 'direct_revision', 'direct_rule',
        'baseline_registered_at', 'run_type', 'previous_scores_reused'))
    result['protocol']['participants'] = [clean_scalars(p, PARTICIPANT) for p in protocol.get('participants', [])]
    for key in ('kinds', 'baseline_ids'):
        result['protocol'][key] = [ident(v) for v in protocol.get(key, [])]
    result['protocol']['schedule'] = [clean_scalars(m, FIXTURE) for m in protocol.get('schedule', [])]
    result['protocol']['game_engine_revisions'] = {ident(k): public_text(v) for k, v in protocol.get('game_engine_revisions', {}).items()}
    options = source.get('options') or {}
    result['options'] = {'participants': [clean_scalars(p, PARTICIPANT) for p in options.get('participants', [])],
                         'games': [game_row(g) for g in options.get('games', [])]}
    fixed = source.get('fixed_config') or {}
    result['fixed_config'] = clean_scalars(fixed, ('revision', 'seed_base', 'seeds', 'legs', 'single_player_episodes_reused', 'engine_revision', 'concurrency'))
    result['fixed_config']['games'] = [game_row(g) for g in fixed.get('games', [])]
    result['fixed_config']['baseline'] = [clean_scalars(p, PARTICIPANT) for p in fixed.get('baseline', [])]
    result['overall'] = [ranked_row(r) for r in source.get('overall', [])]
    result['by_game'] = {ident(k): [ranked_row(r) for r in rows] for k, rows in source.get('by_game', {}).items()}
    result['matches'] = [match_row(m) for m in source.get('matches', [])]
    progress = source.get('progress') or {}
    result['progress'] = clean_scalars(progress, ('state', 'updated_at', 'concurrency', 'run_id', 'completed', 'planned', 'scored', 'errors', 'remaining', 'percent', 'elapsed_seconds'))
    baseline = source.get('baseline_progress') or {}
    result['baseline_progress'] = clean_scalars(baseline, ('state', 'completed', 'planned', 'errors'))
    result['baseline_progress']['participants'] = [clean_scalars(p, ('id', 'name', 'state', 'completed', 'planned', 'coverage', 'required_games', 'errors')) for p in baseline.get('participants', [])]
    result['snapshot'] = {
        'exported_at': exported_at,
        'match_history_count': len(result['matches']),
        'match_history_complete': len(result['matches']) == result.get('completed'),
        'replays_included': False,
        'note': 'Read-only historical aggregates. Recent-match summaries may be truncated by the source API. Replay traces are not included.',
    }
    assert_public(result)
    validate_arena(result)
    return result


def validate_arena(result):
    assert_public(result)
    if result.get('schema_version') != 'jev.arena.snapshot.v1':
        raise ValueError('unknown Arena snapshot schema')
    games = {ident(g['id']) for g in result['fixed_config']['games']}
    models = {ident(r['id']) for r in result['overall']}
    if set(result['by_game']) != games:
        raise ValueError('Arena game coverage differs from the fixed configuration')
    for rows in [result['overall'], *result['by_game'].values()]:
        if {r['id'] for r in rows} != models:
            raise ValueError('Arena model identities differ across rankings')
        for row in rows:
            if row['wins'] + row['draws'] + row['losses'] != row['played']:
                raise ValueError('Arena settled outcome counts disagree')
    for match in result['matches']:
        if match['kind'] not in games or not {match['a'], match['b']} <= models:
            raise ValueError('Arena match references an unknown identity')


def validate_replays(arena, replay):
    assert_public(replay)
    if replay.get('run_id') != arena.get('run_id'):
        raise ValueError('replay archive belongs to a different Arena run')
    fixtures = {item['ordinal']: item for item in arena['protocol']['schedule']}
    recorded = {item['ordinal']: item for item in replay.get('matches', [])}
    if len(recorded) != len(replay.get('matches', [])) or set(recorded) != set(fixtures):
        raise ValueError('replay archive does not cover the registered schedule')
    episodes = replay.get('episodes', {})
    replays = replay.get('replays', {})
    if len(replays) != len(recorded):
        raise ValueError('replay count differs from the match count')
    for ordinal, fixture in fixtures.items():
        for key in FIXTURE:
            if fixture.get(key) != recorded[ordinal].get(key):
                raise ValueError('replay match identity differs from the Arena schedule')
        item = replays.get(f'{ordinal:05d}')
        if not item or any(item.get(key) != fixture.get(key) for key in FIXTURE):
            raise ValueError('replay stream identity differs from the Arena schedule')
        for stream in item.get('streams', []):
            if 'episode_id' in stream:
                episode = episodes.get(stream['episode_id'])
                if not episode or episode.get('kind') != fixture['kind'] or episode.get('participant') != stream.get('participant'):
                    raise ValueError('replay episode reference is missing or inconsistent')
    for match in arena['matches']:
        saved = recorded[match['ordinal']]
        if any(saved.get(key) != match.get(key) for key in ('kind', 'seed', 'a', 'b', 'status', 'score_a')):
            raise ValueError('replay result differs from the exported Arena result')
    return {
        'replays_included': True,
        'replay_file': 'arena-replays.json',
        'replay_matches': len(replays),
        'replay_episodes': len(episodes),
        'games_with_missing_frames': sorted({item['kind'] for item in episodes.values() if item.get('missing_frames')}),
    }


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
    arena = json.loads((output / 'arena.json').read_text())
    validate_arena(arena)
    print(f"Arena: {len(arena['overall'])} models, {len(arena['by_game'])} games, {arena['scored']}/{arena['planned']} scored; public-field checks passed")
    replay_path = output / 'arena-replays.json'
    if replay_path.exists():
        metadata = validate_replays(arena, json.loads(replay_path.read_text()))
        if any(arena['snapshot'].get(key) != value for key, value in metadata.items()):
            raise ValueError('Arena replay metadata is stale')
        print(f"Replays: matching run, {metadata['replay_matches']} matches and {metadata['replay_episodes']} episodes; identities and results checked")
    elif arena['snapshot'].get('replays_included'):
        raise ValueError('Arena snapshot refers to a missing replay file')


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
    exported_at = datetime.now(timezone.utc).isoformat()
    source = get('leaderboard')
    documents = {b['id']: export_benchmark(b) for b in source['benchmarks'] if b.get('id') in BENCHMARKS}
    if set(documents) != set(BENCHMARKS):
        raise ValueError('source is missing a requested benchmark')
    arena = export_arena(get('elo'), exported_at)
    replay_path = args.output / 'arena-replays.json'
    if replay_path.exists():
        arena['snapshot'].update(validate_replays(arena, json.loads(replay_path.read_text())))
        arena['snapshot']['note'] = 'Read-only historical aggregates. Recent-match summaries may be truncated by the source API. A separately validated replay archive is included; missing-frame flags describe recording limits.'
    # Project and validate every response before writing any export.
    for benchmark, document in documents.items():
        write_json(args.output / (benchmark + '.json'), document)
    write_json(args.output / 'arena.json', arena)
    check(args.output)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Response bodies and request URLs must not leak via chained exceptions.
        print('Export failed: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
