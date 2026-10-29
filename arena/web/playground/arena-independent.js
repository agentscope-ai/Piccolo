(function(root){
  'use strict';
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pending=row=>row.status==='pending';
  const modelName=row=>root?.JevModelLabels?.displayName(row.id,row.name)??
    (row.id==='oneshot-w22m05r02-v5best-avg50'?String(row.name).replace(/^(?:OneShot|Blink)\b/i,'Piccolo'):row.name);
  function success(row){return !pending(row)&&finite(row.success_rate)?row.success_rate:null;}
  function csv(payload){
    const fields=['model','game','success_rate','success_rate_valid','wins','planned','valid','errors','budget_exhausted',
      'current_mean_seconds','current_p50_seconds','current_p95_seconds','all_mean_seconds','all_p50_seconds','all_p95_seconds'];
    const quote=value=>'"'+String(value??'').replace(/"/g,'""')+'"';
    const rows=Object.entries(payload.by_game).flatMap(([game,table])=>table.map(row=>[
      modelName(row),game,success(row),row.success_rate_valid,row.wins,row.planned,row.valid,row.errors,row.budget_exhausted,
      ...['mean_seconds','p50_seconds','p95_seconds'].map(k=>row.latency_current?.[k]),
      ...['mean_seconds','p50_seconds','p95_seconds'].map(k=>row.latency_all?.[k])
    ]));
    return '\ufeff'+[fields,...rows].map(row=>row.map(quote).join(',')).join('\r\n');
  }
  let scope='overall',latencySource='current';
  function render(payload,host){
    const t=(en,zh)=>root.JevI18n?.t(en,zh)??en;
    const number=value=>finite(value)?value.toLocaleString('en-US'):'—';
    const rate=value=>finite(value)?(value*100).toFixed(2)+'%':'—';
    const seconds=value=>finite(value)?value.toFixed(2):'—';
    const games=payload.fixed_config.games;
    const label=game=>t(game.label_en,game.label_zh);
    const model=id=>{const row=payload.overall.find(row=>row.id===id);return row?modelName(row):id;};
    if(scope!=='overall'&&!games.some(g=>g.id===scope))scope='overall';
    if(scope==='overall')latencySource='current';
    const table=scope==='overall'?payload.overall:payload.by_game[scope];
    const rows=table.map((row,index)=>{
      const empty=pending(row),latency=row['latency_'+latencySource],score=success(row);
      const identity=root.JevModelLogo?.identity(row,modelName(row))||escape(modelName(row));
      return '<tr data-independent-model="'+escape(row.id)+'"><td>'+(!empty?index+1:'—')+'</td>'+
        '<td><strong class="lb-model-name" data-i18n-raw>'+identity+'</strong>'+(empty?'<small>'+t('Awaiting results','等待成绩')+'</small>':'')+'</td>'+
        '<td class="lb-score" data-independent-score="'+(score??'')+'">'+rate(score)+(row.errors>0?'<small>'+t('Lower bound','下界')+' · '+t('Valid episodes','有效局')+' '+rate(row.success_rate_valid)+'</small>':'')+'</td>'+
        '<td>'+(!empty?number(row.wins)+' / '+number(row.planned):'—')+'</td>'+
        '<td>'+(!empty?number(row.valid)+' / '+number(row.planned):'—')+'</td>'+
        '<td>'+number(row.errors)+'</td><td>'+number(row.budget_exhausted)+'</td>'+
        ['mean_seconds','p50_seconds','p95_seconds'].map(k=>'<td>'+seconds(latency?.[k])+'</td>').join('')+'</tr>';
    }).join('');
    const headers=[t('#','序号'),t('Model','模型'),t('Success rate','成功率'),t('Success / Planned','成功 / 计划'),
      t('Valid / Planned','有效 / 计划'),t('Episode errors','局错误'),t('Budget exhausted','预算耗尽'),
      t('Mean (s)','均值（秒）'),'P50 (s)','P95 (s)'];
    const repair=payload.replay_validation.mario;
    host.innerHTML='<p class="elo-configuration">'+t('Independent games','独立游戏评测')+' · '+games.length+' '+t('games','款游戏')+' × 8 '+t('seeds','个种子')+' · '+
      number(payload.completed)+' / '+number(payload.planned)+' '+t('finished','局结束')+' · '+number(payload.scored)+' '+t('valid','局有效')+' · '+number(payload.errors)+' '+t('episode errors','局错误')+'</p>'+
      '<p class="muted">'+t('Success rate = successes / planned episodes, with games weighted equally. Errors remain explicit; affected rates are lower bounds. Draws and budget exhaustion are not successes. Piccolo results are pending.',
        '成功率＝成功局数 / 计划局数，各游戏等权。错误单列，受影响成绩为下界；平局和预算耗尽不计成功。Piccolo 成绩待补。')+'</p>'+
      '<div class="elo-ranking-head"><label>'+t('Game','游戏')+' <select id="independentScope"><option value="overall">'+t('Overall · game-weighted','综合 · 游戏等权')+'</option>'+games.map(g=>'<option value="'+escape(g.id)+'">'+escape(label(g))+'</option>').join('')+'</select></label>'+
      '<label>'+t('Response time','响应耗时')+' <select id="independentLatency"><option value="current">'+t('Current requests','本轮请求')+'</option><option value="all"'+(scope==='overall'?' disabled':'')+'>'+t('Including reused requests','含复用请求')+'</option></select></label>'+
      '<button type="button" id="independentDownload">'+t('Export per-game CSV','导出分游戏 CSV')+'</button></div>'+
      '<div class="lb-table-scroll" tabindex="0" role="region" aria-label="'+t('Independent game results','独立游戏成绩')+'"><table class="lb-table independent-table"><thead><tr>'+headers.map(h=>'<th>'+escape(h)+'</th>').join('')+'</tr></thead><tbody>'+rows+'</tbody></table></div>'+
      '<p class="muted">'+t('Response time is per HTTP request, including server-side queueing. It is not episode duration. Games with no new requests have blank current timings; select a game to inspect timings including reused requests.',
        '响应耗时按每次 HTTP 请求统计，含服务端排队，不等同于整局用时。未新增请求的游戏，本轮耗时留空；选择具体游戏后可查看含复用请求的耗时。')+'</p>'+
      '<p class="independent-replay">'+t('Mario strict replay','马里奥严格回放')+'：'+number(repair.strict_passed)+' / '+number(repair.planned)+' · '+t('Repaired cases','原失败局补跑')+' '+number(repair.old_failed_completed)+' / '+number(repair.old_failed_total)+'</p>'+
      '<details><summary>'+number(payload.errors)+' '+t('episode error records','局错误记录')+'</summary><ul>'+payload.episode_errors.map(e=>'<li>'+escape(model(e.a))+' · '+escape(label(games.find(g=>g.id===e.kind)))+' · '+t('Seed','种子')+' '+e.seed+' · HTTP '+e.http_status+' · '+escape(e.error_code)+'</li>').join('')+'</ul></details>';
    const select=host.querySelector('#independentScope');select.value=scope;select.onchange=()=>{scope=select.value;render(payload,host);};
    const latency=host.querySelector('#independentLatency');latency.value=latencySource;latency.onchange=()=>{latencySource=latency.value;render(payload,host);};
    host.querySelector('#independentDownload').onclick=()=>{
      const url=URL.createObjectURL(new Blob([csv(payload)],{type:'text/csv;charset=utf-8'}));
      const a=document.createElement('a');a.href=url;a.download='gamejevarena-eight-seeds.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };
  }
  const api={success,csv,render};
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.JevIndependentArena=api;
})(typeof window==='undefined'?null:window);
