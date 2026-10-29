const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function renderer(){
 const context={window:{},PlayDraw:{rotations:()=>[[[0,0],[1,0],[2,0],[3,0]]]}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/playground/tetris-renderer.js'),'utf8'),context);
 return context.window.JevTetrisRenderer;
}
function state(y,piece_id=1){return {kind:'tetris_placement',engine_revision:'tetris-realtime-v4-latency-contract',
 board:Array.from({length:12},()=>Array(10).fill(0)),active:{piece:'I',piece_id,x:2,y,rotation:0},
 ghost_cells:[[2,11],[3,11],[4,11],[5,11]],started:true,phase:'falling',steps:0,elapsed:y,
 gravity_clock:.4,gravity_interval:.8};}
test('every supported realtime revision uses the falling-piece renderer',()=>{
 const api=renderer();
 for(const revision of ['tetris-realtime-v1','tetris-realtime-v2-visible-consequences','tetris-realtime-v3-persistent-intent','tetris-realtime-v4-latency-contract'])
  assert.equal(api.supports({...state(0),engine_revision:revision}),true);
 assert.equal(api.supports({...state(0),engine_revision:'archived-turn-based'}),false);
 assert.equal(api.supports({...state(0),kind:'merge_2048'}),false);
});
test('gravity and received motion determine visible coordinates without advancing physics',()=>{
 const api=renderer(),before=state(2),after=state(4),untouched=JSON.stringify([before,after]);
 assert.equal(api.position(before).y,2.5);
 assert.equal(api.visualState(after,{before,progress:.5}).visual_active.y,3.5);
 assert.equal(JSON.stringify([before,after]),untouched);
});
test('lock and new-piece boundaries never interpolate one piece into the next',()=>{
 const api=renderer(),before=state(10),after={...state(0,2),steps:1};
 assert.equal(api.visualState(after,{before,progress:.9}).visual_active.piece_id,1);
 assert.equal(api.visualState(after,{before,progress:1}).visual_active.piece_id,2);
});
