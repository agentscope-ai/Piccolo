#!/usr/bin/env python3
"""Run the official decision benchmarks against a Piccolo /v1/systemone server."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((Path(__file__).with_name('benchmarks.json')).read_text())


def run(command, *, cwd=None, env=None):
    subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True)


def prepare(name, cache):
    source = SOURCES[name]
    path = cache / name / source['revision']
    if not (path / '.git').exists():
        path.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', '-q', path])
        run(['git', '-C', path, 'remote', 'add', 'origin', source['repository']])
        run(['git', '-C', path, 'config', 'remote.origin.promisor', 'true'])
        run(['git', '-C', path, 'fetch', '--depth=1', '--filter=blob:none', 'origin', source['revision']])
        run(['git', '-C', path, 'sparse-checkout', 'set', *source['paths']])
        run(['git', '-C', path, 'checkout', '--detach', source['revision']])
    revision = subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', path, 'status', '--porcelain', '--untracked-files=no'], text=True)
    if revision != source['revision'] or dirty:
        raise RuntimeError(f'{name}: cached source differs from the pinned revision: {path}')
    run(['git', '-C', path, 'sparse-checkout', 'set', *source['paths']])
    return path


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return str(path)


def commands(name, repo, out, args):
    py = [sys.executable, '-m']
    full_endpoint = args.base_url.rstrip('/') + '/v1/systemone'
    options = {'endpoint': full_endpoint, 'model_id': args.model, 'timeout_seconds': args.timeout,
               'transport_retries': 1, 'retry_delay_seconds': 1}
    if os.environ.get(args.key_env):
        options['key_env'] = args.key_env
    limit = ['--limit', str(args.limit)] if args.limit else []
    cfg = out / 'config'
    if name == 'harness':
        config = write_json(cfg / 'engine.json', {'models': {args.model: {
            **options, 'name': args.model, 'engine': 'http', 'adapter': 'systemone_http',
            'concurrency': args.workers, 'compact_json': True}}})
        return [py + ['evaluation', 'verify'],
                py + ['evaluation', 'predict', '--model', args.model, '--config', config,
                      '--output', str(out / name), '--split', 'both', *limit]]
    if name == 'data':
        config = write_json(cfg / 'data-engine.json', options)
        settings = write_json(cfg / 'data-settings.json', {
            'inference_method': 'native candidate probabilities', 'input_format': 'state and questions',
            'hardware': args.hardware, 'retry_policy': 'one transport retry',
            'dependency_revisions': SOURCES[name]['revision']})
        return [py + ['datajevbench', 'verify'],
                py + ['datajevbench', 'run', '--engine', 'datajevbench.engines:create_http',
                      '--engine-options', config, '--settings', settings, '--model-id', args.model,
                      '--model-revision', args.model_revision, '--backend', 'systemone-http',
                      '--backend-revision', args.backend_revision, '--out', str(out / name), *limit],
                py + ['datajevbench', 'score', '--run', str(out / name)]]
    if name == 'jevbench':
        tasks = ','.join(str(repo / 'datasets/public' / f'{split}.jsonl')
                         for split in ('original', 'easy', 'hard'))
        target = out / name
        return [py + ['jevbench.cli', 'run', '--tasks', tasks, '--adapter', 'typesafe',
                      '--endpoint', args.base_url, '--model', args.model,
                      '--key-env', args.key_env if os.environ.get(args.key_env) else '',
                      '--results', str(target / 'results.jsonl'), '--ledger', str(target / 'ledger.jsonl'),
                      '--raw-dir', str(target / 'raw'), '--manifest', str(target / 'manifest.json'),
                      '--reserve-usd', '0', '--cost-basis', 'self_hosted', *limit],
                py + ['jevbench.cli', 'summarize', '--tasks', tasks,
                      '--results', str(target / 'results.jsonl'), '--ledger', str(target / 'ledger.jsonl'),
                      '--public-export', str(target / 'summary.json')]]
    suite = args.decision_suite or args.cache / 'decision-index-suite'
    suite = suite.resolve()
    pre = []
    if args.decision_suite is None and not suite.exists():
        work = args.cache / 'decision-index-rebuild'
        artifacts = work / 'artifacts/benchmark-suite'
        pre = [py + ['decision_index', 'suite', 'rebuild', '--edition', '0.3', '--work', str(work)],
               py + ['decision_index', 'suite', 'import', '--edition', '0.3', '--dir', str(suite),
                     '--rows', str(artifacts / 'release-v2-rebuilt/selected-rows.jsonl.gz'),
                     '--added-rows', str(artifacts / 'release-v2-rebuilt/added-rows.jsonl.gz'),
                     '--gsm8k-rows', str(artifacts / 'release-v3-rebuilt/gsm8k-rows.jsonl.gz')]]
    return pre + [py + ['decision_index', 'suite', 'verify', '--edition', '0.3', '--dir', str(suite)],
                  py + ['decision_index', 'pipeline', '--edition', '0.3', '--suite-dir', str(suite),
                        '--engine', 'http', '--option', 'base_url=' + args.base_url,
                        '--option', 'model=' + args.model, '--option', 'token_env=' + args.key_env,
                        '--option', 'timeout=' + str(args.timeout), '--out', str(out / name), *limit]]


def validate_run(name, output):
    """Do not accept a completed CLI process whose inference requests all failed."""
    if name == 'harness':
        files = sorted(output.glob('predictions-*.jsonl'))
    else:
        files = [output / 'results.jsonl']
    if not files or any(not p.is_file() or not p.stat().st_size for p in files):
        raise RuntimeError(f'{name}: missing prediction output')
    rows = [json.loads(line) for p in files for line in p.read_text().splitlines() if line.strip()]
    observations = ([q for r in rows for q in (r['question_results'].values()
                     if 'question_results' in r else [r['observation']])]
                    if name == 'harness' else rows)
    errors = sum(bool(r.get('error')) or r.get('ok') is False or r.get('valid') is False
                 or r.get('status') in ('error', 'failed', 'invalid') for r in observations)
    if errors:
        raise RuntimeError(f'{name}: {errors} inference failures; inspect {output}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='Server origin, e.g. http://127.0.0.1:18604')
    parser.add_argument('--model', required=True)
    parser.add_argument('--benchmarks', nargs='+', choices=list(SOURCES), default=list(SOURCES))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cache', type=Path, default=ROOT / 'var/evaluation/cache')
    parser.add_argument('--decision-suite', type=Path, help='Reuse an existing Decision Index suite')
    parser.add_argument('--key-env', default='PICCOLO_API_KEY', help='Environment variable holding the server key')
    parser.add_argument('--model-revision', default='server-managed')
    parser.add_argument('--backend-revision', default='server-managed')
    parser.add_argument('--hardware', default='server-managed')
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--workers', type=int, default=1, help='Harness request concurrency')
    parser.add_argument('--limit', type=int, help='Small diagnostic run instead of the full benchmark')
    parser.add_argument('--prepare-only', action='store_true', help='Fetch source and install Decision Index dependencies without inference')
    parser.add_argument('--dry-run', action='store_true', help='Write and print the command plan without downloads or inference')
    args = parser.parse_args(argv)
    url = urlsplit(args.base_url)
    if url.scheme not in ('http', 'https') or not url.netloc or url.path not in ('', '/') or url.query or url.fragment or url.username or url.password:
        parser.error('--base-url must be an HTTP(S) origin without credentials or a path')
    if args.workers < 1 or args.timeout <= 0 or (args.limit is not None and args.limit < 1):
        parser.error('workers, timeout and limit must be positive')
    args.base_url = args.base_url.rstrip('/')
    args.cache = args.cache.resolve()
    out = (args.output or ROOT / 'var/evaluation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    if out.exists():
        parser.error('Output already exists; choose a new directory to preserve previous results')
    out.mkdir(parents=True)
    plan = []
    for name in dict.fromkeys(args.benchmarks):
        repo = args.cache / name / SOURCES[name]['revision']
        if not args.dry_run:
            repo = prepare(name, args.cache)
            if name == 'decision-index':
                run([sys.executable, '-m', 'pip', 'install', str(repo) + ('[rebuild]' if args.decision_suite is None else '')])
        steps = commands(name, repo, out, args)
        plan.append({'benchmark': name, 'revision': SOURCES[name]['revision'], 'cwd': str(repo), 'commands': steps})
    write_json(out / 'plan.json', plan)
    if args.dry_run or args.prepare_only:
        for item in plan:
            print(item['benchmark'] + ':')
            for command in item['commands']:
                print('  ' + shlex.join(command))
        return 0
    for item in plan:
        for command in item['commands']:
            run(command, cwd=item['cwd'])
        validate_run(item['benchmark'], out / item['benchmark'])
    print('Results: ' + str(out))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
