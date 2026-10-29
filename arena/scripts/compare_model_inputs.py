"""Queue an isolated input-format comparison after the original run exits."""
import argparse
import asyncio
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blink_arena.model_inputs import project_record, REVISION
from blink_arena.systemone import SystemOneClient
from jev_demo_game_evaluation import _write


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def request_samples(folder, game):
    for path in sorted((folder / 'requests').glob(game + '-*.jsonl')):
        for line in path.open():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row.get('result', {}).get('input_tokens'), int):
                yield row


async def same_input_latency(baseline, out, games, plan, *, input_format='intent-v2'):
    """Same public snapshots, one HTTP call per format, alternating AB/BA order."""
    client = SystemOneClient(plan['endpoint'], plan['model'], concurrency=plan['concurrency'])
    capacity = asyncio.Semaphore(plan['concurrency'])
    samples = []
    for game in games:
        rows = sorted(request_samples(baseline, game), key=lambda row: row['result']['input_tokens'])
        if not rows:
            continue
        for index in dict.fromkeys((0, len(rows) // 2, len(rows) - 1)):
            samples.append((game, index, rows[index]['record']))
    random.Random(20261021).shuffle(samples)
    results = []

    async def pair(ordinal, game, index, record):
        async with capacity:
            for form in (('original', 'compact') if ordinal % 2 == 0 else ('compact', 'original')):
                key = f'{game}-{index}-{form}'
                target = out / 'same-input' / (key + '.json')
                if target.exists():
                    results.append(load(target)); continue
                actual = project_record(record, input_format) if form == 'compact' else record
                began = time.monotonic()
                row = {'game': game, 'sample': index, 'format': form, 'status': 'error',
                       'input_format': input_format if form == 'compact' else 'original'}
                try:
                    result = await client.predict(actual, 'decision')
                    row.update(status='ok', input_tokens=result.get('input_tokens'), action=result['value'])
                except Exception as error:
                    row.update(error_type=type(error).__name__)
                row['seconds'] = time.monotonic() - began
                _write(target, row); results.append(row)
    try:
        await asyncio.gather(*(pair(i, *sample) for i, sample in enumerate(samples)))
    finally:
        await client.close()
    return results


def report(baseline, out, games, latency, *, completed_only=False):
    original = load(baseline / 'summary.json')
    compact = load(out / 'episodes-run/summary.json')
    rows = []
    for game in games:
        a = next((row for row in original.get('games', []) if row['game'] == game), {})
        if completed_only and a:
            a = {**a, 'planned': a['finished'], 'pending': 0,
                 'success_rate': a['wins'] / a['finished'] if a['finished'] else None}
        b = next((row for row in compact.get('games', []) if row['game'] == game), {})
        same = {}
        for form in ('original', 'compact'):
            samples = [row for row in latency if row['game'] == game and row['format'] == form and row['status'] == 'ok']
            same[form] = {}
            for key in ('input_tokens', 'seconds'):
                values = [row[key] for row in samples if isinstance(row.get(key), (int, float))]
                same[form][key] = statistics.mean(values) if values else None
            same[form]['successes'] = len(samples)
            same[form]['errors'] = sum(row['game'] == game and row['format'] == form and
                row['status'] != 'ok' for row in latency)
        rows.append({'game': game, 'original': a, 'compact': b, 'same_input': same})
    value = {'model_input_revision': REVISION, 'games': rows,
             'baseline': str(baseline), 'concurrency': original.get('concurrency'),
             'status': compact.get('status', 'running'),
             'note': 'Same completed seeds, physics, opponents, budgets and probe counts. HTTP includes upstream queueing. Small paired sample; realtime trajectories depend on inference latency.'}
    _write(out / 'comparison.json', value)
    lines = ['# 模型输入压缩前后对比', '',
             '原轮次未修改。新轮次复用原轮次已完成对局的种子、模型、接口、对手、预算与并发2；棋盘仍每决策3次探测，实时游戏1次。',
             '成功率按原生终局判定，错误和超预算不算成功；中断且未形成终局的两局不计入基线。每游戏3–4局是小样本；实时轨迹也会随响应耗时改变。', '',
             '| 游戏 | 原成功/完成 | 新成功/计划 | 新已完成 | 原/新错误局 | 原/新HTTP错误次数 | 原/新HTTP均值（秒） | 同输入原/新token | 同输入原/新响应（秒） |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(x): return '—' if x is None else f'{x:.2f}'
    for row in rows:
        a, b, same = row['original'], row['compact'], row['same_input']
        lines.append(f"| {row['game']} | {a.get('wins', '—')}/{a.get('finished', '—')} | {b.get('wins', '—')}/{b.get('planned', '—')} | {b.get('finished', '—')} | {a.get('errors', '—')}/{b.get('errors', '—')} | "
                     f"{a.get('http_errors', '—')}/{b.get('http_errors', '—')} | "
                     f"{fmt(a.get('http_mean_seconds'))}/{fmt(b.get('http_mean_seconds'))} | "
                     f"{fmt(same['original'].get('input_tokens'))}/{fmt(same['compact'].get('input_tokens'))} | "
                     f"{fmt(same['original'].get('seconds'))}/{fmt(same['compact'].get('seconds'))} |")
    lines += ['', '同输入对照从每游戏已记录的短/中/长输入各取一个公开快照，交替原版/压缩版顺序，每次只请求一次，整体并发2。动作变化仅表示选择不同，不作为成功率。',
              '原轮次与新轮次运行时间不同，直接整局HTTP均值可能受服务负载影响；同输入对照用于辅助区分输入长度影响。', '']
    failures = [row for row in latency if row['status'] != 'ok']
    lines.append(f'同输入对照失败请求：{len(failures)}。HTTP 暂态错误即使重试成功也单独计数，不等于错误局。')
    (out / 'comparison.md').write_text('\n'.join(lines))
    return value


def main(args):
    import fcntl
    baseline, out = Path(args.baseline).resolve(), Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / 'comparison.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = load(baseline / 'plan.json')
    if not plan or set(args.games) - set(plan['games']) or plan['concurrency'] != 2:
        raise ValueError('invalid baseline plan or comparison games')
    command = [sys.executable, str(ROOT / 'scripts/evaluate_systemone.py'), '--out', str(out / 'episodes-run'),
               '--endpoint', plan['endpoint'], '--model', plan['model'], '--concurrency', '2', '--episodes', '8',
               '--baseline-plan', str(baseline / 'plan.json'), '--input-format', 'intent-v2', '--games', *args.games]
    if args.completed_baseline_only:
        command.append('--completed-baseline-only')
    while True:
        summary, runtime = load(baseline / 'summary.json'), load(baseline / 'runtime.json')
        ready = (summary.get('status') == 'complete' and summary.get('finished') == len(plan['jobs'])
                 and runtime.get('runner_exited') and not runtime.get('active'))
        if args.completed_baseline_only:
            ready = (summary.get('status') in ('stopped', 'complete') and summary.get('finished', 0) > 0
                     and runtime.get('runner_exited') and not runtime.get('active'))
        _write(out / 'status.json', {'phase': 'ready' if ready else 'waiting_for_baseline',
            'baseline_finished': summary.get('finished'), 'baseline_planned': len(plan['jobs']),
            'games': args.games, 'completed_baseline_only': args.completed_baseline_only, 'updated_at': time.time(),
            'source_root': str(ROOT), 'model_input_revision': REVISION})
        if ready:
            break
        time.sleep(30)
    _write(out / 'status.json', {'phase': 'same_input_latency', 'updated_at': time.time()})
    latency = asyncio.run(same_input_latency(baseline, out, args.games, plan))
    _write(out / 'status.json', {'phase': 'compact_episodes', 'updated_at': time.time()})
    with (out / 'episodes-run.log').open('a') as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        while child.poll() is None:
            report(baseline, out, args.games, latency, completed_only=args.completed_baseline_only)
            time.sleep(30)
    final = report(baseline, out, args.games, latency, completed_only=args.completed_baseline_only)
    _write(out / 'status.json', {'phase': final['status'] if child.returncode == 0 else 'error',
                               'exit_code': child.returncode, 'updated_at': time.time()})
    return child.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--games', nargs='+', required=True)
    parser.add_argument('--completed-baseline-only', action='store_true')
    raise SystemExit(main(parser.parse_args()))
