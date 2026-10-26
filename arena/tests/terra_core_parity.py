"""Native Node core vs archived original Chromium engine, same actions/frames.

The old page gets an explicit test-only frame driver. The new Node process
requires the production module directly; no fake DOM, original-page eval or VM.
"""
import argparse
import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading
import time

from playwright.async_api import async_playwright

PACKAGE=Path(__file__).resolve().parents[1]
HOOK=r'''
  window.__TerraParity={advanceTo(target){
    let safety=0;while(frame<target){if(++safety>200000||jevEpisodeTerminal)throw Error('unreachable');jevAdvance();}
    if(frame!==target)throw Error('frame mismatch');return frame;
  },terminal(){return {outcome:jevEpisodeTerminal?'win':null,wins,frame};}};
'''


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


async def main(args):
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(PACKAGE/'web')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    result={'scope':'original Chromium physics vs production Node module; no model call/GPU; fixture trajectories are not capability scores',
            'checks':[], 'seed_rows':[]}
    node=await asyncio.create_subprocess_exec('node',str(Path(__file__).with_name('terra_core_parity_node.cjs')),
        stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
        limit=4*1024*1024)
    async def rpc(command):
        node.stdin.write((json.dumps(command)+'\n').encode());await node.stdin.drain()
        value=json.loads(await node.stdout.readline());assert value['ok'],value
        return value['value']
    old_source=args.original.read_text();marker=old_source.rfind('})();');assert marker>0
    old_source=old_source[:marker]+HOOK+old_source[marker:]
    try:
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,args=['--disable-gpu'])
            page=await browser.new_page()
            await page.add_init_script('window.__JEV_TEST_MODE__=true;window.requestAnimationFrame=()=>0;')
            async def original(route):await route.fulfill(status=200,content_type='application/javascript',body=old_source)
            await page.route('**/terraria.js*',original)
            await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html',wait_until='domcontentloaded')
            await page.wait_for_function('!!window.__TerraParity')
            current=await browser.new_page()
            await current.add_init_script('window.requestAnimationFrame=()=>0;')
            await current.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html',wait_until='domcontentloaded')
            await current.wait_for_function('!!window.JevTerramai?.advanceTo')
            async def chrome(command,target=page):
                return await target.evaluate('''c=>{
                  const g=JevTerramai;
                  if(c.op==='reset'){g.reset(c.seed);g.activate(true);g.prepare({clock:'realtime'});window.__settled=null;}
                  else if(c.op==='prepare')g.prepare({clock:c.clock||'realtime'});
                  else if(c.op==='act'){window.__settled=null;g.act(c.action).then(value=>{window.__settled=value;});}
                  else if(c.op==='advance')(window.__TerraParity||g).advanceTo(c.frame);
                  else if(c.op==='terminal')return (window.__TerraParity||g).terminal();
                  else if(c.op==='private'){
                    if(g.inspectWorld){let s=g.inspectWorld();delete s.lastHitF;delete s.gateFails;return s;}
                    const s=g.renderState();return {world:Array.from(s.world),explored:Array.from(s.explored),surface:s.surf,spawn:s.spawn,goal:s.goal,
                      enemies:s.enemies,items:s.items,chests:s.chests,player:s.P,gear:s.gear,stat:s.stat,wins:s.wins,
                      deaths:s.deaths,frame:s.frame,evt:s.evt,buffs:s.buffs,agent:s.agent};
                  }
                  else if(c.op==='settled')return window.__settled;
                  else if(c.op!=='snapshot')throw Error('unknown command');
                  return g.snapshot();
                }''',command)
            comparisons=0
            numeric_differences=[]
            def differences(a,b,path=''):
                if a==b:return []
                if isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys():
                    return [d for k in a for d in differences(a[k],b[k],path+'.'+k)]
                if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
                    return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,f'{path}[{i}]')]
                if type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b):
                    return [{'path':path,'old':a,'node':b,'absolute_error':abs(a-b)}]
                return [{'path':path,'structural_difference':True}]
            async def same(command):
                nonlocal comparisons
                a,b,c=await asyncio.gather(chrome(command),rpc(command),chrome(command,current))
                if a!=c:
                    args.out.with_suffix('.browser-difference.json').write_text(json.dumps({'command':command,'old':a,'new_browser':c},ensure_ascii=False,indent=2))
                    raise AssertionError('Old/new Chromium core mismatch: '+json.dumps(command))
                if a!=b:
                    delta=differences(a,b)
                    # Report every cross-V8 numeric difference. No production
                    # value or assertion of browser exact equivalence is rounded.
                    if command['op']!='private' or any(x.get('structural_difference') or x['absolute_error']>1e-9 for x in delta):
                        args.out.with_suffix('.difference.json').write_text(json.dumps({'command':command,'old':a,'node':b,'delta':delta},ensure_ascii=False,indent=2))
                        raise AssertionError('Native state mismatch: '+json.dumps(command))
                    numeric_differences.extend(delta)
                comparisons+=1
                return b
            actions=['explore_right','collect_visible','mine_down','move_right','jump_move_right','return_surface',
                     'collect_visible_gem','recover','fight_nearest','approach_guardian','fight_guardian',
                     'reach_known_goal','pass_enemy_right','retreat_left','cross_gap_right','clear_right','explore_left','wait']
            for seed in [0,1,17,1194710013,1792178101,4294967295]:
                state=await same({'op':'reset','seed':seed})
                await same({'op':'private'})
                # Runtime terminal polling must not reveal/observe new geometry.
                before=state
                for _ in range(20):await same({'op':'terminal'})
                assert await same({'op':'snapshot'})==before
                applied=0
                for i,action in enumerate(actions*2):
                    state=await same({'op':'prepare'})
                    # Same actual wait frames, then same mechanical intent.
                    state=await same({'op':'advance','frame':state['frame']+[0,1,17,61][i%4]})
                    await same({'op':'act','action':action});applied+=1
                    for span in [1,35,64,140,120]:
                        state=await same({'op':'advance','frame':state['frame']+span})
                        if await same({'op':'settled'}) is not None:break
                    await same({'op':'private'})
                    if state['episode_terminal']:break
                result['seed_rows'].append({'seed':seed,'frame':state['frame'],'actions':applied,
                    'deaths':state['deaths'],'wins':state['wins'],'progression':state['progression']})
                print(json.dumps({'seed':seed,'frame':state['frame'],'comparisons':comparisons}),flush=True)
            result['checks'].append({'name':'six_seed_node_public_exact_and_private_numeric_bound_1e9','passed':True,
                                     'comparisons':comparisons,'actions':sum(x['actions']for x in result['seed_rows'])})
            result['cross_runtime_private_bitwise_equal']=not numeric_differences
            result['cross_runtime_private_numeric_differences']=numeric_differences
            result['browser_old_new_all_fields_exact']=True
            await browser.close()
        result['passed']=True
    except BaseException as error:
        result['passed']=False;result['error']=str(error);raise
    finally:
        node.stdin.close();await node.wait()
        await asyncio.to_thread(server.shutdown);server.server_close()
        result['at']=time.time();args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'passed':result['passed'],'out':str(args.out)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--original',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
