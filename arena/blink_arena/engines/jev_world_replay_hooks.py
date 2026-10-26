"""Exact replay hooks for the existing browser physics, without archive tooling.

These constants are shared with offline replay and the real-time RL verifier.
"""

MARIO_HOOK = r'''
  window.__ArenaReplay={snapshot:()=>snapshot(),advance(target,capture){
    const frames=[];let safety=0;
    while(frame<target){
      if(++safety>200000||outcome)throw Error('unreachable_archived_frame');
      if(remaining>0){physics(command.direction,command.jump&&remaining===12);remaining=Math.max(0,remaining-1);if(!remaining||outcome)finishAction();}
      else physics(0,false);
      if(capture&&(frame%6===0||frame===target))frames.push(snapshot());
    }
    if(frame!==target)throw Error('archived_frame_mismatch');return frames;
  }};
'''

TERRA_HOOK = r'''
  function arenaSnapshot(){
    const s=jevSnapshot();
    const pick=(o,keys)=>Object.fromEntries(keys.filter(k=>o[k]!==undefined).map(k=>[k,o[k]]));
    s.replay_scene={
      enemies:enemies.filter(e=>Math.abs(e.x-P.x)<TS*12&&Math.abs(e.y-P.y)<TS*9&&explored[idx(Math.floor(e.x/TS),Math.floor(e.y/TS))]).map(e=>pick(e,['x','y','w','h','kind','face','ground','hp','maxhp','lv','boss'])),
      player:pick(P,['x','y','vx','vy','w','h','inv']),agent:pick(agent,['atk','digT','digP']),surface:Array.from(surf)
    };return s;
  }
  window.__ArenaReplay={snapshot:arenaSnapshot,advance(target,capture){
    const frames=[];let safety=0;
    while(frame<target){
      if(++safety>200000)throw Error('unreachable_archived_frame');
      if(jevFrames>0&&jevAction){keys={};jevKeys[jevAction].forEach(k=>keys[k]=1);}
      update(1);
      if(jevFrames>0&&--jevFrames<=0)jevFinish();
      if(capture&&(frame%6===0||frame===target))frames.push(arenaSnapshot());
    }
    if(frame!==target)throw Error('archived_frame_mismatch');return frames;
  }};
'''
