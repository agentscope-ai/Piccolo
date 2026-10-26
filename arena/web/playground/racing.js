/* Rally Sprint: original vector art and rendering; perspective-road idea
 * informed by Jake Gordon's javascript-racer (MIT). No sprites/music copied.
 * Draws only public engine observations and interpolates actual physics frames. */
window.JevRacing=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en;
 let lastPaint=null;
 function eventLabel(g){
  if(g.outcome==='win')return tr("Finish line reached","已抵达终点");
  if(g.failure_reason==='vehicle_destroyed')return tr("Vehicle destroyed","车辆损毁");
  if(g.failure_reason==='race_time_exhausted')return tr("Time limit reached","赛时耗尽");
  if(g.failure_reason==='decision_budget_exhausted')return tr("Decision limit reached","决策预算耗尽");
  return g.outcome?tr("Race finished","本场结束"):g.race_started===false?tr("Accelerate to start","踩油门开始计时"):tr("Race in progress","比赛进行中");
 }
 const mix=(a,b,t)=>a+(b-a)*t;
 function draw(g,o={}){
  lastPaint={g,o};
  const canvas=o.canvas||document.getElementById('showcaseCanvas'),c=canvas.getContext('2d');
  const compact=canvas.getBoundingClientRect().width>0&&canvas.getBoundingClientRect().width<560;
  const f=o.frame?{...g,...o.frame}:g,z=f.z,x=f.x;
  if(o.frame&&f.elapsed<g.elapsed-1e-8){
   if(!('outcome' in o.frame))f.outcome=null;
   if(!Array.isArray(o.frame.contacts)){
    const recorded=g.execution_trace?.frames||[];
    f.contacts=recorded.length?interpolateFrames(decorateFrames(g,recorded,new Map()),f.elapsed).contacts:[];
   }
  }
  const contacts=Array.isArray(f.contacts)?f.contacts:[],outcome=f.outcome;
  // The canvas is shared with card/arcade games. Never inherit their alignment,
  // transforms, shadows or compositing when painting a racing HUD.
  c.save();c.resetTransform();c.globalAlpha=1;c.globalCompositeOperation='source-over';
  c.shadowColor='transparent';c.shadowBlur=0;c.shadowOffsetX=0;c.shadowOffsetY=0;c.filter='none';
  c.textAlign='left';c.textBaseline='alphabetic';c.direction='ltr';c.setLineDash([]);
  const geometry=g.collision_geometry||{},carWidth=geometry.car_width??1.25,carLength=geometry.car_length??2;
  const roadHalf=geometry.road_half_width??4.675,obstacleLength=geometry.obstacle_length??1;
  c.clearRect(0,0,900,540);c.fillStyle='#dceef2';c.fillRect(0,0,900,540);
  function poly(points,color){c.fillStyle=color;c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill()}
  function text(t,x,y,size=16,color='#284f52'){c.fillStyle=color;c.font=`600 ${size}px "Jev Comic", "Noto Sans CJK SC", sans-serif`;c.fillText(String(t),x,y)}
  function rect(x,y,w,h,r,color){c.fillStyle=color;c.beginPath();c.roundRect(x,y,w,h,r);c.fill()}
  poly([[0,170],[90,83],[215,160],[350,105],[490,170]],'#aec8bd');
  poly([[400,170],[570,85],[720,155],[810,99],[900,170]],'#b7d0bf');
  c.fillStyle='#9ebca0';c.fillRect(0,169,900,371);
  const track=g.visible_track||[],sections=d=>track.find(s=>s.start<=d&&s.end>d)||track.at(-1)||{curve:0,center:0,grip_speed:23};
  function bend(d){let p=0,v=0;for(let a=0;a<d;a+=2){v+=sections(z+a).curve*2;p+=v*2}return p}
  function project(d,lateral=0){const scale=14/(d+14);return [450+(bend(d)+lateral-x)*46*scale,170+310*scale,scale]}
  for(let d=70;d>=-2;d-=2){const a=project(d),b=project(d+2),aW=roadHalf*46*a[2],bW=roadHalf*46*b[2];
   const band=Math.floor((z+d)/8)%2;
   poly([[b[0]-bW-10*b[2],b[1]],[b[0]+bW+10*b[2],b[1]],[a[0]+aW+10*a[2],a[1]],[a[0]-aW-10*a[2],a[1]]],band?'#d7e4d2':'#f6f3dc');
   poly([[b[0]-bW,b[1]],[b[0]+bW,b[1]],[a[0]+aW,a[1]],[a[0]-aW,a[1]]],band?'#52686b':'#566d70');
   if(Math.floor((z+d)/5)%2===0)for(const lane of [-1.35,1.35]){const p=project(d,lane),q=project(d+2,lane);poly([[q[0]-q[2]*1.7,q[1]],[q[0]+q[2]*1.7,q[1]],[p[0]+p[2]*1.7,p[1]],[p[0]-p[2]*1.7,p[1]]],'#e3ebe1')}
  }
  if(900-z<=70){const [cx,cy,s]=project(900-z);for(let i=0;i<12;i++)rect(cx-roadHalf*46*s+i*(roadHalf*92/12)*s,cy-8*s,(roadHalf*92/12)*s,16*s,0,i%2?'#253a3f':'#fff');text(tr("FINISH","终点"),cx-24*s,cy-18*s,Math.max(9,21*s),'#223a3f')}
  for(const obstacle of [...(g.visible_obstacles||[])].sort((a,b)=>b.z-a.z)){
   if(obstacle.z<z-2||obstacle.z>z+70)continue;
   const depth=obstacle.length??obstacleLength,half=obstacle.width/2,d=obstacle.z-z;
   const near=project(d-depth/2,obstacle.x),far=project(d+depth/2,obstacle.x);
   const hit=contacts.includes(obstacle.id),height=(hit?.2:.8)*46;
   const nw=half*46*near[2],fw=half*46*far[2],nh=height*near[2],fh=height*far[2];
   // The barrier footprint uses the very same width/depth as collision checks.
   poly([[far[0]-fw,far[1]-fh],[far[0]+fw,far[1]-fh],[near[0]+nw,near[1]-nh],[near[0]-nw,near[1]-nh]],hit?'#b8c3b8':'#efbb87');
   poly([[near[0]-nw,near[1]-nh],[near[0]+nw,near[1]-nh],[near[0]+nw,near[1]],[near[0]-nw,near[1]]],hit?'#a1b1a4':'#d99164');
   if(!hit){rect(near[0]-nw+4*near[2],near[1]-nh*.78,Math.max(0,2*nw-8*near[2]),6*near[2],near[2],'#fff0cf');rect(near[0]-nw+4*near[2],near[1]-nh*.35,Math.max(0,2*nw-8*near[2]),6*near[2],near[2],'#fff0cf')}
  }
  // A 1.25 m x 2 m car footprint, at its actual z/x. The old fixed 88 px
  // sprite was roughly 1.9 m wide and suggested contacts outside the hitbox.
  const fl=project(carLength/2,x-carWidth/2),fr=project(carLength/2,x+carWidth/2);
  const rl=project(-carLength/2,x-carWidth/2),rr=project(-carLength/2,x+carWidth/2);
  poly([fl,fr,rr,rl],'#213e4380');
  for(const point of [fl,fr,rl,rr]){
   const frontWheel=point===fl||point===fr,cx=point[0]+(point===fl||point===rl?3:-3),cy=point[1]-5;
   c.save();c.translate(cx,cy);c.rotate(frontWheel?Number(f.steering_input||0)*.3:0);rect(-3,-7,6,15,2,'#273a3b');c.restore();
  }
  poly([[fl[0]+5,fl[1]-28],[fr[0]-5,fr[1]-28],[rr[0]-5,rr[1]-7],[rl[0]+5,rl[1]-7]],'#cf765b');
  const front=project(carLength*.26,x),rear=project(-carLength*.23,x),windWidth=carWidth*46*.65;
  poly([[front[0]-windWidth*.43,front[1]-26],[front[0]+windWidth*.43,front[1]-26],[rear[0]+windWidth*.5,rear[1]-27],[rear[0]-windWidth*.5,rear[1]-27]],'#a8d5d6');
  const braking=f.pedal==='brake';
  rect(rl[0]+7,rl[1]-12,9,4,1,braking?'#ff564d':'#ffdb93');rect(rr[0]-16,rr[1]-12,9,4,1,braking?'#ff564d':'#ffdb93');
  // A collision flash follows a confirmed physics tick, never a future snapshot.
  const impactAge=f.elapsed-Number(f.impact_elapsed??-Infinity);
  if(impactAge>=0&&impactAge<.32){c.save();c.globalAlpha=(1-impactAge/.32)*.75;c.strokeStyle='#df614b';c.lineWidth=4;c.beginPath();[fl,fr,rr,rl].forEach(([px,py],i)=>i?c.lineTo(px,py):c.moveTo(px,py));c.closePath();c.stroke();c.restore();}

  if(compact){
   rect(20,18,860,64,15,'#fbfff4ed');
   text(`${Math.min(900,f.z).toFixed(0)}/900 m`,38,61,32);
   text(`${f.speed.toFixed(1)} m/s`,265,61,32);
   text(`${f.elapsed.toFixed(1)} s`,480,61,32);
   text(tr(`HP ${Math.max(0,f.health).toFixed(0)}`,`耐久 ${Math.max(0,f.health).toFixed(0)}`),695,61,32);
  }else{
  rect(20,18,860,70,15,'#fbfff4ed');text(tr("RALLY SPRINT","拉力冲刺"),38,45,19);text(tr("Steer · Gas / Coast / Brake","转向 · 油门 / 滑行 / 刹车"),38,70,13,'#67827a');
  text(`${Math.min(900,f.z).toFixed(0)} / 900 m`,330,47,19);text(`${f.speed.toFixed(1)} m/s`,330,70,14,'#67827a');
  text(`${f.elapsed.toFixed(1)} / ${g.time_limit||300} s`,520,47,19);text(f.race_started===false?tr("Accelerate to start","踩油门开始计时"):tr(`Target ${sections(z).grip_speed} m/s`,`建议车速 ${sections(z).grip_speed} m/s`),520,70,13,'#67827a');
  text(tr(`HP ${Math.max(0,f.health).toFixed(0)}`,`耐久 ${Math.max(0,f.health).toFixed(0)}`),735,47,19);rect(735,60,117,7,4,'#d7e3d6');rect(735,60,117*Math.max(0,f.health)/100,7,4,f.health<40?'#d18a65':'#6ca58e');
  rect(20,505,860,28,9,'#fbfff4e8');text(`${tr('Offset','横向')} ${f.x.toFixed(2)} m · ${tr('Lateral','横向速度')} ${(f.lateral_velocity??g.lateral_velocity??0).toFixed(2)} m/s · ${ {throttle:tr("Gas","油门"),coast:tr("Coast","滑行"),brake:tr("Brake","刹车")}[f.pedal]||tr("Coast","滑行")} · ${f.race_started===false?tr("Accelerate to start","踩油门开始计时"):f.speed<.01?tr("Stopped · Clock running","已停车 · 赛时继续"):tr("Race continues while waiting","等待期间继续行驶")}`,35,525,13,'#476a66');
  }
  if(outcome){rect(230,219,440,96,18,'#fcfff1eb');text(outcome==='win'?tr("Finish!","冲线成功！"):tr("Race finished","本场结束"),350,258,28);text(eventLabel(f),280,290,16,'#69867b')}
  c.restore();
 }
 function frames(before,after){const t=after.execution_trace;if(!t||t.version!==1||!Array.isArray(t.frames)||t.frames.length<1)throw new Error(tr("Missing racing execution frames","赛车缺少执行帧"));
  if(Math.abs(t.frames[0].z-before.z)>1e-6||Math.abs(t.frames.at(-1).z-after.z)>1e-6)throw new Error(tr("Racing frame boundaries do not match","赛车执行帧边界不一致"));
  for(let i=1;i<t.frames.length;i++){const a=t.frames[i-1],b=t.frames[i],dt=b.elapsed-a.elapsed;if(dt<-1e-8||dt>.101||Math.abs(b.z-a.z)>23*dt+1e-6)throw new Error(tr("Racing execution frames are not continuous","赛车执行帧不连续"))}
  return t.frames;
 }
 async function animate(before,after){
  const actual=frames(before,after),times=new Map((before.contacts||[]).map(id=>[id,before.elapsed]));
  const samples=decorateFrames(after,actual,times);
  if(samples.length===1){draw(after,{frame:samples[0]});return;}
  const duration=Math.max(150,after.execution_trace.duration*500),start=performance.now(),base=samples[0].elapsed;
  return new Promise(resolve=>{function tick(now){
   const progress=Math.min(1,(now-start)/duration),frame=interpolateFrames(samples,base+progress*(samples.at(-1).elapsed-base));
   const state={...after,visible_track:[...before.visible_track,...after.visible_track],visible_obstacles:[...new Map([...before.visible_obstacles,...after.visible_obstacles].map(o=>[o.id,o])).values()]};
   draw(state,{frame});if(progress<1)requestAnimationFrame(tick);else resolve();
  }requestAnimationFrame(tick);});
 }

 function controls(g,choices,container,commit){
  container.innerHTML='';const row=document.createElement('div');row.className='racing-joint-controls';
  row.style.cssText='display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;width:100%';
  const steering={hard_left:tr("⇐ Hard left","⇐ 急左"),left:tr("← Left","← 向左"),straight:tr("↑ Straight","↑ 回正"),right:tr("Right →","向右 →"),hard_right:tr("Hard right ⇒","急右 ⇒"),pulse_left:tr("⇐ Left tap","⇐ 左转脉冲"),pulse_right:tr("Right tap ⇒","右转脉冲 ⇒")};
  const pedals={throttle:tr("Gas","油门"),coast:tr("Coast","滑行"),brake:tr("Brake","刹车")};
  for(const pedal of Object.keys(pedals))for(const steer of Object.keys(steering)){
   const action=steer+':'+pedal,b=document.createElement('button');b.textContent=steering[steer]+' · '+pedals[pedal];
   b.dataset.action=action;b.dataset.pedal=pedal;b.dataset.steering=steer;b.title=steering[steer]+' · '+pedals[pedal];
   b.disabled=!(action in choices);b.onclick=()=>commit(action,false);row.appendChild(b);
  }container.appendChild(row);
 }
 // Merge authoritative samples onto one monotonic presentation clock. New HTTP
 // replies extend the buffer; they never replay a completed interval from its start.
 let streamState=null,streamFrames=[],streamRAF=0,displayElapsed=null,paintWall=null;
 const contactTimes=new Map();
 const numericFrame=g=>Object.fromEntries(['z','x','speed','lateral_velocity','steering_input','pedal','elapsed','health','outcome','event','race_started','contacts','failure_reason'].filter(k=>k in g).map(k=>[k,Array.isArray(g[k])?[...g[k]]:g[k]]));
 function stop(){if(streamRAF)cancelAnimationFrame(streamRAF);streamRAF=0;streamState=null;streamFrames=[];displayElapsed=null;paintWall=null;contactTimes.clear();lastPaint=null;}
 function sweptOverlap(a,b,obstacle,geometry){
  const halfLength=((geometry.car_length??2)+(obstacle.length??geometry.obstacle_length??1))/2,dz=b.z-a.z;
  let lo=0,hi=1;
  if(Math.abs(dz)<1e-12){if(Math.abs(a.z-obstacle.z)>halfLength)return false;}
  else{const u=(obstacle.z-halfLength-a.z)/dz,v=(obstacle.z+halfLength-a.z)/dz;lo=Math.max(0,Math.min(u,v));hi=Math.min(1,Math.max(u,v));if(lo>hi)return false;}
  const x0=a.x+(b.x-a.x)*lo-obstacle.x,x1=a.x+(b.x-a.x)*hi-obstacle.x;
  const distance=x0*x1<=0?0:Math.min(Math.abs(x0),Math.abs(x1));
  return distance<((geometry.car_width??1.25)+obstacle.width)/2-1e-9;
 }
 function decorateFrames(g,actual,times=contactTimes){
  const geometry=g.collision_geometry||{};
  for(const id of g.contacts||[]){
   if(times.has(id))continue;
   const obstacle=(g.visible_obstacles||[]).find(o=>o.id===id);let at=g.elapsed;
   if(obstacle)for(let i=1;i<actual.length;i++)if(sweptOverlap(actual[i-1],actual[i],obstacle,geometry)){at=actual[i].elapsed;break;}
   times.set(id,at);
  }
  return actual.map(frame=>{
   const contacts=Array.isArray(frame.contacts)?[...frame.contacts]:[...times].filter(([,at])=>at<=frame.elapsed+1e-8).map(([id])=>id);
   const impacts=contacts.map(id=>times.get(id)).filter(Number.isFinite);
   return {...frame,race_started:frame.race_started??g.race_started,contacts,impact_elapsed:impacts.length?Math.max(...impacts):null};
  });
 }
 function interpolateFrames(samples,when){
  if(!samples.length)return null;
  if(when<=samples[0].elapsed)return {...samples[0]};
  let i=0;while(i<samples.length-1&&samples[i+1].elapsed<=when+1e-9)i++;
  if(i===samples.length-1)return {...samples[i]};
  const a=samples[i],b=samples[i+1],t=Math.max(0,Math.min(1,(when-a.elapsed)/(b.elapsed-a.elapsed)));
  const frame={...a};
  for(const key of ['z','x','speed','lateral_velocity','elapsed'])if(Number.isFinite(a[key])&&Number.isFinite(b[key]))frame[key]=mix(a[key],b[key],t);
  // Collision damage and terminal/control flags occur on the recorded tick.
  // Small off-road wear is continuous; a 35-HP impact is never spread early.
  const impact=a.health-b.health>5;
  frame.health=impact?a.health:mix(a.health,b.health,t);
  if(impact)frame.speed=a.speed;
  return frame;
 }
 function stream(g){
  if(!g||g.kind!=='racing_sprint'||!Number.isFinite(g.elapsed))return;
  if(streamState&&g.elapsed<streamState.elapsed-1e-8)return;
  const trace=Array.isArray(g.execution_trace?.frames)?g.execution_trace.frames.filter(f=>Number.isFinite(f.elapsed)&&Number.isFinite(f.z)&&Number.isFinite(f.x)&&f.elapsed<=g.elapsed+1e-8).map(f=>({...f})):[];
  const actual=trace.length?trace:[numericFrame(g)];
  if(actual.at(-1).elapsed<g.elapsed-1e-8)actual.push(numericFrame(g));
  else actual[actual.length-1]={...actual.at(-1),...numericFrame(g)};
  const incoming=decorateFrames(g,actual),byTime=new Map(streamFrames.map(frame=>[frame.elapsed.toFixed(6),frame]));
  for(const frame of incoming){
   // An overlapping trace must not overwrite already displayed contact metadata.
   const key=frame.elapsed.toFixed(6),previous=byTime.get(key);
   byTime.set(key,previous?{...previous,...frame}:frame);
  }
  streamFrames=[...byTime.values()].sort((a,b)=>a.elapsed-b.elapsed);
  streamState={...g,
   visible_track:[...new Map([...(streamState?.visible_track||[]),...(g.visible_track||[])].map(section=>[section.start,section])).values()],
   visible_obstacles:[...new Map([...(streamState?.visible_obstacles||[]),...(g.visible_obstacles||[])].map(obstacle=>[obstacle.id,obstacle])).values()]};
  if(displayElapsed===null){displayElapsed=g.elapsed;paintWall=performance.now();}
  const floor=displayElapsed-.15;
  while(streamFrames.length>2&&streamFrames[1].elapsed<floor)streamFrames.shift();
  if(streamFrames.length>240)streamFrames.splice(0,streamFrames.length-240);
  if(!streamRAF){paintWall=performance.now();streamRAF=requestAnimationFrame(paintStream);}
 }
 function paintStream(now){
  streamRAF=0;if(!streamState||!streamFrames.length)return;
  const dt=Math.max(0,Math.min(.1,(now-(paintWall??now))/1000));paintWall=now;
  const latest=streamFrames.at(-1).elapsed,lag=latest-displayElapsed;
  const rate=Math.max(1,Math.min(4,lag/.08));
  displayElapsed=Math.min(latest,Math.max(streamFrames[0].elapsed,displayElapsed+dt*rate));
  const frame=interpolateFrames(streamFrames,displayElapsed);
  draw(streamState,{frame});
  if(displayElapsed<latest-1e-8)streamRAF=requestAnimationFrame(paintStream);
 }
 window.JevI18n?.onChange(()=>{if(lastPaint&&document.getElementById('showcasesView')?.dataset.kind==='racing_sprint')draw(lastPaint.g,lastPaint.o);});
 return {eventLabel,draw,frames,animate,controls,stream,stop,interpolateFrames};
})();
