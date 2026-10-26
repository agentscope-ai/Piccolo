(function () {
  'use strict';
  const byId = id => document.getElementById(id);
  // Translate only rendered UI nodes. Source identities, raw protocols and English radar axes stay intact.
  const tr=(en,zh,params)=>window.JevI18n?.t(en,zh,params)??en;
  function createPresentationTranslator(entries,skip='') {
    const originals=new WeakMap();
    const phrases=Object.keys(entries).sort((a,b)=>b.length-a.length);
    const pattern=new RegExp('(?<![A-Za-z0-9_])(?:'+phrases.map(text=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')(?![A-Za-z0-9_])','g');
    function translate(text) {
      const zh=text.replace(pattern,match=>entries[match])
        .replace(/Overall Elo requires all ([\d,]+) 游戏 to be covered\./g,'综合 Elo 需覆盖全部 $1 个游戏。')
        .replace(/View ([\d,]+) dimensions and sample counts/g,'查看 $1 个维度与样本量')
        .replace(/Inspect (?=[A-Za-z])/g,'查看 ');
      return tr(text,zh);
    }
    function update(node,key,read,write) {
      const stored=originals.get(node)||{},current=read(),old=stored[key];
      const source=old&&current===old.output?old.source:current,output=translate(source);
      if(current!==output)write(output);
      stored[key]={source,output};originals.set(node,stored);
    }
    return function localize(root) {
      if(!root)return;
      const excluded='code,pre,[data-i18n-raw],[data-i18n-en]'+(skip?','+skip:'');
      const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()) {
        const node=walker.currentNode;
        if(!node.parentElement?.closest(excluded))update(node,'text',()=>node.nodeValue,value=>{node.nodeValue=value;});
      }
      [root,...root.querySelectorAll('[title],[aria-label]')].forEach(node=>{
        if(node.matches(excluded)||node.closest('code,pre'))return;
        for(const name of ['title','aria-label'])if(node.hasAttribute(name)&&!node.hasAttribute('data-i18n-'+name+'-en'))update(node,name,()=>node.getAttribute(name),value=>node.setAttribute(name,value));
      });
    };
  }
  const uiTranslations={"All games":"全部游戏","Replay":"回放","Load more":"更多对局","No matches for this game.":"该游戏暂无对局。","Waiting":"等待中","Evaluation running":"评测进行中","Pausing":"暂停中","Paused":"已暂停","Interrupted":"已中断","Complete with failures":"已完成（含失败）","Complete with errors":"已完成（含错误）","Complete":"已完成","Evaluation error":"评测错误","Registered":"已登记","Queued":"排队中","Pending":"待评测","Running":"进行中","Error":"错误","Blocked":"已阻塞","Scoring":"计分中","Archived":"归档","Incomplete":"未完成","Model enrolled":"模型已加入","Submitting…":"提交中…","Evaluate current model":"评测当前模型","Loading model…":"读取模型中…","Checking eligibility…":"检查准入中…","Enrolled.":"已加入。","This connection is not supported.":"当前连接暂不支持。","Connect the model first.":"请先连接模型。","This model cannot join yet.":"当前模型暂不能加入。","Previous results are reused.":"沿用已有结果。","new matches.":"场新增对局。","Pause":"暂停","Resume":"继续","Refresh":"刷新","Final game score":"游戏最终成绩","Final score":"最终成绩","Completion first":"优先比较是否通关","lower is better":"越低越好","higher is better":"越高越好","Gates reached; final horizontal position breaks ties":"已到达关卡数；平分时比较最终横向位置","Platforms reached":"已到达平台数","Lines cleared":"消除行数","Food collected":"吃到的食物数","Merge points":"合并得分","Boxes on targets":"目标上的箱子数","Level progress (%); native score breaks ties":"关卡进度（%）；平分时比较原生得分","Distance (m); remaining durability breaks ties":"行驶距离（米）；平分时比较剩余耐久度","Native payoff against the dealer":"对庄家的原生收益","board games":"棋盘游戏","direct matches":"直接对战","3 repeats per decision":"每次决策重复 3 次","Loading schedule…":"读取赛程中…","Same seed, reversed roles":"相同种子，交换执方","Direct match":"直接对战","Final-score comparison":"最终成绩比较","Waiting for schedule":"等待赛程","evaluation progress":"评测进度","Complete probabilities for all three repeats":"三次重复均有完整概率","Sample variance across aligned candidate probabilities; lower is better":"对齐候选概率的样本方差；越低越好","Per-game only":"仅分游戏计分","Incomplete coverage":"覆盖未完成","Not evaluated":"未评测","scored matches":"有效对局","W / D / L":"胜 / 平 / 负","Coverage / W–D–L":"覆盖 / 胜–平–负","Elo rankings":"Elo 排名","Overall · game-weighted":"综合 · 游戏等权","Overall ranking":"综合排名","No settled Elo results for this game.":"该游戏尚无已结算的 Elo 成绩。","Elo is a rating, not a win rate. Pending or incomplete coverage is excluded.":"Elo 是评级分，不是胜率。未评测或覆盖未完成的模型不列入柱图。","Axis starts at 0":"坐标轴从 0 开始","dashed line: initial Elo":"虚线：初始 Elo","Participant":"参赛者","Agreement":"三次一致率","Probability stability":"概率稳定度","Variance ↓":"方差 ↓","Failures":"失败数","No settled results yet.":"暂无已结算成绩。","Native score":"原生得分","Budget exhausted":"预算耗尽","Win":"胜","Loss":"负","Draw":"平局","Failure":"失败","Compare in order":"依次比较","Record":"记录","reused":"复用","new record":"新记录","Recent matches":"最近对局","recorded":"已记录","Error · unscored":"错误 · 未计分","Awaiting result":"等待结果","Same-seed final score":"同种子最终成绩","Roles reversed":"交换执方","Final scores and match records appear after settlement.":"对局结算后显示最终成绩与记录。","Repair running":"修复中","Repair complete":"修复完成","Repair blocked":"修复受阻","Repair paused":"修复已暂停","Repair pending":"等待修复","Repair queued":"修复排队中","Repair progress":"修复进度","Repaired":"已修复","Repairing failed matches":"正在修复失败对局","Updated":"更新于","Request failed":"请求失败","Could not load Arena":"天梯加载失败","Enrolling model…":"正在加入模型…","Requesting pause…":"正在请求暂停…","Resuming…":"正在继续…","Model enrolled. Previous results are reused.":"模型已加入，沿用已有结果。","Pause requested; current matches will finish.":"已请求暂停，当前对局结束后生效。","Schedule resumed.":"赛程已继续。","Action failed":"操作失败","Rule engine":"规则引擎","Local base":"本地基座","Gameplay RL":"游戏 RL","Reviewed SFT / iter":"审核数据 SFT / 迭代","Model":"模型","Othello 6×6":"黑白棋 6×6","Othello 8×8":"黑白棋 8×8","Gomoku":"五子棋","Hex":"六角棋","Dots and Boxes":"点格棋","Terraria":"泰拉瑞亚","Jump Jump":"跳一跳","Tetris":"俄罗斯方块","Snake":"贪吃蛇","Sokoban":"推箱子","Mario":"马里奥","Racing":"赛车","Dou Dizhu":"斗地主","Texas Hold’em":"德州扑克","Property Tycoon":"地产大亨","Liar’s Dice":"吹牛骰子","Blackjack":"二十一点","Golden Flower":"炸金花","Pig Dice":"小猪骰子","games":"游戏","matches":"对局","decisions":"次决策","wins":"获胜","Seed":"种子","vs.":"对阵"};
  Object.assign(uiTranslations,{'Realtime: 1 decision; other games: 3 probes':'实时游戏单次决策；其他游戏三次判断','shorter time breaks ties':'同进度用时较短优先','Elapsed':'用时','Level progress (%)':'关卡进度（%）','Gates reached':'已到达关卡数','Distance (m)':'行驶距离（米）'});
  window.BlinkArenaI18n={createPresentationTranslator,entries:uiTranslations};
  const localize=createPresentationTranslator(uiTranslations);
  const localizePanel=()=>{localize(byId('gameEloPanel'));window.JevMetricHelp?.arena();};

  const html = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const count = value => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('en-US') : '—';
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const percent = value => finite(value) ? (value * 100).toFixed(1) + '%' : '—';
  const decimal = value => finite(value) ? value === 0 ? '0' : value.toPrecision(3) : '—';
  const stateNames={idle:'Waiting',archived:'Archived',running:'Evaluation running',pausing:'Pausing',paused:'Paused',interrupted:'Interrupted',complete:'Complete',complete_with_errors:'Complete with failures',error:'Evaluation error'};
  const gameLabels={othello_6x6:'Othello 6×6',othello_8x8:'Othello 8×8',gomoku_19x19:'Gomoku',hex_7x7:'Hex',dots_and_boxes_3x3:'Dots and Boxes',terraria_survival:'Terraria',jump_jump:'Jump Jump',tetris_placement:'Tetris',snake_navigation:'Snake',merge_2048:'2048',sokoban_puzzle:'Sokoban',mario_platformer:'Mario',racing_sprint:'Racing',doudizhu:'Dou Dizhu',texas_holdem:'Texas Hold’em',property_tycoon:'Property Tycoon',liars_dice:'Liar’s Dice',goofspiel:'Goofspiel',blackjack:'Blackjack',zha_jin_hua:'Golden Flower',pig_dice:'Pig Dice'};
  const modelLabels={'rule-engine-v1':'Rule engine','qwen3.8-27b-base':'Qwen3.8-27B · Local base','qwen3.6-35b-a3b-base':'Qwen3.6-35B-A3B · Local base','qwen3.8-27b-dashscope':'Qwen3.8-27B · DashScope','qwen3.8-max-dashscope':'Qwen3.8-Max · DashScope','qwen3.6-35b-a3b-dashscope':'Qwen3.6-35B-A3B · DashScope','dashscope-qwen3.8-max':'Qwen3.8-Max · DashScope','dashscope-qwen3.6-35b-a3b':'Qwen3.6-35B-A3B · DashScope','oneshot27b-gameplay-terminal-rl4':'Blink 27B · Gameplay RL','oneshot27b-control-reviewed-sft-iter310':'Blink 27B · Reviewed SFT / iter 310'};
  const modelLabel=(id,fallback,identity)=>window.JevModelLabels?.model(id,fallback,identity)||modelLabels[id]||(!/[\u3400-\u9fff]/.test(fallback||'')&&fallback)||id||'Model';
  const gameLabel=id=>gameLabels[id]||id;
  const scoreLabels={gates_reached:'Gates reached; final horizontal position breaks ties',platforms_reached:'Platforms reached',lines_cleared:'Lines cleared',foods_eaten:'Food collected',merge_points:'Merge points',boxes_on_targets:'Boxes on targets',progress_percent:'Level progress (%); native score breaks ties',distance_metres:'Distance (m); remaining durability breaks ties',native_return:'Native payoff against the dealer'};
  window.BlinkArenaLabels={game:gameLabel,model:modelLabel};
  let payload = null, loading = false, visible = false, scope = 'overall', requestVersion = 0;
  const participants = () => payload?.protocol?.participants?.length ? payload.protocol.participants : payload?.options?.participants?.length ? payload.options.participants : payload?.fixed_config?.baseline || [];
  const games = () => payload?.fixed_config?.games || payload?.options?.games || [];
  const participantName = id => {const participant=participants().find(item=>item.id===id);return modelLabel(id,participant?.name,participant?.model_identity||participant?.identity);};
  const gameName = gameLabel;
  const isEngine = id => id === 'rule-engine-v1' || participants().find(item => item.id === id)?.provider === 'rule_engine';
  let lastMessage={text:'',failed:false};
  function message(text, failed = false) {
    byId('eloMessage').textContent = text;
    byId('eloMessage').classList.toggle('error', failed);
    lastMessage={text,failed};localize(byId('eloMessage'));
  }
  function controls() {
    byId('eloRefresh').textContent='Refresh';
    byId('eloRefresh').disabled=loading;
    localize(byId('eloRefresh'));
  }
  function comparisonText(comparison) {
    if(!comparison)return 'Final game score';
    const metric=scoreLabel(comparison);
    if(comparison.time_scoring_revision)return 'Completion first; '+metric+' · shorter time breaks ties';
    return (comparison.metric&&comparison.metric!=='native_return'?'Completion first; ':'')+metric+(comparison.higher_is_better===false?' · lower is better':' · higher is better');
  }
  function renderBaseline() {
    const progress=payload?.baseline_progress,baseline=payload?.fixed_config?.baseline||[];
    const states={idle:'Waiting',registered:'Registered',queued:'Queued',pending:'Pending',running:'Running',pausing:'Pausing',paused:'Paused',interrupted:'Interrupted',complete:'Complete',complete_with_errors:'Complete with failures',error:'Error'};
    const completed=finite(progress?.completed)?progress.completed:0,planned=finite(progress?.planned)?progress.planned:null;
    byId('eloBaselineStatus').textContent=(states[progress?.state]||'Registered')+(planned!==null?' · '+count(completed)+' / '+count(planned)+' matches':'');
    byId('eloBaselineProgress').innerHTML=baseline.map(player=>{
      const item=(progress?.participants||[]).find(row=>row.id===player.id),done=finite(item?.completed)?item.completed:0,total=finite(item?.planned)?item.planned:null;
      const pct=total>0?Math.max(0,Math.min(100,100*done/total)):0,coverage=finite(item?.coverage)?item.coverage:0;
      const scope=count(coverage)+' / '+count(isEngine(player.id)?games().filter(game=>game.engine_supported).length:games().length)+(isEngine(player.id)?' board games':' games');
      return '<div class="elo-baseline-card" title="'+html((states[item?.state]||'Registered')+' · '+scope)+'"><strong>'+html(participantName(player.id))+'</strong><div class="elo-baseline-bar" role="progressbar" aria-label="'+html(participantName(player.id))+' evaluation progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+pct.toFixed(1)+'"><span style="width:'+pct+'%"></span></div><span>'+(total!==null?count(done)+' / '+count(total)+' matches':'Waiting for schedule')+'</span></div>';
    }).join('');
  }
  function renderConfiguration() {
    const baseline=payload?.fixed_config?.baseline||[],direct=games().filter(game=>game.mode==='direct').length;
    const decisions=payload?.protocol?.decision_policy==='jev-game-decision-policy-v2-realtime-single'?'Realtime: 1 decision; other games: 3 probes':'3 repeats per decision';
    byId('eloConfiguration').textContent=games().length?games().length+' games · '+direct+' direct matches · '+decisions:'Loading schedule…';
    byId('eloGames').innerHTML=games().map(item=>'<span class="elo-chip '+(item.mode==='direct'?'direct':'paired')+'" title="'+html(item.mode==='direct'?'Same seed, reversed roles':comparisonText(item.comparison))+'">'+html(gameName(item.id))+'<small>'+(item.mode==='direct'?'Direct match':'Final-score comparison')+'</small></span>').join('');
    byId('eloBaseline').innerHTML=baseline.map(item=>'<span class="elo-chip">'+html(participantName(item.id))+'</span>').join('');
    ['eloEngineRange','eloPlan'].forEach(id=>{byId(id).textContent='';byId(id).hidden=true;});
    renderBaseline();
  }
  function stabilityCells(row) {
    if(isEngine(row.id))return '<td class="elo-stability">—</td><td class="elo-stability">—</td><td class="elo-stability">—</td>';
    const metric=row.stability||{},decisions=Number(metric.decisions||0),probabilityDecisions=Number(metric.probability_decisions||0);
    const agreement=decisions>0?percent(metric.agreement_rate):'—',probability=probabilityDecisions>0?percent(metric.probability_stability):'—';
    const variance=probabilityDecisions>0?decimal(metric.mean_probability_variance):'—';
    return '<td class="elo-stability" title="'+count(decisions)+' decisions"><strong>'+agreement+'</strong></td><td class="elo-stability" title="Complete probabilities for all three repeats: '+count(probabilityDecisions)+' / '+count(decisions)+' decisions"><strong>'+probability+'</strong></td><td class="elo-stability" title="Sample variance across aligned candidate probabilities; lower is better"><strong>'+variance+'</strong></td>';
  }
  function rowMarkup(row) {
    const limitedScope=isEngine(row.id)&&scope==='overall';
    const required=limitedScope?games().filter(game=>game.engine_supported).length:Math.max(Number(row.required_games||0),scope==='overall'?games().length:0),covered=Number(row.coverage||0);
    const completeCoverage=required>0&&covered>=required,hasRating=!limitedScope&&finite(row.rating)&&(scope!=='overall'||completeCoverage);
    const coverage=scope==='overall'?count(covered)+' / '+count(required)+(limitedScope?' board games':' games'):count(Number(row.played||0))+' scored matches';
    return '<tr><td class="lb-rank">'+(!limitedScope&&finite(row.rank)&&(scope!=='overall'||completeCoverage)?html(row.rank):'—')+'</td><td><strong class="lb-model-name" data-i18n-raw>'+(window.JevModelLogo?.markup(row.logo)||'')+'<span>'+html(participantName(row.id))+'</span></strong></td><td class="lb-score'+(hasRating?'':' elo-unrated')+'">'+(hasRating?row.rating.toFixed(1):limitedScope?'Per-game only':scope==='overall'&&covered>0&&!completeCoverage?'Incomplete coverage':'Not evaluated')+'</td><td>'+coverage+'<small>W / D / L '+count(row.match_counts_available===false?null:Number(row.wins||0))+' / '+count(row.match_counts_available===false?null:Number(row.draws||0))+' / '+count(row.match_counts_available===false?null:Number(row.losses||0))+'</small></td>'+stabilityCells(row)+'</tr>';
  }
  function renderRankings() {
    const kindIds = games().length ? games().map(item => item.id) : payload?.protocol?.kinds || [];
    if (scope !== 'overall' && !kindIds.includes(scope)) scope = 'overall';
    byId('eloScope').innerHTML = '<option value="overall">Overall · game-weighted</option>' + kindIds.map(kind => '<option value="' + html(kind) + '">' + html(gameName(kind)) + '</option>').join('');
    byId('eloScope').value = scope;
    const headers=['#','Participant','Elo','Coverage / W–D–L','Agreement','Probability stability','Variance ↓'];
    document.querySelectorAll('#gameEloPanel .elo-table thead th').forEach((node,index)=>{node.textContent=headers[index]||node.textContent;});
    byId('eloRankHeading').textContent = scope === 'overall' ? 'Overall ranking' : gameName(scope);
    const commonAnchor=payload?.protocol?.run_type==='common-anchor-star-v1';
    const controlRows=payload?.snapshot?.control_audit?.rows||[];
    const recordedControls=controlRows.map(row=>participantName(row.model_id)+' ≥ '+count(row.recorded_c_actions)).join(' · ');
    const controlNote=recordedControls?tr(' Recorded rule takeovers C (lower bounds): ',' 已记录规则接管 C（下界）：')+recordedControls+tr('. Missing control audits remain unknown; these counts do not establish pure model performance.','。缺失控制审计的片段保留为未知，这些计数不代表纯模型表现。'):'';
    byId('eloRankingNote').textContent=commonAnchor?tr('Common anchor: SFT-1015. Each reference model plays this anchor, with seats reversed in direct games. Opponents and match counts differ; interpret Elo within this registered schedule.','共同锚点：SFT-1015。各参照模型与此锚点比较，直接对战交换席位。各模型的对手范围和对局数不同，Elo 应结合本次登记赛程解读。')+controlNote:'';
    if(payload?.game_scope?.historical_subset){
      byId('eloRankingNote').textContent += tr(' Historical subset: ',' 历史子集：')+count(payload.game_scope.games.length)+tr(' games. Retired games are excluded; overall Elo is recomputed from the remaining per-game ratings. This is not a new evaluation.',' 款游戏。已移除下线游戏，总 Elo 按保留游戏重新计算；这不是新一轮模型评测。');
      if(payload.source_control_audit)byId('eloRankingNote').textContent += tr(' The source snapshot contains rule takeovers; their counts cover the original game scope and do not establish pure model performance for this subset.',' 原始快照含规则接管记录；其计数覆盖旧游戏范围，不能据此将当前子集成绩视为纯模型表现。');
    }
    byId('eloRankingNote').hidden=!commonAnchor&&!payload?.game_scope?.historical_subset;
    const rows = scope === 'overall' ? payload?.overall || [] : payload?.by_game?.[scope] || [];
    byId('eloRows').innerHTML = rows.length ? rows.map(rowMarkup).join('') : '<tr><td colspan="7" class="lb-empty-cell">No settled results yet.</td></tr>';
    localizePanel();
  }
  function scoreLabel(comparison){
    const simple={gates_reached:'Gates reached',progress_percent:'Level progress (%)',distance_metres:'Distance (m)'};
    return (comparison?.time_scoring_revision&&simple[comparison.metric])||scoreLabels[comparison?.metric]||comparison?.metric||'Native score';
  }
  function episodeMarkup(id,result,comparison) {
    if(!result)return '<div class="elo-episode"><strong>'+html(participantName(id))+'</strong><span>Native score —</span></div>';
    let value='—';
    if(finite(result.score))value=String(result.score);
    else if(typeof result.score==='string'&&result.score)value=result.score;
    else if(result.score&&typeof result.score==='object')value=JSON.stringify(result.score);
    const budget=result.budget_exhausted===true||result.outcome==='budget_exhausted';
    const outcome=budget?'Budget exhausted':({win:'Win',loss:'Loss',draw:'Draw',error:'Failure'}[result.outcome]||result.outcome||'');
    const key=Array.isArray(result.comparison_key)&&result.comparison_key.length>1&&result.comparison_key.every(finite)?'<small>Compare in order: '+html(result.comparison_key.join(' / '))+'</small>':'';
    const elapsed=finite(result.time_score?.elapsed_seconds)?'<span>Elapsed: '+result.time_score.elapsed_seconds.toFixed(1)+' s</span>':'';
    return '<div class="elo-episode"'+(result.episode_id?' title="Record: '+html(result.episode_id)+'"':'')+'><strong>'+html(participantName(id))+'</strong><span>'+html(scoreLabel(comparison))+': <b>'+html(value)+'</b></span>'+elapsed+key+'<small>'+html(outcome)+(result.reused===true?' · reused':result.reused===false?' · new record':'')+'</small></div>';
  }
  // Read-only archive supplies all games, beyond the live endpoint's last 80 rows.
  let matchGame='all',matchLimit=20,replayArchive=null,replayLoading=null,replayError='',replayLastFetch=0;
  function matchRecords(){
    const rows=new Map();
    if(replayArchive?.run_id===payload?.run_id)for(const row of replayArchive.matches)rows.set(Number(row.ordinal),row);
    for(const row of payload?.matches||[])rows.set(Number(row.ordinal),row);
    return [...rows.values()].sort((a,b)=>Number(b.ordinal)-Number(a.ordinal));
  }
  function replayStatus(){
    const node=byId('eloReplayStatus');node.hidden=!replayLoading&&!replayError;
    node.textContent=replayLoading?tr('Loading replay archive…','读取回放归档…'):replayError?tr('Replay archive unavailable. Open a record to retry.','回放归档暂不可用，点击对局可重试。'):'';
  }
  async function loadReplayArchive(force=false){
    if(replayLoading)return replayLoading;
    const run=payload?.run_id;if(!run)return false;
    const current=replayArchive?.run_id===run;
    if(!force&&current&&(Number(replayArchive.updated_at)>=Number(payload.updated_at)||Date.now()-replayLastFetch<30000))return true;
    replayLastFetch=Date.now();replayError='';
    replayLoading=(async()=>{
      try{
        const response=await fetch('./playground/visible-control.js?run='+encodeURIComponent(run)+'&updated='+encodeURIComponent(payload.updated_at||0),{cache:'no-store'});
        if(!response.ok)throw Error('archive_unavailable');
        const source=(await response.text()).trim(),prefix='window.BlinkArenaReplayArchive=';
        if(!source.startsWith(prefix)||!source.endsWith(';'))throw Error('invalid_archive');
        let archive=JSON.parse(source.slice(prefix.length,-1));
        if(archive.encoding==='gzip-base64'){
          if(archive.run_id!==run||typeof archive.data!=='string'||typeof DecompressionStream!=='function')throw Error('unsupported_archive');
          const bytes=Uint8Array.from(atob(archive.data),character=>character.charCodeAt(0));
          const decoded=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
          archive=JSON.parse(await new Response(decoded).text());
        }
        if(archive.schema!=='jev-arena-replay-v1'||archive.run_id!==run||!Array.isArray(archive.matches)||!archive.replays||typeof archive.replays!=='object')throw Error('archive_not_current');
        if(payload?.run_id!==run)return false;
        replayArchive=archive;return true;
      }catch{replayError='unavailable';return false}
      finally{replayLoading=null;renderMatches();localizePanel();}
    })();replayStatus();return replayLoading;
  }
  function replayForMatch(match){
    if(replayArchive?.run_id!==payload?.run_id)return null;
    const record=replayArchive.replays[String(match.ordinal).padStart(5,'0')];
    if(!record||!Array.isArray(record.streams)||record.participants?.[0]!==match.a||record.participants?.[1]!==match.b)return null;
    if(['ordinal','kind','seed','mode','status','score_a','finished_at'].some(key=>record[key]!==match[key]))return null;
    const streams=record.streams.map(stream=>stream.episode_id?{...replayArchive.episodes?.[stream.episode_id],...stream}:stream);
    if(streams.some(stream=>!Array.isArray(stream.steps)))return null;
    return {...record,streams};
  }
  async function openReplay(ordinal){
    await loadReplayArchive();
    let match=matchRecords().find(row=>Number(row.ordinal)===ordinal),record=match&&replayForMatch(match);
    if(!record){await loadReplayArchive(true);match=matchRecords().find(row=>Number(row.ordinal)===ordinal);record=match&&replayForMatch(match);}
    if(record&&window.BlinkArenaReplayView){replayError='';replayStatus();window.BlinkArenaReplayView.open(record);}
    else{replayError='unavailable';replayStatus();}
  }
  function renderMatches() {
    const all=matchRecords(),gameIds=[...new Set([...games().map(game=>game.id),...all.map(row=>row.kind)])];
    if(matchGame!=='all'&&!gameIds.includes(matchGame))matchGame='all';
    byId('eloMatchGame').innerHTML='<option value="all">All games</option>'+gameIds.map(kind=>'<option value="'+html(kind)+'">'+html(gameName(kind))+'</option>').join('');
    byId('eloMatchGame').value=matchGame;
    const filtered=all.filter(row=>matchGame==='all'||row.kind===matchGame),matches=filtered.slice(0,matchLimit);
    byId('eloMatchesSummary').textContent='Recent matches · '+count(all.length)+' recorded';
    byId('eloMatchCount').textContent=count(matches.length)+' / '+count(filtered.length);
    byId('eloMatchesMore').hidden=matches.length>=filtered.length;
    byId('eloMatchRows').innerHTML=matches.length?matches.map(item=>{
      const paired=item.mode==='paired',comparison=item.comparison||games().find(game=>game.id===item.kind)?.comparison;
      const result=item.status==='error'?'Error · unscored':item.score_a===1?participantName(item.a)+' wins':item.score_a===0?participantName(item.b)+' wins':item.score_a===.5?'Draw':'Awaiting result';
      const participantsMarkup=paired?episodeMarkup(item.a,item.result_a,comparison)+episodeMarkup(item.b,item.result_b,comparison):'<strong>'+html(participantName(item.a))+'</strong><small>vs. '+html(participantName(item.b))+'</small>';
      return '<tr data-match="'+html(item.ordinal)+'" data-game="'+html(item.kind)+'"><td>'+html(item.ordinal)+'</td><td>'+html(gameName(item.kind))+'<small>Seed '+html(item.seed)+'</small></td><td>'+(paired?'Same-seed final score':'Direct match')+(paired?'<small>'+html(comparisonText(comparison))+'</small>':'<small>Roles reversed</small>')+'</td><td>'+participantsMarkup+'</td><td>'+html(result)+(item.error_type?'<small>'+html(item.error_type)+'</small>':'')+'</td><td><button type="button" data-replay="'+html(item.ordinal)+'">Replay</button></td></tr>';
    }).join(''):'<tr><td colspan="6" class="lb-empty-cell">'+(all.length?'No matches for this game.':'Final scores and match records appear after settlement.')+'</td></tr>';
    byId('eloMatchRows').querySelectorAll('[data-replay]').forEach(button=>button.onclick=()=>openReplay(Number(button.dataset.replay)));
    replayStatus();localize(byId('eloMatchHistory'));
  }
  function renderRepair() {
    let node=byId('eloRepair');
    if(!node){node=document.createElement('div');node.id='eloRepair';node.className='elo-plan';node.setAttribute('role','status');byId('eloProgress').after(node);}
    const repair=payload?.repair;
    const valid=repair&&Number.isInteger(repair.total)&&repair.total>=0&&Number.isInteger(repair.completed)&&Number.isInteger(repair.remaining)&&repair.completed>=0&&repair.remaining>=0&&repair.completed+repair.remaining===repair.total;
    node.hidden=!valid;if(!valid){node.textContent='';return;}
    const pct=repair.total?100*repair.completed/repair.total:100;
    const state=({running:'Repair running',complete:'Repair complete',blocked:'Repair blocked',paused:'Repair paused'})[repair.state]||'Repair pending';
    node.innerHTML='<strong>'+state+'</strong><div class="lb-progress" role="progressbar" aria-label="Repair progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+pct.toFixed(1)+'"><span style="width:'+pct+'%"></span></div><span>Repaired '+count(repair.completed)+' / '+count(repair.total)+'</span>';
  }
  function render() {
    renderConfiguration(); controls(); renderRankings(); renderMatches(); renderRepair();
    const completed = Number(payload?.completed || 0), planned = Number(payload?.planned || 0);
    const progress = planned ? Math.max(0,Math.min(100,100*completed/planned)) : 0;
    const headline=payload?.repair?.state==='running'?'Repairing failed matches':stateNames[payload?.state]||'Waiting';
    byId('eloStatus').textContent = headline + (planned ? ' · ' + count(completed) + ' / ' + count(planned) + ' matches' : '');
    byId('eloProgress').setAttribute('aria-valuenow', progress.toFixed(1));
    let progressFill=byId('eloProgress').querySelector('span');
    if(!progressFill){progressFill=document.createElement('span');byId('eloProgress').append(progressFill);}
    progressFill.style.width=progress+'%';
    byId('eloRun').textContent='';byId('eloRun').hidden=true;
    if (payload?.error_type) message('Evaluation error: ' + payload.error_type, true);
    localizePanel();
  }
  async function refresh(force = false) {
    if (loading && !force) return;
    const version = ++requestVersion;
    loading = true; controls();
    try {
      const data = await api('elo');
      if (version !== requestVersion) return;
      payload = data;
      if (/^(Could not load Arena: |Evaluation error: )/.test(lastMessage.text) && !data.error_type) message('');
      render();
      if(byId('eloMatchHistory').open)void loadReplayArchive();
    } catch (error) {
      if (version === requestVersion) { message('Could not load Arena: ' + error.message, true); }
    } finally {
      if (version === requestVersion) { loading = false; controls(); }
    }
  }
  byId('eloMatchHistory').addEventListener('toggle',()=>{if(byId('eloMatchHistory').open)void loadReplayArchive();});
  byId('eloMatchGame').onchange=event=>{matchGame=event.target.value;matchLimit=20;renderMatches();};
  byId('eloMatchesMore').onclick=()=>{matchLimit+=20;renderMatches();};
  byId('eloRefresh').onclick = () => refresh();
  byId('eloScope').onchange = event => { scope = event.target.value; renderRankings(); };
  window.JevElo = {refresh,modelChanged() {},setVisible(value) { visible = value; byId('gameEloPanel').classList.toggle('hidden',!value); if (value) refresh(); }};
  window.JevI18n?.onChange(()=>{render();message(lastMessage.text,lastMessage.failed);});
  setInterval(() => { if (!document.hidden && visible && !byId('leaderboardView').classList.contains('hidden')) refresh(); },15000);
})();

/* Replay UI reuses isolated original game renderers; archive inputs remain read-only. */
(function () {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const t=(en,zh)=>window.JevI18n?.t(en,zh)??en;
  const model=id=>id?window.JevModelLabels?.model(id,id)||String(id):'—';
  const json=value=>{try{return JSON.stringify(value,null,2)}catch{return String(value)}};
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const games={othello_6x6:['Othello 6×6','黑白棋 6×6'],othello_8x8:['Othello 8×8','黑白棋 8×8'],gomoku_19x19:['Gomoku','五子棋'],hex_7x7:['Hex','六角棋'],dots_and_boxes_3x3:['Dots and Boxes','点格棋'],jump_jump:['Jump Jump','跳一跳'],terraria_survival:['Terraria','泰拉瑞亚'],tetris_placement:['Tetris','俄罗斯方块'],snake_navigation:['Snake','贪吃蛇'],merge_2048:['2048','2048'],sokoban_puzzle:['Sokoban','推箱子'],mario_platformer:['Mario','马里奥'],racing_sprint:['Racing','赛车'],doudizhu:['Dou Dizhu','斗地主'],texas_holdem:['Texas Hold’em','德州扑克'],property_tycoon:['Property Tycoon','地产大亨'],liars_dice:['Liar’s Dice','吹牛骰子'],goofspiel:['Goofspiel','竞价纸牌'],blackjack:['Blackjack','二十一点'],zha_jin_hua:['Golden Flower','炸金花'],pig_dice:['Pig Dice','小猪骰子']};
  const gameName=id=>games[id]?t(...games[id]):String(id||'Arena');

  let dialog=null,replay=null,streamIndex=0,positions=new Map(),timer=null,playing=false,opener=null;
  let renderer=null,rendererKind=null,mountPromise=null,mountSerial=0,paintSerial=0,playSerial=0,transitioning=false,resumeCurrent=false;
  const streams=()=>Array.isArray(replay?.streams)?replay.streams:[];
  const stream=()=>streams()[streamIndex]||{};
  const steps=()=>Array.isArray(stream().steps)?stream().steps:[];
  const lastPosition=()=>steps().length+(stream().final_state!=null?1:0);
  const position=()=>Math.max(0,Math.min(lastPosition(),positions.get(streamIndex)||0));
  const clone=value=>value==null?value:typeof structuredClone==='function'?structuredClone(value):JSON.parse(JSON.stringify(value));
  const node=selector=>dialog?.querySelector(selector);
  function clearTimer(){if(timer!==null)clearTimeout(timer);timer=null;}
  function pause(){
    resumeCurrent=transitioning;playing=false;++playSerial;clearTimer();renderer?.stop?.({snapToEnd:false});transitioning=false;renderUI();
  }
  function destroyRenderer(){
    ++mountSerial;++paintSerial;renderer?.destroy?.();renderer=null;rendererKind=null;mountPromise=null;
    const host=node('.arv-render-host');if(host)host.replaceChildren();
  }
  function close(){pause();destroyRenderer();if(dialog?.open)dialog.close();}
  function ensureDialog(){
    if(dialog)return;
    dialog=document.createElement('dialog');dialog.id='jevArenaReplayDialog';dialog.className='arv-dialog';dialog.setAttribute('aria-labelledby','arvTitle');
    dialog.innerHTML='<div class="arv-shell"><header class="arv-header"><div><span class="arv-eyebrow"></span><h3 id="arvTitle"></h3><p class="arv-meta"></p></div><button type="button" data-arv-control="close">×</button></header><div class="arv-body"><label class="arv-stream"><span></span><select data-arv-control="stream"></select></label><p class="arv-participants"></p><p class="arv-notice" hidden></p><div class="arv-layout"><section class="arv-state"><h4 class="arv-state-heading"></h4><div class="arv-render-host"></div><p class="arv-render-status" role="status" hidden></p></section><aside class="arv-decision"></aside></div><details class="arv-archive"><summary></summary><div class="arv-state-summary"></div><pre></pre></details></div><footer class="arv-controls"><div class="arv-playback"><button type="button" data-arv-control="prev">←</button><button type="button" data-arv-control="play"></button><button type="button" data-arv-control="next">→</button><span class="arv-position" aria-live="polite"></span></div><input type="range" data-arv-control="position" min="0" max="0" value="0" step="1"></footer></div>';
    document.body.append(dialog);
    dialog.addEventListener('close',()=>{pause();destroyRenderer();if(opener?.isConnected)opener.focus({preventScroll:true});});
    dialog.addEventListener('cancel',()=>pause());
    dialog.addEventListener('click',event=>{if(event.target===dialog)close();});
    node('[data-arv-control="close"]').onclick=close;
    node('[data-arv-control="stream"]').onchange=event=>{const nextStream=Number(event.target.value);pause();streamIndex=nextStream;resumeCurrent=false;renderUI();paint({reason:'stream',animate:false});};
    node('[data-arv-control="prev"]').onclick=()=>seek(position()-1,false);
    node('[data-arv-control="next"]').onclick=()=>seek(position()+1,true);
    node('[data-arv-control="position"]').oninput=event=>seek(Number(event.target.value),false);
    node('[data-arv-control="play"]').onclick=()=>playing?pause():play();
    node('.arv-archive').ontoggle=()=>{if(node('.arv-archive').open)renderArchive();};
  }
  function frameAt(index){
    const s=stream(),items=steps();
    if(index===0)return {state:s.initial_state,label:t('Initial state','初始状态'),step:null};
    if(index>items.length)return {state:s.final_state,label:t('Final state','最终状态'),step:null};
    const step=items[index-1]||{};
    if(step.state!=null)return {state:step.state,label:t('After step','动作后状态'),step};
    if(step.after_state!=null)return {state:step.after_state,label:t('After step','动作后状态'),step};
    if(step.before_state!=null)return {state:step.before_state,label:t('Before step','动作前状态'),step};
    if(step.observation!=null)return {state:step.observation,label:t('Recorded observation','归档观测'),step};
    return {state:null,label:t('Decision record','决策记录'),step};
  }
  const frame=()=>frameAt(position());
  function stateSummary(state){
    if(state==null)return '<p class="arv-empty">'+t('No saved state for this step.','此步未保存状态。')+'</p>';
    if(typeof state!=='object')return '<p class="arv-observation">'+esc(String(state).slice(0,1200))+(String(state).length>1200?'…':'')+'</p>';
    const names={turn:['Turn','执方'],winner:['Winner','胜者'],score:['Score','得分'],points:['Points','分数'],steps:['Steps','步数'],position:['Position','位置'],speed:['Speed','速度'],distance:['Distance','距离'],elapsed:['Elapsed','用时'],elapsed_seconds:['Elapsed seconds','用时（秒）'],time:['Time','时间'],durability:['Durability','耐久度'],phase:['Phase','阶段'],passes:['Passes','跳过次数'],terminal:['Terminal','是否终局'],done:['Finished','是否结束'],stage:['Stage','关卡'],round:['Round','回合'],health:['Health','耐久度'],z:['Distance','距离'],x:['Lateral position','横向位置'],pedal:['Pedal','踏板'],collision_count:['Collisions','碰撞次数'],offroad_seconds:['Off-road seconds','离路秒数'],pot:['Pot','底池'],to_call:['To call','需跟注'],street:['Street','阶段'],landlord:['Landlord','地主席位'],leader:['Leader','领出席位']};
    const entries=Object.entries(state).filter(([key,value])=>names[key]&&(value===null||['string','number','boolean'].includes(typeof value))).slice(0,12);
    const labels={hand:['Recorded hand','归档手牌'],board:['Table cards','桌面牌'],bottom:['Bottom cards','底牌'],dice:['Recorded dice','归档骰子'],opponent_counts:['Opponent card counts','对手剩余牌数'],stacks:['Stacks','筹码']};
    const lists=Object.entries(labels).filter(([key])=>Array.isArray(state[key])&&state[key].length&&state[key].every(value=>['string','number'].includes(typeof value)));
    const chips=lists.map(([key,label])=>'<div class="arv-value-list"><h5>'+esc(t(...label))+'</h5><div class="arv-value-chips">'+state[key].map(value=>'<span>'+esc(value)+'</span>').join('')+'</div></div>').join('');
    const facts=entries.length?'<dl class="arv-state-facts">'+entries.map(([key,value])=>'<div><dt>'+esc(t(...names[key]))+'</dt><dd>'+esc(key==='winner'?winnerName(value):value===null?'—':typeof value==='boolean'?(value?t('Yes','是'):t('No','否')):value)+'</dd></div>').join('')+'</dl>':'';
    return chips+facts||'<p class="arv-empty">'+t('Saved observation is available in the archive details below.','已保存观测可在下方归档详情中查看。')+'</p>';
  }
  function metric(value,percent=false){return finite(value)?percent?(value*100).toFixed(1)+'%':value===0?'0':value.toPrecision(3):'—';}
  function streamName(s,index){return s.participant?model(s.participant):(Array.isArray(s.participants)&&s.participants.length?s.participants.map(model).join(' / '):t('Match','对局')+' '+(index+1));}
  function winnerName(value){
    if(value==null)return '—';
    if(value==='draw')return t('Draw','平局');
    const seat=replay?.seats?.[value];
    const side=!seat&&['X','O'].includes(String(value))&&['X','O'].includes(replay?.a_side)&&replay?.participants?.length===2?replay.participants[value===replay.a_side?0:1]:null;
    return seat||side?model(seat||side)+' · '+value:model(String(value));
  }
  function replayScoreLabel(value){
    const english={'原生合并积分':'Merge points','原生庄家对局结算收益':'Native payoff against the dealer','实际行驶距离（米）':'Distance (m)','已到目标格箱数':'Boxes on targets','已吃食物数':'Food collected','已落平台数':'Platforms reached','最终关卡进度（%）；同进度比较原生积分':'Level progress (%); native score breaks ties','本局到达终点次数；同次数比较最终横坐标':'Gates reached; final horizontal position breaks ties','累计消除行数':'Lines cleared'};
    Object.assign(english,{'最终关卡进度（%）':'Level progress (%)','本局到达终点次数':'Gates reached'});
    return english[value]?t(english[value],value):value||t('Score','得分');
  }
  function resultMarkup(s){
    const result=s.result||{},outcome={win:['Win','胜'],loss:['Loss','负'],draw:['Draw','平'],error:['Failure','失败'],budget_exhausted:['Budget exhausted','预算耗尽']};
    const outcomeKey=result.outcome||result.status;
    const status=outcome[outcomeKey]?t(...outcome[outcomeKey]):result.outcome||winnerName(result.winner);
    const elapsed=finite(result.time_score?.elapsed_seconds)?'<span>'+esc(t('Elapsed','用时'))+': '+result.time_score.elapsed_seconds.toFixed(1)+' s</span>':'';
    return '<div class="arv-result"><span>'+esc(t('Archived result','归档结果'))+'</span><strong>'+esc(status)+'</strong>'+(result.score!=null?'<span>'+esc(replayScoreLabel(result.score_label))+': '+esc(typeof result.score==='object'?JSON.stringify(result.score):result.score)+'</span>':'')+elapsed+'</div>';
  }

  function rendererStatus(message){const target=node('.arv-render-status');if(target){target.textContent=message;target.hidden=!message;}}
  async function ensureRenderer(){
    if(renderer&&rendererKind===replay?.kind)return renderer;
    if(mountPromise&&rendererKind===replay?.kind)return mountPromise;
    destroyRenderer();rendererKind=replay?.kind;const version=mountSerial,kind=rendererKind;
    if(!window.JevReplayRenderer?.mount){rendererStatus(t('Game renderer unavailable. Archived states remain in the details.','游戏画面暂不可用，归档状态仍可在详情中查看。'));return null;}
    rendererStatus(t('Loading game replay…','读取游戏回放中…'));
    mountPromise=Promise.resolve(window.JevReplayRenderer.mount(node('.arv-render-host'),{kind,lang:window.JevI18n?.lang||'en'})).then(instance=>{
      if(version!==mountSerial){instance?.destroy?.();return null;}
      if(!instance||typeof instance.update!=='function')throw Error('renderer_unavailable');
      renderer=instance;mountPromise=null;rendererStatus('');return instance;
    }).catch(()=>{if(version===mountSerial){mountPromise=null;rendererStatus(t('Game renderer unavailable. Archived states remain in the details.','游戏画面暂不可用，归档状态仍可在详情中查看。'));}return null;});
    return mountPromise;
  }
  async function paint({animate=false,reason='seek'}={}){
    const current=frame(),idx=position(),s=stream(),kind=replay?.kind;
    if(current.state==null){++paintSerial;renderer?.stop?.({snapToEnd:false});node('.arv-render-host').hidden=true;rendererStatus(t('No frame was saved for this step. The decision record remains available.','此步未保存画面，可查看决策记录。'));return true;}
    node('.arv-render-host').hidden=false;
    // The adapter receives copies; neither renderer nor viewer can change archived inputs.
    const previous=current.step?.before_state??(idx>0?frameAt(idx-1).state:null);
    const options=clone({kind,state:current.state??null,previousState:reason==='resume'?null:previous,step:current.step,action:current.step?.action??null,position:idx,playing,animate,durationMs:700,lang:window.JevI18n?.lang||'en',recording:s.recording,initial_state:s.initial_state??null,allStates:[s.initial_state,...steps().map(step=>step.state??step.after_state??null),s.final_state].filter(state=>state!=null),stream:s,reason});
    // Mount may clear an old game. Allocate the paint ticket after the mount begins.
    const pending=ensureRenderer(),ticket=++paintSerial;
    const instance=await pending;if(!instance||ticket!==paintSerial||kind!==replay?.kind||!dialog?.open)return false;
    if(reason==='play'&&!playing)options.animate=false;
    try{
      const result=instance.update(options);
      if(result&&typeof result.then==='function')await result;
      else if(options.animate)await new Promise(resolve=>setTimeout(resolve,finite(result?.durationMs)?result.durationMs:options.durationMs));
      return ticket===paintSerial;
    }catch{
      if(ticket===paintSerial){node('.arv-render-host').hidden=true;rendererStatus(t('This saved frame cannot be displayed. See the archive details.','此归档帧暂不能显示，请查看归档详情。'));}
      return false;
    }
  }
  function renderArchive(){
    if(!dialog||!replay)return;const current=frame(),s=stream();
    node('.arv-state-summary').innerHTML=stateSummary(current.state);
    node('.arv-archive pre').textContent=json({recording:s.recording,missing_frames:s.missing_frames,state:current.state??null,step:current.step??null,result:s.result??null});
  }
  function renderUI(){
    if(!dialog||!replay)return;
    const s=stream(),current=frame(),item=current.step,idx=position(),max=lastPosition();
    const stamp=replay.finished_at!=null?new Date(typeof replay.finished_at==='number'?replay.finished_at*1000:replay.finished_at):null;
    const date=stamp&&Number.isFinite(stamp.getTime())?stamp.toLocaleString(window.JevI18n?.lang==='zh'?'zh-CN':'en-GB',{hour12:false,timeZone:'Asia/Shanghai'}):'';
    node('.arv-eyebrow').textContent=t('MATCH REPLAY','对局回放');node('#arvTitle').textContent=gameName(replay.kind)+' · #'+(replay.ordinal??'—');
    node('.arv-meta').textContent=t('Seed','种子')+' '+(replay.seed??'—')+(date?' · '+date:'');
    node('[data-arv-control="close"]').setAttribute('aria-label',t('Close replay','关闭回放'));
    node('.arv-stream').hidden=streams().length<2;node('.arv-stream>span').textContent=t('Model replay','模型轨迹');
    const selector=node('[data-arv-control="stream"]'),labels=streams().map((row,index)=>'<option value="'+index+'">'+esc(streamName(row,index))+'</option>').join('');
    if(selector.innerHTML!==labels)selector.innerHTML=labels;selector.value=String(streamIndex);
    node('.arv-participants').hidden=streams().length>1;node('.arv-participants').textContent=streamName(s,streamIndex);
    const missing=s.missing_frames===true||['action_log','decision-record'].includes(s.recording);
    node('.arv-notice').hidden=!missing;node('.arv-notice').textContent=t('Incomplete frame archive · only recorded states are shown.','画面归档不完整，仅展示已有状态。');
    const stateHeading=node('.arv-state-heading');stateHeading.textContent=current.label;
    stateHeading.title=s.recording==='reconstructed_verified'?t('Reconstructed from archived moves; final state verified.','由归档动作重建，已核对终局状态。'):'';
    const actor=item?(item.player?model(item.player):s.participant?model(s.participant):'—')+(item.actor!=null?' · '+item.actor:''):'—';
    const forced=item?.origin==='forced_legal';
    const action=item?.action==null?'—':typeof item.action==='object'?JSON.stringify(item.action):String(item.action),metrics=item?.stability||{};
    const frameLabel=idx===0?t('Initial','初态'):idx>steps().length?t('Final','终态'):t('Step','步骤')+' '+idx+' / '+steps().length;
    node('.arv-decision').innerHTML='<h4>'+esc(frameLabel)+'</h4>'+(forced?'<p class="arv-forced">'+t('Forced legal action','规则强制动作')+'</p>':'')+'<dl class="arv-decision-facts"><div><dt>'+t('Actor','行动者')+'</dt><dd>'+esc(actor)+'</dd></div><div><dt>'+t('Action','动作')+'</dt><dd class="arv-action">'+esc(action)+'</dd></div><div><dt>'+t('Latency','耗时')+'</dt><dd>'+esc(finite(item?.latency_seconds)?item.latency_seconds.toFixed(2)+' s':'—')+'</dd></div></dl>'+(item&&!forced&&item.model_call!==false?'<dl class="arv-stability"><div><dt>'+t('Agreement','三次一致率')+'</dt><dd>'+metric(metrics.agreement_rate,true)+'</dd></div><div><dt>'+t('Probability stability','概率稳定度')+'</dt><dd>'+metric(metrics.probability_stability,true)+'</dd></div><div><dt>'+t('Variance ↓','方差 ↓')+'</dt><dd>'+metric(metrics.mean_probability_variance)+'</dd></div></dl>':'')+resultMarkup(s);
    node('.arv-archive summary').textContent=t('Archived state & record','归档状态与记录');if(node('.arv-archive').open)renderArchive();
    const prev=node('[data-arv-control="prev"]'),next=node('[data-arv-control="next"]'),play=node('[data-arv-control="play"]'),range=node('[data-arv-control="position"]');
    prev.disabled=!idx;next.disabled=idx>=max;play.disabled=!max;play.textContent=playing?t('Pause','暂停'):t('Play','播放');
    prev.setAttribute('aria-label',t('Previous step','上一步'));next.setAttribute('aria-label',t('Next step','下一步'));range.setAttribute('aria-label',t('Replay position','回放位置'));
    node('.arv-position').textContent=frameLabel;range.max=String(max);range.value=String(idx);range.disabled=!max;
  }
  async function seek(index,animate){
    pause();resumeCurrent=false;positions.set(streamIndex,Math.max(0,Math.min(lastPosition(),index)));renderUI();
    const ticket=playSerial;transitioning=animate;await paint({animate,reason:animate?'next':'seek'});if(ticket===playSerial)transitioning=false;
  }
  async function advance(token,resume=false){
    if(!playing||token!==playSerial||!dialog?.open)return;
    if(!resume){if(position()>=lastPosition()){playing=false;renderUI();return;}positions.set(streamIndex,position()+1);}
    resumeCurrent=false;transitioning=true;renderUI();await paint({animate:true,reason:resume?'resume':'play'});
    if(!playing||token!==playSerial)return;
    transitioning=false;
    if(position()>=lastPosition()){playing=false;renderUI();return;}
    timer=setTimeout(()=>{timer=null;advance(token);},220);
  }
  function play(){
    clearTimer();const resume=resumeCurrent||transitioning;if(position()>=lastPosition()&&!resume)positions.set(streamIndex,0);
    playing=true;const token=++playSerial;renderUI();advance(token,resume);
  }
  function open(data){
    pause();destroyRenderer();replay=data&&typeof data==='object'?data:{};streamIndex=0;positions=new Map();resumeCurrent=false;opener=document.activeElement;ensureDialog();
    node('.arv-archive').open=false;node('.arv-body').scrollTop=0;renderUI();if(!dialog.open)dialog.showModal();paint({animate:false,reason:'open'});node('[data-arv-control="close"]').focus();
  }
  window.BlinkArenaReplayView={open,close};
  window.JevI18n?.onChange(()=>{if(dialog?.open){renderUI();paint({animate:false,reason:'locale'});}});
})();
