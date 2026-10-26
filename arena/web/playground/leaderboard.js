(function () {
  'use strict';
  const byId=id=>document.getElementById(id);
  const localize=window.BlinkArenaI18n.createPresentationTranslator({...window.BlinkArenaI18n.entries,...{"General decision making":"通用决策","Data decisions":"数据决策","Decision benchmarks":"决策基准","Tools and execution":"工具与执行","Game evaluation":"游戏评测","Accuracy":"准确率","Quick subset index":"快速子集指数","Decision Index":"决策指数","Game-weighted win rate":"游戏等权胜率","Mean Hard task score":"Hard 任务平均分","Native author-labelled scoring over the full public set. Failures stay in the planned denominator.":"按作者原生标注对完整公开集计分，失败保留在计划分母中。","Decision Index 0.3 full public suite, with official chance correction and domain weighting. Private tests are not included.":"Decision Index 0.3 公开评测集，含随机基线校正和领域加权；不包含私有测试。","Two views. Hard scores average axes within calls, calls within tasks, then tasks equally. Soft distribution metrics remain separate; failures stay in the denominator.":"采用两个视图。Hard 分数先在调用内平均各维度，再在任务内平均调用，最后按任务等权。Soft 分布指标单列，失败保留在分母中。","Evaluation protocol":"评测协议","Dataset and scoring":"数据集与计分","Version and scoring record":"版本与计分记录","See the registered evaluation protocol.":"详见已登记的评测协议。","See source":"详见来源","Dataset":"数据集","Version":"版本","unregistered":"未登记","Metric":"指标","Identity":"身份","Source":"来源","Run":"运行","Coverage":"覆盖","Protocol":"协议","Archived protocol":"归档协议","Strict scoring record":"严格计分记录","Before repair":"修复前","Details":"详情","Results":"成绩","Score":"得分","Samples":"样本","Errors":"错误","No results for the current version.":"当前版本暂无成绩。","Win rate":"胜率","95% CI":"95% 置信区间","Timeouts":"超时","Per-game results":"分游戏成绩","Archived failed attempts stay in the denominator. Incomplete games have no final win rate.":"归档失败尝试保留在分母中，未完成游戏不显示最终胜率。","Evaluation progress":"评测进度","Top-k probability estimate":"Top-k 概率估计","Full observed distributions":"完整观测分布","Estimated distributions":"估计分布","Missing candidate probabilities are estimated as zero before normalization, not observed zeros. Soft and calibration scores depend on this estimate. Strict score":"缺失候选概率在归一化前估为零，并非实际观测为零。Soft 与校准分数依赖这一估计。严格得分","DashScope top-k estimates":"DashScope top-k 估计","DashScope top-k probabilities":"DashScope top-k 概率","Local complete candidate probabilities":"本地完整候选概率","Accuracy by capability":"各能力准确率","Chance-corrected domain skill":"随机基线校正领域能力","Hard task score by scenario":"各场景 Hard 任务得分","Native per-family accuracy with full planned denominators. Sample counts differ across axes.":"使用完整计划分母的原生能力分类准确率，各维度样本数不同。","Native public-suite area skill × 100, with official chance correction. Separate from raw accuracy; private tests are not included.":"原生公开评测集领域能力分 × 100，含随机基线校正；与原始准确率分开，不包含私有测试。","Native Hard task scores, two views, tasks weighted equally. Soft-only scenarios have no Hard score and remain unavailable.":"原生 Hard 任务得分，两个视图，任务等权。仅有 Soft 指标的场景没有 Hard 得分，保留为缺失。","Soft-only; no Hard score":"仅 Soft；无 Hard 得分","Rule engine · board games only":"规则引擎 · 仅棋盘游戏","Current Arena · settled matches":"当前天梯 · 已结算对局","No settled valid matches":"暂无已结算有效对局","Match points by game":"各游戏对局得分率","Win = 1, draw = 0.5, loss = 0, divided by settled valid matches. Single-player outcomes compare final scores using the same game and seed. This 0–100% rate is separate from Elo. Failed or unsettled matches do not produce invented outcomes.":"胜记 1 分，平记 0.5 分，负记 0 分，再除以已结算有效对局数。单人游戏按同游戏、同种子的最终成绩比较。这一 0–100% 得分率与 Elo 分开计算。失败或未结算对局不填补结果。","Refresh failed; showing last settled records":"刷新失败；显示上次已结算记录","Arena records unavailable":"天梯记录暂不可用","Live Arena results":"当前天梯成绩","Loading Arena results":"读取天梯成绩中","No capability or scenario scores for the current registered results.":"当前登记成绩暂无能力或场景分数。","Awaiting dimension scores":"等待维度成绩","DashScope · includes top-k estimates":"DashScope · 含 top-k 估计","DashScope · top-k probabilities":"DashScope · top-k 概率","Local · full candidate probabilities":"本地 · 完整候选概率","Registered result snapshot":"已登记成绩快照","Native evaluation scores":"原生评测成绩","Local full candidate probabilities and DashScope top-k protocols are shown together. Hover over a model for its protocol; scoring details are preserved in the result records.":"同时展示本地完整候选概率与 DashScope top-k 协议的结果。悬停模型可查看协议，成绩记录中保留详细计分口径。","Each axis spans 0 to 100; outward is higher. Missing dimensions remain disconnected, never zero-filled. Full values are available in dimension details.":"各轴范围为 0–100，向外数值越高。缺失维度保留断线，不填零。完整数值见维度详情。","Chart view":"图表视图","Fit":"总览","Expand":"放大","CAPABILITY RADAR":"能力雷达图","Capability radar":"能力雷达图","Capabilities":"能力","Games":"游戏","No dimension scores yet":"暂无维度得分","Inspect dimension":"查看维度","Dimension / scenario":"能力 / 场景","Missing values are shown as gaps and —.":"缺失值以断线和 — 表示。","No score for this dimension":"该维度暂无得分","Select a model to view its scores":"选择模型查看得分","Loading results…":"读取成绩中…","No registered results yet.":"暂无已登记成绩。","Could not load results":"成绩加载失败","unavailable":"暂无数据","requests":"请求","valid questions":"有效题目","questions":"题目","tasks":"任务","views":"视图","episodes":"局","records":"记录","sources":"来源","scenarios":"场景","completed":"已完成","remaining":"剩余","sub-benchmarks":"子基准","pts":"分","results":"成绩"}},'.lb-radar-axis,#lbRadarDimension option,.lb-radar-inspect>strong,.lb-radar-values tbody th');
  const localizeLeaderboard=()=>['leaderboardTabs','leaderboardDetail','leaderboardStatus','leaderboardRefresh'].forEach(id=>localize(byId(id)));
  let loadError='';

  const definitions=[['gamejevbench','Blink Arena','Game evaluation'],['jevbench','JevBench','General decision making'],['decisionindex','DecisionIndex','Decision benchmarks'],['harnessjevbench','HarnessJevBench','Tools and execution'],['datajevbench','DataJevBench','Data decisions']];
  let selected='jevbench',payload=null,loading=false;
  const html=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const valueText=value=>value==null?'—':typeof value==='object'?JSON.stringify(value):String(value);
  const percent=value=>Number.isFinite(value)?(100*value).toFixed(1)+'%':'—';
  const number=value=>Number.isFinite(value)?value.toLocaleString('en-US'):'—';
  const modelLabel=row=>{
    const label=window.JevModelLabels?.model(row.model_key||row.id,row.model||row.name,row.model_identity)||window.BlinkArenaLabels?.model(row.model_key||row.id,row.model||row.name)||row.model_key||row.id||'Model';
    const estimated=row.approximation||/candidate-topk-estimate/.test(row.runtime_protocol||'')||row.display_metrics?.calibration_estimated>0;
    return estimated&&!/top[- ]?k/i.test(label)?label+' · '+(window.JevI18n?.t('Top-k estimate','Top-k 估计')||'Top-k estimate'):label;
  };
  const logoMarkup=row=>window.JevModelLogo?.markup(row.logo)||'';
  const chartLabel=row=>({'access-microsoft--microsoft-decision-1':'Microsoft Decision 1','access-inception--mercury-decide':'Mercury Decide','access-typesafe--jev-1.14':'TypeSafe JEV 1.14','access-typesafe--jev-1.13':'TypeSafe JEV 1.13'})[row.id]||row.label.replace(/ · (?:Local|本地|原版（本地）)$/, '');
  const ownModelIds=['oneshot27b-control-reviewed-sft-iter310','oneshot27b-gameplay-terminal-rl4','oneshot27b-game-rl-native-iter17'];
  const isOwnModel=id=>ownModelIds.includes(id);
  const tableFilters=new Map(), radarSearch=new Map();
  const gameLabel=id=>window.BlinkArenaLabels?.game(id)||id;
  const metricLabels={accuracy:'Accuracy',quick_subset_public_index_estimate:'Quick subset index',decision_index:'Decision Index',game_macro_win_rate:'Game-weighted win rate',mean_task_score:'Mean Hard task score'};
  const datasetNotes={jevbench:'Native author-labelled scoring over the full public set. Failures stay in the planned denominator.',decisionindex:'Decision Index 0.3 full public suite, with official chance correction and domain weighting. Private tests are not included.',harnessjevbench:'Two views. Hard scores average axes within calls, calls within tasks, then tasks equally. Soft distribution metrics remain separate; failures stay in the denominator.'};
  function sourceLink(url,label) {
    if(typeof url!=='string'||!/^(https?:\/\/|\.\/|\/)/i.test(url)||url.startsWith('//'))return html(label);
    return '<a href="'+html(url)+'" target="_blank" rel="noopener noreferrer">'+html(label)+' ↗</a>';
  }
  function tabs() {
    const host=byId('leaderboardTabs');
    if(!host.querySelector('[data-benchmark]'))host.innerHTML=definitions.map(([id,title,description])=>{
      const titleMarkup=({harnessjevbench:'Harness<wbr>JevBench',gamejevbench:'Blink <wbr>Arena',datajevbench:'Data<wbr>JevBench',decisionindex:'Decision<wbr>Index'})[id]||html(title);
      return '<button type="button" class="lb-tab'+(selected===id?' active':'')+'" role="tab" id="lb-tab-'+id+'" aria-controls="leaderboardDetail" aria-selected="'+(selected===id)+'" data-benchmark="'+id+'"><strong>'+titleMarkup+'</strong></button>';
    }).join('');
    host.querySelectorAll('button').forEach(button=>{
      button.classList.toggle('active',selected===button.dataset.benchmark);
      button.setAttribute('aria-selected',String(selected===button.dataset.benchmark));
      button.onclick=()=>{selected=button.dataset.benchmark;render();};
    });
  }
  function coverageText(coverage) {
    if(!coverage||typeof coverage!=='object')return valueText(coverage);
    if('completed_requests' in coverage)return number(coverage.completed_requests)+' / '+number(coverage.planned_requests)+' requests; '+number(coverage.completed_questions)+' / '+number(coverage.planned_questions)+' questions';
    if('completed_views' in coverage)return number(coverage.tasks)+' tasks; '+number(coverage.completed_views)+' / '+number(coverage.planned_views)+' views';
    if('games' in coverage)return number(coverage.games)+' games · '+number(coverage.completed)+' / '+number(coverage.planned)+' episodes';
    if('questions' in coverage)return number(coverage.valid)+' / '+number(coverage.questions)+' valid questions';
    return valueText(coverage);
  }
  function protocolMarkup(protocol) {
    if(!protocol||typeof protocol!=='object')return '';
    return '<details class="lb-protocol"><summary>Evaluation protocol</summary><pre>'+html(JSON.stringify(protocol,null,2))+'</pre></details>';
  }
  function datasetMarkup(benchmark) {
    const dataset=benchmark.dataset;if(!dataset||typeof dataset!=='object'||!Object.keys(dataset).length)return '';
    const scope=[number(dataset.records)+(benchmark.id==='harnessjevbench'?' tasks':' records'),number(dataset.questions)+' questions'];
    if(Number.isFinite(dataset.sources))scope.push(number(dataset.sources)+' sources');
    if(Number.isFinite(dataset.scenarios))scope.push(number(dataset.scenarios)+' scenarios');
    const paths=Array.isArray(dataset.source_files)&&dataset.source_files.length?dataset.source_files:[dataset.source_root].filter(Boolean);
    return '<section class="lb-dataset" aria-label="Dataset"><div class="lb-dataset-heading"><strong>Version '+html(dataset.version||benchmark.version||'unregistered')+'</strong><span class="lb-dataset-scope">'+html(scope.join(' · '))+'</span></div><details class="lb-dataset-sources"><summary>Dataset and scoring</summary><p><b>Metric: </b>'+html(metricLabels[dataset.primary_metric]||dataset.primary_metric||'See source')+'</p><p>'+html(benchmark.id==='decisionindex'?metricText('Native scoring with chance correction and domain weighting. The registered dataset version determines whether this is the quick subset or full suite.','采用随机基线校正和领域加权的原生计分；快速子集或全量范围以登记的数据集版本为准。'):datasetNotes[benchmark.id]||'See the registered evaluation protocol.')+'</p><ul>'+paths.map(path=>'<li><code>'+html(path)+'</code></li>').join('')+'</ul><p>'+sourceLink(dataset.source_url,'Version and scoring record')+'</p></details></section>';
  }
  function gameBreakdown(row) {
    if(!Array.isArray(row.by_game)||!row.by_game.length)return '';
    const cards=row.by_game.map(game=>{const complete=game.completed===game.planned&&!game.invalid;return '<li><strong>'+html(gameLabel(game.kind))+'</strong><span>'+number(game.completed)+' / '+number(game.planned)+' completed · '+number(game.wins)+' / '+number(game.attempts)+' wins</span><span>Win rate '+(complete?percent(game.score):'Incomplete')+' · 95% CI '+(complete&&Array.isArray(game.interval95)?game.interval95.map(percent).join('–'):'—')+'</span><span>Errors '+number(game.errors)+' · Timeouts '+number(game.timeouts)+' · Budget exhausted '+number(game.budget_exhausted)+'</span></li>';}).join('');
    return '<tr class="lb-game-details"><td colspan="7"><details><summary>Per-game results · '+row.by_game.length+' games</summary><ul class="lb-game-cards">'+cards+'</ul><p class="muted">Archived failed attempts stay in the denominator. Incomplete games have no final win rate.</p></details></td></tr>';
  }
  function progressMarkup(progress) {
    if(!progress||!Number.isFinite(progress.total)||progress.total<=0||progress.remaining===0)return '';
    const attempted=Number(progress.attempted||0),pct=Math.max(0,Math.min(100,100*attempted/progress.total));
    return '<div class="lb-row-progress"><div role="progressbar" aria-label="Evaluation progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+pct.toFixed(1)+'"><span style="width:'+pct+'%"></span></div><small>'+number(attempted)+' / '+number(progress.total)+' · '+pct.toFixed(1)+'%</small></div>';
  }
  function repairMarkup(repair) {
    if(!repair)return '';
    const total=repair.initial_request_errors+repair.initial_unsupported,remaining=repair.remaining_request_errors+repair.remaining_unsupported;
    if(!Number.isInteger(total)||!Number.isInteger(remaining)||!Number.isInteger(repair.recovered_questions)||total<0||remaining<0||repair.recovered_questions+remaining!==total)return '';
    const state=({running:'Repair running',complete:'Repair complete',blocked:'Repair blocked',paused:'Repair paused',queued:'Repair queued'})[repair.state]||'Repair pending';
    return '<div>'+state+' · Repaired '+number(repair.recovered_questions)+' / '+number(total)+(remaining?' · '+number(remaining)+' remaining':'')+'</div>';
  }
  function approximationMarkup(row) {
    const meta=row.approximation,total=row.progress?.total;if(!meta||!Number.isFinite(total)||total<=0)return '';
    const hundred=row.score_scale?.[1]===100,strict=Number.isFinite(meta.strict_score)?hundred?meta.strict_score.toFixed(2):(100*meta.strict_score).toFixed(2)+'%':'—';
    return '<div class="lb-approximation"><b>Top-k probability estimate</b><p>Full observed distributions: '+number(meta.observed_complete_questions)+' / '+number(total)+'. Estimated distributions: '+number(meta.estimated_questions)+' / '+number(total)+'.</p><p>Missing candidate probabilities are estimated as zero before normalization, not observed zeros. Soft and calibration scores depend on this estimate. Strict score: '+strict+'.</p></div>';
  }
  const nativeMetricArchive = {rows: []}; // Portable results come from the versioned import API.

  const metricText=(en,zh)=>window.JevI18n?.t(en,zh)??en;
  const metricNumber=(value,maximum=1)=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=maximum?value:null;
  const metricPercent=value=>Number.isFinite(value)?(100*value).toFixed(2)+'%':'—';
  const metricDecimal=value=>Number.isFinite(value)?value.toFixed(4):'—';
  function tableMetrics(row,benchmark) {
    if(!Number.isFinite(row.score))return {};
    if(row.model_identity?.provider==='imported'){
      const saved=row.display_metrics||{},counts={};
      ['accuracy_n','correct','brier_n','ece_n','ece_bins','calibration_observed','calibration_estimated','calibration_missing'].forEach(key=>{if(Number.isInteger(saved[key])&&saved[key]>=0)counts[key]=saved[key];});
      return {...counts,accuracy:metricNumber(benchmark.id==='harnessjevbench'?(saved.strict_task_accuracy??saved.accuracy??saved.acc):(saved.accuracy??saved.acc)),brier:metricNumber(saved.brier,2),ece:metricNumber(saved.ece)};
    }
    if(['jevbench','datajevbench'].includes(benchmark.id))return {accuracy:row.metric==='accuracy'?metricNumber(row.score):null,brier:metricNumber(row.calibration?.brier,2),ece:metricNumber(row.calibration?.ece),brier_n:row.calibration?.questions,ece_n:row.calibration?.questions};
    if(benchmark.id==='decisionindex'){
      const saved=row.display_metrics;
      if(!['jev-di-display-metrics-v1','di-0.3-full-classification-micro-calibration-v1'].includes(saved?.revision))return {};
      const counts=['accuracy_n','correct','brier_n','ece_n','calibration_observed','calibration_estimated','calibration_missing'];
      if(counts.some(key=>!Number.isInteger(saved[key])||saved[key]<0)||saved.accuracy_n===0)return {};
      if(metricNumber(saved.accuracy)===null||(saved.brier_n>0?(metricNumber(saved.brier,2)===null||metricNumber(saved.ece)===null):(saved.brier!=null||saved.ece!=null)))return {};
      if(saved.correct>saved.accuracy_n||Math.abs(saved.accuracy-saved.correct/saved.accuracy_n)>1e-10||saved.ece_bins!==10)return {};
      if(saved.brier_n!==saved.ece_n||saved.calibration_observed+saved.calibration_estimated!==saved.brier_n||saved.brier_n+saved.calibration_missing>saved.accuracy_n)return {};
      return {...saved};
    }
    if(benchmark.id!=='harnessjevbench')return {};
    const native=row.display_metrics;
    if(native?.revision==='jev-harness-native-display-metrics-v1'&&native.accuracy_n===271&&native.soft_included===false){
      const validCount=n=>Number.isInteger(n)&&n>=0&&n<=598;
      return {accuracy:metricNumber(native.accuracy),accuracy_n:271,
        brier:validCount(native.brier_n)&&native.brier_n>0?metricNumber(native.brier,2):null,brier_n:native.brier_n,
        ece:validCount(native.ece_n)&&native.ece_n>0&&native.ece_bins===10?metricNumber(native.ece):null,ece_n:native.ece_n};
    }
    // A missing or changed result identity never borrows another model/run's metrics.
    const keys=[...radarBindingKeys,'model_key','updated_at'];
    const binding=Object.fromEntries(keys.map(key=>[key,row[key]??null]));
    const saved=nativeMetricArchive.rows.find(item=>item.benchmark===benchmark.id&&stableJSON(item.binding)===stableJSON(binding));
    return saved?{...saved.metrics,archived_at:nativeMetricArchive.archived_at}:{};
  }
  function metricNotes(benchmark) {
    if(['jevbench','datajevbench'].includes(benchmark.id))return {
      accuracy:metricText('Accuracy over all planned questions; failures remain in the denominator.','完整计划题集的准确率；失败保留在分母。'),
      calibration:metricText('Brier: multiclass squared probability error (0–2). ECE: top-label calibration error, 10 equal-width bins (0–1). Only available probability distributions are included.','Brier：多类别概率平方误差（0–2）。ECE：10 个等宽区间的最高概率标签校准误差（0–1）。仅纳入可用概率分布。')};
    if(benchmark.id==='harnessjevbench')return {
      accuracy:metricText('Strict task accuracy: every question correct in both views, over the registered Hard tasks.','严格任务准确率：已登记 Hard 任务中，两视图所有子题均正确的任务占比。'),
      calibration:metricText('Hard questions only. Brier: multiclass squared probability error (0–2). ECE: 10 equal-width confidence bins (0–1). Soft-distribution scores are separate.','仅 Hard 子题。Brier：多类别概率平方误差（0–2）。ECE：10 个等宽置信度区间（0–1）。Soft 分布得分单列。')};
    return {
      accuracy:metricText('Micro accuracy over classifiable subquestions, excluding retrieval, routing and auxiliary questions. Any accepted answer counts as correct for multi-answer questions. This supplementary ACC is separate from the native index.','可分类子题的微平均准确率，排除 retrieval、routing 和辅助题。多答案题命中任一 accepted 答案即正确；此补充 ACC 与原生指数分别计分。'),
      calibration:metricText('Single-label classification subquestions only; multi-answer questions are excluded. Brier = Σ(p−y)² (0–2). ECE uses 10 equal-width top-confidence bins (0–1). Observed and top-k estimated distributions are counted separately in each result.','仅单标签分类子题，排除多答案题。Brier = Σ(p−y)²（0–2）；ECE 使用 10 个等宽最高置信度区间（0–1）。各行分别列出真实观测和 Top-k 估计分布的数量。')};
  }
  function metricDetail(row,benchmark,metrics) {
    const notes=metricNotes(benchmark);
    const coverage=Number.isFinite(metrics.brier_n)||Number.isFinite(metrics.ece_n)?'<p>'+html(metricText('Calibration coverage','校准覆盖'))+': Brier '+number(metrics.brier_n)+' · ECE '+number(metrics.ece_n)+'</p>':'';
    const classification=benchmark.id==='decisionindex'&&Number.isInteger(metrics.accuracy_n)?'<p>'+html(metricText('Classifiable subquestion ACC','可分类子题 ACC'))+': '+number(metrics.correct)+' / '+number(metrics.accuracy_n)+'</p><p>'+html(metricText('Complete observed candidate distributions','实际完整候选概率分布'))+': '+number(metrics.calibration_observed)+' · '+html(metricText('Top-k estimated distributions','Top-k 估计分布'))+': '+number(metrics.calibration_estimated)+' · '+html(metricText('Missing calibration distributions','校准分布缺失'))+': '+number(metrics.calibration_missing)+'</p><p>'+sourceLink(metrics.source_url,metricText('Supplementary metric source and scoring scope','补充指标来源与计分范围'))+'</p>':'';
    const date=metrics.archived_at?new Date(metrics.archived_at):null;
    const stamp=date?'<p>'+html(metricText('Registered result snapshot','已登记成绩快照'))+' · '+html(date.toLocaleString('en-GB',{hour12:false}))+'</p>':'';
    const importedNotes=['imported','model_access_kit'].includes(row.model_identity?.provider)?(row.notes||[]).map(note=>'<p>'+html(note)+'</p>').join(''):'';
    return '<div class="lb-metric-detail">'+importedNotes+'<p>'+html(notes.accuracy)+'</p>'+(notes.calibration?'<p>'+html(notes.calibration)+'</p>':'')+classification+coverage+stamp+'</div>';
  }
  function metricHelpText(key,benchmark,row) {
    const notes=metricNotes(benchmark),metrics=row?tableMetrics(row,benchmark):{};
    const definitions={
      accuracy:metricText('ACC · Higher is better. ','ACC · 越高越好。')+notes.accuracy,
      brier:metricText('Brier · Lower is better (0–2). Measures how far predicted probabilities are from the correct answer: Σ(p−y)². Zero is perfect; confidently wrong answers receive a larger penalty.','Brier · 越低越好（0–2）。衡量预测概率与正确答案的差距：Σ(p−y)²。0 表示完全正确且确定；高置信度的错误受罚更重。'),
      ece:metricText('ECE · Lower is better (0–1). Checks whether confidence matches actual accuracy—for example, whether predictions with 80% confidence are correct about 80% of the time. Uses 10 equal-width confidence bins.','ECE · 越低越好（0–1）。衡量模型的把握程度是否符合实际正确率，例如有 80% 把握的预测是否约有 80% 正确。按 10 个等宽置信度区间加权计算。'),
      native:benchmark.id==='decisionindex'?metricText('Index · Higher is better (0–100). The registered scorer combines task scores with chance correction and fixed domain weights; dataset scope follows the registered version. Classification ACC is a separate diagnostic. Private tests are not included.','Index · 越高越好（0–100）。登记计分器对任务得分做随机基线校正和固定领域加权；数据范围以登记版本为准。分类 ACC 是独立诊断指标；不含私有测试分。'):metricText('Hard score · Higher is better. Average axes within each call, calls within each task, then weight Hard tasks equally. A task can receive partial credit; Task ACC requires every question in both views to be correct.','Hard 得分 · 越高越好。先在调用内平均各维度，再在任务内平均调用，最后对 Hard 任务等权平均。任务可以获得部分分；任务 ACC 则要求两视图的所有子题都正确。'),
      errors:metricText('Errors · Execution or scoring failures, including timeouts and invalid outputs. These are distinct from valid but incorrect answers and remain in the planned denominator.','错误 · 执行或计分失败，包括超时与无效输出。正常作答但答案错误不计入此列；这些失败仍保留在计划分母中。')
    };
    const parts=[definitions[key]];
    if(key==='brier'||key==='ece'){
      parts.push(benchmark.id==='decisionindex'?metricText('Scope: single-label classification subquestions in the registered 0.3 dataset; excludes retrieval, routing, auxiliary fields and multi-answer questions.','范围：已登记 0.3 数据集中的单标签分类子题；排除检索、路由、辅助字段及多答案题。'):benchmark.id==='harnessjevbench'?metricText('Scope: Hard questions with usable probability distributions. Soft-distribution scores are reported separately.','范围：有可用概率分布的 Hard 子题；Soft 分布得分单列。'):metricText('Scope: questions with usable probability distributions.','范围：有可用概率分布的题目。'));
      const n=metrics[key+'_n'];
      if(Number.isFinite(n))parts.push(metricText('This result: ','本行统计：')+number(n)+metricText(' questions.',' 题。'));
      if(Number.isInteger(metrics.calibration_estimated))parts.push(metricText('Full observed distributions: ','完整观测概率：')+number(metrics.calibration_observed)+metricText('; top-k estimates: ','；Top-k 估计：')+number(metrics.calibration_estimated)+metricText('; missing: ','；缺失：')+number(metrics.calibration_missing)+'。');
      if(metrics.calibration_estimated>0||row?.approximation)parts.push(metricText('Includes top-k estimates: missing candidates are estimated as zero before normalization. This assumption affects calibration.','包含 Top-k 估计：未返回候选在归一化前估为零，此假设会影响校准指标。'));
    }else if(key==='accuracy'&&row){
      const n=metrics.accuracy_n??(benchmark.id==='jevbench'?row.samples:null);
      if(Number.isFinite(n))parts.push(metricText('Denominator for this result: ','本行分母：')+number(n)+(benchmark.id==='harnessjevbench'?metricText(' tasks.',' 个任务。'):metricText(' questions.',' 题。')));
    }else if(key==='errors'&&row){
      const units={requests:metricText('requests','请求'),questions:metricText('questions','题目'),question_views:metricText('question views','子题视图')};
      if(units[row.error_unit])parts.push(metricText('Unit: ','统计单位：')+units[row.error_unit]+'。');
    }
    if(row&&key!=='errors'&&(!Number.isFinite(row.score)||(key!=='native'&&!Number.isFinite(metrics[key]))))parts.push(metricText('No result is available yet; — does not mean zero.','当前尚无可用结果；— 不代表零分。'));
    return parts.filter(Boolean).join('\n\n');
  }
  function helpTarget(node,text) {
    if(!node||!text)return;
    node.dataset.metricHelp=text;node.classList.add('lb-has-metric-help');node.tabIndex=0;
    node.removeAttribute('title');
  }
  function decorateMetricTable(benchmark,rows) {
    const table=byId('leaderboardDetail').querySelector('.lb-metrics-table');if(!table)return;
    const keys=['rank','model',...(['jevbench','datajevbench'].includes(benchmark.id)?[]:['native']),'accuracy','brier','ece'];
    table.querySelectorAll('thead th').forEach((cell,index)=>{if(!['rank','model','record'].includes(keys[index]))helpTarget(cell,metricHelpText(keys[index],benchmark));});
    table.querySelectorAll('tbody tr[data-result-model]').forEach(tr=>{
      const row=rows.find(item=>item.model_key===tr.dataset.resultModel);if(!row)return;
      [...tr.cells].forEach((cell,index)=>{if(!['rank','model','record'].includes(keys[index]))helpTarget(cell,metricHelpText(keys[index],benchmark,row));});
    });
  }
  function decorateArenaMetrics() {
    const table=byId('eloRows')?.closest('table');if(!table)return;
    table.querySelectorAll('tbody>tr').forEach(row=>{const name=row.cells[1]?.textContent||'';const own=/Blink|Qwen.*(?:SFT-1015|RL-1012|RL-1019)/.test(name);row.classList.toggle('lb-own-row',own);row.dataset.ownModel=String(own);row.dataset.modelSearch=name.toLowerCase();});
    let toolbar=byId('gameEloPanel').querySelector('.lb-table-tools');if(!toolbar){table.closest('.lb-table-scroll').insertAdjacentHTML('beforebegin',tableFilterMarkup('gamejevbench'));toolbar=byId('gameEloPanel').querySelector('.lb-table-tools');}
    toolbar.querySelector('.lb-table-search>span').textContent=metricText('Find a model','查找模型');toolbar.querySelector('input').placeholder=metricText('Search model names…','搜索模型名称…');toolbar.querySelector('[data-table-own]').textContent=metricText('Blink only','只看 Blink');
    bindTableFilter('gamejevbench',table,toolbar);
    const definitions={
      2:metricText('Elo · Higher is better. Relative rating from settled matches; it is not a win percentage. Overall rankings require full game coverage. The rule engine participates only in supported board games.','Elo · 越高越好。根据已结算对局计算的相对评级，不是胜率。综合排名要求完整游戏覆盖；规则引擎只参与支持的棋盘游戏。'),
      3:metricText('Coverage: evaluated games / applicable games (or settled matches for a selected game). W / D / L counts valid wins, draws and losses. Failures remain in the underlying result records.','覆盖：已评测游戏数 / 适用游戏数；选择单个游戏时显示有效对局数。胜 / 平 / 负统计有效结算结果，失败保留在原始成绩记录中。'),
      4:metricText('Agreement · Higher is more consistent. Each decision is repeated three times with shuffled choices. Take the most frequent action’s vote share (1/3, 2/3 or 3/3), then average across decisions. This is not accuracy.','三次一致率 · 越高越一致。每次决策打乱选项后重复三次，取最高票动作的票数占比（1/3、2/3 或 3/3），再对决策平均。它不表示答案正确率。'),
      5:metricText('Probability stability · Higher is more stable. 1 − mean pairwise Jensen–Shannon distance across three repeated distributions. Only decisions with complete probabilities for all three repeats are included; 100% means identical distributions.','概率稳定度 · 越高越稳定。1 − 三次概率分布的两两 JS 距离均值。仅纳入三次都有完整概率的决策；100% 表示三次分布相同。'),
      6:metricText('Probability variance · Lower is more stable. Align actions across three repeats, calculate each action’s sample variance (ddof=1), then average. Zero means unchanged probabilities. Only complete distributions are included.','概率方差 · 越低越稳定。对齐三次重复的动作，计算各动作概率的样本方差（ddof=1）再平均。0 表示概率未变化；仅纳入完整概率分布。'),
      7:metricText('Failures · Matches with execution errors or missing valid outcomes. They stay in the schedule and coverage accounting, but no win, loss or Elo outcome is invented.','失败 · 执行出错或缺少有效结果的对局。保留在赛程和覆盖统计中，不人为补成胜负或 Elo 结果。')
    };
    table.querySelectorAll('tr').forEach(tr=>Object.entries(definitions).forEach(([index,text])=>{
      const cell=tr.cells[index];if(!cell)return;
      // Preserve the row-specific coverage supplied by the Arena renderer.
      if(cell.hasAttribute('title'))cell.dataset.metricOriginalHelp=cell.getAttribute('title');
      helpTarget(cell,text+(cell.tagName==='TD'&&cell.dataset.metricOriginalHelp?'\n\n'+cell.dataset.metricOriginalHelp:''));
    }));
  }
  function installMetricHelp() {
    const tip=document.createElement('div');tip.id='lbMetricTooltip';tip.className='lb-metric-tooltip';tip.role='tooltip';tip.hidden=true;tip.setAttribute('data-i18n-raw','');document.body.appendChild(tip);
    let anchor=null,closeTimer;
    const hide=()=>{clearTimeout(closeTimer);if(anchor){const ids=(anchor.getAttribute('aria-describedby')||'').split(' ').filter(id=>id&&id!==tip.id);ids.length?anchor.setAttribute('aria-describedby',ids.join(' ')):anchor.removeAttribute('aria-describedby');}anchor=null;tip.hidden=true;};
    const position=()=>{if(!anchor?.isConnected){hide();return;}const rect=anchor.getBoundingClientRect(),gap=8,pad=10;if(rect.bottom<0||rect.top>innerHeight||rect.right<0||rect.left>innerWidth){hide();return;}const width=tip.offsetWidth,height=tip.offsetHeight;tip.style.left=Math.max(pad,Math.min(rect.left+rect.width/2-width/2,innerWidth-width-pad))+'px';tip.style.top=Math.max(pad,Math.min(rect.top-height-gap>=pad?rect.top-height-gap:rect.bottom+gap,innerHeight-height-pad))+'px';};
    const show=node=>{clearTimeout(closeTimer);if(anchor!==node)hide();anchor=node;tip.textContent=node.dataset.metricHelp;tip.hidden=false;node.setAttribute('aria-describedby',[...(node.getAttribute('aria-describedby')||'').split(' ').filter(Boolean),tip.id].filter((id,index,all)=>all.indexOf(id)===index).join(' '));position();};
    const target=event=>event.target instanceof Element?event.target.closest('#leaderboardView [data-metric-help]'):null;
    document.addEventListener('pointerover',event=>{const node=target(event);if(node)show(node);});
    document.addEventListener('pointerout',event=>{const node=target(event);if(node&&!node.contains(event.relatedTarget)&&event.relatedTarget!==tip)closeTimer=setTimeout(hide,120);});
    document.addEventListener('focusin',event=>{const node=target(event);if(node)show(node);});
    document.addEventListener('focusout',event=>{if(target(event))hide();});
    document.addEventListener('click',event=>{const node=target(event);if(node)show(node);else if(!tip.contains(event.target))hide();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
    document.addEventListener('scroll',event=>{if(anchor&&event.target!==tip)position();},true);
    tip.addEventListener('pointerenter',()=>clearTimeout(closeTimer));tip.addEventListener('pointerleave',hide);
    window.addEventListener('resize',hide);
    window.JevMetricHelp={arena:decorateArenaMetrics,hide};
    decorateArenaMetrics();
  }
  function rowMarkup(row,rank,benchmark) {
    const metrics=tableMetrics(row,benchmark),notes=metricNotes(benchmark);
    const hasNativeScore=!['jevbench','datajevbench'].includes(benchmark.id);
    const status=({complete:'Complete',complete_with_errors:'Complete with errors',incomplete:'Incomplete',paused:'Paused',running:'Running',queued:'Queued',scoring:'Scoring',pending:'Pending',blocked:'Blocked'})[row.status]||row.status||'Archived';
    const displayScore=Number.isFinite(row.score)?(row.score_scale?.[1]===100?row.score.toFixed(2)+' / 100':(100*row.score).toFixed(2)+'%'):'—';
    const probability=['imported','model_access_kit'].includes(row.model_identity?.provider)?row.runtime_protocol||'Imported result':row.approximation?'DashScope top-k estimates':row.provider==='dashscope'?'DashScope top-k probabilities':'Local complete candidate probabilities';
    const sampleTitle=Number.isFinite(metrics.brier_n)?' · n='+number(metrics.brier_n):'';
    const calibrationTitle=notes.calibration+(metrics.calibration_estimated>0?' · '+metricText('Top-k estimated distributions: ','Top-k 估计分布：')+number(metrics.calibration_estimated):row.approximation?' · '+metricText('Includes explicitly marked top-k estimates.','包含明确标记的 top-k 估计。'):'');
    return '<tr class="'+(isOwnModel(row.model_key)?'lb-own-row':'')+'" data-own-model="'+isOwnModel(row.model_key)+'" data-result-model="'+html(row.model_key||'')+'" data-model-search="'+html(modelLabel(row).toLowerCase())+'"><td class="lb-rank">'+(Number.isFinite(row.score)?rank:'—')+'</td><td><strong title="'+html(probability)+'" class="lb-model-name" data-i18n-raw>'+logoMarkup(row)+'<span>'+html(modelLabel(row))+'</span>'+'</strong>'+(isOwnModel(row.model_key)?'<small class="lb-own-badge" data-i18n-raw>Blink</small>':'')+(!Number.isFinite(row.score)?'<small>'+html(status)+'</small>':'')+'</td>'+(hasNativeScore?'<td class="lb-score" data-metric="native">'+html(displayScore)+'</td>':'')+'<td class="'+(hasNativeScore?'lb-metric-value':'lb-score')+'" data-metric="accuracy" title="'+html(notes.accuracy)+'">'+metricPercent(metrics.accuracy)+'</td><td class="lb-metric-value" data-metric="brier" title="'+html(calibrationTitle+sampleTitle)+'">'+metricDecimal(metrics.brier)+'</td><td class="lb-metric-value" data-metric="ece" title="'+html(calibrationTitle+(Number.isFinite(metrics.ece_n)?' · n='+number(metrics.ece_n):''))+'">'+metricDecimal(metrics.ece)+'</td></tr>';
  }
  function tableFilterMarkup(key) {
    const state=tableFilters.get(key)||{query:'',own:false};
    return '<div class="lb-table-tools" data-table-filter="'+html(key)+'"><label class="lb-table-search"><span data-i18n-raw>'+html(metricText('Find a model','查找模型'))+'</span><input type="search" value="'+html(state.query)+'" placeholder="'+html(metricText('Search model names…','搜索模型名称…'))+'"></label><button type="button" data-table-own aria-pressed="'+state.own+'" data-i18n-raw>'+html(metricText('Blink only','只看 Blink'))+'</button><span class="lb-table-count" role="status" data-i18n-raw></span></div>';
  }
  function bindTableFilter(key,table,toolbar) {
    if(!table||!toolbar)return;const state=tableFilters.get(key)||{query:'',own:false};
    const input=toolbar.querySelector('input'),button=toolbar.querySelector('[data-table-own]');
    function apply(){let count=0;const rows=[...table.querySelectorAll('tbody>tr')];rows.forEach(row=>{row.hidden=(!((row.dataset.modelSearch||row.cells[1]?.textContent||'').toLowerCase().includes(state.query.trim().toLowerCase())))||(state.own&&row.dataset.ownModel!=='true');if(!row.hidden)count++;});toolbar.querySelector('.lb-table-count').textContent=count+' / '+rows.length+' '+metricText('models','个模型');button.setAttribute('aria-pressed',String(state.own));tableFilters.set(key,state);}
    input.oninput=()=>{state.query=input.value;apply();};button.onclick=()=>{state.own=!state.own;apply();};apply();
  }
  function groupMarkup(group,benchmark) {
    const rows=[...(group.rows||[])].sort((a,b)=>(Number.isFinite(b.score)?b.score:-Infinity)-(Number.isFinite(a.score)?a.score:-Infinity));
    const native=benchmark.id==='decisionindex'?'<th title="'+html(metricText('Native index, 0–100. Dataset scope and scoring follow the registered version.','原生指数（0–100），数据范围和计分以登记版本为准。'))+'">'+metricText('Index','指数')+'</th>':benchmark.id==='harnessjevbench'?'<th title="'+html(metricText('Native Hard task score: axes, calls and tasks weighted as in the registered scorer.','原生 Hard 任务得分，按登记计分器的轴、调用与任务权重计算。'))+'">'+metricText('Hard score','Hard 得分')+'</th>':'';
    const accuracy=benchmark.id==='harnessjevbench'?metricText('Task ACC ↑','任务 ACC ↑'):'ACC ↑';
    const columns=native?6:5;
    return '<section class="lb-group"><div class="lb-group-heading"><div><span class="lb-section-kicker" data-i18n-raw>'+html(metricText('MODEL RANKING','模型排名'))+'</span><h3>Results <span class="lb-result-total">'+rows.length+'</span></h3></div></div>'+tableFilterMarkup(benchmark.id)+protocolMarkup(group.protocol)+'<div class="lb-table-scroll" tabindex="0" role="region" aria-label="'+html(benchmark.title||'Benchmark')+' results"><table class="lb-table lb-metrics-table"><thead><tr><th>#</th><th>Model</th>'+native+'<th title="'+html(metricNotes(benchmark).accuracy)+'">'+accuracy+'</th><th title="'+html(metricNotes(benchmark).calibration||metricNotes(benchmark).accuracy)+'">Brier ↓</th><th title="'+html(metricNotes(benchmark).calibration||metricNotes(benchmark).accuracy)+'">ECE ↓</th></tr></thead><tbody>'+(rows.length?rows.map((row,index)=>rowMarkup(row,index+1,benchmark)).join(''):'<tr><td colspan="'+columns+'" class="lb-empty-cell">No results for the current version.</td></tr>')+'</tbody></table></div></section>';
  }
  const archivedRadarSnapshot = {rows: []}; // No machine-bound historical fallback.
  const radarMetrics={subset_accuracy:'Accuracy by data subset',family_accuracy:'Accuracy by capability',area_skill:'Chance-corrected domain skill',scenario_mean_task_score:'Hard task score by scenario'};
  const radarNotes={subset_accuracy:'Subset accuracy from the supplied DataJevBench results. Missing probability metrics remain unavailable.',family_accuracy:'Native per-family accuracy with full planned denominators. Sample counts differ across axes.',area_skill:'Native public-suite area skill × 100, with official chance correction. Separate from raw accuracy; private tests are not included.',scenario_mean_task_score:'Native Hard task scores, two views, tasks weighted equally. Soft-only scenarios have no Hard score and remain unavailable.'};
  const axisLabels={adequacy:'Adequacy',adversarial:'Adversarial judgment',ambiguous:'Ambiguity',extraction:'Extraction',fact:'Facts',intent:'Intent',judge_hard:'Hard judgment',long_policy:'Long policy',multi_hop:'Multi-hop reasoning',ordinal:'Ordinal scoring',policy:'Policy',probability:'Probability',routing:'Routing',routing_hard:'Hard routing',temporal_numeric:'Time and numbers',tool_selection:'Tool selection',tradeoff:'Trade-offs',trap:'Trap detection',knowledge:'Knowledge',language:'Language',retrieval:'Retrieval',tools:'Tools',arts:'Arts'};
  const axisLabel=id=>axisLabels[id]||id.split('_').map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(' ');
  const axisChinese={adequacy:'充分性判断',adversarial:'对抗判断',ambiguous:'歧义判断',extraction:'信息提取',fact:'事实判断',intent:'意图识别',judge_hard:'复杂评判',long_policy:'长规则理解',multi_hop:'多步推理',ordinal:'有序评分',policy:'规则判断',probability:'概率判断',routing:'路由选择',routing_hard:'复杂路由',temporal_numeric:'时间与数值',tool_selection:'工具选择',tradeoff:'权衡决策',trap:'陷阱识别',knowledge:'知识与推理',language:'语言理解',retrieval:'检索与分类',tools:'工具与自动化',arts:'艺术与审美'};
  const displayAxis=axis=>({...axis,label:metricText(axisLabels[axis.id]||axis.label_en||axisLabel(axis.id),axisChinese[axis.id]||axis.label_zh||axis.label||axisLabel(axis.id))+(axis.metric==='soft_distribution_overlap'?' · Soft':''),unit:axis.unit==='题'?'questions':axis.unit==='项子基准'?'sub-benchmarks':axis.unit==='局'?'matches':axis.unit||'samples',missing_reason:axis.missing_reason_code==='incomplete_soft_distribution'?metricText('Incomplete or invalid Soft probability results','Soft 概率结果不完整或无效'):axis.missing_reason?metricText('Soft-only; no Hard score','仅 Soft；无 Hard 得分'):null});
  const radarHidden = new Map(), radarAxisSelection = new Map();
  let arenaRadar = null, arenaRadarLoading = false, arenaRadarAt = 0, arenaRadarError = false;
  function radarColor(id) {
    // Keep a model's accent consistent when its rank or benchmark changes.
    const fixed={
      'oneshot-w22m05r02-v5best-avg50':'#d76543',
      'access-qwen38-27b':'#258d80',
      'access-StartLux-Decision-v1.1-27B-Instant':'#b48316',
      'access-StartLux-Decision-v1.1-27B-AutoThink':'#397fc0',
      'access-strands-decider-26B-A4B-gemma4-v1-2610':'#8860b7',
      'access-Clef-27B-original':'#bd5683',
      'access-microsoft--microsoft-decision-1':'#328ba6',
      'access-inception--mercury-decide':'#708d32',
      'access-openai--gpt-6-luna-decisions':'#c18b46',
      'access-typesafe--jev-1.14':'#ad6370',
      'access-qwen3.8-27b-chat-Direct-v1':'#736cac',
      'access-vllm-sr--d3':'#448d55',
      'access-perplexity-ai--pplx-decider-v1.2':'#58739b',
      'oneshot27b-control-reviewed-sft-iter310':'#8860b7',
      'oneshot27b-gameplay-terminal-rl4':'#d76543',
      'oneshot27b-game-rl-native-iter17':'#258d80',
      'rule-engine-v1':'#65758e'
    };
    if(fixed[id])return fixed[id];
    let value=2166136261;for(const char of String(id))value=Math.imul(value^char.charCodeAt(0),16777619);
    const seed=value>>>0;
    return 'hsl('+(seed%3600)/10+' '+(55+seed%13)+'% '+(39+seed%9)+'%)';
  }
  const radarBindingKeys = ['source_id','run_id','model_identity','runtime_protocol','benchmark_version','score','evaluated_at','probability_source'];
  const stableJSON = value => JSON.stringify(value, (key, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(k => [k,item[k]])) : item);
  function radarForRow(benchmark, row) {
    if (!Number.isFinite(row.score)) return null;
    if (row.radar?.metric==='portable_dimensions'){
      const metric=benchmark.id==='datajevbench'?'subset_accuracy':benchmark.id==='jevbench'?'family_accuracy':benchmark.id==='decisionindex'?'area_skill':row.radar.axes?.some(axis=>axis.metric==='soft_distribution_overlap')?'scenario_hard_score_or_soft_overlap':'scenario_mean_task_score';
      return {data:{...row.radar,metric},archived:false};
    }
    if (['jev-benchmark-radars-v1','jev-benchmark-radars-v2','di03-full-v1'].includes(row.radar?.revision)) return {data:row.radar, archived:false};
    const binding=Object.fromEntries(radarBindingKeys.map(key=>[key,row[key]??null]));
    const saved=archivedRadarSnapshot.rows.find(item=>item.benchmark===benchmark.id && stableJSON(item.binding)===stableJSON(binding));
    return saved ? {data:saved.radar,archived:true} : null;
  }
  function radarData(benchmark) {
    if (benchmark.id === 'gamejevbench') {
      const games=arenaRadar?.fixed_config?.games||[], rows=arenaRadar?.overall||[];
      const axes=games.map(game=>{const en=gameLabel(game.id),zh=game.id==='goofspiel'?'竞价夺牌':window.BlinkArenaI18n.entries[en]||en;return {id:game.id,label:metricText(en,zh)};});
      const series=rows.map(row=>({id:row.id,label:modelLabel(row),logo:row.logo,protocol:row.id==='rule-engine-v1'?'Rule engine · board games only':'Current Arena · settled matches',axes:axes.map(axis=>{
        const game=(arenaRadar?.by_game?.[axis.id]||[]).find(item=>item.id===row.id);
        const valid=game && Number.isFinite(game.played) && game.played>0 && [game.wins,game.draws,game.losses].every(Number.isFinite) && game.wins+game.draws+game.losses===game.played;
        return {...axis,score:valid?(game.wins+.5*game.draws)/game.played:null,samples:valid?game.played:null,unit:'matches',missing_reason:'No settled valid matches'};
      })})).map(row=>({...row,unavailable:!row.axes.some(axis=>Number.isFinite(axis.score))}));
      return {axes,series,metric:'Match points by game',unit:'%',note:'Win = 1, draw = 0.5, loss = 0, divided by settled valid matches. Single-player outcomes compare final scores using the same game and seed. This 0–100% rate is separate from Elo. Failed or unsettled matches do not produce invented outcomes.',stamp:arenaRadar?.updated_at,status:arenaRadarError?(arenaRadar?'Refresh failed; showing last settled records':'Arena records unavailable'):arenaRadar?'Live Arena results':'Loading Arena results',unfinished:true};
    }
    const rows=benchmark.display_rows||[],valid=rows.map(row=>({row,radar:radarForRow(benchmark,row)}));
    const first=valid.find(item=>item.radar)?.radar?.data;
    if (!first) {
      // Reuse only the matching benchmark version's axis names, never archived
      // model scores. Pending evaluations keep the same frame with empty values.
      const registered=rows.find(row=>row.model_identity?.provider==='imported'&&row.radar?.axes?.length)?.radar||archivedRadarSnapshot.rows.find(item=>item.benchmark===benchmark.id&&item.binding.benchmark_version===benchmark.version)?.radar;
      const axes=(registered?.axes||[]).map(axis=>{const label=displayAxis(axis);return {id:axis.id,label:label.label,metric:axis.metric};});
      return {axes,series:rows.map(row=>({id:row.model_key||row.source_id,label:modelLabel(row),logo:row.logo,axes:[],unavailable:!Number.isFinite(row.score)})),
        metric:radarMetrics[registered?.metric]||'Capabilities',unit:benchmark.id==='decisionindex'?' pts':'%',
        note:'No capability or scenario scores for the current registered results.',status:'Awaiting dimension scores'};
    }
    const axes=new Map();
    valid.forEach(({radar})=>radar?.data?.axes?.forEach(axis=>{if(!axes.has(axis.id))axes.set(axis.id,{id:axis.id,label:displayAxis(axis).label,label_en:axis.label_en,label_zh:axis.label_zh,metric:axis.metric});}));
    const series=valid.map(({row,radar})=>({id:row.model_key||row.source_id,label:modelLabel(row),logo:row.logo,
      protocol:['imported','model_access_kit'].includes(row.model_identity?.provider)?row.runtime_protocol||'Imported result':row.provider==='dashscope'||row.model_identity?.provider==='dashscope'?(row.approximation?'DashScope · includes top-k estimates':'DashScope · top-k probabilities'):'Local · full candidate probabilities',
      axes:(radar?.data?.axes||[]).map(displayAxis),source_url:row.source_url,unavailable:!Number.isFinite(row.score),archived:radar?.archived,
      softEstimatedViews:row.approximation?.soft_estimated_questions??0}));
    const archival=valid.some(item=>item.radar?.archived);
    const mixed=first.metric==='scenario_hard_score_or_soft_overlap';
    return {axes:[...axes.values()],series,metric:mixed?metricText('Hard task score / Soft distribution agreement','Hard 任务得分 / Soft 分布一致度'):radarMetrics[first.metric]||first.metric,unit:benchmark.id==='decisionindex'?' pts':'%',note:benchmark.id==='decisionindex'?metricText('Native domain skill × 100, with chance correction. Dataset scope follows the registered version; this differs from raw accuracy.','原生领域能力分 × 100，含随机基线校正；数据范围以登记版本为准，与原始准确率不同。'):mixed?metricText('Hard axes keep native task scores. The Soft axis uses 1 − TV, where TV = ½Σ|predicted − target probability|. This is distribution agreement, not accuracy, and is excluded from the overall Hard score. Both views are included; incomplete Soft results stay unavailable.','Hard 轴保留原生任务分；Soft 轴使用 1 − TV，其中 TV = ½Σ|预测概率 − 标注概率|。Soft 衡量分布一致度，不是准确率，不并入 Hard 总分。两个视图均纳入；Soft 结果不完整时留空。'):radarNotes[first.metric]||'',
      stamp:archival?archivedRadarSnapshot.archived_at:null,status:archival?'Registered result snapshot':'Native evaluation scores',
      protocolNote:rows.some(row=>['imported','model_access_kit'].includes(row.model_identity?.provider))?'':'Local full candidate probabilities and DashScope top-k protocols are shown together. Hover over a model for its protocol; scoring details are preserved in the result records.'};
  }
  const shortAxisLabels={argument_validation:['Argument','checks'],browser_action:['Browser','actions'],browser_confirmation:['Browser','confirm'],budget_allocation:['Budget','allocation'],cache_reuse:['Cache','reuse'],cache_validity:['Cache','validity'],clarification_abstention:['Clarify /','abstain'],completion_verification:['Completion','checks'],concurrency_transaction:['Concurrent','work'],context_compression:['Context','compression'],context_retention:['Context','retention'],delegation:['Delegation'],injection_boundary:['Injection','boundary'],memory_write:['Memory','writes'],model_routing:['Model','routing'],plan_progress:['Plan','progress'],privacy_release:['Privacy','release'],reasoning_budget:['Reasoning','budget'],retrieval_evidence:['Retrieval','evidence'],retry_or_escalate:['Retry /','escalate'],retry_recovery:['Retry','recovery'],safety_gate:['Safety','gates'],secret_egress:['Secret','egress'],subagent_dispatch:['Subagent','dispatch'],termination_evidence:['Termination','evidence'],tool_call_review:['Tool call','review'],tool_permission:['Tool','permissions'],tool_selection:['Tool','selection'],trajectory_progress:['Trajectory','progress'],uncertainty_abstention:['Uncertainty','abstention'],version_conflict:['Version','conflicts'],adversarial:['Adversarial','judgment'],ambiguous:['Ambiguity'],judge_hard:['Hard','judgment'],routing_hard:['Hard','routing'],temporal_numeric:['Time and','numbers'],multi_hop:['Multi-hop','reasoning'],dots_and_boxes_3x3:['Dots and','Boxes'],property_tycoon:['Property','Tycoon'],texas_holdem:['Texas','Hold’em']};
  function axisLines(axis) {
    // Translate complete labels first; English line breaks never leak into Chinese.
    if(/[\p{Script=Han}]/u.test(axis.label)){
      const [label,qualifier]=axis.label.split(' · '),lines=[];
      let line='',width=0;
      for(const token of label.match(/\p{Script=Han}|[^\p{Script=Han}]+/gu)||[]){
        const size=/\p{Script=Han}/u.test(token)?1:Array.from(token).length*.5;
        if(line&&width+size>6){lines.push(line.trim());line=token;width=size;}
        else{line+=token;width+=size;}
      }
      if(line)lines.push(line.trim());if(qualifier)lines.push(qualifier);return lines;
    }
    if((!axis.label_en||axis.label_en===axis.id)&&axis.metric==='soft_distribution_overlap'&&shortAxisLabels[axis.id]){const lines=[...shortAxisLabels[axis.id]];lines[lines.length-1]+=' · Soft';return lines;}
    if((!axis.label_en||axis.label_en===axis.id)&&shortAxisLabels[axis.id])return shortAxisLabels[axis.id];
    if(axis.label.length<=13)return [axis.label];
    const words=axis.label.split(' '),lines=[''];
    words.forEach(word=>{const last=lines.length-1;if(lines[last]&&lines[last].length+word.length>13)lines.push(word);else lines[last]+=(lines[last]?' ':'')+word;});
    return lines;
  }
  const radarScore = (score,unit) => Number.isFinite(score) ? (score*100).toFixed(1)+unit : '—';
  const radarPoint = (index,total,radius,centerY=390,centerX=410) => {const angle=2*Math.PI*index/total-Math.PI/2;return [centerX+Math.cos(angle)*radius,centerY+Math.sin(angle)*radius];};
  function softAxisHelp(item,series) {
    if(item?.metric!=='soft_distribution_overlap')return '';
    const formula=metricText('Soft · Distribution agreement = 1 − TV (higher is better). TV is the total variation distance between predicted and labelled distributions. This is not classification accuracy and does not enter the Hard total.','Soft · 分布一致度 = 1 − TV，越高越接近标注分布。TV 为预测分布与标注分布的总变差距离；该值不是分类准确率，不并入 Hard 总分。');
    if(!Number.isFinite(item.valid_samples)||!Number.isFinite(item.planned_samples))return formula;
    return formula+'\n\n'+metricText('Coverage: ','覆盖：')+number(item.valid_samples)+' / '+number(item.planned_samples)+metricText(' views from ',' 个视图，来自 ')+number(item.tasks)+metricText(' tasks.',' 个任务。')+(Number.isFinite(item.raw_value)?' TV = '+item.raw_value.toFixed(4)+'。':'')+(series.softEstimatedViews>0?'\n\n'+metricText('Includes top-k estimates in ','包含 Top-k 概率估计：')+number(series.softEstimatedViews)+' / '+number(item.planned_samples)+metricText(' views; missing candidates are estimated zero before normalization.',' 个视图；未返回候选在归一化前估为零。'):'');
  }
  function radarSVG(data, visible) {
    const n=data.axes.length,dense=n>24,radius=280,centerY=390,centerX=410;
    const point=(index,r)=>radarPoint(index,n,r,centerY,centerX);
    // Keep one plot geometry; distribute dense labels without shrinking the plot.
    const callouts=new Map();
    if(dense){
      const anchors=data.axes.map((axis,index)=>({index,end:point(index,radius)}));
      for(const top of [true,false]){
        const group=anchors.filter(item=>Math.abs(item.end[0]-centerX)<radius*.4&&(item.end[1]<centerY)===top).sort((a,b)=>a.end[0]-b.end[0]);
        group.forEach((item,order)=>callouts.set(item.index,{x:130+order*560/Math.max(1,group.length-1),y:top?42:738}));
      }
      for(const right of [true,false]){
        const side=anchors.filter(item=>!callouts.has(item.index)&&(item.end[0]>centerX)===right)
          .map(item=>({...item,label:point(item.index,radius+24)})).sort((a,b)=>a.label[1]-b.label[1]);
        const gap=44;
        side.forEach((item,index)=>item.y=Math.max(96,item.label[1],index?side[index-1].y+gap:96));
        for(let index=side.length-1;index>=0;index--)side[index].y=Math.min(684,side[index].y,index<side.length-1?side[index+1].y-gap:684);
        side.forEach(item=>callouts.set(item.index,{x:item.label[0],y:item.y,side:right?1:-1}));
      }
    }
    let content='<title>'+html(data.metric)+'</title><desc>'+html(metricText('Scores from 0 to 100. Missing values remain gaps.','各轴为 0–100，缺失值保留为空。'))+'</desc>';
    for (const level of [.25,.5,.75,1]) {
      const points=data.axes.map((axis,index)=>point(index,radius*level).join(',')).join(' ');
      content+='<polygon class="lb-radar-grid" points="'+points+'"/><text class="lb-radar-tick" x="'+(centerX+6)+'" y="'+(centerY-radius*level-5)+'">'+(level*100)+'</text>';
    }
    data.axes.forEach((axis,index)=>{
      const end=point(index,radius),callout=callouts.get(index),label=callout?[callout.x,callout.y]:point(index,radius+(dense?24:76));
      const lines=axisLines(axis),spacing=dense?22:24;
      content+='<line class="lb-radar-spoke" x1="'+centerX+'" y1="'+centerY+'" x2="'+end[0]+'" y2="'+end[1]+'"/>';
      if(callout){const elbow=point(index,radius+20);content+='<path class="lb-radar-callout" d="M '+end.join(' ')+' L '+elbow.join(' ')+' L '+(label[0]-(callout.side||0)*6)+' '+(callout.side?label[1]:label[1]+(label[1]<centerY?26:-32))+'"/>';}
      content+='<text class="lb-radar-axis" tabindex="0" role="button" data-radar-axis="'+index+'" aria-label="'+html(metricText('Inspect ','查看 ')+axis.label)+'" x="'+label[0]+'" y="'+label[1]+'" text-anchor="'+(callout?.side?(callout.side>0?'start':'end'):'middle')+'">'+lines.map((line,lineIndex)=>'<tspan x="'+label[0]+'" y="'+(label[1]+(lineIndex-(lines.length-1)/2)*spacing)+'">'+html(line)+'</tspan>').join('')+'<title>'+html(axis.label+' · '+axis.id)+'</title></text>';
    });
    visible.forEach(series=>{
      content+='<g class="lb-radar-series" data-series-id="'+html(series.id)+'">';
      const points=data.axes.map((axis,index)=>{
        const item=series.axes.find(item=>item.id===axis.id),value=item?.score;
        return Number.isFinite(value)&&value>=0&&value<=1?{point:point(index,radius*value),value,index,item}:null;
      });
      if(points.every(Boolean)) content+='<polygon class="lb-radar-shape" points="'+points.map(point=>point.point.join(',')).join(' ')+'" fill="'+series.color+'" stroke="'+series.color+'"/>';
      else points.forEach((point,index)=>{
        const next=points[(index+1)%n];
        if(point&&next) content+='<line class="lb-radar-partial" x1="'+point.point[0]+'" y1="'+point.point[1]+'" x2="'+next.point[0]+'" y2="'+next.point[1]+'" stroke="'+series.color+'"/>';
      });
      points.filter(Boolean).forEach(point=>{const help=softAxisHelp(point.item,series)||metricText('Click to compare this dimension.','点击比较这个维度。');content+='<circle class="lb-radar-dot'+(point.item?.metric==='soft_distribution_overlap'?' lb-radar-soft-dot':'')+'" tabindex="0" data-radar-axis="'+point.index+'" data-radar-model-id="'+html(series.id)+'"'+(help?' data-metric-help="'+html(series.label+' · '+data.axes[point.index].label+' · '+radarScore(point.value,data.unit)+'\n\n'+help)+'"':'')+' cx="'+point.point[0]+'" cy="'+point.point[1]+'" r="'+(point.item?.metric==='soft_distribution_overlap'?'5':'3.5')+'" fill="'+series.color+'" aria-label="'+html(series.label+', '+data.axes[point.index].label+', '+radarScore(point.value,data.unit))+'">'+(help?'':'<title>'+html(series.label+' · '+data.axes[point.index].label+': '+radarScore(point.value,data.unit))+'</title>')+'</circle>';});
      content+='</g>';
    });
    content+='<text class="lb-radar-tick" x="'+(centerX+6)+'" y="'+(centerY+15)+'">0</text>';
    return '<svg class="lb-radar-svg'+(visible.length>6?' lb-radar-many':'')+'" viewBox="0 0 820 780" role="img" aria-label="'+html(data.metric)+'">'+content+'</svg>';
  }
  function comparisonBars(benchmark,data,visible,axis) {
    const arena=benchmark.id==='gamejevbench',overall=!axis;
    const metric=axis?axis.label:arena?'Elo':benchmark.id==='decisionindex'?metricText('Index','指数'):benchmark.id==='harnessjevbench'?metricText('Hard score','Hard 得分'):'ACC';
    const rows=visible.map(series=>{
      const source=arena?(arenaRadar?.overall||[]).find(row=>row.id===series.id):(benchmark.display_rows||[]).find(row=>(row.model_key||row.source_id)===series.id);
      let score=axis?series.axes.find(item=>item.id===axis.id)?.score:arena?(source?.overall_eligible===true?source.rating:null):source?.score;
      const scale=source?.score_scale||benchmark.score_scale;
      if(Number.isFinite(score)&&!(overall&&arena))score*=overall&&scale?.[1]===100?1:100;
      return {...series,score:Number.isFinite(score)?score:null};
    }).sort((a,b)=>(b.score??-Infinity)-(a.score??-Infinity));
    const maximum=overall&&arena?Math.max(1600,Math.ceil(Math.max(0,...rows.map(row=>row.score||0))/200)*200):100;
    const unit=overall&&arena?'':overall&&benchmark.id==='decisionindex'?'':axis&&data.unit===' pts'?'':'%';
    const help=axis?.metric==='soft_distribution_overlap'?softAxisHelp({metric:axis.metric},visible[0]||{}):overall&&arena?metricText('Registered game-weighted Elo. Incomplete coverage has no overall rating.','登记的游戏等权 Elo；覆盖不完整时不显示总分。'):overall?metricText('The same registered score as the table below.','与下方排行榜使用同一登记得分。'):data.note;
    const bars=rows.map((row,index)=>{
      const score=row.score===null?'—':row.score.toFixed(overall&&arena?0:1)+unit;
      const identity=logoMarkup(row)+'<span class="lb-bar-name">'+html(chartLabel(row))+'</span>';
      const width=row.score===null?0:Math.max(0,Math.min(100,100*row.score/maximum));
      const fill=row.score===null?'':'<span class="lb-bar-fill" style="width:'+width+'%;--bar-color:'+row.color+'"><span class="lb-bar-identity">'+identity+'</span></span>';
      // Missing and zero scores keep a readable label without inventing a positive bar.
      const empty=width===0?'<div class="lb-bar-unscored">'+identity+'</div>':'';
      return '<div class="lb-bar-row'+(row.score===null?' missing':'')+'" role="listitem" data-bar-model="'+html(row.id)+'" data-bar-score="'+(row.score===null?'':row.score)+'" data-i18n-raw><div class="lb-bar-track" role="button" aria-pressed="false" tabindex="0" data-metric-help="'+html(row.label+' · '+metric+' · '+score)+'" aria-label="'+html(row.label+' · '+score)+'">'+fill+empty+'</div><b class="lb-bar-value">'+score+'</b></div>';
    }).join('');
    return '<div class="lb-bar-metric" data-i18n-raw><span tabindex="0" data-metric-help="'+html(help)+'">'+html(metric)+'</span><span>0 — '+maximum+unit+'</span></div><div class="lb-bars" role="list" aria-label="'+html(metric)+'">'+(rows.length?bars:'<p class="lb-bar-empty" data-i18n-raw>'+html(metricText('Select a model','选择模型'))+'</p>')+'</div>';
  }
  function renderRadar(benchmark) {
    const host=byId('leaderboardRadar');if(!host)return;
    const pickerOpen=host.querySelector('.lb-model-picker')?.open||false;
    const previousChart=host.querySelector('.lb-radar-chart'),previousScroll=previousChart?.scrollLeft;
    const data=radarData(benchmark),series=data.series.map(row=>({...row,color:radarColor(row.id)}));
    const hidden=radarHidden.get(benchmark.id)||new Set(),visible=series.filter(row=>!hidden.has(row.id));
    host.dataset.radarBenchmark=benchmark.id;
    const dense=data.axes.length>24,query=radarSearch.get(benchmark.id)||'';
    const heading='<div class="lb-radar-heading"><h3 data-i18n-raw>'+html(definitions.find(row=>row[0]===benchmark.id)?.[1]||benchmark.title)+'</h3></div>';
    const legend=[...series].sort((a,b)=>Number(isOwnModel(b.id))-Number(isOwnModel(a.id))).map(row=>'<div class="lb-radar-legend-row'+(!hidden.has(row.id)?' selected':'')+'" data-legend-search="'+html((row.label+' '+row.id).toLowerCase())+'"><label title="'+html(row.unavailable?metricText('No registered overall score yet','暂无登记总分'):row.protocol)+'" class="lb-radar-legend-item'+(row.unavailable?' unavailable':'')+'"><input type="checkbox" data-radar-model="'+html(row.id)+'" '+(!hidden.has(row.id)?'checked ':'')+'><span class="lb-radar-swatch" style="background:'+row.color+'"></span><span><strong class="lb-model-name" data-i18n-raw>'+logoMarkup(row)+'<span>'+html(row.label)+'</span>'+'</strong>'+(row.unavailable?'<small data-i18n-raw>'+html(metricText('No overall score','暂无总分'))+'</small>':'')+'</span></label>'+('<button type="button" class="lb-model-only" data-radar-only="'+html(row.id)+'" title="'+html(metricText('Compare this model only','仅显示此模型'))+'" data-i18n-raw>'+html(metricText('Only','仅此'))+'</button>')+'</div>').join('');
    const axisList='<select data-i18n-raw id="lbRadarDimension" aria-label="'+html(metricText('Score or dimension','选择总分或维度'))+'"><option value="-1" data-i18n-raw>'+html(metricText('Overall','总分'))+'</option>'+data.axes.map((axis,index)=>'<option value="'+index+'">'+html(axis.label)+'</option>').join('')+'</select>';

    const table='<details class="lb-radar-values"><summary data-i18n-raw>'+html(metricText('All dimensions & sample counts','全部维度与样本数'))+' · '+data.axes.length+'</summary><p class="lb-radar-note">'+html(data.note)+' Missing values are shown as gaps and —.</p>'+(data.protocolNote?'<p class="lb-radar-note">'+html(data.protocolNote)+'</p>':'')+'<div class="lb-radar-table-scroll" tabindex="0"><table><thead><tr><th>Dimension / scenario</th>'+visible.map(row=>'<th data-i18n-raw>'+html(row.label)+'</th>').join('')+'</tr></thead><tbody>'+data.axes.map(axis=>'<tr><th data-i18n-raw>'+html(axis.label)+'<small>'+html(axis.id)+'</small></th>'+visible.map(row=>{const item=row.axes.find(value=>value.id===axis.id);return '<td data-i18n-raw>'+radarScore(item?.score,data.unit)+'<small>'+html(Number.isFinite(item?.score)&&Number.isFinite(item?.samples)?number(item.samples)+' '+metricText(item.unit||'samples',({'questions':'题','tasks':'任务','views':'视图','matches':'场','samples':'样本','sub-benchmarks':'项子基准'})[item.unit]||'样本'):item?.missing_reason||metricText('No score for this dimension','暂无该维度成绩'))+'</small></td>';}).join('')+'</tr>').join('')+'</tbody></table></div></details>';
    host.innerHTML=heading+'<details class="lb-model-picker"><summary data-i18n-raw>'+html(metricText('Compare models','选择模型'))+'</summary><div class="lb-model-picker-body"><input id="lbRadarSearch" type="search" value="'+html(query)+'" placeholder="'+html(metricText('Search models…','搜索模型…'))+'" aria-label="'+html(metricText('Search models','搜索模型'))+'"><div class="lb-selection-actions"><button type="button" data-radar-selection="default" data-i18n-raw>'+html(metricText('Default','默认'))+'</button><button type="button" data-radar-selection="all" data-i18n-raw>'+html(metricText('Select all','全选'))+'</button><button type="button" data-radar-selection="none" data-i18n-raw>'+html(metricText('Clear','清空'))+'</button></div><div class="lb-radar-legend">'+legend+'</div><p class="lb-legend-no-match" hidden data-i18n-raw>'+html(metricText('No matching models','没有匹配的模型'))+'</p></div></details><div class="lb-comparison-grid"><section class="lb-chart-card lb-radar-main"><div class="lb-chart-title"><h4 data-i18n-raw>'+html(metricText('Capability profile','能力分布'))+'</h4><span class="lb-chart-scale">0–100</span>'+('<span class="lb-chart-pan-hint" data-i18n-raw>'+html(metricText('← Swipe to explore →','← 左右滑动查看 →'))+'</span>')+'</div><div class="lb-radar-chart'+(dense?' lb-radar-dense':'')+'" data-i18n-raw>'+(data.axes.length>=3?radarSVG(data,visible):'<div class="lb-empty-radar" aria-hidden="true"><i></i><i></i><i></i><i></i></div>')+'<p class="lb-radar-empty" '+(visible.some(row=>row.axes.some(axis=>Number.isFinite(axis.score)))&&data.axes.length>=3?'hidden':'')+'>'+html(metricText(visible.length?'No dimension scores yet':'Select a model',visible.length?'暂无维度成绩':'选择模型'))+'</p></div></section><section class="lb-chart-card lb-bar-card"><div class="lb-chart-title"><h4 data-i18n-raw>'+html(metricText('Score comparison','得分对比'))+'</h4>'+axisList+'</div><div id="lbBarChart" aria-live="polite"></div></section></div>'+table+'<div class="lb-radar-inspect" hidden></div>';
    {
      const chart=host.querySelector('.lb-radar-chart');
      chart.tabIndex=0;chart.setAttribute('role','region');
      chart.setAttribute('aria-label',metricText('Capability profile · Scroll horizontally to view all labels','能力分布 · 左右滚动查看完整标签'));
      requestAnimationFrame(()=>{if(chart.isConnected)chart.scrollLeft=previousScroll??Math.max(0,(chart.scrollWidth-chart.clientWidth)/2);});
    }
    function inspect(index) {
      const axis=data.axes[index];
      radarAxisSelection.set(benchmark.id,axis?.id||'overall');host.querySelector('#lbRadarDimension').value=String(axis?index:-1);
      host.querySelector('#lbBarChart').innerHTML=comparisonBars(benchmark,data,visible,axis);
      highlight(pinnedModel);
      host.querySelectorAll('[data-radar-axis]').forEach(node=>node.classList.toggle('is-active',Number(node.dataset.radarAxis)===index));
      if(!axis)return;
      host.querySelector('.lb-radar-inspect').innerHTML=(axis.metric==='soft_distribution_overlap'?'<small data-i18n-raw>'+html(metricText('Soft · 1 − TV · Distribution agreement','Soft · 1 − TV · 分布一致度'))+'</small>':'')+visible.map(row=>{const item=row.axes.find(value=>value.id===axis.id),help=softAxisHelp(item,row);return '<p><span class="lb-radar-swatch" style="background:'+row.color+'"></span><span data-i18n-raw>'+html(row.label)+'<small>'+html(Number.isFinite(item?.samples)?number(item.samples)+' '+metricText(item.unit||'samples',({'questions':'题','tasks':'任务','views':'视图','matches':'场','samples':'样本','sub-benchmarks':'项子基准'})[item.unit]||item.unit||'样本'):item?.missing_reason?metricText(item.missing_reason,window.BlinkArenaI18n.entries[item.missing_reason]||'暂无该维度成绩'):metricText('No score for this dimension','暂无该维度成绩'))+'</small></span><b'+(help?' tabindex="0" data-metric-help="'+html(help)+'"':'')+'>'+radarScore(item?.score,data.unit)+'</b></p>';}).join('');
    }
    function redraw(){const pickerOpen=host.querySelector('.lb-model-picker').open,scroll=host.querySelector('.lb-radar-legend').scrollTop,focused=document.activeElement,attribute=['data-radar-model','data-radar-only','data-radar-selection'].find(key=>focused?.hasAttribute(key)),value=attribute?focused.getAttribute(attribute):null;renderRadar(benchmark);host.querySelector('.lb-model-picker').open=pickerOpen;host.querySelector('.lb-radar-legend').scrollTop=scroll;if(attribute)host.querySelector('['+attribute+'="'+CSS.escape(value)+'"]')?.focus({preventScroll:true});}
    const search=host.querySelector('#lbRadarSearch');
    function filterLegend(){const value=search.value.trim().toLowerCase();let count=0;host.querySelectorAll('[data-legend-search]').forEach(row=>{row.hidden=!row.dataset.legendSearch.includes(value);if(!row.hidden)count++;});host.querySelector('.lb-legend-no-match').hidden=count>0;radarSearch.set(benchmark.id,search.value);}
    search.oninput=filterLegend;filterLegend();
    host.querySelectorAll('[data-radar-selection]').forEach(button=>button.onclick=()=>{const mode=button.dataset.radarSelection;radarHidden.set(benchmark.id,new Set(series.filter(()=>mode==='none').map(row=>row.id)));redraw();});
    host.querySelectorAll('[data-radar-only]').forEach(button=>button.onclick=()=>{radarHidden.set(benchmark.id,new Set(series.filter(row=>row.id!==button.dataset.radarOnly).map(row=>row.id)));redraw();});
    host.querySelector('#lbRadarDimension').onchange=event=>inspect(Number(event.target.value));
    host.querySelectorAll('[data-radar-model]').forEach(input=>input.onchange=()=>{input.checked?hidden.delete(input.dataset.radarModel):hidden.add(input.dataset.radarModel);radarHidden.set(benchmark.id,hidden);redraw();});
    host.querySelectorAll('[data-radar-axis]').forEach(item=>{item.onclick=()=>inspect(Number(item.dataset.radarAxis));item.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect(Number(item.dataset.radarAxis));}};});
    let pinnedModel=null;
    function highlight(id){
      host.classList.toggle('has-highlight',Boolean(id));
      host.querySelectorAll('[data-series-id],[data-bar-model]').forEach(node=>{node.classList.toggle('is-highlighted',(node.dataset.seriesId||node.dataset.barModel)===id);node.querySelector('.lb-bar-track')?.setAttribute('aria-pressed',String(node.dataset.barModel===pinnedModel));});
    }
    const barHost=host.querySelector('#lbBarChart');
    const barId=event=>event.target.closest('[data-bar-model]')?.dataset.barModel;
    barHost.onpointerover=event=>highlight(barId(event)||pinnedModel);
    barHost.onpointerleave=()=>highlight(pinnedModel);
    barHost.onfocusin=event=>highlight(barId(event)||pinnedModel);
    barHost.onfocusout=()=>highlight(pinnedModel);
    barHost.onclick=event=>{const id=barId(event);if(id){pinnedModel=pinnedModel===id?null:id;highlight(pinnedModel);}};
    barHost.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();event.target.click();}if(event.key==='Escape'){pinnedModel=null;highlight(null);}};
    host.querySelector('.lb-model-picker').open=pickerOpen;
    inspect(data.axes.findIndex(axis=>axis.id===radarAxisSelection.get(benchmark.id)));localizeLeaderboard();
  }
  async function refreshArenaRadar() {
    if(arenaRadarLoading||Date.now()-arenaRadarAt<10000)return;
    arenaRadarLoading=true;
    try {arenaRadar=await api('elo');arenaRadarAt=Date.now();arenaRadarError=false;}
    catch(error) {arenaRadarError=true;}
    finally {arenaRadarLoading=false;}
    if(selected==='gamejevbench'){const benchmark=payload?.benchmarks?.find(item=>item.id===selected);if(benchmark)renderRadar(benchmark);}
  }

  function render(cacheOnly=false) {
    window.JevMetricHelp?.hide();
    const openDetails=[...byId('leaderboardDetail').querySelectorAll('details')].map(node=>node.open);
    tabs();renderStatus();
    const benchmark=payload?.benchmarks?.find(item=>item.id===selected);
    byId('leaderboardDetail').setAttribute('aria-labelledby','lb-tab-'+selected);
    if(!cacheOnly)window.JevElo?.setVisible(selected==='gamejevbench');
    if(!benchmark){byId('leaderboardDetail').innerHTML='<div class="lb-empty">'+(loading?'Loading results…':'No registered results yet.')+'</div>';localizeLeaderboard();return;}
    const radarMarkup='<section id="leaderboardRadar" class="lb-radar-panel" aria-label="Capability radar"></section>';
    if(selected==='gamejevbench'){
      byId('leaderboardDetail').innerHTML=radarMarkup;renderRadar(benchmark);if(!cacheOnly)refreshArenaRadar();
      if(cacheOnly)byId('leaderboardDetail').querySelectorAll('details').forEach((node,index)=>{node.open=!!openDetails[index];});return;
    }
    const chosen=(benchmark.groups||[]).find(group=>group.id===benchmark.display_group_id);
    const group={...(chosen||{id:'pending',current:true}),rows:benchmark.display_rows||[]};
    byId('leaderboardDetail').innerHTML=radarMarkup+datasetMarkup(benchmark)+groupMarkup(group,benchmark);
    renderRadar(benchmark);
    decorateMetricTable(benchmark,group.rows);
    bindTableFilter(benchmark.id,byId('leaderboardDetail').querySelector('.lb-metrics-table'),byId('leaderboardDetail').querySelector('.lb-table-tools'));
    if(cacheOnly)byId('leaderboardDetail').querySelectorAll('details').forEach((node,index)=>{node.open=!!openDetails[index];});
  }
  function renderStatus() {
    const benchmark=payload?.benchmarks?.find(item=>item.id===selected);
    const date=benchmark?.updated_at?new Date(benchmark.updated_at):null;
    byId('leaderboardStatus').dataset.updatedAt=benchmark?.updated_at||'';
    byId('leaderboardStatus').title=benchmark?.source_file||'';
    byId('leaderboardStatus').setAttribute('data-i18n-raw','');
    byId('leaderboardStatus').textContent=loadError?metricText('Could not load results: ','成绩加载失败：')+loadError:metricText('Updated ','更新于 ')+(date&&Number.isFinite(date.getTime())?date.toLocaleString(window.JevI18n?.lang==='zh'?'zh-CN':'en-GB',{hour12:false}):'—');
    byId('leaderboardRefresh').textContent='Refresh';localizeLeaderboard();
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    byId('leaderboardRefresh').disabled = true;
    if (!payload) render();
    try {
      const next = await api('leaderboard');
      const changed = JSON.stringify(payload?.benchmarks) !== JSON.stringify(next.benchmarks);
      payload = next;
      loadError='';renderStatus();
      if (changed) render();
    } catch (error) {
      loadError=error.message||'Request failed';renderStatus();
    } finally {
      loading = false;
      byId('leaderboardRefresh').disabled = false;
      if (!payload) render();
    }
    if (selected === 'gamejevbench') {window.JevElo?.refresh();refreshArenaRadar();}
  }
  byId('leaderboardRefresh').textContent='Refresh';
  byId('leaderboardRefresh').onclick = refresh;
  window.JevLeaderboard = {refresh, activate:refresh};
  window.JevI18n?.onChange(()=>{render(true);renderStatus();});
  installMetricHelp();
  render();
  setInterval(() => {
    if (!byId('leaderboardView').classList.contains('hidden')) {
      refresh();
    }
  }, 15000);
})();
