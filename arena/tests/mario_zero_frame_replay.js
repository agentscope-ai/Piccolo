'use strict';
const assert=require('node:assert/strict');
const core=require('../web/playground/mario-core.js');
const seeds=require('../web/playground/world-seed.js');
const arrival=require('../web/playground/world-arrival.js');
const api=core.create({seedModule:seeds,seed:47,viewportWidth:896,now:()=>0});
arrival.install(api,'mario_platformer');api.reset(47);api.activate(true);api.prepare({clock:'realtime'});
const cases=[
  ['cross_right',0,92,132,true],
  ['cross_visible_right:pipe:11:13:11:9',133,224,277,true],
  ['cross_right',277,368,414,true],
  ['cross_right',414,505,505,false],
  ['cross_right',507,598,598,false],
  ['cross_visible_right:gap:21:24:24:11',600,690,690,true],
];
for(const [action,before,at,after,valid] of cases){
  api.advanceTo(before);const observed=api.prepare({clock:'realtime'});
  api.advanceTo(at);const current=api.snapshot(),verdict=api.checkActionArrival(action,observed,current);
  assert.equal(verdict.valid,valid);
  if(valid)api.act(action);else api.rejectActionArrival(action,observed,current,verdict);
  api.advanceTo(after,{completeAction:true});
  assert.equal(api.snapshot().frame,after);
}
const state=api.snapshot(),effect=state.action_execution.recent_effects.at(-1);
assert.equal(effect.frames,0);
assert.equal(effect.failure_reason,'visible_danger_on_selected_approach');
assert.equal(state.action_execution.status,'idle');
assert.equal(state.recent_player_positions.length,4);
// Recorded frame is an assertion, never permission to finish an action early.
api.prepare({clock:'realtime'});api.act('wait');
assert.throws(()=>api.advanceTo(690,{completeAction:true}),/completion_frame_mismatch/);
console.log('Mario zero-frame action completion and frame tampering checks passed');
