/* The server owns every physics step. Human controls submit the same joint Choice
 * as the model; held inputs renew intent, never integrate a client-side car. */
window.JevRacingUI=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en;
 const kind='racing_sprint',steers={hard_left:'Hard left',left:'Left',straight:'Straight',right:'Right',hard_right:'Hard right'},pedals={throttle:'Gas',coast:'Coast',brake:'Brake'};
 let timer=null,pollEpoch=0,sessionId=null,pending=null,sequence=0,lastHumanAction=null;
 const receipts=[],keys=new Set(),pointers=new Map(),drivers=new Map();
 const active=()=>playTabVisible&&selectedPlay===kind&&showcaseSession?.world.kind===kind;
 const current=id=>active()&&showcaseSession.session_id===id;
 const steerName=k=>tr(steers[k]||k,({hard_left:'急左',left:'向左',straight:'回正',right:'向右',hard_right:'急右'})[k]||k);
 const pedalName=k=>tr(pedals[k]||k,({throttle:'油门',coast:'滑行',brake:'刹车'})[k]||k);
 let lastResultCopy=null,decisionCopy=null;
 const actionName=a=>{const [s,p]=String(a).split(':');return (s in steers?steerName(s):{pulse_left:tr('Left · 0.35 s','左转 · 0.35 秒'),pulse_right:tr('Right · 0.35 s','右转 · 0.35 秒')}[s]||s)+' · '+pedalName(p)};
 const held=()=>keys.size>0||[...pointers.values()].some(pointer=>pointer.value);
 function remember(r){receipts.push(r);if(receipts.length>200)receipts.shift()}
 function halt(){pollEpoch++;clearTimeout(timer);timer=null;JevRacing.stop()}
 function cancelPending(){
  if(!pending)return;const request=pending;pending=null;sequence++;
  remember({session_id:request.session_id,status:'cancelled',reason:'user_cancelled',clock_contract:'realtime-v1'});
  api('showcases/racing/cancel',{session_id:request.session_id}).catch(e=>{if(current(request.session_id))error(e)});
  showcaseBusy=false;showcaseControls(false);
  if(current(request.session_id)){decisionCopy={kind:'cancelled'};repaintDecision();}
 }
 function controls(disabled){
  const cancel=$('racingCancel');if(cancel){cancel.disabled=!pending;cancel.classList.toggle('hidden',!pending)}
  if(pending){$('showcaseNew').disabled=false;document.querySelectorAll('#gamePicker button').forEach(b=>b.disabled=false)}
  const ended=!!showcaseSession?.world.outcome;
  document.querySelectorAll('#showcaseActions .race-hold,#showcaseActions .race-once').forEach(b=>b.disabled=ended);
  const driver=drivers.get(showcaseSession?.session_id),manual=held()||!!driver?.sending||!!driver?.desired;
  if(manual||ended){$('showcaseModel').disabled=true;$('showcaseAuto').disabled=!showcaseAuto}
  const desired=desiredAction();
  document.querySelectorAll('.race-hold').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.raceSteer===desired.split(':')[0]||b.dataset.racePedal===desired.split(':')[1])));
 }
 function status(g){
  $('showcaseGoal').textContent=tr("Reach the finish before time or vehicle health runs out.","在赛时或车辆耐久耗尽前抵达终点。");
  $('sceneStats').innerHTML=statMarkup([[g.z.toFixed(0)+' m',tr("Distance / ","进度 / ")+g.finish_distance+' m'],[g.speed.toFixed(1),tr("Speed · m/s","速度 · m/s")],[Math.max(0,g.health).toFixed(0),tr("Condition","耐久")],[g.race_started===false?tr("Ready","待发车"):g.elapsed.toFixed(1)+' s',tr("Time / ","赛时 / ")+g.time_limit+' s']]);
  $('keyboardHint').textContent=tr("Accelerate to start the clock. W / ↑ gas · S / ↓ / Space brake · A D / ← → steer · Shift hard turn. Touch: slide to steer while holding a pedal.","踩油门后开始计时。W / ↑ 油门 · S / ↓ / 空格刹车 · A D / ← → 转向 · Shift 急转。触屏可滑动转向，同时按住踏板。");
  const live=$('racingControlState');if(live)live.textContent=pedalName(g.pedal||'coast')+tr(" · Steering "," · 转向 ")+Number(g.steering_input||0).toFixed(1)+tr(" · Lateral "," · 横向速度 ")+Number(g.lateral_velocity||0).toFixed(1)+tr(" m/s · Safety brakes "," m/s · 安全制动 ")+g.rule_takeover_count;
  const outcome=$('showcaseOutcome');outcome.className=g.outcome?(g.outcome==='win'?'win':'loss'):'hidden';
  if(g.outcome){outcome.innerHTML='<strong>'+esc(JevRacing.eventLabel(g))+'</strong><button id="sceneAgain">'+esc(tr('Play again ↻','再开一局 ↻'))+'</button>';$('sceneAgain').onclick=()=>newShowcase();keys.clear();pointers.clear()}
  $('showcaseNew').textContent=g.outcome?tr("↻ Play again","↻ 再开一局"):tr("↻ Restart","↻ 重新开局");controls(showcaseBusy);
 }
 function mergeWorld(update){
  if(!current(update.session_id)||update.world.elapsed+1e-8<showcaseSession.world.elapsed)return false;
  // A tick started before an input can return at the same 50 ms timestamp.
  // Keep the newer control revision instead of briefly reverting its pedal.
  if(update.revision<showcaseSession.revision&&update.world.elapsed<=showcaseSession.world.elapsed+1e-8)return false;
  showcaseSession.world=update.world;showcaseSession.revision=Math.max(showcaseSession.revision,update.revision);
  const driver=drivers.get(update.session_id);if(driver)driver.revision=Math.max(driver.revision,update.revision);
  status(update.world);JevRacing.stream(update.world);return true;
 }
 async function poll(id,epoch){
  if(epoch!==pollEpoch||!current(id))return;
  try{const update=await api('showcases/racing/tick',{session_id:id});if(epoch!==pollEpoch||!current(id))return;mergeWorld(update)}catch(e){if(epoch===pollEpoch&&current(id))error(e)}
  if(epoch===pollEpoch&&current(id)&&!showcaseSession.world.outcome)timer=setTimeout(()=>poll(id,epoch),50);
 }
 function activate(){if(!active())return;const id=showcaseSession.session_id;if(sessionId===id)return;halt();sessionId=id;lastHumanAction=null;decisionCopy=null;JevRacing.stream(showcaseSession.world);timer=setTimeout(()=>poll(id,pollEpoch),0)}
 function desiredAction(){
  const pressed=[...pointers.values()].map(pointer=>pointer.value),has=x=>pressed.includes(x);
  const left=keys.has('a')||keys.has('arrowleft')||keys.has('q')||has('left')||has('hard_left'),right=keys.has('d')||keys.has('arrowright')||keys.has('e')||has('right')||has('hard_right');
  const hard=keys.has('shift')||keys.has('q')||keys.has('e')||has('hard_left')||has('hard_right');
  const steer=has('straight')||left===right?'straight':left?(hard?'hard_left':'left'):(hard?'hard_right':'right');
  const pedal=keys.has('s')||keys.has('arrowdown')||keys.has(' ')||has('brake')?'brake':has('coast')?'coast':keys.has('w')||keys.has('arrowup')||has('throttle')?'throttle':'coast';
  return steer+':'+pedal;
 }
 function renderResultCopy(result,model){
  if(result.result)$('showcaseResult').innerHTML=resultHtml(result.result);
  else $('showcaseResult').innerHTML='<div class="notice">'+(model?tr("No candidate probabilities returned.","未返回候选概率。"):tr("Human · ","人工 · ")+esc(actionName(result.action))+'.')+'</div>';
  if(result.execution){$('showcaseFields').querySelector('[data-racing-feedback]')?.remove();$('showcaseFields').insertAdjacentHTML('beforeend','<div data-racing-feedback>'+field(tr("Execution","执行反馈"),result.execution)+'</div>')}
 }
 function applyResult(result,model){
  if(!current(result.session_id))return;
  const newest=showcaseSession.world.elapsed>result.world.elapsed?showcaseSession.world:result.world;
  showcaseSession={...result,world:newest,revision:Math.max(showcaseSession.revision,result.revision)};status(newest);JevRacing.stream(newest);
  if(result.previous_input)$('showcaseFields').innerHTML=showcaseInputs(result.previous_input);
  lastResultCopy={result,model};if(result.execution)remember({session_id:result.session_id,...result.execution});renderResultCopy(result,model);
  if(result.applied){decisionCopy=null;if(model||lastHumanAction!==result.action)decisionLog(model?'model':'human',actionName(result.action),null,result.result);if(!model)lastHumanAction=result.action}
  else {DecisionTiming.record('showcase',result.result);decisionCopy={kind:'discarded',reason:result.discard_reason};repaintDecision();}
 }
 async function drain(driver){
  if(driver.sending)return;driver.sending=true;
  try{
   while(driver.desired){
    const intent=driver.desired;driver.desired=null;
    // The server already runs fixed 50 ms ticks. Dispatch each input edge
    // immediately; only an in-flight HTTP request coalesces later changes.
    driver.lastSent=performance.now();
    if(current(driver.id))driver.revision=Math.max(driver.revision,showcaseSession.revision);
    try{
     const result=await api('showcases/step',{session_id:driver.id,revision:driver.revision,action:intent.action,model:false,reference:false});
     driver.revision=Math.max(driver.revision,result.revision);driver.errors=0;
     if(current(driver.id))applyResult(result,false);
     if(result.world.outcome){driver.desired=null;driver.manualActive=false;break}
    }catch(e){
     if(++driver.errors<=1){
      try{const snapshot=await api('showcases/racing/tick',{session_id:driver.id});driver.revision=Math.max(driver.revision,snapshot.revision);if(snapshot.world.outcome)break;driver.desired=driver.desired||{action:driver.latest};continue}catch{}
     }
     driver.desired=null;if(current(driver.id))error(e);break;
    }
   }
  }finally{driver.sending=false;if(current(driver.id))showcaseControls(showcaseBusy);else if(!driver.desired)drivers.delete(driver.id)}
 }
 function enqueue(action,id=showcaseSession?.session_id){
  if(!id)return;let driver=drivers.get(id);
  if(!driver){driver={id,revision:showcaseSession?.session_id===id?showcaseSession.revision:0,sending:false,desired:null,lastSent:-Infinity,errors:0,manualActive:false};drivers.set(id,driver)}
  driver.latest=action;driver.manualActive=action!=='straight:coast';driver.desired={action};void drain(driver);if(current(id))controls(showcaseBusy);
 }
 function drive(){if(!active()||showcaseSession.world.outcome)return;if(showcaseAuto||pending)stopAuto();enqueue(desiredAction())}
 function releaseHuman(){
  const id=sessionId,had=held()||!!drivers.get(id)?.manualActive;keys.clear();pointers.clear();
  if(id&&had)enqueue('straight:coast',id);
 }
 function deactivate(){releaseHuman();cancelPending();halt();sessionId=null}
 function pointerDown(e){
  if(!active()||showcaseSession.world.outcome||e.button>0)return;
  e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);
  const group=e.currentTarget.dataset.raceSteer?'steer':'pedal';
  pointers.set(e.pointerId,{group,value:e.currentTarget.dataset.raceSteer||e.currentTarget.dataset.racePedal});drive();
 }
 function pointerMove(e){
  const pointer=pointers.get(e.pointerId);if(!pointer||!active())return;e.preventDefault();
  const row=$('showcaseActions').querySelector(pointer.group==='steer'?'.racing-steering':'.racing-pedals');
  if(!row)return;const bounds=row.getBoundingClientRect();let value=null;
  if(e.clientX>=bounds.left&&e.clientX<=bounds.right&&e.clientY>=bounds.top-8&&e.clientY<=bounds.bottom+8){
   // Include the small gaps between buttons, avoiding neutral blips while sliding.
   const buttons=[...row.querySelectorAll('.race-hold')];
   const nearest=buttons.reduce((best,button)=>{const r=button.getBoundingClientRect(),distance=Math.abs(e.clientX-(r.left+r.width/2));return !best||distance<best.distance?{button,distance}:best;},null)?.button;
   value=nearest?.dataset.raceSteer||nearest?.dataset.racePedal||null;
  }
  if(pointer.value!==value){pointer.value=value;drive();}
 }
 function pointerUp(e){if(!pointers.has(e.pointerId))return;e.preventDefault();pointers.delete(e.pointerId);drive();}
 function buttonKey(e,on){
  if(!['Enter',' '].includes(e.key)||!active()||showcaseSession.world.outcome)return;
  e.preventDefault();e.stopPropagation();const button=e.currentTarget,key='button:'+button.dataset.raceSteer+':'+button.dataset.racePedal;
  if(on){if(e.repeat)return;pointers.set(key,{group:button.dataset.raceSteer?'steer':'pedal',value:button.dataset.raceSteer||button.dataset.racePedal});}
  else pointers.delete(key);
  drive();
 }
 function render(){
  if(!active())return;const isNew=sessionId!==showcaseSession.session_id;
  const el=$('showcaseActions');el.innerHTML='<div class="racing-controls"><div class="racing-control-heading"><strong>'+esc(tr('Hold to drive','按住驾驶'))+'</strong><span>'+esc(tr('Steering + pedal','方向与踏板'))+'</span></div><div class="racing-steering">'+Object.entries(steers).map(([k,v])=>'<button type="button" class="race-hold" data-race-steer="'+k+'" aria-pressed="false">'+esc(steerName(k))+'</button>').join('')+'</div><div class="racing-pedals">'+Object.entries(pedals).map(([k,v])=>'<button type="button" class="race-hold" data-race-pedal="'+k+'" aria-pressed="false">'+esc(pedalName(k))+'</button>').join('')+'</div><div id="racingControlState" class="muted" role="status"></div><details class="racing-once"><summary>'+esc(tr('Single-action controls · ','单次控制 · '))+Object.keys(showcaseSession.choices).length+esc(tr(' actions',' 个动作'))+'</summary><p class="muted">'+esc(tr('Tap turns last 0.35 s; the pedal stays engaged.','短转向持续 0.35 秒，踏板保持。'))+'</p><div>'+Object.entries(showcaseSession.choices).map(([a,label])=>'<button type="button" class="race-once" data-race-action="'+a+'" title="'+esc(actionName(a))+'">'+esc(actionName(a))+'</button>').join('')+'</div></details><button id="racingCancel" class="hidden">'+esc(tr('Cancel response','取消模型回复'))+'</button></div>';
  el.querySelectorAll('.race-hold').forEach(b=>{b.onpointerdown=pointerDown;b.onpointermove=pointerMove;b.onpointerup=pointerUp;b.onpointercancel=pointerUp;b.onlostpointercapture=pointerUp;b.oncontextmenu=e=>e.preventDefault();b.onkeydown=e=>buttonKey(e,true);b.onkeyup=e=>buttonKey(e,false);b.onblur=()=>{const key='button:'+b.dataset.raceSteer+':'+b.dataset.racePedal;if(pointers.delete(key))drive();}});
  el.querySelectorAll('.race-once').forEach(b=>b.onclick=()=>{if(showcaseAuto||pending)stopAuto();enqueue(b.dataset.raceAction)});
  $('racingCancel').onclick=()=>stopAuto();if(isNew)$('showcaseFields').innerHTML=showcaseInputs(showcaseSession.input);status(showcaseSession.world);activate();
 }
 async function step(action,model,reference=false){
  if(!active()||showcaseSession.world.outcome)return false;
  if(reference){error(Error(tr("Choose human or model control for this race.","请选择人工或模型驾驶。")));return false}
  if(!model){if(showcaseAuto||pending)stopAuto();enqueue(action);return true}
  if(showcaseBusy||held()||drivers.get(sessionId)?.sending)return false;
  const driver=drivers.get(sessionId);if(driver)driver.manualActive=false;
  const owner={id:++sequence,session_id:showcaseSession.session_id};pending=owner;showcaseBusy=true;showcaseControls(true);clearError();$('lastDecision').textContent=tr("Model thinking · Race continues","模型思考中 · 赛车继续运行");
  try{
   const result=await api('showcases/step',{session_id:owner.session_id,revision:showcaseSession.revision,action:null,model:true,reference:false});
   if(pending!==owner||!current(owner.session_id)){remember({session_id:owner.session_id,status:'ignored',reason:'inactive_request',execution:result.execution});return false}
   applyResult(result,true);return !!result.applied;
  }catch(e){if(pending===owner&&current(owner.session_id)){error(e);showcaseAuto=false;autoTicket++}return false}
  finally{if(pending===owner){pending=null;showcaseBusy=false;showcaseControls(false)}}
 }
 const drivingKeys=new Set(['w','a','s','d','q','e','arrowup','arrowleft','arrowdown','arrowright','shift',' ']);
 document.addEventListener('keydown',e=>{const k=e.key.toLowerCase();if(!active()||!drivingKeys.has(k)||e.ctrlKey||e.altKey||e.metaKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;e.preventDefault();if(!keys.has(k)){keys.add(k);drive()}});
 document.addEventListener('keyup',e=>{const k=e.key.toLowerCase();if(!keys.has(k))return;e.preventDefault();keys.delete(k);drive()});
 window.addEventListener('blur',releaseHuman);document.addEventListener('visibilitychange',()=>{if(document.hidden)releaseHuman()});
 setInterval(()=>{if(active()&&held()&&!showcaseSession.world.outcome)drive()},1000);

 function repaintDecision(){
  if(!decisionCopy)return;
  $('lastDecision').textContent=decisionCopy.kind==='cancelled'?tr('Response cancelled · Race continues','模型回复已取消 · 赛车继续运行')
    :tr('Not applied · ','未执行 · ')+({terminal:tr('Race finished','赛车已结束'),cancelled:tr('Cancelled','已取消'),model_timeout:tr('Model timed out','模型超时'),model_error:tr('Model request failed','模型请求失败'),race_finished_while_waiting:tr('Race ended while waiting','等待期间赛车已结束')}[decisionCopy.reason]||decisionCopy.reason||tr('Game state changed','对局状态已变化'));
 }
 function repaintLocale(){
  if(!active())return;
  const root=$('showcaseActions');
  root.querySelectorAll('[data-race-steer]').forEach(b=>{b.textContent=steerName(b.dataset.raceSteer);});
  root.querySelectorAll('[data-race-pedal]').forEach(b=>{b.textContent=pedalName(b.dataset.racePedal);});
  root.querySelectorAll('[data-race-action]').forEach(b=>{b.textContent=actionName(b.dataset.raceAction);b.title=b.textContent;});
  const copy=[['.racing-control-heading strong',tr('Hold to drive','按住驾驶')],['.racing-control-heading span',tr('Steering + pedal','方向与踏板')],['.racing-once summary',tr('Single-action controls · ','单次控制 · ')+Object.keys(showcaseSession.choices).length+tr(' actions',' 个动作')],['.racing-once p',tr('Tap turns last 0.35 s; the pedal stays engaged.','短转向持续 0.35 秒，踏板保持。')],['#racingCancel',tr('Cancel response','取消模型回复')]];
  for(const [selector,label] of copy){const node=root.querySelector(selector);if(node)node.textContent=label;}
  status(showcaseSession.world);
  if(lastResultCopy?.result.session_id===showcaseSession.session_id)renderResultCopy(lastResultCopy.result,lastResultCopy.model);
  if(pending)$('lastDecision').textContent=tr('Model thinking · Race continues','模型思考中 · 赛车继续运行');else repaintDecision();
 }
 window.JevI18n?.onChange(repaintLocale);
 return {activate,deactivate,cancelPending,controls,render,step,receipts,releaseHuman};
})();
