/* Public-observation arrival checks shared by browser play and RL.
 * Rejecting an obsolete intent selects no replacement action and never pauses physics.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else {root.JevWorldArrival=api;
    if(root.JevMario)api.install(root.JevMario,'mario_platformer');
    if(root.JevTerramai)api.install(root.JevTerramai,'terraria_survival');
  }
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const revision='visible-arrival-guard-v1';
  const number=x=>typeof x==='number'&&Number.isFinite(x);
  const phase=p=>p.on_ground?'grounded':number(p.vy)&&p.vy<0?'rising':'falling';
  const subgoal=s=>s.control?{subgoal:s.control.subgoal,target:s.control.target,stage:s.control.execution_stage}:
    {goal:s.action_execution?.current_goal,intent:s.action_execution?.selected_intent};
  const visibleIntentPrefix='cross_visible_right:';
  function visibleTarget(facts){
    const intent=facts?.intent,o=intent?.obstacle,l=intent?.landing_region;
    if(intent?.revision!=='visible-crossing-intent-v1'||!o||!l||!['gap','pipe'].includes(o.kind))return null;
    const values=[o.left_col,o.right_col,o.left,o.right,l.column,l.support_row,l.left,l.right,l.top];
    if(!values.every(number))return null;
    return {id:visibleIntentPrefix+[o.kind,o.left_col,o.right_col,l.column,l.support_row].join(':'),
      identity:JSON.stringify([intent.revision,o.kind,...values])};
  }
  function check(kind,action,observed,current){
    let reason=null,fields=[];
    const reject=(value,changed)=>{reason=value;fields=changed;};
    if(current.outcome)reject('terminal',['outcome']);
    else if(observed&&(current.wins||0)!==(observed.wins||0))reject('world_changed',['wins']);
    else if(observed&&((current.deaths||0)!==(observed.deaths||0)||current.player?.respawning||observed.player?.respawning))
      reject('death_or_respawn',['deaths','player.respawning']);
    else if(observed&&!observed.timing?.inference_world_paused&&observed.timing?.mode!=='model_step'){
      const before=observed.player||{},after=current.player||{};
      if(number(before.shield)&&number(after.shield)&&before.shield!==after.shield)
        reject('shield_changed',['player.shield']);
      else if(/jump|cross/.test(action)&&typeof before.on_ground==='boolean'&&typeof after.on_ground==='boolean'&&phase(before)!==phase(after))
        reject('jump_state_changed',['player.on_ground','player.vy']);
      else if(JSON.stringify(subgoal(observed))!==JSON.stringify(subgoal(current)))
        reject('subgoal_changed',['control.subgoal','control.target','action_execution.selected_intent']);
      if(!reason&&kind==='mario_platformer'){
        const oldFacts=observed.candidate_effects?.[action],newFacts=current.candidate_effects?.[action];
        if(oldFacts&&!newFacts)reject('action_unavailable',['candidate_effects']);
        else if(newFacts&&oldFacts&&['plant_or_enemy_risk','visible_pit_fall','landing_plant_exposure','unknown_terrain'].some(k=>newFacts[k]&&!oldFacts[k]))
          reject('visible_danger_changed',['candidate_effects.'+action]);
        if(!reason){
          const horizon=Math.max((after.width||23)*6,60*.65+(after.width||23));
          for(const enemy of current.enemies||[]){
            if(!number(enemy.vx)||Math.abs(enemy.x-after.x)>horizon||Math.abs(enemy.y-after.y)>(after.height||30)+96)continue;
            const candidates=(observed.enemies||[]).filter(e=>number(e.vx)&&e.y===enemy.y&&e.width===enemy.width);
            const dt=Math.max(0,(current.frame||0)-(observed.frame||0));
            candidates.sort((a,b)=>Math.abs(a.x+a.vx*dt-enemy.x)-Math.abs(b.x+b.vx*dt-enemy.x));
            const prior=candidates[0];
            if(prior&&Math.sign(prior.vx)!==Math.sign(enemy.vx)){
              reject('enemy_direction_changed',['enemies.vx']);break;
            }
            if(!prior&&(enemy.x-after.x)*enemy.vx<0){
              reject('new_nearby_enemy',['enemies']);break;
            }
          }
        }
      }
    }
    // A target Choice cannot silently be remapped while its answer is in flight.
    // Launch position and dynamic estimates may change; the selected geometry may not.
    if(!reason&&kind==='mario_platformer'&&action.startsWith(visibleIntentPrefix)){
      const before=visibleTarget(observed?.candidate_effects?.[action]);
      const after=visibleTarget(current.candidate_effects?.[action]);
      if(!before||!after||before.id!==action||after.id!==action)
        reject('action_target_unavailable',['candidate_effects.'+action+'.intent']);
      else if(before.identity!==after.identity)
        reject('action_target_changed',['candidate_effects.'+action+'.intent']);
    }
    return {revision,valid:reason===null,reason,changed_fields:fields,
      requires_new_observation:!!reason&&!['terminal','world_changed'].includes(reason)};
  }
  function install(bridge,kind){
    if(!bridge||bridge.arrival_contract_revision===revision)return;
    const original={snapshot:bridge.snapshot.bind(bridge),prepare:bridge.prepare.bind(bridge),
      act:bridge.act.bind(bridge),reset:bridge.reset.bind(bridge)};
    let rejected=0,recent=[];
    const decorate=s=>({...s,decision_arrival:{revision,rejected_count:rejected,recent_rejections:structuredClone(recent)}});
    bridge.snapshot=(...args)=>decorate(original.snapshot(...args));
    bridge.prepare=(...args)=>decorate(original.prepare(...args));
    bridge.act=(...args)=>Promise.resolve(original.act(...args)).then(decorate);
    bridge.reset=(...args)=>{rejected=0;recent=[];const state=original.reset(...args);return state&&typeof state==='object'?decorate(state):state;};
    bridge.checkActionArrival=(action,observed,current)=>check(kind,action,observed,current);
    bridge.rejectActionArrival=(action,observed,current,verdict)=>{
      if(verdict.valid||!verdict.reason)throw Error('arrival_rejection_requires_invalid_intent');
      rejected++;
      const feedback={revision,action,action_applied:false,reason:verdict.reason,
        changed_fields:verdict.changed_fields,observation_frame:observed?.frame??current.frame,
        arrival_frame:current.frame,requires_new_observation:verdict.requires_new_observation,
        automatic_action:null,rule_takeover_actions:0};
      recent.push(feedback);recent=recent.slice(-8);
      return decorate(current);
    };
    bridge.arrival_contract_revision=revision;
  }
  return {revision,check,install};
});
