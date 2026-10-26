/* Engine host only: no HTML, DOM, Canvas, network, model or alternate physics. */
'use strict';
const {performance}=require('node:perf_hooks');
const readline=require('node:readline');
const seedSource=require('./world-seed.js');
const arrival=require('./world-arrival.js');
let api=null,kind=null,timer=null,replaying=false,started=null,terminalAt=null,stopped=null,initialWins=0,inferencePaused=false;
const now=()=>performance.now();
const nativeTerminal=()=>{const value=api.terminal();return value&&typeof value==='object'?value:{outcome:value,wins:0};};
function observeTerminal(){
  if(started===null||terminalAt!==null||stopped!==null)return;
  const state=nativeTerminal();
  if(state.outcome||(state.wins||0)>initialWins)terminalAt=now();
}
function clockReport(){
  if(started===null)throw Error('episode_clock_not_started');
  observeTerminal();
  return {revision:'engine-first-terminal-wall-clock-v2',
    elapsed_seconds:((terminalAt??stopped??now())-started)/1000,
    observed_wall_seconds:(now()-started)/1000,terminal_observed:terminalAt!==null,
    terminal_detection_precision:'one_engine_tick',clock_source:'performance.now'};
}
function elapsed(){return (now()-started)/1000;}
function close(){if(timer)clearInterval(timer);timer=null;if(api)api.activate(false);}
function beginClock(){initialWins=nativeTerminal().wins||0;started=now();terminalAt=null;stopped=null;}
function tick(){if(api&&!replaying){api.tick(now());observeTerminal();}}
async function dispatch(method,p){
  if(method==='init'){
    if(api)throw Error('engine_already_initialized');
    kind=p.kind;replaying=!!p.replay;inferencePaused=p.inference_world_paused===true;
    const moduleName=p.core_module;
    if(typeof moduleName!=='string'||!/^[a-z][a-z0-9_-]*-core\.js$/.test(moduleName))throw Error('invalid_registered_world_core_module');
    const core=require('./'+moduleName);
    api=core.create({seedModule:seedSource,seedSource,now,seed:p.seed,
      generationOptions:p.options??undefined,viewportWidth:p.width||896,viewportHeight:p.height||448});
    arrival.install(api,kind);
    api.reset(p.seed,p.options??undefined);api.activate(true);
    if(replaying&&p.frame!=null)api.advanceTo(p.frame);
    const state=api.prepare({clock:inferencePaused?'step':'realtime'});beginClock();
    if(!replaying)timer=setInterval(tick,1000/60);
    return {state,replay:replaying,condition:api.condition(),runtime:'jev.shared-core.node.v1'};
  }
  if(!api)throw Error('engine_not_initialized');
  if(method==='capture')return {state:api.prepare({clock:inferencePaused?'step':'realtime'}),seconds:elapsed()};
  if(method==='snapshot')return api.snapshot();
  if(method==='condition')return api.condition();
  if(method==='terminal')return nativeTerminal();
  if(method==='advanceInferenceWait'){
    if(!inferencePaused||replaying||!Number.isSafeInteger(p.frames)||p.frames<120||p.frames>240)
      throw Error('invalid_simulated_inference_wait');
    const start=api.snapshot().frame;
    for(let i=1;i<=p.frames;i++){
      const terminal=nativeTerminal();
      if(terminal.outcome||(terminal.wins||0)>initialWins)break;
      api.advanceTo(start+i);observeTerminal();
    }
    return {requested_frames:p.frames,advanced_frames:api.snapshot().frame-start};
  }
  if(method==='commit'){
    // A public snapshot is a value at capture time, never a live object that
    // can acquire the following action's history while awaiting act().
    const state=structuredClone(api.snapshot()),seconds=elapsed();
    const verdict=api.checkActionArrival(p.action,p.observed,state);
    const after=verdict.valid?await api.act(p.action):api.rejectActionArrival(p.action,p.observed,state,verdict);
    return {arrival_state:state,after_state:after,reason:verdict.reason,arrival_check:verdict,
      arrival_seconds:seconds,real_time_seconds:elapsed()};
  }
  if(method==='finish'){
    const state=api.snapshot(),seconds=elapsed();observeTerminal();stopped=now();
    const terminalClock=clockReport();close();return {state,seconds,terminalClock};
  }
  if(method==='replayObserve'){
    if(!replaying)throw Error('replay_only');
    api.advanceTo(p.frame);return api.prepare({clock:inferencePaused?'step':'realtime'});
  }
  if(method==='replayEvent'){
    if(!replaying)throw Error('replay_only');
    const e=p.event;api.advanceTo(e.arrival_state.frame);const state=structuredClone(api.snapshot());
    const verdict=api.checkActionArrival(e.action,e.before_state,state);
    let completed=false,actionTask,actionError;
    if(verdict.valid)actionTask=api.act(e.action).then(value=>{completed=true;return value;},error=>{actionError=error;});
    else api.rejectActionArrival(e.action,e.before_state,state,verdict);
    api.advanceTo(e.after_state.frame);
    await Promise.resolve();
    if(actionError)throw actionError;
    if(verdict.valid&&kind==='mario_platformer'&&e.after_state.action_execution?.remaining_frames===0){
      if(api.snapshot().action_execution.remaining_frames>0)api.settleActionAtFrame(e.after_state.frame);
      await actionTask;
      if(actionError)throw actionError;
    }
    return {arrival:state,after:api.snapshot(),verdict};
  }
  if(method==='replayFinal'){
    if(!replaying)throw Error('replay_only');
    api.advanceTo(p.frame);
    // A rejected last reply leaves the captured observation awaiting a model.
    // Preparing it again would create an observation absent from the live run
    // (Terra refreshes visible guardian memory in prepare). Only reconstruct a
    // missing prepare transition; finish itself merely takes a snapshot.
    if(p.awaiting&&!api.snapshot().timing?.awaiting_model)api.prepare({clock:inferencePaused?'step':'realtime'});
    return api.snapshot();
  }
  if(method==='close'){close();return {closed:true};}
  throw Error('unknown_engine_method');
}
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
input.on('line',async line=>{
  let request;
  try{request=JSON.parse(line);const result=await dispatch(request.method,request.params||{});
    process.stdout.write(JSON.stringify({id:request.id,result})+'\n');}
  catch(error){process.stdout.write(JSON.stringify({id:request?.id,error:{type:error.name,message:String(error.message).slice(0,500)}})+'\n');}
});
input.on('close',()=>{close();process.exit(0);});
process.on('SIGTERM',()=>{close();process.exit(0);});
