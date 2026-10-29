/* Complete, read-only replay. No policy calls; no frames from an invented route. */
(async()=>{
 'use strict';
 const $=id=>document.getElementById(id),speed=2;
 let manifest,selected,clip,renderer,timeline=[],duration=0,position=0,playing=false,raf=0,last=0,active=-1,generation=0,mountQueue=Promise.resolve();
 const json=async url=>{const r=await fetch(url);if(!r.ok)throw Error('Could not load '+url);return r.json();};
 function pause(){playing=false;cancelAnimationFrame(raf);$('play').textContent='Play';}
 function fail(e){pause();$('error').textContent=String(e.message||e);}
 function decode(phase){let state={};return (phase.frames||[]).map(delta=>state={...state,...delta});}
 function label(id){
  const common={up:'↑ Up',down:'↓ Down',left:'← Left',right:'→ Right',jump_right:'↗ Jump right',jump_left:'↖ Jump left',jump:'↑ Jump',wait:'Wait',cross_right:'Cross right',cross_right_guard:'Cross right · guarded'};
  if(common[id])return common[id];
  if(clip.id==='jump-jump')return `Hold ${id} ms`;
  if(clip.id==='tetris'){const [r,c]=id.split(':');return `Rotation ${r} · column ${c}`;}
  if(clip.id==='sokoban'){const [,x,y,d,tx,ty]=id.split(':');return `Box (${x},${y}) ${ {up:'↑',down:'↓',left:'←',right:'→'}[d]} · goal (${tx},${ty})`;}
  return id;
 }
 function percentage(p){if(p===0)return '0%';if(p<.001)return '<0.1%';if(p<1&&p>.999)return '>99.9%';return (p*100).toFixed(1)+'%';}
 function panel(segment){
  const s=segment.step,automatic=s.actor==='automatic',forced=s.actor.startsWith('forced');
  const shown=automatic?clip.steps.slice(0,s.index).reverse().find(x=>x.probabilities)||s:s;
  const revealed=segment.phase.name!=='observe'||automatic,probs=shown.probabilities;
  $('phase').textContent=automatic?'Environment advances':forced?'Only legal move':segment.phase.name==='observe'?'01 · Observe':segment.phase.name==='choose'?'02 · Decide':'03 · Execute';
  $('decision').querySelector('h3').textContent=automatic?'Previous decision':forced?'Forced action':'Candidate probabilities';
  $('probability-note').textContent=automatic?'No new model request':forced?'No model request':shown.probability_source?.mode==='representative_sample'?`Recorded pass ${shown.probability_source.sample_index+1} of ${shown.probability_source.repeat_count}`:'Recorded action probabilities';
  $('candidates').dataset.sourceStep=String(shown.index);
  $('candidates').replaceChildren();
  const ids=[...shown.candidates].sort((a,b)=>(probs?.[b]??0)-(probs?.[a]??0));
  const visible=new Set(ids.slice(0,6));
  if(shown.action!=null&&!visible.has(String(shown.action))){visible.delete(ids[5]);visible.add(String(shown.action));}
  for(const id of ids){const tag=document.createElement('div');tag.className='candidate';tag.dataset.action=id;tag.title=id;tag.hidden=!visible.has(id);
   const value=probs?.[id],name=document.createElement('span'),number=document.createElement('span');
   name.className='candidate-label';name.textContent=label(id);number.className='probability-value';number.textContent=revealed&&value!=null?percentage(value):'—';
   if(value!=null){tag.dataset.probability=String(value);tag.style.setProperty('--probability',revealed?(value*100)+'%':'0%');}
   tag.append(name,number);
   if(revealed&&String(shown.action)===id){tag.classList.add('selected');if(!shown.applied)tag.classList.add('rejected');name.textContent='✓ '+name.textContent;}
   $('candidates').append(tag);
  }
  if(ids.length>visible.size){const more=document.createElement('button');more.className='more-candidates';
   const remaining=ids.filter(id=>!visible.has(id)),sum=probs?remaining.reduce((n,id)=>n+probs[id],0):null;
   more.textContent=`${remaining.length} more options${revealed&&sum!=null?' · '+percentage(sum):''}`;
   more.onclick=()=>{$('candidates').querySelectorAll('.candidate').forEach(x=>x.hidden=false);more.remove();};$('candidates').append(more);
  }
  $('candidates').scrollTop=0;
  $('feedback').textContent=automatic?'The environment continues after the last action.':forced?'This is the only legal action.':revealed?(shown.applied?'Selected: ':'Not applied: ')+label(String(shown.action)):'Reading the current game state';
  $('position').textContent=`Step ${s.index+1} / ${clip.steps.length} · 2×`;
  $('action').textContent=segment.phase.name==='execute'?(s.action==null?'Clock advances':s.applied?'Action applied':'Action discarded'):'';
 }
 function fit(){
  const host=$('stage'),frame=renderer.frame,canvas=[...frame.contentDocument.querySelectorAll('canvas')].find(c=>c.getBoundingClientRect().width>0);
  if(!canvas)return;const ratio=canvas.width/canvas.height,width=Math.min(host.clientWidth,host.clientHeight*ratio);
  frame.style.setProperty('width',width+'px','important');frame.style.setProperty('height',(width/ratio)+'px','important');frame.style.minHeight='0';
 }
 function sample(seconds){
  position=Math.max(0,Math.min(duration,Number(seconds)));
  if(duration-position<1e-6)position=duration;
  let index=timeline.findIndex(s=>position<s.end);if(index<0)index=timeline.length-1;
  const segment=timeline[index],phase=segment.phase;
  if(index!==active){panel(segment);active=index;}
  const p=Math.max(0,Math.min(1,(position-segment.start)/(segment.end-segment.start)));
  let before=phase.before,after=phase.after,progress=p;
  if(segment.frames.length>1){const part=p*(segment.frames.length-1),i=Math.min(segment.frames.length-2,Math.floor(part));before=segment.frames[i];after=segment.frames[i+1];progress=part-i;}
  renderer.sample({before,after,action:segment.step.action},progress);
  if(position===duration){renderer.sample({before:clip.final_state,after:clip.final_state},1);$('feedback').textContent='Replay complete · '+(clip.final_state.outcome||clip.final_state.winner||clip.result?.outcome||'Final state');}
  fit();$('seek').value=String(position);document.documentElement.dataset.frame=String(position);
  return {step:segment.step.index,phase:phase.name,progress:p};
 }
 async function load(id){
  const ticket=++generation,choice=manifest.items.find(x=>x.id===id)||manifest.items[0];
  pause();document.documentElement.dataset.ready='false';$('error').textContent='';
  for(const id of ['play','seek','restart'])$(id).disabled=true;
  const next=await json('./showcase/'+choice.trace);
  const mount=async()=>{
   if(ticket!==generation)return;
   renderer?.destroy();const instance=await window.JevReplayRenderer.mount($('stage'),{kind:next.kind,lang:'en'});
   if(ticket!==generation){instance.destroy();return;}
   renderer=instance;clip=next;selected=choice;timeline=[];duration=0;active=-1;
   for(const step of clip.steps)for(const phase of step.phases){const length=Math.max(.16,phase.seconds/speed);timeline.push({step,phase,frames:decode(phase),start:duration,end:duration+length});duration+=length;}
   $('game-title').textContent=clip.title;$('title').textContent=clip.title;$('seek').max=String(duration);$('seek').step='any';
   $('games').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===selected.id)));
   $('source').textContent='Original participant: '+clip.participants.join(' / ');
   for(const id of ['play','seek','restart'])$(id).disabled=false;
   sample(0);document.documentElement.dataset.ready='true';
  };
  mountQueue=mountQueue.catch(()=>{}).then(mount);return mountQueue;
 }
 function tick(now){if(!playing)return;sample(position+(now-last)/1000);last=now;if(position>=duration)pause();else raf=requestAnimationFrame(tick);}
 window.addEventListener('resize',()=>{if(renderer)fit();});
 try{
  manifest=await json('./showcase/full-manifest.json');
  for(const item of manifest.items){const b=document.createElement('button');b.dataset.id=item.id;b.textContent=item.id;b.onclick=()=>load(item.id).catch(fail);$('games').append(b);}
  $('seek').oninput=e=>{pause();sample(e.target.value);};$('restart').onclick=()=>{pause();sample(0);};
  $('play').onclick=()=>{if(playing){pause();return;}if(position>=duration)sample(0);playing=true;last=performance.now();$('play').textContent='Pause';raf=requestAnimationFrame(tick);};
  window.PiccoloShowcase={load,sample,seek:sample,get duration(){return duration;},get count(){return clip.steps.length;},get id(){return selected.id;},get timeline(){return timeline.map(({step,phase,start,end})=>({step:step.index,phase:phase.name,start,end}));}};
  await load(new URLSearchParams(location.search).get('game'));
 }catch(e){fail(e);}
})();
