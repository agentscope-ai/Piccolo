const test=require('node:test');
const assert=require('node:assert/strict');
const data=require('../leaderboard/arena-independent.json');
const {success,csv}=require('../web/playground/arena-independent.js');
test('missing Piccolo scores stay missing in the table and all CSV dimensions',()=>{
  const lines=csv(data).split('\r\n');
  assert.equal(lines.length,221);
  const oneshot=lines.filter(line=>line.startsWith('"Piccolo",'));
  assert.equal(oneshot.length,22);
  assert.ok(oneshot.every(line=>line.split(',').slice(2).every(value=>value==='""')));
  for(const rows of [data.overall,...Object.values(data.by_game)]){
    assert.equal(success(rows.find(r=>r.name==='Blink')),null);
  }
});
test('published success rates retain the planned denominator and explicit errors',()=>{
  const luna=data.overall.find(r=>r.name==='GPT-6 Luna Decisions');
  assert.equal(success(luna),49/176);
  assert.equal(luna.success_rate_valid,49/170);
  assert.equal(luna.errors,6);
  assert.equal(success(data.by_game.mario_platformer.find(r=>r.name==='Blink')),null);
});
test('legacy first-party labels export as Piccolo without modifying raw records',()=>{
  const original=Object.freeze({id:'oneshot-w22m05r02-v5best-avg50',name:'OneShot',status:'pending'});
  const custom=Object.freeze({id:'external-custom',name:'OneShot Research Lab',status:'pending'});
  const output=csv({by_game:{example:[original,custom]}});
  assert.match(output,/"Piccolo","example"/);
  assert.match(output,/"OneShot Research Lab","example"/);
  assert.equal(original.name,'OneShot');
  assert.equal(original.id,'oneshot-w22m05r02-v5best-avg50');
});
