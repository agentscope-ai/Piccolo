const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../web/connections.js'),'utf8').split('/* Temporary, browser-owned connections.')[0];
const scope={window:{JevI18n:{t:(en)=>en}}};
vm.createContext(scope);vm.runInContext(source,scope);
const labels=scope.window.JevModelLabels;

test('hosted and published labels use Piccolo with historical IDs intact',()=>{
  for(const id of ['oneshot-hosted','oneshot-w22m05r02-v5best-avg50','oneshot-rl-r6-iter0000019']){
    assert.equal(labels.model(id,'OneShot'),'Piccolo');
  }
  const record=Object.freeze({id:'oneshot27b-game-rl-native-iter17',name:'OneShot 27B RL-1019-iter17'});
  assert.equal(labels.model(record),'Piccolo 27B RL-1019-iter17 · Local');
  assert.equal(record.name,'OneShot 27B RL-1019-iter17');
  assert.equal(record.id,'oneshot27b-game-rl-native-iter17');
});

test('legacy release names normalize without renaming third-party or custom labels',()=>{
  assert.equal(labels.displayName('archived-run','OneShot (27B)'),'Piccolo (27B)');
  assert.equal(labels.displayName('archived-run','Blink (27B)'),'Piccolo (27B)');
  assert.equal(labels.displayName('archived-run','QwenJev 27B RL'),'Piccolo 27B RL');
  for(const label of ['Qwen3.8 27B','GPT-6 Luna Decisions','OneShot Research Lab','My OneShot experiment']){
    assert.equal(labels.displayName('custom-model',label),label);
  }
  assert.equal(labels.model('access-Clef-27B-original','Cloudflare Clef (27B)'),'Cloudflare Clef (27B)');
});
