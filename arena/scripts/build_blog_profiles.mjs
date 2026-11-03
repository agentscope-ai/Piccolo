#!/usr/bin/env node
// Freeze the Blog's capability profiles from the same registered results as Leaderboard.
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const ids = {
  'blink-27b-1028':'p27','blink-9b-1028':'p9','blink-4b-1028':'p4',
  'access-vllm-sr--d3':'d3','access-perplexity-ai--pplx-decider-v1.2':'perplexity',
  'access-inception--mercury-decide':'mercury','access-microsoft--microsoft-decision-1':'microsoft',
  'access-typesafe--jev-1.14':'typesafe','access-openai--gpt-6-luna-decisions':'luna',
  'access-Clef-27B-original':'clef','access-strands-decider-26B-A4B-gemma4-v1-2610':'strands',
};
const axes = {
  harness:[
    ['tools','Tool execution','工具执行与调用审核',['Tools &','execution'],60,['argument_validation','browser_action','concurrency_transaction','tool_call_review','tool_selection']],
    ['resources','Resource allocation','资源分配与协作调度',['Resource','allocation'],60,['budget_allocation','delegation','model_routing','reasoning_budget','subagent_dispatch']],
    ['context','Context & memory','上下文与记忆管理',['Context &','memory'],39,['cache_validity','context_compression','context_retention','memory_write']],
    ['permissions','Permission boundaries','权限安全与信任边界',['Permission','boundaries'],59,['browser_confirmation','injection_boundary','privacy_release','safety_gate','secret_egress','tool_permission']],
    ['completion','Completion & evidence','进度验收与证据核验',['Completion &','evidence'],51,['completion_verification','plan_progress','retrieval_evidence','termination_evidence','trajectory_progress','version_conflict']],
    ['recovery','Uncertainty & recovery','不确定性与异常恢复',['Uncertainty &','recovery'],26,['clarification_abstention','retry_or_escalate','retry_recovery']],
  ],
  data:[
    ['D1','Data admission','数据准入与过滤',['Data','admission'],90,['D1']],
    ['D2','Processing plans','算子与处理方案选择',['Processing','plans'],90,['D2']],
    ['D3','Artifact quality','数据产物质量评价',['Artifact','quality'],80,['D3']],
    ['D4','Information sufficiency','所需信息充分性',['Information','sufficiency'],100,['D4']],
    ['D5','Evidence & privacy','结论核验与隐私审查',['Evidence &','privacy'],80,['D5']],
    ['D6','Workflow control','数据任务执行控制',['Workflow','control'],60,['D6']],
  ],
};
const profiles={};
for (const kind of ['harness','data']) {
  const source='leaderboard/'+kind+'jevbench.json';
  const bytes=await readFile(new URL('../'+source,import.meta.url));
  const registered=JSON.parse(bytes);
  const groups=axes[kind].map(([id,en,zh,lines,samples,sourceAxes])=>({id,label:[en,zh],lines,samples,sourceAxes}));
  const valid=value=>typeof value==='number'&&Number.isFinite(value)?value:null;
  const models=registered.rows.map(row=>{
    if(!ids[row.model_id])throw Error('Unreviewed model identity: '+row.model_id);
    const values=groups.map(group=>{
      const entries=group.sourceAxes.map(id=>row.axes?.find(axis=>axis.id===id));
      if(entries.some(axis=>!axis||valid(axis.score)===null))return null;
      const n=entries.reduce((sum,axis)=>sum+axis.samples,0);
      if(n!==group.samples)throw Error('Task-count mismatch: '+row.model_id+'/'+group.id);
      if(entries.length===1)return entries[0].score;
      return entries.reduce((sum,axis)=>sum+axis.score*axis.samples,0)/n;
    });
    const metrics=row.metrics??{};
    const accuracy=valid(metrics.accuracy);
    if(values.every(value=>value!==null)&&accuracy!==null){
      const total=groups.reduce((sum,group)=>sum+group.samples,0);
      const weighted=values.reduce((sum,value,i)=>sum+value*groups[i].samples,0)/total;
      if(Math.abs(weighted-accuracy)>1e-10)throw Error('Accuracy does not reconcile: '+row.model_id);
    }
    return {id:ids[row.model_id],label:row.model_name,sourceModelId:row.model_id,evaluatedAt:row.evaluated_at,values,
      metrics:{accuracy,tv:valid(metrics.soft_tv),ece:valid(metrics.ece),brier:valid(metrics.brier)},
      validProbabilityViews:valid(kind==='harness'?metrics.soft_valid:metrics.valid),
      plannedProbabilityViews:kind==='harness'?60:500};
  });
  const dates=[...new Set(registered.rows.map(row=>row.evaluated_at?.slice(0,10)).filter(Boolean))].sort();
  profiles[kind]={title:registered.title,version:registered.version,evaluatedAt:dates.length>1?dates[0]+' – '+dates.at(-1):dates[0],source,
    sourceSha256:createHash('sha256').update(bytes).digest('hex'),protocol:registered.rows[0].protocol,
    scoreUnit:'accuracy_fraction',defaultVisible:['p27','d3','perplexity','mercury'],axes:groups,models,
    ...(kind==='harness'?{designTasks:325,hardTasks:295,hardQuestions:303,softViews:60,
      aggregation:'Scored Hard scenario mean_task_score values, weighted by the registered samples in each responsibility group. Soft views are excluded from the radar.'}
      :{tasks:500,choiceTasks:480,scoreTasks:20,
      aggregation:'Registered accuracy for each of D1-D6. All planned records remain in the denominator. Probability sum tolerance is 1e-3 with no renormalization.'})};
}
const target=new URL('../web/blog/benchmark-profiles.js',import.meta.url);
const output='// Generated by scripts/build_blog_profiles.mjs from the registered benchmark results.\n'
  +'// Grouped scores reconcile with the full planned task denominator; missing metrics remain null.\n'
  +'export const benchmarkProfiles = '+JSON.stringify(profiles,null,2)+';\n';
if(process.argv.includes('--check')){
  if(await readFile(target,'utf8')!==output)throw Error('Blog profiles are stale; run node scripts/build_blog_profiles.mjs.');
  console.log('Blog capability profiles match all registered model results.');
} else {await writeFile(target,output);console.log('Generated two benchmark profiles with '+profiles.harness.models.length+' models each.');}
