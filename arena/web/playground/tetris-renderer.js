/* Shared Tetris renderer for play and recorded replay. No game clock or input. */
window.JevTetrisRenderer=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en;
 const colors={I:'#68a8b8',O:'#d9af57',T:'#a38abf',S:'#80aa73',Z:'#c97d76',J:'#758fc4',L:'#ce9b69'};
 const shape=g=>PlayDraw.rotations(g.active?.piece||g.piece)[g.active?.rotation||0]||[];
 function landing(g){
  if(Array.isArray(g.ghost_cells)&&g.ghost_cells.length)return g.ghost_cells;
  if(!g.active)return [];
  const points=shape(g),x=g.active.x;let y=g.active.y;
  const fits=ny=>points.every(([dx,dy])=>x+dx>=0&&x+dx<g.board[0].length&&ny+dy<g.board.length&&(ny+dy<0||!g.board[ny+dy][x+dx]));
  while(fits(y+1))y++;
  return points.map(([dx,dy])=>[x+dx,y+dy]);
 }
 function position(g){
  if(!g.active)return null;
  const active=g.active,points=shape(g),ghost=landing(g);
  const stop=ghost.length?Math.min(...ghost.map(p=>p[1]))-Math.min(...points.map(p=>p[1])):active.y;
  const fraction=g.started&&g.phase==='falling'?Math.min(1,Math.max(0,Number(g.gravity_clock||0)/Number(g.gravity_interval||.8))):0;
  return {...active,y:Math.min(stop,active.y+fraction)};
 }
 function visualState(after,options={}){
  const before=options.before,p=Math.max(0,Math.min(1,options.progress??1));
  if(!before||p>=1)return {...after,visual_active:position(after)};
  // Lock, spawn and line deletion happen exactly at their recorded boundary.
  if(before.active?.piece_id!==after.active?.piece_id||before.steps!==after.steps||JSON.stringify(before.board)!==JSON.stringify(after.board))return {...before,
   clear_clock:before.phase==='clearing'?Math.min(before.clear_delay||.22,Number(before.clear_clock||0)+(after.elapsed-before.elapsed)*p):before.clear_clock,
   visual_active:position(before)};
  const a=position(before),b=position(after),state=p<1?before:after;
  if(!a||!b)return {...state,clear_clock:Number(before.clear_clock||0)+(Number(after.clear_clock||0)-Number(before.clear_clock||0))*p,visual_active:position(state)};
  const sameRotation=a.rotation===b.rotation&&a.piece===b.piece;
  return {...state,elapsed:before.elapsed+(after.elapsed-before.elapsed)*p,
   clear_clock:Number(before.clear_clock||0)+(Number(after.clear_clock||0)-Number(before.clear_clock||0))*p,
   visual_active:sameRotation?{...a,x:a.x+(b.x-a.x)*p,y:a.y+(b.y-a.y)*p}:p<.5?a:b};
 }
 function draw(world,options={},canvas=document.getElementById('showcaseCanvas')){
  const g=visualState(world,options),mobile=window.innerWidth<=620,w=mobile?540:900,h=mobile?660:540;
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  const c=canvas.getContext('2d'),s=mobile?40:32,ox=mobile?70:230,oy=mobile?128:88,bw=g.board[0].length*s,bh=g.board.length*s;
  const text=(value,x,y,size=18,color='#547965',weight=400)=>{c.fillStyle=color;c.font=weight+' '+size+'px "Jev Comic", "Noto Sans CJK SC", sans-serif';c.fillText(value,x,y);};
  const rect=(x,y,width,height,r,color)=>{c.fillStyle=color;c.beginPath();c.roundRect(x,y,width,height,r);c.fill();};
  const block=(x,y,color,ghost=false)=>{if(y<0)return;const px=ox+x*s,py=oy+y*s;
   if(ghost){c.strokeStyle=color;c.lineWidth=2;c.setLineDash([5,4]);c.strokeRect(px+4,py+4,s-8,s-8);c.setLineDash([]);return;}
   rect(px+2,py+2,s-4,s-4,3,color);rect(px+5,py+4,s-10,4,1,'#ffffff52');rect(px+5,py+s-7,s-10,3,1,'#00000015');};
  c.clearRect(0,0,w,h);c.textAlign='left';c.textBaseline='alphabetic';c.fillStyle='#f7f4e7';c.fillRect(0,0,w,h);
  text(tr('TETRIS','俄罗斯方块'),mobile?32:35,mobile?38:43,17,'#718d7b',700);
  rect(ox-13,oy-13,bw+26,bh+26,6,'#6d9484');rect(ox-5,oy-5,bw+10,bh+10,2,'#e8efdf');
  g.board.forEach((row,y)=>row.forEach((value,x)=>{c.fillStyle=(x+y)%2?'#f3f6e9':'#e9f0e2';c.fillRect(ox+x*s,oy+y*s,s,s);c.strokeStyle='#bdd3bd';c.lineWidth=.8;c.strokeRect(ox+x*s,oy+y*s,s,s);if(value)block(x,y,'#668fa0');}));
  if(g.phase==='clearing'){
   const amount=.35+.45*Math.sin(Math.min(1,Number(g.clear_clock||0)/.22)*Math.PI);
   for(const y of g.clearing_rows||[]){c.fillStyle='rgba(255,249,216,'+amount+')';c.fillRect(ox,oy+y*s,bw,s);}
  }
  const active=g.visual_active;
  if(active){const color=colors[active.piece]||'#a38abf';for(const [x,y] of landing(g))block(x,y,color,true);
   const points=PlayDraw.rotations(active.piece||g.piece)[active.rotation||0]||[];
   c.save();c.beginPath();c.rect(ox,oy,bw,bh);c.clip();for(const [x,y] of points)block(active.x+x,active.y+y,color);
   if(g.phase==='locking'){c.globalAlpha=.25;for(const [x,y]of points)block(active.x+x,active.y+y,'#fff8da');}c.restore();
  }
  const next=g.next_piece,preview=next&&PlayDraw.rotations(typeof next==='string'?next:next.piece)?.[0];
  const nx=mobile?356:635,ny=mobile?52:155,ps=mobile?18:25;
  text(tr('Next','下一块'),nx,mobile?33:130,mobile?16:18);
  if(preview)for(const [x,y]of preview)rect(nx+x*ps,ny+y*ps,ps-2,ps-2,2,colors[typeof next==='string'?next:next.piece]||'#a38abf');
  const phase=!g.started?tr('Ready','待开始'):g.outcome?tr('Finished','已结束'):tr(({falling:'Falling',locking:'Locking',clearing:'Clearing'})[g.phase]||'Falling',({falling:'下落中',locking:'即将锁定',clearing:'消行中'})[g.phase]||'下落中');
  if(mobile){text(g.lines+' / 4 '+tr('lines','行'),32,85,23,'#426f60',700);text(phase,202,85,18);}
  else{text(String(g.lines).padStart(2,'0'),632,288,50,'#426f60',700);text('/ 04 '+tr('lines','行'),708,288,19);text(phase,635,350,20);text(g.steps+' / 40 '+tr('pieces','块'),635,390,18);}
  if(!g.started&&!g.outcome){rect(ox+12,oy+bh/2-38,bw-24,76,8,'#f7f9efed');c.textAlign='center';text(tr('Press a key to start','按键开始下落'),ox+bw/2,oy+bh/2+7,mobile?24:22,'#426f60',600);c.textAlign='left';}
 }
 return {draw,visualState,position};
})();
