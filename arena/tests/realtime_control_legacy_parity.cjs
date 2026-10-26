'use strict';
// Compare every existing field with the archived shared core; only the declared
// interface revision and newly added fields differ. No model/API/GPU involved.
const assert=require('node:assert/strict'),path=require('node:path');
const seedModule=require('../web/playground/world-seed.js'),current=require('../web/playground/mario-core.js');
if(!process.argv[2])throw Error('pass an explicit archived mario-core.js path');
const previous=require(path.resolve(process.argv[2]));let comparisons=0;
function oldFields(actual,expected,keys=[]){
 if(keys.join('.')==='action_execution.revision'){assert.equal(actual,'selected-visible-landing-v6-explicit-guard');return expected;}
 if(Array.isArray(expected))return actual.map((v,i)=>oldFields(v,expected[i],[...keys,String(i)]));
 if(expected&&typeof expected==='object')return Object.fromEntries(Object.keys(expected).map(k=>[k,oldFields(actual[k],expected[k],[...keys,k])]));
 return actual;
}
function compare(a,b){const actual=a.snapshot(),expected=b.snapshot();assert.deepEqual(oldFields(actual,expected),expected);comparisons++;}
(async()=>{for(let seed=0;seed<32;seed++){
 const engines=[current,previous].map(factory=>factory.create({seedModule,seed,viewportWidth:880,now:()=>0}));
 for(const g of engines){g.activate(true);g.prepare({clock:'realtime'});}compare(...engines);
 for(const action of ['right','left','jump','jump_right','jump_left','cross_right','wait']){
  for(const g of engines)g.advanceTo(g.snapshot().frame+19);compare(...engines);
  const promises=engines.map(g=>{g.prepare({clock:'realtime'});return g.act(action);});
  for(const g of engines)g.advanceTo(g.snapshot().frame+180);await Promise.all(promises);compare(...engines);
  if(engines[0].snapshot().outcome)break;
 }
}
console.log(JSON.stringify({passed:true,seeds:32,existing_field_snapshot_comparisons:comparisons,existing_actions:7,new_interface_fields_excluded_from_old_contract_comparison:true,physics_outcomes_candidate_old_fields_all_compared:true}));
})().catch(e=>{console.error(e);process.exitCode=1;});
