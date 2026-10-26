'use strict';
// Pure CPU checks of the actual shared browser/RL cores. No policy/API/GPU.
const assert=require('node:assert/strict');
const mario=require('../web/playground/mario-core.js');
const terra=require('../web/playground/terraria-core.js');
const seedModule=require('../web/playground/world-seed.js');
const results=[];
function check(name,fn){fn();results.push({name,passed:true});}
function floor(){return Array.from({length:14},(_,y)=>Array(60).fill(y>=11?1:0));}
function fixture({gap=false,enemy=false,viewportWidth=880,tiles=null}={}){
 const hooks={},g=mario.create({seedModule,seed:0,now:()=>0,testHooks:hooks,viewportWidth});
 const map=tiles||floor();if(gap)for(let y=11;y<14;y++)for(let x=5;x<7;x++)map[y][x]=0;
 hooks.fixture({tiles:map,player:{x:128,y:322,vy:0,on_ground:true},enemies:enemy?[{x:420,y:328,w:24,h:24,vx:-.65,min:0,max:1000,alive:true}]:[],plants:[],coins:[]});
 g.activate(true);g.prepare({clock:'realtime'});return {g,hooks};
}
async function run(g,action,frames=180){const pending=g.act(action);g.advanceTo(g.snapshot(false).frame+frames);return await pending;}
function freeze(value){if(value&&typeof value==='object'){Object.freeze(value);Object.values(value).forEach(freeze);}return value;}
(async()=>{
 const t=terra.create({seed:17,now:()=>0});t.activate(true);t.prepare({clock:'realtime'});
 const before=freeze(t.snapshot()),encoded=JSON.stringify(before),pending=t.act('explore_right');t.advanceTo(260);await pending;
 check('terra_old_nested_snapshot_remains_immutable_across_action',()=>assert.equal(JSON.stringify(before),encoded));
 check('terra_external_snapshot_mutation_cannot_modify_core',()=>{const original=JSON.stringify(t.snapshot()),s=t.snapshot();s.control.recent_effects.push({forged:true});s.map.tiles[0][0]=999;assert.equal(JSON.stringify(t.snapshot()),original);});
 const {g}=fixture({gap:true});const m=freeze(g.snapshot()),m0=JSON.stringify(m);
 let moving=g.act('jump_right');g.advanceTo(20);
 check('no_crossing_reward_while_airborne',()=>assert.equal(g.snapshot().progress_events.length,0));
 g.advanceTo(40);const landed=await moving;
 check('visible_gap_actual_landing_emits_one_event',()=>{assert.equal(landed.progress_events.length,1);assert.equal(landed.progress_events[0].id,'gap:5:7');assert.equal(landed.progress_events[0].kind,'safe_gap_crossing');assert.equal(landed.progress_events[0].landing_on_ground,true);assert.equal(landed.progress_events[0].frame,40);});
 check('mario_capture_is_immutable_across_action',()=>assert.equal(JSON.stringify(m),m0));
 await run(g,'jump_left',40);await run(g,'jump_right',40);
 check('recrossing_same_gap_never_reissues_event',()=>assert.equal(g.snapshot().progress_events.length,1));
 check('mario_external_snapshot_mutation_cannot_modify_core',()=>{const original=JSON.stringify(g.snapshot()),s=g.snapshot();s.progress_events[0].x=-999;s.action_execution.recent_effects.length=0;assert.equal(JSON.stringify(g.snapshot()),original);});
 const standing=fixture().g;await run(standing,'jump',40);
 check('in_place_jump_has_no_crossing_reward',()=>assert.equal(standing.snapshot().progress_events.length,0));
 const hidden=fixture({gap:true,viewportWidth:160}).g;await run(hidden,'jump_right',40);
 check('unobserved_far_gap_edge_is_not_rewarded',()=>assert.equal(hidden.snapshot().progress_events.length,0));
 const deathMap=floor();for(let y=11;y<14;y++)for(let x=5;x<18;x++)deathMap[y][x]=0;
 const falling=fixture({tiles:deathMap}).g;await run(falling,'jump_right',180);
 check('pit_death_without_landing_never_emits_crossing',()=>{assert.equal(falling.snapshot().outcome,'loss');assert.equal(falling.snapshot().progress_events.length,0);});
 const pipeMap=floor();for(let y=9;y<11;y++)for(let x=5;x<7;x++)pipeMap[y][x]=3;
 const pipe=fixture({tiles:pipeMap}).g;await run(pipe,'jump_right',40);await run(pipe,'jump_right',70);
 check('visible_pipe_crossing_can_span_two_selected_jumps',()=>{assert(pipe.snapshot().progress_events.some(e=>e.id==='pipe:5:7'));});
 const baseline=fixture({enemy:true}).g;await run(baseline,'cross_right',40);baseline.prepare({clock:'realtime'});baseline.advanceTo(510);
 const guarded=fixture({enemy:true}).g;const start=await run(guarded,'cross_right_guard',40);guarded.prepare({clock:'realtime'});guarded.advanceTo(510);const safe=guarded.snapshot();
 check('only_selected_guard_covers_visible_enemy_during_real_wait',()=>{assert.equal(baseline.snapshot().outcome,'loss');assert.equal(safe.outcome,null);assert.equal(safe.player.x,start.player.x);assert.equal(safe.action_execution.landing_guard.defensive_jumps,1);assert.equal(safe.enemies_stomped,1);assert.equal(safe.decisions,1);assert.equal(safe.action_execution.rule_takeover_count,0);assert.equal(safe.action_execution.landing_guard.origin,'B');assert.equal(safe.timing.inference_world_paused,false);assert.equal(safe.timing.awaiting_model,true);assert.equal(safe.frame,510);});
 guarded.advanceTo(530);
 check('guard_deadline_is_bounded_and_does_not_renew',()=>{const s=guarded.snapshot();assert.equal(s.action_execution.landing_guard.status,'expired');assert.equal(s.action_execution.landing_guard.executed_frames,480);assert.equal(s.action_execution.selected_intent,null);});
 const cancelled=fixture({enemy:true}).g;await run(cancelled,'cross_right_guard',40);await run(cancelled,'wait',12);cancelled.advanceTo(510);
 check('new_model_intent_cancels_prior_defense',()=>{assert.equal(cancelled.snapshot().action_execution.landing_guard,null);assert.equal(cancelled.snapshot().outcome,'loss');});
 const a=fixture({gap:true,enemy:true}).g,b=fixture({gap:true,enemy:true}).g;
 for(const item of [a,b]){await run(item,'cross_right_guard',40);item.prepare({clock:'realtime'});item.advanceTo(330);}
 check('guard_events_and_candidates_replay_exactly',()=>assert.deepEqual(a.snapshot(),b.snapshot()));
 check('candidate_delays_and_explicit_defense_authority_are_public',()=>{const s=a.snapshot();assert.deepEqual(s.candidate_effects.cross_right_guard.latency_scenarios.map(v=>v.assumed_wait_seconds),[4,8]);assert.equal(s.candidate_effects.cross_right_guard.explicit_landing_guard.only_if_selected,true);assert.equal(s.candidate_effects.cross_right_guard.explicit_landing_guard.horizontal_motion,false);});
 console.log(JSON.stringify({passed:true,checks:results.length,results,controlled_fixture:{baseline_failure_frame:baseline.snapshot().frame,guarded_survival_frame:safe.frame,guarded_defensive_jumps:safe.action_execution.landing_guard.defensive_jumps}}));
})().catch(e=>{console.error(e);process.exitCode=1;});
