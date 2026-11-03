(() => {
'use strict';
// Small, authored SVG scenes: each action moves or changes a different object.
const txt=(x,y,t,cls='')=>`<text x="${x}" y="${y}" class="${cls}">${t}</text>`;
const box=(x,y,w,h,cls='box')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" class="${cls}"/>`;
const path=(d,cls='wire')=>`<path d="${d}" class="${cls}"/>`;
const group=(s,cls)=>`<g class="${cls}">${s}</g>`;
const moving=(s,x,y,dx,dy)=>`<g data-motion="${[x,y,dx,dy].join(',')}" transform="translate(${x} ${y})">${s}</g>`;
const dot=(x,y,dx,dy)=>moving('<circle r="3.5" class="packet"/>',x,y,dx,dy);
const checkmark=(x,y)=>path(`M${x} ${y}l4 4 8-9`,'selected-stroke');
const doc=(x,y,label='',cls='box')=>box(x,y,27,33,cls)+path(`M${x+6} ${y+9}h15 M${x+6} ${y+15}h11 M${x+6} ${y+21}h13`,'paper-line')+(label?txt(x+3,y+45,label,'small'):'');
const robot=(x,y,cls='box')=>box(x,y,28,23,cls)+path(`M${x+14} ${y}v-5 M${x-3} ${y+7}v9 M${x+31} ${y+7}v9`,'ink')+`<circle cx="${x+9}" cy="${y+9}" r="1.5" fill="#a57c53"/><circle cx="${x+19}" cy="${y+9}" r="1.5" fill="#a57c53"/>`+path(`M${x+9} ${y+16}h10`,'ink');
const shield=(x,y)=>path(`M${x} ${y}l17-7 17 7v17c0 11-17 19-17 19s-17-8-17-19z`,'ink');
const funnel=(x,y)=>path(`M${x} ${y}h27l-10 13v12l-7 4V${y+13}z`,'ink');
const scenes={
H1:doc(12,27,'#1842')+group(txt(7,13,'Delivery date?','small'),'before')+path('M43 43H96 M96 43L133 15H167 M96 43H167 M96 43L133 72H167')+box(168,4,93,20)+txt(178,18,'⌕ Web')+box(168,33,93,21,'state-box')+txt(178,47,'▤ Orders')+box(168,62,93,20)+txt(178,76,'✉ Email')+`<circle cx="95" cy="43" r="14" class="box"/>`+path('M88 43h14 M98 39l4 4-4 4','ink')+path('M43 43H166','route')+dot(43,43,118,0)+group(txt(7,13,'Delivered Friday','green-text small'),'after'),
H2:doc(12,27)+txt(5,12,'100 labels · $1 budget','small')+txt(5,87,'Both models qualified','small')+path('M43 43H113 M113 43L147 17 M113 43H147 M113 43L147 72')+robot(148,5,'state-box')+txt(185,20,'Small · $0.20')+robot(148,34)+txt(185,49,'Large · $4')+`<circle cx="161" cy="66" r="5" class="box"/>`+path('M151 81v-3a10 10 0 0 1 20 0v3z','ink')+txt(185,78,'Human · $8')+path('M43 43H113L147 17','route')+dot(46,43,95,-26)+group(txt(6,74,'Assigned ✓','green-text small'),'after'),
H3:txt(7,10,'Dinner-planning memory','small')+group(box(7,15,90,18)+txt(14,28,'Hello!'),'discard')+box(7,39,90,20,'state-box')+txt(14,53,'Peanut allergy')+group(box(7,66,90,18)+txt(14,79,'Old weather'),'discard')+path('M98 49H146 M174 49H212')+funnel(146,35)+box(211,27,59,47,'state-box')+path('M222 36h35 M222 43h28','paper-line')+group(txt(217,59,'Allergy','green-text')+txt(217,70,'retained','green-text small'),'after')+moving('<rect width="16" height="8" rx="3" class="good"/>',101,45,101,0),
H4:txt(7,12,'Draft-only access','small')+box(11,28,39,28)+path('M12 30l18 13 19-13','ink')+path('M51 42H107 M141 42H204 M141 42L180 15H220')+shield(108,29)+box(218,5,51,20)+txt(225,19,'Send')+group(path('M235 7l13 13 M248 7l-13 13','ink'),'after')+box(205,40,63,34,'state-box')+txt(214,65,'Draft tray')+moving(box(0,0,22,15,'good')+path('M1 1l10 8 10-8','selected-stroke'),52,34,163,7)+group(checkmark(118,45),'after'),
H5:Array.from({length:10},(_,i)=>{const x=9+(i%5)*25,y=15+Math.floor(i/5)*32;return box(x,y,19,24,i<8?'good':'state-box')+ (i<8?checkmark(x+3,y+12):group(checkmark(x+3,y+12),'after'));}).join('')+path('M139 43H186')+`<circle cx="223" cy="43" r="28" class="state-box"/>`+group(txt(205,47,'8 / 10'),'before')+group(txt(200,47,'10 / 10','green-text strong'),'after')+moving('<rect width="2" height="65" rx="1" fill="#8a9383" opacity=".55"/>',6,10,131,0)+group(txt(193,83,'All verified','green-text small'),'after'),
H6:robot(15,32)+box(209,19,49,48,'state-box')+path('M219 29h29 M219 38h29 M219 47h29','paper-line')+path('M49 43H207 M202 17C154-6 94-5 58 19 M58 19l3-8 M58 19l9-1')+group(txt(91,33,'503 · busy','strong'),'before')+group(txt(92,33,'200 · OK','green-text strong'),'after')+dot(51,43,154,0)+txt(5,79,'Request','small')+txt(209,79,'Service','small')+txt(90,63,'Temporary error','small')+group(txt(107,78,'Retry ↻','green-text'),'after'),
D1:doc(10,7)+box(10,46,27,33)+txt(19,67,'∅','strong')+doc(45,25)+txt(5,90,'3 input records','small')+path('M76 42H115 M145 42H200 M134 54V76H163')+funnel(116,26)+group(doc(205,11,'','good')+doc(239,39,'','good')+txt(205,89,'2 kept','green-text small'),'after')+moving(box(0,0,19,24,'good')+path('M4 7h11 M4 12h8','paper-line'),78,25,125,-14)+moving(box(0,0,17,21)+txt(4,14,'∅'),101,47,48,16)+group(txt(165,81,'Empty → drop','small'),'after'),
D2:box(4,13,62,23)+txt(10,28,'&lt;p&gt;Hi&lt;/p&gt;')+box(4,50,62,23)+txt(22,65,'Hi')+path('M67 25L92 43 M67 61L92 43H109 M142 43H174 M202 43H232')+`<circle cx="125" cy="43" r="17" class="state-box"/>`+path('M131 31l-13 15 M114 43l10 9 M113 47l8 8','ink')+box(174,24,24,24,'state-box')+txt(180,39,'Hi')+box(182,39,24,24,'state-box')+txt(188,54,'Hi')+group(box(239,27,31,33,'good')+txt(248,47,'Hi','green-text'),'after')+txt(108,79,'Clean','small')+txt(167,79,'Dedup','small')+moving('<circle r="4" class="packet"/>',70,43,164,0)+group(txt(7,86,'2 rows → 1','green-text small'),'after'),
D3:box(4,12,112,67)+txt(12,26,'RETURN POLICY','small')+txt(12,43,'Return within')+txt(12,57,'30 days with')+txt(12,71,'a valid receipt.')+path('M117 45L135 18 M117 45H135 M117 45L135 74')+box(137,3,139,32,'state-box')+txt(144,16,'A  30-day returns')+txt(157,29,'Receipt required')+group(box(137,40,139,22)+txt(144,55,'B  Returns anytime'),'discard')+group(box(137,67,139,22)+txt(144,82,'C  No receipt needed'),'discard')+path('M117 45L135 18','route')+dot(118,45,15,-27)+group(checkmark(262,15),'after'),
D4:box(6,7,124,76)+path('M6 31H130 M6 56H130 M94 7V83')+txt(13,23,'Revenue')+txt(101,23,'120')+txt(13,48,'Costs')+txt(106,48,'80')+txt(13,73,'Tax')+txt(111,73,'?','strong')+path('M131 44H175')+`<circle cx="201" cy="44" r="21" class="box"/>`+txt(195,51,'?','strong')+group(box(164,8,104,23,'good')+txt(173,24,'Request tax','green-text'),'after')+moving('<circle r="4" class="packet"/>',117,68,60,-38)+txt(154,83,'Profit after tax','small'),
D5:box(5,20,101,50)+txt(12,37,'“Great search”')+txt(12,56,'sam@acme.test','small')+path('M107 44H124 M160 44H193')+shield(125,29)+box(195,20,80,50,'state-box')+group(txt(202,37,'Great search')+box(202,46,65,14,'good')+txt(213,57,'[email]','green-text small'),'after')+dot(108,44,83,0)+txt(13,84,'Private row','small')+txt(211,84,'Public row','small'),
D6:group(doc(7,5,'v1 ✓'),'discard')+doc(55,35,'v2','state-box')+path('M85 52H132 M163 52H218')+`<circle cx="147" cy="52" r="17" class="state-box"/>`+group(checkmark(141,52),'after')+box(220,37,50,29,'state-box')+path('M229 50h28 M236 43l-7 7 7 7','ink')+group(txt(203,26,'Ready to commit','green-text small'),'after')+moving(doc(0,0,'','good'),88,35,119,0)+txt(121,84,'Validate','small')
};
const fixtures=[
['H1','Tool selection',['Web','Orders','Email'],1,'Route the order lookup to the correct tool.'],
['H2','Model routing',['Small · $0.20','Large · $4','Human · $8'],0,'Assign a qualified model within the one-dollar budget. Costs are illustrative.'],
['H3','Context & memory',['Greeting','Weather','Allergy'],2,'Retain the allergy while compressing conversation context.'],
['H4','Permissions & trust',['Send','Save draft','Publish'],1,'Save the draft without sending an unauthorized message.'],
['H5','Progress verification',['Verify 2','Finish','Discard'],0,'Verify the two remaining files before finishing.'],
['H6','Failure recovery',['Guess','Abandon','Retry'],2,'Retry a transient failure and receive a valid response.'],
['D1','Data filtering',['Keep all','Drop empty','Drop all'],1,'Filter empty records and preserve useful text.'],
['D2','Processing plans',['Dedup first','Keep both','Clean first'],2,'Clean markup before removing duplicate text.'],
['D3','Output quality',['Summary A','Summary B','Summary C'],0,'Compare summaries against a return policy: preserve both the 30-day limit and the receipt requirement.'],
['D4','Information sufficiency',['40','Request tax','120'],1,'Request the missing tax to calculate after-tax profit.'],
['D5','Evidence & privacy',['Publish all','Drop text','Mask email'],2,'Remove personal information while preserving useful feedback.'],
['D6','Workflow control',['Validate v2','Use v1','Skip check'],0,'Validate v2; the previous v1 check is stale. The validated file becomes ready to commit.']
].map(([id,title,options,answer,description])=>({id,title,options,answer,description,group:id[0]==='H'?'harness':'data'}));
const translations = {
 H1:['工具选择',['网页','订单系统','邮件'],'将订单查询交给合适的工具。'],
 H2:['模型路由',['小模型 · $0.20','大模型 · $4','人工 · $8'],'两个模型均满足任务要求，选择一美元预算内的方案。图中费用为示例设置。'],
 H3:['上下文与记忆',['问候','天气','过敏信息'],'压缩对话时，保留晚餐安排所需的过敏信息。'],
 H4:['权限与信任',['发送','保存草稿','发布'],'保存草稿，避免发送未经授权的消息。'],
 H5:['完成验收',['核查剩余两项','结束任务','丢弃'],'在结束任务前，核查剩余两个文件。'],
 H6:['失败恢复',['猜测','放弃','重试'],'遇到临时服务故障后重试，取得有效响应。'],
 D1:['数据过滤',['全部保留','移除空记录','全部丢弃'],'过滤空记录，保留有效文本。'],
 D2:['处理方案',['先去重','保留两条','先清洗'],'先清理标记，再删除重复文本。'],
 D3:['产物质量',['摘要 A','摘要 B','摘要 C'],'对照退货政策选择摘要，同时保留三十天期限和收据要求。'],
 D4:['信息充分性',['40','询问税额','120'],'补充缺失的税额后，再计算税后利润。'],
 D5:['证据与隐私',['全部发布','删除文本','隐藏邮箱'],'隐藏个人信息，保留有用反馈。'],
 D6:['工作流控制',['校验 v2','沿用 v1','跳过校验'],'先校验 v2，再提交新文件；v1 的校验结果已不适用。']
};
const query = new URLSearchParams(location.search);
let lang = query.get('lang') === 'zh' ? 'zh' : 'en';
const duration=18000;
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
let clock=0, playing=!reducedMotion.matches, speed=3, last=performance.now();
let parentVisible=parent===window, animationFrame=null;
const requestedGroup=new URLSearchParams(location.search).get('group');
const groupFilter=['harness','data'].includes(requestedGroup)?requestedGroup:null;
if(groupFilter){
 document.documentElement.classList.add('single-group');
 document.querySelectorAll('.workflow-gallery').forEach(section=>{
  if(!section.querySelector(`#${groupFilter}`))section.remove();
 });
}
const cards=fixtures.filter(f=>!groupFilter||f.group===groupFilter).map((f,i)=>{
const el=document.createElement('article');el.className='demo-card';el.dataset.case=f.id;el.setAttribute('aria-label',f.title);
el.innerHTML=`<header class="card-heading"><span>${f.id}</span><h3>${f.title}</h3></header><div class="scene"><svg viewBox="0 0 280 92" role="img" aria-label="${f.description}">${scenes[f.id]}</svg></div><div class="options" role="list" aria-label="Candidate actions">${f.options.map((s,n)=>`<div class="option" role="listitem"><span>${s}</span><span class="tick" aria-hidden="true">✓</span></div>`).join('')}</div><div class="progress" aria-hidden="true"><i></i></div>`;
document.getElementById(f.group).append(el);
return {f,el,offset:(i%6)*850,phase:'',cycles:0,options:[...el.querySelectorAll('.option')],bar:el.querySelector('.progress i'),motions:[...el.querySelectorAll('[data-motion]')].map(e=>({e,v:e.dataset.motion.split(',').map(Number)}))};
});
function render(){cards.forEach(c=>{
const elapsed=clock+c.offset,pos=elapsed%duration;c.cycles=Math.floor(elapsed/duration);
const phase=pos<4500?'read':pos<11000?'choose':'result';
if(c.phase!==phase){c.phase=phase;c.el.dataset.phase=phase;c.options.forEach((o,n)=>o.classList.toggle('selected',phase!=='read'&&n===c.f.answer));}
// Geometry, fades and state transitions share the playback clock, including pause/speed.
const u=Math.max(0,Math.min(1,(pos-5000)/5000)),ease=u*u*(3-2*u);
c.el.style.setProperty('--travel',ease.toFixed(3));
c.el.style.setProperty('--outcome',Math.max(0,Math.min(1,(pos-9300)/700)).toFixed(3));
c.motions.forEach(({e,v:[x,y,dx,dy]})=>e.setAttribute('transform',`translate(${x+dx*ease} ${y+dy*ease})`));
c.bar.style.transform=`scaleX(${pos/duration})`;
});}
const play=document.getElementById('play');
const tr=(en,zh)=>lang==='zh'?zh:en;
function reflect(){
 play.textContent=playing?tr('Ⅱ Pause','Ⅱ 暂停'):tr('▶ Play','▶ 播放');
 play.setAttribute('aria-label',playing?tr('Pause animations','暂停动画'):tr('Play animations','播放动画'));
 play.setAttribute('aria-pressed',String(playing));
}
function translate(next){
 lang=next==='zh'?'zh':'en';document.documentElement.lang=lang==='zh'?'zh-CN':'en';
 document.querySelector('.overview-title').textContent=tr('Overview Illustration','场景示意');
 document.querySelector('.standalone-nav a').textContent=tr('← Piccolo Blog','← Piccolo 博客');
 document.getElementById('speed').setAttribute('aria-label',tr('Playback speed','播放速度'));
 const dataHeading=document.getElementById('data-heading');if(dataHeading)dataHeading.textContent=tr('Data Processing','数据处理');
 cards.forEach(({f,el})=>{
  const [title,options,description]=lang==='zh'?translations[f.id]:[f.title,f.options,f.description];
  el.setAttribute('aria-label',title);el.querySelector('h3').textContent=title;
  el.querySelector('svg').setAttribute('aria-label',description);
  el.querySelector('.options').setAttribute('aria-label',tr('Candidate actions','候选动作'));
  el.querySelectorAll('.option').forEach((option,i)=>option.firstElementChild.textContent=options[i]);
 });
 reflect();resize();
}
function running(){return playing&&parentVisible&&!document.hidden;}
function schedule(){if(running()&&animationFrame===null)animationFrame=requestAnimationFrame(tick);}
function updatePlayback(){
 last=performance.now();
 if(!running()&&animationFrame!==null){cancelAnimationFrame(animationFrame);animationFrame=null;}
 schedule();
}
function tick(now){
 animationFrame=null;if(!running())return;
 const delta=now-last;last=now;clock+=Math.min(delta,100)*speed;render();schedule();
}
play.onclick=()=>{playing=!playing;reflect();updatePlayback();};
document.getElementById('speed').onchange=e=>{speed=Number(e.target.value);};
document.addEventListener('visibilitychange',updatePlayback);
reducedMotion.addEventListener('change',event=>{if(event.matches){playing=false;reflect();updatePlayback();}});
window.addEventListener('message',event=>{
 if(event.source!==parent||event.origin!==location.origin||event.data?.type!=='piccolo-showcase-context')return;
 parentVisible=event.data.visible===true;
 if(['zh','en'].includes(event.data.lang)&&event.data.lang!==lang)translate(event.data.lang);
 updatePlayback();
});
function resize(){if(parent!==window)parent.postMessage({type:'piccolo-showcase-height',height:document.body.getBoundingClientRect().height},location.origin);}
new ResizeObserver(resize).observe(document.body);
translate(lang);render();updatePlayback();
window.__showcase={state:()=>({playing,speed,clock,lang,active:running(),cards:cards.map(c=>({id:c.f.id,phase:c.phase,cycles:c.cycles,answer:c.f.answer}))})};
})();
