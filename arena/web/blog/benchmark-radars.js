import {benchmarkProfiles} from './benchmark-profiles.js';
import {renderMath} from './math.js';

const locale = window.JevI18n;
const tr = (en, zh) => locale.t(en, zh);
const NS = 'http://www.w3.org/2000/svg';
const palette = {
  p27: {stroke:'#9a613b', dash:'', fill:.10},
  p9: {stroke:'#b18b5c', dash:'3 4', fill:0},
  p4: {stroke:'#a59a86', dash:'1 5', fill:0},
  d3: {stroke:'#58817a', dash:'7 4', fill:.025},
  perplexity:{stroke:'#788aab',dash:'',fill:0},
  mercury:{stroke:'#899d61',dash:'',fill:0},
  microsoft:{stroke:'#6b9bac',dash:'5 3',fill:0},
  typesafe:{stroke:'#a67b91',dash:'',fill:0},
  luna:{stroke:'#82939a',dash:'2 3',fill:0},
  clef:{stroke:'#bb8c71',dash:'6 3',fill:0},
  strands:{stroke:'#85746a',dash:'2 4',fill:0}
};
const finite = value => typeof value === 'number' && Number.isFinite(value);
const percent = value => finite(value) ? (value * 100).toFixed(2) + '%' : tr('Not reported', '未报告');
const decimal = value => finite(value) ? value.toFixed(4) : tr('Not reported', '未报告');

function element(tag, className = '', text) {
  const result = document.createElement(tag);
  result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}

function svgElement(tag, attributes = {}, text) {
  const result = document.createElementNS(NS, tag);
  Object.entries(attributes).forEach(([key, value]) => result.setAttribute(key, String(value)));
  if (text !== undefined) result.textContent = text;
  return result;
}

function xy(axis, fraction, radius = 135) {
  const angle = axis * Math.PI / 3 - Math.PI / 2;
  return [300 + Math.cos(angle) * radius * fraction, 225 + Math.sin(angle) * radius * fraction];
}

function polygonPoints(fraction) {
  return Array.from({length:6}, (_, i) => xy(i, fraction).join(',')).join(' ');
}

function chart(profile, models, readout) {
  const svg = svgElement('svg', {viewBox:'0 0 600 455', class:'benchmark-radar-svg', role:'group', 'aria-label':tr(profile.title + ' six-axis accuracy, from 0 to 100 percent. Focus or select a point for its exact score.', profile.title + ' 六维准确率，统一采用 0 到 100% 刻度；聚焦或点击数据点可查看准确数值。')});
  svg.append(svgElement('title', {}, profile.title + ' · ' + profile.version + ' · Accuracy (%)'));
  const grid = svgElement('g', {class:'radar-grid', 'aria-hidden':'true'});
  [.25,.5,.75,1].forEach(level => {
    grid.append(svgElement('polygon', {points:polygonPoints(level), class:level === 1 ? 'radar-grid-outer' : ''}));
    const [x,y] = xy(0, level);
    grid.append(svgElement('text', {x:x + 7,y:y - 4,class:'radar-ring-value'}, String(level * 100)));
  });
  profile.axes.forEach((axis, i) => {
    const [x,y] = xy(i, 1);
    grid.append(svgElement('line', {x1:300,y1:225,x2:x,y2:y}));
  });
  grid.append(svgElement('text', {x:307,y:239,class:'radar-ring-value'}, '0'));
  svg.append(grid);

  profile.axes.forEach((axis, i) => {
    const [x,y] = xy(i, 1, 178);
    const anchor = i === 0 || i === 3 ? 'middle' : i < 3 ? 'start' : 'end';
    const firstY = i === 0 ? y - 14 : i === 3 ? y + 2 : y - 5;
    const label = svgElement('text', {x,y:firstY,'text-anchor':anchor,class:'radar-axis-label'});
    const parts=locale.lang==='zh' ? axis.label[1].match(/.{1,5}/g) : axis.lines;
    parts.forEach((line, lineIndex) => label.append(svgElement('tspan', {x,dy:lineIndex === 0 ? 0 : 18}, line)));
    label.append(svgElement('tspan', {x,dy:18,class:'radar-axis-count'}, 'n = ' + axis.samples));
    svg.append(label);
  });

  // A partial profile is never closed through zero. Missing dimensions remain gaps.
  [...models].sort((a,b) => Number(a.id === 'p27') - Number(b.id === 'p27')).forEach(model => {
    const style = palette[model.id];
    const group = svgElement('g', {class:'radar-series', 'data-series':model.id});
    const complete = model.values.length === 6 && model.values.every(finite);
    const common = {stroke:style.stroke,'stroke-width':model.id === 'p27' ? 2.6 : 2.1,'stroke-dasharray':style.dash,'stroke-linejoin':'round'};
    if (complete) {
      group.append(svgElement('polygon', {...common,points:model.values.map((value,i) => xy(i,value).join(',')).join(' '),fill:style.stroke,'fill-opacity':style.fill}));
    } else {
      const segments = [];
      for (let i=0;i<6;i++) {
        const next = (i+1)%6;
        if (finite(model.values[i]) && finite(model.values[next])) segments.push('M' + xy(i,model.values[i]).join(',') + ' L' + xy(next,model.values[next]).join(','));
      }
      group.append(svgElement('path', {...common,d:segments.join(' '),fill:'none'}));
    }
    model.values.forEach((value, i) => {
      if (!finite(value)) return;
      const [cx,cy] = xy(i,value);
      const axis = profile.axes[i];
      const description = model.label + ' · ' + tr(...axis.label) + ': ' + (value * 100).toFixed(4) + '% · n = ' + axis.samples;
      group.append(svgElement('circle', {cx,cy,r:3.3,fill:style.stroke,class:'radar-point', 'aria-hidden':'true'}));
      const hit = svgElement('circle', {cx,cy,r:10,fill:'transparent',class:'radar-hotspot',tabindex:0,role:'button','aria-label':description});
      hit.append(svgElement('title', {}, description));
      const inspect = () => { readout.textContent=description; readout.dataset.active='true'; };
      hit.addEventListener('pointerenter',inspect);
      hit.addEventListener('focus',inspect);
      hit.addEventListener('click',inspect);
      hit.addEventListener('keydown',event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspect(); }
      });
      group.append(hit);
    });
    svg.append(group);
  });
  return svg;
}

function taskDistribution(profile,kind) {
  const section=element('section','radar-design');
  section.append(element('h3','',tr('Task distribution','任务分布')),
    element('p','radar-design-intro',kind==='harness'
      ? tr('Six scenario categories and 29 task types, with 325 evaluation cases in total. The counts below cover the 295 Hard cases used for accuracy, containing 303 scored questions. Soft probability judgments are evaluated separately.',
        '基准覆盖 6 类场景、29 个细分任务，共 325 个评测样本。下表按场景列出用于准确率评测的 295 个 Hard 样本，合计 303 个问题；Soft 样本的概率分布单独评估。')
      : tr('500 tasks across six decision families: 480 choice questions and 20 ordered-scoring questions. The latter are included in artifact quality. Materials include documents, tables and workflow states.',
        '500 道任务覆盖六类决策，包括 480 道选择题和 20 道有序评分题；评分题归入产物质量类。材料包含文档、表格和工作流状态。')));
  const list=element('dl','radar-distribution');
  profile.axes.forEach(axis=>{
    const item=element('div');
    item.append(element('dt','',tr(...axis.label)),element('dd','',String(axis.samples)));
    list.append(item);
  });
  section.append(list);
  return section;
}

function metricDefinitions(kind) {
  const section=element('section','radar-definitions');section.append(element('h3','',tr('What the metrics measure','指标怎样计分')));
  const definitions=kind==='harness' ? [
    ['Hard Accuracy ↑',
      'Average the scored judgment dimensions within each call, calls within each task, then the 295 tasks equally. Failed or missing answers score zero. The six radar axes aggregate these same task scores by scenario.',
      '先对一次调用内的判断维度取平均，再对任务内的调用取平均，最后对 295 个任务等权平均。失败或缺失答案记零；雷达图将同一批任务得分按任务场景汇总。'],
    ['Soft TV ↓',
      'Total variation distance measures the gap between predicted and reference probability distributions. Zero means they match exactly. It is reported separately over 60 valid probability views, not added to Hard accuracy.',
      '总变差距离衡量预测概率与参考分布的差异，零表示完全一致。该指标对 60 份有效概率输出单独计算，不与 Hard 准确率合成一个总分。',
      '\\operatorname{TV}(p,y)=\\frac{1}{2}\\sum_k|p_k-y_k|'],
  ] : [
    ['Accuracy ↑',
      'Correct decisions divided by all 500 planned tasks. Invalid or missing outputs stay in the denominator and score zero. Subset accuracy uses the corresponding task count above.',
      '正确决策数除以全部 500 道计划任务数。无效或缺失输出保留在分母中并记零；分项准确率分别以上述各类任务数为分母。'],
    ['ECE10 ↓',
      'Group predictions into ten confidence bins. In each bin, compare mean confidence with observed accuracy, then weight the absolute gaps by the number of predictions. Lower values indicate better calibration.',
      '将预测按置信度分为十组，比较每组的平均置信度与实际准确率，再按样本数加权汇总绝对差值。数值越低，置信度与实际正确率越一致。'],
    ['Brier ↓',
      'For each task, sum the squared differences between predicted and reference probabilities over all candidates, then average across tasks. This evaluates the full probability vector, including confidence assigned to incorrect choices.',
      '对每道任务，将各候选项的预测概率与参考概率之差平方后求和，再对任务取平均。它评估完整概率向量，也计入分配给错误候选的概率。'],
  ];
  const list=element('dl');
  definitions.forEach(([name,en,zh,latex])=>{
    const item=element('div');const body=element('dd','',tr(en,zh));
    if(latex){const formula=element('div','radar-formula');formula.dataset.latex=latex;formula.dataset.display='inline';body.append(formula);}
    item.append(element('dt','',name),body);list.append(item);
  });section.append(list);return section;
}

function metricTable(models, kind) {
  const region=element('div','radar-metrics');
  const title=element('h4','',tr('Overall accuracy and probability quality','总体准确率与概率质量'));
  region.append(title,element('p','radar-table-hint',tr('Scroll sideways to view probability metrics and coverage.','横向滑动查看概率指标与有效输出数。')));
  if (!models.length) {
    region.append(element('p','radar-empty',tr('Select a model above to inspect its profile.','请在上方选择模型，查看能力分布。')));
    return region;
  }
  const wrapper=element('div','radar-table-scroll');
  wrapper.tabIndex=0;
  wrapper.setAttribute('aria-label',tr('Overall benchmark metrics','总体评测指标'));
  const table=element('table','radar-metrics-table');
  const thead=element('thead');
  const columns=kind === 'harness' ? [tr('Model','模型'),'Accuracy ↑','Soft TV ↓',tr('Valid Soft views','有效 Soft 输出')] : [tr('Model','模型'),'Accuracy ↑','ECE10 ↓','Brier ↓',tr('Valid distributions','有效概率分布')];
  const heading=element('tr');
  columns.forEach(label => { const th=element('th','',label); th.scope='col'; heading.append(th); });
  thead.append(heading);
  const body=element('tbody');
  models.forEach(model => {
    const row=element('tr');
    const name=element('th','',model.label);name.scope='row';
    row.append(name,element('td','',percent(model.metrics.accuracy)));
    if (kind === 'harness') row.append(element('td','',decimal(model.metrics.tv)));
    else row.append(element('td','',decimal(model.metrics.ece)),element('td','',decimal(model.metrics.brier)));
    row.append(element('td','',finite(model.validProbabilityViews)?model.validProbabilityViews+' / '+model.plannedProbabilityViews:tr('Not reported','未报告')));
    body.append(row);
  });
  table.append(thead,body);wrapper.append(table);region.append(wrapper);
  region.append(element('p','radar-metric-note',kind === 'harness'
    ? tr('Soft TV is withheld when the registered 60-view coverage is incomplete; a valid-only diagnostic is not substituted for the benchmark metric. Missing results are never filled with zero.','未覆盖全部 60 份输出时，Soft TV 保留为未报告；不以仅有效输出的诊断值替代正式指标，缺失值不补零。')
    : tr('ECE10 and Brier are withheld unless all 500 probability distributions are valid. Probability sums use a tolerance of 1e-3, without renormalization. Missing results are never filled with zero.','只有全部 500 份概率分布有效时才报告 ECE10 与 Brier。概率和容差为 1e-3，不重新归一化；缺失指标不补零。')));
  return region;
}

function mountRadar(host, kind) {
  if (!host) return {render() {}};
  const profile=benchmarkProfiles[kind];
  // Keep the article comparison small: Piccolo-27B and the three highest
  // overall-accuracy external models. The full cohort remains in the source.
  const external=profile.models.filter(model=>!['p27','p9','p4'].includes(model.id))
    .sort((a,b)=>(b.metrics.accuracy??-1)-(a.metrics.accuracy??-1)).slice(0,3);
  const comparisonModels=[profile.models.find(model=>model.id==='p27'),...external].filter(Boolean);
  const selected=new Set(comparisonModels.map(model=>model.id));

  function render(focusId) {
    host.classList.add('benchmark-profile');
    host.replaceChildren();
    const heading=element('div','radar-heading');
    heading.append(element('span','radar-kicker',profile.title.toUpperCase() + ' · ' + profile.version),
      element('h3','',tr('Capability profiles and model comparison','能力分布与模型对比')),
      element('p','',tr('Piccolo-27B and the three external models with the highest overall accuracy. Toggle a name to compare the six task categories.',
        '这里比较 Piccolo-27B 与总体准确率最高的三个外部模型。点击模型名称，可对照六类任务的表现。')));
    const legend=element('div','radar-legend');
    legend.setAttribute('role','group');
    legend.setAttribute('aria-label',tr('Select models for the radar','选择雷达图中的模型'));
    comparisonModels.forEach(model => {
      const button=element('button','radar-legend-item',model.label);
      button.type='button';button.dataset.model=model.id;
      button.setAttribute('aria-pressed',String(selected.has(model.id)));
      button.style.setProperty('--series-color',palette[model.id].stroke);
      const swatch=element('span','radar-swatch radar-swatch-'+model.id);swatch.setAttribute('aria-hidden','true');
      button.prepend(swatch);
      button.onclick=()=>{if(selected.has(model.id))selected.delete(model.id);else selected.add(model.id);render(model.id);};
      legend.append(button);
    });

    const readout=element('div','radar-readout',tr('Hover or focus a point for its score and sample count.','悬停或聚焦数据点，查看准确率与任务数。'));
    readout.setAttribute('role','status');readout.setAttribute('aria-live','polite');
    const models=comparisonModels.filter(model=>selected.has(model.id));
    const layout=element('div','radar-layout');
    const canvas=element('div','radar-canvas');
    canvas.append(chart(profile,models,readout),readout);
    if(!models.length)canvas.append(element('p','radar-empty',tr('Select a model to show its curve.','选择一个模型以显示曲线。')));
    layout.append(canvas);
    const fullLeaderboard=element('a','radar-full-link',tr('Full leaderboard · all 11 models ↗','完整榜单 · 全部 11 个模型 ↗'));
    fullLeaderboard.href='https://decisionplayground.agentscope.io/?view=leaderboard&benchmark='+kind+'jevbench';
    fullLeaderboard.target='_blank';fullLeaderboard.rel='noopener noreferrer';
    const provenance=element('p','radar-provenance',tr('Evaluation: ','评测日期：') + profile.evaluatedAt + ' · ' + profile.title + ' ' + profile.version + ' · ' + tr('Selected comparison from the 11-model cohort','选自 11 模型对比集'));
    host.append(taskDistribution(profile,kind),metricDefinitions(kind),heading,legend,layout,metricTable(comparisonModels,kind),fullLeaderboard,provenance);
    renderMath(host);
    if(focusId)host.querySelector('[data-model="'+focusId+'"]')?.focus({preventScroll:true});
  }
  render();
  return {render};
}

export function mountBenchmarkRadars({harness,data}) {
  const views=[mountRadar(harness,'harness'),mountRadar(data,'data')];
  return {render(){views.forEach(view=>view.render());}};
}
