/* Shared Mario engine core. The browser and RL execute this same fixed-step engine.
 * This module has no DOM, rendering, timers, or browser globals. Scheduling belongs
 * to the host; candidate forecasts consume only the public observation. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.JevMarioCore = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const height = p => p<20?0:p<45?(p-20)*1.92:p<142?48:p<167?(167-p)*1.92:0;
  function phases(plant, frame) {
    const history=plant.visible_height_history||[{frame,height:plant.height}];
    return Array.from({length:180},(_,i)=>i).filter(p=>history.every(h=>
      Math.abs(height((p-(frame-h.frame)%180+180)%180)-h.height)<.15));
  }
  function mario(obs, action, frames=12, wait=0, control={}) {
    const p={...obs.player},terrain=obs.map,T=terrain.tile_size;
    let unknown=false,blocked=false,head=false,landed=false,risk=false,pitFall=false;
    const direction=action.includes('right')?1:action.includes('left')?-1:0;
    const jump=action.startsWith('jump');
    const at=(x,y)=>{const row=terrain.tiles[y-terrain.origin[1]],c=x-terrain.origin[0];
      if(!row||c<0||c>=row.length){unknown=true;return 1}return row[c]};
    const stomped=new Set();
    const plants=(obs.plants||[]).map(v=>({...v,phases:phases(v,obs.frame)}));
    let landingFrame=null,simulatedFrames=0;
    for(let t=1;t<=frames;t++){
      simulatedFrames=t;
      if(t===1&&jump&&p.on_ground){p.vy=-10;p.on_ground=false}
      const moving=Number.isFinite(control.stopX)&&direction>0&&p.x>=control.stopX?0:direction;
      p.x+=moving*3.2;
      let bounds={y0:Math.floor(p.y/T),y1:Math.floor((p.y+p.height-.01)/T),x0:Math.floor(p.x/T),x1:Math.floor((p.x+p.width-.01)/T)};
      for(let y=bounds.y0;y<=bounds.y1;y++)
        for(let x=bounds.x0;x<=bounds.x1;x++)if(at(x,y)>0){
          if(moving>0)p.x=x*T-p.width;else if(moving<0)p.x=(x+1)*T;blocked=true;}
      const wasGround=p.on_ground;
      const previousBottom=p.y+p.height;
      p.vy=Math.min(10,p.vy+.5);p.y+=p.vy;p.on_ground=false;
      // Leaving the bottom of the fully visible terrain through known air is a
      // visible pit, distinct from an unknown horizontal frontier.
      if(p.y+p.height>=(terrain.origin[1]+terrain.tiles.length)*T){
        const c0=Math.floor(p.x/T)-terrain.origin[0],c1=Math.floor((p.x+p.width-.01)/T)-terrain.origin[0];
        if(c0>=0&&c1<terrain.tiles[0].length&&terrain.tiles[terrain.tiles.length-1].slice(c0,c1+1).every(v=>v===0))pitFall=true;
      }
      if(pitFall){landed=false;break}
      bounds={y0:Math.floor(p.y/T),y1:Math.floor((p.y+p.height-.01)/T),x0:Math.floor(p.x/T),x1:Math.floor((p.x+p.width-.01)/T)};
      for(let y=bounds.y0;y<=bounds.y1;y++)
        for(let x=bounds.x0;x<=bounds.x1;x++)if(at(x,y)>0){
          if(p.vy>0){p.y=y*T-p.height;p.on_ground=true;if(!wasGround){landed=true;landingFrame=t}}
          else if(p.vy<0){p.y=(y+1)*T;head=true}p.vy=0;}
      for(const flower of plants){
        const base=flower.y+flower.height;
        const heights=flower.phases.map(v=>height((v+t+wait)%180));
        const max=heights.length?Math.max(...heights):48;
        if(max>12&&p.x<flower.x+flower.width&&p.x+p.width>flower.x&&p.y<base&&p.y+p.height>base-max)risk=true;
      }
      // Enemy motion is an estimate: an unobserved patrol boundary may reverse it.
      for(const e of obs.enemies||[]){const x=e.x+(e.vx||0)*(t+wait);
        if(!stomped.has(e)&&p.x<x+e.width&&p.x+p.width>x&&p.y<e.y+e.height&&p.y+p.height>e.y){if(p.vy>0&&previousBottom<=e.y+9){stomped.add(e);p.y=e.y-p.height;p.vy=-7;landed=false;}else risk=true;}}
      if(landed||pitFall)break;
    }
    const contact=(obs.enemies||[]).filter(e=>e.x+e.width>=obs.player.x+obs.player.width).map(e=>({
      x:e.x,contact_frames_estimate:(e.x-obs.player.x-obs.player.width)/Math.max(.01,direction*3.2-(e.vx||0)),
      uncertainty:'constant velocity until unknown patrol reversal'}));
    return {certainty:unknown?'unknown_outside_view':'visible_geometry_with_plant_phase_bounds_and_enemy_velocity_estimate',
      predicted_player:{x:+p.x.toFixed(1),y:+p.y.toFixed(1),on_ground:!!p.on_ground,vy:+p.vy.toFixed(1)},head_collision:head,blocked,
      landed,landing_frame:landingFrame,plant_or_enemy_risk:risk,visible_pit_fall:pitFall,unknown_terrain:unknown,
      enemy_contact:contact,plant_phase_counts:plants.map(p=>p.phases.length),
      predicted_stomps:stomped.size,enemy_projection_kind:'constant_velocity_estimate; unknown patrol reversal',jump_state:obs.player.on_ground?(jump?'starts_jump':'grounded'):(obs.player.vy<0?'rising':'falling'),
      can_restart_jump:!!obs.player.on_ground,frames,simulated_frames:simulatedFrames,landing_plant_exposure:plants.some(f=>p.x<f.x+f.width&&p.x+p.width>f.x&&p.y<f.y+f.height&&p.y+p.height>f.y+f.height-48)};
  }

  const INTENT_PREFIX='cross_visible_right:',INTENT_REVISION='visible-crossing-intent-v1';
  const INTENT_FRAMES=300,INTENT_WAIT_FRAMES=180;
  function visibleTile(obs,x,y){
    const map=obs.map,row=map.tiles[y-map.origin[1]],column=x-map.origin[0];
    return row&&column>=0&&column<row.length?row[column]:null;
  }
  function supportedPose(obs,x,y,fullFoot=true){
    const T=obs.map.tile_size,w=obs.player.width,h=obs.player.height;
    const left=Math.floor(x/T),right=Math.floor((x+w-.01)/T),foot=(y+h)/T;
    if(Math.abs(foot-Math.round(foot))>.02)return false;
    let supported=false;
    for(let col=left;col<=right;col++){
      const support=visibleTile(obs,col,Math.round(foot));
      if(support===null||fullFoot&&support<=0)return false;
      supported||=support>0;
      for(let row=Math.floor(y/T);row<=Math.floor((y+h-.01)/T);row++)if(visibleTile(obs,col,row)!==0)return false;
    }
    return supported;
  }
  function landingInside(facts,region,width,height){
    const p=facts.predicted_player;
    return facts.landed&&!facts.visible_pit_fall&&!facts.unknown_terrain&&
      p.x>=region.left-.1&&p.x+width<=region.right+.1&&Math.abs(p.y+height-region.top)<.2;
  }
  function visibleContinuation(obs,facts){
    const result={prediction_type:'deterministic_visible_geometry_only',available:false,
      visible_forward_landing_regions:[],visible_retreat_landing_regions:[],headroom_pixels:null,
      unknown_frontier:!!facts.unknown_terrain,dynamic_safety:'not_estimated; geometry_only_no_enemy_or_plant_guarantee'};
    const pose=facts.predicted_player;
    if(!pose?.on_ground||facts.visible_pit_fall||facts.unknown_terrain)return result;
    const local={...obs,enemies:[],plants:[],player:{...obs.player,...pose}},T=obs.map.tile_size;
    result.available=true;
    const cols=[Math.floor(pose.x/T),Math.floor((pose.x+obs.player.width-.01)/T)];
    let clearance=0,known=true;
    for(let row=Math.floor((pose.y-.01)/T);row>=obs.map.origin[1];row--){
      const values=cols.map(col=>visibleTile(obs,col,row));
      if(values.includes(null)){known=false;break;}
      if(values.some(value=>value>0))break;
      clearance=pose.y-row*T;
    }
    result.headroom_pixels=known?Math.max(0,Math.round(clearance*10)/10):null;
    for(const [action,field,sign] of [['jump_right','visible_forward_landing_regions',1],['jump_left','visible_retreat_landing_regions',-1]]){
      const next=mario(local,action,90);result.unknown_frontier||=next.unknown_terrain;
      if(!next.landed||next.visible_pit_fall||next.unknown_terrain||(next.predicted_player.x-pose.x)*sign<obs.player.width)continue;
      const q=next.predicted_player,column=Math.floor(q.x/T),support_row=Math.round((q.y+obs.player.height)/T);
      if(supportedPose(local,q.x,q.y))result[field].push({left:q.x,right:q.x+obs.player.width,top:support_row*T,column,support_row});
    }
    return result;
  }
  function visibleObstacles(obs){
    if(!obs.player.on_ground)return [];
    const map=obs.map,T=map.tile_size,support=Math.round((obs.player.y+obs.player.height)/T),result=[];
    const origin=map.origin[0],floor=map.tiles[support-map.origin[1]],above=map.tiles[support-1-map.origin[1]];
    if(!floor||!above)return result;
    for(const [row,value,kind] of [[floor,0,'gap'],[above,3,'pipe']]){
      for(let i=0;i<row.length;i++)if(row[i]===value){
        const begin=i;while(i+1<row.length&&row[i+1]===value)i++;
        if(begin===0||i+1>=row.length)continue;
        const left_col=origin+begin,right_col=origin+i+1,left=left_col*T,right=right_col*T;
        if(obs.player.x+obs.player.width<=left+.1&&left-obs.player.x<=T*8)
          result.push({kind,left_col,right_col,left,right,support_row:support});
      }
    }
    return result.sort((a,b)=>a.left-b.left||a.right-b.right);
  }
  function visibleIntents(obs){
    const result={},obstacle=visibleObstacles(obs)[0];
    if(!obstacle||!supportedPose(obs,obs.player.x,obs.player.y))return result;
    const T=obs.map.tile_size,p=obs.player,geometry={...obs,enemies:[],plants:[]};
    // One visible obstacle, at most three landing tiles. A tall pipe can need
    // one jump onto its top; the model must separately choose what follows.
    const targets=obstacle.kind==='pipe'?[
      [obstacle.left_col,obstacle.support_row-2],[obstacle.right_col-1,obstacle.support_row-2],
      [obstacle.right_col,obstacle.support_row]]:
      [0,1,2].map(offset=>[obstacle.right_col+offset,obstacle.support_row]);
    for(const [col,supportRow] of targets){
      const pipeTop=obstacle.kind==='pipe'&&supportRow<obstacle.support_row;
      const region={column:col,support_row:supportRow,left:col*T,right:(col+1)*T,top:supportRow*T};
      // The real collision rule needs some visible solid support, not a full
      // foot-width tile. Fixed edge bands preserve safe pipe-side stances.
      if(pipeTop&&col===obstacle.left_col)region.left-=p.width-1;
      if(pipeTop&&col===obstacle.right_col-1)region.right+=p.width-1;
      const stopX=region.left+(region.right-region.left-p.width)/2;
      if(!supportedPose(obs,stopX,region.top-p.height,!pipeTop))continue;
      let first=null,last=null;
      for(let steps=0;steps<=80;steps++){
        const x=+(p.x+steps*3.2).toFixed(1);
        if(x+p.width>obstacle.left+.1||!supportedPose(obs,x,p.y))break;
        const launch={...geometry,player:{...p,x}};
        const projected=mario(launch,'jump_right',90,0,{stopX});
        if(landingInside(projected,region,p.width,p.height)){
          if(!first)first={x,steps,projected};last=x;
        }else if(first)break;
      }
      if(!first)continue;
      const launch={...obs,player:{...p,x:first.x}},facts=mario(launch,'jump_right',90,first.steps,{stopX});
      // A retracting plant is not evidence that its mouth is a safe place to
      // stand through the next model request. Do not offer such a landing.
      if(facts.landing_plant_exposure)continue;
      const approach=mario(obs,'right',first.steps);
      facts.plant_or_enemy_risk||=approach.plant_or_enemy_risk;
      facts.intent={revision:INTENT_REVISION,obstacle:{...obstacle},landing_region:region,
        launch_window:{minimum_x:first.x,maximum_x:last,selected_x:first.x,approach_frames:first.steps},
        deadline_frames:INTENT_FRAMES,max_wait_frames:INTENT_WAIT_FRAMES,one_jump:true,strategy_origin:'A',execution_origin:'B'};
      facts.certainty='visible_geometry_with_observed_dynamic_estimates; target_revalidated_during_execution';
      facts.approach_risk_estimate=approach.plant_or_enemy_risk;
      facts.continuation=visibleContinuation(obs,first.projected);
      facts.wait_assumption='Approach and one jump are projected from current visible information; waiting window may never become safe; no future world state or successor policy is used.';
      result[`${INTENT_PREFIX}${obstacle.kind}:${obstacle.left_col}:${obstacle.right_col}:${col}:${supportRow}`]=facts;
    }
    return result;
  }

  const visibleControl = Object.freeze({mario, phases,visibleIntents,visibleContinuation});
  function create(options = {}) {
    const seedModule = options.seedModule;
    if (!seedModule || typeof seedModule.marioLayout !== 'function') throw new TypeError('seedModule is required');
    const now = options.now || (() => Date.now());
    const changed = () => { if (typeof options.onChange === 'function') options.onChange(); };
    const T=32,H=14,FLOOR=11;
    let viewportWidth = options.viewportWidth || 920, visibilityHidden = false;
  let W=96,GOAL=91*T,environmentGeneration=null;
  const ACTIONS={right:'向右跑',jump_right:'向右跳',left:'向左跑',jump_left:'向左跳',jump:'原地跳跃',wait:'等待落地',cross_right:'当前站位等待安全窗口后向右跳一次',cross_right_guard:'向右越障一次，落地后在原位按可见威胁原地跳防御，最多8秒'};
  let tiles,coins,enemies,plants,powerups,popups,p,camera=0,frame=0,collected=0,powerupsCollected=0,score=0,outcome=null,event='',history=[],recentPositions=[],decisions=0;
  let active=false,locked=false,modelStepping=false,remaining=0,resolveAction=null,command=null,keys=new Set(),jumpQueued=false,last=0,accumulator=0;
  let modelAwaiting=false,episodeGeneration=0;
  let actionEffects=[],noProgressCount=0,plantVisibleHistory=new Map(),stompedCount=0,shieldsUsed=0;
  // This reflex is B only when the model explicitly chose cross_right_guard.
  // It cannot advance horizontally, choose another obstacle, or renew itself.
  let landingGuard=null,flightCrossing=null,progressEvents=[],crossedIds=new Set(),observedCrossings=new Map();
  let conditionSeed, mushroomBlocks=new Set([28,74]);
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const tile=(x,y)=>x<0||x>=W?1:y<0||y>=H?0:tiles[y][x];
  const solid=(x,y)=>tile(x,y)>0;
  const overlap=(a,b)=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;
  const held=k=>keys.has(k);
  const round=v=>Math.round(v*10)/10;
  function pipePlants(){
    const found=[];
    for(let x=1;x<W-1;x++)if(tile(x,FLOOR-2)===3&&tile(x-1,FLOOR-2)!==3)
      found.push({pipe_x:x,offset:(70+found.length*47)%180});
    return found;
  }
  function plantBody(plant){
    if(plant.replayBody)return plant.replayBody;
    const phase=(frame+plant.offset)%180;
    const height=phase<20?0:phase<45?(phase-20)*1.92:phase<142?48:phase<167?(167-phase)*1.92:0;
    return {pipe_x:plant.pipe_x,x:plant.pipe_x*T+17,y:(FLOOR-2)*T-height,w:30,h:height,emerged:height>12};
  }
  function reset(seed,options){
    const nextSeed=seedModule.normalize(seed);
    const layout=seedModule.marioLayout(nextSeed,options);
    release();conditionSeed=nextSeed;episodeGeneration++;
    W=layout.width;GOAL=layout.goalColumn*T;
    // Provenance is outside snapshot()/model input: hidden obstacle totals and
    // mushroom positions must never become facts available to the policy.
    environmentGeneration={generator_revision:layout.generator_revision,profile:layout.profile};
    tiles=Array.from({length:H},()=>Array(W).fill(0));coins=[];enemies=[];powerups=[];popups=[];
    for(let x=0;x<W;x++)for(let y=FLOOR;y<H;y++)tiles[y][x]=1;
    layout.pits.forEach((a,i)=>{for(let x=a;x<a+layout.pitWidths[i];x++)for(let y=FLOOR;y<H;y++)tiles[y][x]=0;});
    for(const x of layout.pipes)for(let dx=0;dx<2;dx++)for(let y=FLOOR-2;y<FLOOR;y++)tiles[y][x+dx]=3;
    layout.bricks.forEach((x,i)=>{for(let dx=0;dx<layout.brickLengths[i];dx++)tiles[7][x+dx]=dx===1?4:2;});
    mushroomBlocks=new Set(layout.mushrooms);
    for(let x=5;x<layout.goalColumn-2;x+=3){if(solid(x,FLOOR))coins.push({x:x*T+10,y:(solid(x,FLOOR-1)?FLOOR-4:FLOOR-2)*T+8,w:12,h:18});}
    for(const [x,a,b] of layout.patrols)enemies.push({x:x*T,y:FLOOR*T-24,w:26,h:24,vx:-.65,min:a*T,max:b*T,alive:true});
    plants=pipePlants();plants.forEach((plant,i)=>{plant.offset=layout.plantOffsets[i]});
    p={x:2*T,y:FLOOR*T-30,w:23,h:30,vx:0,vy:0,on_ground:true,facing:1,shield:0,invulnerable_until:0};
    camera=0;frame=0;collected=0;powerupsCollected=0;score=0;outcome=null;event='前往旗杆；顶问号方块取奖励，避开管道里的食人花';history=[];recentPositions=[];decisions=0;actionEffects=[];noProgressCount=0;plantVisibleHistory=new Map();stompedCount=0;shieldsUsed=0;
    landingGuard=null;flightCrossing=null;progressEvents=[];crossedIds=new Set();observedCrossings=new Map();
    changed();return snapshot();
  }
  function clearKeys(){keys.clear();jumpQueued=false;}
  function finishAction(){if(command){recentPositions.push([round(p.x),round(p.y)]);const dx=round(p.x-command.startX),dy=round(p.y-command.startY);noProgressCount=Math.abs(dx)+Math.abs(dy)<1?noProgressCount+1:0;actionEffects.push({action:command.action,delta_x:dx,delta_y:dy,frames:command.elapsed,event:command.event||'action_complete',failure_reason:command.failureReason||null,landing_target:command.landingTarget||null,horizontal_target_reached:!!command.targetReached,execution_class:'B',policy_decision_class:'A',...(command.intent?{intent_revision:INTENT_REVISION,selected_obstacle:command.intent.obstacle,selected_landing_region:command.intent.landing_region,execution_stage:command.stage,approach_frames:command.approachFrames,wait_frames:command.waitFrames,jumps_started:command.jumpsStarted,danger_event:command.dangerEvent||null}:{})});actionEffects=actionEffects.slice(-6);}recentPositions=recentPositions.slice(-8);remaining=0;locked=false;command=null;clearKeys();accumulator=0;if(resolveAction){const done=resolveAction;resolveAction=null;done(snapshot());}changed();}
  function release(){modelAwaiting=false;modelStepping=false;landingGuard=null;finishAction();}
  function finish(result,message){outcome=result;event=message;remaining=0;p.vx=0;p.vy=0;clearKeys();changed();}
  function bump(x,y){
    if(tile(x,y)===4){
      tiles[y][x]=5;
      if(mushroomBlocks.has(x)){
        powerups.push({x:x*T+5,y:y*T+8,w:22,h:22,vx:1.2,vy:0,rise:20,taken:false});
        event='问号方块弹出蘑菇；碰到它可挡住一次伤害';
      }else{
        collected++;score+=100;popups.push({x:x*T+11,y:y*T-5,ttl:32,kind:'coin'});
        event='问号方块弹出金币 +1';
      }
    }else if(tile(x,y)===2){tiles[y][x]=0;score+=10;event='顶碎砖块';}
  }
  function hurt(message){
    if(frame<p.invulnerable_until)return;
    if(p.shield){p.shield--;shieldsUsed++;p.invulnerable_until=frame+50;event='蘑菇护盾挡住一次伤害';return;}
    finish('loss',message);
  }
  function updatePowerups(){
    for(const reward of powerups){
      if(reward.taken)continue;
      if(reward.rise>0){reward.y-=1.5;reward.rise--;}
      else{
        const next=reward.x+reward.vx,front=reward.vx>0?next+reward.w:next;
        if(solid(Math.floor(front/T),Math.floor((reward.y+reward.h/2)/T)))reward.vx=-reward.vx;
        else reward.x=next;
        reward.vy=Math.min(7,reward.vy+.4);reward.y+=reward.vy;
        const foot=Math.floor((reward.y+reward.h)/T);
        if(reward.vy>=0&&(solid(Math.floor(reward.x/T),foot)||solid(Math.floor((reward.x+reward.w-1)/T),foot))){reward.y=foot*T-reward.h;reward.vy=0;}
      }
      if(reward.y>H*T+20){reward.taken=true;continue;}
      if(overlap(p,reward)){
        reward.taken=true;p.shield=1;powerupsCollected++;score+=300;
        event='拿到蘑菇：护盾可挡一次敌人或食人花伤害';
      }
    }
    for(const popup of popups){popup.y-=1.1;popup.ttl--;}
    popups=popups.filter(item=>item.ttl>0);
  }
  function physics(direction,jump){
    if(outcome)return;
    if(jump&&p.on_ground){
      flightCrossing={start_x:p.x};
      for(const target of visibleCrossingTargets(snapshot(false)))if(p.x+p.w<=target.left&&!crossedIds.has(target.id))observedCrossings.set(target.id,target);
    }
    frame++;p.vx=direction*3.2;if(direction)p.facing=direction;
    if(jump&&p.on_ground){p.vy=-10;p.on_ground=false;}
    p.x+=p.vx;
    for(let y=Math.floor(p.y/T);y<=Math.floor((p.y+p.h-.01)/T);y++)for(let x=Math.floor(p.x/T);x<=Math.floor((p.x+p.w-.01)/T);x++)if(solid(x,y)){
      if(p.vx>0)p.x=x*T-p.w;else if(p.vx<0)p.x=(x+1)*T;p.vx=0;
    }
    const previousBottom=p.y+p.h;
    p.vy=Math.min(10,p.vy+.5);p.y+=p.vy;p.on_ground=false;
    for(let y=Math.floor(p.y/T);y<=Math.floor((p.y+p.h-.01)/T);y++)for(let x=Math.floor(p.x/T);x<=Math.floor((p.x+p.w-.01)/T);x++)if(solid(x,y)){
      if(p.vy>0){p.y=y*T-p.h;p.on_ground=true;}else if(p.vy<0){p.y=(y+1)*T;bump(x,y);}p.vy=0;
    }
    p.x=clamp(p.x,0,W*T-p.w);
    for(const c of coins)if(!c.taken&&overlap(p,c)){c.taken=true;collected++;score+=100;event='收集金币 +1';}
    updatePowerups();
    for(const e of enemies){
      if(!e.alive)continue;
      e.x+=e.vx;if(e.x<=e.min||e.x>=e.max){e.x=clamp(e.x,e.min,e.max);e.vx=-e.vx;}
      if(overlap(p,e)){
        if(p.vy>0&&previousBottom<=e.y+9){e.alive=false;stompedCount++;p.y=e.y-p.h;p.vy=-7;score+=200;event='踩退敌人 +200';}
        else{hurt('碰到敌人了，再试一次');if(outcome)break;}
      }
    }
    if(!outcome)for(const plant of plants){
      const body=plantBody(plant);
      if(body.emerged&&overlap(p,body)){hurt('碰到食人花了，再试一次');if(outcome)break;}
    }
    if(!outcome&&p.y>H*T+32)finish('loss','落入深坑，再试一次');
    if(!outcome&&p.x+p.w>=GOAL){score+=1000;finish('win','抵达旗杆，闯关成功！');}
    if(flightCrossing&&p.on_ground){
      if(!outcome||outcome==='win')for(const target of observedCrossings.values()){
        if(flightCrossing.start_x<target.right&&p.x>=target.right&&!crossedIds.has(target.id)){
          crossedIds.add(target.id);observedCrossings.delete(target.id);progressEvents.push({id:target.id,kind:target.kind,frame,x:round(p.x),landing_on_ground:true,
            observed_left:target.left,observed_right:target.right,source:'visible_geometry_then_executed_landing'});
        }
      }
      flightCrossing=null;
    }
    camera=clamp(p.x-viewportWidth*.32,0,W*T-viewportWidth);
    for(const plant of plants){const body=plantBody(plant);if(body.x+body.w>=camera&&body.x<=camera+viewportWidth){const seen=plantVisibleHistory.get(body.pipe_x)||[];seen.push({frame,height:round(body.h)});plantVisibleHistory.set(body.pipe_x,seen.slice(-180));}}
    if(frame%6===0){changed();}
  }
  function visibleCrossingTargets(obs){
    const map=obs.map,origin=map.origin[0],floor=map.tiles[FLOOR],above=map.tiles[FLOOR-1],result=[];
    for(const [row,value,kind,prefix] of [[floor,0,'safe_gap_crossing','gap'],[above,3,'safe_obstacle_crossing','pipe']]){
      for(let i=0;i<row.length;i++)if(row[i]===value){
        const begin=i;while(i+1<row.length&&row[i+1]===value)i++;
        // Both edges must have been visible before the crossing, never infer a
        // hidden end from the full engine map or the environment generator.
        if(begin>0&&i+1<row.length)result.push({id:prefix+':'+(origin+begin)+':'+(origin+i+1),kind,left:(origin+begin)*T,right:(origin+i+1)*T});
      }
    }
    return result;
  }
  function snapshot(includeCandidates=true){
    const origin=Math.floor(camera/T),end=Math.min(W,Math.ceil((camera+viewportWidth)/T));
    const obs={player:{x:round(p.x),y:round(p.y),width:p.w,height:p.h,vx:round(p.vx),vy:round(p.vy),on_ground:p.on_ground,facing:p.facing,shield:p.shield,invulnerable:frame<p.invulnerable_until},
      map:{origin:[origin,0],tile_size:T,tiles:tiles.map(row=>row.slice(origin,end)),legend:{0:'空气或深坑',1:'地面',2:'砖块',3:'管道',4:'问号砖（金币或蘑菇）',5:'已用砖'}},
      enemies:enemies.filter(e=>e.alive&&e.x+e.w>=camera&&e.x<=camera+viewportWidth).map(e=>({x:round(e.x),y:e.y,width:e.w,height:e.h,vx:e.vx})),
      plants:plants.map(plantBody).filter(body=>body.x+body.w>=camera&&body.x<=camera+viewportWidth).map(body=>({pipe_x:body.pipe_x,x:body.x,y:round(body.y),width:body.w,height:round(body.h),emerged:body.emerged,visible_height_history:(plantVisibleHistory.get(body.pipe_x)||[{frame,height:round(body.h)}]).filter(h=>h.frame%6===0||h.frame===frame).slice(-25)})),
      coins:coins.filter(c=>!c.taken&&c.x>=camera&&c.x<camera+viewportWidth).map(c=>({x:c.x,y:c.y})),
      powerups:powerups.filter(item=>!item.taken&&item.x>=camera&&item.x<camera+viewportWidth).map(item=>({x:round(item.x),y:round(item.y),width:item.w,height:item.h,type:'mushroom'})),
      goal_x:GOAL,progress:outcome==='win'?100:Math.min(100,Math.floor(Math.max(0,p.x-2*T)/(GOAL-2*T)*100)),collected,powerups_collected:powerupsCollected,enemies_stomped:stompedCount,shields_used:shieldsUsed,score,decisions,frame,outcome,event,last_actions:history.slice(-6),recent_player_positions:recentPositions.slice(-8),
      progress_events:progressEvents,progress_event_revision:'visible-crossing-landed-v1',
      action_execution:{revision:'selected-visible-landing-v6-explicit-guard',current_goal:'reach_visible_flag_to_right',selected_intent:command?.action||(landingGuard?.status==='active'?'cross_right_guard':null),status:remaining?'executing':modelAwaiting?'awaiting_model':'idle',remaining_frames:remaining,recent_effects:actionEffects,no_progress_count:noProgressCount,rule_takeover_count:0,landing_guard:landingGuard},
      timing:{mode:active?(modelStepping?'model_step':'realtime'):'paused',clock_contract:modelStepping?'stepped-v1':'realtime-v1',awaiting_model:modelAwaiting,inference_world_paused:modelStepping,visibility_paused:visibilityHidden,waiting_input:'release_keys',frames_per_second:60,action_frames:12,action_frames_by_action:{right:12,left:12,wait:12,jump:60,jump_right:60,jump_left:60,cross_right:180},jump_ends_on:'first_landing_or_ground_block_or_terminal_or_60_frames',note:modelStepping?'模型分步：观察和推理时暂停；跑动最多12帧，选定跳跃持续同方向至落地或最多60帧。':modelAwaiting?'模型实时：推理等待期间世界继续运行，按键已松开；重力、敌人和食人花持续推进。':'实时：选定跳跃持方向至首次落地；动作完成后仍受重力和敌人影响。'}};
    obs.timing.action_frames_by_action.cross_right_guard=180;
    obs.action_execution.visible_intent_revision=INTENT_REVISION;
    if(command?.intent){
      obs.action_execution.execution_stage=command.stage;
      obs.action_execution.selected_target=command.intent;
      obs.action_execution.deadline_frame=command.startFrame+INTENT_FRAMES;
    }
    obs.timing.latency_projection_assumptions='4/8 second dynamic scenarios at the observed launch pose; observed enemy velocity only, unknown patrol reversals; arrival jump phase is revalidated; not probability or Monte Carlo';
    if(landingGuard?.status==='active'){obs.timing.waiting_input='explicit_selected_in_place_guard';obs.timing.note='世界继续；模型已选cross_right_guard的原地防御仍机械执行，直到新意图/8秒期限/不可处理危险。';}
    if(includeCandidates)obs.candidate_effects=Object.fromEntries(Object.keys(ACTIONS).map(action=>{const projected=action.startsWith('cross_right')?'jump_right':action,duration=projected.startsWith('jump')?60:12,facts=visibleControl.mario(obs,projected,duration);const later=visibleControl.mario(obs,projected,duration,60);facts.after_assumed_60_frame_wait={plant_or_enemy_risk:later.plant_or_enemy_risk};const landed={...obs,player:{...obs.player,...facts.predicted_player}},idle=visibleControl.mario(landed,'wait',60,facts.simulated_frames);facts.post_action_idle_60_frames={plant_or_enemy_risk:idle.plant_or_enemy_risk,visible_pit_fall:idle.visible_pit_fall};facts.wait_assumption='Only an estimate for 1 second of API latency; actual latency and enemy patrol reversals are unknown.';
      facts.latency_scenarios=[240,480].map(n=>{const delayed=visibleControl.mario(obs,projected,duration,n),held=visibleControl.mario(landed,'wait',n,facts.simulated_frames);return {assumed_wait_seconds:n/60,arrival_dynamic_risk_estimate:delayed.plant_or_enemy_risk,post_landing_idle_risk_estimate:held.plant_or_enemy_risk,post_landing_pit:held.visible_pit_fall};});
      if(action==='cross_right_guard')facts.explicit_landing_guard={seconds:8,horizontal_motion:false,only_if_selected:true,trigger:'visible collision estimated within36frames; safe visible in-place jump',abort_on:['unknown_or_unsafe_jump','deadline','new_model_intent','terminal'],strategy_origin:'A',execution_origin:'B'};
      facts.continuation=visibleContinuation(obs,facts);
      return [action,facts];}));
    if(includeCandidates){
      const intents=visibleIntents(obs);
      Object.assign(obs.candidate_effects,intents);
      for(const action of Object.keys(intents))obs.timing.action_frames_by_action[action]=INTENT_FRAMES;
    }
    return structuredClone(obs);
  }
  function advanceLandingGuard(){
    const g=landingGuard;
    if(!g||g.status!=='active')return false;
    if(frame>=g.deadline_frame){g.status='expired';g.reason='selected_guard_deadline';return false;}
    const obs=snapshot(false);let jump=false;
    if(p.on_ground){
      const stay=visibleControl.mario(obs,'wait',36);
      if(stay.plant_or_enemy_risk||stay.visible_pit_fall){
        const escape=visibleControl.mario(obs,'jump',90);
        if(!escape.landed||escape.plant_or_enemy_risk||escape.visible_pit_fall||escape.unknown_terrain||escape.landing_plant_exposure){
          const imminent=visibleControl.mario(obs,'wait',6);
          if(stay.visible_pit_fall||imminent.plant_or_enemy_risk){g.status='blocked';g.reason='selected_in_place_defense_has_no_safe_visible_landing';return false;}
          g.last_event='waiting_visible_defense_window';
        }else{jump=true;g.defensive_jumps++;g.last_event='visible_danger_defensive_jump';}
      }
    }
    physics(0,jump);g.executed_frames++;
    if(outcome){g.status='terminal';g.reason=outcome;}
    return true;
  }
  function advanceSelectedAction(){
    if(command.intent){advanceVisibleIntent();return;}
    const wasGround=p.on_ground,oldX=p.x;let direction=command.direction,jump=command.jump&&command.elapsed===0;
    if(command.action.startsWith('cross_right')&&!command.launched){
      const facts=visibleControl.mario(snapshot(false),'jump_right',60);
      if(facts.landing_plant_exposure||facts.visible_pit_fall||facts.unknown_terrain||!facts.landed){
        physics(0,false);command.elapsed++;command.event='blocked';command.failureReason='selected_jump_has_no_safe_visible_landing';remaining=0;finishAction();return;
      }
      if(remaining>=60&&p.on_ground&&!facts.plant_or_enemy_risk){command.launched=true;command.jump=true;command.landingTarget={...facts.predicted_player};jump=true;}
      else direction=0;
    }
    if(command.action.startsWith('cross_right')&&command.launched&&p.x>=command.landingTarget.x-.1&&!p.on_ground){
      const hold=visibleControl.mario(snapshot(false),'wait',90);
      if(hold.landed&&!hold.visible_pit_fall&&!hold.plant_or_enemy_risk&&!hold.unknown_terrain){direction=0;command.targetReached=true;}
    }
    physics(direction,jump);command.elapsed++;remaining=Math.max(0,remaining-1);
    if(outcome){command.event=outcome;remaining=0;}
    else if(command.jump&&!wasGround&&p.on_ground){command.event='landed';remaining=0;
      if(command.action==='cross_right_guard')landingGuard={intent:'cross_right_guard',owner_decision:decisions,origin:'B',strategy_origin:'A',status:'active',start_frame:frame,deadline_frame:frame+480,anchor_x:round(p.x),defensive_jumps:0,executed_frames:0,last_event:'landed',reason:null};}
    else if(direction&&Math.abs(p.x-oldX)<.1&&p.on_ground){command.event='blocked';remaining=0;}
    else if(!remaining)command.event=command.jump||command.action.startsWith('cross_right')?'expired':'action_complete';
    if(!remaining||outcome)finishAction();
  }
  function abortVisibleIntent(reason,status='blocked'){
    // Releasing input does not pause gravity or select a replacement strategy.
    command.failureReason=reason;command.event=status;remaining=0;finishAction();
  }
  function advanceVisibleIntent(){
    const obs=snapshot(false),intent=command.intent,region=intent.landing_region;
    const stopX=region.left+(region.right-region.left-p.w)/2,wasGround=p.on_ground,oldX=p.x;
    const pipeTop=intent.obstacle.kind==='pipe'&&region.support_row<intent.obstacle.support_row;
    let direction=0,jump=false;
    if(command.stage!=='flight'){
      const current=visibleObstacles(obs).find(o=>o.kind===intent.obstacle.kind&&
        o.left_col===intent.obstacle.left_col&&o.right_col===intent.obstacle.right_col&&o.support_row===intent.obstacle.support_row);
      if(!current||!supportedPose(obs,stopX,region.top-p.h,!pipeTop)){
        abortVisibleIntent('selected_visible_target_changed');return;
      }
      if(!p.on_ground){abortVisibleIntent('selected_approach_left_support','danger_changed');return;}
      if(remaining<=60){abortVisibleIntent('selected_intent_deadline','expired');return;}
    }
    if(command.stage==='approach'){
      const launchX=intent.launch_window.selected_x;
      if(p.x<launchX-.1){
        if(!supportedPose(obs,p.x+3.2,p.y)){abortVisibleIntent('selected_approach_blocked');return;}
        const ahead=visibleControl.mario(obs,'right',Math.min(8,Math.ceil((launchX-p.x)/3.2)));
        if(ahead.plant_or_enemy_risk||ahead.visible_pit_fall||ahead.unknown_terrain){
          abortVisibleIntent('visible_danger_on_selected_approach','danger_changed');return;
        }
        direction=1;command.approachFrames++;
      }else command.stage='wait_window';
    }
    if(command.stage==='wait_window'){
      const facts=visibleControl.mario(obs,'jump_right',90,0,{stopX});
      const staticFacts=visibleControl.mario({...obs,enemies:[],plants:[]},'jump_right',90,0,{stopX});
      if(!landingInside(staticFacts,region,p.w,p.h)||facts.landing_plant_exposure){
        abortVisibleIntent('selected_landing_geometry_changed');return;
      }
      if(landingInside(facts,region,p.w,p.h)&&!facts.plant_or_enemy_risk){
        command.stage='flight';command.launched=true;command.jump=true;command.jumpsStarted++;
        command.landingTarget={...staticFacts.predicted_player};direction=1;jump=true;
      }else{
        command.waitFrames++;
        const stay=visibleControl.mario(obs,'wait',8);
        if(stay.plant_or_enemy_risk||stay.visible_pit_fall){abortVisibleIntent('visible_danger_while_waiting','danger_changed');return;}
        if(command.waitFrames>=INTENT_WAIT_FRAMES){abortVisibleIntent('selected_safe_window_not_found','expired');return;}
      }
    }else if(command.stage==='flight'){
      direction=p.x>=stopX?0:1;
      if(!direction)command.targetReached=true;
      // A new threat cannot authorize another target. Release only when the
      // visible projection gives a safe place to fall; otherwise complete the
      // already selected bounded jump and report the change at its landing.
      if(command.elapsed%6===0){
        const future=visibleControl.mario(obs,'jump_right',90,0,{stopX});
        if(future.plant_or_enemy_risk||future.unknown_terrain){
          command.dangerEvent='visible_danger_changed_during_selected_flight';
          const hold=visibleControl.mario(obs,'wait',90);
          if(hold.landed&&!hold.plant_or_enemy_risk&&!hold.visible_pit_fall&&!hold.unknown_terrain&&!hold.landing_plant_exposure){
            abortVisibleIntent(command.dangerEvent,'danger_changed');return;
          }
        }
      }
    }
    physics(direction,jump);command.elapsed++;remaining=Math.max(0,remaining-1);
    if(outcome){command.event=outcome;remaining=0;}
    else if(command.stage==='flight'&&!wasGround&&p.on_ground){
      const landed={landed:true,visible_pit_fall:false,unknown_terrain:false,predicted_player:{x:p.x,y:p.y}};
      const reached=landingInside(landed,region,p.w,p.h);
      command.event=reached?'landed':'blocked';
      if(!reached)command.failureReason='selected_landing_region_not_reached';
      command.stage='landed';command.targetReached=reached;remaining=0;
    }else if(direction&&Math.abs(p.x-oldX)<.1&&p.on_ground){
      command.event='blocked';command.failureReason='selected_approach_collision';remaining=0;
    }else if(!remaining){command.event='expired';command.failureReason='selected_intent_deadline';}
    if(!remaining||outcome)finishAction();
  }
  const api={snapshot,reset,release,condition(){return {seed:conditionSeed,generator_version:environmentGeneration.generator_revision,generation:episodeGeneration,...environmentGeneration}},prepare(options){const clock=options?.clock??'step';if(clock!=='step'&&clock!=='realtime')throw new RangeError('unknown simulation clock');finishAction();modelStepping=clock==='step';modelAwaiting=true;locked=true;clearKeys();changed();return snapshot();},activate(value){active=value;if(!value)release();last=now();accumulator=0;},
    act(action){const selected=typeof action==='string'&&action.startsWith(INTENT_PREFIX)?visibleIntents(snapshot(false))[action]:null;if(!(action in ACTIONS)&&!selected)return Promise.reject(Error('Unknown or unavailable visible action'));if(!active)return Promise.reject(Error('Open Mario first'));if(outcome)return Promise.resolve(snapshot());landingGuard=null;modelAwaiting=false;finishAction();locked=true;decisions++;history.push(action);command={action,startX:p.x,startY:p.y,elapsed:0,event:null,launched:false,direction:action.includes('right')?1:action.includes('left')?-1:0,jump:action.startsWith('jump')};if(selected)Object.assign(command,{intent:structuredClone(selected.intent),stage:'approach',startFrame:frame,approachFrames:0,waitFrames:0,jumpsStarted:0});remaining=selected?INTENT_FRAMES:action.startsWith('cross_right')?180:command.jump?60:12;changed();return new Promise(resolve=>{resolveAction=resolve;});}
  };

    function stepFrame() {
      if (remaining>0) advanceSelectedAction();
      else if (!outcome&&!advanceLandingGuard()) { const jump=!locked&&jumpQueued; jumpQueued=false; physics(locked?0:Number(held('right'))-Number(held('left')),jump); }
    }
    function tick(ts) {
      if (!Number.isFinite(ts)) throw new TypeError('tick timestamp must be finite');
      accumulator=Math.min(50,accumulator+(ts-last||0));last=ts;
      if(!active||visibilityHidden||modelStepping&&!remaining){accumulator=0;return frame;}
      while(accumulator>=1000/60){accumulator-=1000/60;
        if(modelStepping&&!remaining){accumulator=0;break;}
        stepFrame();
      }
      return frame;
    }
    function advanceTo(target, options={}) {
      if (!Number.isSafeInteger(target)||target<frame) throw new RangeError('advanceTo requires a future integer frame');
      while(frame<target&&!outcome)stepFrame();
      // A selected intent can reject a changed visible danger before physics
      // advances a frame. Live act() resolves that transition; replay must
      // execute it too, including its feedback and action history.
      if(options.completeAction&&remaining>0&&!outcome){
        stepFrame();
        if(frame!==target||remaining>0)throw new Error('replay_action_completion_frame_mismatch');
      }
      return frame;
    }
    function setInput(key, down, fresh=true) {
      if(!['left','right','jump'].includes(key))return false;
      if(!down){keys.delete(key);return true;}
      if(!active||locked||outcome)return false;
      if(modelStepping)release();
      keys.add(key);if(key==='jump'&&fresh)jumpQueued=true;return true;
    }
    function renderState(){return {T,H,FLOOR,W,GOAL,tiles,coins,enemies,plants:plants.map(plantBody),powerups,popups,p,camera,frame,collected,powerupsCollected,score,outcome,event,decisions,active,locked,modelStepping,modelAwaiting,remaining,command};}
    Object.assign(api,{tick,advanceTo,terminal:()=>outcome,renderState,setInput,clearInput:clearKeys,
      setVisibility(value){visibilityHidden=!!value;if(visibilityHidden)clearKeys();},
      setViewport(width){if(!Number.isFinite(width)||width<=0)throw new RangeError('invalid viewport width');viewportWidth=width;camera=clamp(p.x-viewportWidth*.32,0,W*T-viewportWidth);return viewportWidth;}});
    // Explicitly injected fixture hooks are used only by offline browser tests.
    // The production API does not expose state mutation or fixture methods.
    if (options.testHooks) Object.assign(options.testHooks,{
      inspectWorld:()=>JSON.parse(JSON.stringify({tiles,coins,enemies,plants,mushrooms:[...mushroomBlocks],player:p,frame,powerups,popups,collected,powerupsCollected,score,outcome})),
      testBump:(x,y)=>{bump(x,y);return powerups.length;},
      fixture:f=>{reset(f.seed??conditionSeed??0,{generator_revision:'world-seed-v1'});if(f.tiles){tiles=f.tiles;W=tiles[0].length;GOAL=(W-5)*T;}if(f.enemies)enemies=f.enemies;if(f.coins)coins=f.coins;plants=f.plants||pipePlants();powerups=f.powerups||[];Object.assign(p,f.player);recentPositions=[];changed();return snapshot();},
      probe:(direction,jump,n=1)=>{for(let i=0;i<n;i++)physics(direction,jump&&i===0);return snapshot();}
    });
    reset(options.seed,options.generationOptions);
    return api;
  }
  return Object.freeze({create,visibleControl});
});
