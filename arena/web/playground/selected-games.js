/* Public-state renderers; all legal actions and game rules come from the server. */
window.JevSelectedGames=(()=>{
 let root=null,sourceCell=null,position=null,rendered=null,gridElement=null,gridKind=null;
 const kinds=new Set(['checkers','xiangqi','guess_the_number','minesweeper','sudoku','uno']);
 function ui(value){
  const text=String(value??'');if(window.JevI18n?.lang==='zh')return text;
  const names={'已知动作反馈':'Known action feedback','连续无效动作剩余重试：':'Invalid-action retries remaining: ','空格':'Empty','UNO纸牌':'UNO','双人UNO':'UNO','西洋跳棋':'Checkers','围棋 · 9×9':'Go · 9×9','中国象棋':'Chinese Chess','猜数字':'Guess the Number','扫雷':'Minesweeper','数独':'Sudoku','单人挑战':'Solo','白方':'White','黑方':'Black','红方':'Red','当前顶牌':'Discard','当前颜色':'Active color','你的手牌':'Your hand','对手':'Opponent','红色':'Red','绿色':'Green','蓝色':'Blue','黄色':'Yellow','万能牌':'Wild','跳过':'Skip','反转':'Reverse','加二':'Draw two','变色':'Wild','加四':'Wild draw four','抽一张牌':'Draw a card','全部合法着法':'All legal moves','停一手（Pass）':'Pass','请将界面交给下一位玩家。上一位的私有信息已收起。':'Pass the device to the next player. Private information is hidden.','亮框手牌可出；万能牌在下方选择颜色后出牌。':'Highlighted cards are playable. Choose a color below to play a wild card.','选择填入数字，或返回重选空格。':'Choose a number, or go back to pick another cell.','点击空格，再选择数字。':'Select an empty cell, then choose a number.','目标更大':'Higher','目标更小':'Lower','在下方选择出牌后的颜色':'Choose the next color below','点击棋子，再选择目标格。':'Select a piece, then its destination.','点击空点落子，或选择停着。':'Click an intersection to play, or pass.','选择下方的数字进行猜测。':'Choose a number below to guess.','点击未揭开的格子。':'Click a covered cell.','点击可出的手牌，或使用下方操作。':'Play a highlighted card, or use the controls below.'};
  if(names[text])return names[text];
  let out=text;for(const [zh,en] of Object.entries(names).sort((a,b)=>b[0].length-a[0].length))out=out.split(zh).join(en);
  return out.replace(/玩家\s*(\d+)/g,'Player $1').replace(/显示 Player (\d+) 的局面/g,'Show Player $1’s position').replace(/(\d+) 张/g,'$1 cards').replace(/剩余 (\d+) 次/g,'$1 guesses left').replace(/共 (\d+) 枚雷/g,'$1 mines').replace(/白方贴目 /g,'White komi ').replace(/White贴目 /g,'White komi ').replace(/双方连续停着后计分。/g,'Both players pass to score.');
 }
 function feedbackReason(reason){
  if(window.JevI18n?.lang!=='zh')return reason;
  let match;if((match=/^You hit a mine at \((\d+), (\d+)\)\.$/.exec(reason)))return '已踩到雷：'+(+match[1]+1)+'行 '+(+match[2]+1)+'列，避开此格。';
  if((match=/attempted to place (\d+) at \((\d+), (\d+)\), which violates Sudoku rules/.exec(reason)))return match[2]+'行 '+match[3]+'列填 '+match[1]+' 被原生规则拒绝，请尝试其他动作。';
  return reason;
 }
 function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=ui(text);if(cls)n.className=cls;return n}
 const colors={r:'红色',g:'绿色',b:'蓝色',y:'黄色'};
 function unoName(card){const [color,type]=card.split('-');return (type.startsWith('wild')?'万能牌':colors[color])+' · '+({skip:'跳过',reverse:'反转',draw_2:'加二',wild:'变色',wild_draw_4:'加四'}[type]||type)}
 function unoCard(card,tag='span'){
  const [color,type]=card.split('-'),wild=type.startsWith('wild'),symbol={skip:'⊘',reverse:'⇄',draw_2:'+2',wild:'✦',wild_draw_4:'+4'}[type]||type;
  const c=node(tag,undefined,'uno-card'+(wild?' uno-wild':''));c.dataset.color=color;c.setAttribute('aria-label',ui(unoName(card)));c.title=ui(unoName(card));
  c.append(node('span',symbol,'uno-corner'),node('span',symbol,'uno-face'),node('span',symbol,'uno-corner uno-corner-bottom'));
  return c;
 }
 function hide(){if(root)root.hidden=true}
 function panel(){if(!root){root=node('section',undefined,'selected-game');root.id='selectedGameBoard';$('showcaseCanvas').after(root)}root.hidden=false;root.replaceChildren();return root}
 function reveal(){if(showcaseBusy)return;showcaseBusy=true;showcaseControls(true);api('showcases/reveal',{session_id:showcaseSession.session_id,revision:showcaseSession.revision}).then(s=>{showcaseSession=s;renderShowcaseGame()}).catch(error).finally(()=>{showcaseBusy=false;showcaseControls(false)})}
 function boardRows(g){if(g.board)return g.board;const lines=g.board_text.split('\n');if(g.kind==='xiangqi')return lines.filter(l=>l.length===9).map(l=>[...l]);if(g.kind==='checkers')return lines.filter(l=>/^[1-8]/.test(l)).map(l=>[...l.slice(1)]);return lines.filter(l=>/^\s*[1-9]\s+[+.XOxo]+\s*$/.test(l)).map(l=>[...l.trim().split(/\s+/)[1]])}
 function piece(g,v){if(v===null)return '';if(g.kind==='minesweeper')return v<0?'💣':v===0?'':String(v);if(g.kind==='sudoku')return v===0?'':String(v);if(g.kind==='go')return ['.','+'].includes(v)?'':v.toLowerCase()==='x'?'●':'○';if(g.kind==='checkers')return v==='.'?'':v==='o'?'○':v==='+'?'●':v==='8'?'♔':v==='*'?'♚':v;const zh={r:'車',h:'馬',e:'象',a:'士',g:'將',c:'砲',s:'卒',R:'車',H:'馬',E:'相',A:'仕',G:'帥',C:'炮',S:'兵'};return zh[v]||''}
 function xiangqiBoard(){
  const ns='http://www.w3.org/2000/svg';
  function svg(tag,attrs){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el}
  const board=svg('svg',{viewBox:'0 0 900 1000',class:'xiangqi-lines','aria-hidden':'true',focusable:'false'});
  function line(x1,y1,x2,y2,cls=''){board.append(svg('line',{x1,y1,x2,y2,class:cls}))}
  for(let r=0;r<10;r++)line(50,50+r*100,850,50+r*100);
  for(let c=0;c<9;c++){const x=50+c*100;if(c===0||c===8)line(x,50,x,950);else{line(x,50,x,450);line(x,550,x,950)}}
  for(const y of [50,750]){line(350,y,550,y+200,'xiangqi-palace');line(550,y,350,y+200,'xiangqi-palace')}
  // Traditional cannon/pawn starting-point marks, inside the board edges.
  for(const [r,cols] of [[2,[1,7]],[3,[0,2,4,6,8]],[6,[0,2,4,6,8]],[7,[1,7]]]){
   for(const c of cols)for(const dx of [-1,1])for(const dy of [-1,1]){
    if(c===0&&dx<0||c===8&&dx>0)continue;
    const x=50+c*100,y=50+r*100;
    board.append(svg('path',{d:`M ${x+dx*11} ${y+dy*23} V ${y+dy*11} H ${x+dx*23}`}));
   }
  }
  for(const [x,word] of [[250,'楚 河'],[650,'漢 界']]){const label=svg('text',{x,y:500,'text-anchor':'middle','dominant-baseline':'central'});label.textContent=word;board.append(label)}
  return board;
 }
 function mappings(g,options){const moves=[];for(const [action,label] of Object.entries(options)){
  let m;if(g.kind==='checkers'&&(m=/^([a-h])([1-8])([a-h])([1-8])/.exec(label)))moves.push({action,from:[8-+m[2],m[1].charCodeAt(0)-97],to:[8-+m[4],m[3].charCodeAt(0)-97]});
  if(g.kind==='xiangqi'&&(m=/\((\d+),(\d+)\)-\((\d+),(\d+)\)/.exec(label)))moves.push({action,from:[+m[1],+m[2]],to:[+m[3],+m[4]]});
 }return moves}
 function render(g,options,act){if(!kinds.has(g.kind)){hide();return false}
  const signature=JSON.stringify([g,options,window.JevI18n?.lang,window.JevParticipants?.isDuel()?JevParticipants.badges():null]);
  if(root&&rendered===signature){root.hidden=false;return true}
  rendered=signature;const p=panel();
  if(position!==g.kind+':'+g.steps){sourceCell=null;position=g.kind+':'+g.steps}
  const title=node('div',g.name+' · '+(g.seat_count>1?(g.player_name||'玩家 '+(g.player+1)):'单人挑战'),'selected-heading');if(window.JevParticipants?.isDuel()){const roles=g.kind==='xiangqi'?['红方','黑方']:g.kind==='checkers'?['白方','黑方']:undefined;title.innerHTML=JevParticipants.badges(roles?.map(ui));}p.append(title);
  if(g.handoff&&!g.fixed_view){p.append(node('p','请将界面交给下一位玩家。上一位的私有信息已收起。'));const b=node('button','显示玩家 '+(g.player+1)+' 的局面','selected-reveal');b.onclick=reveal;p.append(b);return true}
  if(g.action_feedback?.length){
   const feedback=node('div',undefined,'selected-feedback');feedback.setAttribute('role','status');
   feedback.append(node('strong','已知动作反馈'));
   for(const item of g.action_feedback)feedback.append(node('p',item.action+' · '+feedbackReason(item.reason)));
   if(!g.outcome)feedback.append(node('p','连续无效动作剩余重试：'+g.invalid_retry_remaining));
   p.append(feedback);
  }
  if(g.kind==='uno'){
   const view=g.fixed_view||{seat:g.player,hand:g.hand,hand_counts:g.hand_counts,target:g.target},seat=view.seat;
   const seatName=i=>window.JevParticipants?.isDuel()?JevParticipants.seatMarker(i):ui(i===seat?'你的手牌':'对手');
   const table=node('div',undefined,'uno-table'),opponent=node('div',undefined,'uno-opponent');
   opponent.append(node('strong',seatName(1-seat)+' · '+view.hand_counts[1-seat]+' 张'));
   const backs=node('div',undefined,'uno-backs');for(let i=0;i<Math.min(7,view.hand_counts[1-seat]);i++)backs.append(node('span','UNO','uno-back'));opponent.append(backs);table.append(opponent);
   const discard=node('div',undefined,'uno-discard');discard.append(node('strong','当前顶牌'),unoCard(view.target),node('span','当前颜色 · '+colors[view.target[0]],'uno-active-color'));table.append(discard);p.append(table);
   p.append(node('h3',seatName(seat)+' · '+view.hand_counts[seat]+' 张','uno-hand-title'));
   const hand=node('div',undefined,'selected-hand');
   if(view.concealed)for(let i=0;i<view.hand_counts[seat];i++)hand.append(node('span','UNO','uno-card uno-back'));
   for(const card of view.hand){
    const c=unoCard(card,'button'),type=card.split('-')[1];
    const entries=Object.entries(options).filter(([,label])=>type.startsWith('wild')?label.split('-')[1]===type:label===card);
    c.disabled=!!g.outcome||entries.length===0||(window.JevParticipants?.isDuel()&&!JevParticipants.canAct());c.classList.toggle('uno-playable',!c.disabled);
    if(entries.length===1){c.dataset.action=entries[0][0];c.onclick=()=>{if(!showcaseBusy)act(entries[0][0])}}
    else if(entries.length){c.title+=' · 在下方选择出牌后的颜色';c.onclick=()=>{const first=$('showcaseActions').querySelector('[data-action="'+entries[0][0]+'"]');first?.focus();first?.scrollIntoView({block:'nearest',behavior:'smooth'})}}
    hand.append(c);
   }p.append(hand);
   p.append(node('p',window.JevParticipants?.isDuel()?JevParticipants.seatMarker(JevParticipants.actor()):'亮框手牌可出；万能牌在下方选择颜色后出牌。','uno-hint'));return true;
  }
  if(g.kind==='guess_the_number'){
   p.append(node('p',g.minimum+'–'+g.maximum+' · 剩余 '+g.remaining+' 次'));
   const list=node('ol');for(const [guess,hint] of g.history)list.append(node('li',guess+' → '+(hint==='higher'?'目标更大':'目标更小')));p.append(list);return true;
  }
  const rows=boardRows(g),grid=gridKind===g.kind&&gridElement?gridElement:node('div',undefined,'selected-grid '+g.kind);
  gridKind=g.kind;gridElement=grid;grid.replaceChildren();grid.style.setProperty('--columns',rows[0]?.length||9);const moves=mappings(g,options);
  if(g.kind==='xiangqi'){grid.append(xiangqiBoard());grid.setAttribute('aria-label',ui('中国象棋')+' · 9 × 10')}
  function mark(){grid.querySelectorAll('button').forEach(b=>{const cell=[+b.dataset.row,+b.dataset.col];b.classList.toggle('origin',sourceCell&&String(cell)===String(sourceCell));b.classList.toggle('destination',moves.some(m=>String(m.from)===String(sourceCell)&&String(m.to)===String(cell)))})}
  // Native Minesweeper leaves a hit mine covered; only mark coordinates already disclosed by action feedback.
  const hitMines=new Set((g.kind==='minesweeper'?g.action_feedback||[]:[]).flatMap(item=>{const m=/^You hit a mine at \((\d+), (\d+)\)\.$/.exec(item.reason);return m?[+m[1]+':'+(+m[2])]:[]}));
  rows.forEach((row,r)=>row.forEach((v,c)=>{const hit=hitMines.has(r+':'+c),symbol=hit?'💣':piece(g,v);const b=node('button',symbol,'selected-cell');b.dataset.row=r;b.dataset.col=c;if(g.kind==='xiangqi'&&/[A-Z]/.test(v))b.classList.add('red-piece');b.setAttribute('aria-label',(r+1)+'行 '+(c+1)+'列 '+(hit?(window.JevI18n?.lang==='zh'?'踩中炸弹':'Mine hit'):(symbol||'空格')));if(g.kind==='checkers')b.classList.toggle('dark',(r+c)%2===1);if(g.kind==='minesweeper'){b.classList.toggle('covered',v===null&&!hit);b.classList.toggle('mine-hit',hit);if(hit)b.title=window.JevI18n?.lang==='zh'?'踩中炸弹':'Mine hit';}if(g.kind==='sudoku'){b.classList.toggle('origin',String(g.selected)===String([r,c]));if(c===2||c===5)b.classList.add('box-right');if(r===2||r===5)b.classList.add('box-bottom')}
   let action=null;if(g.kind==='minesweeper')action='['+r+' '+c+']';else if(g.kind==='sudoku')action='cell:'+r+':'+c;else if(g.kind==='go'){const coord='abcdefghj'[c]+(rows.length-r);action=Object.keys(options).find(k=>options[k].toLowerCase().endsWith(' '+coord))}
   if(action&&action in options){b.dataset.action=action;b.onclick=()=>{if(!showcaseBusy)act(action)}}
   else if(moves.length){b.onclick=()=>{if(showcaseBusy)return;const target=moves.find(m=>String(m.from)===String(sourceCell)&&String(m.to)===String([r,c]));if(target){sourceCell=null;act(target.action)}else{sourceCell=moves.some(m=>String(m.from)===String([r,c]))?[r,c]:null;mark()}}}
   else b.disabled=true;
   if(g.kind==='go'){
    const coord='ABCDEFGHJ'[c]+(rows.length-r);b.setAttribute('aria-label',coord+' '+(piece(g,v)||'空点'));b.title=coord;
    b.replaceChildren();if(piece(g,v))b.append(node('span',undefined,'go-stone '+(v.toLowerCase()==='x'?'black':'white')));
    else if((r===2||r===6)&&(c===2||c===6)||r===4&&c===4)b.append(node('span',undefined,'go-star'));
   }
   if(g.kind==='xiangqi'){
    const symbol=piece(g,v),side=/[A-Z]/.test(v)?'红方':'黑方';b.replaceChildren();b.dataset.piece=v;
    b.classList.toggle('has-piece',!!symbol);b.classList.toggle('selectable',moves.some(m=>m.from[0]===r&&m.from[1]===c));
    if(symbol){const token=node('span',symbol,'xiangqi-piece');token.setAttribute('aria-hidden','true');b.append(token)}
    b.setAttribute('aria-label',`${r+1}, ${c+1} · ${symbol?ui(side)+' '+symbol:ui('空格')}`);
   }
   if(g.outcome)b.disabled=true;grid.append(b)}));
  if(g.kind==='go'){const axes=node('div',undefined,'go-coordinates');for(const coord of 'ABCDEFGHJ')axes.append(node('span',coord));p.append(axes)}p.append(grid);
  if(g.kind==='sudoku')p.append(node('p',g.phase==='select_number'?'选择填入数字，或返回重选空格。':'点击空格，再选择数字。'));
  if(g.kind==='go')p.append(node('p','9×9 · 白方贴目 '+g.komi+' · 双方连续停着后计分。'));
  if(g.kind==='minesweeper')p.append(node('p','共 '+g.mine_count+' 枚雷 · 点击未揭开的格子。'));
  return true;
 }
 function controls(g,options,act){$('keyboardHint').textContent=ui(({checkers:'点击棋子，再选择目标格。',xiangqi:'点击棋子，再选择目标格。',go:'点击空点落子，或选择停着。',guess_the_number:'选择下方的数字进行猜测。',minesweeper:'点击未揭开的格子。',sudoku:'点击空格，再选择数字。',uno:'点击可出的手牌，或使用下方操作。'})[g.kind]||'');const el=$('showcaseActions');el.replaceChildren();if(g.handoff||g.outcome)return;
  let entries=Object.entries(options);if(g.kind==='go')entries=entries.filter(([a,label])=>label.toLowerCase().includes('pass'));if(g.kind==='minesweeper'||g.kind==='sudoku'&&g.phase==='select_cell')entries=[];
  const target=['checkers','xiangqi'].includes(g.kind)?node('details'):el;if(target!==el){target.append(node('summary','全部合法着法'));el.append(target)}
  for(const [action,label] of entries){
   const b=node('button',g.kind==='uno'?(label==='draw'?'抽一张牌':unoName(label)+(label.includes('wild')?' → '+colors[label[0]]:'')):g.kind==='go'?'停一手（Pass）':label);
   if(g.kind==='uno'){b.className='uno-action';if(label!=='draw'){b.dataset.color=label[0];b.prepend(unoCard(label))}}
   b.dataset.action=action;b.onclick=()=>{if(!showcaseBusy)act(action)};target.append(b)
  }
 }
 return {render,controls,hide,has:k=>kinds.has(k)};
})();
