"""Real Chromium regressions for selected Terra escapes and honest interruption.

No provider/GPU calls. Old release comparison is optional and read-only.
"""
from __future__ import annotations
import argparse
import asyncio
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture

PACKAGE = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def fixture(kind='poison'):
    tiles=[[x,15,1] for x in range(3,24)] + [[9,10,2]]
    tiles += [[10,y,15] for y in range(10,15)]
    f={'x':10,'y':13.75,'dirt':8,'tiles':tiles}
    if kind=='new_lava':
        f['tiles']=[t for t in tiles if t[:2] != [10,13]]+[[10,13,14]]
    elif kind=='new_poison':
        f['tiles']=[t for t in tiles if t[:2] != [10,14]]
    elif kind=='enemy':
        f['enemies']=[{'kind':'bat','x':161,'y':220,'w':12,'h':8,'vx':0,'vy':0,'hp':100,'maxhp':100,'lv':1,'t':0,'ground':False}]
    elif kind=='death': f['hp']=.05
    elif kind=='ceiling': f['tiles'] += [[10,12,11]]
    elif kind=='safe': f['tiles']=[t for t in tiles if t[2]!=15]
    return f

async def run(package:Path, cases):
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(package/'web')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    output=[]
    try:
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True)
            try:
                for name,f,action in cases:
                    page=await browser.new_page()
                    await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;')
                    await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                    result=await page.evaluate('''async ({f,action})=>{
                      const api=JevTerramai;api.fixture(f);api.activate(true);
                      const before=api.prepare({clock:'step'}),start=performance.now();
                      const after=await api.act(action);api.activate(false);
                      return {before,after,wall_seconds:(performance.now()-start)/1000,render_error:window.jevRenderError||null};
                    }''',{'f':f,'action':action})
                    result.update(name=name,action=action,package=str(package))
                    output.append(result)
                    print(json.dumps({'name':name,'frames':result['after']['control']['recent_effects'][-1]['frames'],'status':result['after']['control']['status'],'event':result['after']['control']['events'],'reason':result['after']['control']['failure_reason'],'deaths':result['after']['deaths'],'hp':result['after']['player']['hp']},ensure_ascii=False),flush=True)
                    await page.close()
            finally:await browser.close()
    finally:
        await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
    return output

async def main(args):
    rows=[]
    if args.legacy_package:
        rows+=await run(args.legacy_package,[('legacy_poison_return',fixture(),'return_surface')])
    rows+=await run(args.package,[
        ('known_poison_return',fixture(),'return_surface'),
        ('explore_first_damage',fixture(),'explore_right'),
        ('new_lava_interrupts',fixture('new_lava'),'return_surface'),
        ('new_poison_interrupts',fixture('new_poison'),'return_surface'),
        ('new_enemy_interrupts',fixture('enemy'),'return_surface'),
        ('death_stops_escape',fixture('death'),'return_surface'),
        ('unmineable_ceiling',fixture('ceiling'),'return_surface'),
        ('deadline_unchanged',fixture('safe'),'recover'),
    ])
    failures=[]
    for r in rows:
        c=r['after']['control'];effect=c['recent_effects'][-1];last=r['after']['last_effects'][-1];name=r['name']
        checks={'no_render_error':not r['render_error'],'no_rule_takeover':r['after']['execution_audit']['rule_takeover_count']==0}
        if name=='legacy_poison_return':checks.update(reproduces_one_frame=effect['frames']==1,reproduces_misleading_completed=c['status']=='completed' and c['failure_reason'] is None)
        else:
            checks.update(feedback_consistent=last['event']==effect['event'] and last['status']==c['status'] and last['failure_reason']==c['failure_reason'],noncompletion_has_reason=c['status']=='completed' or bool(c['failure_reason']))
            if name=='known_poison_return':checks.update(sustained=effect['frames']>30,known_damage_recorded=any(x.get('known_environment_escape') for x in c['intermediate_events']),damage_preserved=r['after']['player']['hp']<r['before']['player']['hp'],original_deadline_preserved=effect['frames']==360 and c['status']=='expired')
            elif name in ('explore_first_damage','new_lava_interrupts','new_poison_interrupts','new_enemy_interrupts'):checks.update(interrupted=c['status']=='interrupted',danger=c['events']==['danger_changed'],prompt_stop=effect['frames']<10)
            elif name=='death_stops_escape':checks.update(death=r['after']['deaths']==1,interrupted=c['status']=='interrupted',death_event=c['events']==['death_or_respawn'])
            elif name=='unmineable_ceiling':checks.update(blocked=c['status']=='blocked',ceiling=c['events']==['blocked_ceiling'])
            elif name=='deadline_unchanged':checks.update(expired=c['status']=='expired',frames=effect['frames']==300,reason=c['failure_reason']=='action_deadline_exhausted')
        r['checks']=checks
        failures.extend(name+':'+key for key,val in checks.items() if not val)
    result={'real_chromium':True,'api_calls':0,'GPU':False,'cases':len(rows),'failures':failures,'passed':not failures,'rows':rows}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':not failures,'cases':len(rows),'failures':failures}),flush=True)
    return int(bool(failures))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=PACKAGE);p.add_argument('--legacy-package',type=Path);p.add_argument('--out',type=Path,required=True)
    raise SystemExit(asyncio.run(main(p.parse_args())))
