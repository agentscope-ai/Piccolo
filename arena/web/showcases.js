let worldOutcome=null;
let showcaseMotionFrame=null;
let terraTool="mine",terraDir="right",terraJump=false;
let showcaseKinds=[],showcaseKind=null,showcaseSession=null,showcaseCase=null,showcaseCases=[],showcaseBusy=false,showcaseAuto=false;
const featuredPlayOrder=['snake_navigation','sokoban_puzzle','blackjack','chess','tetris_placement','uno'];
let selectedPlay=featuredPlayOrder[0],playTabVisible=true,autoTicket=0,autoMode='model',tetrisRot=0,tetrisCol=4,chargeStart=0,chargeFrame=0,terraCalls=0,lastSocialCanvasKind=null;
const playIcons={tic_tac_toe:'♯',connect_four:'⠿',othello_6x6:'◐',othello_8x8:'◒',gomoku_19x19:'✣',hex_7x7:'⬡',dots_and_boxes_3x3:'▦',terraria_survival:'⚒',mario_platformer:'♜',jump_jump:'↗',tetris_placement:'▥',snake_navigation:'∿',merge_2048:'◇',sokoban_puzzle:'▣',emotion_context:'☺',support_routing:'▤',robot_pick_cola:'⌁',racing_sprint:'⚑',chess:'♞'};
const compactNames={...JevPlayText.names,othello_6x6:'Othello 6×6',othello_8x8:'Othello 8×8',gomoku_19x19:'Gomoku',hex_7x7:'Hex',dots_and_boxes_3x3:'Dots & Boxes',terraria_survival:'Terraria',mario_platformer:'Mario',jump_jump:'Jump Jump',merge_2048:'2048',sokoban_puzzle:'Sokoban',racing_sprint:'Rally Sprint',chess:'Chess'};
const playTaglines={tic_tac_toe:'Connect three',connect_four:'Connect four',othello_6x6:'Compact strategy',othello_8x8:'Classic strategy',gomoku_19x19:'Five in a row',hex_7x7:'Connect opposite edges',dots_and_boxes_3x3:'Close boxes to score',jump_jump:'Time your jump',tetris_placement:'Falling blocks',snake_navigation:'Collect apples',merge_2048:'Merge tiles',sokoban_puzzle:'Push boxes to targets',doudizhu:'Three-player card strategy',texas_holdem:'Heads-up poker',property_tycoon:'Buy, build and trade',terraria_survival:'Explore and survive',mario_platformer:'Platform adventure',robot_pick_cola:'Pick and lift',emotion_context:'Understand emotion',support_routing:'Route requests',racing_sprint:'Real-time decisions',chess:'Checkmate the king'};
const emotionNames={joy:['☺','Joy'],sadness:['☂','Sadness'],anger:['ϟ','Anger'],fear:['◌','Fear'],surprise:['!','Surprise'],gratitude:['♡','Gratitude'],disgust:['≈','Disgust'],neutral:['―','Neutral'],mixed:['◐','Mixed emotions'],uncertain:['?','Uncertain']};
const routeNames={security:['◇','Account security'],billing:['¥','Billing and refunds'],technical:['⌘','Technical support'],delivery:['□','Delivery'],cancel:['↩','Cancellation'],clarify:['?','Clarification']};
function showcaseInputs(input){return input?field('STATE',input.state)+field('PROMPT',input.prompt)+(input.option?field('OPTION',input.option):''):''}
// Chess uses the native session renderer, not the archived OpenSpiel UI.
function legacyAgentShowcase(kind){return kind!=='chess'&&AgentGames.has(kind)}
// Registry metadata supplies the bridge; game-specific renderers remain optional.
function worldFrame(kind=showcaseKind?.kind){
 if(kind==='mario_platformer')return $('marioFrame');
 if(kind==='terraria_survival')return $('terrariaFrame');
 let frame=$('engineWorldFrame');
 if(!frame){frame=document.createElement('iframe');frame.id='engineWorldFrame';frame.title='Game world';frame.className='hidden';$('marioFrame').after(frame)}
 const spec=showcaseKinds.find(item=>item.kind===kind)?.engine;
 if(spec?.browser_page&&spec?.browser_bridge&&frame.dataset.kind!==kind){
  const page=spec.browser_page;
  if(typeof page!=='string'||!page.split('/').every(part=>/^[a-zA-Z0-9_-]+$/.test(part)))throw Error('Invalid registered browser page');
  frame.src='./playground/'+page+'.html';frame.dataset.kind=kind;
 }
 return frame;
}
function worldBridge(kind=showcaseKind?.kind){
 const name=showcaseKinds.find(item=>item.kind===kind)?.engine?.browser_bridge||({mario_platformer:'JevMario',terraria_survival:'JevTerramai'})[kind];
 const frame=kind==='mario_platformer'?$('marioFrame'):kind==='terraria_survival'?$('terrariaFrame'):$('engineWorldFrame');
 return frame&&(kind==='mario_platformer'||kind==='terraria_survival'||frame.dataset.kind===kind)?frame.contentWindow?.[name]:null;
}
function registryGeneric(g){return ['generic','selected','chess'].includes(showcaseKind?.engine?.renderer)&&showcaseKind.kind===g.kind}
let registryPollBusy=false;
function cancelRegistryPending(){
 const spec=showcaseKind?.engine,session=showcaseSession;
 if(spec?.renderer==='generic'&&spec.clock==='realtime'&&spec.backend==='native'&&session)
  api('engines/'+encodeURIComponent(spec.kind)+'/cancel',{session_id:session.session_id}).catch(error);
}
setInterval(async()=>{
 const spec=showcaseKind?.engine,session=showcaseSession;
 if(registryPollBusy||!playTabVisible||spec?.renderer!=='generic'||spec.clock!=='realtime'||spec.backend!=='native'||!session||session.world.outcome)return;
 registryPollBusy=true;
 try{const r=await api('engines/'+encodeURIComponent(spec.kind)+'/tick',{session_id:session.session_id});
  if(showcaseSession?.session_id===session.session_id){showcaseSession.world=r.world;showcaseSession.revision=r.revision;renderRegisteredState(r.world)}}
 catch(e){error(e)}finally{registryPollBusy=false}
},150);
function genericStateElement(){let node=$('enginePublicState');if(!node){node=document.createElement('pre');node.id='enginePublicState';$('showcaseCanvas').after(node)}return node}
function renderRegisteredState(g){
 if(g.kind==='chess'){window.JevChessUI.render();return;}
 $('showcaseCanvas').classList.add('hidden');const node=genericStateElement();
 if(showcaseKind?.engine?.renderer==='selected'&&window.JevSelectedGames?.render(g,showcaseSession.choices,a=>showcaseStep(a,false))){node.hidden=true;return;}
 window.JevSelectedGames?.hide();node.hidden=false;node.textContent=JSON.stringify(g,null,2);
}
function renderRegisteredActions(options){
 $('showcaseActions').replaceChildren();
 for(const [action,label] of Object.entries(options)){const b=document.createElement('button');b.dataset.action=action;b.textContent=label;b.onclick=()=>showcaseStep(action,false);$('showcaseActions').append(b)}
}
function renderRegisteredWorld(obs,controls=true){
 worldOutcome=obs.outcome||null;$('showcaseGoal').textContent=showcaseKind.engine.goal;$('sceneStats').replaceChildren();
 $('showcaseOutcome').className=worldOutcome?(worldOutcome==='win'?'win':'loss'):'hidden';$('showcaseOutcome').textContent=worldOutcome||'';
 if(controls){const kind=showcaseKind.kind;api('engines/'+encodeURIComponent(kind)+'/observe',{state:obs}).then(r=>{if(showcaseKind?.kind===kind){renderRegisteredActions(r.record.questions.decision.criteria);$('showcaseFields').innerHTML=showcaseInputs({state:r.record.state,prompt:r.record.questions.decision.instructions,option:r.record.questions.decision.criteria})}}).catch(error)}
}
function releaseWorld(){for(const item of showcaseKinds.filter(s=>s.mode==='world'))worldBridge(item.kind)?.release()}
function stopAuto(){window.JevChessUI?.stop();cancelRegistryPending();window.JevTetrisUI?.cancelPending();window.JevSnakeUI?.cancelPending();window.JevRacingUI?.cancelPending();showcaseAuto=false;autoTicket++;releaseWorld();$('showcaseAuto').textContent=JevPlayText.ui('▶ Autoplay');$('showcaseReference').textContent=JevPlayText.ui('Demo')}
function activatePlay(visible){playTabVisible=visible;if(!visible||selectedPlay!=='chess')window.JevChessUI?.hide();else if(showcaseSession)window.JevChessUI?.restore();if(!visible||selectedPlay!=='tetris_placement')window.JevTetrisUI?.deactivate();else window.JevTetrisUI?.activate();if(!visible||selectedPlay!=='snake_navigation')window.JevSnakeUI?.deactivate();else window.JevSnakeUI?.activate();if(!visible||selectedPlay!=='racing_sprint')window.JevRacingUI?.deactivate();else window.JevRacingUI?.activate();const textPlay=window.JevTextPlays?.activate(selectedPlay,visible)===true;const board=selectedPlay!=='chess'&&!!catalog?.games.some(g=>g.id===selectedPlay);$('boardPlay').classList.toggle('hidden',!board||textPlay);$('showcasesView').classList.toggle('hidden',board||textPlay);if(!visible)stopAuto();$('terrariaFrame').contentWindow?.JevTerramai?.activate(visible&&selectedPlay==='terraria_survival');$('marioFrame').contentWindow?.JevMario?.activate(visible&&selectedPlay==='mario_platformer');for(const item of showcaseKinds.filter(s=>s.mode==='world'&&!['terraria_survival','mario_platformer'].includes(s.kind)))worldBridge(item.kind)?.activate(visible&&selectedPlay===item.kind)}
function showBoardPlay(kind){if(showcaseBusy&&selectedPlay==='tetris_placement')window.JevTetrisUI?.cancelPending();if(showcaseBusy&&selectedPlay==='snake_navigation')window.JevSnakeUI?.cancelPending();if(showcaseBusy&&selectedPlay==='racing_sprint')window.JevRacingUI?.cancelPending();if(showcaseBusy)return;stopAuto();selectedPlay=kind;activatePlay(true);markPicker()}
function markPicker(){document.querySelectorAll('#gamePicker button').forEach(b=>{b.classList.toggle('active',b.dataset.kind===selectedPlay);b.setAttribute('aria-pressed',String(b.dataset.kind===selectedPlay))})}
let playFilter='new';
Object.assign(playIcons,{checkers:'◉',go:'●',xiangqi:'將',guess_the_number:'?',minesweeper:'✹',sudoku:'▦',uno:'▣'});
Object.assign(playTaglines,{checkers:'Checkers strategy',go:'9×9 territory',xiangqi:'Chinese chess',guess_the_number:'Higher or lower',minesweeper:'Reveal safe cells',sudoku:'Fill the grid',uno:'Match colors and numbers'});
Object.assign(playIcons,{liars_dice:'⚄',goofspiel:'♧',blackjack:'21',zha_jin_hua:'♠',pig_dice:'⚅'});
Object.assign(playTaglines,{liars_dice:'Hidden-dice strategy',goofspiel:'Bidding strategy',blackjack:'Probability strategy',zha_jin_hua:'Probability play',pig_dice:'Roll or bank'});
function renderPlayPicker(){if(!catalog)return;
 const metadata=new Map(showcaseKinds.map(s=>[s.kind,s]));
 const removed=new Set(['breakthrough','mancala','robot_pick_cola','tic_tac_toe','connect_four','jump_jump','iterated_rps']);
 const seen=new Set(),realtime=new Set(['terraria_survival','mario_platformer','racing_sprint','snake_navigation','tetris_placement',...showcaseKinds.filter(s=>s.engine?.clock==='realtime').map(s=>s.kind)]);
 const all=[...catalog.games,...showcaseKinds.map(x=>({id:x.kind,name:x.name})),...(window.JevTextPlays?.items||[])].filter(g=>{if(removed.has(g.id)||seen.has(g.id))return false;seen.add(g.id);return true});
 const featured=featuredPlayOrder.map(id=>all.find(g=>g.id===id)).filter(Boolean);
 const categories={new:featured,realtime:all.filter(g=>realtime.has(g.id)),board:all.filter(g=>g.id==='chess'||catalog.games.some(b=>b.id===g.id)||metadata.get(g.id)?.play_category==='board'),table:all.filter(g=>['doudizhu','texas_holdem','property_tycoon','liars_dice','goofspiel','blackjack','zha_jin_hua','pig_dice'].includes(g.id)||metadata.get(g.id)?.play_category==='table'),arcade:all.filter(g=>['jump_jump','merge_2048','sokoban_puzzle'].includes(g.id)||metadata.get(g.id)?.play_category==='arcade'),scene:all.filter(g=>['mbti_text','emotion_context','support_routing'].includes(g.id)),all};
 $('playFilters').innerHTML=JevPlayText.html(Object.entries({new:'Featured',realtime:'Realtime',board:'Board',table:'Table',arcade:'Arcade & puzzles',scene:'Simulation & text',all:'All'}).map(([k,n])=>'<button data-filter="'+k+'" class="'+(playFilter===k?'active':'')+'" aria-pressed="'+(playFilter===k)+'">'+n+'<small>'+categories[k].length+'</small></button>').join(''));
 const query=$('playSearch').value.trim().toLowerCase(),items=(query?all:categories[playFilter]).filter(g=>(g.name+' '+g.id+' '+(compactNames[g.id]||'')).toLowerCase().includes(query));
 $('gamePicker').dataset.filter=query?'search':playFilter;
 $('gamePicker').innerHTML=JevPlayText.html('<div class="picker-row">'+items.map(g=>{return '<button data-kind="'+g.id+'" aria-pressed="'+(selectedPlay===g.id)+'"><span class="game-symbol" aria-hidden="true">'+(playIcons[g.id]||'◈')+'</span><span class="game-copy"><strong>'+esc(compactNames[g.id]||g.name)+'</strong><small>'+esc(playTaglines[g.id]||'Play now')+'</small></span></button>'}).join('')+'</div>'+(items.length?'':'<p class="muted">No matching games.</p>'));
 $('playCount').textContent=JevPlayText.ui(all.length+' scenarios');
 $('playFilters').querySelectorAll('button').forEach(b=>b.onclick=()=>{playFilter=b.dataset.filter;$('playSearch').value='';renderPlayPicker()});
 $('gamePicker').querySelectorAll('button').forEach(b=>b.onclick=async()=>{if(showcaseBusy&&selectedPlay==='tetris_placement')window.JevTetrisUI?.cancelPending();if(showcaseBusy&&selectedPlay==='snake_navigation')window.JevSnakeUI?.cancelPending();if(showcaseBusy&&selectedPlay==='racing_sprint')window.JevRacingUI?.cancelPending();if(showcaseBusy||busy)return;b.blur();if(!window.JevTextPlays?.open(b.dataset.kind)){if(b.dataset.kind==='chess')await chooseShowcase('chess');else if(catalog.games.some(g=>g.id===b.dataset.kind))await startGame(b.dataset.kind);else await chooseShowcase(b.dataset.kind)}$('gamesView').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});window.dispatchEvent(new Event('blink:game-ready'))});markPicker();
}
$('playSearch').oninput=renderPlayPicker;
// Both catalogs load independently. Open the selected game once they are ready,
// and preserve it when returning from another page.
function ensurePlay(){
 if($('gamesView').classList.contains('hidden')||!catalog||busy||showcaseBusy)return;
 if(catalog.games.some(g=>g.id===selectedPlay)){
  if(!gameState)return startGame(selectedPlay);
  drawBoard();
 }else if(!showcaseKind&&showcaseKinds.some(g=>g.kind===selectedPlay))return chooseShowcase(selectedPlay);
}
window.addEventListener('catalog-ready',()=>{renderPlayPicker();ensurePlay()});
function showcaseControls(disabled){JevSeedUI.setBusy(disabled);['showcaseNew','showcaseModel','showcaseClassify','showcaseSample','showcaseReplay','showcaseBrowse','showcaseContext','showcaseTextInput','modelSelect','showcaseOpponent'].forEach(id=>$(id).disabled=disabled);$('showcaseModel').disabled=disabled||!modelReady;$('showcaseAuto').disabled=!modelReady||(disabled&&!showcaseAuto);$('showcaseClassify').disabled=disabled||!modelReady;document.querySelectorAll('#gamePicker button,#showcaseActions button,#showcaseActions input,#showcaseActions select').forEach(b=>b.disabled=disabled||b.dataset.invalid==='true'||!!(b.dataset.action&&showcaseSession&&!(b.dataset.action in showcaseSession.choices)));$('sceneBusy').classList.toggle('hidden',!disabled);$('agentGameStage').style.pointerEvents=disabled?'none':'auto';if(showcaseSession?.world.handoff){$('showcaseModel').disabled=true;$('showcaseAuto').disabled=true}$('terrariaFrame').style.pointerEvents=disabled?'none':'auto';$('marioFrame').style.pointerEvents=disabled?'none':'auto';if(!disabled&&showcaseKind?.mode==='world'&&worldOutcome){$('showcaseModel').disabled=true;$('showcaseAuto').disabled=true;document.querySelectorAll('#showcaseActions button').forEach(b=>b.disabled=true)}if(!disabled&&showcaseSession?.world.outcome){$('showcaseModel').disabled=true;document.querySelectorAll('#showcaseActions button').forEach(b=>b.disabled=true)}if(selectedPlay==='racing_sprint')window.JevRacingUI?.controls(disabled);if(selectedPlay==='snake_navigation')window.JevSnakeUI?.controls(disabled);if(selectedPlay==='tetris_placement')window.JevTetrisUI?.controls(disabled);if(selectedPlay==='chess')window.JevChessUI?.controls(disabled)}
async function worldReady(){worldFrame();for(let n=0;n<120;n++){const bridge=worldBridge();if(bridge)return bridge;await new Promise(r=>setTimeout(r,100))}throw Error('Game world failed to load. Refresh the page.')}
function renderWorld(obs){if(showcaseKind?.kind==='mario_platformer')renderMario(obs);else if(showcaseKind?.kind==='terraria_survival')renderTerra(obs);else renderRegisteredWorld(obs)}
async function terraReady(){for(let n=0;n<120;n++){const bridge=$('terrariaFrame').contentWindow?.JevTerramai;if(bridge)return bridge;await new Promise(r=>setTimeout(r,100))}throw Error('Terraria failed to load. Refresh the page.')}
function fitWorldFrame(frame){const doc=frame.contentDocument,wrap=doc?.querySelector('#tw-wrap,#wrap');if(!wrap||!frame.clientWidth)return;const style=getComputedStyle(doc.body);frame.style.height=Math.ceil(wrap.getBoundingClientRect().height+parseFloat(style.paddingTop)+parseFloat(style.paddingBottom)+2)+'px'}
for(const id of ['terrariaFrame','marioFrame']){const frame=$(id);const watch=()=>{const wrap=frame.contentDocument?.querySelector('#tw-wrap,#wrap');if(wrap){frame.worldResize?.disconnect();frame.worldResize=new ResizeObserver(()=>fitWorldFrame(frame));frame.worldResize.observe(wrap);fitWorldFrame(frame)}};frame.addEventListener('load',watch);watch()}
function worldActionName(action){const simple={left:'Move left',right:'Move right',jump_left:'Jump left',jump_right:'Jump right',jump:'Jump',wait:'Wait'};if(simple[action])return simple[action];const match=/^(jump_)?(move|mine|attack|place)_(left|right|up|down)$/.exec(action);return match?(match[1]?'Jump and ':'')+match[2]+' '+match[3]:action}
function clearPlayResult(){DecisionTiming.reset('showcase');DecisionTiming.reset('text');worldOutcome=null;$('showcaseResult').innerHTML='';$('showcaseFields').innerHTML='';$('showcaseHistory').innerHTML=JevPlayText.html('');$('lastDecision').textContent=JevPlayText.ui('Ready');$('showcaseOutcome').classList.add('hidden');$('decisionDetails').open=false}
async function chooseShowcase(kind){if(showcaseBusy&&selectedPlay==='tetris_placement')window.JevTetrisUI?.cancelPending();if(showcaseBusy&&selectedPlay==='snake_navigation')window.JevSnakeUI?.cancelPending();if(showcaseBusy&&selectedPlay==='racing_sprint')window.JevRacingUI?.cancelPending();if(showcaseBusy||busy)return;window.JevRacingUI?.deactivate();window.JevSnakeUI?.deactivate();window.JevTetrisUI?.deactivate();stopAuto();showcaseKind=showcaseKinds.find(s=>s.kind===kind);if(!showcaseKind)return;selectedPlay=kind;showcaseSession=null;showcaseCase=null;showcaseCases=[];showcaseBusy=true;activatePlay(true);markPicker();showcaseControls(true);clearError();clearPlayResult();
 try{$('showcasesView').dataset.kind=kind;$('showcaseName').textContent=JevPlayText.ui(JevPlayText.name(kind,showcaseKind.name));$('showcaseNote').textContent=JevPlayText.ui('');$('showcaseNote').hidden=true;$('showcaseMode').textContent=JevPlayText.ui(({doudizhu:'CARD TABLE',texas_holdem:'POKER TABLE',property_tycoon:'PROPERTY TOUR',mario_platformer:'PIXEL ADVENTURE',terraria_survival:'PIXEL SANDBOX',merge_2048:'NUMBER PUZZLE',sokoban_puzzle:'WAREHOUSE PUZZLE',racing_sprint:'REALTIME RACING',tetris_placement:'REALTIME TETRIS'})[kind]||(kind==='robot_pick_cola'?'ROBOTICS':showcaseKind.mode==='text'?'LANGUAGE':'PLAY'));
 $('showcaseSource').innerHTML=JevPlayText.html(showcaseKind.url?'<a target="_blank" rel="noopener" href="'+esc(showcaseKind.url)+'">Source ↗</a>':'');
 const text=showcaseKind.mode==='text',world=showcaseKind.mode==='world',agent=legacyAgentShowcase(kind);JevSeedUI.show(null,false,!text);$('opponentTools').classList.toggle('hidden',kind==='chess'||!showcaseKind.supports_opponent);$('agentRulesBox').classList.toggle('hidden',!agent);$('agentGameStage').classList.toggle('hidden',!agent);$('showcaseOpponent').value='human';$('showcaseGame').classList.toggle('hidden',text);$('showcaseText').classList.toggle('hidden',!text);$('terrariaFrame').classList.toggle('hidden',!world||kind!=='terraria_survival');$('marioFrame').classList.toggle('hidden',!world||kind!=='mario_platformer');$('showcaseCanvas').classList.toggle('hidden',world||agent);if($('enginePublicState'))$('enginePublicState').hidden=true;if($('engineWorldFrame'))$('engineWorldFrame').classList.add('hidden');if(world)worldFrame(kind).classList.remove('hidden');$('showcaseReference').classList.toggle('hidden',kind!=='robot_pick_cola');$('sampleTools').classList.toggle('hidden',showcaseKind.category_id==null);$('showcaseReplay').classList.toggle('hidden',text);$('showcaseDifficulty').textContent=JevPlayText.ui('');
 if(showcaseKind.category_id!=null){showcaseCases=await api('cases?category='+showcaseKind.category_id);$('showcaseSample').innerHTML=JevPlayText.html(showcaseCases.map((r,i)=>'<option value="'+r.seq+'">Sample '+String(i+1).padStart(2,'0')+' / '+showcaseCases.length+'</option>').join(''));await loadShowcaseSample(showcaseCases[0].seq,false)}
 if(world){const b=await worldReady();b.activate(true);fitWorldFrame(worldFrame(kind));renderWorld(b.reset(JevSeedUI.request().seed));JevSeedUI.show({seed:b.condition().seed})}else if(!text){showcaseSession=kind==='chess'?await JevChessUI.create(JevSeedUI.request().seed):await api('showcases/new',{kind,opponent:$('showcaseOpponent').value,...JevSeedUI.request()});JevSeedUI.show(showcaseSession.environment);tetrisRot=0;tetrisCol=4;renderShowcaseGame()}
 }catch(e){error(e)}finally{showcaseBusy=false;showcaseControls(false)}}
async function loadShowcaseSample(seq,replay=true){showcaseCase=await api('case/'+seq);const r=showcaseCase.record;$('showcaseSample').value=seq;$('showcaseDifficulty').textContent=JevPlayText.ui('');
 if(showcaseKind.mode==='text'){$('showcaseContext').value=r.state.context;$('showcaseTextInput').value=r.state.text;resetClassification();$('showcaseFields').innerHTML=showcaseInputs({state:r.state,prompt:r.questions.decision.instructions,option:r.questions.decision.criteria})}
 else if(replay){showcaseSession=await api('showcases/new',{kind:showcaseKind.kind,seq:+seq});JevSeedUI.show(showcaseSession.environment);tetrisRot=0;tetrisCol=4;clearPlayResult();renderShowcaseGame()}}
async function newShowcase(seq=null,mode='standard'){if(showcaseBusy&&selectedPlay==='tetris_placement')window.JevTetrisUI?.cancelPending();if(showcaseBusy&&selectedPlay==='snake_navigation')window.JevSnakeUI?.cancelPending();if(showcaseBusy&&selectedPlay==='racing_sprint')window.JevRacingUI?.cancelPending();if(showcaseBusy)return;window.JevRacingUI?.deactivate();window.JevSnakeUI?.deactivate();window.JevTetrisUI?.deactivate();stopAuto();showcaseBusy=true;showcaseControls(true);clearPlayResult();try{if(showcaseKind.mode==='world'){terraCalls=0;const bridge=await worldReady();renderWorld(bridge.reset(JevSeedUI.request(false,false,mode).seed));JevSeedUI.show({seed:bridge.condition().seed},false,true,mode)}else{showcaseSession=showcaseKind.kind==='chess'?await JevChessUI.create(JevSeedUI.request(false,false,mode).seed):await api('showcases/new',{kind:showcaseKind.kind,seq,opponent:$('showcaseOpponent').value,...JevSeedUI.request(false,seq!==null,mode)});JevSeedUI.show(showcaseSession.environment,false,true,mode);tetrisRot=0;tetrisCol=4;renderShowcaseGame()}}catch(e){error(e)}finally{showcaseBusy=false;showcaseControls(false)}}
function statMarkup(items){return items.map(([n,l])=>'<div><strong>'+esc(JevPlayText.text(n))+'</strong><span>'+esc(JevPlayText.text(l))+'</span></div>').join('')}
function renderTerra(obs,controls=true){renderTerraStatus(obs);terraDir=obs.player.aim||terraDir;$('showcaseGoal').textContent=JevPlayText.ui('Mine and upgrade, defeat the gate guardian, then enter the portal.');$('sceneStats').innerHTML=JevPlayText.html(statMarkup([[Math.round(obs.player.hp),'Health'],[obs.stats.ore,'Ore'],[obs.decisions,'Decisions']]));if(!controls)return;$('keyboardHint').textContent=JevPlayText.ui('Arrow keys move and aim. K mines, X attacks, C places blocks, Space jumps. The world keeps running during model responses.');$('showcaseNew').textContent=JevPlayText.ui('↻ New world');$('showcaseActions').innerHTML=JevPlayText.html('<div class="terra-tools">'+Object.entries({move:'Move',mine:'Mine',attack:'Attack',place:'Place'}).map(([k,v])=>'<button data-terra-tool="'+k+'" aria-pressed="'+(terraTool===k)+'">'+v+'</button>').join('')+'<label><input id="terraJump" type="checkbox" '+(terraJump?'checked':'')+'> Jump too</label></div><div class="dpad">'+Object.entries({up:'↑ Up',left:'← Left',down:'↓ Down',right:'Right →'}).map(([d,n])=>'<button data-terra-dir="'+d+'">'+n+'</button>').join('')+'</div><button id="terraAct">'+({move:'Move',mine:'Mine',attack:'Attack',place:'Place'}[terraTool])+' '+terraDir+'</button>');document.querySelectorAll('[data-terra-tool]').forEach(b=>b.onclick=()=>{terraTool=b.dataset.terraTool;renderTerra(obs)});document.querySelectorAll('[data-terra-dir]').forEach(b=>b.onclick=()=>{terraDir=b.dataset.terraDir;showcaseStep((terraJump?'jump_':'')+terraTool+'_'+terraDir,false)});$('terraJump').onchange=e=>terraJump=e.target.checked;$('terraAct').onclick=async()=>{terraDir=(await terraReady()).snapshot().player.aim||terraDir;showcaseStep((terraJump?'jump_':'')+terraTool+'_'+terraDir,false)};}
let terraRespawning=false;
function renderTerraStatus(obs){$('showcaseOutcome').className=obs.wins>0?'win':'hidden';if(obs.wins>0)$('showcaseOutcome').textContent=JevPlayText.ui(obs.episode_terminal?'Guardian defeated and gate reached. Episode complete; reset to play again.':'Portal reached. Keep your gear and explore the next world.');if(obs.player.respawning)$('lastDecision').textContent=JevPlayText.ui('Respawning…');else if(terraRespawning)$('lastDecision').textContent=JevPlayText.ui('Respawned. Keep exploring.');terraRespawning=obs.player.respawning}
function renderMario(obs,controls=true){
 worldOutcome=obs.outcome;$('showcaseGoal').textContent=JevPlayText.ui('Cross the gaps and reach the flag.');$('sceneStats').innerHTML=JevPlayText.html(statMarkup([[obs.progress+'%','Progress'],[obs.collected,'Coins'],[obs.decisions,'Decisions']]));
 $('keyboardHint').textContent=JevPlayText.ui('A / D or arrows move. W / Space jumps. The world keeps running while the model responds.');$('showcaseNew').textContent=JevPlayText.ui('↻ Restart');
 if(controls){$('showcaseActions').innerHTML=JevPlayText.html(Object.entries({left:'← Left',jump_left:'↖ Jump left',jump:'↑ Jump',jump_right:'Jump right ↗',right:'Right →',wait:'Wait'}).map(([a,n])=>'<button data-action="'+a+'">'+n+'</button>').join(''));bindActions()}
 $('showcaseOutcome').className=obs.outcome?(obs.outcome==='win'?'win':'loss'):'hidden';if(obs.outcome){$('showcaseOutcome').textContent=JevPlayText.ui(JevPlayText.event('mario_platformer',obs));stopAuto();showcaseControls(showcaseBusy)}
}
window.addEventListener('message',e=>{if(e.origin!==location.origin||!playTabVisible)return;if(e.source===$('marioFrame').contentWindow&&e.data?.type==='jev-mario-state'&&selectedPlay==='mario_platformer')renderMario(e.data.observation,false);else if(e.source===$('terrariaFrame').contentWindow&&e.data?.type==='jev-terraria-state'&&selectedPlay==='terraria_survival')renderTerra(e.data.observation,false)});
function renderShowcaseGame(){if(!showcaseSession)return;const g=showcaseSession.world;if(registryGeneric(g)&&!g.stats)g.stats=[[g.steps??0,'Moves']];if(window.JevTetrisUI?.isWorld(g)){window.JevTetrisUI.render();return;}if(window.JevSnakeUI?.isWorld(g)){window.JevSnakeUI.render();return;}$('showcaseGoal').textContent=JevPlayText.ui(JevPlayText.goal(g.kind,showcaseSession.goal));const socialStats=g.kind==='doudizhu'?[[g.hand.length,'Cards left'],[g.steps,'Turns']]:g.kind==='texas_holdem'||g.kind==='zha_jin_hua'?[[g.stacks[0],'Your chips'],[g.pot,'Pot']]:g.kind==='pig_dice'?[[g.scores[0]+' / '+g.scores[1],'Scores'],[g.turn_points,'Unbanked']]:g.kind==='property_tycoon'?[[g.round+'/20','Round'],[g.cash[0],'Your cash']]:g.kind==='merge_2048'?[[Math.max(...g.board.flat()),'Largest tile'],[g.score,'Score']]:g.kind==='sokoban_puzzle'?[[g.steps,'Moves'],[g.score+'/'+g.targets.length,'Boxes on target']]:null;$('sceneStats').innerHTML=JevPlayText.html(statMarkup(g.stats||socialStats||(g.kind==='robot_pick_cola'?[[g.steps,'Moves'],[g.holding?'Holding':'Ready','Target']]:[[g.steps,g.kind==='tetris_placement'?'Pieces':'Moves'],[g.kind==='tetris_placement'?g.lines:g.score,g.kind==='tetris_placement'?'Lines':'Score']])));
 $('showcaseOutcome').className=g.outcome?(g.outcome==='win'?'win':'loss'):'hidden';if(g.outcome)$('showcaseOutcome').innerHTML=JevPlayText.html('<strong>'+esc(g.outcome_label?JevPlayText.text(g.outcome_label):JevPlayText.event(g.kind,g))+'</strong><button id="sceneAgain">Play again ↻</button>');if($('sceneAgain'))$('sceneAgain').onclick=()=>newShowcase();$('showcaseNew').textContent=JevPlayText.ui(g.outcome?'↻ Play again':'↻ Restart');
 if(legacyAgentShowcase(g.kind)){$('lastDecision').textContent=JevPlayText.ui(JevPlayText.event(g.kind,g));$('showcaseHistory').innerHTML=JevPlayText.html(g.history.slice().reverse().map(line=>'<div>'+esc(JevPlayText.text(line))+'</div>').join(''))}renderControls(g);$('showcaseFields').innerHTML=showcaseInputs(showcaseSession.input);if(g.handoff){$('showcaseResult').innerHTML='';$('decisionDetails').open=false}drawShowcase();if(g.kind!==lastSocialCanvasKind&&['doudizhu','texas_holdem','property_tycoon','merge_2048','sokoban_puzzle'].includes(g.kind)&&window.innerWidth<=620){const shell=$('showcaseCanvas').parentElement;shell.scrollLeft=(shell.scrollWidth-shell.clientWidth)/2}lastSocialCanvasKind=g.kind;}
function drawShowcase(extra={}){if(showcaseSession?.world.kind!=='chess')window.JevChessUI?.hide();if(showcaseKind?.engine?.renderer!=='selected')window.JevSelectedGames?.hide();if(showcaseSession&&registryGeneric(showcaseSession.world)){renderRegisteredState(showcaseSession.world);return;}if(showcaseSession?.world.kind==='racing_sprint'){JevRacing.stream(showcaseSession.world);return;}if(showcaseSession&&legacyAgentShowcase(showcaseSession.world.kind)){AgentGames.render(showcaseSession.world,showcaseSession.choices);return}if(showcaseSession)PlayDraw.draw(showcaseMotionFrame?.world||showcaseSession.world,{rot:tetrisRot,col:tetrisCol,...(showcaseMotionFrame?.options||{}),...extra})}
function bindActions(){$('showcaseActions').querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{b.blur();showcaseStep(b.dataset.action,false)})}
function validTetris(){const opts=Object.keys(showcaseSession.choices),same=opts.filter(x=>+x.split(':')[0]===tetrisRot);if(!same.length&&opts.length){tetrisRot=+opts[0].split(':')[0];tetrisCol=+opts[0].split(':')[1]}else if(same.length)tetrisCol=+same.reduce((a,b)=>Math.abs(+a.split(':')[1]-tetrisCol)<=Math.abs(+b.split(':')[1]-tetrisCol)?a:b).split(':')[1]}
function renderControls(g){if(g.kind==='chess')return;if(showcaseKind?.engine?.renderer==='selected'){JevSelectedGames.controls(g,showcaseSession.choices,a=>showcaseStep(a,false));return;}if(registryGeneric(g)){renderRegisteredActions(showcaseSession.choices);return;}if(g.kind==='racing_sprint')return JevRacing.controls(g,showcaseSession.choices,$('showcaseActions'),(action)=>showcaseStep(action,false));if(legacyAgentShowcase(g.kind))return AgentGames.controls(g,showcaseSession.choices);const choices=showcaseSession.choices,el=$('showcaseActions');if(g.outcome){el.innerHTML=JevPlayText.html('');return}
 if(g.kind==='jump_jump'){const mid=g.holds[Math.floor(g.holds.length/2)];el.innerHTML=JevPlayText.html('<button id="chargeButton" class="charge-button">Hold to charge · Release to jump</button><div class="charge-range"><input id="holdTime" aria-label="Charge time" type="range" min="'+g.holds[0]+'" max="'+g.holds.at(-1)+'" step="20" value="'+mid+'"><output id="holdLabel">'+mid+' ms</output><button id="jumpCommit">Jump</button></div>');$('holdTime').oninput=()=>{$('holdLabel').textContent=JevPlayText.ui($('holdTime').value+' ms');drawShowcase({charging:($('holdTime').value-g.holds[0])/(g.holds.at(-1)-g.holds[0])})};$('jumpCommit').onclick=()=>showcaseStep($('holdTime').value,false);$('chargeButton').onpointerdown=e=>{e.preventDefault();if(showcaseBusy)return;$('chargeButton').setPointerCapture(e.pointerId);startCharge()};$('chargeButton').onpointerup=endCharge;$('chargeButton').onpointercancel=cancelCharge;$('keyboardHint').textContent=JevPlayText.ui('Hold Space or the button to charge, then release. Or set a duration and press Jump.')}
 else if(g.kind==='tetris_placement'){validTetris();el.innerHTML=JevPlayText.html('<div class="tetris-control"><button id="tetrisRotate">↻ Rotate</button><button id="tetrisLeft">←</button><input id="tetrisColumn" type="range" min="0" max="9" value="'+tetrisCol+'" aria-label="Drop column"><button id="tetrisRight">→</button><button id="tetrisDrop" class="drop">↓ Drop</button></div>');$('tetrisRotate').onclick=()=>{tetrisRot=(tetrisRot+1)%PlayDraw.rotations(g.piece).length;updateTetris()};$('tetrisColumn').oninput=e=>{tetrisCol=+e.target.value;updateTetris()};$('tetrisLeft').onclick=()=>{tetrisCol--;updateTetris()};$('tetrisRight').onclick=()=>{tetrisCol++;updateTetris()};$('tetrisDrop').onclick=()=>showcaseStep(tetrisRot+':'+tetrisCol,false);$('keyboardHint').textContent=JevPlayText.ui('← / → choose a column. ↑ rotates. Space drops. The outline previews the landing.')}
 else {const robot=g.kind==='robot_pick_cola',up=robot?'forward':'up',down=robot?'backward':'down',defs=[[up,robot?'↑ Forward':'↑'],['left',robot?'← Left':'←'],[down,robot?'↓ Back':'↓'],['right',robot?'Right →':'→']];el.innerHTML=JevPlayText.html('<div class="dpad">'+defs.map(([a,t])=>'<button data-action="'+a+'" '+(!(a in choices)?'disabled':'')+'>'+t+'</button>').join('')+'</div>'+(robot?'<div class="robot-extra">'+[['up','Lift'],['down','Lower'],['grasp','Grasp'],['open','Release']].map(([a,t])=>'<button data-action="'+a+'" '+(!(a in choices)?'disabled':'')+'>'+t+'</button>').join('')+'</div>':''));bindActions();$('keyboardHint').textContent=JevPlayText.ui(robot?'Arrows move. Q lifts, E lowers, Space grasps. Demo uses a rule planner.':g.kind==='merge_2048'?'Arrows or WASD slide tiles. Merge equal values and keep room to move.':g.kind==='sokoban_puzzle'?'Arrows or WASD move. Push boxes onto targets; avoid dead corners.':'Arrows or WASD move. Avoid walls, obstacles and your own body.')}
}
function updateTetris(){if(showcaseBusy)return;validTetris();$('tetrisColumn').value=tetrisCol;drawShowcase()}
function startCharge(){if(showcaseBusy||chargeStart)return;chargeStart=performance.now();const tick=()=>{if(!chargeStart)return;const g=showcaseSession.world,ms=Math.min(g.holds.at(-1),Math.max(g.holds[0],performance.now()-chargeStart)),n=g.holds.reduce((a,b)=>Math.abs(a-ms)<=Math.abs(b-ms)?a:b);$('holdTime').value=n;$('holdLabel').textContent=JevPlayText.ui(n+' ms');drawShowcase({charging:ms/g.holds.at(-1)});chargeFrame=requestAnimationFrame(tick)};tick()}
function cancelCharge(){chargeStart=0;cancelAnimationFrame(chargeFrame);if(showcaseSession)drawShowcase()}
function endCharge(){if(!chargeStart)return;const action=$('holdTime').value;cancelCharge();showcaseStep(action,false)}
// Replay only physical states returned by the authoritative engine. A push
// intent still has one model probability and one API revision, however long its
// deterministic walk to the chosen standing square is.
function sokobanMotionFrames(before,after){
 const trace=after.execution_trace,frames=trace?.frames;
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 const boxKey=boxes=>boxes.map(p=>p.join(',')).sort().join('|');
 const matches=(a,b)=>same(a.player,b.player)&&boxKey(a.boxes)===boxKey(b.boxes)&&a.steps===b.steps;
 const invalid=()=>{throw Error('Incomplete Sokoban movement receipt. Start a new game.')};
 if(trace?.version!==1||!Array.isArray(frames)||!frames.length||!matches(frames[0],before)||!matches(frames.at(-1),after))invalid();
 if(frames.length-1!==after.execution?.mechanical_moves)invalid();
 const walls=new Set(before.walls.map(p=>p.join(','))),dirs={up:[0,-1],right:[1,0],down:[0,1],left:[-1,0]};
 for(let i=1;i<frames.length;i++){
  const prev=frames[i-1],next=frames[i],delta=dirs[next.action];
  if(!delta||next.steps!==prev.steps+1||next.steps>80||next.player.some((n,j)=>n!==prev.player[j]+delta[j]))invalid();
  const inside=p=>Number.isInteger(p[0])&&Number.isInteger(p[1])&&p[0]>=0&&p[0]<before.width&&p[1]>=0&&p[1]<before.height&&!walls.has(p.join(','));
  if(!inside(next.player)||next.boxes.length!==prev.boxes.length||next.boxes.some(p=>!inside(p)))invalid();
  const occupied=new Set(prev.boxes.map(p=>p.join(','))),pushed=occupied.has(next.player.join(','));
  if(pushed){const target=next.player.map((n,j)=>n+delta[j]);if(!inside(target)||occupied.has(target.join(',')))invalid();occupied.delete(next.player.join(','));occupied.add(target.join(','))}
  if([...occupied].sort().join('|')!==boxKey(next.boxes))invalid();
 }
 return frames;
}
async function animateSokoban(before,after){
 const frames=sokobanMotionFrames(before,after),duration=120;
 try{
  for(let i=1;i<frames.length;i++){
   const previous={...before,...frames[i-1]},current={...after,...frames[i],outcome:null};
   await new Promise(resolve=>{
    let start=null;
    const frame=now=>{if(start===null)start=now;const progress=Math.min(1,(now-start)/duration);
     showcaseMotionFrame={world:current,options:{before:previous,progress}};
     drawShowcase();
     if(progress<1)requestAnimationFrame(frame);else resolve();
    };
    requestAnimationFrame(frame);
   });
  }
 }finally{showcaseMotionFrame=null}
}
function animateStep(before,after,action){if(registryGeneric(after))return Promise.resolve();if(window.JevCardTable?.supports(after.kind))return window.JevCardTable.animate(before,after);if(after.kind==='sokoban_puzzle')return animateSokoban(before,after);if(legacyAgentShowcase(after.kind))return Promise.resolve();if(['tetris_placement','merge_2048'].includes(after.kind))return window.JevSceneTransition.animate(before,after,action);const duration=after.kind==='jump_jump'?620:after.kind==='robot_pick_cola'?520:260;return new Promise(resolve=>{const start=performance.now();function frame(now){const p=Math.min(1,(now-start)/duration);PlayDraw.draw(after,{before,progress:p,action});if(p<1)requestAnimationFrame(frame);else resolve()}requestAnimationFrame(frame)})}
function decisionLog(controller,action,actorLabel=null,result=null){const who=(actorLabel?JevPlayText.text(actorLabel):null)||(controller==='reference'?'Planner':controller==='model'?'Model':'You');action=JevPlayText.text(action);$('lastDecision').textContent=JevPlayText.ui(action);const line=document.createElement('div');line.innerHTML=JevPlayText.html('<b>'+who+'</b>'+esc(action));const at=DecisionTiming.record('showcase',result);DecisionTiming.history(line,at);$('showcaseHistory').prepend(line)}
// Execution receipts are UI audit metadata; the model input remains the sent snapshot.
const worldDecisionReceipts=[];
function recordWorldDecision(receipt){
 worldDecisionReceipts.push(receipt);if(worldDecisionReceipts.length>200)worldDecisionReceipts.shift();
 const messages={episode_changed:'Game restarted',terminal:'Game ended',death_or_respawn:'Player respawned; observing again',world_changed:'World changed',cancelled:'Cancelled',shield_changed:'Shield changed; observing again',jump_state_changed:'Jump state changed; observing again',subgoal_changed:'Intent changed; observing again',visible_danger_changed:'Visible danger changed; observing again',enemy_direction_changed:'Nearby enemy changed direction; observing again',new_nearby_enemy:'New approaching enemy; observing again'};
 if(receipt.status==='discarded')$('lastDecision').textContent=JevPlayText.ui('Response skipped · '+(messages[receipt.reason]||receipt.reason));
 else if(receipt.status==='executed')$('lastDecision').textContent=JevPlayText.ui(worldActionName(receipt.action)+' · World advanced '+receipt.inference_frames+' frames');
 if(receipt.status!=='cancelled')$('showcaseFields').insertAdjacentHTML('beforeend',field('Execution details',receipt));
}
async function showcaseStep(action,model,reference=false){
 if(window.JevChessUI?.active())return JevChessUI.step(action,model,reference);
 if(window.JevTetrisUI?.active())return JevTetrisUI.step(action,model,reference);
 if(window.JevSnakeUI?.active())return JevSnakeUI.step(action,model,reference);
 if(showcaseSession?.world.kind==='racing_sprint'&&selectedPlay==='racing_sprint')return JevRacingUI.step(action,model,reference);
 if(showcaseBusy)return false;
 showcaseBusy=true;showcaseControls(true);clearError();let bridge=null;const requestTicket=autoTicket;
 try{
  if(showcaseKind.mode==='world'){
   const requestKind=showcaseKind.kind;bridge=await worldReady();if(worldOutcome)return false;
   const condition=bridge.condition();let observed=null,r=null,started=performance.now();
   if(model){
    observed=bridge.prepare({clock:'realtime'});
    $('lastDecision').textContent=JevPlayText.ui('Model thinking · World running');
    r=await api('showcases/world',{state:observed,kind:requestKind});action=r.result.value;
   }
   const current=bridge.snapshot(),nowCondition=bridge.condition();
   const sameEpisode=condition.generation===nowCondition.generation;
   const cancelled=!playTabVisible||selectedPlay!==requestKind||requestTicket!==autoTicket;
   // The bridge shares this public-observation check with RL and exact replay.
   if(model&&typeof bridge.checkActionArrival!=='function')throw Error('World arrival contract unavailable');
   const arrivalCheck=observed&&sameEpisode&&!cancelled?bridge.checkActionArrival(action,observed,current):null;
   const reason=!sameEpisode?'episode_changed':cancelled?'cancelled':arrivalCheck?.reason||(current.outcome?'terminal':null);
   const receipt={kind:requestKind,clock_contract:'realtime-v1',arrival_check:arrivalCheck,status:reason?'discarded':'executing',reason,
    action,observation_frame:observed?.frame??current.frame,execution_frame:current.frame,
    inference_frames:observed?current.frame-observed.frame:0,latency_ms:Math.round(performance.now()-started),
    generation:condition.generation,model_decision:!!model,rule_takeover_actions:0};
   // A response from another episode or a cancelled request must not replace the new UI.
   if(r&&sameEpisode&&!cancelled){$('showcaseResult').innerHTML=resultHtml(r.result);$('showcaseFields').innerHTML=showcaseInputs(r.input)}
   if(reason){
    if(sameEpisode&&!cancelled){
     const feedback=arrivalCheck&&!arrivalCheck.valid?bridge.rejectActionArrival(action,observed,current,arrivalCheck):current;
     receipt.action_applied=false;receipt.after_frame=feedback.frame;receipt.automatic_action=null;
     renderWorld(feedback);DecisionTiming.record('showcase',r?.result);recordWorldDecision(receipt);
    }else{worldDecisionReceipts.push(receipt);if(worldDecisionReceipts.length>200)worldDecisionReceipts.shift()}
    return sameEpisode&&!cancelled&&arrivalCheck?.requires_new_observation?'reobserve':false;
   }
   if(!model)bridge.release();
   const obs=await bridge.act(action);
   receipt.status='executed';receipt.action_applied=true;receipt.after_frame=obs.frame;receipt.after_outcome=obs.outcome??null;
   if(bridge.condition().generation!==condition.generation){receipt.status='interrupted';receipt.reason='episode_changed';worldDecisionReceipts.push(receipt);return false}
   if(!playTabVisible||selectedPlay!==requestKind||requestTicket!==autoTicket){worldDecisionReceipts.push(receipt);return false}
   terraCalls++;renderWorld(obs);decisionLog(model?'model':'human',worldActionName(action),null,r?.result);recordWorldDecision(receipt);return true;
  }
 if(!showcaseSession||showcaseSession.world.outcome)return false;const before=structuredClone(showcaseSession.world);
 const card_ids=!model&&!reference&&before.kind==='doudizhu'&&before.hand_card_ids&&cardSelection.length&&cardSelection.map(i=>before.hand[i]).sort((a,b)=>a-b).join(',')===action?cardSelection.map(i=>before.hand_card_ids[i]):undefined;
 const r=await api('showcases/step',{session_id:showcaseSession.session_id,revision:showcaseSession.revision,action,model,reference,card_ids});$('sceneBusy').classList.add('hidden');showcaseSession=r;await animateStep(before,r.world,r.action);tetrisRot=0;tetrisCol=4;renderShowcaseGame();if(!legacyAgentShowcase(r.world.kind))decisionLog(r.controller,JevPlayText.action(r.world.kind,r.action,r.action_name),r.actor_label,r.result);else DecisionTiming.record('showcase',r.result||r.decision_timing);if(r.result)$('showcaseResult').innerHTML=resultHtml(r.result);else if(r.controller==='reference')$('showcaseResult').innerHTML='<div class="notice">Planner chose '+esc(r.action_name)+'; no model call.</div>';else if(r.forced)$('showcaseResult').innerHTML='<div class="notice">Only one legal action; applied automatically.</div>';if(r.previous_input)$('showcaseFields').innerHTML=showcaseInputs(r.previous_input);return true;
 }catch(e){error(e);stopAuto();return false}finally{bridge?.release();showcaseBusy=false;showcaseControls(false)}}
async function autoplay(reference=false){if(window.JevChessUI?.active())return JevChessUI.autoplay();if(showcaseAuto){stopAuto();return}if(showcaseBusy)return;showcaseAuto=true;const ticket=++autoTicket;autoMode=reference?'reference':'model';$(reference?'showcaseReference':'showcaseAuto').textContent=JevPlayText.ui('■ Stop '+(reference?'demo':'autoplay'));const limit=showcaseKind?.engine?.limit||(['snake_navigation','racing_sprint','tetris_placement'].includes(selectedPlay)?(showcaseSession?.world.max_model_decisions||(selectedPlay==='snake_navigation'?240:320)):selectedPlay==='terraria_survival'?300:selectedPlay==='mario_platformer'?160:120);try{for(let i=0;i<limit&&showcaseAuto&&ticket===autoTicket;i++){if(showcaseSession?.world.outcome||worldOutcome)break;const progress=await showcaseStep(null,!reference,reference);if(!progress)break;if(progress!=='reobserve')await new Promise(r=>setTimeout(r,reference?150:200))}}finally{if(ticket===autoTicket)stopAuto()}}
async function modelShowcaseStep(){
 // A discarded reply consumes a request but no engine action. Observe immediately,
 // retaining the existing request budget and cancellation/generation checks.
 const ticket=autoTicket,kind=selectedPlay,limit=showcaseKind?.engine?.limit||160;
 for(let i=0;i<limit&&ticket===autoTicket&&kind===selectedPlay&&playTabVisible;i++){
  const progress=await showcaseStep(null,true);if(progress!=='reobserve')return progress;
 }
 return false;
}
function renderTextChrome(){const routes=showcaseKind.kind==='support_routing';$('messageAvatar').textContent=JevPlayText.ui(routes?'▤':'☺');$('messageTitle').textContent=JevPlayText.ui(routes?'Customer message':'Text');$('messageSubtitle').textContent=JevPlayText.ui(routes?'Choose the right support queue':'Identify emotion in context');$('messageInputLabel').textContent=JevPlayText.ui(routes?'Request':'Text to analyze');$('classificationTitle').textContent=JevPlayText.ui(routes?'Support queue':'Emotions');$('showcaseClassify').textContent=JevPlayText.ui(routes?'Route request ↗':'Identify emotion ↗');}
function resetClassification(){classificationResultCache=null;DecisionTiming.reset('text');$('textDecision').textContent=JevPlayText.ui('Ready');renderTextChrome();const routes=showcaseKind.kind==='support_routing';$('classificationResult').innerHTML=JevPlayText.html(routes?'Which team should handle this?':'What emotion does this text express?');$('showcaseResult').innerHTML='';renderClassChoices()}
let classificationResultCache=null;
function renderClassChoices(result=null){classificationResultCache=result;const mapping=showcaseKind.kind==='support_routing'?routeNames:emotionNames,partial=result?.probability_coverage?.complete===false,probs=new Map(result?.distribution.map(x=>[x.value,partial?x.raw_token_probability:x.probability])||[]);$('classificationChoices').innerHTML=JevPlayText.html(Object.entries(mapping).map(([k,[icon,label]])=>'<div class="classification-choice '+(result?.value===k?'selected':'')+'"><strong><span class="mood-icon">'+icon+'</span>'+label+'</strong><b>'+(Number.isFinite(probs.get(k))?(probs.get(k)*100).toFixed(1)+'%':result?'Unavailable':'')+'</b></div>').join(''));if(result){const winner=mapping[result.value],p=probs.get(result.value);$('classificationResult').innerHTML=JevPlayText.html(esc(winner?winner[1]:result.value)+'<small>Model choice · '+(partial?'Observed token probability ':'Candidate probability ')+(Number.isFinite(p)?(p*100).toFixed(1)+'%':'Unavailable')+'</small>')}}
$('showcaseClassify').onclick=async()=>{if(showcaseBusy||!showcaseCase)return;showcaseBusy=true;showcaseControls(true);const label=$('showcaseClassify').textContent;$('showcaseClassify').textContent=JevPlayText.ui('Analyzing…');clearError();try{const r=await api('showcases/text',{seq:showcaseCase.seq,text:$('showcaseTextInput').value,context:$('showcaseContext').value});renderClassChoices(r.result);const choice=(showcaseKind.kind==='support_routing'?routeNames:emotionNames)[r.result.value];$('textDecision').textContent=JevPlayText.ui(choice?choice[1]:String(r.result.value));DecisionTiming.record('text',r.result);$('showcaseResult').innerHTML=resultHtml(r.result);$('showcaseFields').innerHTML=showcaseInputs(r.input)}catch(e){error(e)}finally{showcaseBusy=false;showcaseControls(false);$('showcaseClassify').textContent=JevPlayText.ui(label)}};
$('showcaseContext').oninput=$('showcaseTextInput').oninput=()=>resetClassification();
$('showcaseOpponent').onchange=()=>newShowcase();$('showcaseNew').onclick=()=>newShowcase();$('showcaseReplay').onclick=()=>newShowcase(+$('showcaseSample').value);$('showcaseModel').onclick=()=>modelShowcaseStep();$('showcaseAuto').onclick=()=>autoplay();$('showcaseReference').onclick=()=>autoplay(true);
$('showcaseSample').onchange=async e=>{if(showcaseBusy)return;stopAuto();showcaseBusy=true;showcaseControls(true);clearError();try{await loadShowcaseSample(+e.target.value)}catch(e){error(e)}finally{showcaseBusy=false;showcaseControls(false)}};
$('showcaseBrowse').onclick=()=>{tab('cases');$('sourceFilter').value=showcaseKind.source||'cues_showcase_synthetic_v1';$('search').value='';$('kindFilter').value='all';filterCategories();selectCategory(showcaseKind.category_id)};
$('showcaseCanvas').onclick=e=>{if(window.JevTetrisUI?.active())return;if(showcaseBusy||selectedPlay!=='tetris_placement'||showcaseSession?.world.outcome)return;const box=e.currentTarget.getBoundingClientRect(),x=(e.clientX-box.left)*900/box.width;tetrisCol=Math.floor((x-210)/32);updateTetris()};
document.addEventListener('keydown',e=>{if(window.JevTetrisUI?.active()||window.JevSnakeUI?.active())return;if(!playTabVisible||showcaseBusy||showcaseKind?.kind!==selectedPlay||showcaseKind?.mode!=='game'||showcaseSession?.world.outcome||/INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName)||e.ctrlKey||e.altKey||e.metaKey)return;const k=e.key.toLowerCase();if(selectedPlay==='jump_jump'&&k===' '){e.preventDefault();if(!e.repeat)startCharge();return}if(e.repeat)return;if(selectedPlay==='tetris_placement'){if(k==='arrowleft'){tetrisCol--;updateTetris()}else if(k==='arrowright'){tetrisCol++;updateTetris()}else if(k==='arrowup')$('tetrisRotate').click();else if(k===' ')$('tetrisDrop').click();else return;e.preventDefault();return}const action=selectedPlay==='robot_pick_cola'?({arrowup:'forward',arrowdown:'backward',arrowleft:'left',arrowright:'right',q:'up',e:'down',' ':'grasp'})[k]:({arrowup:'up',w:'up',arrowdown:'down',s:'down',arrowleft:'left',a:'left',arrowright:'right',d:'right'})[k];if(action){e.preventDefault();if(action in showcaseSession.choices)showcaseStep(action,false)}});
document.addEventListener('keyup',e=>{if(e.key===' '&&chargeStart){e.preventDefault();endCharge()}});window.addEventListener('blur',cancelCharge);
async function initShowcases(){try{showcaseKinds=await api('showcases');showcaseKinds.forEach(s=>names[s.kind]=JevPlayText.name(s.kind,s.name));renderPlayPicker();ensurePlay()}catch(e){error(e)}}initShowcases();

// The card/property controls share the existing single-step and auto-play flow.
const baseRenderControls=renderControls;
renderControls=function(g){if(!['doudizhu','texas_holdem','property_tycoon','zha_jin_hua','pig_dice'].includes(g.kind))return baseRenderControls(g);const el=$('showcaseActions');$('keyboardHint').textContent=JevPlayText.ui(g.kind==='doudizhu'?'Select cards, then confirm.':g.kind==='texas_holdem'?'Opponent cards reveal at showdown.':g.kind==='zha_jin_hua'?'Peeking doubles your bets. Opponent cards stay hidden until showdown.':g.kind==='pig_dice'?'A roll of 1 loses the unbanked points. Bank to end your turn.':'Roll, then buy or upgrade.');
 if(g.kind==='doudizhu'){
  window.cardSelection=[];
  el.innerHTML=JevPlayText.html('<div class="social-actions social-actions--cards"><div class="social-actions__intro"><strong>Your cards</strong><span id="cardSelectionStatus" aria-live="polite">Select a legal combination</span></div><div class="social-actions__buttons"><button id="playCards" class="social-primary" disabled>Play cards ↗</button><button data-action="pass" class="social-secondary" '+('pass' in showcaseSession.choices?'':'disabled')+'>Pass</button></div><label class="social-actions__picker"><span>Quick selection</span><select id="legalCardCombo" aria-label="Choose a legal combination"><option value="">Choose a combination…</option>'+Object.entries(showcaseSession.choices).filter(([key])=>key!=='pass').map(([key,value])=>'<option value="'+esc(key)+'">'+esc(JevPlayText.action(g.kind,key,value))+'</option>').join('')+'</select></label></div>');
  window.updateCardAction=()=>{const action=cardSelection.map(i=>g.hand[i]).sort((a,b)=>a-b).join(','),valid=action in showcaseSession.choices;$('playCards').disabled=showcaseBusy||!valid;$('cardSelectionStatus').textContent=JevPlayText.ui(!cardSelection.length?'Select a legal combination':valid?'Selected '+cardSelection.length+' cards · Ready':'Selected '+cardSelection.length+' cards · Invalid combination');$('playCards').onclick=()=>{if(valid)showcaseStep(action,false)}};
  $('legalCardCombo').onchange=e=>{if(!e.target.value)return;let rest=e.target.value.split(',').map(Number);window.cardSelection=[];g.hand.forEach((value,i)=>{const at=rest.indexOf(value);if(at>=0){cardSelection.push(i);rest.splice(at,1)}});drawShowcase();updateCardAction()};
 }else{
  const title=g.kind==='texas_holdem'||g.kind==='zha_jin_hua'?'Your move':g.kind==='pig_dice'?'Risk or bank':'Your move';
  const buttons=Object.entries(showcaseSession.choices).map(([action,value])=>'<button data-action="'+action+'" class="social-'+(action==='fold'||action==='skip'||action==='next'?'secondary':action==='raise'?'gold':'primary')+'">'+esc(JevPlayText.action(g.kind,action,value))+'</button>').join('');
  el.innerHTML=JevPlayText.html('<div class="social-actions social-actions--'+(['texas_holdem','zha_jin_hua'].includes(g.kind)?'poker':'property')+'"><div class="social-actions__intro"><strong>'+title+'</strong><span>'+esc(JevPlayText.event(g.kind,g)||'Choose an action')+'</span></div><div class="social-actions__buttons">'+buttons+'</div></div>');
 }
 bindActions()};

// Locale changes redraw the current view; they never create a session or execute a move.
function redrawPlayLanguage(){
 renderPlayPicker();
 const oldDecision=$('lastDecision').textContent;
 const selectedCards=Array.isArray(window.cardSelection)?window.cardSelection.slice():[];
 const selectedBid=$('showcaseActions').querySelector('[data-bid][aria-pressed="true"]')?.dataset.bid;
 const chosenCombo=$('legalCardCombo')?.value,hold=$('holdTime')?.value;
 if(showcaseKind){
  $('showcaseName').textContent=JevPlayText.name(showcaseKind.kind,showcaseKind.name);
  $('showcaseMode').textContent=JevPlayText.ui(({doudizhu:'CARD TABLE',texas_holdem:'POKER TABLE',property_tycoon:'PROPERTY TOUR',mario_platformer:'PIXEL ADVENTURE',terraria_survival:'PIXEL SANDBOX',merge_2048:'NUMBER PUZZLE',sokoban_puzzle:'WAREHOUSE PUZZLE',racing_sprint:'REALTIME RACING',tetris_placement:'REALTIME TETRIS'})[showcaseKind.kind]||(showcaseKind.mode==='text'?'LANGUAGE':'PLAY'));
  if(showcaseKind.url)$('showcaseSource').innerHTML=JevPlayText.html('<a target="_blank" rel="noopener" href="'+esc(showcaseKind.url)+'">Source ↗</a>');
  [...$('showcaseSample').options].forEach((option,i)=>option.textContent=JevPlayText.ui('Sample '+String(i+1).padStart(2,'0')+' / '+showcaseCases.length));
  if(showcaseKind.mode==='text'){
   renderTextChrome();renderClassChoices(classificationResultCache);
   if(classificationResultCache){const mapping=showcaseKind.kind==='support_routing'?routeNames:emotionNames;$('textDecision').textContent=JevPlayText.ui(mapping[classificationResultCache.value]?.[1]||classificationResultCache.value);}
   else{$('textDecision').textContent=JevPlayText.ui('Ready');$('classificationResult').textContent=JevPlayText.ui(showcaseKind.kind==='support_routing'?'Which team should handle this?':'What emotion does this text express?');}
  }else if(showcaseKind.mode==='world'){
   const bridge=worldBridge();
   if(bridge)renderWorld(bridge.snapshot());
  }else if(showcaseSession&&showcaseSession.world.kind!=='racing_sprint'){
   renderShowcaseGame();
   if(showcaseSession.world.kind==='doudizhu'){window.cardSelection=selectedCards;drawShowcase();window.updateCardAction?.();if(chosenCombo&&$('legalCardCombo'))$('legalCardCombo').value=chosenCombo;}
   if(selectedBid!==undefined)$('showcaseActions').querySelector('[data-bid="'+selectedBid+'"]')?.click();
   if(hold!==undefined&&$('holdTime')){$('holdTime').value=hold;$('holdLabel').textContent=hold+' '+JevPlayText.ui('ms');}
  }
 }
 if(showcaseKind?.kind!=='racing_sprint'&&!legacyAgentShowcase(showcaseSession?.world.kind)){
  $('lastDecision').textContent=JevPlayText.ui(oldDecision);
  $('showcaseHistory').querySelectorAll('div').forEach(row=>{for(const node of row.childNodes)if(node.nodeType===3)node.nodeValue=JevPlayText.ui(node.nodeValue);const actor=row.querySelector('b');if(actor)actor.textContent=JevPlayText.ui(actor.textContent);});
 }
 $('showcaseAuto').textContent=JevPlayText.ui(showcaseAuto&&autoMode==='model'?'■ Stop autoplay':'▶ Autoplay');
 $('showcaseReference').textContent=JevPlayText.ui(showcaseAuto&&autoMode==='reference'?'■ Stop demo':'Demo');
 showcaseControls(showcaseBusy);
}
window.JevI18n?.onChange(redrawPlayLanguage);
