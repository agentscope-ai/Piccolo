/* Mario UI adapter: rendering and human input only. Rules execute in JevMarioCore. */
(() => {
  'use strict';
  const uiLocale=(()=>{try{return window.parent.JevI18n||window.JevI18n;}catch{return window.JevI18n;}})();
  const tr=(en,zh)=>uiLocale?.t(en,zh)??en;
  const replayOnly=new URLSearchParams(location.search).get('replay')==='1'||!!window.__JEV_REPLAY_FRAME__;
  const canvas=document.getElementById('game'),ctx=canvas.getContext('2d'),T=32,H=14,FLOOR=11;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  let W,GOAL,tiles,coins,enemies,plants,powerups,popups,p,camera,frame,collected,powerupsCollected,score,outcome,event,decisions,active,locked,modelStepping,modelAwaiting,remaining;
  let core, replayState=null;
  const pointers=new Map(),keys=new Set(),testHooks=window.__JEV_TEST_MODE__?{}:undefined;
  window.JevVisibleControl=window.JevMarioCore.visibleControl;
  function syncState(){if(!core)return;({W,GOAL,tiles,coins,enemies,plants,powerups,popups,p,camera,frame,collected,powerupsCollected,score,outcome,event,decisions,active,locked,modelStepping,modelAwaiting,remaining}=replayState||core.renderState());}
  const tile=(x,y)=>x<0||x>=W?1:y<0||y>=H?0:tiles[y][x];
  const solid=(x,y)=>tile(x,y)>0;
  const plantBody=plant=>plant.replayBody||plant;
  const snapshot=(...args)=>core.snapshot(...args);
  function publish(){if(!replayOnly&&window.parent!==window)window.parent.postMessage({type:'jev-mario-state',observation:snapshot()},window.location.origin);}
  function repaint(){if(!core)return;syncState();hud();draw();publish();}
  core=window.JevMarioCore.create({seedModule:window.JevWorldSeed,now:()=>performance.now(),viewportWidth:canvas.width,onChange:repaint,testHooks});
  function clearKeys(){keys.clear();pointers.clear();core.clearInput();document.querySelectorAll('[data-key]').forEach(b=>b.classList.remove('held'));}
  function release(){core.release();clearKeys();repaint();}
  const held=k=>keys.has(k)||[...pointers.values()].includes(k);
  // Keep model observations unchanged; translate only visible event text.
  const eventLabels={"前往旗杆；顶问号方块取奖励，避开管道里的食人花": "Reach the flag. Hit ? blocks for rewards and avoid Piranha Plants.", "问号方块弹出蘑菇；碰到它可挡住一次伤害": "Mushroom released. Collect it for a shield.", "问号方块弹出金币 +1": "Coin from ? block +1", "顶碎砖块": "Brick broken", "蘑菇护盾挡住一次伤害": "Shield absorbed a hit", "拿到蘑菇：护盾可挡一次敌人或食人花伤害": "Mushroom collected · Shield ready", "收集金币 +1": "Coin collected +1", "踩退敌人 +200": "Enemy defeated +200", "碰到敌人了，再试一次": "Hit an enemy. Try again.", "碰到食人花了，再试一次": "Hit a Piranha Plant. Try again.", "落入深坑，再试一次": "Fell into a pit. Try again.", "抵达旗杆，闯关成功！": "Flag reached. Level complete!"};
  const eventLabel=value=>tr(eventLabels[value]||value,value);
  function hud(){
    document.getElementById('coins').textContent=String(collected).padStart(2,'0');
    document.getElementById('powerup').textContent=p&&p.shield?tr("Shield · 1 hit","护盾 · 1 次"):tr("No shield","无护盾");
    document.getElementById('progress').textContent=(p?snapshot().progress:0)+'%';
    document.getElementById('event').textContent=eventLabel(event);
    document.getElementById('hint').textContent=outcome?eventLabel(event):modelStepping?(remaining?tr("Model intent · Until event/deadline","模型意图 · 至事件/期限"):locked?tr("Paused · Waiting for model","已暂停 · 等待模型"):tr("Paused · Arrow keys to resume","已暂停 · 方向键恢复")):modelAwaiting?tr("Model thinking · World continues","模型思考中 · 世界继续运行"):tr("← → / A D move · Space / W jump","← → / A D 移动 · 空格 / W 跳跃");
    document.querySelectorAll('[data-key]').forEach(b=>b.disabled=locked||!!outcome);
  }
  function rect(x,y,w,h,color){ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),w,h);}
  function cloud(x,y,s){ctx.fillStyle='#f8fcf1';for(const [dx,dy,r] of [[0,4,16],[20,-6,24],[43,3,18]]){ctx.beginPath();ctx.arc(x+dx*s,y+dy*s,r*s,0,Math.PI*2);ctx.fill();}}
  function draw(){
    const w=canvas.width,h=canvas.height,scale=h/(H*T);ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,w,h);
    const sky=ctx.createLinearGradient(0,0,0,h);sky.addColorStop(0,'#addde5');sky.addColorStop(1,'#e5f1c9');ctx.fillStyle=sky;ctx.fillRect(0,0,w,h);
    ctx.save();ctx.scale(1,scale);
    for(let i=-1;i<8;i++){const x=i*240-camera*.18;cloud(x+70+(frame*.12%240),66+(i%3)*26,.8);ctx.fillStyle=i%2?'#a7cda7':'#bad8b4';ctx.beginPath();ctx.moveTo(x-100,352);ctx.quadraticCurveTo(x+65,140,x+200,352);ctx.fill();}
    for(let i=0;i<15;i++){const x=i*200-camera*.5;ctx.fillStyle='#7eb895';ctx.beginPath();ctx.ellipse(x,349,70,33,0,0,Math.PI*2);ctx.fill();}
    const a=Math.max(0,Math.floor(camera/T)),b=Math.min(W,Math.ceil((camera+w)/T));
    for(let y=0;y<H;y++)for(let x=a;x<b;x++){
      const t=tiles[y][x],sx=x*T-camera,sy=y*T;if(!t)continue;
      if(t===1){rect(sx,sy,32,32,'#ba8660');rect(sx+1,sy+3,30,2,'#dca878');rect(sx+8,sy+12,5,3,'#a67456');rect(sx+23,sy+24,5,3,'#a67456');if(!solid(x,y-1)){rect(sx,sy,32,8,'#548e52');rect(sx,sy,32,3,'#8fc95e');rect(sx+5,sy+8,4,4,'#548e52');}}
      else if(t===3){rect(sx,sy,32,32,'#438656');rect(sx+4,sy,7,32,'#7dbb69');rect(sx+26,sy,4,32,'#2f6747');if(tile(x,y-1)!==3){rect(sx-2,sy,36,10,'#387747');rect(sx,sy+2,32,3,'#a2d479');}}
      else{rect(sx+1,sy+1,30,30,t===4?'#f4c85c':t===5?'#a49b79':'#c87d53');rect(sx+2,sy+2,28,3,t===4?'#ffeaa5':'#e7b183');rect(sx+2,sy+27,28,3,'#9c6748');if(t===4){ctx.font='bold 24px "Jev Comic", "Noto Sans CJK SC", sans-serif';ctx.fillStyle='#99672c';ctx.textAlign='center';ctx.fillText('?',sx+16,sy+25);}if(t===2){rect(sx,sy+15,32,2,'#965c41');rect(sx+15,sy,2,15,'#965c41');rect(sx+7,sy+17,2,14,'#965c41');}}
    }
    for(const c of coins)if(!c.taken&&c.x>camera-32&&c.x<camera+w){const sx=c.x-camera;ctx.fillStyle='#ffdc63';ctx.beginPath();ctx.ellipse(sx+6,c.y+9,7,11,0,0,Math.PI*2);ctx.fill();rect(sx+5,c.y+3,3,12,'#c59531');rect(sx+2,c.y+3,2,8,'#fff1a4');}
    for(const plant of plants){const b=plantBody(plant);if(b.x-camera<-30||b.x-camera>w)continue;
      const x=b.x-camera,y=b.y;
      if(!b.emerged){
        // Keep a visible warning at the pipe mouth while the hitbox is retracted.
        rect(x+10,(FLOOR-2)*T-10,10,10,'#3e9b54');
        rect(x+4,(FLOOR-2)*T-12,22,8,'#d95b57');
        rect(x+8,(FLOOR-2)*T-14,14,4,'#f29a75');
        continue;
      }
      // Clip the sprite to the pipe mouth so the visible plant and its hitbox agree.
      ctx.save();ctx.beginPath();ctx.rect(x,y,b.w,b.h);ctx.clip();
      rect(x+12,y+17,6,Math.max(4,b.h-17),'#3e9b54');
      rect(x+2,y+4,26,20,'#d95b57');rect(x+5,y,20,7,'#f29a75');
      rect(x+2,y+15,26,6,'#fff1d2');
      rect(x+7,y+15,4,5,'#fff');rect(x+19,y+15,4,5,'#fff');
      rect(x+7,y+8,4,4,'#f5e7d4');rect(x+19,y+8,4,4,'#f5e7d4');
      ctx.restore();
    }
    for(const reward of powerups)if(!reward.taken&&reward.x-camera>-30&&reward.x-camera<w){const x=reward.x-camera,y=reward.y;
      rect(x+2,y+8,18,13,'#f4dfb0');rect(x,y+2,22,11,'#d74e48');rect(x+3,y,16,4,'#f3916f');
      rect(x+5,y+5,4,5,'#fff7e7');rect(x+14,y+5,4,5,'#fff7e7');rect(x+6,y+13,2,4,'#4d5444');rect(x+15,y+13,2,4,'#4d5444');
    }
    for(const popup of popups)if(popup.kind==='coin'){const x=popup.x-camera;rect(x,popup.y,12,17,'#ffd65d');rect(x+4,popup.y+3,3,11,'#b57b2b');}
    const flag=GOAL-camera;rect(flag,128,5,224,'#e6eadb');rect(flag-3,122,11,11,'#d7ad55');ctx.fillStyle='#e57357';ctx.beginPath();ctx.moveTo(flag+5,135);ctx.lineTo(flag+65,153);ctx.lineTo(flag+5,172);ctx.fill();rect(flag-10,342,25,10,'#8f9b7b');
    for(const e of enemies)if(e.alive){const x=e.x-camera,y=e.y;rect(x+2,y+4,22,15,'#9b6151');rect(x+5,y,16,7,'#bb7d60');rect(x+6,y+8,5,7,'#fff3cf');rect(x+16,y+8,5,7,'#fff3cf');rect(x+8,y+10,2,5,'#3d4134');rect(x+16,y+10,2,5,'#3d4134');rect(x,y+19,10,5,'#493f36');rect(x+16,y+19,10,5,'#493f36');}
    const px=Math.round(p.x-camera),py=Math.round(p.y),stride=p.on_ground&&p.vx?Math.floor(frame/5)%2*3:0;
    ctx.save();ctx.translate(px+(p.facing<0?p.w:0),py);ctx.scale(p.facing,1);
    rect(3,0,17,5,'#d95548');rect(1,4,23,4,'#d95548');rect(5,8,15,9,'#f2c391');rect(2,8,6,8,'#775443');rect(16,9,3,4,'#334638');rect(17,14,6,3,'#775443');rect(3,17,18,6,'#d95548');rect(7,17,3,9,'#4b7094');rect(17,17,3,9,'#4b7094');rect(7,23,13,5,'#4b7094');rect(0,19,5,7,'#f2c391');rect(5-stride,28,9,3,'#594b42');rect(15+stride,28,9,3,'#594b42');ctx.restore();
    if(p.shield){ctx.strokeStyle='#ffcf62';ctx.lineWidth=3;ctx.strokeRect(px-3,py-3,p.w+6,p.h+6);}
    if(outcome){ctx.fillStyle='#183d3cb3';ctx.fillRect(0,0,w,H*T);ctx.textAlign='center';ctx.fillStyle='#fff8df';ctx.font='bold 28px "Jev Comic", "Noto Sans CJK SC", sans-serif';ctx.fillText(outcome==='win'?tr("Level complete!","闯关成功！"):tr("Try again","再试一次"),w/2,202);ctx.font='14px "Jev Comic", "Noto Sans CJK SC", sans-serif';ctx.fillText(eventLabel(event),w/2,237);ctx.fillText(tr("Select Restart to play again","点击重新开局再玩一局"),w/2,265);}
    ctx.restore();
  }
  function tick(ts){if(replayOnly)return;requestAnimationFrame(tick);core.setVisibility(document.hidden);core.tick(ts);syncState();draw();}
  function focus(){canvas.focus({preventScroll:true});}
  function keyName(key){return ({ArrowLeft:'left',a:'left',ArrowRight:'right',d:'right',' ':'jump',ArrowUp:'jump',w:'jump'})[key.length===1?key.toLowerCase():key];}
  canvas.addEventListener('pointerdown',focus);
  document.addEventListener('keydown',e=>{if(!active||locked||outcome||e.ctrlKey||e.metaKey||e.altKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;const k=keyName(e.key);if(!k)return;e.preventDefault();if(modelStepping)release();keys.add(k);core.setInput(k,true,!e.repeat);});
  document.addEventListener('keyup',e=>{const k=keyName(e.key);if(k){keys.delete(k);if(!held(k))core.setInput(k,false);e.preventDefault();}});
  window.addEventListener('blur',clearKeys);document.addEventListener('visibilitychange',()=>{if(document.hidden)clearKeys();});
  document.querySelectorAll('[data-key]').forEach(button=>{
    button.addEventListener('pointerdown',e=>{if(!active||locked||outcome||e.button>0)return;e.preventDefault();if(modelStepping)release();focus();pointers.set(e.pointerId,button.dataset.key);button.classList.add('held');core.setInput(button.dataset.key,true);button.setPointerCapture(e.pointerId);});
    const up=e=>{pointers.delete(e.pointerId);if(!held(button.dataset.key)){core.setInput(button.dataset.key,false);button.classList.remove('held');}};
    for(const type of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(type,up);
    button.addEventListener('click',e=>{if(e.detail===0&&!locked&&!outcome){release();window.JevMario.act(button.dataset.key==='jump'?'jump':button.dataset.key);}});
  });
  function fit(){if(replayOnly)return;canvas.width=Math.max(280,Math.min(920,document.getElementById('wrap').clientWidth));canvas.height=canvas.width<520?320:448;ctx.imageSmoothingEnabled=false;if(p){core.setViewport(canvas.width);syncState();draw();}}
  window.addEventListener('resize',fit);
  window.JevMario={...core,
    reset(...args){const state=core.reset(...args);clearKeys();replayState=null;return state;},
    release,
    activate(value){core.activate(value);if(!value)clearKeys();syncState();}
  };
  if(testHooks)Object.assign(window.JevMario,testHooks);
  fit();syncState();repaint();
  // Replay renders recorded observations with the same sprites, without running physics.
  if(replayOnly)window.JevMario.renderReplay=function(s){
    if(!s?.player||!s?.map?.tiles)return;
    core.activate(false);syncState();active=false;clearKeys();
    if(Number.isFinite(s.goal_x)&&s.goal_x>2*T){GOAL=s.goal_x;W=Math.ceil(GOAL/T)+5;}
    tiles=Array.from({length:H},()=>Array(W).fill(0));
    const [ox,oy]=s.map.origin||[0,0];
    s.map.tiles.forEach((row,y)=>row.forEach((v,x)=>{if(y+oy>=0&&y+oy<H&&x+ox>=0&&x+ox<W)tiles[y+oy][x+ox]=Math.max(0,v);}));
    p={...s.player,w:s.player.width||23,h:s.player.height||30,invulnerable_until:0};
    frame=s.frame||0;camera=clamp(p.x-canvas.width*.32,0,W*T-canvas.width);
    enemies=(s.enemies||[]).map(e=>({...e,w:e.width||26,h:e.height||24,alive:true}));
    plants=(s.plants||[]).map(b=>({replayBody:{...b,w:b.width,h:b.height}}));
    coins=(s.coins||[]).map(e=>({...e,taken:false}));powerups=(s.powerups||[]).map(e=>({...e,taken:false}));popups=[];
    outcome=s.outcome||null;event=s.event||'';collected=s.collected||0;score=s.score||0;decisions=s.decisions||0;
    draw();
  };
  function repaintLocale(){
    document.documentElement.lang=uiLocale?.lang==='zh'?'zh-CN':'en';
    document.title=tr('Mario · Green Hills','马里奥 · 绿野');
    const labels=[['.hud > div:nth-child(1) small',tr('COINS','金币')],['.hud > div:nth-child(2) small',tr('POWER','护盾')],['.hud > div:nth-child(3) small',tr('PROGRESS','进度')],['.hud .level small',tr('GREEN HILLS','绿野')],['.hud .level b',tr('Level 01','第 01 关')],['[data-key="jump"]',tr('Jump ↑','跳跃 ↑')]];
    for(const [selector,label] of labels){const node=document.querySelector(selector);if(node)node.textContent=label;}
    canvas.setAttribute('aria-label',tr('Mario. Arrow keys move, Space jumps. Hit question blocks for rewards and avoid Piranha Plants.','马里奥。方向键移动，空格跳跃；顶问号方块拿奖励，避开食人花。'));
    document.querySelector('[data-key="left"]').setAttribute('aria-label',tr('Hold to move left','按住向左移动'));
    document.querySelector('[data-key="right"]').setAttribute('aria-label',tr('Hold to move right','按住向右移动'));
    hud();draw();
  }
  repaintLocale();
  const stopLocale=uiLocale?.onChange(repaintLocale);
  window.addEventListener('pagehide',()=>{if(typeof stopLocale==='function')stopLocale();},{once:true});
  requestAnimationFrame(tick);
})();
