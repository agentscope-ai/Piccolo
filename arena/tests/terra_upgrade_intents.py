"""Real JS selection, mining/upgrade, wait and death contracts; no model calls."""
from __future__ import annotations
import argparse
import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture

PACKAGE=Path(__file__).resolve().parents[1]

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

async def main(args):
    p=args.package.resolve();sys.path.insert(0,str(p))
    import blink_arena
    import jev_terraria_contract as c
    assert Path(c.__file__).resolve().is_relative_to(p)
    js=engine_source(p);source=test_source(js)
    needle='(f.tiles||[]).forEach(function(t){setT(t[0],t[1],t[2])});'
    assert source.count(needle)==1
    # Test-only fixture setup does not alter the executing mining/upgrade logic.
    injected=source.replace(needle,"if(f.testGear)Object.assign(gear,f.testGear);wins=f.testWins||0;"+needle+"(f.hideTiles||[]).forEach(function(t){explored[idx(t[0],t[1])]=0;});")
    marker='if(target){jevControl.target=target;jevControl.subgoal={intent:action,target:target};}'
    assert injected.count(marker)==1
    injected=injected.replace(marker,marker+"if(window.__targets&&target)window.__targets.push({observation:structuredClone(obs),target:structuredClone(target)});")
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(p/'web')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    scenarios=[
        dict(name='gem_selected_over_closer_ore',action='collect_visible_gem',gear={'gems':1,'pts':3},tiles=[[11,14,4],[12,14,8]]),
        dict(name='legacy_collect_keeps_nearest_ore',action='collect_visible',gear={'gems':1,'pts':3},tiles=[[11,14,4],[12,14,8]]),
        dict(name='gem_armor_multiple_levels',action='collect_visible_gem',gear={'gems':7,'armor':0},tiles=[[11,14,8]]),
        dict(name='gold_upgrades_sword',action='collect_visible',gear={'pick':2,'sword':1,'pts':3},tiles=[[11,14,6]]),
        dict(name='diamond_points_can_upgrade_armor_at_cap',action='collect_visible',gear={'pick':20,'sword':20,'armor':19,'pts':20},tiles=[[11,14,7]]),
        dict(name='gem_equal_distance_x_tiebreak',action='collect_visible_gem',x=10,gear={},tiles=[[9,14,8],[11,14,8]]),
        dict(name='gem_equal_distance_y_tiebreak',action='collect_visible_gem',x=10,y=13.5,gear={},tiles=[[11,13,8],[11,14,8]]),
        dict(name='gem_uses_exact_geometry',action='collect_visible_gem',x=10.04,gear={},tiles=[[9,14,8],[11,14,8]]),
        dict(name='gem_hidden_not_available',action='collect_visible_gem',gear={},tiles=[[11,14,8]],hideTiles=[[11,14]]),
        dict(name='gem_outside_public_map_not_available',action='collect_visible_gem',gear={},tiles=[[50,14,8]]),
        dict(name='chest_random_not_predicted',action='collect_visible',gear={},tiles=[[12,14,13],[11,14,7]]),
    ]
    rows=[];checks={}
    try:
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True)
            try:
                page=await browser.new_page();await install_fixture(page, p);await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__targets=[];')
                async def intercept(route):await route.fulfill(status=200,content_type='application/javascript',body=injected)
                await page.route('**/'+engine_source(p).name+'*',intercept)
                await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                for scenario in scenarios:
                    r=await page.evaluate('''async s=>{
                        const api=JevTerramai;api.reset(20261017);
                        api.fixture({x:s.x??10,y:s.y??13.75,dirt:5,testGear:s.gear,tiles:Array.from({length:60},(_,x)=>[x,15,11]).concat(s.tiles),hideTiles:s.hideTiles||[]});
                        api.activate(true);let before=structuredClone(api.prepare({clock:'step'}));window.__targets=[];
                        let after=structuredClone(await api.act(s.action));api.activate(false);
                        return {before,after,first:window.__targets[0]||null,error:window.jevRenderError||null};
                    }''',scenario)
                    obs=r['first']['observation'] if r['first'] else r['before'];record=c.as_record(obs)
                    facts=c.collection_facts(obs,scenario['action']=='collect_visible_gem');target=facts['target'];effect=facts['successful_collection_effect']
                    local={'C0':r['after']['execution_audit']['rule_takeover_count']==0,'one_model_intent':r['after']['decisions']==1,'no_render_error':not r['error'],
                           'choice_availability':(scenario['action'] in record['questions']['decision']['criteria'])==facts['candidate_available'],
                           'deadline_unchanged':r['after']['control']['deadline_frames']==240,'recover_preserved':'recover' in record['questions']['decision']['criteria'],
                           'single_choice':list(record['questions'])==['decision']}
                    if target:
                        local['JS_Python_target_exact']=all(r['first']['target'].get(k)==v for k,v in target.items())
                        local['option_discloses_bound_target']=str(target) in record['questions']['decision']['criteria'][scenario['action']]
                        if effect['deterministic']:
                            local['native_collection_completed']=r['after']['control']['events']==['target_completed']
                            local['equipment_after_exact']=all(r['after']['equipment'][k]==v for k,v in effect['equipment_after'].items())
                            local['gem_gained_exact']=r['after']['equipment']['gems']-obs['equipment']['gems']==effect['gems_gained']
                    else:local['JS_no_hidden_target']=r['after']['control']['events']==['target_missing']
                    name=scenario['name']
                    if name=='chest_random_not_predicted':local['future_random_unknown']=effect['deterministic'] is False and effect['equipment_after'] is None
                    if name=='gem_selected_over_closer_ore':local['new_intent_keeps_ordinary_ore']=r['after']['stats']['ore']==0 and target['tile']==8
                    if name=='legacy_collect_keeps_nearest_ore':local['legacy_target_still_ordinary']=target['tile']==4
                    if name=='gem_equal_distance_x_tiebreak':local['smaller_x_wins']=target['x']==9
                    if name=='gem_equal_distance_y_tiebreak':local['smaller_y_wins']=target['y']==13
                    if name=='gem_uses_exact_geometry':local['exact_geometry_breaks_rounded_tie']=target['x']==11
                    r.update(name=name,facts=facts,upgrade_rules=c.progression_facts(obs),checks=local);rows.append(r)
                    checks.update({name+':'+k:v for k,v in local.items()})
                kills=[]
                for lv,boss in [(2,False),(3,False),(3,True)]:
                    result=await page.evaluate('''async ({lv,boss})=>{
                      const api=JevTerramai;api.reset(20261017);
                      api.fixture({x:10,y:13.75,dirt:0,testGear:{gems:1,pts:2},tiles:Array.from({length:25},(_,x)=>[x,15,11]),
                        enemies:[{kind:'slime',x:11.2*16,y:14.3*16,w:14,h:11,hp:1,maxhp:1,lv,boss,vx:0,vy:0,t:0,ground:true}]});
                      api.activate(true);const before=structuredClone(api.prepare({clock:'step'})),after=structuredClone(await api.act('fight_nearest'));api.activate(false);return {before,after};
                    }''',{'lv':lv,'boss':boss})
                    facts=c.progression_facts(result['before']);expected=dict(facts['equipment'])
                    c._apply_points(expected,lv,facts['equipment_level_cap'])
                    if lv>=3:expected['gems']+=1;c._apply_gem_armor(expected,facts['equipment_level_cap'])
                    if boss:expected['gems']+=5
                    key=f'actual_player_kill_lv{lv}_boss{boss}'
                    checks[key+'_true_credit']=result['after']['progression']['player_direct_kills']==1 and result['after']['progression']['player_attack_damage']>0
                    checks[key+'_public_upgrade_rules_match']=all(result['after']['equipment'][k]==v for k,v in expected.items())
                    checks[key+'_no_guardian_unlock']=not result['after']['objective']['gate_unlocked']
                    kills.append(dict(level=lv,boss=boss,expected=expected,**result))
                extra=await page.evaluate('''async()=>{
                    const api=JevTerramai;
                    api.fixture({x:10,y:13.75,hp:.05,dirt:0,tiles:Array.from({length:20},(_,x)=>[x,15,11]).concat([[10,14,15],[12,14,8]])});
                    api.activate(true);const before=structuredClone(api.prepare({clock:'step'})),dead=structuredClone(await api.act('collect_visible_gem')),recovered=structuredClone(await api.act('recover'));api.activate(false);
                    api.fixture({x:10,y:8,dirt:0,tiles:Array.from({length:20},(_,x)=>[x,15,11]).concat([[12,14,8]])});api.activate(true);
                    const waitBefore=structuredClone(api.prepare({clock:'realtime'}));await new Promise(r=>setTimeout(r,650));const waitAfter=structuredClone(api.snapshot());api.activate(false);
                    return {before,dead,recovered,waitBefore,waitAfter};
                }''')
                checks.update(death_recorded=extra['dead']['deaths']==1,death_feedback=extra['dead']['control']['events']==['death_or_respawn'],
                    death_no_unearned_gem=extra['dead']['equipment']['gems']==0,respawn_count_preserved=extra['recovered']['progression']['death_count']==1 and extra['recovered']['progression']['respawn_count']==1,
                    wait_frames_advance=extra['waitAfter']['frame']>extra['waitBefore']['frame']+20,wait_gravity=extra['waitAfter']['player']['y']!=extra['waitBefore']['player']['y'],
                    wait_no_new_decision=extra['waitAfter']['decisions']==extra['waitBefore']['decisions'],wait_C0=extra['waitAfter']['execution_audit']['rule_takeover_count']==0)
            finally:await browser.close()
    finally:await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
    assert test_source(js)==source
    result={'passed':all(checks.values()),'checks':checks,'cases':len(rows)+len(kills),'rows':rows,'kills':kills,'extra':extra,'real_chromium':True,'model_calls':0,'GPU_calls':0,'test_fixture_not_model_victory':True}
    with args.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':result['passed'],'cases':result['cases'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v]}),flush=True)
    return int(not result['passed'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
