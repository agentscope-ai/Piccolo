/* Re-run the archived clock through the shipped engine, recording every physics tick. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../arena/web/playground');
const source=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const {create}=require(path.join(base,'mario-core.js'));
const seedSource=require(path.join(base,'world-seed.js'));
const options={generator_revision:source.replay.environment_generation.generator_revision};
const api=create({seedModule:seedSource,seedSource,now:()=>0,seed:source.seed,generationOptions:options,viewportWidth:896,viewportHeight:448});
require(path.join(base,'world-arrival.js')).install(api,'mario_platformer');
const visualKeys=['player','map','enemies','plants','coins','powerups','goal_x','progress','collected','powerups_collected','enemies_stomped','shields_used','score','decisions','frame','outcome','event','recent_player_positions'];
function visual(){const s=api.snapshot(false);return Object.fromEntries(visualKeys.map(k=>[k,s[k]]));}
const phases=[];
function advance(target){const frames=[visual()];while(api.snapshot(false).frame<target){const old=api.snapshot(false).frame;api.advanceTo(old+1);assert(api.snapshot(false).frame>old,'Clock stopped before archive frame');frames.push(visual());}return frames;}
(async()=>{
 api.reset(source.seed,options);api.activate(true);api.advanceTo(source.initial_state.frame);api.prepare({clock:'realtime'});
 assert.deepStrictEqual(api.snapshot(),source.initial_state);
 for(const e of source.replay.replay_events){
  const pre=advance(e.before_state.frame);api.prepare({clock:'realtime'});
  assert.deepStrictEqual(api.snapshot(),e.before_state);
  const waiting=advance(e.arrival_state.frame);assert.deepStrictEqual(api.snapshot(),e.arrival_state);
  const verdict=api.checkActionArrival(e.action,e.before_state,api.snapshot());assert.equal(verdict.valid,e.action_applied);
  let task;if(verdict.valid)task=api.act(e.action);else api.rejectActionArrival(e.action,e.before_state,api.snapshot(),verdict);
  const execution=advance(e.after_state.frame);await Promise.resolve();
  if(verdict.valid&&e.after_state.action_execution?.remaining_frames===0){if(api.snapshot().action_execution.remaining_frames>0)api.settleActionAtFrame(e.after_state.frame);await task;}
  assert.deepStrictEqual(api.snapshot(),e.after_state);
  execution[execution.length-1]=visual();
  phases.push({pre,waiting,execution});
 }
 assert.deepStrictEqual(api.snapshot(),source.final_state);api.activate(false);
 process.stdout.write(JSON.stringify(phases));
})().catch(error=>{console.error(error);process.exit(1);});
