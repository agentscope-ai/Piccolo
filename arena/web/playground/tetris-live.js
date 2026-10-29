/* The server advances the clock. Drawing only interpolates received states. */
window.JevTetrisUI=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en,kind='tetris_placement';
 const isWorld=g=>window.JevTetrisRenderer.supports(g);
 const active=()=>playTabVisible&&selectedPlay===kind&&isWorld(showcaseSession?.world);
 const current=session=>active()&&showcaseSession.session_id===session;
 const buttons={left:['← Left','← 左移'],rotate_ccw:['↶ Rotate','↶ 左旋'],rotate_cw:['↷ Rotate','↷ 右旋'],right:['Right →','右移 →'],soft_drop:['↓ Soft drop','↓ 软降'],hard_drop:['⤓ Hard drop','⤓ 直落']};
 let id=null,epoch=0,timer=null,raf=null,pending=null,driver=null,painted=null,animation=null;
 const receipts=[];
 function halt(){epoch++;clearTimeout(timer);cancelAnimationFrame(raf);timer=raf=null;animation=null;painted=null;}
 function cancelPending(){if(!pending)return;const old=pending;pending=null;api('showcases/tetris/cancel',{session_id:old.id}).catch(()=>{});showcaseBusy=false;showcaseControls(false);}
 function deactivate(){cancelPending();halt();if(id){$('showcaseCanvas').width=900;$('showcaseCanvas').height=540;}id=null;driver=null;}
 function controls(){
  if(!active())return;const g=showcaseSession.world,ended=!!g.outcome;
  document.querySelectorAll('[data-tetris-action]').forEach(button=>{button.disabled=ended||g.phase==='clearing';});
  $('showcaseNew').disabled=false;document.querySelectorAll('#gamePicker button').forEach(b=>b.disabled=false);
  if(ended){$('showcaseModel').disabled=true;$('showcaseAuto').disabled=!showcaseAuto;}
 }
 function status(g){
  $('showcaseGoal').textContent=tr('Clear 4 lines within 40 pieces and 240 seconds.','240 秒、40 块内消除 4 行。');
  $('sceneStats').innerHTML=statMarkup([[g.lines+' / '+(g.line_target||4),tr('Lines','已消行')],[g.steps+' / '+(g.max_pieces||40),tr('Pieces','已落方块')],[g.started?Number(g.elapsed).toFixed(1)+' s':tr('Ready','待开始'),tr('Time','时间')],[!g.started?tr('Ready','待开始'):tr(({falling:'Falling',locking:'Locking',clearing:'Clearing'})[g.phase]||'Finished',({falling:'下落中',locking:'即将锁定',clearing:'消行中'})[g.phase]||'已结束'),tr('Phase','阶段')]]);
  $('keyboardHint').textContent=tr('← → / A D move · ↑ / W rotate · Z reverse rotate · ↓ / S soft drop · Space hard drop. The first key starts gravity; pieces keep falling while the model responds.','← → / A D 移动 · ↑ / W 旋转 · Z 反转 · ↓ / S 软降 · 空格直落。首次按键后自动下落，模型思考时继续运行。');
  const outcome=$('showcaseOutcome');outcome.className=g.outcome?(g.outcome==='win'?'win':'loss'):'hidden';
  if(g.outcome){outcome.innerHTML='<strong>'+esc(g.outcome==='win'?tr('Four lines cleared!','四行已消除！'):tr('Game over','本局结束'))+'</strong><button id="sceneAgain">'+esc(tr('Play again ↻','再开一局 ↻'))+'</button>';$('sceneAgain').onclick=()=>newShowcase();}
  $('showcaseNew').textContent=tr('↻ Restart','↻ 重新开局');controls();
 }
 function paint(g){
  const old=painted;painted=g;
  if(old&&g.elapsed>=old.elapsed){
   const frames=(g.execution_trace?.frames||[]).filter(f=>Number(f.elapsed)>Number(old.elapsed)+1e-8).map(f=>({...g,...f}));
   // Receipts contain every physics contact, lock and clear boundary. Never
   // invent a movement between two different pieces or across a board change.
   animation={frames:[old,...frames,g],start:performance.now(),duration:Math.min(180,Math.max(45,(g.elapsed-old.elapsed)*1000))};
  }
  if(raf)return;
  const frame=now=>{raf=null;if(!active())return;
   if(animation){const p=Math.min(1,(now-animation.start)/animation.duration),frames=animation.frames;
    const first=Number(frames[0].elapsed),last=Number(frames.at(-1).elapsed),target=first+(last-first)*p;
    let index=0;while(index<frames.length-2&&Number(frames[index+1].elapsed)<=target)index++;
    const before=frames[index],after=frames[index+1],span=Number(after.elapsed)-Number(before.elapsed);
    PlayDraw.draw(after,{before,progress:span>0?Math.min(1,Math.max(0,(target-Number(before.elapsed))/span)):p});
    if(p<1)raf=requestAnimationFrame(frame);else animation=null;
   }else PlayDraw.draw(painted);
  };raf=requestAnimationFrame(frame);
 }
 function merge(update){
  if(!current(update.session_id))return false;const before=showcaseSession.world;
  if(update.world.elapsed+1e-7<before.elapsed||update.revision<showcaseSession.revision&&update.world.elapsed<=before.elapsed+1e-7)return false;
  showcaseSession.world=update.world;showcaseSession.revision=Math.max(showcaseSession.revision,update.revision);showcaseSession.choices=update.choices||showcaseSession.choices;
  if(driver)driver.revision=Math.max(driver.revision,showcaseSession.revision);status(update.world);paint(update.world);return true;
 }
 async function poll(session,token){
  if(token!==epoch||!current(session))return;
  try{const result=await api('showcases/tetris/tick',{session_id:session});if(token===epoch)merge(result);}catch(e){if(token===epoch&&current(session))error(e);}
  if(token===epoch&&current(session)&&!showcaseSession.world.outcome)timer=setTimeout(()=>poll(session,token),80);
 }
 function activate(){if(!active()||id===showcaseSession.session_id)return;halt();id=showcaseSession.session_id;driver={id,revision:showcaseSession.revision,sending:false,queue:[]};paint(showcaseSession.world);timer=setTimeout(()=>poll(id,epoch),0);}
 function apply(result,model){
  if(!current(result.session_id))return;merge(result);
  if(result.previous_input)$('showcaseFields').innerHTML=showcaseInputs(result.previous_input);
  if(result.result)$('showcaseResult').innerHTML=resultHtml(result.result);
  if(result.execution){receipts.push(result.execution);if(receipts.length>200)receipts.shift();}
  if(result.applied)decisionLog(model?'model':'human',JevPlayText.action(kind,result.action,result.action_name),null,result.result);
  else if(model){DecisionTiming.record('showcase',result.result);$('lastDecision').textContent=result.discard_reason==='continuing_intent'?tr('Executing selected target · Gravity continues','执行已选目标 · 重力持续运行'):result.discard_reason==='piece_changed_while_waiting'?tr('Response skipped · A new piece is falling','回复未执行 · 已进入下一块'):tr('Response skipped · Game continued','回复未执行 · 游戏继续运行');}
 }
 async function drain(owner){
  if(owner.sending)return;owner.sending=true;
  try{while(owner.queue.length&&current(owner.id)){
   const intent=owner.queue.shift();
   if(intent.piece_id!==showcaseSession.world.active?.piece_id)continue;
   const result=await api('showcases/step',{session_id:owner.id,revision:Math.max(owner.revision,showcaseSession.revision),piece_id:intent.piece_id,action:intent.action,model:false,reference:false});
   owner.revision=Math.max(owner.revision,result.revision);apply(result,false);if(result.world.outcome)break;
  }}catch(e){owner.queue.length=0;if(current(owner.id)){try{merge(await api('showcases/tetris/tick',{session_id:owner.id}));}catch{}error(e);}}
  finally{owner.sending=false;if(current(owner.id))controls();}
 }
 async function step(action,model,reference=false){
  if(!active()||showcaseSession.world.outcome||reference)return false;
  if(!model){if(!(action in buttons)||showcaseSession.world.phase==='clearing')return false;if(showcaseAuto||pending)stopAuto();
   if(driver.queue.length<12)driver.queue.push({action,piece_id:showcaseSession.world.active?.piece_id});void drain(driver);return true;}
  if(showcaseBusy||driver?.sending)return false;
  const owner={id:showcaseSession.session_id};pending=owner;showcaseBusy=true;showcaseControls(true);clearError();$('lastDecision').textContent=showcaseSession.world.started?tr('Model thinking · Pieces keep falling','模型思考中 · 方块继续下落'):tr('First decision · Gravity starts after the reply','首次判断中 · 回复后开始重力下落');
  try{const result=await api('showcases/step',{session_id:owner.id,revision:showcaseSession.revision,action:null,model:true,reference:false});if(pending!==owner||!current(owner.id))return false;apply(result,true);return !!result.applied||['piece_changed_while_waiting','clearing','continuing_intent'].includes(result.discard_reason)&&!result.world.outcome;}
  catch(e){if(pending===owner&&current(owner.id))error(e);return false;}
  finally{if(pending===owner){pending=null;showcaseBusy=false;showcaseControls(false);}}
 }
 function render(){
  if(!active())return;const fresh=id!==showcaseSession.session_id;
  $('showcaseActions').innerHTML='<div class="tetris-live-controls">'+Object.entries(buttons).map(([action,label])=>'<button type="button" data-tetris-action="'+action+'">'+esc(tr(...label))+'</button>').join('')+'</div>';
  document.querySelectorAll('[data-tetris-action]').forEach(button=>button.onclick=()=>{button.blur();step(button.dataset.tetrisAction,false);});
  if(fresh)$('showcaseFields').innerHTML=showcaseInputs(showcaseSession.input);status(showcaseSession.world);activate();if(!fresh)paint(showcaseSession.world);
 }
 document.addEventListener('keydown',e=>{if(!active()||e.ctrlKey||e.altKey||e.metaKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;
  const action={arrowleft:'left',a:'left',arrowright:'right',d:'right',arrowup:'rotate_cw',w:'rotate_cw',x:'rotate_cw',z:'rotate_ccw',arrowdown:'soft_drop',s:'soft_drop',' ':'hard_drop'}[e.key.toLowerCase()];
  if(action){e.preventDefault();if(e.repeat&&['rotate_cw','rotate_ccw','hard_drop'].includes(action))return;step(action,false);}});
 window.JevI18n?.onChange(()=>{if(active())render();});
 return {isWorld,active,activate,deactivate,cancelPending,controls,render,step,receipts};
})();
