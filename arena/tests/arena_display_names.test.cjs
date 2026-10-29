const test=require('node:test');
const assert=require('node:assert/strict');
const {model}=require('../web/playground/elo.js');

test('registered Arena checkpoints use the requested release names',()=>{
  assert.equal(model('oneshot27b-game-rl-native-iter17','Piccolo 27B RL-1019-iter17 · Local'),'Piccolo 27B RL');
  assert.equal(model('oneshot27b-gameplay-terminal-rl4','Piccolo 27B RL-1012 · 本地'),'Piccolo 27B RL');
  assert.equal(model('oneshot27b-control-reviewed-sft-iter310','Piccolo 27B SFT-1015 · Local'),'Piccolo 27B SFT');
});

test('archived and identity-resolved names use the same release display mapping',()=>{
  assert.equal(model('archived-run','Piccolo 27B SFT-1015 · 本地'),'Piccolo 27B SFT');
  assert.equal(model('archived-run','Piccolo 27B RL-1019-iter17'),'Piccolo 27B RL');
  assert.equal(model('archived-run','Piccolo 27B RL'),'Piccolo 27B RL');
  assert.equal(model('archived-run','OneShot 27B SFT-1015 · 本地'),'Piccolo 27B SFT');
  assert.equal(model('archived-run','OneShot 27B RL-1019-iter17'),'Piccolo 27B RL');
  assert.equal(model('archived-run','OneShot (27B)'),'Piccolo (27B)');
  assert.equal(model('archived-run','Blink 27B RL-1019-iter17'),'Piccolo 27B RL');
  assert.equal(model('oneshot-hosted','OneShot'),'Piccolo');
  assert.equal(model('custom-model','OneShot Research Lab'),'OneShot Research Lab');
});

test('Arena removes only the provider suffix from model display names',()=>{
  for(const suffix of [' · DashScope',' - DashScope',' (DashScope)',' DashScope']){
    assert.equal(model('qwen3.8-max-dashscope','Qwen3.8 Max'+suffix),'Qwen3.8 Max');
  }
  assert.equal(model('qwen3.8-27b-base','Qwen3.8 27B · Local'),'Qwen3.8 27B · Local');
  assert.equal(model('other','MyDashScope'),'MyDashScope');
  assert.equal(model('other','DashScopeRouter'),'DashScopeRouter');
  assert.equal(model('rule-engine-v1','规则引擎'),'规则引擎');
});

test('display mapping preserves the source record and its exact model ID',()=>{
  const record=Object.freeze({id:'oneshot27b-game-rl-native-iter17',name:'OneShot 27B RL-1019-iter17',rating:1534.25});
  const display={...record,label:model(record.id,record.name)};
  assert.equal(display.label,'Piccolo 27B RL');
  assert.equal(display.id,record.id);
  assert.equal(display.name,record.name);
  assert.equal(display.rating,record.rating);
});
