"""Real Terra threat-boundary regressions, with read-only public-observation telemetry."""
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
import sys

PACKAGE=Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

async def run(package,cases):
    source=engine_source(package);text=test_source(source)
    needle='var obs=jevSnapshot(),m=obs.map,p=Object.assign({},obs.player,obs.player.geometry||{}),tx=p.tile[0],ty=p.tile[1];'
    assert text.count(needle)==1
    observed=text.replace(needle,needle+"if(window.__terraPublicFrames)window.__terraPublicFrames.push({action,observation:structuredClone(obs)});")
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(package/'web')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();rows=[]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            try:
                for name,action,kind,telemetry in cases:
                    page=await browser.new_page();await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__terraPublicFrames=[];')
                    if telemetry:
                        async def intercept(route):await route.fulfill(status=200,content_type='application/javascript',body=observed)
                        await page.route('**/'+engine_source(package).name+'*',intercept)
                    await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                    row=await page.evaluate('''async ({action,kind})=>{
                      const api=JevTerramai;api.reset(20261016);
                      let enemy={kind:'zombie',x:23*16,y:15*16-42,w:25.3,h:42,hp:1051,maxhp:1051,lv:10,boss:true,vx:0,vy:0,t:0,ground:true};
                      if(kind==='selected')enemy={kind:'slime',x:13*16,y:15*16-11,w:14,h:11,hp:14,maxhp:14,lv:1,vx:0,vy:0,t:0,ground:true};
                      if(kind==='behind')enemy.x=6*16;
                      if(kind==='vertical')enemy={kind:'bat',x:14*16,y:3*16,w:12,h:8,hp:20,maxhp:20,lv:1,vx:0,vy:0,t:0,ground:false};
                      // Navigation fixtures begin after the guardian prerequisite.
                      // Actual combat/unlocking causality is tested in terra_guardian.
                      api.fixture({x:10,y:13.75,dirt:0,guardianDefeatedByPlayer:true,tiles:Array.from({length:50},(_,x)=>[x,15,2]),goal:[kind==='vertical'?12:kind==='clear'||kind==='behind'?18:40,14],exploredGoal:true,enemies:kind==='clear'?[]:[enemy]});
                      api.activate(true);const before=structuredClone(api.prepare({clock:'step'})),after=await api.act(action);api.activate(false);
                      return {before,after,observed_frames:window.__terraPublicFrames,render_error:window.jevRenderError||null};
                    }''',{'action':action,'kind':kind})
                    row.update(name=name,action=action,kind=kind,telemetry=telemetry,package=str(package));rows.append(row)
                    print(json.dumps({'name':name,'event':row['after']['control']['events'],'hp':row['after']['player']['hp'],'frames':row['after']['control']['recent_effects'][-1]['frames'],'wins':row['after']['wins']}),flush=True)
                    await page.close()
            finally:await browser.close()
    finally:await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
    assert test_source(source)==text,'fixture must not modify frozen or working engine source'
    return rows

async def main(args):
    args.package = args.package.resolve()
    sys.path.insert(0, str(args.package))
    import blink_arena
    import jev_terraria_contract as contract
    assert Path(contract.__file__).resolve().is_relative_to(args.package), 'contract must come from the selected package'
    as_record, visible_approach_threats = contract.as_record, contract.visible_approach_threats
    rows=[]
    if args.legacy_package:
        rows+=await run(args.legacy_package,[('legacy_goal_first_damage','reach_known_goal','approaching',True)])
    rows+=await run(args.package,[
        ('goal_visible_threat','reach_known_goal','approaching',True),
        ('explore_visible_threat','explore_right','approaching',True),
        ('goal_without_threat','reach_known_goal','clear',True),
        ('selected_pass','pass_enemy_right','selected',True),
        ('selected_fight','fight_nearest','selected',True),
        ('selected_retreat','retreat_left','selected',True),
        ('enemy_behind','reach_known_goal','behind',True),
        ('enemy_far_vertical','reach_known_goal','vertical',True),
        ('goal_clean_control','reach_known_goal','approaching',False),
        ('explore_clean_control','explore_right','approaching',False),
    ])
    failures=[]
    for r in rows:
        a=r['after'];c=a['control'];name=r['name'];frames=[x['observation'] for x in r['observed_frames']]
        visible=[s for s in frames if s['enemies']];threats=[s for s in frames if visible_approach_threats(s)]
        r['first_visible_frame']=visible[0]['frame'] if visible else None
        r['first_threat_frame']=threats[0]['frame'] if threats else None
        checks={'no_render_error':not r['render_error'],'C0':a['execution_audit']['rule_takeover_count']==0,'single_selected_intent':a['execution_audit']['model_decisions']==1}
        if name=='legacy_goal_first_damage':
            checks.update(old_trigger_after_visibility=a['frame']>r['first_threat_frame']+1,old_trigger_after_damage=c['events']==['danger_changed'] and a['player']['hp']<100)
        elif name in ('goal_visible_threat','explore_visible_threat'):
            q=as_record(a);r['after_record']=q
            checks.update(initial_no_enemy=not r['before']['enemies'],before_damage=a['player']['hp']==100,threat_boundary=c['events']==['threat_detected'] and a['frame']==r['first_threat_frame']+1,interrupted=c['status']=='interrupted',reason=c['failure_reason']=='threat_detected',public_facts_match=q['state']['navigation']['approach_threat_ids']==[e['id'] for e in visible_approach_threats(a)],candidate_explains_redecision='遇前方已见威胁先返回模型' in q['questions']['decision']['criteria']['reach_known_goal'])
        elif name in ('goal_without_threat','enemy_behind','enemy_far_vertical'):
            checks.update(native_win=a['wins']==1,goal_completed=c['events']==['goal_door_entered'],no_spurious_threat='threat_detected' not in c['events'])
        elif name.startswith('selected_'):
            checks.update(continues_selected_strategy=c['recent_effects'][-1]['frames']>1,no_new_threat_stop='threat_detected' not in c['events'])
        elif name.endswith('clean_control'):
            reference=next(x for x in rows if x['name']==name.replace('_clean_control','_visible_threat'))
            checks['telemetry_final_state_exactly_equal']=a==reference['after']
        r['checks']=checks;failures.extend(name+':'+k for k,v in checks.items() if not v)
    result={'real_chromium':True,'model_calls':0,'GPU_calls':0,'cases':len(rows),'scenarios_excluding_telemetry_controls':len(rows)-2,'failures':failures,'passed':not failures,'rows':rows}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':not failures,'cases':len(rows),'failures':failures}),flush=True)
    return int(bool(failures))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--legacy-package',type=Path);parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
