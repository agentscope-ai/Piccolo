"""Original Chromium versus shared Mario core, with full public snapshots.

Controller-only hooks drive the pre-extraction script at exact frames. No policy,
API service, GPU, hidden state in observations, or second game simulator is used.
"""
from __future__ import annotations
import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import tempfile
from pathlib import Path
import subprocess
import threading
import unittest
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get('JEV_CORE_TEST_EVIDENCE', str(Path(tempfile.gettempdir()) / 'jev-core-tests'))) / 'mario'
ORIGINAL = Path(os.environ.get('JEV_MARIO_ORIGINAL_SCRIPT', str(ROOT / 'tests' / 'fixtures' / 'mario-before.js')))
EVIDENCE.mkdir(parents=True, exist_ok=True)

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

class MarioCoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT/'web')))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch(headless=True,args=['--no-sandbox'])
    async def asyncTearDown(self):
        await self.browser.close(); await self.pw.stop()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    async def pages(self):
        old=await self.browser.new_page(viewport={'width':1000,'height':700})
        new=await self.browser.new_page(viewport={'width':1000,'height':700})
        original=ORIGINAL.read_text()
        original=original.replace('  function tick(ts){', '''  window.__originalAdvanceTo=target=>{while(frame<target&&!outcome){if(remaining>0)advanceSelectedAction();else physics(0,false);}return frame;};
  function tick(ts){''')
        await old.route('**/mario.js?*',lambda route:route.fulfill(body=original,content_type='application/javascript'))
        for page in (old,new):
            await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__JEV_REPLAY_FRAME__=true;')
            # Both share the exact canonical seed module. Only the old engine is pinned.
            html=(ROOT/'web/playground/mario.html').read_text()
            if 'src="./mario-core.js' not in html:
                html=html.replace('<script src="./mario.js', '<script src="./mario-core.js"></script><script src="./mario.js')
            async def serve_html(route):
                await route.fulfill(body=html,content_type='text/html')
            await page.route('**/mario.html',serve_html)
            await page.goto(self.url+'/playground/mario.html',wait_until='domcontentloaded')
            await page.wait_for_function('!!window.JevMario?.snapshot')
        return old,new
    @unittest.skipUnless(ORIGINAL.is_file(), 'Set JEV_MARIO_ORIGINAL_SCRIPT for historical browser parity')
    async def test_exact_original_public_snapshots_for_32_seeded_maps_and_all_intents(self):
        old,new=await self.pages()
        comparisons=0
        actions=['right','left','jump','jump_right','jump_left','cross_right','wait']
        for seed in range(32):
            options={'generator_revision':'world-seed-v1'} if seed in (0,7) else {}
            init='''([seed,options])=>{JevMario.reset(seed,options);JevMario.activate(true);return JevMario.prepare({clock:'realtime'});}'''
            a=await old.evaluate(init,[seed,options]);b=await new.evaluate(init,[seed,options])
            self.assertEqual(a,b,('reset',seed));comparisons+=1
            for index,action in enumerate(actions):
                target=a['frame']+18+index
                a=await old.evaluate('t=>{__originalAdvanceTo(t);return JevMario.snapshot();}',target)
                b=await new.evaluate('t=>{JevMario.advanceTo(t);return JevMario.snapshot();}',target)
                self.assertEqual(a,b,('wait',seed,action));comparisons+=1
                # Do not await act until the deterministic host advances its frames.
                for page in (old,new):
                    await page.evaluate('a=>{JevMario.prepare({clock:"realtime"});window.__pending=JevMario.act(a);}',action)
                target=a['frame']+180
                a=await old.evaluate('t=>{__originalAdvanceTo(t);return JevMario.snapshot();}',target)
                b=await new.evaluate('t=>{JevMario.advanceTo(t);return JevMario.snapshot();}',target)
                self.assertEqual(a,b,('intent',seed,action));comparisons+=1
                self.assertEqual(await old.evaluate('()=>window.__pending'),await new.evaluate('()=>window.__pending'))
                if a['outcome']: break
        self.assertGreater(comparisons,300)
        (EVIDENCE/'browser-core-parity.json').write_text(json.dumps({'passed':True,'seeds':32,'exact_full_snapshot_comparisons':comparisons,'all_candidate_facts_compared':True,'policy_calls':0},indent=2)+'\n')

    @unittest.skipUnless(ORIGINAL.is_file(), 'Set JEV_MARIO_ORIGINAL_SCRIPT for historical browser parity')
    async def test_node_module_and_visible_history_match_original_chromium(self):
        old,new=await self.pages()
        cases=[]
        for seed in (0,1,2,3,42,4294967295):
            for page in (old,new):
                await page.evaluate('seed=>{JevMario.reset(seed);JevMario.activate(true);JevMario.prepare({clock:"realtime"});}',seed)
            for target in (0,30,90,150):
                original=await old.evaluate('t=>{__originalAdvanceTo(t);return JevMario.snapshot();}',target)
                current=await new.evaluate('t=>{JevMario.advanceTo(t);return JevMario.snapshot();}',target)
                self.assertEqual(original,current)
                cases.append({'seed':seed,'target':target,'snapshot':original})
        code='''const fs=require('fs'),assert=require('node:assert/strict');
const core=require(process.argv[1]),seedModule=require(process.argv[2]),arrival=require(process.argv[3]);
const cases=JSON.parse(fs.readFileSync(0,'utf8'));let engine,last;
for(const c of cases){if(last!==c.seed){engine=core.create({seedModule,seed:c.seed,viewportWidth:880,now:()=>0});arrival.install(engine,'mario_platformer');engine.activate(true);engine.prepare({clock:'realtime'});last=c.seed;}engine.advanceTo(c.target);assert.deepEqual(JSON.parse(JSON.stringify(engine.snapshot())),c.snapshot);}
console.log(JSON.stringify({passed:true,node_original_chromium_snapshots:cases.length}));'''
        # Replay pages retain the source canvas width (880), matching Node exactly.
        result=subprocess.run(['node','-e',code,str(ROOT/'web/playground/mario-core.js'),str(ROOT/'web/playground/world-seed.js'),str(ROOT/'web/playground/world-arrival.js')],input=json.dumps(cases),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        (EVIDENCE/'node-browser-parity.json').write_text(json.dumps(report,indent=2)+'\n')

    async def test_node_realtime_wait_action_completion_and_step_clock(self):
        code=r"""const assert=require('node:assert/strict');
const factory=require(process.argv[1]),seedModule=require(process.argv[2]);
const engine=factory.create({seedModule,seed:0,viewportWidth:880,now:()=>performance.now()});
assert.equal(typeof document,'undefined');assert.equal(typeof window,'undefined');
assert.equal(engine.fixture,undefined);assert.equal(engine.probe,undefined);
engine.activate(true);engine.prepare({clock:'realtime'});
const start=engine.snapshot().frame;
const timer=setInterval(()=>engine.tick(performance.now()),4);
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{try{
 await delay(700);const waiting=engine.snapshot();assert.ok(waiting.frame>=start+30);
 assert.equal(waiting.timing.awaiting_model,true);assert.equal(waiting.timing.inference_world_paused,false);
 const completed=await engine.act('right');assert.equal(completed.last_actions.at(-1),'right');
 assert.equal(completed.action_execution.remaining_frames,0);
 assert.equal(completed.action_execution.recent_effects.at(-1).frames,12);
 assert.equal(completed.action_execution.recent_effects.at(-1).execution_class,'B');
 engine.prepare({clock:'step'});const paused=engine.snapshot().frame;await delay(120);
 assert.equal(engine.snapshot().frame,paused);
 const landed=await engine.act('jump');assert.equal(landed.action_execution.remaining_frames,0);
 assert.ok(landed.frame>paused);await delay(80);assert.equal(engine.snapshot().frame,landed.frame);
 const before=JSON.stringify(engine.snapshot());engine.terminal();engine.terminal();assert.equal(JSON.stringify(engine.snapshot()),before);
 console.log(JSON.stringify({passed:true,world_frames_during_700ms_wait:waiting.frame-start,real_action_frames:12,step_clock_paused:true,pure_terminal:true,dom_used:false}));
}finally{clearInterval(timer);}})().catch(e=>{console.error(e);process.exitCode=1;});"""
        result=await asyncio.to_thread(subprocess.run,['node','-e',code,str(ROOT/'web/playground/mario-core.js'),str(ROOT/'web/playground/world-seed.js')],text=True,capture_output=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        (EVIDENCE/'node-real-clock.json').write_text(json.dumps(json.loads(result.stdout),indent=2)+'\n')

if __name__=='__main__': unittest.main()
