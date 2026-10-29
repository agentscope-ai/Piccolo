"""Run the existing frontend evaluator against a JEV System One service."""
import argparse
import asyncio
from contextvars import ContextVar
from collections import Counter
import csv
import json
import os
from pathlib import Path
import random
import sys
import time

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_arena.systemone import SystemOneClient
from blink_arena.model_inputs import project_record, REVISION as INPUT_REVISION, LOSSLESS_REVISION, SELECTED_REVISION
from blink_arena.engine import get_engine
from jev_demo_game_evaluation import GameEvaluator, _write, KINDS, EVALUATION_REVISION
from jev_demo_decision_stability import repeated_predict, POLICY_REVISION

episode_context = ContextVar('systemone_episode')
METRICS_REVISION = 'http-attempt-and-queued-request-v1'


def error_info(error):
    detail = getattr(error, 'detail', None)
    code = getattr(error, 'code', None)
    if not code and isinstance(detail, dict):
        code = detail.get('cause') or detail.get('code')
    if not code:
        code = ('timeout' if isinstance(error, httpx.TimeoutException) else
                'connection_failed' if isinstance(error, httpx.TransportError) else
                'cancelled' if isinstance(error, asyncio.CancelledError) else
                'invalid_response' if isinstance(error, (ValueError, KeyError, TypeError)) else
                type(error).__name__)
    return {'code': code, 'error_type': type(error).__name__,
            **({'http_status': error.status} if hasattr(error, 'status') else {}),
            **({'sample_index': detail.get('sample_index')} if isinstance(detail, dict) else {})}


def latency_stats(samples):
    values = sorted(row['seconds'] for row in samples if row['status'] == 'ok')
    def percentile(q):
        if not values:
            return None
        position = (len(values) - 1) * q
        low = int(position)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)
    return {'count': len(samples), 'successes': len(values),
            'errors': dict(Counter(row.get('code', 'unknown') for row in samples if row['status'] != 'ok')),
            'mean_seconds': sum(values) / len(values) if values else None,
            'p50_seconds': percentile(.5), 'p95_seconds': percentile(.95),
            'max_seconds': max(values) if values else None}


def report(out, plan):
    rows = []
    for kind in plan['games']:
        jobs = [job for job in plan['jobs'] if job['game'] == kind]
        results = [json.loads(path.read_text()) for job in jobs
                   if (path := out / 'episodes' / (job['id'] + '.json')).exists()]
        wins = sum(row['status'] == 'complete' and row.get('outcome') == 'win' for row in results)
        metrics = {key: latency_stats([sample for result in results
            for sample in result.get('timings', {}).get(key, [])])
            for key in ('http', 'request', 'decision')}
        rows.append({'game': kind, 'name': get_engine(kind).name, 'planned': len(jobs),
            'finished': len(results), 'wins': wins, 'success_rate': wins / len(jobs),
            'losses': sum(r.get('outcome') == 'loss' for r in results),
            'draws': sum(r.get('outcome') == 'draw' for r in results),
            'budget_exhausted': sum(r.get('outcome') == 'budget_exhausted' for r in results),
            'errors': sum(r['status'] != 'complete' for r in results),
            'pending': len(jobs) - len(results),
            'error_counts': dict(Counter(r.get('error_info', {}).get('code') or r.get('error_type') or 'unknown'
                for r in results if r['status'] != 'complete')),
            'http_attempts': metrics['http']['count'], 'http_errors': sum(metrics['http']['errors'].values()),
            **{'http_' + key: metrics['http'][key] for key in
               ('mean_seconds', 'p50_seconds', 'p95_seconds', 'max_seconds')},
            'request_mean_seconds': metrics['request']['mean_seconds'],
            'request_p95_seconds': metrics['request']['p95_seconds'],
            'decision_mean_seconds': metrics['decision']['mean_seconds'],
            'decision_p95_seconds': metrics['decision']['p95_seconds'],
            'episode_mean_seconds': sum(r['seconds'] for r in results) / len(results) if results else None,
            'latencies': metrics})
    summary = {'schema': 'jev.systemone.frontend-evaluation.v1', 'model': plan['model'],
               'planned': len(plan['jobs']), 'finished': sum(r['finished'] for r in rows),
               'wins': sum(r['wins'] for r in rows), 'games': rows, 'updated_at': time.time(),
               'endpoint': plan['endpoint'], 'concurrency': plan['concurrency'],
               'metrics_revision': METRICS_REVISION}
    summary['status'] = 'complete' if summary['finished'] == summary['planned'] else 'running'
    _write(out / 'summary.json', summary)
    temp = out / 'success_rates.csv.tmp'
    with temp.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=[key for key in rows[0] if key != 'latencies'])
        writer.writeheader(); writer.writerows({key: (json.dumps(value, ensure_ascii=False)
            if isinstance(value, dict) else value) for key, value in row.items() if key != 'latencies'} for row in rows)
    temp.replace(out / 'success_rates.csv')
    lines = ['# System One 前端游戏成功率', '',
        f"模型：`{plan['model']}`；已结束 {summary['finished']}/{summary['planned']} 局。", '',
        f"接口：`{plan['endpoint']}`；对局及 HTTP 请求并发上限均为 {plan['concurrency']}。",
        '使用当前 PiccoloArena 前端评测引擎；规则对手；每局不同种子。回合制每步三次选项顺序探测，实时游戏单次判断且时钟持续。',
        '成功率分母为全部计划局数；错误、超预算和未完成均不计成功。未结束游戏的数值是当前下界。', '',
        '| 游戏 | 已结束/计划 | 成功 | 成功率 | 失败 | 平局 | 超预算 | 错误 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['finished']}/{r['planned']} | {r['wins']} | {r['success_rate']:.1%} | {r['losses']} | {r['draws']} | {r['budget_exhausted']} | {r['errors']} |")
    lines += ['', '## 响应耗时', '',
        '单位为秒。HTTP 为每次实际发送到上游、读完响应的耗时，包含服务端排队；请求另含本地并发等待及有限重试；决策另含三次探测聚合。表中 HTTP 耗时仅统计 2xx 请求，错误尝试单列，不能等同 GPU 推理时间。p50/p95 使用线性插值。运行中统计只含已结束对局。', '',
        '| 游戏 | HTTP 次数 | HTTP 错误 | HTTP 均值 | p50 | p95 | 最大 | 请求 p95 | 决策 p95 | 整局均值 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(value):
        return '—' if value is None else f'{value:.3f}'
    for r in rows:
        lines.append(f"| {r['name']} | {r['http_attempts']} | {r['http_errors']} | " + ' | '.join(fmt(r[key]) for key in
            ('http_mean_seconds', 'http_p50_seconds', 'http_p95_seconds', 'http_max_seconds',
             'request_p95_seconds', 'decision_p95_seconds', 'episode_mean_seconds')) + ' |')
    lines += ['', '## 错误分类', '', '错误局不自动补跑；HTTP 暂态错误的有限重试保留每次尝试。完整记录位于 `episodes/`、`http_requests/`、`requests/` 和 `decisions/`。', '']
    for r in rows:
        if r['errors'] or r['http_errors']:
            lines.append(f"- {r['name']}：对局 {json.dumps(r['error_counts'], ensure_ascii=False)}；HTTP {json.dumps(r['latencies']['http']['errors'], ensure_ascii=False)}")
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    return summary


async def run(args):
    import fcntl
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    lock = (out / 'runner.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name in ('episodes', 'decisions', 'requests', 'http_requests'):
        (out / name).mkdir(exist_ok=True)
    games = args.games or list(KINDS)
    if set(games) - set(KINDS):
        raise ValueError('game_not_in_frontend')
    from jev_game_prompt_calibration import CONFIG
    profile = Path(getattr(args, 'prompt_config', None) or os.environ.get('JEV_GAME_PROMPTS_PATH', str(CONFIG))).resolve()
    profile_value = json.loads(profile.read_text())
    if profile_value.get('schema') != 'jev.live-prompt-calibration.v1' or not profile_value.get('revision'):
        raise ValueError('invalid_prompt_profile')
    frozen_profile = out / 'prompt-config.json'
    if frozen_profile.exists() and json.loads(frozen_profile.read_text()) != profile_value:
        raise ValueError('saved_prompt_profile_differs')
    _write(frozen_profile, profile_value)
    os.environ['JEV_GAME_PROMPTS_PATH'] = str(frozen_profile)
    service_identity = None
    expected_path = getattr(args, 'expected_model_path', None)
    if expected_path:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as identity_client:
            response = await identity_client.get(args.endpoint.removesuffix('/v1/systemone') + '/health')
            response.raise_for_status()
            health = response.json()
        if health.get('model_path') != str(Path(expected_path).resolve()) or health.get('model') != args.model:
            raise ValueError('checkpoint_service_identity_mismatch')
        if health.get('attention_mode') != 'bidirectional_prompt' or health.get('mode') != 'direct':
            raise ValueError('checkpoint_attention_contract_mismatch')
        backend = health.get('actual_backend', {})
        if backend.get('model_path') != health['model_path'] or backend.get('attention') != 'bidirectional_prompt':
            raise ValueError('checkpoint_actual_backend_mismatch')
        service_identity = {k: health.get(k) for k in ('model_path', 'model', 'mode', 'attention_mode', 'actual_backend')}
    plan = {'model': args.model, 'endpoint': args.endpoint, 'games': games,
            'episodes_per_game': args.episodes, 'seed_base': args.seed_base,
            'concurrency': args.concurrency,
            'evaluator_revision': EVALUATION_REVISION, 'policy_revision': POLICY_REVISION,
            'metrics_revision': METRICS_REVISION,
            'prompt_revision': profile_value['revision'], 'prompt_config': profile_value,
            'service_identity': service_identity,
            'source_root': str(Path(__file__).resolve().parents[1]),
            'opponent': 'rule_engine', 'jobs': [
                {'id': f'{kind}-{args.seed_base + i * args.episodes + j}', 'game': kind,
                 'seed': args.seed_base + i * args.episodes + j}
                for i, kind in enumerate(games) for j in range(args.episodes)]}
    input_format = getattr(args, 'input_format', 'original')
    if input_format != 'original':
        plan['model_input_revision'] = (SELECTED_REVISION if input_format == 'selected-v1' else
                                       INPUT_REVISION if input_format == 'intent-v2' else LOSSLESS_REVISION)
    if getattr(args, 'baseline_plan', None):
        baseline = json.loads(Path(args.baseline_plan).read_text())
        if (baseline['model'], baseline['endpoint'], baseline['concurrency']) != (args.model, args.endpoint, args.concurrency):
            raise ValueError('comparison_model_endpoint_or_concurrency_changed')
        if baseline.get('service_identity') is not None and baseline['service_identity'] != service_identity:
            raise ValueError('comparison_checkpoint_or_backend_changed')
        plan['jobs'] = [job for job in baseline['jobs'] if job['game'] in games]
        if getattr(args, 'completed_baseline_only', False):
            baseline_root = Path(args.baseline_plan).parent
            plan['jobs'] = [job for job in plan['jobs']
                if (path := baseline_root / 'episodes' / (job['id'] + '.json')).exists()
                and json.loads(path.read_text()).get('status') == 'complete']
            counts = {game: sum(job['game'] == game for job in plan['jobs']) for game in games}
            if not all(counts.values()):
                raise ValueError('comparison_missing_completed_baseline')
            plan.update(episodes_per_game=None, episodes_by_game=counts, completed_baseline_only=True)
        elif any(sum(job['game'] == game for job in plan['jobs']) != args.episodes for game in games):
            raise ValueError('comparison_seed_coverage_changed')
        plan['baseline_plan'] = str(Path(args.baseline_plan).resolve())
    if (out / 'plan.json').exists():
        if json.loads((out / 'plan.json').read_text()) != plan:
            raise ValueError('resume_plan_changed')
    else:
        _write(out / 'plan.json', plan)
    client = SystemOneClient(args.endpoint, args.model, concurrency=args.concurrency)

    def append(folder, row):
        with (out / folder / (episode_context.get()['id'] + '.jsonl')).open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')

    original_send = client.http.send
    http_active = 0
    http_peak = 0
    async def timed_send(request, *send_args, **send_kwargs):
        nonlocal http_active, http_peak
        http_active += 1
        http_peak = max(http_peak, http_active)
        started = time.monotonic()
        row = {'started_at': time.time(), 'status': 'error', 'inflight_at_start': http_active}
        try:
            response = await original_send(request, *send_args, **send_kwargs)
            row.update(http_status=response.status_code,
                       status='ok' if 200 <= response.status_code < 300 else 'error')
            if row['status'] != 'ok':
                row['code'] = 'http_' + str(response.status_code)
            return response
        except (Exception, asyncio.CancelledError) as error:
            row.update(error_info(error))
            raise
        finally:
            http_active -= 1
            row['seconds'] = time.monotonic() - started
            episode_context.get()['timings']['http'].append(row)
            append('http_requests', row)
    client.http.send = timed_send

    async def predict_once(record, qid, model=None):
        started = time.monotonic()
        timing = {'started_at': time.time(), 'status': 'error'}
        try:
            result = await client.predict(record, qid, model=model)
            timing['status'] = 'ok'
            timing['input_tokens'] = result.get('input_tokens')
        except (Exception, asyncio.CancelledError) as error:
            timing.update(error_info(error))
            append('requests', {'record': record, 'error_type': type(error).__name__,
                                'error_info': error_info(error), 'seconds': time.monotonic() - started})
            raise
        finally:
            timing['seconds'] = time.monotonic() - started
            episode_context.get()['timings']['request'].append(timing)
        append('requests', {'record': record, 'result': result})
        return result

    async def predict(record, qid, model=None):
        record = project_record(record, input_format)
        context = episode_context.get()
        started = time.monotonic()
        timing = {'started_at': time.time(), 'status': 'error'}
        try:
            result = await repeated_predict(predict_once, record, qid, model=model, rng=context['rng'])
            timing['status'] = 'ok'
        except (Exception, asyncio.CancelledError) as error:
            timing.update(error_info(error))
            raise
        finally:
            timing['seconds'] = time.monotonic() - started
            context['timings']['decision'].append(timing)
        append('decisions', {'record': record, 'result': result})
        return result

    evaluator = GameEvaluator(predict, lambda: args.model,
        lambda model: (args.model, {'provider': 'decision', 'served_model': args.model}),
        'http://127.0.0.1:30101', out=out, episodes_per_game=8)
    evaluator.capture_final_state = True
    capacity = asyncio.Semaphore(args.concurrency)
    active = {}

    async def episode(job):
        path = out / 'episodes' / (job['id'] + '.json')
        if path.exists():
            return
        async with capacity:
            timings = {key: [] for key in ('http', 'request', 'decision')}
            token = episode_context.set({**job, 'rng': random.Random(f"systemone-probes/{job['id']}"), 'timings': timings})
            started = time.monotonic()
            kind, seed = job['game'], job['seed']
            engine = get_engine(kind)
            mode = 'rule_engine' if 'rule_engine' in engine.opponent_modes else 'environment'
            active[job['id']] = {**job, 'mode': mode, 'started_at': time.time(), 'timings': timings}
            print(json.dumps({'event': 'started', **job, 'mode': mode}), flush=True)
            try:
                if engine.family == 'board':
                    result = await evaluator._board(None, kind, seed, mode, args.model)
                elif engine.family == 'world' or engine.backend == 'browser':
                    result = await evaluator._registered_browser(None, engine, seed, args.model)
                else:
                    result = await evaluator._python(None, kind, seed, mode, args.model)
                row = {**job, 'mode': mode, 'status': 'complete', **result,
                       'evaluation_only': True, 'on_policy': False}
            except Exception as error:
                row = {**job, 'mode': mode, 'status': 'error', 'outcome': 'error',
                       'error_type': type(error).__name__, 'error': str(error)[:500],
                       'error_info': error_info(error)}
            if row['status'] != 'complete' and 'error_info' not in row:
                row['error_info'] = {'code': row.get('error_type') or row.get('failure_reason') or 'engine_error'}
            row['timings'] = timings
            row['seconds'] = time.monotonic() - started
            _write(path, row)
            active.pop(job['id'], None)
            status = report(out, plan)
            print(json.dumps({'event': 'finished', **job, 'status': row['status'],
                'outcome': row.get('outcome'), 'seconds': round(row['seconds'], 3),
                'finished': status['finished'], 'planned': status['planned'],
                **({'error': row['error']} if row.get('error') else {})}), flush=True)
            episode_context.reset(token)

    report(out, plan)
    async def heartbeat():
        while True:
            _write(out / 'runtime.json', {'updated_at': time.time(), 'active': [
                {**{key: value for key, value in item.items() if key != 'timings'},
                 'progress': {key: latency_stats(samples) for key, samples in item['timings'].items()}}
                for item in active.values()],
                'episode_concurrency': args.concurrency, 'model_request_concurrency': args.concurrency,
                'http_active': http_active, 'http_peak': http_peak})
            await asyncio.sleep(15)
    ticker = asyncio.create_task(heartbeat())
    try:
        # Interleave games so long realtime episodes do not block roster coverage.
        ordered = sorted(plan['jobs'], key=lambda j: (j['seed'] - args.seed_base) % args.episodes)
        await asyncio.gather(*(episode(job) for job in ordered))
    finally:
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
        _write(out / 'runtime.json', {'updated_at': time.time(), 'active': list(active.values()),
            'runner_exited': True, 'http_peak': http_peak,
            'episode_concurrency': args.concurrency, 'model_request_concurrency': args.concurrency})
        await client.close()
    result = report(out, plan)
    return int(any(row['errors'] for row in result['games']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://10.29.240.38:30000/v1/systemone')
    parser.add_argument('--model', default='jev-policy')
    parser.add_argument('--out', required=True)
    parser.add_argument('--episodes', type=int, default=8)
    parser.add_argument('--seed-base', type=int, default=2026102100)
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--games', nargs='+')
    parser.add_argument('--prompt-config', help='Freeze an explicit prompt profile for this run')
    parser.add_argument('--expected-model-path', help='Require the direct bidirectional service to report this checkpoint')
    parser.add_argument('--input-format', choices=('original', 'compact-v1', 'lossless-v1', 'intent-v2', 'selected-v1'), default='original')
    parser.add_argument('--baseline-plan', help='Reuse exact per-game seeds from an earlier plan')
    parser.add_argument('--completed-baseline-only', action='store_true', help='Pair only finished episodes from an interrupted baseline')
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 8 or not 1 <= args.episodes <= 8:
        parser.error('concurrency and episodes must be between 1 and 8')
    raise SystemExit(asyncio.run(run(args)))
