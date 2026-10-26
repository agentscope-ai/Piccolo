/* Server-owned fixed-clock Snake. UI animates received moves, never advances physics. */
window.JevSnakeUI=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en,kind='snake_navigation';
 const isWorld=g=>g?.kind===kind&&g.engine_revision==='snake-realtime-v1-six-apples';
 const active=()=>playTabVisible&&selectedPlay===kind&&isWorld(showcaseSession?.world);
 const current=id=>active()&&showcaseSession.session_id===id;
 const names={up:['↑ Up','↑ 上'],left:['← Left','← 左'],down:['↓ Down','↓ 下'],right:['Right →','右 →']};
 let id=null,epoch=0,timer=null,raf=null,pending=null,driver=null,painted=null,animation=null;
 const receipts=[];
 function halt(){epoch++;clearTimeout(timer);cancelAnimationFrame(raf);timer=raf=null;animation=null;painted=null;}
 function cancelPending(){if(!pending)return;const old=pending;pending=null;api('showcases/snake/cancel',{session_id:old.id}).catch(()=>{});showcaseBusy=false;showcaseControls(false);}
 function deactivate(){cancelPending();halt();if(id){const canvas=$('showcaseCanvas');canvas.width=900;canvas.height=540;}id=null;driver=null;}
 function controls(){
  if(!active())return;const ended=!!showcaseSession.world.outcome;
  document.querySelectorAll('[data-snake-direction]').forEach(button=>{button.disabled=ended||!(button.dataset.snakeDirection in showcaseSession.choices);button.setAttribute('aria-pressed',String(button.dataset.snakeDirection===showcaseSession.world.pending_direction));});
  $('showcaseNew').disabled=false;document.querySelectorAll('#gamePicker button').forEach(b=>b.disabled=false);
  if(ended){$('showcaseModel').disabled=true;$('showcaseAuto').disabled=!showcaseAuto;}
 }
 function status(g){
  $('showcaseGoal').textContent=JevPlayText.goal(kind);
  $('sceneStats').innerHTML=statMarkup([[g.score+' / '+g.food_target,tr('Apples','苹果')],[g.started?g.elapsed.toFixed(1)+' s':tr('Ready','待开始'),tr('Time','时间')],[g.steps+' / '+g.max_steps,tr('Moves','移动')],[g.move_interval.toFixed(2)+' s',tr('Per cell','每格')]]);
  $('keyboardHint').textContent=tr('Arrows / WASD or direction buttons. Your first direction starts the clock; Snake keeps moving while the model responds.','方向键 / WASD 或方向按钮。首次输入后自动前进，模型思考时仍继续移动。');
  const outcome=$('showcaseOutcome');outcome.className=g.outcome?(g.outcome==='win'?'win':'loss'):'hidden';
  if(g.outcome){outcome.innerHTML='<strong>'+esc(g.outcome==='win'?tr('Six apples collected!','六颗苹果已集齐！'):g.event==='collision'?tr('Collision · Game over','发生碰撞 · 本局结束'):tr('Game over','本局结束'))+'</strong><button id="sceneAgain">'+esc(tr('Play again ↻','再开一局 ↻'))+'</button>';$('sceneAgain').onclick=()=>newShowcase();}
  $('showcaseNew').textContent=tr('↻ Restart','↻ 重新开局');controls();
 }
 function paint(g){
  if(painted&&g.steps>painted.steps){
   const frames=g.execution_trace?.frames||[];
   const previous=frames.find(f=>f.steps===g.steps-1);
   animation={before:previous?{...g,...previous}:painted,after:g,start:performance.now()};
  }
  painted=g;
  if(raf)return;
  const frame=now=>{raf=null;if(!active())return;if(animation){const progress=Math.min(1,(now-animation.start)/180);PlayDraw.draw(animation.after,{before:animation.before,progress});if(progress<1)raf=requestAnimationFrame(frame);else animation=null;}else PlayDraw.draw(painted);};
  raf=requestAnimationFrame(frame);
 }
 function merge(update){
  if(!current(update.session_id))return false;
  const before=showcaseSession.world;
  if(update.world.elapsed+1e-7<before.elapsed||update.revision<showcaseSession.revision&&update.world.elapsed<=before.elapsed+1e-7)return false;
  showcaseSession.world=update.world;showcaseSession.revision=Math.max(showcaseSession.revision,update.revision);
  showcaseSession.choices=update.choices||showcaseSession.choices;
  if(driver)driver.revision=Math.max(driver.revision,showcaseSession.revision);
  status(update.world);paint(update.world);return true;
 }
 async function poll(session,token){
  if(token!==epoch||!current(session))return;
  try{const result=await api('showcases/snake/tick',{session_id:session});if(token===epoch)merge(result);}catch(e){if(token===epoch&&current(session))error(e);}
  if(token===epoch&&current(session)&&!showcaseSession.world.outcome)timer=setTimeout(()=>poll(session,token),80);
 }
 function activate(){if(!active())return;if(id===showcaseSession.session_id)return;halt();id=showcaseSession.session_id;driver={id,revision:showcaseSession.revision,sending:false,desired:null};paint(showcaseSession.world);timer=setTimeout(()=>poll(id,epoch),0);}
 function apply(result,model){
  if(!current(result.session_id))return;merge(result);
  if(result.previous_input)$('showcaseFields').innerHTML=showcaseInputs(result.previous_input);
  if(result.result)$('showcaseResult').innerHTML=resultHtml(result.result);
  if(result.execution){receipts.push(result.execution);if(receipts.length>200)receipts.shift();}
  if(result.applied)decisionLog(model?'model':'human',JevPlayText.action(kind,result.action,result.action_name),null,result.result);
  else if(model){DecisionTiming.record('showcase',result.result);$('lastDecision').textContent=tr('Response skipped · Game continued','回复未执行 · 游戏继续运行');}
 }
 async function drain(owner){
  if(owner.sending)return;owner.sending=true;
  try{while(owner.desired&&current(owner.id)){
   const action=owner.desired;owner.desired=null;
   try{const result=await api('showcases/step',{session_id:owner.id,revision:Math.max(owner.revision,showcaseSession.revision),action,model:false,reference:false});owner.revision=Math.max(owner.revision,result.revision);apply(result,false);if(result.world.outcome)break;}
   catch(e){if(current(owner.id)){const update=await api('showcases/snake/tick',{session_id:owner.id});merge(update);if(!update.world.outcome&&action in update.choices){const result=await api('showcases/step',{session_id:owner.id,revision:update.revision,action,model:false,reference:false});owner.revision=result.revision;apply(result,false);}}}
  }}catch(e){if(current(owner.id))error(e);}finally{owner.sending=false;if(current(owner.id))controls();}
 }
 async function step(action,model,reference=false){
  if(!active()||showcaseSession.world.outcome)return false;
  if(reference)return false;
  if(!model){if(!(action in showcaseSession.choices))return false;if(showcaseAuto||pending)stopAuto();driver.desired=action;void drain(driver);return true;}
  if(showcaseBusy||driver?.sending)return false;
  const owner={id:showcaseSession.session_id};pending=owner;showcaseBusy=true;showcaseControls(true);clearError();$('lastDecision').textContent=tr('Model thinking · Snake keeps moving','模型思考中 · 贪吃蛇继续前进');
  try{const result=await api('showcases/step',{session_id:owner.id,revision:showcaseSession.revision,action:null,model:true,reference:false});if(pending!==owner||!current(owner.id))return false;apply(result,true);return !!result.applied||result.discard_reason==='direction_changed_while_waiting'&&!result.world.outcome;}
  catch(e){if(pending===owner&&current(owner.id))error(e);return false;}
  finally{if(pending===owner){pending=null;showcaseBusy=false;showcaseControls(false);}}
 }
 function render(){
  if(!active())return;const fresh=id!==showcaseSession.session_id;
  $('showcaseActions').innerHTML='<div class="dpad snake-directions">'+Object.entries(names).map(([a,label])=>'<button type="button" data-snake-direction="'+a+'">'+esc(tr(...label))+'</button>').join('')+'</div>';
  document.querySelectorAll('[data-snake-direction]').forEach(button=>button.onclick=()=>step(button.dataset.snakeDirection,false));
  if(fresh)$('showcaseFields').innerHTML=showcaseInputs(showcaseSession.input);
  status(showcaseSession.world);activate();if(!fresh)paint(showcaseSession.world);
 }
 document.addEventListener('keydown',e=>{if(!active()||e.repeat||e.ctrlKey||e.altKey||e.metaKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;const action={arrowup:'up',w:'up',arrowdown:'down',s:'down',arrowleft:'left',a:'left',arrowright:'right',d:'right'}[e.key.toLowerCase()];if(action){e.preventDefault();step(action,false);}});
 window.JevI18n?.onChange(()=>{if(active())render();});
 return {isWorld,active,activate,deactivate,cancelPending,controls,render,step,receipts};
})();
