const test=require('node:test');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const fs=require('node:fs/promises');
const root=path.resolve(__dirname,'..');
const casesPromise=import(pathToFileURL(path.join(root,'web/blog/workflow-cases.js')).href);

test('each task family has one complete bilingual case and a valid illustrated action',async()=>{
 const {workflowCases}=await casesPromise;
 assert.deepEqual(Object.keys(workflowCases),['harness','data']);
 const expected={harness:[1,1,0,0,0,0],data:[1,2,1,1,2,2]};
 for(const [kind,scenes] of Object.entries(workflowCases)){
  assert.equal(scenes.length,6);
  assert.equal(new Set(scenes.map(s=>s.id)).size,6);
  assert.deepEqual(scenes.map(s=>s.answer),expected[kind]);
  for(const s of scenes){
   assert.ok(s.source_url.startsWith('https://'));
   for(const k of ['tab','title','background','goal','judge','policy','why','outcome','source_note']){
    assert.equal(s[k].length,2);assert.ok(s[k].every(text=>typeof text==='string'&&text.length>0),kind+'/'+s.id+'/'+k);
   }
   for(let lang=0;lang<2;lang++){
    assert.ok(s.answer>=0&&s.answer<s.options[lang].length);
    assert.equal(s.options[lang].length,s.options[1-lang].length);
    assert.ok(s.rows[lang].every(row=>row.length===s.headers[lang].length));
   }
   assert.equal(s.probabilities,undefined,'No invented probabilities');
  }
 }
});

test('original game recordings and the three demo sections remain available',async()=>{
 const html=await fs.readFile(path.join(root,'web/piccolo.html'),'utf8');
 for(const id of ['demogames','demoharness','demodata'])assert.ok(html.includes('id="'+id+'"'));
 for(const game of ['mario','hex','sokoban','2048','jump','othello','snake','tetris','dots-boxes'])await fs.access(path.join(root,'web/blog/assets',game+'.gif'));
 const release=await fs.readFile(path.join(root,'scripts/build_release.py'),'utf8');
 for(const asset of ['workflow-cases.js','workflow-demos.js','workflow-demos.css'])assert.ok(release.includes("'web/blog/"+asset+"'"));
 for(const asset of ['index.html','app.js','embed.js','style.css']){
  await fs.access(path.join(root,'web/showcase',asset));
  assert.ok(release.includes("'web/showcase/"+asset+"'"));
 }
});

test('model routing selects a model that fits both the task and budget',async()=>{
 const {workflowCases}=await casesPromise;
 const scene=workflowCases.harness.find(s=>s.id==='model-routing');
 const {task,cost_cap,models}=scene.state;
 const feasible=Object.entries(models).filter(([,model])=>
  model.context_tokens>=task.input_tokens
  && (!task.requires_structured_json||model.structured_json)
  && model.cost<=cost_cap
 ).sort((a,b)=>a[1].cost-b[1].cost);
 assert.ok(feasible.length>0);
 const selected=scene.options[0][scene.answer].match(/^Model ([A-D])$/)[1];
 assert.equal(selected,feasible[0][0]);
 assert.ok(models.A.context_tokens<task.input_tokens,'A cannot fit the contract');
 assert.ok(models.C.cost>cost_cap,'C is over budget');
 assert.equal(models.D.structured_json,false,'D cannot provide the required output');
 assert.match(scene.background[0],/illustrative/i);
 assert.match(scene.background[1],/示例配置/);
 assert.equal(scene.source_id,'blog-model-routing-example-v1');
 assert.doesNotMatch(scene.source_id,/^jev-harness-/,'An illustrative case must not inherit an unrelated benchmark ID');
});

// The presentation may shorten evidence and options, but its answer must remain
// bound to the pinned upstream reference rather than to a hand-authored index.
test('each Data case selects the published reference label from a pinned real task',async()=>{
 const {workflowCases}=await casesPromise;
 const audit=JSON.parse(await fs.readFile(path.join(root,'docs/demo-data-cases/selected-records.json'),'utf8'));
 const originals=new Map(audit.records.map(r=>[r.id,r]));
 assert.equal(originals.size,6);
 const {createHash}=require('node:crypto');
 const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
 for(const [index,scene] of workflowCases.data.entries()){
  const record=originals.get(scene.source_id);
  assert.ok(record);assert.ok(record.id.startsWith('D'+(index+1)+'-'));
  assert.equal(scene.benchmark_reference.revision,audit.revision);
  assert.equal(scene.option_ids[scene.answer],record.expected);
  assert.equal(scene.benchmark_reference.expected,record.expected);
  assert.equal(scene.state,record.state);
  assert.ok(scene.option_ids.every(id=>Object.hasOwn(record.question.criteria,id)));
  const hash=createHash('sha256').update(JSON.stringify(canonical(record))).digest('hex');
  assert.equal(scene.benchmark_reference.record_sha256,hash);
 }
 assert.equal(workflowCases.data[2].rows[0][1][1],'hotel north beach is near chinatown has internet.');
 assert.equal(workflowCases.data[2].rows[1][1][1],workflowCases.data[2].rows[0][1][1]);
});


test('overview frames follow article language and visibility, and accept only their own resize messages',async()=>{
 const vm=require('node:vm');
 const origin='https://preview.example';
 const frames=[],listeners={},documentListeners={};
 let language='zh',changeLanguage,observeEntries;
 const hosts=new Map(['harness','data'].map(group=>['piccolo-'+group+'-preview',{append(frame){frames.push(frame);}}]));
 const document={
  hidden:false,currentScript:{src:origin+'/showcase/embed.js?v=merge-revision'},
  getElementById:id=>hosts.get(id),
  addEventListener:(name,callback)=>documentListeners[name]=callback,
  createElement:()=>({style:{},listeners:{},contentWindow:{messages:[],postMessage(message,target){this.messages.push({message,target});}},addEventListener(name,callback){this.listeners[name]=callback;}})
 };
 const window={JevI18n:{get lang(){return language;},onChange(callback){changeLanguage=callback;}},addEventListener:(name,callback)=>listeners[name]=callback};
 const IntersectionObserver=class{constructor(callback){observeEntries=callback;}observe(){}disconnect(){}};
 vm.runInNewContext(await fs.readFile(path.join(root,'web/showcase/embed.js'),'utf8'),{window,document,location:{origin},URL,IntersectionObserver});
 assert.equal(frames.length,2);
 const [harness,data]=frames;
 assert.match(harness.src,/group=harness&lang=zh&v=merge-revision/);
 assert.match(data.src,/group=data&lang=zh&v=merge-revision/);
 assert.equal(harness.contentWindow.messages.at(-1).message.visible,false);
 observeEntries([{target:harness,isIntersecting:true}]);
 assert.equal(harness.contentWindow.messages.at(-1).message.visible,true);
 language='en';changeLanguage();
 assert.equal(harness.contentWindow.messages.at(-1).message.lang,'en');
 assert.equal(data.contentWindow.messages.at(-1).message.lang,'en');
 assert.equal(harness.contentWindow.messages.at(-1).target,origin);
 document.hidden=true;documentListeners.visibilitychange();
 assert.equal(harness.contentWindow.messages.at(-1).message.visible,false);
 listeners.message({source:harness.contentWindow,origin:'https://other.example',data:{type:'piccolo-showcase-height',height:800}});
 assert.equal(harness.style.height,undefined);
 listeners.message({source:{},origin,data:{type:'piccolo-showcase-height',height:800}});
 assert.equal(harness.style.height,undefined);
 listeners.message({source:harness.contentWindow,origin,data:{type:'piccolo-showcase-height',height:600.5}});
 assert.equal(harness.style.height,'606px');
 assert.equal(data.style.height,undefined);
 listeners.message({source:harness.contentWindow,origin,data:{type:'piccolo-showcase-height',height:Infinity}});
 assert.equal(harness.style.height,'606px');
});
