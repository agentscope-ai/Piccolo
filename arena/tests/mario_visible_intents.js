'use strict';
// Offline tests execute the same core used by the frontend and RL worker.
const test=require('node:test');
const assert=require('node:assert/strict');
const core=require('../web/playground/mario-core.js');
const seedModule=require('../web/playground/world-seed.js');
const prefix='cross_visible_right:';
function fixture(kind='gap',extra={}) {
  const hooks={},engine=core.create({seedModule,seed:0,testHooks:hooks,now:()=>0,viewportWidth:880});
  const tiles=Array.from({length:14},(_,y)=>Array(40).fill(y>=11?1:0));
  if(kind==='gap')for(let y=11;y<14;y++)tiles[y][10]=tiles[y][11]=0;
  else for(let y=9;y<11;y++)tiles[y][10]=tiles[y][11]=3;
  hooks.fixture({tiles,enemies:[],coins:[],plants:kind==='flower'?[{pipe_x:10,offset:0}]:[],
    player:{x:128,y:322,vy:0,on_ground:true},...extra});
  engine.activate(true);engine.prepare({clock:'realtime'});return {engine,hooks};
}
const choices=engine=>Object.entries(engine.snapshot().candidate_effects).filter(([action])=>action.startsWith(prefix));
async function execute(engine,action) {
  const promise=engine.act(action);let previous=engine.renderState().p.x,frames=0;
  while(engine.renderState().remaining>0&&frames++<302){
    engine.advanceTo(engine.renderState().frame+1);
    assert.ok(Math.abs(engine.renderState().p.x-previous)<=3.20001,'horizontal motion must use real physics');
    previous=engine.renderState().p.x;
  }
  assert.equal(engine.renderState().remaining,0,'intent must terminate within its deadline');
  const observation=await promise;
  return {observation,effect:observation.action_execution.recent_effects.at(-1)};
}
test('one Choice approaches and crosses the selected visible gap with one jump',async()=>{
  const {engine}=fixture(),options=choices(engine);
  assert.ok(options.length>0&&options.length<=3);
  const {observation,effect}=await execute(engine,options[0][0]);
  assert.equal(effect.event,'landed');assert.equal(effect.jumps_started,1);assert.ok(effect.approach_frames>0);
  assert.equal(observation.decisions,1);assert.equal(effect.policy_decision_class,'A');assert.equal(effect.execution_class,'B');
  assert.equal(observation.action_execution.rule_takeover_count,0);
  assert.equal(observation.action_execution.revision,'selected-visible-landing-v6-explicit-guard');
  const x=observation.player.x;engine.prepare({clock:'realtime'});engine.advanceTo(observation.frame+30);
  assert.equal(engine.snapshot(false).player.x,x);assert.equal(engine.snapshot(false).frame,observation.frame+30);
});
test('distinct landing-region choices retain distinct actual outcomes',async()=>{
  const left=fixture().engine,right=fixture().engine,options=choices(left);
  assert.ok(options.length>=2);
  const a=await execute(left,options[0][0]),b=await execute(right,options[1][0]);
  assert.equal(a.effect.event,'landed');assert.equal(b.effect.event,'landed');
  assert.ok(b.observation.player.x-a.observation.player.x>=31.9);
});
test('a flower pipe offers a legal partial-foot side landing and stops after landing',async()=>{
  const {engine}=fixture('flower'),options=choices(engine);
  assert.ok(options.length>0);assert.equal(options[0][1].landing_plant_exposure,false);
  const {observation,effect}=await execute(engine,options[0][0]);
  assert.equal(effect.event,'landed');assert.equal(effect.jumps_started,1);assert.equal(observation.player.y,258);
  assert.ok(observation.player.x<320&&observation.player.x+observation.player.width>320);
  assert.ok(observation.player.x+observation.player.width<=337);
  engine.advanceTo(observation.frame+180);assert.equal(engine.terminal(),null);
  assert.equal(engine.snapshot(false).player.x,observation.player.x);
});
test('a blocked dynamic safe window expires without choosing another action',async()=>{
  const enemy={x:340,y:240,w:26,h:24,vx:0,min:0,max:1000,alive:true};
  const {engine}=fixture('gap',{enemies:[enemy]}),options=choices(engine);
  assert.ok(options.length>0&&options[0][1].plant_or_enemy_risk);
  const {observation,effect}=await execute(engine,options[0][0]);
  assert.equal(effect.event,'expired');assert.equal(effect.failure_reason,'selected_safe_window_not_found');
  assert.equal(effect.jumps_started,0);assert.ok(effect.wait_frames<=180);
  assert.equal(observation.decisions,1);assert.equal(observation.action_execution.rule_takeover_count,0);
});
test('a visible approach threat aborts; it does not trigger a replacement strategy',async()=>{
  const enemy={x:205,y:328,w:26,h:24,vx:0,min:0,max:1000,alive:true};
  const {engine}=fixture('gap',{enemies:[enemy]}),options=choices(engine);
  const {observation,effect}=await execute(engine,options[0][0]);
  assert.equal(effect.event,'danger_changed');assert.equal(effect.jumps_started,0);
  assert.equal(observation.action_execution.rule_takeover_count,0);assert.equal(observation.decisions,1);
});
test('unobserved far map and entities cannot change candidate facts',()=>{
  const a=fixture(),b=fixture();
  const hidden=b.hooks.inspectWorld();hidden.tiles[8][35]=3;
  b.hooks.fixture({tiles:hidden.tiles,enemies:[{x:1120,y:328,w:26,h:24,vx:-1,min:1080,max:1200,alive:true}],coins:[],plants:[],player:{x:128,y:322,vy:0,on_ground:true}});
  assert.deepEqual(choices(a.engine),choices(b.engine));
  const obs=a.engine.snapshot(false);obs.map.tiles=obs.map.tiles.map(row=>row.slice(0,11));
  assert.deepEqual(core.visibleControl.visibleIntents(obs),{});
});
test('continuation facts explicitly exclude dynamic safety and separate unknown frontier',()=>{
  const {engine}=fixture(),obs=engine.snapshot(false),facts=choices(engine)[0][1];
  const c=facts.continuation;
  assert.equal(c.prediction_type,'deterministic_visible_geometry_only');assert.equal(c.available,true);
  assert.match(c.dynamic_safety,/no_enemy_or_plant_guarantee/);assert.equal(typeof c.headroom_pixels,'number');
  const geometry=core.visibleControl.mario({...obs,enemies:[],plants:[]},'jump_right',90);
  assert.deepEqual(core.visibleControl.visibleContinuation(obs,geometry),
    core.visibleControl.visibleContinuation({...obs,enemies:[{x:500,y:280,width:26,height:24,vx:-1}],plants:[]},geometry));
});
test('candidate identities remain fixed while a safe stationary player waits',()=>{
  const {engine}=fixture(),before=choices(engine).map(([id,f])=>[id,f.intent.obstacle,f.intent.landing_region]);
  engine.advanceTo(30);
  assert.deepEqual(choices(engine).map(([id,f])=>[id,f.intent.obstacle,f.intent.landing_region]),before);
  assert.equal(engine.snapshot(false).timing.inference_world_paused,false);
});
