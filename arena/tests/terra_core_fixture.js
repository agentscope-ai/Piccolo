/* Test-only fixtures injected by the dedicated test harness. Never loaded by a production core. */
    bridge.fixture=function(f){jevRelease();jevActive=false;world.fill(AIR);explored.fill(1);enemies=[];drops=[];items=[];parts=[];chests=[];frame=1;regenT=0;
      P.x=f.x*TS;P.y=f.y*TS;P.vx=0;P.vy=0;P.hp=100;P.dead=0;P.ground=true;P.face=f.face||1;P.placeCD=0;jevAim=f.aim||'right';agent.atk=0;agent.digT=null;agent.digP=0;agent.on=false;
      gear={pick:f.pick||1,sword:1,armor:0,gems:0,pts:0,dirt:f.dirt===undefined?5:f.dirt,swordMul:1,pickMul:1,armorMul:1,potAtk:0,potArm:0};Object.keys(stat).forEach(function(k){stat[k]=0});Object.keys(buffs).forEach(function(k){buffs[k]=0});evt.name='';evt.t=0;evt.timer=1900;P.inv=0;P.maxhp=100;wins=0;deaths=0;jevHistory=[];jevPositions=[];jevCalls=0;jevSurfaceAnchor=null;jevEffects=[];jevBefore=null;jevEntityIds=new WeakMap();jevEntitySeq=0;jevCollectedItems=[];jevKnownGuardians={};jevVisited={};jevKnownSurfaces={};jevControl={effects:[],status:'idle',subgoal:null,event:null,no_progress_count:0};jevStart=null;jevTool=null;jevRuleFrames=0;jevRuleDecisions=0;jevAppliedFrames=0;
      progression=freshProgression();combatEvents=[];guardianDefeatedByPlayer=!!f.guardianDefeatedByPlayer;guardianDefeatedVia=guardianDefeatedByPlayer?'player_attack':null;jevEpisodeManaged=false;jevEpisodeTerminal=false;
      if(f.spawn)spawn={x:f.spawn[0]*TS,y:f.spawn[1]*TS};
      (f.enemies||[]).forEach(function(e){enemies.push(Object.assign({},e))});if(f.hp!==undefined)P.hp=f.hp;
      (f.tiles||[]).forEach(function(t){setT(t[0],t[1],t[2])});if(f.goal){goal.x=f.goal[0];goal.y=f.goal[1];setT(goal.x,goal.y,GOAL);explored[idx(goal.x,goal.y)]=f.exploredGoal?1:0}return jevSnapshot()};
    bridge.probe=function(action,n){clearKeys();jevKeys[action].forEach(function(k){keys[k]=1});for(var i=0;i<(n||36);i++)update(1);clearKeys();return jevSnapshot()};
    bridge.tile=function(x,y){return get(x,y)};
    bridge.inspectWorld=function(){return JSON.parse(JSON.stringify({world:Array.from(world),explored:Array.from(explored),surface:surf,spawn:spawn,goal:goal,enemies:enemies,items:items,chests:chests,player:P,gear:gear,stat:stat,wins:wins,deaths:deaths,frame:frame,evt:evt,buffs:buffs,agent:agent,lastHitF:lastHitF,gateFails:gateFails}))};
    bridge.testCosmetics=function(){burst(P.x,P.y,'#fff',50);pickThink('EXPLORE')};
  
