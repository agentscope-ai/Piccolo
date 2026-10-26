"""Run the existing frontend evaluator against a JEV System One service."""
import argparse
import asyncio
from contextvars import ContextVar
import csv
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_arena.systemone import SystemOneClient
from blink_arena.engine import get_engine
from jev_demo_game_evaluation import GameEvaluator, _write, KINDS, EVALUATION_REVISION
from jev_demo_decision_stability import repeated_predict, POLICY_REVISION

episode_context = ContextVar('systemone_episode')


def report(out, plan):
    rows = []
    for kind in plan['games']:
        jobs = [job for job in plan['jobs'] if job['game'] == kind]
        results = [json.loads(path.read_text()) for job in jobs
                   if (path := out / 'episodes' / (job['id'] + '.json')).exists()]
        wins = sum(row['status'] == 'complete' and row.get('outcome') == 'win' for row in results)
        rows.append({'game': kind, 'name': get_engine(kind).name, 'planned': len(jobs),
            'finished': len(results), 'wins': wins, 'success_rate': wins / len(jobs),
            'losses': sum(r.get('outcome') == 'loss' for r in results),
            'draws': sum(r.get('outcome') == 'draw' for r in results),
            'budget_exhausted': sum(r.get('outcome') == 'budget_exhausted' for r in results),
            'errors': sum(r['status'] != 'complete' for r in results),
            'pending': len(jobs) - len(results)})
    summary = {'schema': 'jev.systemone.frontend-evaluation.v1', 'model': plan['model'],
               'planned': len(plan['jobs']), 'finished': sum(r['finished'] for r in rows),
               'wins': sum(r['wins'] for r in rows), 'games': rows, 'updated_at': time.time()}
    summary['status'] = 'complete' if summary['finished'] == summary['planned'] else 'running'
    _write(out / 'summary.json', summary)
    temp = out / 'success_rates.csv.tmp'
    with temp.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    temp.replace(out / 'success_rates.csv')
    lines = ['# System One 前端游戏成功率', '',
        f"模型：`{plan['model']}`；已结束 {summary['finished']}/{summary['planned']} 局。", '',
        '使用当前 BlinkArena 前端评测引擎；规则对手；每局不同种子。回合制每步三次顺序探测，实时游戏单次判断且时钟持续。',
        '成功率分母为全部计划局数；错误、超预算和未完成均不计成功。未结束游戏的数值是当前下界。', '',
        '| 游戏 | 已结束/计划 | 成功 | 成功率 | 失败 | 平局 | 超预算 | 错误 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['finished']}/{r['planned']} | {r['wins']} | {r['success_rate']:.1%} | {r['losses']} | {r['draws']} | {r['budget_exhausted']} | {r['errors']} |")
    (out / 'report.md').write_text('\n'.join(lines) + '\n')
    return summary


async def run(args):
    import fcntl
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    lock = (out / 'runner.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name in ('episodes', 'decisions', 'requests'):
        (out / name).mkdir(exist_ok=True)
    games = args.games or list(KINDS)
    if set(games) - set(KINDS):
        raise ValueError('game_not_in_frontend')
    plan = {'model': args.model, 'endpoint': args.endpoint, 'games': games,
            'episodes_per_game': args.episodes, 'seed_base': args.seed_base,
            'evaluator_revision': EVALUATION_REVISION, 'policy_revision': POLICY_REVISION,
            'source_root': str(Path(__file__).resolve().parents[1]),
            'opponent': 'rule_engine', 'jobs': [
                {'id': f'{kind}-{args.seed_base + i * args.episodes + j}', 'game': kind,
                 'seed': args.seed_base + i * args.episodes + j}
                for i, kind in enumerate(games) for j in range(args.episodes)]}
    if (out / 'plan.json').exists():
        if json.loads((out / 'plan.json').read_text()) != plan:
            raise ValueError('resume_plan_changed')
    else:
        _write(out / 'plan.json', plan)
    client = SystemOneClient(args.endpoint, args.model, concurrency=args.concurrency)

    def append(folder, row):
        with (out / folder / (episode_context.get()['id'] + '.jsonl')).open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')

    async def predict_once(record, qid, model=None):
        try:
            result = await client.predict(record, qid, model=model)
        except Exception as error:
            append('requests', {'record': record, 'error_type': type(error).__name__,
                                'error': str(error)[:200]})
            raise
        append('requests', {'record': record, 'result': result})
        return result

    async def predict(record, qid, model=None):
        context = episode_context.get()
        result = await repeated_predict(predict_once, record, qid, model=model, rng=context['rng'])
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
            token = episode_context.set({**job, 'rng': random.Random(f"systemone-probes/{job['id']}")})
            started = time.monotonic()
            kind, seed = job['game'], job['seed']
            engine = get_engine(kind)
            mode = 'rule_engine' if 'rule_engine' in engine.opponent_modes else 'environment'
            active[job['id']] = {**job, 'mode': mode, 'started_at': time.time()}
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
                       'error_type': type(error).__name__, 'error': str(error)[:500]}
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
            _write(out / 'runtime.json', {'updated_at': time.time(), 'active': list(active.values()),
                'episode_concurrency': args.concurrency, 'model_request_concurrency': args.concurrency})
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
            'runner_exited': True})
        await client.close()
    result = report(out, plan)
    return int(any(row['errors'] for row in result['games']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:30100/v1/systemone')
    parser.add_argument('--model', default='jev-policy')
    parser.add_argument('--out', required=True)
    parser.add_argument('--episodes', type=int, default=8)
    parser.add_argument('--seed-base', type=int, default=2026102100)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--games', nargs='+')
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 8 or not 1 <= args.episodes <= 8:
        parser.error('concurrency and episodes must be between 1 and 8')
    raise SystemExit(asyncio.run(run(args)))
