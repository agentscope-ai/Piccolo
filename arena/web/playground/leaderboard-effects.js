/* Presentation-only particle field. Bounded work; never touches game state or input. */
(function () {
  'use strict';
  if (document.getElementById('lbPixelAtmosphere')) return;
  const byId = id => document.getElementById(id);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const active = () => ['leaderboardView','blogView','gamesView'].some(id => byId(id) && !byId(id).classList.contains('hidden'));
  const enabled = () => active() && !document.hidden && !reduced.matches;
  const layer = document.createElement('div');
  layer.id='lbPixelAtmosphere';layer.className='lb-pixel-atmosphere';
  layer.setAttribute('aria-hidden','true');layer.inert=true;
  const canvas=document.createElement('canvas');canvas.className='lb-particle-network';layer.appendChild(canvas);
  const ctx=canvas.getContext('2d');
  for(let i=0;i<6;i++){
    const dot=document.createElement('i');
    dot.style.cssText='--x:'+((i*37+3)%100)+'%;--y:'+((i*23+8)%100)+'%;--size:'+(i%2?3:4)+'px;--delay:'+(-i*2.3)+'s;--duration:'+(24+i%5*6)+'s';
    layer.appendChild(dot);
  }
  const fx=document.createElement('div');fx.id='lbPixelEffects';fx.className='lb-pixel-effects';
  fx.setAttribute('aria-hidden','true');fx.inert=true;
  document.body.prepend(layer);document.body.appendChild(fx);
  let width=0,height=0,points=[],frame=0,lastFrame=0,elapsed=0;
  const pointer={x:-1000,y:-1000};
  function draw(){
    if(!ctx)return;
    ctx.clearRect(0,0,width,height);
    const moving=!reduced.matches;
    const nodes=points.map((p,i)=>{
      let x=p.x+Math.sin(elapsed*.17+i*1.7)*(moving?13:0),y=p.y+Math.cos(elapsed*.12+i*.9)*(moving?16:0);
      const distance=Math.hypot(x-pointer.x,y-pointer.y);
      if(moving&&distance<180){const pull=(1-distance/180)*.04;x+=(pointer.x-x)*pull;y+=(pointer.y-y)*pull;}
      return {x,y,size:p.size,accent:i%9===0};
    });
    const limit=width<600?125:190;
    for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
      const a=nodes[i],b=nodes[j],distance=Math.hypot(a.x-b.x,a.y-b.y);
      if(distance>=limit)continue;
      ctx.strokeStyle='rgba(99,133,126,'+(.19*(1-distance/limit))+')';ctx.lineWidth=.7;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    }
    for(const n of nodes){
      const near=moving&&Math.hypot(n.x-pointer.x,n.y-pointer.y)<150;
      ctx.fillStyle=n.accent?'rgba(185,110,80,'+(near?.7:.43)+')':'rgba(104,140,132,'+(near?.7:.36)+')';
      ctx.fillRect(n.x,n.y,n.size,n.size);
      if(near){ctx.strokeStyle='rgba(185,110,80,.15)';ctx.lineWidth=.7;ctx.strokeRect(n.x-4,n.y-4,n.size+8,n.size+8);}
    }
  }
  function loop(now){
    frame=0;if(!enabled())return;
    if(now-lastFrame>=32){elapsed+=Math.min(100,now-lastFrame)/1000;lastFrame=now;draw();}
    frame=requestAnimationFrame(loop);
  }
  function resize(){
    width=window.innerWidth;height=window.innerHeight;
    const dpr=Math.min(window.devicePixelRatio||1,1.5);
    canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
    if(ctx)ctx.setTransform(dpr,0,0,dpr,0,0);
    const count=width<600?22:42;
    points=Array.from({length:count},(_,i)=>({x:((i*137.508+31)%1000)/1000*width,y:((i*231.73+19)%1000)/1000*height,size:i%5===0?3:2}));
    draw();
  }
  let serial=0,lastAt=0,lastX=-100,lastY=-100;
  function pixel(x,y,dx,dy,size,color,delay=0){
    while(fx.childElementCount>=36)fx.firstElementChild.remove();
    const dot=document.createElement('i');dot.className='lb-cursor-pixel';
    dot.style.cssText='left:'+x+'px;top:'+y+'px;--dx:'+dx+'px;--dy:'+dy+'px;--size:'+size+'px;--color:'+color+';animation-delay:'+delay+'ms';
    fx.appendChild(dot);dot.addEventListener('animationend',()=>dot.remove(),{once:true});
    setTimeout(()=>dot.remove(),1100+delay);
  }
  document.addEventListener('pointermove',event=>{
    if(!enabled()||event.pointerType==='touch'||event.buttons||event.target.closest('.brand,canvas,iframe,input,textarea,select,.scene-controls,.dpad,.selected-game')){pointer.x=pointer.y=-1000;return;}
    pointer.x=event.clientX;pointer.y=event.clientY;
    if(!event.target.closest('.mast,.tabs,.blog-heading,.lb-heading,.lb-radar-heading,.playground-heading'))return;
    const now=performance.now();if(now-lastAt<85||Math.hypot(event.clientX-lastX,event.clientY-lastY)<12)return;
    lastAt=now;lastX=event.clientX;lastY=event.clientY;const i=serial++;
    pixel(lastX-2,lastY+8,(i%2?-1:1)*(9+i%8),12+i%12,i%4?3:4,i%3?'#91a89e':'#b96e50');
  },{passive:true});
  window.addEventListener('oneshot:wind',event=>{
    if(!enabled())return;
    const {x,y,direction}=event.detail;
    for(let i=0;i<7;i++)pixel(x-direction*(24+i*4),y-13+i*4,direction*(45+i*6),-5+(i%3)*3,i%3?2:3,i%3?'#9bb2a8':'#b96e50',i*15);
  });
  document.documentElement.addEventListener('pointerleave',()=>{pointer.x=pointer.y=-1000;},{passive:true});
  function sync(){
    if(frame){cancelAnimationFrame(frame);frame=0;}
    const running=enabled();layer.classList.toggle('is-paused',!running);layer.dataset.animated=String(running);
    if(!running)fx.replaceChildren();
    if(running&&ctx){lastFrame=performance.now();frame=requestAnimationFrame(loop);}else draw();
  }
  const observer=new MutationObserver(sync);
  ['leaderboardView','blogView','gamesView'].forEach(id=>byId(id)&&observer.observe(byId(id),{attributes:true,attributeFilter:['class']}));
  window.addEventListener('resize',resize,{passive:true});
  document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);
  window.JevI18n?.onChange(sync);resize();sync();
})();

/* Page-mask grains: bounded paint snapshots; live games and input stay in place. */
(function () {
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'),jobs=new Map();
  const canvas=document.createElement('canvas');canvas.id='fsSandCanvas';canvas.className='fs-sand-canvas';
  canvas.setAttribute('aria-hidden','true');canvas.inert=true;canvas.dataset.active='0';
  const ctx=canvas.getContext('2d');if(!ctx)return;
  document.body.appendChild(canvas);
  let frame=0,width=0,height=0;
  const clamp=n=>Math.max(0,Math.min(1,n)),smooth=n=>{n=clamp(n);return n*n*(3-2*n);};
  const noise=n=>{const value=Math.sin(n*12.9898+78.233)*43758.5453;return value-Math.floor(value);};
  function restore(job){job.node.style.opacity=job.opacity;jobs.delete(job.node);}
  function cancel(){
    if(frame)cancelAnimationFrame(frame);frame=0;
    for(const job of jobs.values())restore(job);
    ctx.clearRect(0,0,width,height);canvas.dataset.active='0';
  }
  function resize(){
    cancel();width=innerWidth;height=innerHeight;
    const dpr=Math.min(devicePixelRatio||1,1.5);
    canvas.width=Math.ceil(width*dpr);canvas.height=Math.ceil(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
  }
  function mask(node){
    const rect=node.getBoundingClientRect(),style=getComputedStyle(node),text=node.textContent.trim();
    const box={x:Math.max(0,rect.x),y:Math.max(0,rect.y),width:Math.min(width,rect.right)-Math.max(0,rect.x),height:Math.min(height,rect.bottom)-Math.max(0,rect.y)};
    if(box.width<1||box.height<1)return null;
    const bitmap=document.createElement('canvas'),scale=2,w=Math.ceil(box.width)+4,h=Math.ceil(box.height)+4;
    bitmap.width=w*scale;bitmap.height=h*scale;
    const paint=bitmap.getContext('2d',{willReadFrequently:true});if(!paint)return null;
    paint.scale(scale,scale);paint.textBaseline='alphabetic';
    const regions=[{root:node,dx:0,dy:0}],clip={left:box.x,top:box.y,right:box.x+box.width,bottom:box.y+box.height};
    function visible(el,dx,dy){
      const r=el.getBoundingClientRect(),face=getComputedStyle(el);
      return r.width&&r.height&&r.right+dx>clip.left&&r.left+dx<clip.right&&r.bottom+dy>clip.top&&r.top+dy<clip.bottom&&face.visibility!=='hidden'&&face.display!=='none';
    }
    function drawElement(el,dx,dy){
      if(!visible(el,dx,dy))return;
      const r=el.getBoundingClientRect(),face=getComputedStyle(el),x=r.x+dx-box.x+2,y=r.y+dy-box.y+2;
      if(el instanceof SVGElement)return; // Render SVG shapes together below.
      paint.save();
      const radius=Math.min(parseFloat(face.borderRadius)||0,r.width/2,r.height/2);
      paint.beginPath();paint.roundRect(x,y,r.width,r.height,radius);
      let fill=face.backgroundColor;
      if(fill==='rgba(0, 0, 0, 0)'&&face.backgroundImage!=='none'){
        fill=face.backgroundImage.match(/#[0-9a-f]{3,8}\b|rgba?\([^)]+\)/i)?.[0]||fill;
      }
      if(fill!=='rgba(0, 0, 0, 0)'){paint.fillStyle=fill;paint.fill();}
      if(parseFloat(face.borderTopWidth)>0){paint.strokeStyle=face.borderTopColor;paint.lineWidth=parseFloat(face.borderTopWidth);paint.stroke();}
      if(el.tagName==='CANVAS'&&el.width&&el.height){
        try{paint.drawImage(el,x,y,r.width,r.height);}catch{} // Unreadable surfaces keep their frame/background.
      }else if(el.tagName==='IMG'&&el.complete&&el.naturalWidth){
        try{if(new URL(el.currentSrc,location.href).origin===location.origin)paint.drawImage(el,x,y,r.width,r.height);}catch{}
      }else if(el.tagName==='IFRAME'){
        // Same-origin world frames share the actual rendered canvas; no game
        // reset, simulation or model request is needed for this snapshot.
        try{const doc=el.contentDocument;if(doc?.body)regions.push({root:doc.body,dx:dx+r.x+el.clientLeft,dy:dy+r.y+el.clientTop});}catch{}
      }else if(el.tagName==='INPUT'||el.tagName==='TEXTAREA'||el.tagName==='SELECT'){
        paint.fillStyle=face.color;paint.font=face.font;
        const value=el.tagName==='SELECT'?el.selectedOptions[0]?.textContent:el.type==='password'?'':el.value||el.placeholder;
        if(value)paint.fillText(value,x+parseFloat(face.paddingLeft||0),y+r.height*.67,r.width-12);
      }
      paint.restore();
    }
    for(let region=0;region<regions.length&&region<8;region++){
      const {root,dx,dy}=regions[region];
      for(const el of [root,...root.querySelectorAll('*')])drawElement(el,dx,dy);
      for(const svg of root.querySelectorAll('svg')){
        if(!visible(svg,dx,dy))continue;
        for(const shape of svg.querySelectorAll('path,line,rect,circle,ellipse,polyline,polygon')){
          const matrix=shape.getScreenCTM(),face=getComputedStyle(shape);if(!matrix||face.visibility==='hidden')continue;
          let path;const n=k=>Number(shape.getAttribute(k)||0);
          try{
            if(shape.tagName==='path')path=new Path2D(shape.getAttribute('d')||'');
            else{path=new Path2D();if(shape.tagName==='line'){path.moveTo(n('x1'),n('y1'));path.lineTo(n('x2'),n('y2'));}
              else if(shape.tagName==='rect')path.rect(n('x'),n('y'),n('width'),n('height'));
              else if(shape.tagName==='circle'||shape.tagName==='ellipse')path.ellipse(n('cx'),n('cy'),n(shape.tagName==='circle'?'r':'rx'),n(shape.tagName==='circle'?'r':'ry'),0,0,Math.PI*2);
              else{const points=(shape.getAttribute('points')||'').trim().split(/[\s,]+/).map(Number);for(let i=0;i<points.length-1;i+=2)i?path.lineTo(points[i],points[i+1]):path.moveTo(points[i],points[i+1]);if(shape.tagName==='polygon')path.closePath();}
            }
            paint.save();paint.transform(matrix.a,matrix.b,matrix.c,matrix.d,matrix.e+dx-box.x+2,matrix.f+dy-box.y+2);
            if(face.fill!=='none'){paint.fillStyle=face.fill.startsWith('url(')?'#6d9287':face.fill;paint.fill(path);}
            if(face.stroke!=='none'){paint.strokeStyle=face.stroke.startsWith('url(')?'#6d9287':face.stroke;paint.lineWidth=parseFloat(face.strokeWidth)||1;paint.stroke(path);}
            paint.restore();
          }catch{}
        }
      }
    }
    // Sample rendered line positions, including wrapped subtitles and CJK fallback fonts.
    for(const {root,dx,dy} of regions){
    const walker=root.ownerDocument.createTreeWalker(root,NodeFilter.SHOW_TEXT),range=root.ownerDocument.createRange();
    let textNode;
    while((textNode=walker.nextNode())){
      const face=getComputedStyle(textNode.parentElement),lines=[];
      const bounds=textNode.parentElement.getBoundingClientRect();
      if(!visible(textNode.parentElement,dx,dy))continue;
      const matrix=textNode.parentElement instanceof SVGElement?textNode.parentElement.getScreenCTM():null,scale=matrix?Math.hypot(matrix.a,matrix.b):1;
      paint.font=face.fontWeight+' '+(parseFloat(face.fontSize)*scale)+'px '+face.fontFamily;
      paint.letterSpacing=face.letterSpacing==='normal'?'0px':(parseFloat(face.letterSpacing)*scale)+'px';paint.fillStyle=face.color;
      for(let index=0;index<textNode.length;){
        const char=String.fromCodePoint(textNode.data.codePointAt(index));
        range.setStart(textNode,index);range.setEnd(textNode,index+char.length);index+=char.length;
        const rect=range.getBoundingClientRect();if(!rect.width||!rect.height)continue;
        const last=lines[lines.length-1];
        if(last&&Math.abs(last.y-rect.y)<1)last.text+=char;else lines.push({x:rect.x,y:rect.y,height:rect.height,text:char});
      }
      for(const line of lines){
        const metrics=paint.measureText(line.text),ascent=metrics.fontBoundingBoxAscent||parseFloat(face.fontSize)*.8,descent=metrics.fontBoundingBoxDescent||parseFloat(face.fontSize)*.2;
        paint.fillText(line.text,2+line.x+dx-box.x,2+line.y+dy-box.y+(line.height-ascent-descent)/2+ascent);
      }
    }
    }
    let pixels;try{pixels=paint.getImageData(0,0,bitmap.width,bitmap.height).data;}catch{return null;}
    const grains=[],sampleStep=Math.max(1.5,Math.sqrt(w*h/20000));
    for(let y=1;y<h-1;y+=sampleStep)for(let x=1;x<w-1;x+=sampleStep){
      const offset=(Math.floor(y*scale)*bitmap.width+Math.floor(x*scale))*4,alpha=pixels[offset+3]/255;
      if(alpha>.18)grains.push({x,y,alpha,color:'rgb('+pixels[offset]+','+pixels[offset+1]+','+pixels[offset+2]+')'});
    }
    const large=box.height>100,cap=large?(width<600?2500:5000):(width<600?360:600),stride=Math.max(1,Math.ceil(grains.length/cap));
    return {bitmap,w,h,box:{x:box.x-2,y:box.y-2},color:style.color,grains:grains.filter((_,i)=>i%stride===0)};
  }
  function paintJob(job,now){
    const t=now-job.start;if(t<0)return;
    if(!job.node.isConnected||(!job.ghost&&!job.node.getClientRects().length)||t>=job.duration){restore(job);return;}
    const m=job.mask,p=clamp(t/job.duration),dir=job.direction;
    const opacity=job.mode==='out'?(job.ghost?0:smooth((p-.48)/.42)):smooth((p-.53)/.4);
    job.node.style.opacity=String(opacity);
    const nav=document.querySelector('.tabs')?.getBoundingClientRect();
    ctx.save();ctx.beginPath();ctx.rect(0,Math.max(0,nav?.bottom||0),width,height);ctx.clip();
    if(job.mode==='out'){
      // A continuous eroding edge leaves the unbroken part of the actual glyph visible.
      const swept=clamp(t/310)*m.w;
      ctx.save();ctx.beginPath();ctx.rect(m.box.x+(dir>0?swept:0),m.box.y,m.w-swept,m.h);ctx.clip();
      ctx.drawImage(m.bitmap,m.box.x,m.box.y,m.w,m.h);ctx.restore();
    }
    for(let i=0;i<m.grains.length;i++){
      const g=m.grains[i],r=noise(i+11),phase=noise(i+31),along=dir>0?g.x/m.w:1-g.x/m.w;
      let x=g.x,y=g.y,alpha=0;
      if(job.mode==='out'){
        const age=(t-along*310)/580;if(age<0||age>1)continue;
        const drift=age*age*.42+age*.58;
        x+=dir*(38+r*95)*drift;y+=age*age*(18+phase*50);y+=Math.sin(age*5+r*8)*age*10;
        alpha=(1-smooth(age))*.85;
      }else{
        const progress=clamp((t-along*190)/(job.duration-210)),remaining=1-smooth(progress);
        x-=dir*(42+r*105)*remaining;y-=(8+phase*25)*remaining;
        y+=Math.sin(progress*5+r*7)*remaining*10;
        alpha=smooth(p*7)*(1-opacity)*(.7+progress*.3);
      }
      ctx.globalAlpha=alpha*g.alpha;
      ctx.fillStyle=i%19===0?'#B96E50':g.color;
      const size=1.1+r*1.3;ctx.fillRect(m.box.x+x,m.box.y+y,size,size);
    }
    ctx.globalAlpha=1;
    ctx.restore();
  }
  function tick(now){
    frame=0;ctx.clearRect(0,0,width,height);
    for(const job of jobs.values())paintJob(job,now);
    canvas.dataset.active=String(jobs.size);
    if(jobs.size)frame=requestAnimationFrame(tick);
  }
  function start(node,mode,direction=1,delay=0,ghost=false){
    if(!node||reduced.matches||document.hidden)return false;
    if(jobs.has(node))restore(jobs.get(node));
    const sampled=mask(node);if(!sampled||!sampled.grains.length)return false;
    if(jobs.size>=6)restore(jobs.values().next().value);
    const job={node,mode,ghost,direction:direction<0?-1:1,mask:sampled,opacity:node.style.opacity,start:performance.now()+delay,duration:mode==='out'?880:820};
    jobs.set(node,job);node.style.opacity='0';canvas.dataset.active=String(jobs.size);
    if(!frame)frame=requestAnimationFrame(tick);return true;
  }
  window.OneShotDust={reveal:(node,direction=1,delay=0)=>start(node,'in',direction,delay),dissolve:(node,direction=1)=>start(node,'out',direction,0,true),cancel};
  window.addEventListener('resize',resize,{passive:true});
  window.addEventListener('scroll',cancel,{passive:true});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
  reduced.addEventListener('change',()=>{if(reduced.matches)cancel();});
  window.JevI18n?.onChange(cancel);resize();
})();
