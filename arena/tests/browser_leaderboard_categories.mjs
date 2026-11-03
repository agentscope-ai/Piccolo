import fs from 'node:fs';
const baseURL=process.env.JEV_PREVIEW_URL||'http://127.0.0.1:18086/';
const debugURL=process.env.JEV_CHROME_DEBUG||'http://127.0.0.1:19286';
const page=(await(await fetch(debugURL+'/json/list')).json()).find(p=>p.type==='page');
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));let serial=0;const pending=new Map(),errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);});
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
const pause=ms=>new Promise(r=>setTimeout(r,ms));
await call('Runtime.enable');await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await call('Page.navigate',{url:baseURL});await pause(1500);
console.log('initial',await evaluate('document.title'));
await evaluate(`document.querySelector('[data-tab="leaderboard"]').click()`);await pause(1500);
console.log('state',await evaluate(`({errors:document.querySelector('#leaderboardDetail').innerText.slice(0,400),tabs:[...document.querySelectorAll('[data-benchmark]')].map(n=>n.dataset.benchmark)})`));
const report=[];const out=process.argv[2]||'artifacts/leaderboard-preview';fs.mkdirSync(out,{recursive:true});
for(const [device,width] of [['desktop',1440],['mobile',390]]){
 await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:device==='mobile'});
 for(const lang of ['en','zh']){
  await evaluate(`document.querySelector('[data-language="${lang}"]').click()`);await pause(100);
  for(const bench of ['harnessjevbench','datajevbench','jevbench','decisionindex']){
   await evaluate(`document.querySelector('[data-benchmark="${bench}"]').click()`);await pause(100);
   const result=await evaluate(`({models:document.querySelectorAll('.lb-metrics-table tbody tr[data-result-model]').length,names:document.querySelector('.lb-metrics-table').innerText,heading:document.querySelector('.lb-radar-heading').innerText,axes:[...document.querySelectorAll('.lb-radar-axis')].map(n=>[...n.querySelectorAll('tspan')].map(t=>t.textContent).join(' ')),overflow:document.documentElement.scrollWidth>innerWidth+1})`);
   if(result.models!==10||result.names.includes('AutoThink')||result.names.includes('Qwen3.8-27B')||!result.names.includes('Instant')||result.overflow)throw Error(JSON.stringify({device,lang,bench,result}));
   const expectedKeys=bench==='harnessjevbench'?['accuracy','soft_tv']:bench==='decisionindex'?['native']:['accuracy','brier','ece'];
   const metricRows=await evaluate(`[...document.querySelectorAll('.lb-metrics-table tbody tr[data-result-model]')].map(tr=>({id:tr.dataset.resultModel,cells:[...tr.querySelectorAll('[data-metric]')].map(td=>({key:td.dataset.metric,text:td.textContent.trim(),help:td.dataset.metricHelp}))}))`);
   const sourceDocument=await(await fetch(baseURL+'api/v1/leaderboards/'+bench)).json();
   for(const row of metricRows){
    if(JSON.stringify(row.cells.map(c=>c.key))!==JSON.stringify(expectedKeys))throw Error('Wrong metric columns for '+bench);
    const original=sourceDocument.rows.find(r=>r.model_id===row.id);
    for(const cell of row.cells){
     const value=cell.key==='native'||(bench==='harnessjevbench'&&cell.key==='accuracy')?original.score:original.metrics[cell.key];
     const expected=value==null?'—':cell.key==='native'?value.toFixed(2):cell.key==='accuracy'?(100*value).toFixed(2)+'%':value.toFixed(4);
     if(cell.text!==expected||!cell.help)throw Error('Incorrect metric value/help: '+bench+'/'+row.id+'/'+cell.key);
    }
   }
   if(['jevbench','decisionindex'].includes(bench)&&(!result.heading.includes('Public')||!(await evaluate(`document.querySelector('[data-benchmark="${bench}"]').innerText`)).includes('Public')))throw Error('Missing Public heading');
   const version=await evaluate(`document.querySelector('.lb-radar-heading h3 .lb-benchmark-version')?.textContent`);
   if(version!==String(sourceDocument.version).replace(/^(\d)/,'v$1'))throw Error('Heading does not match the registered version: '+bench);
   if(['jevbench','decisionindex'].includes(bench)){
    const official=await evaluate(`document.querySelector('.lb-radar-heading h3 .lb-benchmark-link')?.href`);
    const expected=bench==='jevbench'?'https://github.com/fstandhartinger/jevbench':'https://huggingface.co/spaces/multimodalart/jev-decision-index';
    if(official!==expected)throw Error('Missing official benchmark link: '+bench);
   }
   if(['harnessjevbench','datajevbench'].includes(bench)){
    const status=await evaluate(`({tab:document.querySelector('[data-benchmark="${bench}"]').textContent,description:document.querySelector('.lb-benchmark-description')?.textContent})`);
    const expected=bench==='harnessjevbench'?'HarnessJevBench':'DataJevBench';
    if(status.tab!==expected)throw Error('Benchmark tab should contain only its name: '+bench);
    if(!status.description.includes(lang==='zh'?'自建 · 未公开':'Self-developed · Unreleased')||!status.description.includes(lang==='zh'?'内部评测预览':'Internal preview'))throw Error('Unreleased benchmark lacks an internal preview label: '+bench);
   }
   if(bench==='decisionindex'){
    const introduction=await evaluate(`document.querySelector('.lb-benchmark-about-body').textContent`);
    if(/quick|快速子集/i.test(introduction)||!introduction.includes(lang==='zh'?'缺失成绩保留为空':'missing results remain unavailable'))throw Error('Incorrect Decision Index scope note');
   }
   if(bench==='harnessjevbench'){
    if(result.axes.length!==6)throw Error('Expected six primary scenarios');
    const source=await(await fetch(baseURL+'api/v1/leaderboards/harnessjevbench')).json();
    for(const row of source.rows){
     const children=row.axes.filter(a=>['tool_selection','argument_validation','tool_call_review','browser_action','concurrency_transaction'].includes(a.id));
     const expected=(100*children.reduce((n,a)=>n+a.score*a.samples,0)/children.reduce((n,a)=>n+a.samples,0)).toFixed(1)+'%';
     const label=await evaluate(`document.querySelector('.lb-radar-dot[data-radar-axis="0"][data-radar-model-id="${row.model_id}"]')?.getAttribute('aria-label')`);
     if(!label?.includes(expected))throw Error('Primary weighting differs for '+row.model_id);
    }
    await evaluate(`(()=>{let s=document.querySelector('#lbHarnessLevel');s.value='secondary';s.dispatchEvent(new Event('change'));})()`);
    await evaluate(`(()=>{let s=document.querySelector('#lbHarnessCategory');s.value='all';s.dispatchEvent(new Event('change'));})()`);
    const expectedSecondary=new Set(source.rows.flatMap(row=>row.axes.map(axis=>axis.id))).size;
    if(await evaluate(`document.querySelectorAll('.lb-radar-axis').length`)!==expectedSecondary)throw Error('Secondary scenarios differ from registered results');
    const groups=await evaluate(`[...document.querySelectorAll('#lbHarnessCategory option')].map(n=>n.value).filter(x=>x!=='all')`);let total=0;
    for(const group of groups){await evaluate(`(()=>{let s=document.querySelector('#lbHarnessCategory');s.value='${group}';s.dispatchEvent(new Event('change'));})()`);total+=await evaluate(`document.querySelectorAll('.lb-radar-axis').length`);}
    if(total!==expectedSecondary)throw Error('Missing or duplicated scenarios: '+total);
    const secondaryShot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(`${out}/${device}-${lang}-harness-secondary.png`,Buffer.from(secondaryShot.data,'base64'));
    await evaluate(`(()=>{let s=document.querySelector('#lbHarnessLevel');s.value='primary';s.dispatchEvent(new Event('change'));})()`);
   }
   if(bench==='datajevbench'&&result.axes.some(x=>/^D[1-6]$/.test(x.trim())))throw Error('Unexpanded D label');
   const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(`${out}/${device}-${lang}-${bench}.png`,Buffer.from(shot.data,'base64'));
   await evaluate(`document.querySelector('.lb-group').scrollIntoView({block:'start'})`);await pause(100);
   const resultsShot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(`${out}/${device}-${lang}-${bench}-results.png`,Buffer.from(resultsShot.data,'base64'));
   await evaluate('scrollTo(0,0)');
   report.push({device,lang,benchmark:bench,models:result.models,metrics:expectedKeys,axes:result.axes,passed:true});
  }
 }
}
fs.writeFileSync(`${out}/browser-validation.json`,JSON.stringify({cases:report,errors},null,2));console.log(report.length+' browser cases passed; exceptions: '+errors.length);ws.close();
