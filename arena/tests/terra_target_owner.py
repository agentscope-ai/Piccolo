"""Real Chromium target-ownership regressions; no model/backend/GPU calls."""
from __future__ import annotations
import argparse
import asyncio
import copy
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture
import sys

PACKAGE = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

async def run(package):
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(package / 'web')))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;')
                await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                return await page.evaluate('''async()=>{
                  const api=JevTerramai,snap=()=>structuredClone(api.snapshot()),act=async action=>structuredClone(await api.act(action));
                  const fixture={x:22,y:40.75,dirt:0,tiles:Array.from({length:17},(_,i)=>[14+i,42,i===8?2:11]),goal:[237,30],exploredGoal:true};
                  async function one(previousGoal){
                    api.fixture(fixture);api.probe('jump_move_up',previousGoal?1:2);api.activate(true);api.prepare({clock:'step'});
                    let prior=null;if(previousGoal)prior=await act('reach_known_goal');
                    const before=snap(),after=await act('return_surface');api.activate(false);
                    return {prior,before,after};
                  }
                  const clean=await one(false),switched=await one(true);
                  const tiles=Array.from({length:25},(_,i)=>[i,15,11]).concat([[9,10,2],[13,10,2],[10,12,11]]);
                  api.fixture({x:10,y:13.75,dirt:0,tiles});api.activate(true);api.prepare({clock:'step'});
                  const first=await act('return_surface');api.probe('move_right',24);
                  const beforeContinue=snap(),continued=await act('return_surface');api.activate(false);
                  const deathTiles=Array.from({length:21},(_,i)=>[i+3,15,1]).concat([[9,10,2]],Array.from({length:5},(_,i)=>[10,i+10,15]));
                  api.fixture({x:10,y:13.75,dirt:8,hp:.05,tiles:deathTiles});api.activate(true);api.prepare({clock:'step'});
                  const dead=await act('return_surface'),respawned=await act('recover');api.activate(false);
                  api.fixture(fixture);api.probe('jump_move_up',1);api.activate(true);
                  const waitBefore=structuredClone(api.prepare({clock:'realtime'}));await new Promise(r=>setTimeout(r,650));
                  const waitAfter=snap();api.activate(false);
                  api.fixture({x:10,y:13.75,dirt:0,tiles:Array.from({length:22},(_,i)=>[i+3,15,11]).concat([[11,14,2]])});
                  const beforeMine=snap();api.probe('mine_right',36);api.activate(true);api.prepare({clock:'step'});
                  const removedBefore=snap(),removedAfter=await act('return_surface');api.activate(false);
                  return {removed:{beforeMine,before:removedBefore,after:removedAfter},clean,switched,sameIntent:{first,before:beforeContinue,after:continued},death:{dead,respawned},waiting:{before:waitBefore,after:waitAfter},render_error:window.jevRenderError||null};
                }''')
            finally: await browser.close()
    finally:
        await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)

async def main(args):
    args.package = args.package.resolve()
    sys.path.insert(0, str(args.package))
    import blink_arena  # Register only this independent package's bundled engines.
    import jev_terraria_contract as contract
    assert Path(contract.__file__).resolve().is_relative_to(args.package), 'contract must come from the selected package'
    as_record, return_surface_anchor = contract.as_record, contract.return_surface_anchor
    r = await run(args.package)
    checks = {}
    for name in ('clean', 'switched', 'sameIntent'):
        lane = r[name];before,after=lane['before'],lane['after'];record=as_record(before)
        lane['before_record']=record
        anchor=return_surface_anchor(before)
        checks[name+'_candidate_matches_execution']=record['state']['navigation']['return_surface_anchor']==after['control']['target_surface']==anchor
        checks[name+'_option_discloses_anchor']=str(anchor) in record['questions']['decision']['criteria']['return_surface']
        checks[name+'_owner']=after['control']['target_surface_owner']=='return_surface'
        checks[name+'_no_takeover']=after['execution_audit']['rule_takeover_count']==0
    checks.update(
        same_physical_state=r['clean']['before']['player']==r['switched']['before']['player'],
        same_public_map=r['clean']['before']['map']==r['switched']['before']['map'],
        previous_goal_owned=r['switched']['prior']['control']['target_surface_owner']=='reach_known_goal',
        previous_goal_remote=r['switched']['prior']['control']['target_surface']==[237,31],
        switched_local=r['switched']['after']['control']['target_surface']==[22,42],
        both_return_without_material=all(r[n]['after']['control']['events']==['goal_reached'] and r[n]['after']['player']['on_ground'] and r[n]['before']['equipment']['dirt']==0 for n in ('clean','switched')),
        same_intent_retains_target=r['sameIntent']['first']['control']['target_surface']==r['sameIntent']['after']['control']['target_surface'],
        same_intent_new_local_is_different=r['sameIntent']['before']['last_known_surface']!=r['sameIntent']['first']['control']['target_surface'],
        death_recorded=r['death']['dead']['deaths']==1 and r['death']['dead']['control']['events']==['death_or_respawn'],
        respawn_recorded=not r['death']['respawned']['player']['respawning'],
        death_clears_target=r['death']['dead']['control']['target_surface'] is None and r['death']['dead']['control']['target_surface_owner'] is None and not r['death']['dead']['control']['path'] and r['death']['dead']['control']['subgoal'] is None,
        respawn_clears_target=r['death']['respawned']['control']['target_surface'] is None and r['death']['respawned']['control']['target_surface_owner'] is None,
        realtime_wait_advances=r['waiting']['after']['frame']>r['waiting']['before']['frame']+20,
        realtime_wait_no_model_action=r['waiting']['after']['decisions']==r['waiting']['before']['decisions'],
        realtime_wait_gravity=r['waiting']['after']['player']['y']!=r['waiting']['before']['player']['y'],
        removed_support_actually_mined=r['removed']['beforeMine']['last_known_surface']==[11,14] and r['removed']['before']['equipment']['dirt']>0,
        removed_support_no_candidate='return_surface' not in as_record(r['removed']['before'])['questions']['decision']['criteria'],
        removed_support_no_execution_anchor=r['removed']['after']['control']['target_surface'] is None and r['removed']['after']['control']['events']==['blocked_unknown_surface'],
        no_render_error=not r['render_error'],
    )
    # Pure contract checks cover invalidated targets without reading private state.
    base=copy.deepcopy(r['sameIntent']['before']);base['control']['events']=[]
    for name,event in [('completed','goal_reached'),('death','death_or_respawn'),('respawn','respawned')]:
        sample=copy.deepcopy(base);sample['control']['events']=[event]
        checks[name+'_candidate_refreshes']=return_surface_anchor(sample)==sample['last_known_surface']
    sample=copy.deepcopy(base);sample['control']['target_surface_owner']='reach_known_goal'
    checks['foreign_owner_candidate_refreshes']=return_surface_anchor(sample)==sample['last_known_surface']
    sample=copy.deepcopy(base);sample['control']['status']='completed'
    checks['completed_status_candidate_refreshes']=return_surface_anchor(sample)==sample['last_known_surface']
    sample=copy.deepcopy(base);sample['player']['respawning']=True
    checks['respawning_candidate_refreshes']=return_surface_anchor(sample)==sample['last_known_surface']
    result={'scope':'independent real Chromium fixtures; not model episodes','model_calls':0,'GPU_calls':0,'package':str(args.package),'checks':checks,'passed':all(checks.values()),'result':r}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v],'frames':{n:r[n]['after']['control']['recent_effects'][-1]['frames'] for n in ('clean','switched','sameIntent')}},ensure_ascii=False),flush=True)
    return int(not result['passed'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
