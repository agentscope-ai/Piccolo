/* Read-only player: render saved states; never call a model or advance an engine. */
(async()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  let manifest,selected,record,renderer,position=0,timer=null,generation=0,paint=Promise.resolve();
  let frames=[];
  const pause=()=>{clearInterval(timer);timer=null;$('play').textContent='Play';};
  const fail=error=>{$('error').textContent=String(error.message||error);pause();};
  async function json(url){const response=await fetch(url);if(!response.ok)throw Error('Could not load '+url);return response.json();}
  async function seek(index){
    const ticket=generation;
    const task=async()=>{
      if(ticket!==generation)return;
      position=Math.max(0,Math.min(frames.length-1,Number(index)));
      const item=frames[position];
      await renderer.update({kind:record.kind,state:item.state,step:item.step,position,animate:false,lang:'en',reason:'seek'});
      if(ticket!==generation)return;
      $('position').textContent=`State ${position+1} / ${frames.length} · seed ${selected.seed}`;
      const action=item.step?.action;
      $('action').textContent=action==null?(position===0?'Initial state':position===frames.length-1?'Final state':'Recorded state'):'Action · '+(typeof action==='object'?JSON.stringify(action):action);
      $('seek').value=String(position);
      document.documentElement.dataset.frame=String(position);
    };
    paint=paint.then(task);await paint;
    return position;
  }
  async function load(id){
    pause();const ticket=++generation;
    document.documentElement.dataset.ready='false';$('error').textContent='';
    selected=manifest.items.find(item=>item.id===id)||manifest.items[0];
    $('play').disabled=true;$('seek').disabled=true;$('restart').disabled=true;
    const next=await json('./showcase/'+selected.trace);
    if(ticket!==generation)return;
    await paint;renderer?.destroy();record=next;paint=Promise.resolve();
    frames=[{state:record.initial_state,step:null},...record.steps.map(step=>({state:step.state??step.after_state,step})),{state:record.final_state,step:null}].filter(frame=>frame.state!=null);
    if(record.missing_frames||frames.length<2)throw Error('This trajectory has no complete visual record.');
    const instance=await window.JevReplayRenderer.mount($('stage'),{kind:record.kind});
    if(ticket!==generation){instance.destroy();return;}renderer=instance;
    $('title').textContent=selected.title;$('seek').max=String(frames.length-1);
    $('games').querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.id===selected.id)));
    const link=document.createElement('a');link.href='./showcase/'+selected.trace;link.textContent='Trajectory JSON ↗';
    $('source').replaceChildren(document.createTextNode('Original participant: '+record.participants.join(' / ')+' · '),link);
    await seek(0);if(ticket!==generation)return;
    $('play').disabled=false;$('seek').disabled=false;$('restart').disabled=false;
    document.documentElement.dataset.ready='true';
  }
  try{
    manifest=await json('./showcase/manifest.json');
    for(const item of manifest.items){const button=document.createElement('button');button.dataset.id=item.id;button.textContent=item.title;button.setAttribute('aria-pressed','false');button.onclick=()=>load(item.id).catch(fail);$('games').append(button);}
    $('seek').oninput=event=>{pause();seek(Number(event.target.value)).catch(fail);};
    $('restart').onclick=()=>{pause();seek(0).catch(fail);};
    $('play').onclick=()=>{
      if(timer){pause();return;}if(position===frames.length-1)seek(0).catch(fail);
      $('play').textContent='Pause';timer=setInterval(()=>{if(position===frames.length-1){pause();return;}seek(position+1).catch(fail);},700);
    };
    window.BlinkShowcase={load,seek,get count(){return frames.length;},get id(){return selected.id;}};
    await load(new URLSearchParams(location.search).get('game'));
  }catch(error){fail(error);}
})();
