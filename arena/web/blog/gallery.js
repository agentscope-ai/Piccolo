import {schemaQuestions, labelVariants, trainingRecord} from './schema-data.js';
export {mountEvolution} from './evolution.js';

const locale=window.JevI18n;
const tr=(en,zh)=>locale.t(en,zh);
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const node=(tag,cls='',text)=>{
 const n=document.createElement(tag);n.className=cls;
 if(text!==undefined)n.textContent=text;return n;
};
const button=(text,callback,selected)=>{
 const n=node('button','',text);n.type='button';n.onclick=callback;
 if(selected!==undefined)n.setAttribute('aria-pressed',String(selected));
 return n;
};
const demos=[
 {id:'mario',title:'Mario',kind:['Movement and timing','移动与时机'],caption:['Watch the ranking of movement actions change as the character approaches an obstacle.','观察角色接近障碍物时，不同移动动作的候选概率怎样变化。']},
 {id:'zenless-zone-zero',title:'Zenless Zone Zero',zhTitle:'绝区零',video:'./blog/assets/zenless-zone-zero.mp4',kind:['Combat footage · 1:35','战斗实录 · 1:35'],caption:['Watch the highlighted inputs alongside the fight as the character moves, attacks and dodges.','左侧按键随战斗高亮，可以对照角色的移动、攻击和闪避。']},
 {id:'black-myth-wukong',title:'Black Myth: Wukong',video:'https://decisionplayground.agentscope.io/blog/assets/black-myth-wukong.mp4',previewBase:'https://decisionplayground.agentscope.io/blog/assets/black-myth-wukong',kind:['Combat footage · 2:16','Combat footage · 2:16'],caption:['Watch a staff fight against a wolf-like opponent in the forest arena.','Watch a staff fight against a wolf-like opponent in the forest arena.']},
 {id:'hex',title:'Hex',kind:['Board strategy','对局策略'],caption:['Follow how a placement changes the path across the board, then compare the next set of legal moves.','观察一次落子怎样改变连通路径，再比较下一步的合法落点。']},
 {id:'sokoban',title:'Sokoban',kind:['Constrained planning','约束规划'],caption:['Compare the box–goal assignments. A nearby goal is useful only if the remaining boxes can still be moved.','比较箱子与目标的分配：目标近还不够，剩余箱子也要有继续移动的空间。']},
 {id:'2048',title:'2048',kind:['Sequential decisions','连续决策'],caption:['Watch which merges remain available after each move, and how that changes the ranking of the four directions.','观察每一步之后还剩哪些合并机会，以及四个方向的排序如何随之变化。']},
 {id:'jump',title:'Jump Jump',kind:['Timing a jump','跳跃时机'],caption:['Compare the proposed hold durations with the distance to the next platform.','对照下一块平台的距离，观察不同按压时长的候选排序。']},
 {id:'othello',title:'Othello',kind:['Board strategy','对局策略'],caption:['Follow a legal placement and the opponent’s reply to see how the position changes.','跟随一次合法落子与对手的回应，观察局势变化。']},
 {id:'snake',title:'Snake',kind:['Navigating space','空间选择'],caption:['Watch how the available space changes before the model chooses its next direction.','观察可用空间怎样变化，以及模型随后选择哪个方向。']},
 {id:'tetris',title:'Tetris',kind:['Piece placement','落点选择'],caption:['Compare rotations and landing columns, then inspect the gaps left by the chosen placement.','比较旋转角度与落点，再观察方块落下后留下的空隙。']},
 {id:'dots-boxes',title:'Dots & Boxes',kind:['Board strategy','对局策略'],caption:['Follow the choice of an edge and the boxes it leaves available on the board.','跟随每次选边，观察棋盘上留下了哪些可以围成的方格。']},
 {id:'qwenpaw-audit',anchor:'qwenpaw-showcase',title:'QwenPaw',kind:['Piccolo tool review','Piccolo 工具审核'],zhReplay:'qwenpaw-audit-zh',alt:['Qwen Plus requests the tools. Local Piccolo-4B-Q4_K_M approves the CSV reads and flags the report overwrite as destructive. QwenPaw asks the operator, who denies the write.','Qwen Plus 发起工具调用，本地 Piccolo-4B-Q4_K_M 判断能否自动执行。两次 CSV 读取直接通过。覆盖报告被标记为破坏性操作，QwenPaw 请求确认，操作者点选 Deny。']},
 {id:'data-judge',anchor:'datajev-showcase',title:'Data queries',kind:['Evidence judgments','证据充分性判断'],caption:['Piccolo-4B-Q4_K_M judges 24 full DataJevBench evidence cases. The queries are abbreviated on screen. Each percentage is the probability assigned to the displayed judgment.','Piccolo-4B-Q4_K_M 对 DataJevBench 的 24 条完整样本逐项判断。画面左侧是问题简写，右侧是判断及其候选概率。'],source:'./blog/assets/data-judge-cases.json'}
];
export function mountGallery(host,{gamesOnly=false,ids=null}={}){
 const featured=['mario','zenless-zone-zero','black-myth-wukong','qwenpaw-audit','data-judge','sokoban','hex'].map(id=>demos.findIndex(demo=>demo.id===id));
 // Keep every published game recording available in the article.
 const articleGames=['zenless-zone-zero','black-myth-wukong','mario','jump','sokoban','2048','tetris','hex','othello','dots-boxes','snake'];
 const order=ids?ids.map(id=>demos.findIndex(demo=>demo.id===id)):gamesOnly?articleGames.map(id=>demos.findIndex(demo=>demo.id===id))
  :[...featured,...demos.map((_game,i)=>i).filter(i=>!featured.includes(i))];
 let index=order[0],wanted=!reduced.matches,modalPlaying=false,previews=[],motionButton,modalImage,modalMotion,returnGame=demos[index].id;
 const dialog=node('dialog','game-dialog');dialog.id=host.id+'-dialog';
 dialog.setAttribute('aria-labelledby',dialog.id+'-title');
 document.body.append(dialog);
 function zoomIcon(shrink=false){
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d',shrink?'M3 9h6V3M21 9h-6V3M3 15h6v6M21 15h-6v6':'M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6');
  svg.append(path);return svg;
 }
 function replaySrc(game,playing){
  const id=locale.lang==='zh'&&game.zhReplay?game.zhReplay:game.id;
  return (game.previewBase || './blog/assets/'+id)+(playing?'.gif':'-poster.png');
 }
 function setImage(image,game,playing){
  const src=replaySrc(game,playing);
  if(image&&image.getAttribute('src')!==src)image.src=src;
 }
 function updateMotion(){
  for(const preview of previews)setImage(preview.image,demos[preview.index],wanted&&preview.visible&&!dialog.open&&!document.hidden);
  if(motionButton){
   motionButton.textContent=wanted?tr('Pause previews','暂停预览'):tr('Play previews','播放预览');
   motionButton.setAttribute('aria-pressed',String(wanted));
  }
  setImage(modalImage,demos[index],dialog.open&&modalPlaying&&!document.hidden);
  if(modalMotion){
   modalMotion.textContent=modalPlaying?tr('Pause replay','暂停回放'):tr('Play replay','播放回放');
   modalMotion.setAttribute('aria-pressed',String(modalPlaying));
  }
 }
 function updateExpanded(){
  host.querySelectorAll('[data-game]').forEach(item=>item.setAttribute('aria-expanded',String(dialog.open&&item.dataset.game===demos[index].id)));
 }
 function renderDialog(focusKey){
  const game=demos[index];
  const name=tr(game.title,game.zhTitle||game.title);
  const focused=focusKey||(dialog.contains(document.activeElement)?document.activeElement.dataset.dialogControl:null);
  const header=node('div','game-dialog-heading'),identity=node('div');
  identity.append(node('small','',tr(...game.kind)));
  const title=node('h3','',name);title.id=dialog.id+'-title';title.setAttribute('aria-live','polite');identity.append(title);
  const close=button('',()=>dialog.close());close.className='game-dialog-close';close.dataset.dialogControl='close';close.autofocus=true;
  close.setAttribute('aria-label',tr('Shrink '+name+' and return to the gallery','缩小 '+name+'，返回画廊'));
  close.title=tr('Shrink replay','缩小回放');close.append(zoomIcon(true));
  header.append(identity,close);
  const stage=node('div','game-dialog-screen');stage.setAttribute('aria-busy','true');
  const activeVideo=dialog.querySelector('video');
  const reuseVideo=game.video&&activeVideo?.getAttribute('src')===game.video&&!activeVideo.error;
  const resume=reuseVideo&&!activeVideo.paused;
  activeVideo?.pause();
  const recording=reuseVideo?activeVideo:node(game.video?'video':'img','game-recording');
  modalImage=game.video?null:recording;
  const ready=()=>stage.setAttribute('aria-busy','false');
  if(game.video){
   recording.controls=true;recording.playsInline=true;recording.preload='metadata';
   recording.poster=replaySrc(game,false);recording.setAttribute('aria-label',name);
   recording.onloadedmetadata=ready;
   if(!reuseVideo)recording.src=game.video;
   if(recording.readyState>=1)ready();
  }else{
   recording.width=892;recording.height=515;recording.alt=name+' · '+tr(...(game.alt||game.caption));
   recording.onload=ready;
  }
  recording.onerror=()=>{
   stage.setAttribute('aria-busy','false');
   stage.replaceChildren(node('p','media-error',tr('The recording could not be loaded.','这段素材暂时无法加载。')),button(tr('Retry','重试'),()=>renderDialog('play')));
  };
  stage.append(recording);
  dialog.replaceChildren(header,stage);
  if(resume)recording.play().catch(()=>{});
  if(game.caption){
   const caption=node('p','game-dialog-caption',tr(...game.caption));caption.id=dialog.id+'-caption';
   if(game.source){
    const source=node('a','figure-link',tr('Query IDs and judgments ↗','问题 ID 与判断记录 ↗'));
    source.href=game.source;source.target='_blank';source.rel='noopener';caption.append(' ',source);
   }
   dialog.append(caption);dialog.setAttribute('aria-describedby',caption.id);
  }else dialog.removeAttribute('aria-describedby');
  const controls=node('div','game-dialog-controls');
  modalMotion=null;
  const previous=button('←',()=>step(-1,'previous'));previous.dataset.dialogControl='previous';previous.setAttribute('aria-label',tr('Previous replay','上段回放'));
  const next=button('→',()=>step(1,'next'));next.dataset.dialogControl='next';next.setAttribute('aria-label',tr('Next replay','下段回放'));
  const original=node('a','game-original',game.video?tr('Open full video ↗','打开完整视频 ↗'):tr('Open original ↗','查看原图 ↗'));original.href=game.video||replaySrc(game,true);original.target='_blank';original.rel='noopener';original.dataset.dialogControl='original';
  controls.append(previous);
  if(!game.video){
   modalMotion=button('',()=>{modalPlaying=!modalPlaying;updateMotion();});modalMotion.dataset.dialogControl='play';controls.append(modalMotion);
  }
  controls.append(next,node('span','game-counter',String(order.indexOf(index)+1).padStart(2,'0')+' / '+String(order.length).padStart(2,'0')),original);
  dialog.append(controls);
  updateMotion();updateExpanded();
  if(focused)dialog.querySelector('[data-dialog-control="'+focused+'"]')?.focus({preventScroll:true});
 }
 function step(direction,focusKey){
  index=order[(order.indexOf(index)+direction+order.length)%order.length];renderDialog(focusKey);
 }
 function open(i){
  index=i;returnGame=demos[i].id;modalPlaying=true;
  renderDialog();dialog.showModal();updateMotion();updateExpanded();
 }
 function render(){
  observer.disconnect();previews=[];
  host.replaceChildren();host.className='game-gallery';host.classList.toggle('game-gallery-single',order.length===1);
  const header=node('div','game-selection-header'),copy=node('div');
  copy.append(node('h3','game-selection-title',gamesOnly?tr('Explore the game recordings','查看游戏回放'):tr('Explore the showcases','查看决策示例')),
   node('p','game-selection-label',tr('Open a recording to inspect the actions and judgments.','点击卡片，放大查看动作与判断过程。')));
  motionButton=button('',()=>{wanted=!wanted;updateMotion();});motionButton.className='game-motion';header.append(copy,motionButton);
  const grid=node('div','game-catalog');grid.setAttribute('role','group');grid.setAttribute('aria-label',tr('Demo recordings','决策示例回放'));
  order.forEach(i=>{
   const game=demos[i],item=button('',()=>open(i));item.dataset.game=game.id;item.id=game.anchor||game.id+'-showcase';
   const name=tr(game.title,game.zhTitle||game.title);
   item.setAttribute('aria-controls',dialog.id);item.setAttribute('aria-haspopup','dialog');
   item.setAttribute('aria-label',tr('Expand '+name+' replay','放大 '+name+' 回放'));
   const frame=node('span','game-preview');
   const preview=node('img');preview.src=replaySrc(game,false);preview.alt='';preview.width=892;preview.height=515;preview.loading='lazy';
   previews.push({image:preview,index:i,visible:false});
   const expand=node('span','game-expand');expand.setAttribute('aria-hidden','true');expand.append(zoomIcon());
   frame.append(preview,expand);
   const title=node('span','game-tile-title');title.append(node('strong','',name));
   item.append(frame,title,node('small','',tr(...game.kind)));grid.append(item);
  });
  host.append(header,grid);updateMotion();updateExpanded();
  previews.forEach(preview=>observer.observe(preview.image));
  if(dialog.open)renderDialog();
 }
 const observer=new IntersectionObserver(entries=>{
  for(const entry of entries){const preview=previews.find(item=>item.image===entry.target);if(preview)preview.visible=entry.isIntersecting;}
  updateMotion();
 },{threshold:.1});
 dialog.addEventListener('close',()=>{
  dialog.querySelector('video')?.pause();
  modalPlaying=false;updateMotion();updateExpanded();
  host.querySelector('[data-game="'+returnGame+'"]')?.focus({preventScroll:true});
 });
 dialog.addEventListener('click',event=>{
  const bounds=dialog.getBoundingClientRect();
  if(event.target===dialog&&(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom))dialog.close();
 });
 dialog.addEventListener('keydown',event=>{
  if(event.key!=='Tab')return;
  const controls=[...dialog.querySelectorAll('button:not([disabled]),a[href],video[controls]')];
  const first=controls[0],last=controls[controls.length-1];
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
 });
 const visibility=()=>{if(document.hidden)dialog.querySelector('video')?.pause();updateMotion();};
 const preference=()=>{if(reduced.matches){wanted=false;modalPlaying=false;}updateMotion();};
 document.addEventListener('visibilitychange',visibility);reduced.addEventListener('change',preference);
 window.addEventListener('pagehide',()=>{observer.disconnect();dialog.remove();document.removeEventListener('visibilitychange',visibility);reduced.removeEventListener('change',preference);},{once:true});
 render();return{render};
}

function jsonCode(value){
 const pre=node('pre'),code=node('code'),text=JSON.stringify(value,null,2);
 const pattern=/("(?:\\.|[^"\\])*")(?=\s*:)|("(?:\\.|[^"\\])*")|\b(true|false|null|-?\d+(?:\.\d+)?)\b/g;
 let start=0;
 for(const match of text.matchAll(pattern)){
  code.append(document.createTextNode(text.slice(start,match.index)));
  code.append(node('span',match[1]?'json-key':match[2]?'json-string':'json-number',match[0]));
  start=match.index+match[0].length;
 }
 code.append(document.createTextNode(text.slice(start)));pre.append(code);pre.tabIndex=0;return pre;
}
export function mountSchema(host){
 let type='choice',variant='hard';
 const labels={
  choice:['Route a ticket','工单分流'],
  score:['Assess severity','判断故障等级'],
  noul:['Check for a workaround','判断是否有替代方案']
 };
 function render(){
  host.replaceChildren();host.className='decision-record';
  const header=node('div','record-heading');
  header.append(node('h4','',tr('The same state, different judgments','同一状态，不同判断')),node('span','',tr('TRAINING EXAMPLE','训练样例')));
  const state=node('div','record-state');state.append(node('small','','state'),node('p','','PDF export fails; CSV export still works.'));
  const types=node('div','record-primitives');types.setAttribute('role','group');types.setAttribute('aria-label',tr('Decision primitive','决策原语'));
  Object.keys(schemaQuestions).forEach(key=>{
   const b=button(key,()=>{type=key;variant='hard';render();host.querySelector('.record-primitives [aria-pressed=true]').focus({preventScroll:true});},key===type);
   b.append(node('span','',tr(...labels[key])));types.append(b);
  });
  const variants=node('div','record-label-tabs');variants.setAttribute('role','group');variants.setAttribute('aria-label',tr('Supervision form','监督形式'));
  Object.keys(labelVariants[type]).forEach(key=>variants.append(button(key,()=>{variant=key;render();host.querySelector('.record-label-tabs [aria-pressed=true]').focus({preventScroll:true});},key===variant)));
  const example=trainingRecord(type,variant);
  const columns=node('div','record-columns'),question=node('div','record-question'),label=node('div','record-label');
  question.append(node('small','','questions.judgment'),jsonCode(schemaQuestions[type]));
  label.append(node('small','','labels.judgment'),variants,jsonCode(example.labels.judgment));
  columns.append(question,label);
  const summary=node('p','record-explanation',type==='noul'&&variant==='soft'
   ?tr('A single value stores P(yes). The complementary probability is P(no) = 1 - P(yes).','单个数值表示 P(yes)，其余概率为 P(no) = 1 - P(yes)。')
   :variant==='soft'
   ?tr('The soft label covers every candidate, including zero-probability candidates. Its probabilities sum to one.','soft 标签覆盖全部候选，包括概率为零的候选；各项概率和为一。')
   :tr('A hard label identifies a candidate, an ordered level, or a boolean value, according to the primitive.','hard 标签按题型保存候选 ID、有序档位或布尔值。'));
  const full=node('details','record-json');full.append(node('summary','',tr('Minimal JSON record','查看精简 JSON')));
  const pre=jsonCode({state:example.state,questions:example.questions,labels:example.labels});pre.className='schema-code';full.append(pre);
  const foot=node('div','record-foot');const link=node('a','figure-link',tr('Download label examples ↓','下载标签样例 ↓'));link.href='./blog/label-examples.json';link.download='piccolo-label-examples.json';
  foot.append(link);
  host.append(header,state,types,columns,summary,full,foot);
 }
 render();return{render};
}
export function mountHero(image){
 let visible=false,wanted=!reduced.matches;
 const toggle=button('',()=>{wanted=!wanted;render();});toggle.className='hero-motion';
 (image.closest('figure').querySelector('.hero-media-footer')||image.closest('figure')).append(toggle);
 function render(){
  const src='./blog/assets/mario'+(visible&&wanted&&!document.hidden?'.gif':'-poster.png');
  if(image.getAttribute('src')!==src)image.src=src;
  toggle.textContent=wanted?tr('Pause preview','暂停预览'):tr('Play preview','播放预览');
  toggle.setAttribute('aria-pressed',String(wanted));
 }
 const observer=new IntersectionObserver(entries=>{visible=entries.some(e=>e.isIntersecting);render();});observer.observe(image);
 const preference=()=>{if(reduced.matches)wanted=false;render();};
 document.addEventListener('visibilitychange',render);reduced.addEventListener('change',preference);locale.onChange(render);
 window.addEventListener('pagehide',()=>{observer.disconnect();document.removeEventListener('visibilitychange',render);reduced.removeEventListener('change',preference);},{once:true});
}
