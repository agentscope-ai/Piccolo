"""Native four-way sword AABB and selected-combat execution, no model calls."""
from __future__ import annotations
import argparse,asyncio,functools,json,sys,threading,copy,random
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture
PACKAGE=Path(__file__).resolve().parents[1]
PUBLIC_CASE={'player': {'x': 62.5, 'y': 39.7, 'width': 0.625, 'height': 1.25, 'geometry': {'x': 62.48740913833604, 'y': 39.728124999999984}, 'vx': 0, 'vy': 0, 'invulnerable_frames': 0, 'tile': [62, 40], 'hp': 100, 'max_hp': 100, 'on_ground': True, 'facing': 1, 'aim': 'down', 'respawning': False}, 'map': {'origin': [52, 34], 'tiles': [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 10, 10, 10, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 10, 10, 10, 0, 0, 0, 10, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 9, 0, 0, 0, 0, 0, 10, 10, 0, 10], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 2, 1, 1, 1, 9, 0, 0, 0, 0, 0, 9, 1, 1, 0], [1, 1, 1, 1, 2, 2, 2, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 9, 0, 0, 0], [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2], [1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1], [3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1]], 'legend': {'0': '空气', '1': '泥土', '2': '草地', '3': '石头', '4': '铜', '5': '铁', '6': '金', '7': '钻石', '8': '宝石', '9': '木头', '10': '树叶', '11': '基岩', '12': '胜利之门', '13': '宝箱', '14': '熔岩', '15': '毒雾', '-1': '未知'}}, 'equipment': {'pick': 8, 'sword': 8, 'armor': 3, 'gems': 7, 'pts': 7, 'dirt': 19, 'swordMul': 1, 'pickMul': 1, 'armorMul': 1, 'potAtk': 0, 'potArm': 0}, 'enemies': [{'id': 14, 'x': 64, 'y': 41.7, 'width': 0.75, 'height': 1.25, 'kind': 'zombie', 'hp': 30, 'boss': False, 'gate_guardian': False, 'player_damage_received': 0, 'level': 1}]}
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
async def main(a):
 package=a.package.resolve();sys.path.insert(0,str(package));import blink_arena;import jev_terraria_contract as c
 assert Path(c.__file__).resolve().is_relative_to(package)
 js=engine_source(package);source=test_source(js);inject=source
 needle='(f.tiles||[]).forEach(function(t){setT(t[0],t[1],t[2])});'
 inject=inject.replace(needle,needle+"if(f.testGear)Object.assign(gear,f.testGear);if(f.publicMap){explored.fill(0);f.publicMap.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(v>=0)explored[idx(x+f.publicMap.origin[0],y+f.publicMap.origin[1])]=1}));}")
 marker='if(window.__JEV_TEST_MODE__){';assert inject.count(marker)==1
 inject=inject.replace(marker,marker+"window.__nativeSword=(p,e)=>Object.fromEntries(['left','right','up','down'].map(a=>{const r=attackRectangle(a,p.x*16,p.y*16,p.width*16,p.height*16);return [a,{x:r.x/16,y:r.y/16,width:r.w/16,height:r.h/16,intersects_enemy:attackIntersects(r,{x:e.x*16,y:e.y*16,w:e.width*16,h:e.height*16})}]}));")
 needle='  function jevIntentKeys(action){';assert inject.count(needle)==1
 inject=inject.replace(needle,"""  function jevIntentKeys(action){var ks=jevIntentKeysOriginal(action);if(action==='fight_nearest'&&jevControl.execution_stage==='attack_in_range'){var o=jevSnapshot(),e=o.enemies.find(e=>e.id===jevControl.target.id);if(e){var p=Object.assign({},o.player,o.player.geometry),eg=Object.assign({},e,e.geometry);window.__combatFrames.push({aim:jevAim,hit:window.__nativeSword(p,eg)[jevAim].intersects_enemy,frame});}}return ks;}
  function jevIntentKeysOriginal(action){""")
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(package/'web')));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();checks={};rows={};matrix=[]
 try:
  async with async_playwright() as pw:
   browser=await pw.chromium.launch(headless=True)
   try:
    page=await browser.new_page();await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__combatFrames=[];')
    async def route(r):await r.fulfill(status=200,content_type='application/javascript',body=inject)
    await page.route('**/'+engine_source(package).name+'*',route);await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
    rng=random.Random(1712);positions=[(7.5+d,10) for d in [-1e-7,0,1e-7]]+[(12.375+d,10) for d in [-1e-7,0,1e-7]]+[(10,7+d) for d in [-1e-7,0,1e-7]]+[(10,13+d) for d in [-1e-7,0,1e-7]]+[(11.7,12),(10.1,10.1)]
    for aim in ('left','right','up','down'):
     for ex,ey in positions:
      r=await page.evaluate("""({aim,ex,ey})=>{const api=JevTerramai;api.fixture({x:10,y:10,dirt:0,enemies:[{kind:'zombie',x:ex*16,y:ey*16,w:12,h:20,hp:1000,maxhp:1000,lv:1,vx:0,vy:0,hop:40,t:0,ground:false}]});const before=structuredClone(api.snapshot()),after=structuredClone(api.probe('attack_'+aim,1));return {before,after};}""",{'aim':aim,'ex':ex,'ey':ey})
      ob=r['before'];e=ob['enemies'][0];f=c.native_attack_facts(ob,e);actual=r['after']['progression']['player_attack_hits']>0
      matrix.append({'aim':aim,'ex':ex,'ey':ey,'facts':f,'actual_native_hit':actual});assert actual==f['rectangles_tiles'][aim]['intersects_enemy'],(aim,ex,ey,f,actual)
    checks['native_56_directional_boundary_cases']=len(matrix)==56
    probes=[]
    for i in range(160):
     p={'x':10+rng.random()*.1,'y':10+rng.random()*.1,'width':.625,'height':1.25};e={'x':8+rng.random()*5,'y':8+rng.random()*5,'width':.7+rng.random()*.3,'height':.7+rng.random()*1.8}
     probes.append({'p':p,'e':e})
    native=await page.evaluate('xs=>xs.map(x=>window.__nativeSword(x.p,x.e))',probes)
    checks['JS_Python_640_exact_rectangles']=all(c.native_attack_facts({'player':dict(x['p'],geometry=x['p'])},dict(x['e'],geometry=x['e']))['rectangles_tiles']==got for x,got in zip(probes,native))
    old=copy.deepcopy(matrix[0]['facts']);legacy=c.native_attack_facts({'player':{'x':10,'y':10,'width':.625,'height':1.25}}, {'x':12.375,'y':10,'width':.75,'height':1.25})
    checks['legacy_rounded_is_estimate']=legacy['geometry_exact'] is False and legacy['geometry_basis']=='legacy_rounded_geometry_estimate'
    r=await page.evaluate("""async o=>{const api=JevTerramai,tiles=[];o.map.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(v>=0)tiles.push([x+o.map.origin[0],y+o.map.origin[1],v])}));api.fixture({x:o.player.geometry.x,y:o.player.geometry.y,dirt:o.equipment.dirt,tiles,testGear:o.equipment,publicMap:o.map,enemies:o.enemies.map(e=>({kind:e.kind,x:e.x*16,y:e.y*16,w:e.width*16,h:e.height*16,hp:e.hp,maxhp:e.hp,lv:e.level,vx:0,vy:0,t:0,hop:40,ground:true}))});api.activate(true);window.__combatFrames=[];const before=structuredClone(api.prepare({clock:'step'})),after=structuredClone(await api.act('fight_nearest'));api.activate(false);return {before,after,frames:window.__combatFrames};}""",PUBLIC_CASE);rows['recorded_corner']=r
    checks.update(recorded_corner_genuine_hit=r['after']['progression']['player_attack_hits']>0,recorded_corner_completed=r['after']['control']['events']==['target_completed'],recorded_corner_original_hp=r['before']['enemies'][0]['hp']==30,recorded_corner_B_approach=r['after']['player']['x']>r['before']['player']['x']+.2,recorded_corner_C0=r['after']['execution_audit']['rule_takeover_count']==0)
    for name,ceil,below,moving in [('jump_up',False,False,False),('ceiling',True,False,False),('below_unreachable',False,True,False),('moving_enemy',False,False,True)]:
     r=await page.evaluate("""async s=>{const api=JevTerramai;let tiles=Array.from({length:30},(_,x)=>[x,15,11]);let e={kind:'zombie',x:10.2*16,y:9.75*16,w:12,h:20,hp:9,maxhp:9,lv:1,vx:0,vy:0,t:0,hop:40,ground:true};if(s.below){e.y=19*16;tiles.push([10,21,11],[11,21,11])}else if(s.moving){e.x=14*16;e.y=13.75*16}else tiles.push([10,11,11],[11,11,11]);if(s.ceil)tiles.push([10,12,11],[11,12,11]);api.fixture({x:10,y:13.75,dirt:5,tiles,enemies:[e]});api.activate(true);window.__combatFrames=[];const before=structuredClone(api.prepare({clock:'step'})),after=structuredClone(await api.act('fight_nearest'));api.activate(false);return {before,after,frames:window.__combatFrames};}""",{'ceil':ceil,'below':below,'moving':moving});rows[name]=r
     checks[name+':C0']=r['after']['execution_audit']['rule_takeover_count']==0
     checks[name+':never_false_in_range']=all(f['hit'] for f in r['frames'])
     checks[name+':original_deadline']=r['after']['control']['deadline_frames']==240
     if name in ('jump_up','moving_enemy'):checks[name+':actual_hit']=r['after']['progression']['player_attack_hits']>0
     else:checks[name+':honest_blocked']=r['after']['control']['status']=='blocked' and bool(r['after']['control']['failure_reason'])
    checks['all_recorded_corner_in_range_true']=all(f['hit'] for f in rows['recorded_corner']['frames'])
    checks['new_enemy_geometry_is_exact']=all(k in rows['recorded_corner']['before']['enemies'][0]['geometry'] for k in ('x','y','width','height'))
    facts=c.as_record(rows['recorded_corner']['before']);checks['choice_reports_actual_hit_directions']='当前原生剑框命中方向=[]' in facts['questions']['decision']['criteria']['fight_nearest']
    checks['no_render_error']=not await page.evaluate('window.jevRenderError||null')
   finally:await browser.close()
 finally:await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)
 assert test_source(js)==source
 result={'passed':all(checks.values()),'checks':checks,'rows':rows,'native_matrix':matrix,'geometry_probes':probes,'legacy_estimate':legacy,'model_calls':0,'GPU_calls':0,'real_chromium':True,'fixture_not_capability_score':True}
 with a.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps({'passed':result['passed'],'checks':len(checks),'native_cases':len(matrix),'exact_rectangles':len(probes)*4,'failed':[k for k,v in checks.items() if not v]},ensure_ascii=False));return int(not result['passed'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=PACKAGE);p.add_argument('--out',type=Path,required=True);raise SystemExit(asyncio.run(main(p.parse_args())))
