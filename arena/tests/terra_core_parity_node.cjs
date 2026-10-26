/* Test RPC only. Imports the actual production core with no DOM or VM shim. */
'use strict';
const readline=require('node:readline');
const factory=require('../web/playground/terraria-core.js');
const arrival=require('../web/playground/world-arrival.js');
let clock=0,core=factory.create({seed:1,now:()=>clock}),settled=null;
arrival.install(core,'terraria_survival');
function privateState(){
  const s=core.renderState();
  return {world:Array.from(s.world),explored:Array.from(s.explored),surface:s.surf,spawn:s.spawn,goal:s.goal,
    enemies:s.enemies,items:s.items,chests:s.chests,player:s.P,gear:s.gear,stat:s.stat,wins:s.wins,
    deaths:s.deaths,frame:s.frame,evt:s.evt,buffs:s.buffs,agent:s.agent};
}
async function command(c){
  if(c.op==='reset'){core.reset(c.seed);core.activate(true);core.prepare({clock:'realtime'});settled=null;}
  else if(c.op==='prepare')core.prepare({clock:c.clock||'realtime'});
  else if(c.op==='act'){settled=null;core.act(c.action).then(value=>{settled=value;});}
  else if(c.op==='advance')core.advanceTo(c.frame);
  else if(c.op==='tick'){clock=c.time;core.tick(clock);}
  else if(c.op==='terminal')return core.terminal();
  else if(c.op==='private')return privateState();
  else if(c.op==='settled')return settled;
  else if(c.op!=='snapshot')throw Error('unknown test command');
  return core.snapshot();
}
const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
let serial=Promise.resolve();
rl.on('line',line=>{serial=serial.then(async()=>{
  try{process.stdout.write(JSON.stringify({ok:true,value:await command(JSON.parse(line))})+'\n');}
  catch(error){process.stdout.write(JSON.stringify({ok:false,error:String(error)})+'\n');}
});});
