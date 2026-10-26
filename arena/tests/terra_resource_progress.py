"""Public-map resource descent and honest progress regressions, real Chromium, no model."""
from __future__ import annotations
import argparse,asyncio,functools,json,sys,threading
from collections import Counter
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture
PACKAGE=Path(__file__).resolve().parents[1]
# Captured public geometry only; unknown cells remain unexplored in the fixture.
PUBLIC_CASE={'player': {'x': 159.9, 'y': 39.7, 'width': 0.625, 'height': 1.25, 'geometry': {'x': 159.93320529733776, 'y': 39.74687499999994}, 'vx': 0.039, 'vy': 0, 'invulnerable_frames': 0, 'tile': [160, 40], 'hp': 100, 'max_hp': 100, 'on_ground': True, 'facing': 1, 'aim': 'right', 'respawning': False}, 'map': {'origin': [150, 34], 'tiles': [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 0, 0, 0, 10, 10, 10], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 10, 10, 0, 10, 10, 10, 10], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 0, 0, 0, 10, 10, 10], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 9, 0, 0, 0, 0, 0, 9, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 0], [0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 0], [2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 1, 1, 1, 9, 1, 1, 1, 1, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 0, 0, 0, 2, 2, 2, 2, 2, 2, 0], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 7, 0], [1, 1, 1, 1, 1, 3, 3, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 6, 0]], 'legend': {'0': '空气', '1': '泥土', '2': '草地', '3': '石头', '4': '铜', '5': '铁', '6': '金', '7': '钻石', '8': '宝石', '9': '木头', '10': '树叶', '11': '基岩', '12': '胜利之门', '13': '宝箱', '14': '熔岩', '15': '毒雾', '-1': '未知'}}, 'equipment': {'pick': 3, 'sword': 3, 'armor': 0, 'gems': 1, 'pts': 1, 'dirt': 1, 'swordMul': 1, 'pickMul': 1, 'armorMul': 1, 'potAtk': 0, 'potArm': 0}}
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
async def main(a):
 package=a.package.resolve();sys.path.insert(0,str(package));import blink_arena;import jev_terraria_contract as contract
 assert Path(contract.__file__).resolve().is_relative_to(package)
 js=engine_source(package);source=test_source(js)
 needle='(f.tiles||[]).forEach(function(t){setT(t[0],t[1],t[2])});'
 assert source.count(needle)==1
 inject=source.replace(needle,needle+"if(f.testGear)Object.assign(gear,f.testGear);if(f.publicMap){explored.fill(0);f.publicMap.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(v>=0)explored[idx(x+f.publicMap.origin[0],y+f.publicMap.origin[1])]=1}));}")
 inject=inject.replace('if (agent.digP >= HARD[t]) {','if (agent.digP >= HARD[t]) {if(window.__tools)window.__tools.push({kind:"mine",x:tx,y:ty,tile:t,frame});')
 inject=inject.replace('jevControl.execution_counts.placed++;','jevControl.execution_counts.placed++;if(window.__tools)window.__tools.push({kind:"place",x,y,frame});')
 marker='if(window.__JEV_TEST_MODE__){'
 assert inject.count(marker)==1
 inject=inject.replace(marker,marker+"window.__progress=jevMeaningfulProgress;")
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(package/'web')));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 checks={};rows={}
 try:
  async with async_playwright() as pw:
   browser=await pw.chromium.launch(headless=True)
   try:
    page=await browser.new_page();await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__tools=[];')
    async def route(r):await r.fulfill(status=200,content_type='application/javascript',body=inject)
    await page.route('**/'+engine_source(package).name+'*',route);await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
    for gem in (False,True):
     r=await page.evaluate("""async ({o,gem})=>{const api=JevTerramai,tiles=[];o.map.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(v>=0)tiles.push([x+o.map.origin[0],y+o.map.origin[1],gem&&v===7?8:v])}));api.reset(1792164002);api.fixture({x:o.player.geometry.x,y:o.player.geometry.y,pick:o.equipment.pick,dirt:o.equipment.dirt,tiles,testGear:o.equipment,publicMap:o.map});api.activate(true);window.__tools=[];const before=structuredClone(api.prepare({clock:'step'})),after=structuredClone(await api.act(gem?'collect_visible_gem':'collect_visible'));api.activate(false);return {before,after,tools:window.__tools};}""",{'o':PUBLIC_CASE,'gem':gem})
     name='gem_public_descent' if gem else 'ore_public_descent';rows[name]=r;after=r['after'];c=after['control'];tools=r['tools'];placed={(t['x'],t['y']) for t in tools if t['kind']=='place'}
     checks.update({name+':completed':c['events']==['target_completed'],name+':actual_gain':after['stats']['gem' if gem else 'ore']==1,name+':within_original_budget':c['recent_effects'][-1]['frames']<=240,name+':no_recycled_support':not any(t['kind']=='mine' and (t['x'],t['y']) in placed for t in tools),name+':movement':after['player']['x']-r['before']['player']['x']>5,name+':C0':after['execution_audit']['rule_takeover_count']==0,name+':both_feedback_progress':c['recent_effects'][-1]['meaningful_progress'] and after['last_effects'][-1]['meaningful_progress']})
    r=await page.evaluate("""async()=>{const api=JevTerramai;api.fixture({x:10,y:13.75,dirt:6,pick:3,tiles:Array.from({length:25},(_,x)=>[x,15,[13,14].includes(x)?0:11]).concat([[18,14,4]])});api.activate(true);const before=structuredClone(api.prepare({clock:'step'})),after=structuredClone(await api.act('collect_visible'));api.activate(false);return {before,after};}""");rows['horizontal_bridge']=r
    checks.update(horizontal_resource_still_collected=r['after']['stats']['ore']==1,horizontal_bridge_still_used=r['after']['control']['execution_counts']['placed']>0)
    r=await page.evaluate("""async()=>{const api=JevTerramai;api.fixture({x:10,y:13.75,dirt:0,tiles:Array.from({length:25},(_,x)=>[x,15,11]).concat([[17,14,7],[16,14,11],[18,14,11],[17,13,11]])});api.activate(true);const before=structuredClone(api.prepare({clock:'step'})),first=structuredClone(await api.act('collect_visible')),second=structuredClone(await api.act('collect_visible'));api.activate(false);const reset=structuredClone(api.reset(1792164002));return {before,first,second,reset};}""");rows['blocked_resource']=r
    second=r['second'];record=contract.as_record(second);facts=record['state']['navigation']['collection']['collect_visible'];first=r['first']
    checks.update(blocked_feedback=first['control']['status']=='blocked' and second['control']['status']=='blocked',blocked_reason_visible=second['control']['failure_reason']=='no_public_path_to_resource',no_progress_increments=first['control']['no_progress_count']==1 and second['control']['no_progress_count']==2,failure_history_increments=facts['previous_failure_count']==2,failure_option_disclosed='no_public_path_to_resource' in record['questions']['decision']['criteria']['collect_visible'],candidate_not_arbitrarily_removed='collect_visible' in record['questions']['decision']['criteria'],reset_clears_history=not r['reset']['control']['failed_targets'],reset_clears_no_progress=r['reset']['control']['no_progress_count']==0,blocked_C0=second['execution_audit']['rule_takeover_count']==0)
    r=await page.evaluate("""()=>{const p={x:0,y:0,deaths:0,hp:100,ore:0,gem:0,chest:0,kill:0,pick:1,sword:1,armor:0,terrain:'',dig:null,dig_progress:0},q=window.__progress;return {jitter_not_progress:!q(p,{...p,x:.12*16}),threshold_progress:q(p,{...p,x:.25*16}),restored_terrain_not_progress:!q(p,{...p,terrain:''}),net_terrain_progress:q(p,{...p,terrain:'10,15:1'}),ore_progress:q(p,{...p,ore:1}),death_not_progress:!q(p,{...p,deaths:1,x:100}),partial_native_dig_progress:q({...p,dig:'10,15',dig_progress:2},{...p,dig:'10,15',dig_progress:3})};}""");rows['progress_predicates']=r;checks.update(r)
    checks['no_render_error']=not await page.evaluate('window.jevRenderError||null')
   finally:await browser.close()
 finally:await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
 assert test_source(js)==source
 result={'passed':all(checks.values()),'checks':checks,'rows':rows,'package':str(package),'scope':'public geometry fixtures, never teacher/student victories','real_chromium':True,'model_calls':0,'GPU_calls':0}
 with a.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v]},ensure_ascii=False));return int(not result['passed'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=PACKAGE);p.add_argument('--out',type=Path,required=True);raise SystemExit(asyncio.run(main(p.parse_args())))
