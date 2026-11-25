/* Home benchmark cards use the registered results and metric definitions. */
(() => {
  'use strict';
  const modelId = 'blink-27b-1028';
  const visionModelId = 'piccolo-27b-vl';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const definitions = [
    {id: 'jevbench', title: 'JevBench Public', publicVersion: true, url: 'https://github.com/fstandhartinger/jevbench', metric: ['Accuracy', '准确率'],
      scope: ['231 questions', '231 道题'],
      note: ['Public-231 accuracy. Piccolo results were updated on 2 November; other models retain their recorded evaluation dates.',
        'Public-231 答题准确率。Piccolo 成绩更新于 11 月 2 日，其他模型沿用各自评测日期。']},
    {id: 'decisionindex', title: 'Decision Index · Text Public', titleZh: 'Decision Index · 文本 Public', publicVersion: true, url: 'https://huggingface.co/spaces/multimodalart/jev-decision-index', metric: ['Decision Index · 0–100', '决策指数 · 0–100'],
      scope: ['Public suite · Five domains', 'Public 公开集 · 五个领域'],
      note: ['Text Public scores combine five domain skills after chance correction.',
        '文本 Public 成绩按五个领域的随机基线校正能力分加权汇总。']},
    {id: 'decisionindex-vision', title: 'Decision Index · Vision Public', titleZh: 'Decision Index · 多模态 Public', publicVersion: true, url: 'https://huggingface.co/spaces/multimodalart/jev-decision-index', metric: ['Public vision index · 0–100', '多模态公开指数 · 0–100'],
      scope: ['11 benchmarks · 11 models', '11 benchmarks · 11 models'],
      note: ['Public vision suite: 12,210 questions across perception, charts, documents and visual reasoning. The index averages chance-corrected benchmark skills with the official weights.',
        '公开视觉题集共 12,210 道题，覆盖感知、图表、文档与视觉推理；按官方权重汇总各子基准的随机基线校正能力分。']},
    {id: 'harnessjevbench', title: 'HarnessJevBench', publicVersion: true, url: 'https://github.com/agentscope-ai/HarnessJevBench', metric: ['Mean Hard task score', 'Hard 任务平均分'],
      scope: ['295 Hard tasks · 303 questions', '295 个 Hard 任务 · 303 个问题'],
      note: ['Hard scores are averaged equally across tasks; Soft TV measures probability-distribution distance. Radar axes show the corresponding scenario scores.',
        'Hard 分数按任务等权平均；Soft TV 衡量概率分布差异。雷达图展示对应场景的得分。']},
    {id: 'datajevbench', title: 'DataJevBench', publicVersion: true, url: 'https://github.com/datajuicer/DataJevBench', metric: ['Accuracy', '准确率'],
      scope: ['500 questions · Six data decision subsets', '500 道题 · 六类数据决策'],
      note: ['Accuracy covers all 500 questions. Probability validation uses a sum tolerance of 1e-3 and retains the original values.',
        '准确率按全部 500 道题计算；概率和容差为 1e-3，使用原始概率值计分。']},
  ];
  const host = document.getElementById('homeResults');
  const chart = document.getElementById('homeComparison');
  let payload = null, failed = false, loading = false, selected = 'jevbench';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const chartEffects = new Set();
  let chartObserver = null;
  function cancelChartMotion() {
    chartObserver?.disconnect(); chartObserver = null;
    for (const effect of chartEffects) effect.cancel();
    chartEffects.clear();
  }
  function revealBars(list, previous) {
    if (reducedMotion.matches || typeof list.animate !== 'function') return;
    const play = () => {
      if (document.hidden || !chart.getClientRects().length) return;
      for (const [i, bar] of [...list.querySelectorAll('.home-bar-fill')].entries()) {
        const width = Number(bar.dataset.width), old = previous.get(bar.closest('li').dataset.modelKey) ?? 0;
        if (!width || old === width) continue;
        const effect = bar.animate([{transform: `scaleX(${old / width})`}, {transform: 'scaleX(1)'}], {
          duration: 480, delay: Math.min(i * 22, 150), easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'backwards',
        });
        chartEffects.add(effect);
        effect.finished.then(() => chartEffects.delete(effect), () => chartEffects.delete(effect));
      }
    };
    if (!('IntersectionObserver' in window)) { play(); return; }
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      observer.disconnect();
      if (chartObserver === observer) chartObserver = null;
      if (list.isConnected && !reducedMotion.matches) play();
    }, {threshold: .15});
    chartObserver = observer; observer.observe(list);
  }
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const complete = row => row?.status === 'complete' && Number.isFinite(row.score);
  const versionText = benchmark => benchmark?.version ? 'v' + String(benchmark.version).replace(/^v/i, '') : '';
  const titleText = (definition, benchmark) => tr(definition.title, definition.titleZh ?? definition.title) +
    (definition.publicVersion && versionText(benchmark) ? ' ' + versionText(benchmark) : '');
  function navigate(mode) {
    const destination = document.querySelector(`.tabs [data-tab="${mode}"]`);
    if (!destination) return;
    destination.click();
    destination.focus({preventScroll: true});
    document.querySelector('.mast').scrollIntoView({block: 'start'});
  }
  function openBenchmark(id) {
    window.JevLeaderboard.open(id);
    document.querySelector('.tabs [data-tab="leaderboard"]').focus({preventScroll: true});
    document.querySelector('.mast').scrollIntoView({block: 'start'});
  }
  function render() {
    host.replaceChildren();
    for (const definition of definitions) {
      const benchmark = payload?.benchmarks?.find(item => item.id === definition.id);
      const row = benchmark?.display_rows?.find(item => item.model_key === (definition.id === 'decisionindex-vision' ? visionModelId : modelId));
      const button = make('button', 'home-result' + (selected === definition.id ? ' is-selected' : ''));
      button.type = 'button';
      button.dataset.benchmark = definition.id;
      button.setAttribute('aria-pressed', String(selected === definition.id));
      button.setAttribute('aria-controls', 'homeComparison');
      const copy = make('span', 'home-result-copy');
      copy.append(make('span', 'home-result-name', titleText(definition, benchmark)), make('small', '', tr(...definition.metric)));
      const value = complete(row) ? row.score_display : '—';
      button.append(copy, make('strong', '', value), make('span', 'home-result-arrow', '↗'));
      button.setAttribute('aria-label', `${titleText(definition, benchmark)} · ${value} · ${tr('Compare results', '对比成绩')}`);
      button.onclick = () => {
        selected = definition.id;
        render();
        host.querySelector(`[data-benchmark="${selected}"]`).focus({preventScroll: true});
      };
      host.append(button);
    }
    renderChart();
  }
  function renderChart() {
    const previous = new Map([...chart.querySelectorAll('.home-bar-fill')].map(bar => [bar.closest('li').dataset.modelKey, Number(bar.dataset.width)]));
    cancelChartMotion();
    chart.replaceChildren();
    chart.setAttribute('aria-busy', String(loading));
    const definition = definitions.find(item => item.id === selected);
    const benchmark = payload?.benchmarks?.find(item => item.id === selected);
    const rows = [...(benchmark?.display_rows ?? [])].sort((a, b) => {
      if (complete(a) !== complete(b)) return complete(a) ? -1 : 1;
      return (complete(a) ? b.score - a.score : 0) || a.model_key.localeCompare(b.model_key);
    });
    const heading = make('div', 'home-chart-heading');
    const titleBlock = make('div');
    const title = make('h3', '', titleText(definition, benchmark));
    if (definition.url) {
      const source = make('a', 'home-benchmark-source', titleText(definition, benchmark) + ' ↗');
      source.href = definition.url;
      source.target = '_blank';
      source.rel = 'noopener noreferrer';
      source.title = tr('Official benchmark · opens in a new tab', '官方基准 · 在新标签页打开');
      title.replaceChildren(source);
    }
    titleBlock.append(title, make('p', '', benchmark
      ? `${definition.publicVersion ? '' : versionText(benchmark) + ' · '}${tr(...definition.scope)}`
      : tr('Registered evaluation results', '已登记评测成绩')));
    heading.append(titleBlock, make('span', 'home-chart-badge', selected === 'decisionindex-vision' ? 'Piccolo-27B-VL highlighted' : tr('Piccolo-27B highlighted', '铜橙色标记 Piccolo-27B')));
    chart.append(heading);
    if (!rows.length || failed) {
      const empty = make('div', 'home-chart-empty', tr(
        failed ? 'Results could not be loaded.' : loading ? 'Loading registered results…' : 'No results for this benchmark yet.',
        failed ? '暂时无法读取成绩。' : loading ? '正在读取登记成绩…' : '此基准暂未登记成绩。'));
      if (failed) {
        const retry = make('button', '', tr('Try again', '重新加载'));
        retry.type = 'button';
        retry.onclick = refresh;
        empty.append(retry);
      }
      chart.append(empty);
      return;
    }
    const axis = make('div', 'home-chart-axis');
    const scale = make('span', 'home-chart-scale');
    scale.append(make('span', '', '0'), make('span', '', '100'));
    axis.append(make('span', '', tr(...definition.metric)), scale, make('span', ''));
    chart.append(axis);
    const list = make('ol', 'home-bar-list');
    list.setAttribute('aria-label', `${definition.title} · ${tr(...definition.metric)}`);
    for (const row of rows) {
      const valid = complete(row), ours = row.model_key === (selected === 'decisionindex-vision' ? visionModelId : modelId);
      const item = make('li', 'home-bar-row' + (ours ? ' is-ours' : '') + (!valid ? ' is-pending' : ''));
      item.dataset.modelKey = row.model_key;
      const name = window.JevModelLabels?.displayName(row.model_key, row.model) ?? row.model;
      const label = make('span', 'home-bar-label', name);
      const publisher = window.JevModelLogo?.resolve(row);
      if (publisher) {
        const link = make('a', 'home-model-link');
        link.href = publisher.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.title = publisher.name + ' · ' + tr('Official page', '官方页面');
        const logo = make('img', 'lb-model-logo');
        logo.src = publisher.logo;
        logo.width = 14; logo.height = 14; logo.alt = '';
        link.append(logo, make('span', '', name));
        label.replaceChildren(link);
      }
      const value = make('span', 'home-bar-value', valid ? row.score_display.replace(' / 100', '') : '—');
      const track = make('span', 'home-bar-track');
      track.setAttribute('aria-hidden', 'true');
      if (valid) {
        const bar = make('span', 'home-bar-fill');
        const maximum = row.score_scale?.[1] ?? (selected.startsWith('decisionindex') ? 100 : 1);
        const width = Math.max(0, Math.min(100, 100 * row.score / maximum));
        bar.style.width = `${width}%`; bar.dataset.width = String(width);
        track.append(bar);
      }
      item.append(label, track, value);
      list.append(item);
    }
    chart.append(list);
    revealBars(list, previous);
    const caption = make('p', 'home-chart-note', tr(...definition.note));
    const footer = make('div', 'home-chart-footer');
    const open = make('button', 'home-inline-link', tr('Open leaderboard ↗', '查看榜单 ↗'));
    open.type = 'button';
    open.onclick = () => openBenchmark(selected);
    const completed = rows.filter(complete).length;
    footer.append(make('span', '', tr(`${completed} of ${rows.length} models evaluated`, `${completed} / ${rows.length} 个模型已有成绩`)), open);
    chart.append(caption, footer);
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    if (!payload) render();
    try {
      const response = await fetch('./api/leaderboard', {
        headers: {Accept: 'application/json'}, signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw Error('Results unavailable');
      payload = await response.json();
      failed = false;
    } catch {
      failed = true;
      payload = null;
    } finally {
      loading = false;
      render();
    }
  }
  document.getElementById('blogView').addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.homeTarget) navigate(button.dataset.homeTarget);
    if (button.dataset.homeBenchmark) openBenchmark(button.dataset.homeBenchmark);
    if (button.dataset.homeScroll) document.getElementById(button.dataset.homeScroll)?.scrollIntoView({
      block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
    });
  });
  window.JevI18n?.onChange(render);
  reducedMotion.addEventListener('change', cancelChartMotion);
  document.addEventListener('visibilitychange', () => { if (document.hidden) cancelChartMotion(); });
  new MutationObserver(() => {
    const home = document.getElementById('blogView');
    if (home.hidden || home.classList.contains('hidden')) cancelChartMotion();
  }).observe(document.getElementById('blogView'), {attributes: true, attributeFilter: ['class', 'hidden']});
  document.querySelector('.tabs [data-tab="blog"]').addEventListener('click', refresh);
  render();
  refresh();
})();
