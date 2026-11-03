import {workflowCases} from './workflow-cases.js';

const locale=window.JevI18n;
const tr=(en,zh)=>locale.t(en,zh);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pick=value=>value[locale.lang==='zh'?1:0];

export function mountWorkflowDemo(host,kind){
 const scenes=workflowCases[kind];
 const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
 let active=0,visible=false,wanted=!reducedMotion.matches,timer=null,cursor=0,disposed=false;
 let timeline=[];
 function stop(){clearTimeout(timer);timer=null;}
 function buildTimeline(){
  const scene=current();
  timeline=[...pick(scene.rows).map((_row,i)=>({phase:'reading',row:i,delay:650})),
   {phase:'policy',delay:1000},{phase:'transfer',delay:750},
   {phase:'comparing',delay:1800},
   {phase:'selected',delay:1700},{phase:'complete',delay:6500}];
 }
 function running(){return wanted&&visible&&!document.hidden&&!disposed;}
 function schedule(){stop();if(!running())return;timer=setTimeout(()=>{cursor=(cursor+1)%timeline.length;applyFrame();schedule();},timeline[cursor].delay);}
 function applyFrame(){
  const entry=timeline[cursor],scene=current(),chosen=['selected','complete'].includes(entry.phase);
  host.dataset.phase=entry.phase;
  host.classList.toggle('wd-is-running',running());
  const activity={reading:tr('Piccolo is reading the input','Piccolo 正在读取输入'),policy:tr('Checking the decision rules','核对判断规则'),transfer:tr('Input and rules are ready','输入与规则已就绪'),comparing:tr('Piccolo is evaluating the candidates together','Piccolo 正在同时评估候选'),selected:tr('Piccolo has selected an action','Piccolo 已作出选择'),complete:tr('The selected action is ready','展示对应处理结果')};
  host.querySelector('.wd-activity').textContent=activity[entry.phase];
  const input=host.querySelector('.wd-input-status');
  input.textContent=entry.phase==='reading'?tr('READING INPUT','读取输入')+' · '+(entry.row+1)+' / '+pick(scene.rows).length:tr('INPUT READ ✓','输入已读取 ✓');
  host.querySelectorAll('tbody tr').forEach((row,i)=>{row.classList.toggle('is-reading',entry.phase==='reading'&&i===entry.row);row.classList.toggle('is-read',entry.phase!=='reading'||i<entry.row);});
  host.querySelector('.wd-policy').classList.toggle('is-reading',entry.phase==='policy');
  host.querySelector('.wd-model-status').textContent=chosen?tr('PICCOLO / ACTION SELECTED','PICCOLO / 已选中动作'):entry.phase==='comparing'?tr('PICCOLO / COMPARING OPTIONS','PICCOLO / 比较候选'):tr('PICCOLO / WAITING FOR INPUT','PICCOLO / 等待输入');
  host.querySelectorAll('.wd-choice').forEach((choice,i)=>{const selected=chosen&&i===scene.answer;choice.classList.toggle('is-selected',selected);choice.classList.toggle('is-comparing',entry.phase==='comparing');choice.classList.toggle('is-muted',chosen&&!selected);choice.querySelector('.wd-check').hidden=!selected;});
  const reason=host.querySelector('.wd-explanation');reason.classList.toggle('is-revealed',chosen);reason.querySelector('.wd-reason-copy').setAttribute('aria-hidden',String(!chosen));reason.querySelector('.wd-reason-pending').setAttribute('aria-hidden',String(chosen));
  const complete=entry.phase==='complete',outcome=host.querySelector('.wd-outcome');outcome.classList.toggle('is-executed',complete);outcome.querySelector('.wd-outcome-copy').setAttribute('aria-hidden',String(!complete));outcome.querySelector('.wd-outcome-pending').setAttribute('aria-hidden',String(complete));
  const button=host.querySelector('[data-motion]');button.textContent=wanted?tr('Ⅱ Pause animation','Ⅱ 暂停动画'):tr('▷ Play animation','▷ 播放动画');button.setAttribute('aria-pressed',String(wanted));
 }

 const id=host.id;
 const current=()=>scenes[active];
 function render(focusKey){
  stop();
  const scene=current();
  host.className='workflow-demo';
  const kindTitle=kind==='harness'?'HARNESS':'DATA PROCESSING';
  const options=pick(scene.options);
  host.innerHTML=`
   <h4 class="wd-section-title">${esc(tr('Decision Walkthrough','决策过程详解'))}</h4>
   <div class="wd-tabs" role="tablist" aria-label="${esc(tr(kindTitle+' scenarios',kindTitle+' 子场景'))}">${scenes.map((s,i)=>`<button type="button" role="tab" id="${id}-tab-${i}" aria-controls="${id}-panel" aria-selected="${i===active}" tabindex="${i===active?0:-1}" data-case="${i}">${esc(pick(s.tab))}</button>`).join('')}</div>
   <div class="wd-panel" id="${id}-panel" role="tabpanel" aria-labelledby="${id}-tab-${active}">
    <div class="wd-heading"><span class="wd-eyebrow">${kindTitle} / ${String(active+1).padStart(2,'0')}</span><div class="wd-motion-tools"><button type="button" class="wd-motion" data-motion aria-pressed="true"></button></div></div>
    <h4 class="wd-title">${esc(pick(scene.title))}</h4><p class="wd-background">${esc(pick(scene.background))}</p>
    <div class="wd-brief"><div><span>${esc(tr('THE USER NEEDS','任务目标'))}</span><p>${esc(pick(scene.goal))}</p></div><div><span>${esc(tr('WHAT PICCOLO MUST DECIDE','Piccolo 需要判断什么'))}</span><p>${esc(pick(scene.judge))}</p></div></div>
    <div class="wd-animation-status"><i aria-hidden="true"></i><span class="wd-activity" role="status" aria-live="polite"></span></div>
    <div class="wd-workspace">
     <section class="wd-material" aria-label="${esc(tr('Evidence supplied to the decision model','提供给决策模型的材料'))}"><div class="wd-filebar"><span>${esc(scene.artifact)}</span><span class="wd-input-status"></span></div><div class="wd-material-body"><div class="wd-material-label">${esc(tr('Evidence at this decision point','当前判断节点的证据'))}</div><div class="wd-table-wrap" tabindex="0" role="region" aria-label="${esc(tr('Case evidence table','案例证据表'))}"><table><thead><tr>${pick(scene.headers).map(text=>`<th scope="col">${esc(text)}</th>`).join('')}</tr></thead><tbody>${pick(scene.rows).map(row=>`<tr>${row.map(text=>`<td>${esc(text)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="wd-policy"><span>${esc(tr('RULES TO APPLY','判断规则'))}</span><p>${esc(pick(scene.policy))}</p></div></div></section>
     <section class="wd-judgment" aria-label="${esc(tr('Decision and its consequence','判断与处理后果'))}"><span class="wd-eyebrow wd-model-status"></span><h5>${esc(pick(scene.call))}</h5><div class="wd-choices">${options.map((text,i)=>`<div class="wd-choice "><span class="wd-choice-key">${String.fromCharCode(65+i)}</span><span>${esc(text)}</span><span class="wd-check" hidden aria-label="${esc(tr('Selected','已选择'))}">✓</span></div>`).join('')}</div>
      <div class="wd-explanation"><span>${esc(tr('DECISION BASIS','判断依据'))}</span><div class="wd-reveal"><p class="wd-reason-pending">${esc(tr('Compare the input and rules before selecting an action.','读取输入，对照规则，比较可选动作。'))}</p><p class="wd-reason-copy" aria-hidden="true">${esc(pick(scene.why))}</p></div></div>
      <div class="wd-outcome"><span>${esc(tr('NEXT ACTION','下一步动作'))}</span><div class="wd-reveal"><p class="wd-outcome-pending">${esc(tr('Waiting for Piccolo’s selection…','等待 Piccolo 作出选择…'))}</p><p class="wd-outcome-copy" aria-hidden="true">${esc(pick(scene.outcome))}</p></div></div>
     </section>
    </div>
   </div>
   `;
  buildTimeline();cursor=wanted?0:timeline.length-1;applyFrame();schedule();
  if(focusKey)host.querySelector(focusKey)?.focus({preventScroll:true});
 }
 function selectCase(next,focus=false){active=next;render(focus?`[data-case="${next}"]`:null);}
 host.addEventListener('click',event=>{
  if(event.target.closest('[data-motion]')){wanted=!wanted;if(wanted&&cursor===timeline.length-1)cursor=0;applyFrame();schedule();return;}
  const tab=event.target.closest('[data-case]');
  if(tab)selectCase(Number(tab.dataset.case),true);
 });
 host.addEventListener('keydown',event=>{
  const tab=event.target.closest('[data-case]');if(!tab)return;
  let next=Number(tab.dataset.case);
  if(event.key==='ArrowRight')next=(next+1)%scenes.length;
  else if(event.key==='ArrowLeft')next=(next+scenes.length-1)%scenes.length;
  else if(event.key==='Home')next=0;
  else if(event.key==='End')next=scenes.length-1;
  else return;
  event.preventDefault();selectCase(next,true);
 });
 const observer=new IntersectionObserver(entries=>{for(const entry of entries){visible=entry.isIntersecting;if(visible){applyFrame();schedule();}else{stop();host.classList.remove('wd-is-running');}}},{threshold:0.08});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){stop();host.classList.remove('wd-is-running');}else{applyFrame();schedule();}});
 window.addEventListener('pagehide',()=>{disposed=true;stop();observer.disconnect();},{once:true});
 render();observer.observe(host);
 return {render};
}
