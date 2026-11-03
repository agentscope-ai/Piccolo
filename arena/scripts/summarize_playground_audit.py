"""Summarize real browser playthrough receipts without counting API failures as losses."""
import argparse
from collections import Counter
import json
import time
from pathlib import Path


def summarize(source,output):
    s=json.loads(Path(source).read_text());groups={}
    for r in s['runs']:groups.setdefault(r['game'],[]).append(r)
    # A successful retry must not erase an upstream/UI error from the report.
    attempts={(r['game'],r['seed'],r.get('started_at')):r for r in s['runs']}
    for path in (Path(source).parent/'runs').rglob('result.json'):
        r=json.loads(path.read_text())
        attempts[(r['game'],r['seed'],r.get('started_at'))]=r
    active_paths={str(Path(r['artifacts']).resolve()) for r in s.get('active',[]) if r.get('artifacts')}
    interrupted=[]
    for path in (Path(source).parent/'runs').glob('*/attempt-*'):
        if not (path/'result.json').exists() and (path/'initial-state.json').exists() and str(path.resolve()) not in active_paths:
            game,_,seed=path.parent.name.rpartition('-')
            interrupted.append({'game':game,'seed':int(seed),'artifacts':str(path)})
    rows=[]
    for game,runs in groups.items():
        valid=[r for r in runs if (r.get('terminal') or r['status']=='budget_exhausted') and not r.get('errors')]
        outcomes=Counter(r.get('outcome') for r in valid)
        wins=outcomes['win']+outcomes['X'];n=len(valid)
        calls=sum(r['model_calls'] for r in valid)
        mean=sum((r.get('mean_response_seconds') or 0)*r['model_calls'] for r in valid)/calls if calls else None
        failed=[r for r in attempts.values() if r['game']==game and
                (r.get('errors') or r.get('status') in ('audit_error','stalled','audit_time_limit','audit_step_limit'))]
        rows.append({'game':game,'finished':n,'target':len(s['seeds']),'wins':wins,
          'success_rate':wins/n if n else None,'draws':outcomes['draw'],'budget_exhausted':outcomes['budget_exhausted'],
          'model_calls':calls,'mean_response_seconds':round(mean,3) if mean else None,
          'errors':sum(len(r.get('errors',[]))+(r.get('status')=='audit_error' and not any(e.get('type')=='script' for e in r.get('errors',[]))) for r in failed),
          'error_requests':sum(e.get('type')=='http' for r in failed for e in r.get('errors',[])),
          'failed_attempts':len(failed),
          'interrupted_attempts':sum(r['game']==game for r in interrupted),
          'incomplete_runs':sum(bool(r.get('errors')) or not r.get('terminal') and r['status']!='budget_exhausted' for r in runs),
          'display_issues':sorted(set(i for r in runs for i in r.get('display_issues',[]))),
          'seeds_finished':[r['seed'] for r in valid]})
    rows.sort(key=lambda r:(r['success_rate'] if r['success_rate'] is not None else 2,r['game']))
    result={'updated_at':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'source_updated_at':s.get('updated_at'),
      'games':rows,'completed_runs':sum(r['finished'] for r in rows),'target_runs':len(s.get('games',range(22)))*len(s['seeds']),
      'error_requests':sum(r['error_requests'] for r in rows),
      'failed_attempts':sum(r['failed_attempts'] for r in rows),'interrupted_attempts':interrupted,
      'zero_success_candidates':[r['game'] for r in rows if r['target']>=5 and r['finished']==r['target'] and not r['wins']],
      'active':[{k:v for k,v in a.items() if k in ['game','seed','steps','model_calls']} for a in s.get('active',[])]}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Playground 完整对局检查','',f"已完成 {result['completed_runs']} / {result['target_runs']} 局。",
      '',f"更新时间：{result['updated_at']}。",
      '', '真实 Piccolo 后端；不同种子；对战游戏第一席对原生规则策略；并发 2；实时世界等待模型时继续运行。',
      '世界游戏达到已有决策预算仍未通关时记为预算耗尽。接口/脚本故障单独统计，不能当作模型输局。', '',
      '| 游戏 | 完成 | 成功 | 成功率 | 和局 | 预算耗尽 | 接口/脚本错误记录 | 平均模型响应秒 |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        rate=f"{r['success_rate']:.0%}" if r['success_rate'] is not None else '—'
        lines.append(f"| {r['game']} | {r['finished']}/{r['target']} | {r['wins']} | {rate} | {r['draws']} | {r['budget_exhausted']} | {r['errors']} | {r['mean_response_seconds'] or '—'} |")
    lines+=['','5 局全部完成且 0 次成功的候选：'+('、'.join(result['zero_success_candidates']) or '尚无完整五局候选。'),'',
      f"中断尝试：{len(interrupted)}；已保留原始文件，单独记录，不计为模型负局或接口故障。",'',
      '这是 5 局试玩的弱项定位，不作为稳定能力排名；未自动删除任何游戏。']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'completed':result['completed_runs'],'target':result['target_runs'],'zero_success_candidates':result['zero_success_candidates'],'active':result['active']},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--watch-pid',type=int,help='Refresh while the specified browser audit process is alive')
    a=p.parse_args()
    if a.watch_pid:
        for _ in range(100):
            if Path(a.source).exists():break
            if not (Path('/proc')/str(a.watch_pid)).exists():break
            time.sleep(.1)
    while True:
        summarize(a.source,a.output)
        if not a.watch_pid:break
        proc=Path('/proc')/str(a.watch_pid)
        try:
            state=(proc/'stat').read_text().rsplit(')',1)[1].split()[0]
            running=b'browser_five_seed_playthrough.py' in (proc/'cmdline').read_bytes()
        except OSError:break
        if state=='Z' or not running:break
        time.sleep(30)
