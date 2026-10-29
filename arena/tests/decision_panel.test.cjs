const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/showcases.js'),'utf8');
function setup(){
 const nodes=new Map();const element=()=>({innerHTML:'',textContent:'',children:[],classList:{add(){},remove(){}},prepend(n){this.children.unshift(n)}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
 const scope=vm.createContext({$:get,document:{createElement:element},window:{JevParticipants:{renderSocial:()=>false}},
   JevI18n:{t:(en,zh)=>zh},JevPlayText:{ui:x=>x,text:x=>x,html:x=>x,goal:()=>'',event:()=>''},
   resultHtml:r=>'<div class="result">'+r.value+' '+r.distribution[0].probability+'</div>',
   showcaseInputs:()=>'',statMarkup:()=>'',registryGeneric:()=>false,legacyAgentShowcase:()=>false,
   renderControls(){},drawShowcase(){},lastSocialCanvasKind:'uno',
   showcaseSession:{world:{kind:'uno',stats:[],handoff:true},input:null}});
 const a=source.indexOf('function renderShowcaseDecision('),b=source.indexOf('\nasync function showcaseStep(',a);
 const c=source.indexOf('function renderShowcaseGame('),d=source.indexOf('\nfunction drawShowcase(',c);
 vm.runInContext(source.slice(a,b)+'\n'+source.slice(c,d),scope);
 return {scope,get};
}
test('measured result remains visible through generic private handoff and reveal',()=>{
 const {scope,get}=setup();
 scope.renderShowcaseDecision({result:{value:'play',distribution:[{probability:.8}]}},'玩家1 · Piccolo');
 const before=get('showcaseResult').innerHTML;
 scope.renderShowcaseGame();assert.equal(get('showcaseResult').innerHTML,before);
 scope.showcaseSession.world.handoff=false;scope.renderShowcaseGame();assert.equal(get('showcaseResult').innerHTML,before);
 assert.equal(get('showcaseResult').children[0].textContent,'玩家1 · Piccolo');
});
test('forced moves and rule steps explicitly identify that no model result exists',()=>{
 const {scope,get}=setup();
 scope.renderShowcaseDecision({forced:true,result:null});assert.match(get('showcaseResult').textContent,/未调用模型/);
 scope.renderShowcaseDecision({controller:'rule_engine',action_name:'pass'});assert.match(get('showcaseResult').textContent,/规则引擎.*pass/);
 scope.renderShowcaseDecision({decision_timing:{latency_seconds:1}});assert.match(get('showcaseResult').textContent,/暂不公开/);
});
