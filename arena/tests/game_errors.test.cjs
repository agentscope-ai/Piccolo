const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function load(){const context={window:{JevI18n:{t:(en,zh)=>zh}}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/playground/errors.js'),'utf8'),context);return context.window.JevGameErrors;}
test('repeated decision errors explain the actual bounded cause without raw JSON',()=>{
 const e=load().fromResponse({detail:{code:'decision_repeat_failed',cause:'rate_limited',sample_index:1}},429);
 assert.match(e.message,/限流/);assert.equal(e.code,'rate_limited');assert.equal(e.status,429);
 assert.ok(!e.message.includes('decision_repeat_failed'));
});
test('provider diagnostic text is not rendered from an unknown error object',()=>{
 const e=load().fromResponse({detail:{private:'fixture-secret'}},502);
 assert.ok(!e.message.includes('fixture-secret'));assert.match(e.message,/重试/);
});
