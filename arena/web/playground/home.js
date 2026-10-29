/* Public comparisons and clearly marked internal previews use registered results. */
(() => {
  'use strict';
  const modelId = 'blink-27b-1028';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const definitions = [
    {id: 'jevbench', title: 'JevBench Public', publicVersion: true, url: 'https://github.com/fstandhartinger/jevbench', metric: ['Accuracy', '准确率'],
      scope: ['231 examples · Self-run evaluation', '231 个样本 · 自行复现评测'],
      note: ['All eleven registered models use the Public-231 protocol, with fresh inference on October 28. This is separate from the 1,500-item Capability test.',
        '十一个登记模型均采用 Public-231 协议，成绩来自 10 月 28 日重新推理；与 1,500 条 Capability 测试分开。']},
    {id: 'decisionindex', title: 'Decision Index Public', publicVersion: true, url: 'https://huggingface.co/spaces/multimodalart/jev-decision-index', metric: ['Public Index · 0–100', '公开决策指数 · 0–100'],
      scope: ['Public suite · Chance-corrected index', '公开评测集 · 随机基线校正指数'],
      note: ['The three Piccolo sizes reuse training-team Public results (140,178 requests); other available scores use official Public results. Seven of eleven models have scores. No new Decision Index inference was run; official per-request error coverage is unverified.',
        'Piccolo 三个尺寸复用训练侧 Public 成绩（140,178 个请求），其他已有分数来自官方 Public 榜单；11 个模型中有 7 个取得成绩。本次未重跑 Decision Index，官方逐请求错误覆盖未经独立核验。']},
    {id: 'harnessjevbench', title: 'HarnessJevBench', publicVersion: true, url: 'https://github.com/agentscope-ai/HarnessJevBench', metric: ['Mean Hard task score', 'Hard 任务平均分'],
      scope: ['295 Hard tasks · Soft scores separate', '295 个 Hard 任务 · Soft 单独计分'],
      note: ['Scores use the October 28 evaluation of 295 Hard tasks / 303 questions; failures score zero. Soft is separate. Radar dimensions use the same scored predictions.',
        '成绩来自 10 月 28 日评测：295 个 Hard 任务、303 个问题，失败计零分；Soft 单独计分，雷达维度来自同轮预测。']},
    {id: 'datajevbench', title: 'DataJevBench', unreleased: true, metric: ['Accuracy', '准确率'],
      scope: ['500 examples · Six data decision subsets', '500 个样本 · 六类数据决策'],
      note: ['October 28 inference, rescored with probability-sum tolerance 1e-3 and no probability normalization. All 500 records remain in the denominator; each contributes 0.2 percentage points.',
        '采用 10 月 28 日推理结果，概率和容差 1e-3，不归一化原始概率。全部 500 条记录保留在分母中，每条对应 0.2 个百分点。']},
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
  const titleText = (definition, benchmark) => definition.title +
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
      const row = benchmark?.display_rows?.find(item => item.model_key === modelId);
      const button = make('button', 'home-result' + (selected === definition.id ? ' is-selected' : ''));
      button.type = 'button';
      button.dataset.benchmark = definition.id;
      button.setAttribute('aria-pressed', String(selected === definition.id));
      button.setAttribute('aria-controls', 'homeComparison');
      const copy = make('span', 'home-result-copy');
      copy.append(make('span', 'home-result-name', titleText(definition, benchmark)), make('small', '', tr(...definition.metric)));
      if (definition.unreleased) copy.append(make('span', 'home-result-status', tr('Internal preview · Coming Soon', '内部预览 · Coming Soon')));
      const value = complete(row) ? row.score_display : '—';
      button.append(copy, make('strong', '', value), make('span', 'home-result-arrow', '↗'));
      button.setAttribute('aria-label', `${titleText(definition, benchmark)} · ${value} · ${definition.unreleased ? tr('Internal preview · Coming Soon', '内部预览 · Coming Soon') : tr('Compare results', '对比成绩')}`);
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
    heading.append(titleBlock, make('span', 'home-chart-badge', tr('Piccolo-27B highlighted', '铜橙色标记 Piccolo-27B')));
    chart.append(heading);
    if (definition.unreleased) {
      const release = make('div', 'home-internal-preview');
      release.append(
        make('span', 'home-release-badge', tr('Unreleased · Coming Soon', '未公开 · Coming Soon')),
        make('p', '', tr('A benchmark developed by Piccolo. Results shown here are an internal evaluation preview.', 'Piccolo 自建基准；当前成绩为内部评测预览，基准尚未公开发布。'))
      );
      chart.append(release);
    }
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
      const valid = complete(row), ours = row.model_key === modelId;
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
        const maximum = row.score_scale?.[1] ?? (selected === 'decisionindex' ? 100 : 1);
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
    const open = make('button', 'home-inline-link', definition.unreleased
      ? tr('Explore the internal preview ↗', '查看内部评测预览 ↗')
      : tr('Explore the full leaderboard ↗', '查看完整榜单 ↗'));
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
