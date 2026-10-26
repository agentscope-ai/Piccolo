'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const coreModule=require('../web/playground/terraria-core.js');
const arrival=require('../web/playground/world-arrival.js');
const results=[];
function checked(name,fn){fn();results.push({name,passed:true});}
async function main(){
  assert.equal(typeof globalThis.window,'undefined');assert.equal(typeof globalThis.document,'undefined');
  let clock=0;
  const g=coreModule.create({seed:17,now:()=>clock});arrival.install(g,'terraria_survival');
  checked('production_exports_no_test_privileges',()=>{
    for(const key of ['fixture','probe','inspectWorld','testCosmetics'])assert.equal(g[key],undefined);
  });
  g.activate(true);g.prepare({clock:'realtime'});
  checked('terminal_and_render_polling_do_not_observe_or_mutate',()=>{
    const before=structuredClone(g.snapshot());
    for(let i=0;i<100;i++){g.terminal();g.renderState();}
    assert.deepEqual(g.snapshot(),before);
  });
  checked('private_renderer_copy_cannot_modify_world',()=>{
    const before=structuredClone(g.snapshot()),scene=g.renderState();
    scene.world.fill(0);scene.P.hp=-1;scene.enemies.length=0;
    assert.deepEqual(g.snapshot(),before);
  });
  checked('model_snapshot_has_no_private_scene_or_seed',()=>{
    const s=g.snapshot();
    for(const key of ['world','surface','spawn','renderState','replay_scene','seed','conditionSeed'])assert.equal(s[key],undefined);
    assert(s.map.tiles.some(row=>row.includes(-1)));
  });
  checked('original_50ms_accumulator_cap_preserved',()=>{
    const before=g.terminal().frame;clock+=1000;g.tick(clock);
    assert(g.terminal().frame-before>0);assert(g.terminal().frame-before<=3);
  });
  g.reset(17);g.activate(true);g.prepare({clock:'step'});
  checked('step_clock_pauses_without_selected_action',()=>{
    const before=g.terminal().frame;clock+=100;g.tick(clock);assert.equal(g.terminal().frame,before);
  });
  let settled=false;const pending=g.act('move_right').then(s=>{settled=true;return s;});
  await Promise.resolve();assert.equal(settled,false);
  const start=g.terminal().frame;for(let i=0;i<36;i++){clock+=20;g.tick(clock);}
  const done=await pending;assert(settled);assert.equal(done.frame-start,36);
  results.push({name:'act_promise_completes_only_through_real_ticks',passed:true});
  checked('step_mode_stops_at_action_completion',()=>{
    const before=g.terminal().frame;clock+=100;g.tick(clock);assert.equal(g.terminal().frame,before);
  });
  const first=coreModule.create({seed:1299000129,now:()=>0});
  const replay=coreModule.create({seed:1299000129,now:()=>0});
  for(const item of [first,replay]){arrival.install(item,'terraria_survival');item.activate(true);item.prepare({clock:'realtime'});}
  let comparisons=0;
  for(const action of ['explore_right','mine_down','collect_visible','return_surface','fight_nearest','recover','explore_left']){
    for(const item of [first,replay])item.prepare({clock:'realtime'});
    assert.deepEqual(first.snapshot(),replay.snapshot());comparisons++;
    const end=first.terminal().frame+23;first.advanceTo(end);replay.advanceTo(end);
    const a=first.act(action),b=replay.act(action);
    for(let n=0;n<360;n++){
      const frame=first.terminal().frame+1;first.advanceTo(frame);replay.advanceTo(frame);
      assert.deepEqual(first.snapshot(),replay.snapshot());comparisons++;
    }
    assert.deepEqual(await a,await b);
  }
  results.push({name:'same_node_full_frame_replay_is_bit_exact',passed:true,comparisons});
  const separate=coreModule.create({seed:17,now:()=>0}),before=separate.snapshot();
  first.reset(99);assert.deepEqual(separate.snapshot(),before);
  results.push({name:'independent_instance_reset_has_no_shared_mutation',passed:true});
  const live=coreModule.create({seed:17});live.activate(true);const waiting=live.prepare({clock:'realtime'});
  const timer=setInterval(()=>live.tick(performance.now()),10);
  await new Promise(resolve=>setTimeout(resolve,220));clearInterval(timer);
  const after=live.snapshot();assert(after.frame>waiting.frame+5);assert.equal(after.decisions,waiting.decisions);
  results.push({name:'real_timer_advances_world_while_policy_waits',passed:true,frames:after.frame-waiting.frame,
    decisions:after.decisions-waiting.decisions});
  const result={passed:true,checks:results,scope:'actual shared module in Node; no DOM, VM, model or GPU'};
  if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({passed:true,checks:results.length}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
