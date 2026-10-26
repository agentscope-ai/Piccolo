"""Real browser regression for the shared visible arrival contract (zero API calls)."""
from __future__ import annotations

import asyncio
import copy
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
import sys

from playwright.async_api import async_playwright
PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / 'blink_arena/engines'), str(PACKAGE)]
import jev_world_realtime_rl as world


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ArrivalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            Handler, directory=str(PACKAGE / 'web')))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True, args=['--no-sandbox'])

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    async def page(self, game='mario'):
        page = await self.browser.new_page()
        await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__JEV_FAST_STEP__=true;')
        await page.goto(self.url + '/playground/' + game + '.html')
        return page

    async def test_enemy_reversal_rejects_without_action_and_feedback_is_public(self):
        page = await self.page()
        result = await page.evaluate('''async()=>{
          const api=JevMario,tiles=Array.from({length:14},(_,y)=>Array(96).fill(y>=11?1:0));
          api.fixture({tiles,player:{x:64,y:322,on_ground:true,vy:0},coins:[],plants:[],
            enemies:[{x:180,y:328,w:26,h:24,vx:.65,min:100,max:185,alive:true}]});
          api.activate(true);const before=api.prepare({clock:'realtime'});
          await new Promise(r=>setTimeout(r,900));const arrival=api.snapshot();
          const verdict=api.checkActionArrival('right',before,arrival);
          const feedback=api.rejectActionArrival('right',before,arrival,verdict);
          const next=api.prepare({clock:'realtime'});api.activate(false);
          return {before,arrival,verdict,feedback,next};
        }''')
        self.assertGreater(result['arrival']['frame'], result['before']['frame'] + 30)
        self.assertFalse(result['verdict']['valid'])
        self.assertIn(result['verdict']['reason'], ('enemy_direction_changed', 'visible_danger_changed'))
        self.assertEqual(result['arrival']['decisions'], result['feedback']['decisions'])
        self.assertEqual(result['arrival']['player'], result['feedback']['player'])
        self.assertEqual(result['feedback']['decision_arrival'], result['next']['decision_arrival'])
        feedback = result['next']['decision_arrival']['recent_rejections'][-1]
        self.assertIsNone(feedback['automatic_action'])
        self.assertEqual(feedback['rule_takeover_actions'], 0)
        record = world.get_engine('mario_platformer').observe(result['next'])
        self.assertEqual(record['state']['observation']['decision_arrival'], result['next']['decision_arrival'])

    async def test_real_landing_invalidates_old_jump_and_legacy_clock_remains(self):
        page = await self.page()
        result = await page.evaluate('''async()=>{
          const api=JevMario,delay=ms=>new Promise(r=>setTimeout(r,ms));
          const tiles=Array.from({length:14},(_,y)=>Array(96).fill(y>=11?1:0));
          api.fixture({tiles,player:{x:64,y:240,on_ground:false,vy:0},coins:[],plants:[],enemies:[]});
          api.activate(true);const before=api.prepare({clock:'realtime'});await delay(600);
          const arrival=api.snapshot(),verdict=api.checkActionArrival('jump_right',before,arrival);
          api.rejectActionArrival('jump_right',before,arrival,verdict);
          const fresh=api.prepare({clock:'realtime'}),current=api.snapshot();
          const accepted=api.checkActionArrival('jump_right',fresh,current);
          const frozen=api.prepare();await delay(200);const stayed=api.snapshot();
          api.release();await delay(200);const running=api.snapshot();api.activate(false);
          return {before,arrival,verdict,accepted,frozen,stayed,running};
        }''')
        self.assertEqual(result['verdict']['reason'], 'jump_state_changed')
        self.assertTrue(result['accepted']['valid'])
        self.assertTrue(result['arrival']['player']['on_ground'])
        self.assertFalse(result['arrival']['timing']['inference_world_paused'])
        self.assertEqual(result['frozen']['frame'], result['stayed']['frame'])
        self.assertGreater(result['running']['frame'], result['stayed']['frame'])

    async def test_public_contract_rejects_shield_subgoal_and_respawn_no_hidden_state(self):
        page = await self.page()
        result = await page.evaluate('''()=>{
          const base={frame:1,player:{x:0,y:0,shield:1,on_ground:true},timing:{clock_contract:'realtime-v1'},
            action_execution:{current_goal:'flag',selected_intent:null},enemies:[],candidate_effects:{right:{}}};
          const check=(patch,action='right',kind='mario_platformer')=>JevWorldArrival.check(kind,action,base,{...structuredClone(base),...patch});
          return {shield:check({player:{...base.player,shield:0}}),
            subgoal:check({action_execution:{current_goal:'flag',selected_intent:'jump'}}),
            death:check({deaths:1},'recover','terraria_survival'),
            terminal:check({outcome:'loss'}),same:check({})};
        }''')
        self.assertEqual(result['shield']['reason'], 'shield_changed')
        self.assertEqual(result['subgoal']['reason'], 'subgoal_changed')
        self.assertEqual(result['death']['reason'], 'death_or_respawn')
        self.assertFalse(result['terminal']['requires_new_observation'])
        self.assertTrue(result['same']['valid'])

    async def test_rl_rejected_action_has_no_pg_trace_and_exact_replay_recomputes_guard(self):
        calls = []
        async def policy(record, episode_id, ordinal):
            calls.append(copy.deepcopy(record))
            await asyncio.sleep(1.0 if ordinal == 0 else .05)
            return 'jump_right', {'origin':'fixture', 'on_policy':False}
        # Real physics fixture: begin airborne so a delayed jump necessarily
        # arrives after landing. Apply the same fixture to the independent replay.
        async def fixture_page(**kwargs):
            page = await self.browser.new_page(**kwargs)
            await page.add_init_script('''
              window.__JEV_TEST_MODE__=true;
              document.addEventListener('DOMContentLoaded',()=>{
                const reset=JevMario.reset.bind(JevMario);
                JevMario.reset=seed=>{
                  reset(seed);
                  const tiles=Array.from({length:14},(_,y)=>Array(96).fill(y>=11?1:0));
                  return JevMario.fixture({tiles,player:{x:64,y:240,on_ground:false,vy:0},coins:[],plants:[],enemies:[]});
                };
              });
            ''')
            return page
        sampler = SimpleNamespace(browser=SimpleNamespace(new_page=fixture_page), args=SimpleNamespace(frontend=self.url), policy_action=policy)
        job = {'kind':'mario_platformer','seed':1194710010,'episode_id':'arrival-clock-fixture'}
        previous = world.LIMITS.get(job['kind'])
        world.LIMITS[job['kind']] = 3
        try:
            initial, final, trace, outcome, extra = await world.play(sampler, job)
        finally:
            if previous is None:
                world.LIMITS.pop(job['kind'])
            else:
                world.LIMITS[job['kind']] = previous
        self.assertGreater(extra['discarded_replies'], 0)
        rejected = [e for e in extra['replay_events'] if not e['action_applied']]
        self.assertEqual(len(trace), len(extra['replay_events']) - len(rejected))
        self.assertTrue(all(e['ordinal'] not in [t['ordinal'] for t in trace] for e in rejected))
        self.assertEqual(calls, [e['record'] for e in extra['replay_events']])
        self.assertGreater(extra['replay_events'][0]['arrival_state']['frame'], initial['frame'])
        await world.verify(sampler, job, initial, final, extra, trace)
        changed = copy.deepcopy(extra)
        changed['replay_events'][0]['arrival_check']['reason'] = 'falsified'
        with self.assertRaisesRegex(ValueError, 'arrival_check_did_not_replay'):
            await world.verify(sampler, job, initial, final, changed, trace)

    async def test_terra_world_runs_and_new_contract_exactly_replays(self):
        async def policy(record, episode_id, ordinal):
            await asyncio.sleep(.15)
            return 'explore_right', {'origin':'fixture', 'on_policy':False}
        sampler = SimpleNamespace(browser=self.browser, args=SimpleNamespace(frontend=self.url), policy_action=policy)
        job = {'kind':'terraria_survival','seed':1194110010,'episode_id':'arrival-terra-fixture'}
        previous = world.LIMITS.get(job['kind'])
        world.LIMITS[job['kind']] = 2
        try:
            initial, final, trace, outcome, extra = await world.play(sampler, job)
        finally:
            if previous is None:
                world.LIMITS.pop(job['kind'])
            else:
                world.LIMITS[job['kind']] = previous
        self.assertEqual(len(trace), 2)
        self.assertTrue(all(e['arrival_state']['frame'] > e['before_state']['frame'] for e in extra['replay_events']))
        self.assertEqual(final['execution_audit']['rule_takeover_count'], 0)
        await world.verify(sampler, job, initial, final, extra, trace)

    async def test_terra_guardian_terminal_and_credit_exactly_replay(self):
        # One real player attack defeats this reduced-health causal fixture.
        # This is a test controller, never a model/capability score or PG source.
        async def fixture_page(**kwargs):
            page = await self.browser.new_page(**kwargs)
            await page.add_init_script('''
              window.__JEV_TEST_MODE__=true;
              document.addEventListener('DOMContentLoaded',()=>{
                const reset=JevTerramai.reset.bind(JevTerramai);
                JevTerramai.reset=seed=>{
                  reset(seed);
                  return JevTerramai.fixture({x:10,y:13.75,dirt:5,goal:[11,14],exploredGoal:true,
                    tiles:Array.from({length:28},(_,x)=>[x,15,11]),enemies:[{
                      kind:'zombie',boss:true,gateGuardian:true,x:174,y:220,w:14,h:20,
                      lv:10,vx:0,vy:0,ground:true,hp:9,maxhp:9,hop:40,face:-1,t:0}]});
                };
              });
            ''')
            return page
        async def policy(record, episode_id, ordinal):
            await asyncio.sleep(.05)
            return 'fight_nearest', {'origin':'fixture', 'on_policy':False}
        sampler=SimpleNamespace(browser=SimpleNamespace(new_page=fixture_page),
            args=SimpleNamespace(frontend=self.url),policy_action=policy)
        job={'kind':'terraria_survival','seed':1792178103,'episode_id':'guardian-terminal-fixture'}
        previous=world.LIMITS.get(job['kind']);world.LIMITS[job['kind']]=3
        try:
            initial,final,trace,outcome,extra=await world.play(sampler,job)
        finally:
            if previous is None:world.LIMITS.pop(job['kind'])
            else:world.LIMITS[job['kind']]=previous
        self.assertEqual(outcome,'win')
        self.assertTrue(final['objective']['guardian_defeated_by_player'])
        self.assertTrue(final['episode_terminal'])
        self.assertEqual(final['progression']['player_direct_kills'],1)
        self.assertEqual(final['execution_audit']['rule_takeover_count'],0)
        self.assertEqual(final['control']['events'],['goal_door_entered'])
        self.assertLess(final['control']['recent_effects'][-1]['frames'],36)
        self.assertTrue(extra['terminal_clock']['terminal_observed'])
        self.assertTrue(all(t['policy']['on_policy'] is False for t in trace))
        await world.verify(sampler,job,initial,final,extra,trace)
        from jev_gameplay_reward_contract import settle_episode
        reward=settle_episode(job['kind'],initial,trace,1.,final_state=final)
        self.assertEqual(reward['terminal_utility'],1.)
        self.assertEqual(reward['reward_audit']['death_cost_total'],0.)
        self.assertAlmostEqual(reward['reward_audit']['closure_error'],0.)
        self.assertGreaterEqual(reward['training_utility'],1.)
        self.assertLessEqual(reward['training_utility'],1.1)
        self.assertEqual(len(reward['process_reward_components']),len(trace))
        print(json.dumps({'guardian_fixture_reward':reward,'exact_replay':True,
                          'on_policy':False,'trace_count':len(trace)},ensure_ascii=False),flush=True)

    async def test_terra_visible_gem_choice_and_reward_exactly_replay(self):
        async def fixture_page(**kwargs):
            page=await self.browser.new_page(**kwargs)
            await page.add_init_script('''
              window.__JEV_TEST_MODE__=true;
              document.addEventListener('DOMContentLoaded',()=>{
                const reset=JevTerramai.reset.bind(JevTerramai);
                JevTerramai.reset=seed=>{reset(seed);return JevTerramai.fixture({x:10,y:13.75,dirt:0,
                  tiles:Array.from({length:25},(_,x)=>[x,15,11]).concat([[11,14,4],[12,14,8],[13,14,8]])});};
              });
            ''')
            return page
        async def policy(record,episode_id,ordinal):
            self.assertIn('collect_visible_gem',record['questions']['decision']['criteria'])
            self.assertEqual(record['state']['navigation']['collection']['collect_visible_gem']['target']['tile'],8)
            await asyncio.sleep(.08)
            return 'collect_visible_gem',{'origin':'fixture','on_policy':False}
        sampler=SimpleNamespace(browser=SimpleNamespace(new_page=fixture_page),args=SimpleNamespace(frontend=self.url),policy_action=policy)
        job={'kind':'terraria_survival','seed':1792218104,'episode_id':'visible-gem-choice-fixture'}
        previous=world.LIMITS.get(job['kind']);world.LIMITS[job['kind']]=2
        try:initial,final,trace,outcome,extra=await world.play(sampler,job)
        finally:
            if previous is None:world.LIMITS.pop(job['kind'])
            else:world.LIMITS[job['kind']]=previous
        self.assertEqual(outcome,'budget_exhausted')
        self.assertEqual(final['equipment']['gems'],2)
        self.assertEqual(final['equipment']['armor'],1)
        self.assertEqual(final['progression']['ore_mined'],0)
        self.assertEqual(final['execution_audit']['rule_takeover_count'],0)
        self.assertEqual(len(trace),2)
        self.assertTrue(all(t['action']=='collect_visible_gem' and not t['policy']['on_policy'] for t in trace))
        await world.verify(sampler,job,initial,final,extra,trace)
        from jev_gameplay_reward_contract import settle_episode
        reward=settle_episode(job['kind'],initial,trace,-1.,final_state=final)
        self.assertEqual(reward['terminal_utility'],-1.)
        self.assertAlmostEqual(reward['reward_audit']['closure_error'],0.)
        self.assertGreater(reward['training_utility'],-1.)
        self.assertLess(reward['training_utility'],0.)
        print(json.dumps({'gem_fixture_exact_replay':True,'applied':len(trace),'on_policy':False,
                          'original_game_budget_unchanged':300,'test_only_fixture_decisions':2,'reward':reward}),flush=True)

    async def test_terra_resource_failure_memory_and_wait_exactly_replay(self):
        async def fixture_page(**kwargs):
            page=await self.browser.new_page(**kwargs)
            await page.add_init_script('''
              window.__JEV_TEST_MODE__=true;
              document.addEventListener('DOMContentLoaded',()=>{
                const reset=JevTerramai.reset.bind(JevTerramai);
                JevTerramai.reset=seed=>{reset(seed);return JevTerramai.fixture({x:10,y:13.75,dirt:0,
                  tiles:Array.from({length:25},(_,x)=>[x,15,11]).concat([[17,14,7],[16,14,11],[18,14,11],[17,13,11]])});};
              });
            ''')
            return page
        async def policy(record,episode_id,ordinal):
            self.assertIn('collect_visible',record['questions']['decision']['criteria'])
            facts=record['state']['navigation']['collection']['collect_visible']
            self.assertEqual(facts['previous_failure_count'],ordinal)
            await asyncio.sleep(.08)
            return 'collect_visible',{'origin':'fixture','on_policy':False}
        sampler=SimpleNamespace(browser=SimpleNamespace(new_page=fixture_page),args=SimpleNamespace(frontend=self.url),policy_action=policy)
        job={'kind':'terraria_survival','seed':1792221104,'episode_id':'resource-failure-memory-fixture'}
        previous=world.LIMITS.get(job['kind']);world.LIMITS[job['kind']]=2
        try:initial,final,trace,outcome,extra=await world.play(sampler,job)
        finally:
            if previous is None:world.LIMITS.pop(job['kind'])
            else:world.LIMITS[job['kind']]=previous
        self.assertEqual(outcome,'budget_exhausted')
        self.assertEqual(len(trace),2)
        self.assertEqual(final['control']['failed_targets'][0]['failures'],2)
        self.assertEqual(final['control']['no_progress_count'],2)
        self.assertTrue(all(t['after_state']['control']['status']=='blocked' for t in trace))
        self.assertTrue(all(t['arrival_state']['frame']>t['before_state']['frame'] for t in trace))
        self.assertTrue(all(t['action_applied'] and not t['policy']['on_policy'] for t in trace))
        self.assertEqual(final['execution_audit']['rule_takeover_count'],0)
        await world.verify(sampler,job,initial,final,extra,trace)
        from jev_gameplay_reward_contract import settle_episode
        reward=settle_episode(job['kind'],initial,trace,-1.,final_state=final)
        self.assertEqual(reward['training_utility'],-1.)
        self.assertAlmostEqual(reward['reward_audit']['closure_error'],0.)

    async def test_terra_native_attack_geometry_and_credit_exactly_replay(self):
        from tests.terra_attack_geometry import PUBLIC_CASE
        source=(PACKAGE/'web/playground/terraria.js').read_text()
        marker='(f.tiles||[]).forEach(function(t){setT(t[0],t[1],t[2])});'
        self.assertEqual(source.count(marker),1)
        injected=source.replace(marker,marker+'if(f.testGear)Object.assign(gear,f.testGear);')
        async def fixture_page(**kwargs):
            page=await self.browser.new_page(**kwargs)
            async def intercept(route):
                await route.fulfill(status=200,content_type='application/javascript',body=injected)
            await page.route('**/terraria.js*',intercept)
            await page.add_init_script('window.__JEV_TEST_MODE__=true;window.__publicCase='+json.dumps(PUBLIC_CASE)+';'+'''
              document.addEventListener('DOMContentLoaded',()=>{
                const reset=JevTerramai.reset.bind(JevTerramai);
                JevTerramai.reset=seed=>{reset(seed);const o=window.__publicCase,tiles=[];
                  o.map.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(v>=0)tiles.push([x+o.map.origin[0],y+o.map.origin[1],v])}));
                  return JevTerramai.fixture({x:o.player.geometry.x,y:o.player.geometry.y,dirt:o.equipment.dirt,testGear:o.equipment,tiles,
                    enemies:o.enemies.map(e=>({kind:e.kind,x:e.x*16,y:e.y*16,w:e.width*16,h:e.height*16,hp:e.hp,maxhp:e.hp,lv:e.level,vx:0,vy:0,t:0,hop:40,ground:true}))});};
              });
            ''')
            return page
        async def policy(record,episode_id,ordinal):
            hit=record['state']['navigation']['combat'][0]['native_attack']
            self.assertTrue(hit['geometry_exact'])
            self.assertEqual(hit['hitting_directions'],[])
            await asyncio.sleep(.08)
            return 'fight_nearest',{'origin':'fixture','on_policy':False}
        sampler=SimpleNamespace(browser=SimpleNamespace(new_page=fixture_page),args=SimpleNamespace(frontend=self.url),policy_action=policy)
        job={'kind':'terraria_survival','seed':1792221204,'episode_id':'native-attack-geometry-fixture'}
        previous=world.LIMITS.get(job['kind']);world.LIMITS[job['kind']]=1
        try:initial,final,trace,outcome,extra=await world.play(sampler,job)
        finally:
            if previous is None:world.LIMITS.pop(job['kind'])
            else:world.LIMITS[job['kind']]=previous
        self.assertEqual(outcome,'budget_exhausted')
        self.assertEqual(len(trace),1)
        self.assertEqual(final['progression']['player_direct_kills'],1)
        self.assertEqual(final['progression']['player_attack_damage'],30)
        self.assertEqual(final['control']['events'],['target_completed'])
        self.assertEqual(final['execution_audit']['rule_takeover_count'],0)
        self.assertFalse(trace[0]['policy']['on_policy'])
        await world.verify(sampler,job,initial,final,extra,trace)
        from jev_gameplay_reward_contract import settle_episode
        reward=settle_episode(job['kind'],initial,trace,-1.,final_state=final)
        self.assertEqual(reward['terminal_utility'],-1.)
        self.assertAlmostEqual(reward['reward_audit']['closure_error'],0.)

    async def test_actual_frontend_reobserves_rejected_reply_immediately(self):
        page = await self.page()
        text = (PACKAGE / 'web/showcases.js').read_text()
        step = text[text.index('async function showcaseStep('):text.index('async function autoplay(')]
        manual = text[text.index('async function modelShowcaseStep('):text.index('function renderTextChrome(')]
        await page.evaluate('''()=>{
          window.showcaseSession=null;window.showcaseBusy=false;window.autoTicket=0;window.playTabVisible=true;
          window.selectedPlay='mario_platformer';window.showcaseKind={kind:'mario_platformer',mode:'world',engine:{limit:4}};
          window.worldOutcome=null;window.terraCalls=0;window.worldDecisionReceipts=[];
          const dom={};window.$=id=>dom[id]||(dom[id]={textContent:'',innerHTML:''});
          window.JevPlayText={ui:x=>x};window.DecisionTiming={record:()=>{}};
          for(const k of ['showcaseControls','clearError','renderWorld','decisionLog','stopAuto'])window[k]=()=>{};
          window.resultHtml=window.showcaseInputs=x=>JSON.stringify(x);window.error=e=>{throw e};
          window.worldReady=async()=>JevMario;window.worldActionName=x=>x;
          window.recordWorldDecision=r=>worldDecisionReceipts.push(r);window.apiCalls=[];
          window.api=async(path,body)=>{
            apiCalls.push(structuredClone(body));await new Promise(r=>setTimeout(r,apiCalls.length===1?900:0));
            return {result:{value:apiCalls.length===1?'right':'wait'},input:body};
          };
          const tiles=Array.from({length:14},(_,y)=>Array(96).fill(y>=11?1:0));
          JevMario.fixture({tiles,player:{x:64,y:322,on_ground:true,vy:0},coins:[],plants:[],
            enemies:[{x:180,y:328,w:26,h:24,vx:.65,min:100,max:185,alive:true}]});
          JevMario.activate(true);
        }''')
        await page.add_script_tag(content=step+'\n'+manual)
        result = await page.evaluate('''async()=>{
          const result=await modelShowcaseStep();JevMario.activate(false);
          return {result,calls:apiCalls,receipts:worldDecisionReceipts,state:JevMario.snapshot()};
        }''')
        self.assertTrue(result['result'])
        self.assertEqual(len(result['calls']), 2)
        self.assertEqual([r['status'] for r in result['receipts']], ['discarded', 'executed'])
        self.assertEqual(result['calls'][1]['state']['decision_arrival']['rejected_count'], 1)
        self.assertEqual(result['state']['decisions'], 1)
        self.assertEqual(result['receipts'][0]['rule_takeover_actions'], 0)


if __name__ == '__main__':
    unittest.main()
