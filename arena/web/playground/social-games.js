(function () {
  const originalDraw = PlayDraw.draw;
  const socialKinds = new Set(['doudizhu', 'texas_holdem', 'property_tycoon', 'zha_jin_hua', 'pig_dice']);
  const canvas = document.getElementById('showcaseCanvas');
  const ctx = canvas.getContext('2d');
  // Logical positions stay constant for drawing, animations and card hit tests.
  // The backing store follows the display density; it must not define geometry.
  const W = 900, H = 540;
  let lastGame = null;
  function prepareCanvas() {
    const density = window.devicePixelRatio || 1;
    const scale = Math.max(1, density, canvas.getBoundingClientRect().width / W * density);
    const width = Math.round(W * scale), height = Math.round(H * scale);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width; canvas.height = height;
    }
    ctx.setTransform(width / W, 0, 0, height / H, 0, 0);
    ctx.imageSmoothingEnabled = true;
    canvas.style.imageRendering = 'auto';
  }
  let cardHits = [];
  let brightTable = false;
  window.cardSelection = [];

  const brightFill = {
    '#09282ae8':'#fff7e3', '#0b3839df':'#fff9e8', '#0a383adf':'#fff9e8',
    '#08292ad9':'#fff9e8', '#0d3537ed':'#fff7e3', '#082d30ea':'#fff7e3',
    '#092f3188':'#eff5e8', '#0b3234df':'#fff7e3', '#0e3438':'#fff7e3',
    '#0a3238':'#fff4dc', '#1b5a4b':'#a9d9b8', '#175148':'#abd8b8',
    '#15584c':'#a9d9b8', '#ffffff36':'#4c76596b', '#ffffff1a':'#5d856448',
    '#e8d3a56b':'#587b63aa', '#f4e8c52c':'#4c765956'
  };
  function tint(value) { return brightTable ? brightFill[value] || value : value; }
  function readable(value) {
    if (!brightTable || typeof value !== 'string' || !/^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(value)) return value;
    const hex = value.length === 4 ? value.slice(1).split('').map(ch => ch + ch).join('') : value.slice(1);
    const red = parseInt(hex.slice(0, 2), 16), green = parseInt(hex.slice(2, 4), 16), blue = parseInt(hex.slice(4, 6), 16);
    return (red * .2126 + green * .7152 + blue * .0722) > 164 ? '#2b5144' : value;
  }

  function box(x, y, w, h, radius, fill, stroke, lineWidth = 1) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 0);
    if (fill) { ctx.fillStyle = tint(fill); ctx.fill(); }
    if (stroke) { ctx.strokeStyle = tint(stroke); ctx.lineWidth = lineWidth; ctx.stroke(); }
  }
  function label(value, x, y, size = 16, color = '#fff', weight = 500, align = 'left', maxWidth) {
    value=JevPlayText.text(value);
    ctx.fillStyle = readable(color);
    const family='px "Inter", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif';
    let fontSize=Math.max(12,size);
    ctx.font = weight + ' ' + fontSize + family;
    if(maxWidth && ctx.measureText(String(value)).width>maxWidth){
      fontSize*=maxWidth/ctx.measureText(String(value)).width;
      ctx.font=weight+' '+fontSize+family;
    }
    ctx.textAlign = align;
    ctx.textBaseline = 'middle';
    ctx.fillText(String(value), x, y);
  }
  function ellipse(x, y, rx, ry, fill, stroke, lineWidth = 1) {
    ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    if (fill) { ctx.fillStyle = tint(fill); ctx.fill(); }
    if (stroke) { ctx.strokeStyle = tint(stroke); ctx.lineWidth = lineWidth; ctx.stroke(); }
  }
  function background(top, bottom) {
    const gradient = ctx.createLinearGradient(0, 0, W, H);
    gradient.addColorStop(0, brightTable ? '#fff6dc' : top);
    gradient.addColorStop(1, brightTable ? '#e6f1db' : bottom);
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, W, H);
  }
  function suitShape(suit, x, y, size, color) {
    ctx.save();ctx.translate(x,y);ctx.scale(size,size);ctx.fillStyle=readable(color);ctx.beginPath();
    if(suit==='♦'){ctx.moveTo(0,-.5);ctx.lineTo(.34,0);ctx.lineTo(0,.5);ctx.lineTo(-.34,0);ctx.closePath();ctx.fill();}
    else if(suit==='♥'){ctx.moveTo(0,.46);ctx.bezierCurveTo(-.9,-.1,-.36,-.8,0,-.28);ctx.bezierCurveTo(.36,-.8,.9,-.1,0,.46);ctx.fill();}
    else if(suit==='♠'){ctx.moveTo(0,-.5);ctx.bezierCurveTo(-.8,.07,-.37,.6,0,.18);ctx.bezierCurveTo(.37,.6,.8,.07,0,-.5);ctx.fill();ctx.beginPath();ctx.moveTo(-.15,.5);ctx.lineTo(.15,.5);ctx.lineTo(0,.05);ctx.closePath();ctx.fill();}
    else{for(const [cx,cy] of [[0,-.25],[-.23,.05],[.23,.05]]){ctx.beginPath();ctx.arc(cx,cy,.24,0,Math.PI*2);ctx.fill();}ctx.beginPath();ctx.moveTo(-.15,.5);ctx.lineTo(.15,.5);ctx.lineTo(0,.02);ctx.closePath();ctx.fill();}
    ctx.restore();
  }
  function rankCard(value, x, y, w, h, opts = {}) {
    // Match 21-point cards, using only the identity of a visible card.
    // Old rank-only replays retain their corner ranks without inventing suits.
    const face=opts.face!==false,selected=!!opts.selected,compact=!!opts.compact;
    const id=opts.cardId,suit=Number.isInteger(id)&&id>=0&&id<52&&Math.floor(id/4)+3===value?['♠','♥','♣','♦'][id%4]:null;
    const radius=Math.min(6,w*.1),ink=suit==='♥'||suit==='♦'||value===17?'#a52b35':'#243c30';
    const frame=(xx,yy,ww,hh,fill,stroke,line=1)=>{ctx.beginPath();ctx.roundRect(xx,yy,ww,hh,radius);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=line;ctx.stroke();}};
    ctx.save();
    frame(x,y+3,w,h,'#e0e4d8');
    frame(x,y,w,h,selected?'#fff7df':'#fffffa',selected?'#337b66':'#d8ded0',selected?2.5:1);
    if(!face){
      ctx.beginPath();ctx.roundRect(x+3,y+3,w-6,h-6,Math.max(1,radius-2));ctx.clip();
      ctx.fillStyle='#768e6d';ctx.fillRect(x+3,y+3,w-6,h-6);
      ctx.strokeStyle='#809975';ctx.lineWidth=3;
      for(let i=-h;i<w+h;i+=7){ctx.beginPath();ctx.moveTo(x+i,y);ctx.lineTo(x+i+h,y+h);ctx.stroke();}
      ctx.fillStyle='#e5ead9';ctx.font='italic '+Math.round(w*.4)+'px serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('J',x+w/2,y+h/2);
      ctx.restore();return;
    }
    const rank=({11:'J',12:'Q',13:'K',14:'A',15:'2',16:'LJ',17:'HJ'}[value]||String(value));
    const corner=compact?5:7,top=compact?11:15;
    const rankSize=value>=16?(compact?10:14):rank.length>1?(compact?12:16):(compact?15:20);
    label(rank,x+corner,y+top,rankSize,ink,600,'left',Math.min(w-corner*2,compact?23:30));
    if(value>=16){
      // A monochrome/red joker emblem identifies the small/big joker without
      // squeezing translated joker names into an overlapping card's centre.
      const cx=x+w/2,cy=y+h*.54,scale=Math.min(w*.56,h*.31);
      ctx.save();ctx.translate(cx,cy);ctx.scale(scale,scale);ctx.fillStyle=ink;
      ctx.beginPath();ctx.moveTo(-.45,-.25);ctx.lineTo(-.18,-.08);ctx.lineTo(0,-.42);ctx.lineTo(.18,-.08);ctx.lineTo(.45,-.25);ctx.lineTo(.31,.27);ctx.lineTo(-.31,.27);ctx.closePath();ctx.fill();
      for(const [xx,yy] of [[-.45,-.3],[0,-.47],[.45,-.3]]){ctx.beginPath();ctx.arc(xx,yy,.065,0,Math.PI*2);ctx.fill();}
      ctx.fillRect(-.3,.32,.6,.07);ctx.restore();
      if(!compact)label('JOKER',cx,y+h*.78,Math.min(9,w*.16),ink,500,'center');
    }else if(suit){
      suitShape(suit,x+w/2,y+h*.56,compact?Math.min(20,h*.36):29,ink);
      if(!compact)suitShape(suit,x+corner+5,y+top+18,10,ink);
    }
    ctx.save();ctx.translate(x+w-corner,y+h-(compact?9:12));ctx.rotate(Math.PI);
    label(rank,0,0,value>=16?8:compact?9:12,ink,500,'left',w-corner*2);ctx.restore();
    ctx.restore();
  }
  function card(value, x, y, w, h, opts = {}) {
    if(!opts.poker)return rankCard(value,x,y,w,h,opts);
    const face = opts.face !== false, poker = !!opts.poker, selected = !!opts.selected;
    ctx.save();
    ctx.shadowColor = '#071c1d66'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 5;
    box(x, y, w, h, 8, selected ? '#fff7df' : face ? '#fffdf7' : '#23505e',
      selected ? '#e2b657' : face ? '#dce0d6' : '#b7c7bd', selected ? 3 : 1.5);
    ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
    ctx.beginPath(); ctx.roundRect(x + 3, y + 3, w - 6, h - 6, 5); ctx.clip();
    if (!face) {
      box(x + 5, y + 5, w - 10, h - 10, 4, '#2d6670', '#c6a86b');
      ctx.strokeStyle = '#bbd4ce58';
      for (let i = -h; i < w + h; i += 13) {
        ctx.beginPath(); ctx.moveTo(x + i, y + 6); ctx.lineTo(x + i + h, y + h - 6); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + i + h, y + 6); ctx.lineTo(x + i, y + h - 6); ctx.stroke();
      }
      ellipse(x + w / 2, y + h / 2, 9, 9, '#e4cf9b', '#29505a', 2);
    } else {
      const suit = poker ? ['♠', '♥', '♣', '♦'][Math.floor(value / 13)] : '';
      const rank = poker ? ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'][value % 13]
        : ({ 11: 'J', 12: 'Q', 13: 'K', 14: 'A', 15: '2', 16: 'LJ', 17: 'HJ' }[value] || String(value));
      const ink = suit === '♥' || suit === '♦' || (!poker && value >= 15) ? '#b64d48' : '#23433e';
      label(rank, x + (opts.compact ? 5 : 8), y + (opts.compact ? 12 : 17), opts.compact ? (rank.length > 1 ? 10 : 14) : rank.length > 1 ? 15 : 20, ink, 750);
      if (poker) {
        suitShape(suit,x+w/2,y+h/2+7,31,ink);
        suitShape(suit,x+w-11,y+h-15,14,ink);
      } else {
        label(rank, x + w / 2, y + h / 2 + 8, opts.compact ? 14 : value >= 16 ? 17 : 23, value >= 15 ? '#d6aaa1' : '#bbd0c5', 400, 'center');
        if (!opts.compact) label(rank, x + w - 7, y + h - 13, 12, ink, 700, 'right');
      }
    }
    ctx.restore();
  }
  function backs(x, y, count) {
    for (let i = 0; i < Math.min(5, count); i++) card(null, x + i * 18, y, 35, 49, { face: false });
  }

  const rankNames = {11:'J',12:'Q',13:'K',14:'A',15:'2',16:'LJ',17:'HJ'};
  const rankValues = {J:11,Q:12,K:13,A:14,'2':15,'小王':16,'大王':17,LJ:16,HJ:17};
  let tableCache = null, animationEpoch = 0, animationRunning = false;
  const cloneTable = value => ({plays:value.plays.map(cards => cards ? cards.slice() : null),passed:value.passed.slice(),passes:value.passes,reset:value.reset,leader:value.leader});
  const emptyTable = () => ({plays:[null,null,null],passed:[false,false,false],passes:0,reset:false,leader:null});
  const tableKey = g => g.kind + ':' + (typeof showcaseSession !== 'undefined' ? showcaseSession?.session_id || '' : '') + ':' + (g.view_seat ?? 0);
  const seatId = relative => lastGame?.seat_ids?.[relative] ?? relative;
  const seatActive = relative => !!lastGame?.duel && !lastGame.outcome && seatId(relative)===lastGame.active_seat;
  const roleName = relative => lastGame?.duel && window.JevParticipants
    ? JevParticipants.seatText(seatId(relative))
    : lastGame?.seat_labels?.[relative] || (relative === 0 ? 'You · Landlord' : 'Farmer ' + (relative === 1 ? 'A' : 'B'));
  const seatName = (relative,fallback) => lastGame?.duel ? (seatActive(relative)?'▶ ':'')+roleName(relative) : fallback;
  const seatBorder = (relative,fallback) => seatActive(relative)?'#318658':fallback;
  const visibleCards = (ranks,ids) => ranks.map((rank,index)=>({rank,cardId:ids?.[index]??null}));
  function publicPlay(entry) {
    if (!entry || ![0,1,2].includes(entry.player) || typeof entry.move !== 'string') return null;
    if (['过','不出','pass'].includes(entry.move)) return {player:entry.player,cards:[],pass:true};
    const cards = entry.move.trim().split(/\s+/).map(value => rankValues[value] ?? Number(value));
    if (!cards.length || cards.some(value => !Number.isInteger(value) || value < 3 || value > 17)) return null;
    return {player:entry.player,cards:visibleCards(cards,entry.card_ids),pass:false};
  }
  function applyPublicPlay(table, play) {
    const next = cloneTable(table);
    if (play.pass) {
      next.passed[play.player] = true;
      next.passes += 1;
      if (next.passes >= 2) next.reset = true;
    } else {
      if (next.reset) {next.plays=[null,null,null];next.passed=[false,false,false];}
      next.reset = false; next.passes = 0; next.leader = play.player;
      next.plays[play.player] = play.cards.slice(); next.passed[play.player] = false;
    }
    return next;
  }
  function newPublicPlays(before, after) {
    const old = before.history || [], recent = after.history || [];
    // One interactive step contains the visible player's move followed by the
    // rule opponents. This also distinguishes repeated identical public moves.
    if (after.steps === before.steps + 1) {
      const own = recent.map(item => item.player).lastIndexOf(0);
      if (own >= 0) return recent.slice(own).map(publicPlay).filter(Boolean);
    }
    let overlap = Math.min(old.length,recent.length);
    for (; overlap > 0; overlap--) {
      if (JSON.stringify(old.slice(-overlap)) === JSON.stringify(recent.slice(0,overlap))) break;
    }
    return recent.slice(overlap).map(publicPlay).filter(Boolean);
  }
  function publicTable(g, commit = true) {
    const key = tableKey(g), cached = tableCache?.key === key && g.steps >= tableCache.steps ? tableCache : null;
    let table = cached ? cloneTable(cached.table) : emptyTable();
    const plays = cached ? newPublicPlays({history:cached.history,steps:cached.steps},g) : (g.history || []).map(publicPlay).filter(Boolean);
    for (const play of plays) table = applyPublicPlay(table,play);
    // The last legal combination is public even when an old history window was
    // truncated. Never obtain cards from another player's private hand.
    if (Array.isArray(g.last?.[3]) && [0,1,2].includes(g.leader) && g.last[3].every(value => Number.isInteger(value) && value >= 3 && value <= 17)) {
      table.plays[g.leader] = visibleCards(g.last[3],g.last_card_ids); table.leader = g.leader;
    }
    if (commit) tableCache = {key,steps:g.steps,history:structuredClone(g.history || []),table:cloneTable(table)};
    return table;
  }
  function tableCards(cards, player) {
    const center = [450,190,710][player], width = player === 0 ? 350 : 302;
    const compact = cards.length > 10, perRow = compact ? 10 : cards.length;
    const w = compact ? 32 : 40, h = compact ? 42 : 57;
    const top = player === 0 ? (compact ? 284 : 293) : (compact ? 205 : 211);
    return cards.map((value,index) => {
      const row = Math.floor(index/perRow), column = index%perRow;
      const columns = Math.min(perRow,cards.length-row*perRow);
      const step = columns <= 1 ? 0 : Math.min(compact ? 27 : 29,(width-w)/(columns-1));
      return {value:value.rank??value,cardId:value.cardId??null,x:center-(w+(columns-1)*step)/2+column*step,y:top+row*25,w,h};
    });
  }
  function playedCards(table, player, flight) {
    const cards = table.plays[player], center = [450,190,710][player], y = player === 0 ? 275 : 194;
    const active = player === table.leader;
    label(roleName(player) + (table.passed[player] ? ' · Pass' : cards ? ' · Played' : ''),center,y,12,active ? '#8b602f' : '#496b54',650,'center',240);
    if (!cards?.length) {
      label(table.passed[player] ? 'Pass' : 'Waiting',center,y+34,16,'#78917b',500,'center');
      return;
    }
    if (flight?.player === player && !flight.pass && flight.progress < 1) return;
    for (const item of tableCards(cards,player)) card(item.value,item.x,item.y,item.w,item.h,{compact:true,selected:active,cardId:item.cardId});
  }
  function flyingPlay(flight) {
    if (!flight) return;
    const p = flight.progress, eased = 1-Math.pow(1-p,3), player = flight.player;
    if (flight.pass) {
      const x=[450,190,710][player], y=(player===0?278:197)-12*(1-p);
      ctx.save();ctx.globalAlpha=.5+.5*p;box(x-35,y-15,70,29,0,'#fff8df','#b69b63');label('Pass',x,y,15,'#7c6947',600,'center');ctx.restore();return;
    }
    const origin = [[450,430],[140,145],[760,145]][player];
    const items = tableCards(flight.cards,player);
    items.forEach((item,index) => {
      const startX=origin[0]-item.w/2+(index-(items.length-1)/2)*3,startY=origin[1]-item.h/2;
      const x=startX+(item.x-startX)*eased,y=startY+(item.y-startY)*eased-Math.sin(p*Math.PI)*20;
      ctx.save();ctx.globalAlpha=.65+.35*p;ctx.translate(x+item.w/2,y+item.h/2);ctx.rotate((1-p)*(player===1?-.12:player===2?.12:0));
      card(item.value,-item.w/2,-item.h/2,item.w,item.h,{compact:true,selected:true,cardId:item.cardId});ctx.restore();
    });
  }

  function drawDoudizhu(g, extra = {}) {
    const table = extra.cardTable || publicTable(g), flight = extra.cardFlight;
    background('#102f31', '#0b2429');
    ellipse(450,256,426,218,'#805f3b');ellipse(450,256,418,210,'#c5a873');
    ellipse(450,256,409,201,'#1b5a4b','#ffffff36',2);ellipse(450,256,381,176,null,'#ffffff1a',2);
    box(337,20,226,41,21,'#09282ae8','#d2af7355');
    label('Dou Dizhu · Turn '+String(g.steps+1).padStart(2,'0')+'',450,41,15,'#ead8ac',700,'center');
    [[g.seat_labels?.[1]||'Farmer A',g.opponent_counts[0],46],[g.seat_labels?.[2]||'Farmer B',g.opponent_counts[1],664]].forEach(([name,count,x],index)=>{
      const relative=index+1;box(x,78,190,107,16,'#0b3839df',seatBorder(relative,'#bfa47177'),seatActive(relative)?3:1.5);ellipse(x+29,105,17,17,'#d7bd87');
      label(name==='Landlord'?'L':'F',x+29,105,17,'#315348',800,'center');label(seatName(relative,name),x+53,100,13,seatActive(relative)?'#216c4e':'#f6eeda',seatActive(relative)?800:680,'left',130);
      label(count+' cards',x+53,123,12,'#bcd2c5');backs(x+39,133,count);
    });
    box(276,88,348,80,0,'#0a383adf','#c6a66c77',1.5);
    label('PUBLIC CARDS',450,108,13,'#6b7651',650,'center');
    label(table.reset ? 'Trick over · New lead' : table.leader == null ? 'Select cards below' : roleName(table.leader)+' leads',450,140,16,'#315648',600,'center',320);
    [1,2,0].forEach(player=>playedCards(table,player,flight));
    box(37,363,826,166,19,'#08292ad9',seatBorder(0,'#e1c28a55'),seatActive(0)?3:1.5);
    label(seatName(0,'Your hand · '+(g.seat_labels?.[0]||'Landlord')),67,391,16,seatActive(0)?'#216c4e':'#fff5dc',700,'left',640);label((g.hand_count??g.hand.length)+' cards',834,391,15,'#ead09a',700,'right');
    const hand=g.handoff?Array(g.hand_count).fill(null):g.hand;
    const w=54,h=94,step=Math.min(37,(W-144-w)/Math.max(1,hand.length-1)),left=(W-step*(hand.length-1)-w)/2;
    hand.forEach((value,i)=>{const selected=!extra.cardAnimation&&cardSelection.includes(i),x=left+i*step,y=selected?405:420;card(value,x,y,w,h,{selected,face:!g.handoff,cardId:g.hand_card_ids?.[i]});cardHits.push({x,y,w:i===g.hand.length-1?w:step,h,i});});
    flyingPlay(flight);
    const publicSummary=table.plays.map((cards,player)=>roleName(player)+'：'+(cards?.length?cards.map(value=>(rankNames[value.rank]||value.rank)+(Number.isInteger(value.cardId)&&value.cardId<52?['♠','♥','♣','♦'][value.cardId%4]:'')).join(' '):'No play')+(table.passed[player]?', pass':'')).join('；');
    canvas.setAttribute('aria-label',JevPlayText.ui('Dou Dizhu table. Public cards: '+publicSummary+'. Select cards from your hand below.'));
  }

  function drawPoker(g, extra = {}) {
    background('#14232b', '#0b1b24');
    ellipse(450, 276, 423, 225, '#785c3b');
    ellipse(450, 276, 415, 217, '#cba976');
    ellipse(450, 276, 406, 208, '#175148', '#e8d3a56b', 2);
    ellipse(450, 276, 371, 179, null, '#f4e8c52c', 2);
    label('PRIVATE TABLE', 39, 38, 13, '#d6bc89', 780);
    label('VIRTUAL CHIPS  ·  HEADS UP', 861, 38, 12, '#a9b9ae', 550, 'right');
    const street = g.board.length === 0 ? 'Preflop' : g.board.length === 3 ? 'Flop' : g.board.length === 4 ? 'Turn' : 'River';
    box(344, 21, 212, 53, 17, '#0d3537ed', seatBorder(1,'#a98d63aa'),seatActive(1)?3:1);
    label(seatName(1,'Opponent'),362,42,12,seatActive(1)?'#216c4e':'#fff8e8',700,'left',116);
    label(g.stacks[1] + ' chips', 539, 42, 14, '#f0d3a2', 700, 'right');
    label(g.duel?(seatActive(1)?JevI18n.t('To act','当前回合'):JevI18n.t('Waiting','等待行动')):g.opponent_last||'Waiting',450,64,11,'#afcabe',500,'center');
    card(g.opponent_hand && g.opponent_hand[0], 385, 82, 59, 82, { face: !!g.showdown, poker: true });
    card(g.opponent_hand && g.opponent_hand[1], 457, 82, 59, 82, { face: !!g.showdown, poker: true });
    box(374, 180, 152, 67, 17, '#082d30ea', '#d7b77f94', 1.5);
    label('Pot', 450, 201, 12, '#c4d7c9', 600, 'center');
    label(g.pot, 450, 228, 27, '#f3d9a6', 760, 'center');
    label(street + ' · Community cards', 450, 268, 13, '#e6d6af', 700, 'center');
    const cardW = 67, gap = 10, start = (W - cardW * 5 - gap * 4) / 2;
    for (let i = 0; i < 5; i++) {
      const x = start + i * (cardW + gap);
      if (i < g.board.length) {
        const animation=extra.pokerAnimation;
        const progress=!animation||i<animation.previousCount?1:Math.max(0,Math.min(1,(animation.elapsed-(i-animation.previousCount)*75)/330));
        if(progress>0){const eased=1-Math.pow(1-progress,3);ctx.save();ctx.globalAlpha=.35+.65*progress;card(g.board[i],450+(x-450)*eased,206+(285-206)*eased,cardW,94,{poker:true});ctx.restore();}
        else box(x,285,cardW,94,8,'#092f3188','#b1c9b060',1.5);
      }
      else {
        box(x, 285, cardW, 94, 8, '#092f3188', '#b1c9b060', 1.5);
        label(String(i + 1).padStart(2, '0'), x + cardW / 2, 332, 16, '#97b5a4', 650, 'center');
      }
    }
    box(25,410,192,102,15,'#0b3234df',seatBorder(0,'#8fb8a455'),seatActive(0)?3:1);
    label(seatName(0,'Your chips'),45,436,12,seatActive(0)?'#216c4e':'#aacbbb',700,'left',152);
    label(g.stacks[0], 45, 474, 29, '#f9f5e5', 760);
    label(seatName(0,'Your hand'),450,398,13,seatActive(0)?'#216c4e':'#deceaa',700,'center',360);
    (g.handoff?[null,null]:g.hand).forEach(function (value, i) { card(value, 376 + i * 78, 413, 69, 104, { poker: true, face:!g.handoff }); });
    box(683, 410, 192, 102, 15, '#0b3234df', '#8fb8a455');
    label('To call', 704, 436, 12, '#aacbbb', 600);
    label(g.to_call || 'Check available', 704, 474, g.to_call ? 29 : 21, '#f2d39b', 760);
    canvas.setAttribute('aria-label', JevPlayText.ui('Texas Holdem table: opponent above, community cards in the center, your hand below.'));
  }

  function drawZhaJinHua(g) {
    background('#192a31', '#0d1924');
    ellipse(450, 275, 420, 224, '#6b5038');
    ellipse(450, 275, 408, 210, '#15584c', '#dbc08d', 3);
    label('Zha Jin Hua · Three-card poker', 44, 39, 20, '#f4e6c4', 780);
    label('Virtual chips', 858, 39, 14, '#d7c49b', 550, 'right');
    box(326,73,248,139,16,'#0e3438',seatBorder(1,'#d4ae70'),seatActive(1)?3:2);
    label(seatName(1,'Opponent')+' · '+g.stacks[1]+' chips',450,98,14,seatActive(1)?'#216c4e':'#f7e7c9',700,'center',220);
    for (let i = 0; i < 3; i++)
      card(g.opponent_hand?.[i], 363 + i * 64, 118, 55, 77, { face: !!g.showdown, poker: true });
    box(338, 223, 224, 91, 18, '#0a3238', '#d5b878', 2);
    label('Pot', 450, 247, 14, '#bed6c8', 600, 'center');
    label(String(g.pot), 450, 282, 31, '#ffe3a8', 800, 'center');
    label('Round ' + g.round + ' / 5 · Stake ' + g.stake, 450, 341, 15, '#f1dfb6', 650, 'center');
    box(302,372,296,157,17,'#0e3438',seatBorder(0,'#d4ae70'),seatActive(0)?3:2);
    label(seatName(0,'You')+' · '+g.stacks[0]+' chips · '+(g.seen?'Seen':'Blind'),450,395,14,seatActive(0)?'#216c4e':'#f7e7c9',700,'center',270);
    for (let i = 0; i < 3; i++)
      card(g.hand?.[i], 350 + i * 68, 421, 60, 93, { face: !!g.hand, poker: true });
    canvas.setAttribute('aria-label', JevPlayText.ui('Three-card poker. Opponent cards are revealed only at showdown.'));
  }

  function drawPigDice(g) {
    background('#d8d6bf', '#a5b59c');
    box(50, 37, 800, 484, 16, '#f6ebcc', '#406158', 4);
    label('Pig · First to 50', 450, 91, 29, '#24463f', 800, 'center');
    for (const [i, x, color] of [[0, 75, '#16695b'], [1, 533, '#b46b46']]) {
      box(x, 143, 291, 159, 15, '#fffaf0', color, 3);
      label(i === 0 ? 'You' : 'Rule opponent', x + 26, 171, 19, color, 750);
      label(String(g.scores[i]), x + 145, 232, 65, color, 800, 'center');
      label('Banked points', x + 145, 278, 15, '#70857a', 550, 'center');
    }
    box(322, 321, 256, 148, 15, '#28584d', '#1a453e', 2);
    label('Unbanked points', 450, 351, 17, '#e1e9d7', 650, 'center');
    label(String(g.turn_points), 450, 402, 57, '#ffe4a9', 800, 'center');
    label(g.last_roll ? 'Last roll: ' + g.last_roll : 'No roll yet', 450, 449, 15, '#dfecdc', 550, 'center');
    canvas.setAttribute('aria-label', JevPlayText.ui('Pig scoreboard: banked points on each side; unbanked points in the center.'));
  }

  function propertyPanel(x, side, cash, count, position, accent) {
    box(x,169,162,205,17,'#fffaf1ed',seatBorder(side,'#ccbfa5'),seatActive(side)?3:1.5);
    box(x + 64, 181, 34, 34, 13, accent);
    label(side === 0 ? 'Y' : 'R', x + 81, 198, 17, '#fff', 750, 'center');
    label(seatName(side,side===0?'Your assets':'Opponent assets'),x+81,232,13,seatActive(side)?'#216c4e':'#334d45',700,'center',142);
    label('Cash', x + 20, 253, 12, '#52675a');
    label('$' + cash, x + 20, 286, 27, '#243f36', 750);
    ctx.strokeStyle = '#ddd4bf'; ctx.beginPath(); ctx.moveTo(x + 20, 309); ctx.lineTo(x + 142, 309); ctx.stroke();
    label(count + ' properties', x + 20, 337, 14, '#536d5e', 650);
    label('At ' + position, x + 20, 357, 12, '#52675a',500,'left',130);
  }

  function drawProperty(g) {
    background('#e8e1cf', '#d7d2bd');
    ctx.strokeStyle = '#fff8e54d'; ctx.lineWidth = 1;
    for (let i = -H; i < W + H; i += 34) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i + H, H); ctx.stroke();
    }
    const cells = [];
    for (let x = 0; x < 5; x++) cells.push([x, 0]);
    for (let y = 1; y < 5; y++) cells.push([4, y]);
    for (let x = 3; x >= 0; x--) cells.push([x, 4]);
    for (let y = 3; y > 0; y--) cells.push([0, y]);
    const size = 100, ox = 200, oy = 20;
    box(ox - 9, oy - 9, 518, 518, 24, '#b8ac8b', '#fff8e2', 2);
    box(ox - 2, oy - 2, 504, 504, 19, '#ecdfbf');
    cells.forEach(function (cell, i) {
      const x = ox + cell[0] * size, y = oy + cell[1] * size, owner = g.owners[String(i)];
      const special = i === 0 ? 'Start' : [2, 10].includes(i) ? 'Chance' : [4, 12].includes(i) ? 'Tax'
        : [6, 14].includes(i) ? 'Transit' : i === 8 ? 'Rest' : null;
      const fill = owner === 0 ? '#e9f4e9' : owner === 1 ? '#f9eae3' : special === 'Chance' ? '#fff1d7'
        : special === 'Tax' ? '#f9ece6' : '#fffaf0';
      box(x + 4, y + 4, 92, 92, 10, fill, '#cfc3a9');
      box(x + 4, y + 4, 92, 9, 5, owner === 0 ? '#338469' : owner === 1 ? '#d07b64'
        : special === 'Chance' ? '#d8ae62' : '#98ad9b');
      label(g.names[i], x + 50, y + 38, 16, '#243d32', 700, 'center',84);
      const price = g.prices[String(i)];
      label(price ? '$' + price : special || '', x + 50, y + 58, 14, price ? '#3f5d4e' : '#74542d', 600, 'center');
      const level = g.levels[String(i)] || 0;
      if (level) label('◆'.repeat(level), x + 50, y + 79, 11, '#d0a45f', 700, 'center');
      g.positions.forEach(function (position, side) {
        if (position !== i) return;
        const px = x + 31 + side * 39;
        ellipse(px, y + 81, 11, 11, '#fffaf1', '#bbaf96');
        ellipse(px, y + 81, 8, 8, side ? '#d07961' : '#32876d');
        label(side ? 'R' : 'Y', px, y + 81, 8, '#fff', 700, 'center');
      });
    });
    const holdings = [0, 1].map(function (side) {
      return Object.values(g.owners).filter(function (owner) { return owner === side; }).length;
    });
    propertyPanel(20, 0, g.cash[0], holdings[0], JevPlayText.text(g.names[g.positions[0]]), '#34866b');
    propertyPanel(718, 1, g.cash[1], holdings[1], JevPlayText.text(g.names[g.positions[1]]), '#ce7960');
    box(307, 131, 286, 278, 20, '#fffaf2f0', '#d5c8aa', 1.5);
    label('PROPERTY TOUR', 450, 160, 11, '#9c9a7d', 750, 'center');
    label('Property Tycoon', 450, 204, 30, '#2d644f', 760, 'center');
    box(368, 224, 164, 37, 18, '#e8efe3');
    label('Round ' + g.round + ' / 20', 450, 242, 14, '#4a7965', 750, 'center');
    ctx.strokeStyle = '#ddd2bb'; ctx.beginPath(); ctx.moveTo(339, 277); ctx.lineTo(561, 277); ctx.stroke();
    box(404, 293, 92, 70, 13, '#2d7962', '#24614e', 1.5);
    label(g.dice == null ? '—' : g.dice, 450, 326, 34, '#fff8e7', 780, 'center');
    label('Last roll', 450, 380, 12, '#789282', 600, 'center');
    label(g.phase === 'buy' ? 'Buy this property' : g.phase === 'build' ? 'Upgrade this property'
      : g.phase === 'roll' ? 'Roll to move' : 'End turn', 450, 397, 12, '#4f6a5d', 650, 'center');
    canvas.setAttribute('aria-label', JevPlayText.ui('Property Tycoon. You are green; your opponent is orange.'));
  }

  function publicAnimation(duration, token, draw) {
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    return new Promise(resolve=>{let started=null;function frame(now){if(token!==animationEpoch){resolve(false);return;}if(started===null)started=now;const progress=reduced?1:Math.min(1,(now-started)/duration);draw(progress);if(progress<1)requestAnimationFrame(frame);else resolve(true);}requestAnimationFrame(frame);});
  }
  window.JevCardTable = {
    stop(){++animationEpoch;animationRunning=false;},
    supports(kind){return kind==='doudizhu'||kind==='texas_holdem';},
    async animate(before,after){
      const token=++animationEpoch;animationRunning=true;
      try{
        if(after.kind==='doudizhu'){
          let table=publicTable(before,false);
          const plays=newPublicPlays(before,after);
          for(const play of plays){const next=applyPublicPlay(table,play);const finished=await publicAnimation(play.pass?180:280,token,progress=>PlayDraw.draw(after,{cardTable:next,cardFlight:{...play,progress},cardAnimation:true}));if(!finished)return;table=next;}
          tableCache={key:tableKey(after),steps:after.steps,history:structuredClone(after.history||[]),table:cloneTable(table)};
          PlayDraw.draw(after,{cardTable:table,cardAnimation:true});
        }else{
          const added=Math.max(0,after.board.length-before.board.length),duration=330+Math.max(0,added-1)*75;
          if(added)await publicAnimation(duration,token,progress=>PlayDraw.draw(after,{pokerAnimation:{previousCount:before.board.length,elapsed:duration*progress},cardAnimation:true}));
          else PlayDraw.draw(after,{cardAnimation:true});
        }
      }finally{if(token===animationEpoch)animationRunning=false;}
    }
  };

  PlayDraw.draw = function (g, extra = {}) {
    if(g.duel && g.table) g=g.table;
    if(animationRunning&&!extra.cardAnimation){++animationEpoch;animationRunning=false;}
    if (!socialKinds.has(g.kind)) { lastGame = null; canvas.onclick = null; canvas.style.removeProperty('image-rendering'); ctx.setTransform(1,0,0,1,0,0); return originalDraw(g, extra); }
    lastGame = g; prepareCanvas();
    brightTable = ['doudizhu', 'texas_holdem', 'zha_jin_hua'].includes(g.kind);
    cardHits = []; ctx.clearRect(0, 0, W, H);
    if (g.kind === 'doudizhu') drawDoudizhu(g,extra);
    else if (g.kind === 'texas_holdem') drawPoker(g,extra);
    else if (g.kind === 'zha_jin_hua') drawZhaJinHua(g);
    else if (g.kind === 'pig_dice') drawPigDice(g);
    else drawProperty(g);
    if(g.duel){canvas.setAttribute('aria-label',(g.seat_ids||[0,1]).map((_,i)=>seatName(i)).join('; ')+'; '+canvas.getAttribute('aria-label'));canvas.dataset.viewSeat=String(g.view_seat);canvas.dataset.activeSeat=String(g.active_seat);}
    canvas.onclick = function (event) {
      if (g.kind !== 'doudizhu' || showcaseBusy || g.outcome || g.handoff || (g.duel && !window.JevParticipants?.canAct())) return;
      const bounds = canvas.getBoundingClientRect();
      const x = (event.clientX - bounds.left) * W / bounds.width;
      const y = (event.clientY - bounds.top) * H / bounds.height;
      const hit = cardHits.slice().reverse().find(function (item) {
        return x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h;
      });
      if (!hit) return;
      cardSelection = cardSelection.includes(hit.i)
        ? cardSelection.filter(function (i) { return i !== hit.i; }) : cardSelection.concat(hit.i);
      PlayDraw.draw(g); window.updateCardAction && window.updateCardAction();
    };
  };
  // Redraw when moving between screens with different pixel densities.
  window.addEventListener('resize', () => {
    if (lastGame && canvas.getClientRects().length && !animationRunning) PlayDraw.draw(lastGame);
  });
})();
