import {rankedRows, barPercent} from './evidence.js';

const ownModel = 'blink-27b-1028';
const benchmarks = {
  jevbench: {title:'JevBench Public', url:'https://github.com/fstandhartinger/jevbench', scope:['231 questions', '231 道题']},
  decisionindex: {title:'Decision Index', url:'https://huggingface.co/spaces/multimodalart/jev-decision-index', scope:['Text index', '文本指数']},
  harnessjevbench: {title:'HarnessJevBench Hard', url:'https://github.com/agentscope-ai/HarnessJevBench', scope:['295 tasks · macro accuracy', '295 个任务 · 宏平均准确率']},
  datajevbench: {title:'DataJevBench', url:'https://github.com/datajuicer/DataJevBench', scope:['500 tasks', '500 道任务']},
};

// Differences use the unrounded scores. Each rank belongs only to this snapshot.
export function benchmarkSummary(benchmark) {
  if (!benchmark || !Number.isFinite(benchmark.scale) || benchmark.scale <= 0) return null;
  const rows = rankedRows(benchmark).filter(row => row.status === 'complete'
    && Number.isFinite(row.score) && row.score >= 0 && row.score <= benchmark.scale);
  const own = rows.find(row => row.model_key === ownModel);
  if (!own) return null;
  const peers = rows.filter(row => !/^Piccolo(?:-|$)/i.test(row.model));
  const peer = peers.reduce((best, row) => !best || Math.abs(row.score - own.score) < Math.abs(best.score - own.score) ? row : best, null);
  return {
    own, peer, scored:rows.length,
    rank:1 + rows.filter(row => row.score > own.score).length,
    tied:rows.filter(row => row.score === own.score).length > 1,
    delta:peer ? (own.score - peer.score) / benchmark.scale * 100 : null,
  };
}

export function mountBenchmarkOverview(host) {
  const t = (en, zh) => window.JevI18n.t(en, zh);
  const node = (tag, className, text) => {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text != null) result.textContent = text;
    return result;
  };
  const score = (row, benchmark) => benchmark.scale === 100
    ? row.score.toFixed(2) : (row.score / benchmark.scale * 100).toFixed(2) + '%';

  function comparisonRow(row, benchmark, isOwn) {
    const item = node('div', 'bo-comparison-row' + (isOwn ? ' bo-own-row' : ''));
    const label = node('div', 'bo-row-label');
    label.append(node('span', '', row.model), node('span', 'bo-row-value', score(row, benchmark)));
    const track = node('div', 'bo-track');
    track.setAttribute('aria-hidden', 'true');
    const fill = node('span', 'bo-fill');
    fill.style.width = barPercent(row, benchmark.scale) + '%';
    track.append(fill); item.append(label, track);
    return item;
  }

  function metric(benchmark) {
    const definition = benchmarks[benchmark.id];
    const summary = benchmarkSummary(benchmark);
    const item = node('article', 'bo-metric');
    const heading = node('h4', 'bo-metric-title');
    const link = node('a', '', definition.title + ' ↗');
    link.href = definition.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    heading.append(link);
    item.append(heading, node('p', 'bo-scope', t(...definition.scope)));
    if (!summary) {
      item.append(node('p', 'bo-unavailable', t('No reported Piccolo-27B result.', '暂无 Piccolo-27B 成绩。')));
      return item;
    }
    const result = node('div', 'bo-result');
    const value = node('strong', 'bo-value', score(summary.own, benchmark));
    if (benchmark.scale === 100) value.append(node('small', '', ' / 100'));
    const rank = node('span', 'bo-rank', t(
      `${summary.tied ? 'Joint rank' : 'Rank'} ${summary.rank} / ${summary.scored} scored models`,
      `${summary.tied ? '并列第' : '第'} ${summary.rank} 名 / ${summary.scored} 个有成绩模型`
    ));
    result.append(value, rank);
    item.append(result);
    const comparisons = node('div', 'bo-comparisons');
    comparisons.append(comparisonRow(summary.own, benchmark, true));
    if (summary.peer) comparisons.append(comparisonRow(summary.peer, benchmark, false));
    item.append(comparisons);
    if (summary.peer) {
      const unit = benchmark.scale === 100 ? t('index points', '指数分') : t('percentage points', '个百分点');
      const magnitude = Math.abs(summary.delta).toFixed(2);
      const gap = summary.delta === 0
        ? t('Tied with the closest peer in this comparison.', '与本组最接近的其他模型持平。')
        : t(`${summary.delta > 0 ? '+' : '−'}${magnitude} ${unit} versus the closest peer.`, `相对本组最接近的其他模型：${summary.delta > 0 ? '+' : '−'}${magnitude} ${unit}。`);
      item.append(node('p', 'bo-gap', gap));
    }
    return item;
  }

  function render(snapshot) {
    if (!host) return;
    host.classList.add('benchmark-overview');
    host.replaceChildren();
    if (!Array.isArray(snapshot?.benchmarks)) {
      host.append(node('p', 'bo-unavailable', t('Benchmark results are loading.', '正在读取评测结果。')));
      return;
    }
    const heading = node('div', 'bo-heading');
    heading.append(node('h3', '', t('Piccolo-27B at a glance', 'Piccolo-27B 成绩概览')),
      node('span', '', snapshot.snapshot_date));
    host.append(heading);
    const groups = [
      {title:['External benchmarks', '外部基准'], ids:['jevbench', 'decisionindex']},
      {title:['Benchmarks we designed', '我们设计的基准'], ids:['harnessjevbench', 'datajevbench']},
    ];
    for (const group of groups) {
      const section = node('div', 'bo-group');
      section.append(node('h3', 'bo-group-title', t(...group.title)));
      const grid = node('div', 'bo-grid');
      for (const id of group.ids) {
        const benchmark = snapshot.benchmarks.find(item => item.id === id);
        if (benchmark) grid.append(metric(benchmark));
      }
      section.append(grid); host.append(section);
    }
    host.append(node('p', 'bo-footnote', t(
      'Ranks refer to this dated comparison; differences use unrounded scores. Bars start at zero: accuracy uses 0–100%; Decision Index uses 0–100 points. Benchmark titles link to the official sources.',
      '排名仅针对该日期的对比集，差值由未四舍五入的成绩计算。条形均从零开始：准确率为 0–100%，Decision Index 为 0–100 分。点击基准名称可查看官方来源。'
    )));
  }
  return {render};
}
