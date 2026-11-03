// Native vector redraws of the manuscript's data and feedback architecture.
// Keep experimental values separate from schematic process arrows.
const palette = ['#729398', '#a0b4a1', '#c5a173', '#b6b0a0', '#8b9aa9'];
const esc = value => String(value).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const text = (x,y,value,cls='label',anchor='start') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(value)}</text>`;
const lines = (x,y,values,cls='label',step=22) => values.map((v,i)=>text(x,y+i*step,v,cls)).join('');
const box = (x,y,w,h,cls='box',extra='') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" class="${cls}" ${extra}/>`;
const path = (d,cls='connector',extra='') => `<path d="${d}" class="${cls}" ${extra}/>`;
const arrow = (id,d,cls='connector') => path(d,cls,`marker-end="url(#${id}-arrow)"`);
const icon = (x,y,type) => {
  const shapes = {
    records:'<rect x="5" y="1" width="28" height="33" rx="4"/><path d="M11 10h16M11 17h16M11 24h10M1 8v30h25"/>',
    filter:'<path d="M1 3h34L23 20v12l-10 5V20Z"/><path d="M9 10h18"/>',
    record:'<rect x="1" y="1" width="34" height="35" rx="5"/><path d="M10 11 6 18l4 7M26 11l4 7-4 7M21 9l-6 18"/>',
    tags:'<path d="M1 5h21l13 13-18 18L1 20Z"/><circle cx="10" cy="13" r="3"/><path d="m24 7 12 12"/>',
    recipe:'<path d="M3 1h25l7 7v28H3Z"/><path d="M25 1v10h10M10 17h17M10 24h17M10 31h10"/>',
    model:'<path d="m18 1 17 9v19l-17 9L1 29V10Zm0 18 17-9M18 19 1 10M18 19v19"/>',
    human:'<circle cx="18" cy="10" r="8"/><path d="M2 36v-4c0-9 7-14 16-14s16 5 16 14v4"/>',
    agent:'<rect x="2" y="10" width="32" height="23" rx="7"/><path d="M18 10V3M0 18v9M36 18v9M11 33v5M25 33v5"/><circle cx="18" cy="2" r="2"/><circle cx="11" cy="20" r="2"/><circle cx="25" cy="20" r="2"/><path d="M12 27h12"/>',
    audit:'<circle cx="15" cy="15" r="12"/><path d="m23 24 12 12M8 15l5 5 9-10"/>',
    database:'<ellipse cx="18" cy="7" rx="16" ry="6"/><path d="M2 7v24c0 8 32 8 32 0V7M2 19c0 8 32 8 32 0"/>',
    chart:'<path d="M2 2v32h34M8 27V17h5v10M19 27V9h5v18M30 27V3h5v24"/>'
  };
  return `<g transform="translate(${x} ${y})" class="glyph">${shapes[type]}</g>`;
};
function svg(id,height,title,description,body,width=1040,extraStyle='') {
  return `<svg xmlns="http://www.w3.org/2000/svg" class="architecture-canvas" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="${id}-title ${id}-desc">
<title id="${id}-title">${esc(title)}</title><desc id="${id}-desc">${esc(description)}</desc>
<defs><marker id="${id}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="m1 1 8 4-8 4" fill="none" stroke="#8b7964" stroke-width="1.4" stroke-linejoin="round"/></marker></defs>
<style>
text{font-family:Inter,Arial,sans-serif;fill:#46453c;font-weight:400}.label{font-size:14px}.small{font-size:12px;fill:#7f786a}.tiny{font-size:11px;fill:#7f786a}.title{font-size:17px;font-weight:550;letter-spacing:-.3px}.number{font-size:35px;fill:#8f5e3f;letter-spacing:-1px}.stat{font-size:17px;fill:#70583f}.eyebrow{font-size:10px;font-weight:600;letter-spacing:1.4px;fill:#8c735b}.mono{font-size:13px;font-family:ui-monospace,monospace;fill:#556964}
.box{fill:#fbf9f3;stroke:#cfc7b8;stroke-width:1.2}.sage{fill:#f0f4ed;stroke:#a7b49d;stroke-width:1.2}.blue{fill:#eff4f3;stroke:#a0b5b6;stroke-width:1.2}.sand{fill:#faf2e6;stroke:#c7ac86;stroke-width:1.2}.neutral{fill:#f3f0e9;stroke:#bdb7a7;stroke-width:1.2}.inner{fill:#fffdf8;stroke:#dbd4c6;stroke-width:1}.connector{fill:none;stroke:#8b7964;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}.dashed{fill:none;stroke:#9b9587;stroke-width:1.2;stroke-dasharray:5 5;stroke-linecap:round}.rule{stroke:#ddd6c8;stroke-width:1}.glyph{fill:none;stroke:#566968;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}.stage-frame{transition:stroke .2s,fill .2s}.stage-frame.is-active{stroke:#a56440;stroke-width:2.3;fill:#f8ecdc}
${extraStyle}</style>
${body}</svg>`.replace(/<style>([\s\S]*?)<\/style>/, (_, css) =>
    '<style>' + css.replace(/([^{}]+)\{/g, (_, selector) => '.architecture-canvas ' + selector.trim() + '{') + '</style>');
}

export const dataPortrait = {
  domain:[['Everyday life',54.7],['Computing',13.6],['Math & science',12.7],['Arts & society',5.8],['Other domains',13.2]],
  task:[['Choice',58.87],['Yes / no',24.84],['Score',16.29]]
};
function distribution(x,y,width,items) {
  let offset=x;
  return items.map(([label,value],i)=>{
    const w=width*value/100, part=`<rect x="${offset}" y="${y}" width="${w}" height="12" fill="${palette[i]}"><title>${esc(label)}: ${value}%</title></rect>`;
    offset+=w;return part;
  }).join('');
}
export function dataArchitectureSVG() {
  const id='data-architecture';
  let body='';
  const steps=[
    [20,'01 / COLLECT','6.65M source records','records','blue',['Classification, reasoning,','preferences and tool use.','Add tasks from environments.']],
    [366,'02 / CHECK','Make the judgment valid','filter','sand',['Remove duplicates. Review answers,','constraints and candidate bias.','Check evaluation overlap.']],
    [712,'03 / ORGANIZE','Select what to learn','tags','sage',['Use one decision schema.','Tag the domain and required ability.','Select a recipe for the next run.']]
  ];
  for(const [x,label,title,glyph,color,copy] of steps){
    body+=box(x,20,308,244,color)+text(x+22,49,label,'eyebrow')+icon(x+22,72,glyph)+text(x+22,140,title,'title')+lines(x+22,176,copy,'label',26);
  }
  body+=arrow(id,'M334 137H360')+arrow(id,'M680 137H706');
  body+=box(20,295,1000,89,'inner')+text(42,323,'ONE RECORD, TWO USES','eyebrow');
  body+=text(42,354,'State + candidates + labels → supervision','title')+text(560,354,'Tags + learning feedback → data selection','title');
  body+=text(20,413,'Source records are a starting pool. Each experiment uses a selected and processed training recipe.','label');
  return svg(id,436,'From source records to a training recipe','Collect source records and environment tasks, check that the decisions are valid, then organize them with a shared schema and semantic tags. The record provides supervision; its tags connect learning feedback to future data selection.',body);
}

export function researchLoopSVG() {
  const id='research-loop';
  let body=text(20,30,'A RESEARCH ROUND','eyebrow')+text(1020,30,'Human: objectives, data scope and budget','label','end');
  const stages=[
    [20,60,'01','Diagnose the gap',['Inspect errors and learning signals.','Review the affected data slice.'],'Evidence to investigate','blue'],
    [560,60,'02','Specify an experiment',['Choose data changes and training settings.','Name the parent model and comparison.'],'A testable proposal','sand'],
    [560,287,'03','Build, train and evaluate',['Create the data version and train.','Check target and retained capabilities.'],'Results for each candidate','neutral'],
    [20,287,'04','Choose what to carry forward',['Compare checkpoints and task-level results.','Keep useful recipes and failed attempts.'],'Starting points for the next round','sage']
  ];
  for(const [x,y,n,title,copy,out,color] of stages){
    body+=box(x,y,460,178,color)+text(x+22,y+31,n,'eyebrow')+text(x+60,y+32,title,'title')+lines(x+22,y+72,copy,'label',27)+path(`M${x+22} ${y+119}H${x+438}`,'rule')+text(x+22,y+149,out,'stat');
  }
  body+=arrow(id,'M486 150H554')+arrow(id,'M790 244V281')+arrow(id,'M554 376H486')+arrow(id,'M250 281V244');
  body+=text(20,502,'The next proposal uses the previous results. The diagram describes the procedure, not measured gains.','label');
  return svg(id,526,'How feedback becomes the next experiment','Diagnose a capability gap, specify a proposal, build and evaluate candidates, and carry forward useful checkpoints, recipes and findings. Human researchers set the objectives, permitted data and budget.',body);
}

// Portrait layouts preserve the desktop figures' sequence and content without
// making readers pan across a cropped process on a phone.
const mobileType = '.label{font-size:17px}.small{font-size:16px}.title{font-size:19px}.stat{font-size:17px}.eyebrow{font-size:11px;letter-spacing:1.1px}';

export function dataArchitectureMobileSVG() {
  const id='data-architecture-mobile';
  let body='';
  const steps=[
    [20,'01 / COLLECT','6.65M source records','blue',['Classification, reasoning,','preferences and tool use.','Add tasks from environments.']],
    [252,'02 / CHECK','Make the judgment valid','sand',['Remove duplicates. Review answers,','constraints and candidate bias.','Check evaluation overlap.']],
    [484,'03 / ORGANIZE','Select what to learn','sage',['Use one decision schema.','Tag the domain and required ability.','Select a recipe for the next run.']]
  ];
  for(const [y,label,title,color,copy] of steps){
    body+=box(20,y,360,196,color)+text(40,y+32,label,'eyebrow')+text(40,y+72,title,'title')+lines(40,y+112,copy,'label',26);
  }
  body+=arrow(id,'M200 224V244')+arrow(id,'M200 456V476');
  body+=box(20,720,360,192,'inner')+text(40,749,'ONE RECORD, TWO USES','eyebrow');
  body+=text(40,785,'State + candidates + labels','label')+text(40,812,'→ Supervision','title')+path('M40 831H360','rule');
  body+=text(40,859,'Tags + learning feedback','label')+text(40,886,'→ Data selection','title');
  body+=lines(20,946,['Each experiment selects and processes','its own recipe from the source pool.'],'label',26);
  return svg(id,994,'From source records to a training recipe','Collect source records and environment tasks, check that the decisions are valid, then organize them with a shared schema and semantic tags. The record provides supervision; its tags connect learning feedback to future data selection.',body,400,mobileType);
}

export function researchLoopMobileSVG() {
  const id='research-loop-mobile';
  let body=text(20,25,'A RESEARCH ROUND','eyebrow')+box(20,43,360,65,'inner');
  body+=lines(40,69,['Human: objectives, data scope','and research budget'],'label',25);
  const stages=[
    ['01','Diagnose the gap',['Inspect errors and learning signals.','Review the affected data slice.'],'Evidence to investigate','blue'],
    ['02','Specify an experiment',['Choose data changes and training','settings. Name the parent model','and comparison.'],'A testable proposal','sand'],
    ['03','Build, train and evaluate',['Create the data version and train.','Check target and retained','capabilities.'],'Results for each candidate','neutral'],
    ['04','Choose what to carry forward',['Compare checkpoints and task results.','Keep useful recipes and failed','attempts.'],'Starting points for the next round','sage']
  ];
  stages.forEach(([n,title,copy,out,color],i)=>{
    const y=128+i*232;
    body+=box(20,y,360,200,color)+text(40,y+26,n,'eyebrow')+text(40,y+54,title,'title')+lines(40,y+90,copy,'label',23)+path(`M40 ${y+152}H360`,'rule')+text(40,y+181,out,'stat');
    if(i<stages.length-1) body+=arrow(id,`M200 ${y+208}V${y+224}`);
  });
  body+=lines(20,1056,['Results inform the next proposal.','Procedure only; no measured gains.'],'label',26);
  body+=arrow(id,'M380 1042V1102H8V218H14');
  return svg(id,1120,'How feedback becomes the next experiment','Diagnose a capability gap, specify a proposal, build and evaluate candidates, and carry forward useful checkpoints, recipes and findings. Human researchers set the objectives, permitted data and budget. The results inform the next proposal.',body,400,mobileType);
}

export function evolutionOverviewSVG(milestones) {
  const id='evolution-overview';
  const x=i=>72+i*90,y=score=>270-(score-45)*8;
  let body=text(20,25,'PICCOLO-27B / FULL-SUITE DECISION INDEX','eyebrow');
  for(const v of [50,60,70]) body+=path(`M52 ${y(v)}H1000`,'rule')+text(38,y(v)+5,String(v),'label','end');
  body+=path(milestones.map((p,i)=>(i?'L':'M')+x(i)+' '+y(p.score)).join(' '),'connector');
  milestones.forEach((p,i)=>{
    body+=`<circle cx="${x(i)}" cy="${y(p.score)}" r="4" fill="#9b6040"/>`+text(x(i),y(p.score)-14,p.score.toFixed(2),'label','middle')+text(x(i),295,String(i+1).padStart(2,'0'),'small','middle');
  });
  body+=text(20,330,'Representative checkpoints · joint data and training changes · not an isolated RSI ablation','label');
  return svg(id,350,'Piccolo-27B representative checkpoints','Full-suite Decision Index improves from 48.91 to 68.59 across representative experiments. These points combine data and training changes and do not isolate individual contributions.',body);
}

export function feedbackArchitectureSVG(active=-1) {
  const id='feedback-architecture';
  let body='';
  [[280,'Human','Objectives · budget','human','neutral'],[492,'Agent','Diagnose · design · execute','agent','blue'],[704,'Audit','Data · process · results','audit','sage']].forEach(([x,title,note,glyph,cls])=>{
    body+=box(x,18,188,90,cls)+icon(x+15,42,glyph)+text(x+62,53,title,'title')+text(x+15,91,note,'small');
  });
  body+=arrow(id,'M470 61H486','dashed')+arrow(id,'M682 61H698','dashed')+arrow(id,'M586 109V140','dashed');
  body+=box(20,150,226,414,'blue')+text(40,178,'FEEDBACK SIGNALS','eyebrow')+text(40,210,'What is being learned?','title');
  const traces=[['Mathematics','0.3225 → 0.0885','Falling divergence'],['Computing','0.1421 → 0.0526','Low divergence'],['Arts & media','0.2389 → 0.1735','Fluctuating across windows']];
  traces.forEach(([label,value,note],i)=>{
    const y=231+i*79;body+=text(40,y,label,'label')+text(40,y+25,value,'stat')+text(40,y+46,note,'tiny');
  });
  body+=path('M40 465H226','rule')+lines(40,491,['Data analysis','Model pass rates','Evaluation errors'],'label',24);
  body+=text(40,552,'KL endpoints from recorded windows','tiny');
  body+=box(280,150,490,414,'inner')+text(300,178,'EXPERIMENT LOOP','eyebrow');
  const stages=[
    [304,307,174,84,'Diagnose','Locate gaps','Review slices'],
    [415,200,222,76,'Propose','Target slice · data operation','Training setup · comparison'],
    [560,307,182,84,'Build & test','Process → train','Evaluate the checkpoint'],
    [415,438,222,76,'Retain','Compare task-level results','Reuse models and recipes']
  ];
  stages.forEach(([x,y,w,h,title,a,b],i)=>{
    body+=`<g data-architecture-stage="${i}">`+box(x,y,w,h,'box stage-frame'+(i===active?' is-active':''))+text(x+16,y+24,title,'title')+text(x+16,y+46,a,'small')+text(x+16,y+64,b,'small')+'</g>';
  });
  body+=arrow(id,'M392 302C392 254 394 239 409 239')+arrow(id,'M643 238C682 238 696 265 696 301')+arrow(id,'M696 397C696 449 668 477 643 477')+arrow(id,'M409 476C376 476 347 442 347 397');
  body+=icon(504,338,'model')+text(523,398,'Model','tiny','middle')+text(525,545,'A proposal records the intervention and comparison.','small','middle');
  body+=arrow(id,'M250 349H297');
  body+=box(804,150,216,414,'sage')+text(824,178,'CANDIDATE RESULTS','eyebrow')+text(824,210,'Keep the evidence','title');
  [['Branch A','Useful checkpoint'],['Branch B','Complementary capability'],['Branch C','Revise the proposal']].forEach(([label,note],i)=>{
    const y=235+i*76;body+=box(824,y,176,60,'inner')+text(838,y+23,label,'label')+text(838,y+45,note,'tiny');
  });
  body+=text(824,498,'Record why it worked,','label')+text(824,521,'or why it did not.','label')+text(824,550,'Checkpoints · recipes · findings','tiny');
  body+=arrow(id,'M775 349H798');
  body+=box(20,607,1000,98,'sand')+text(40,634,'DATAJUICER-SANDBOX / EXECUTION','eyebrow');
  body+=text(40,663,'Factory · Hook · Pipeline','title')+text(40,687,'Processing, training and evaluation','small');
  [['Delete / downsample','Reduce errors & repetition'],['Filter / rebalance','Target + background + replay'],['Audit / rewrite','Repair conditions & answers'],['Targeted synthesis','Add missing judgments']].forEach(([a,b],i)=>{
    const x=330+i*171;body+=path(`M${x-14} 628V688`,'rule')+text(x,650,a,'label')+text(x,677,b,'tiny');
  });
  body+=arrow(id,'M650 570V601')+text(665,591,'execute','tiny')+arrow(id,'M390 601V570')+text(304,591,'return results','tiny');
  body+=box(20,741,1000,89,'neutral')+icon(40,766,'database')+text(94,769,'DATAJUICER-PANEL / EXPERIMENT ASSETS','eyebrow');
  body+=text(94,802,'Data versions · Parent models · Configurations · Results · Provenance · Memory','label');
  body+=arrow(id,'M525 736V711','dashed')+arrow(id,'M1025 510H1032V787H1026');
  body+=path('M20 787H6V192H14','dashed')+text(20,860,'Stored learning signals and experiment history inform the next proposal.','small');
  return svg(id,878,'Agentic Data Engineering architecture','Human objectives, an agent and auditing guide an experiment loop. Recorded learning signals feed diagnosis, proposals execute in Sandbox, and candidate models, recipes and findings are retained in Panel. KL values are endpoints from the source figure, not interpolated curves.',body);
}
