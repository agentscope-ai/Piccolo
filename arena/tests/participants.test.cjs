const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup() {
  const nodes = new Map();
  let mounted;
  const element = () => ({
    hidden:false, value:'', innerHTML:'', classList:{toggle(){},add(){},remove(){}},
    append(){}, before(){}, setAttribute(){}, querySelectorAll(){return []},
    replaceChildren(...children){this.options=children;this.innerHTML=''},add(option){this.options.push(option)},
    set id(value){this._id=value;nodes.set(value,this)},get id(){return this._id},
  });
  const get = id => {if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
  const scope = vm.createContext({
    window:{JevI18n:{t:(en)=>en,onChange(){}}},
    document:{getElementById:get,createElement:element,querySelector:()=>element(),querySelectorAll:()=>[],
      addEventListener(name,cb){if(name==='DOMContentLoaded')mounted=cb}},
    Option:function(text,value){return {text,value}},
    ConnectUI:{models:[{id:'oneshot-hosted',ready:true},{id:'external',ready:true}],modelLabel:m=>m.id},
    selectedPlay:'doudizhu',catalog:{games:[]},modelName:'oneshot-hosted',gameState:null,
    showcaseSession:{world:{kind:'doudizhu',current_player:0}},busy:false,showcaseBusy:false,batchRunning:false,
    JevPlayText:{ui:s=>s,goal:()=>'',html:s=>s},statMarkup:()=>'',showcaseInputs:()=>'',renderControls(){},PlayDraw:{draw(){}},esc:s=>String(s),clearTimeout(){},renderShowcaseGame(){},showcaseControls(){},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/playground/participants.js'),'utf8'),scope);
  mounted();
  return {scope,get,ui:scope.window.JevParticipants,
    choose(id,value){get(id).value=value;get(id).onchange()},
    actor(index){scope.showcaseSession.world.current_player=index},
    game(kind){scope.selectedPlay=kind;scope.showcaseSession.world.kind=kind;scope.window.JevParticipants.refresh()}};
}

test('three seats route independently, including the second farmer and external models',()=>{
  const s=setup();
  s.choose('participantFirst','human');
  s.choose('participantOpponent','rule');
  s.choose('participantThird','external');
  for(const [index,expected] of ['human','rule','external'].entries()){
    s.actor(index);assert.equal(s.ui.controller(),expected);
    assert.equal(s.ui.requestModel('showcases/step',{}),expected==='external'?'external':'oneshot-hosted');
  }
  assert.ok(s.ui.ready('rule'));
  assert.equal(s.get('participantThird').hidden,false);
});

test('switching to two seats hides the third but preserves its independent choice',()=>{
  const s=setup();s.choose('participantOpponent','human');s.choose('participantThird','external');
  s.game('texas_holdem');assert.equal(s.get('participantThird').hidden,true);
  s.actor(1);assert.equal(s.ui.controller(),'human');
  s.game('doudizhu');assert.equal(s.get('participantThird').hidden,false);
  s.actor(2);assert.equal(s.ui.controller(),'external');
  assert.equal(s.get('participantThird').value,'external');
  assert.deepEqual(Array.from(s.get('participantThird').options,o=>o.value),['human','rule','oneshot-hosted','external']);
});


test('view stays on the first human seat while active-seat labels follow every turn',()=>{
  const s=setup();assert.equal(s.ui.viewSeat(),1);
  for(const actor of [0,1,2,0]){
    s.actor(actor);
    const body=s.ui.requestBody('showcases/step',{revision:3});
    assert.equal(body.view_seat,1);
    assert.equal(s.ui.activeSeat(actor),true);
    assert.ok(s.ui.seatMarker(actor).startsWith('▶ '));
    assert.equal(s.ui.canAct(),actor===1);
  }
  s.choose('participantOpponent','rule');assert.equal(s.ui.viewSeat(),0);
  s.choose('participantThird','human');assert.equal(s.ui.viewSeat(),2);
  s.actor(0);assert.equal(s.ui.requestBody('showcases/new',{kind:'doudizhu'}).view_seat,2);
  s.actor(1);assert.equal(s.ui.requestBody('showcases/reveal',{}).view_seat,2);
  s.game('texas_holdem');assert.equal(s.ui.viewSeat(),0);
});


test('social table repaint and human reveal do not erase completed decision details',()=>{
  const s=setup(),panel=s.get('showcaseResult');
  panel.innerHTML='<div class="result">Piccolo probabilities</div>';
  s.scope.showcaseSession={world:{kind:'doudizhu',duel:true,current_player:1,handoff:true,steps:1,table:{view_seat:0,hand_count:19}}};
  s.ui.renderSocial();assert.match(panel.innerHTML,/Piccolo probabilities/);
  s.scope.showcaseSession.world.handoff=false;
  s.ui.renderSocial();assert.match(panel.innerHTML,/Piccolo probabilities/);
});
