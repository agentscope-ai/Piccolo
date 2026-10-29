"""Independent fixed-opponent episodes for the Public model cohort."""
import csv
import fcntl
import json
from pathlib import Path
import time
from collections import Counter

from jev_demo_arena import GameArena
from jev_demo_arena_episodes import compare_results
from jev_demo_elo import _read, _write


MODE = 'independent'


def schedule(players, games, seeds, seed_base, revision):
    if not 1 <= seeds <= 8 or not players:
        raise ValueError('invalid_independent_cohort')
    fixtures = [{'ordinal': n, 'kind': kind, 'seed': seed, 'a': p['id'],
                 'b': 'rule-engine-v1', 'leg': 0, 'mode': MODE}
                for n, (seed, kind, p) in enumerate(
                    (seed, kind, p) for seed in range(seed_base, seed_base+seeds)
                    for kind in games for p in players)]
    return {'revision': revision, 'public_revision': revision, 'cohort_mode': MODE,
            'participants': players, 'kinds': list(games), 'seeds': seeds,
            'seed_base': seed_base, 'schedule': fixtures,
            'opponent_rule': 'native fixed rule opponent; environment for solo games',
            'seat_rule': 'existing_game_evaluator_seed_seat_v1; one episode per seed',
            'rating_rule': 'no Elo; independent native success rate'}


def fixture_models(fixture):
    return [fixture['a']] if fixture.get('mode') == MODE else [fixture['a'], fixture['b']]


def match_receipt(fixture, episode):
    return {**fixture, **{k: episode[k] for k in (
        'status', 'outcome', 'score', 'score_label', 'comparison_key', 'budget_exhausted',
        'natural_success', 'terminal', 'seconds', 'finished_at', 'error_type',
        'error_code', 'error_location', 'http_status', 'provenance') if k in episode},
        'episode_id': episode.get('episode_id'),
        'score_a': ({'win': 1., 'draw': .5, 'loss': 0., 'budget_exhausted': 0.}.get(episode.get('outcome'))
                    if episode['status'] == 'complete' else None)}


def inherit(out, source, contract):
    """Import only validated native episodes, never model-duel outcomes."""
    with (source/'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous, old_plan, plan = _read(source/'contract.json'), _read(source/'plan.json'), _read(out/'plan.json')
        for key in ('games', 'seeds', 'seed_base', 'prompt', 'scope', 'max_games',
                    'per_model_concurrency', 'input_format', 'state_serialization',
                    'probability_policy', 'choice_policy'):
            if previous.get(key) != contract.get(key):
                raise ValueError('independent_inheritance_contract_changed:'+key)
        if old_plan['participants'] != plan['participants']:
            raise ValueError('independent_inheritance_participant_changed')
        launch = _read(source.parent/'formal-launch.json')
        if not launch or Path(launch['output']).resolve() != source.resolve():
            launch = _read(source.parent/'formal-launch-v3c.json')
        if launch and Path(launch['output']).resolve() == source.resolve():
            old_root = Path(launch['source_root'])
            new_root = Path(__file__).resolve().parents[1]
            replay_only = {'web/playground/mario-core.js', 'web/playground/world-core-worker.cjs'}
            for name in contract['engine_sources']:
                if name.startswith('web/') and name not in replay_only:
                    if (old_root/name).read_bytes() != (new_root/name).read_bytes():
                        raise ValueError('independent_inheritance_physics_asset_changed:'+name)
        # These edits only add fixed-opponent capture/scoring and diagnostics.
        # All other engine and prompt files must retain their exact inventory.
        compatible = {'blink_arena/engines/jev_demo_game_evaluation.py',
                      'blink_arena/engines/jev_demo_arena_episodes.py',
                      'blink_arena/engines/jev_demo_arena.py'}
        for name, info in previous['engine_sources'].items():
            if ((name.startswith('blink_arena/engines/') or name == 'blink_arena/model_inputs.py')
                    and name not in compatible and contract['engine_sources'].get(name) != info):
                raise ValueError('independent_inheritance_engine_changed:'+name)
        lookup = {(f['kind'], f['seed'], f['a']): f for f in plan['schedule']}
        retained, errors = {}, []
        for path in sorted((source/'episode_summaries').glob('*.json')):
            summary = _read(path)
            key = (summary['kind'], summary['seed'], summary['model'])
            if key not in lookup:
                continue
            if summary.get('status') != 'complete':
                errors.append({'kind': key[0], 'seed': key[1], 'model': key[2],
                               'reason': summary.get('error_type', 'invalid_episode')})
                continue
            row = _read(source/'episodes'/path.name)
            p = next(p for p in plan['participants'] if p['id'] == key[2])
            binding = (row or {}).get('binding', {})
            identity = {k: v for k, v in p.items() if k in ('id', 'provider', 'served_model', 'model_path')}
            if (not row or row.get('status') != 'complete' or binding.get('participant') != p
                    or row.get('model_identity') != identity or summary.get('binding') != binding
                    or binding.get('kind') != key[0] or binding.get('seed') != key[1]
                    or row.get('comparison_spec') != binding.get('comparison')):
                raise ValueError('independent_inheritance_episode_identity_changed')
            if compare_results(row, row) != .5:
                raise ValueError('independent_inheritance_invalid_native_score')
            if key[0] in ('mario_platformer', 'terraria_survival') and (
                    row.get('replay_verified') is not True or not row.get('replay_validation', {}).get('strict_match')):
                raise ValueError('independent_inheritance_realtime_not_strictly_verified')
            origin = {'source': str(source.resolve()), 'kind': 'validated_independent_episode_reuse',
                      'original_provenance': row.get('provenance'), 'original_episode': row['episode_id']}
            row = {**row, 'provenance': origin}
            _write(out/'episodes'/path.name, row)
            _write(out/'episode_summaries'/path.name, GameArena._episode_summary(row))
            receipt = match_receipt(lookup[key], row)
            name = f"{receipt['ordinal']:05d}.json"
            _write(out/'matches'/name, receipt)
            _write(out/'summaries'/name, receipt)
            retained[key] = lookup[key]['ordinal']
        # Every episode was executed in exactly one comparison's request context.
        # Remap those original requests to its independent ordinal, and exclude
        # the other model's calls and every failed/unfinished episode.
        requests, streams = 0, {}
        try:
            for path in sorted((source/'requests').glob('*.jsonl')):
                if not path.stem.isdigit():
                    continue
                fixture = old_plan['schedule'][int(path.stem)]
                if fixture['mode'] == 'direct':
                    continue
                for line in path.open():
                    if not line.endswith('\n'):
                        break
                    row = json.loads(line)
                    key = (fixture['kind'], fixture['seed'], row['model'])
                    if key not in retained:
                        continue
                    ordinal = retained[key]
                    if ordinal not in streams:
                        target = out/'requests'/f'{ordinal}.jsonl'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        streams[ordinal] = target.open('w')
                    streams[ordinal].write(json.dumps({**row, 'fixture_ordinal': ordinal,
                        'source_fixture_ordinal': fixture['ordinal'],
                        'runtime_generation': 'independent-inherited'}, ensure_ascii=False)+'\n')
                    requests += 1
        finally:
            for stream in streams.values():
                stream.close()
        result = {'source': str(source.resolve()), 'episodes': len(retained), 'matches': len(retained),
                  'requests': requests, 'requeued_errors': errors, 'duel_results_imported': 0,
                  'realtime_policy': 'reuse only complete strictly verified native episodes',
                  'compatible_engine_extensions': sorted(compatible), 'finished_at': time.time()}
        _write(out/'inheritance.json', result)
        return result


def report(out, plan, receipts, requests, stats):
    metrics, overall = [], []
    for p in plan['participants']:
        for kind in plan['kinds']:
            done = [r for r in receipts if r['kind'] == kind and r['a'] == p['id']]
            valid = [r for r in done if r['status'] == 'complete']
            wins = sum((r.get('natural_success') if r.get('natural_success') is not None
                        else r.get('outcome') == 'win') for r in valid)
            calls = [r for r in requests if r['game'] == kind and r['model'] == p['id']]
            current = [r for r in calls if r.get('runtime_generation') not in ('v2-inherited', 'independent-inherited')]
            latency = stats([r['seconds'] for r in calls if r['status'] == 'ok'])
            current_latency = stats([r['seconds'] for r in current if r['status'] == 'ok'])
            elapsed = stats([r['seconds'] for r in valid if 'seconds' in r])
            metrics.append({'game': kind, 'model': p['id'], 'name': p['name'], 'mode': MODE,
                'planned_episodes': plan['seeds'], 'finished_episodes': len(done), 'valid_episodes': len(valid),
                'successes': wins, 'draws': sum(r.get('outcome') == 'draw' for r in valid),
                'losses': sum(r.get('outcome') == 'loss' for r in valid),
                'budget_exhausted': sum(bool(r.get('budget_exhausted')) for r in valid),
                'errors': len(done)-len(valid), 'pending': plan['seeds']-len(done),
                'success_rate': wins/plan['seeds'],
                'success_rate_valid': wins/len(valid) if valid else None,
                'success_rate_complete': len(done) == plan['seeds'] and len(valid) == plan['seeds'],
                'episode_error_counts': dict(Counter(r.get('error_code', r.get('error_type', 'unknown'))
                    for r in done if r['status'] != 'complete')),
                'episode_mean_seconds': elapsed['mean'], 'episode_p95_seconds': elapsed['p95'],
                'http_requests': len(calls), 'http_errors': sum(r['status'] == 'error' for r in calls),
                'http_cancelled': sum(r['status'] == 'cancelled' for r in calls),
                'http_current_requests': len(current), 'http_inherited_requests': len(calls)-len(current),
                'http_mean_seconds': latency['mean'], 'http_p50_seconds': latency['p50'], 'http_p95_seconds': latency['p95'],
                'http_current_mean_seconds': current_latency['mean'],
                'http_current_p50_seconds': current_latency['p50'], 'http_current_p95_seconds': current_latency['p95'],
                'http_error_counts': dict(Counter(r.get('error', 'unknown') for r in calls if r['status'] == 'error')),
                'reported_cost_usd': sum((r.get('usage') or {}).get('cost', 0) or 0 for r in calls)})
        rows = [m for m in metrics if m['model'] == p['id']]
        overall.append({'id': p['id'], 'name': p['name'],
            **{k: sum(r[k] for r in rows) for k in ('planned_episodes', 'finished_episodes',
                'valid_episodes', 'successes', 'draws', 'losses', 'errors', 'pending', 'budget_exhausted')},
            'mean_game_success_rate': sum(r['success_rate'] for r in rows)/len(rows)})
    summary = {**(_read(out/'status.json') or {'state': 'prepared'}), 'updated_at': time.time(),
        'cohort_mode': MODE, 'planned': len(plan['schedule']), 'finished': len(receipts),
        'valid': sum(r['status'] == 'complete' for r in receipts),
        'errors': sum(r['status'] != 'complete' for r in receipts), 'overall': overall, 'metrics': metrics,
        'inheritance': _read(out/'inheritance.json'),
        'reported_cost_usd': sum(r['reported_cost_usd'] for r in metrics)}
    _write(out/'summary.json', summary)
    with (out/'game_metrics.csv.tmp').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0])); writer.writeheader()
        for row in metrics:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for k,v in row.items()})
    (out/'game_metrics.csv.tmp').replace(out/'game_metrics.csv')
    lines = ['# Piccolo Arena · 独立游戏评测', '',
        f"状态：{summary['state']}；已结束 {summary['finished']}/{summary['planned']} 局；有效 {summary['valid']}；错误 {summary['errors']}。", '',
        '每个模型 × 每款游戏 × 8 个种子，每种子一局；多人游戏使用原生固定规则对手，座位随种子分配。',
        '单模型请求最多 5，全局实际游戏最多 20；回合制三次顺序探测，实时游戏一次且世界时钟持续。',
        '成功率使用固定 8 局分母；未完成时为下界。错误、待跑、预算耗尽单列，有效局成功率另列。', '',
        '| 模型 | 已结束 | 有效 | 成功 | 错误 | 待跑 |', '|---|---:|---:|---:|---:|---:|']
    for row in overall:
        lines.append(f"| {row['name']} | {row['finished_episodes']} | {row['valid_episodes']} | {row['successes']} | {row['errors']} | {row['pending']} |")
    lines += ['', '逐游戏成功率、错误和响应耗时见 [game_metrics.csv](game_metrics.csv)。',
        '复用来源见 inheritance.json；http_current_* 单列本轮耗时，旧请求计入 http_inherited_requests。',
        '错误不能视为有效失败；旧赛程、旧错误和原始请求均保留。Blink 待新 RL checkpoint 登记后追加 176 局。', '']
    (out/'report.md').write_text('\n'.join(lines))
    return summary
