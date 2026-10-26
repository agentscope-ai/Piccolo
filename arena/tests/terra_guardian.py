"""Actual Chromium guardian-gate, combat attribution and absorbing-terminal tests.

Small combat fixtures validate causal mechanics, not teacher/student success or
full-difficulty capability. Production guardian health/damage is not weakened.
No model, provider, active backend or GPU is used.
"""
from __future__ import annotations
import argparse,asyncio,functools,json,threading,sys
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright
from terra_core_test_support import engine_source, test_source, install_fixture

PACKAGE=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

async def run(package):
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(package/'web')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            try:
                page=await browser.new_page()
                await install_fixture(page, package);await page.add_init_script('window.__JEV_TEST_MODE__=true;')
                await page.goto(f'http://127.0.0.1:{server.server_port}/playground/terraria.html')
                return await page.evaluate('''async()=>{
                  const api=JevTerramai,snap=()=>structuredClone(api.snapshot()),rows={},floor=Array.from({length:28},(_,i)=>[i,15,11]);
                  const enemy=(extra={})=>Object.assign({kind:'zombie',boss:true,gateGuardian:true,x:174,y:220,w:14,h:20,
                    lv:10,vx:0,vy:0,ground:true,hp:9,maxhp:9,hop:40,face:-1,t:0},extra);
                  const fixture=(extra={})=>Object.assign({x:10,y:13.75,dirt:5,tiles:floor,goal:[14,14],exploredGoal:true,spawn:[5,13.75]},extra);
                  function begin(f,managed=true){api.fixture(f);api.activate(true);if(managed)api.prepare({clock:'step'});return snap()}
                  rows.native_initial={snapshot:api.reset(1792178101),condition:api.condition(),
                    guardians:api.inspectWorld().enemies.filter(e=>e.gateGuardian).map(e=>({kind:e.kind,level:e.lv,hp:e.hp,maxhp:e.maxhp,w:e.w,h:e.h})),
                    bosses:api.inspectWorld().enemies.filter(e=>e.boss).length};
                  begin(fixture({goal:[10,14],enemies:[enemy({x:12*16,hp:1000,maxhp:1000})]}));
                  rows.locked={before:snap(),after:await api.act('reach_known_goal')};
                  begin(fixture({enemies:[enemy({boss:false,gateGuardian:false,lv:1})]}));api.probe('attack_right',1);rows.ordinary=snap();
                  begin(fixture({tiles:floor.concat([[11,14,4]])}));api.probe('mine_right',20);rows.mined=snap();
                  begin(fixture({enemies:[enemy({gateGuardian:false})]}));api.probe('attack_right',1);rows.other_boss=snap();
                  begin(fixture({enemies:[enemy({y:100000,hp:1000,maxhp:1000})]}));api.probe('wait',1);rows.pure_fall=snap();
                  begin(fixture({tiles:floor.concat([[11,14,14]]),enemies:[enemy({hp:.1,maxhp:.1})]}));api.probe('wait',1);rows.pure_lava=snap();
                  begin(fixture({enemies:[enemy()]}));api.probe('attack_right',1);rows.direct={defeated:snap()};
                  rows.direct.won=await api.act('reach_known_goal');
                  const terminalBefore=snap(),generationBefore=api.condition().generation,waitStart=performance.now();
                  api.prepare({clock:'realtime'});await new Promise(r=>setTimeout(r,5200));api.probe('wait',400);
                  await api.act('explore_right');
                  rows.absorbing={before:terminalBefore,after:snap(),generationBefore,generationAfter:api.condition().generation,
                    wallSeconds:(performance.now()-waitStart)/1000};
                  rows.explicit_reset={before:snap(),beforeGeneration:api.condition().generation,after:api.reset(1792178102),afterGeneration:api.condition().generation};
                  begin(fixture({goal:[11,14],enemies:[enemy()]}));rows.atomic_terminal=await api.act('attack_right');
                  begin(fixture({tiles:floor.concat([[11,14,14]]),enemies:[enemy({hp:9.3,maxhp:9.3})]}));
                  api.probe('attack_right',1);rows.assisted=snap();
                  begin(fixture({hp:.05,tiles:floor.concat([[10,14,15]])}));api.probe('wait',1);
                  rows.death={dead:snap()};api.probe('wait',112);rows.death.respawned=snap();
                  // Gate and poison must occupy distinct tiles; fixture() writes
                  // the GOAL tile after terrain. Both are within the gate radius.
                  begin(fixture({hp:.05,goal:[11,14],guardianDefeatedByPlayer:true,tiles:floor.concat([[10,14,15]])}));
                  api.probe('wait',1);rows.dead_at_gate=snap();
                  begin(fixture({goal:[10,14],guardianDefeatedByPlayer:true}),false);
                  const humanGeneration=api.condition().generation;api.probe('wait',1);rows.human={won:snap(),generationBefore:humanGeneration};
                  api.probe('wait',300);rows.human.after=snap();rows.human.generationAfter=api.condition().generation;
                  begin(fixture({x:10,y:11.75}));const waitingBefore=structuredClone(api.prepare({clock:'realtime'}));
                  await new Promise(r=>setTimeout(r,650));rows.waiting={before:waitingBefore,after:snap()};api.activate(false);
                  rows.render_error=window.jevRenderError||null;return rows;
                }''')
            finally:await browser.close()
    finally:
        await asyncio.to_thread(server.shutdown);server.server_close();thread.join(timeout=2)

async def main(args):
    sys.path.insert(0,str(args.package));import blink_arena
    from jev_terraria_contract import as_record
    r=await run(args.package);checks={}
    def verify(name,condition):checks[name]=bool(condition)
    n=r['native_initial'];verify('exactly_one_designated_guardian',len(n['guardians'])==1)
    verify('guardian_native_lv10_health_unchanged',n['guardians'][0]['level']==10 and n['guardians'][0]['hp']==n['guardians'][0]['maxhp'] and n['guardians'][0]['hp']>1000)
    verify('initial_no_hidden_guardian_location',not n['snapshot']['objective']['visible_guardian_ids'] and 'guardian_position' not in n['snapshot']['objective'])
    locked=r['locked']['after'];verify('live_guardian_gate_locked',locked['wins']==0 and not locked['objective']['gate_unlocked'])
    verify('guardian_identity_only_in_visible_enemies',locked['objective']['visible_guardian_ids']==[e['id'] for e in locked['enemies'] if e['gate_guardian']])
    verify('locked_door_honest_feedback',locked['control']['status']=='blocked' and locked['control']['events']==['goal_locked_guardian'] and locked['control']['failure_reason']=='gate_requires_player_defeated_guardian')
    for name in ('ordinary','other_boss'):
        s=r[name];verify(name+'_actual_player_hit',s['progression']['player_attack_hits']==1 and s['progression']['player_attack_damage']==9)
        verify(name+'_kill_does_not_unlock',s['progression']['player_kills']==1 and s['progression']['player_direct_kills']==1 and not s['objective']['gate_unlocked'] and s['wins']==0)
    verify('ordinary_progression_is_not_boss',r['ordinary']['progression']['ordinary_player_kills']==1 and r['other_boss']['progression']['ordinary_player_kills']==0)
    mined=r['mined'];verify('actual_mining_progression',mined['stats']['ore']==mined['progression']['ore_mined']==1 and mined['progression']['ore_points_earned']==1)
    verify('public_equipment_integer_levels',all(isinstance(mined['equipment'][k],int) for k in ('pick','sword','armor')))
    for name in ('pure_fall','pure_lava'):
        s=r[name];verify(name+'_no_false_kill_xp_or_gate',s['stats']['kill']==0 and s['progression']['player_kills']==0 and s['progression']['combat_points_earned']==0 and not s['objective']['gate_unlocked'] and s['equipment']['pts']==0 and s['equipment']['pick']==1 and s['equipment']['sword']==1)
    verify('unseen_environment_death_no_new_telemetry',not r['pure_fall']['recent_combat_events'])
    verify('seen_environment_death_marked_uncredited',r['pure_lava']['recent_combat_events'][-1]['attribution']=='environment_only' and not r['pure_lava']['recent_combat_events'][-1]['credited_to_player'])
    d=r['direct']['defeated'];verify('real_attack_defeats_guardian',d['progression']['player_attack_damage']==9 and d['progression']['guardian_player_kills']==1 and d['objective']['guardian_defeated_by_player'] and d['objective']['guardian_defeated_via']=='player_attack')
    verify('boss_defeat_does_not_itself_count_win',d['wins']==0)
    w=r['direct']['won'];verify('gate_after_guardian_native_win',w['wins']==1 and w['episode_terminal'] and w['control']['events']==['goal_door_entered'])
    atomic=r['atomic_terminal'];verify('atomic_terminal_stops_before_deadline',atomic['wins']==1 and atomic['episode_terminal'] and atomic['control']['events']==['goal_door_entered'] and atomic['control']['recent_effects'][-1]['frames']<36)
    a=r['assisted'];verify('real_hit_environment_assist_separate',a['progression']['player_attack_hits']==1 and a['progression']['player_attack_damage']==9 and a['progression']['player_kills']==1 and a['progression']['player_direct_kills']==0 and a['progression']['environment_assisted_kills']==1)
    verify('participating_assist_unlocks_guardian',a['objective']['gate_unlocked'] and a['objective']['guardian_defeated_via']=='player_assisted_environment' and a['recent_combat_events'][-1]['lethal_source']=='environment_lava')
    dead,respawn=r['death']['dead'],r['death']['respawned'];verify('death_count_real',dead['deaths']==dead['progression']['death_count']==1)
    verify('respawn_count_cumulative',respawn['deaths']==respawn['progression']['death_count']==1 and respawn['progression']['respawn_count']==1 and not respawn['player']['respawning'])
    verify('respawn_does_not_unlock',not respawn['objective']['gate_unlocked'] and respawn['progression']['guardian_player_kills']==0 and respawn['wins']==0)
    verify('dead_player_cannot_enter_gate',r['dead_at_gate']['deaths']==1 and r['dead_at_gate']['wins']==0)
    stable=r['absorbing'];verify('completed_model_wait_exceeds280frames',stable['wallSeconds']>280/60)
    verify('terminal_generation_stable',stable['generationBefore']==stable['generationAfter'])
    verify('terminal_player_progression_gear_frame_stable',all(stable['before'][k]==stable['after'][k] for k in ('player','equipment','progression','stats','wins','deaths','frame','objective','decisions')))
    z=r['explicit_reset'];verify('explicit_reset_reopens_episode',z['afterGeneration']>z['beforeGeneration'] and not z['after']['episode_terminal'] and z['after']['wins']==0 and not z['after']['objective']['gate_unlocked'] and z['after']['progression']['player_kills']==0)
    human=r['human'];verify('manual_continuous_world_preserved',human['won']['wins']==1 and not human['won']['episode_terminal'] and human['generationAfter']>human['generationBefore'])
    waiting=r['waiting'];verify('unfinished_wait_continues_world',waiting['after']['frame']>waiting['before']['frame']+20 and waiting['after']['player']['y']!=waiting['before']['player']['y'])
    verify('unfinished_wait_no_model_action',waiting['after']['decisions']==waiting['before']['decisions'])
    observations=[r['locked']['after'],r['ordinary'],r['other_boss'],r['pure_fall'],r['pure_lava'],d,w,a,dead,respawn,waiting['after']]
    verify('no_rule_takeover',all(s['execution_audit']['rule_takeover_count']==0 for s in observations))
    records=[as_record(s) for s in observations]
    verify('single_decision_choice_preserved',all(list(s['questions'])==['decision'] and s['questions']['decision']['type']=='choice' for s in records))
    verify('prompt_requires_guardian_not_bypass',all('Boss 不是胜利前置' not in s['questions']['decision']['instructions'] and '守门' in s['questions']['decision']['instructions'] for s in records))
    verify('candidate_declares_gate_lock','当前门已解锁=False' in as_record(r['locked']['before'])['questions']['decision']['criteria']['reach_known_goal'])
    verify('render_ok',not r['render_error'])
    result=dict(scope='real Chromium causal fixtures, not complete-difficulty model episodes',package=str(args.package),model_calls=0,GPU_calls=0,
                checks=checks,passed=all(checks.values()),rows=r)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failures=[k for k,v in checks.items() if not v]),ensure_ascii=False),flush=True)
    return int(not result['passed'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=PACKAGE);p.add_argument('--out',type=Path,required=True)
    raise SystemExit(asyncio.run(main(p.parse_args())))
