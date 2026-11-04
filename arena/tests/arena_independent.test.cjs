const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
test('public entry loads shared labels and translation without the ladder player',()=>{
 const root=path.resolve(__dirname,'../web');
 const page=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.match(page,/presentation-i18n.js/);assert.match(page,/model-display.js/);
 assert.doesNotMatch(page,/gameEloPanel|gamejevbench|visible-control|playground\/elo\.(?:js|css)|arena-independent/);
 for(const file of ['elo.js','elo.css','arena-independent.js','visible-control.js','replay.js','replay.css'])assert.ok(!fs.existsSync(path.join(root,'playground',file)));
 assert.ok(fs.existsSync(path.join(root,'playground/home-demo.js')));
});
