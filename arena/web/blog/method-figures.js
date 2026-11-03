import {renderMath} from './math.js';
import {dataArchitectureSVG, feedbackArchitectureSVG} from './architecture.js';

const locale = window.JevI18n;
const tr = (en, zh) => locale.t(en, zh);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

function node(tag, className = '', text) {
  const element = document.createElement(tag);
  element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function heading(kicker, title, note) {
  const head = node('div', 'mf-heading');
  head.append(node('span', 'mf-kicker', kicker), node('h3', '', title));
  if (note) head.append(node('p', 'mf-heading-note', note));
  return head;
}

function caption(en, zh) {
  return node('p', 'mf-caption', tr(en, zh));
}

function list(items, className = '') {
  const element = node('ul', className);
  items.forEach(item => element.append(node('li', '', item)));
  return element;
}

function arrow() {
  const element = node('span', 'mf-arrow', '→');
  element.setAttribute('aria-hidden', 'true');
  return element;
}

function architectureCanvas(markup, file, label) {
  const wrapper = node('div', 'architecture-panel');
  const viewport = node('div', 'architecture-viewport');
  viewport.tabIndex = 0;
  viewport.setAttribute('role', 'region');
  viewport.setAttribute('aria-label', label);
  viewport.innerHTML = markup;
  const footer = node('div', 'architecture-caption');
  footer.append(node('span', '', tr('Scroll the figure on small screens.', '小屏幕可横向滑动查看全图。')));
  const link = node('a', '', tr('Open full-size figure ↗', '打开完整配图 ↗'));
  link.href = './blog/assets/' + file; link.target = '_blank'; link.rel = 'noopener';
  footer.append(link);
  wrapper.append(viewport, footer);
  return wrapper;
}

function preparationFigure(host) {
  if (!host) return;
  host.classList.add('method-figure', 'method-preparation');
  host.replaceChildren(heading('DATA PREPARATION', 'From source records to the next recipe'),
    architectureCanvas(dataArchitectureSVG(), 'data-architecture.svg', 'Data preparation and semantic observation'),
    caption('Source records and synthesized tasks share the same governance and decision schema. Semantic slices describe what each sample teaches; the lower distributions show one recipe from the manuscript.',
      '原始记录与合成任务使用同一套治理流程和决策 Schema。语义切片描述每条样本训练什么能力；下方分布来自原稿中的一份配方示例。'));
}

const stages = [
  {label:'Diagnose', title:['Find a judgment the model has not learned.', '定位模型尚未学会的判断。'], text:['Connect evaluation errors, sample-level learning signals and semantic slices before choosing an intervention.', '先关联评测错误、逐题学习信号与语义切片，再确定需要采取的数据操作。'], asset:'INPUT / Evaluation + learning feedback'},
  {label:'Propose', title:['Make the next data change explicit.', '把下一轮数据调整写成具体方案。'], text:['Specify a target slice, the data operations, the comparison and the capabilities that must be retained.', '明确目标切片、数据操作、比较对象，以及需要保留的已有能力。'], asset:'PROPOSAL / Target slice + recipe + comparison'},
  {label:'Build & test', title:['Execute the experiment in Sandbox.', '在 Sandbox 中执行实验。'], text:['Build a data version, train from the chosen parent model and evaluate the resulting checkpoint.', '构建数据版本，从选定的父模型开展训练，并评测得到的 checkpoint。'], asset:'EXECUTION / Process → train → evaluate'},
  {label:'Retain', title:['Carry the findings into the next proposal.', '把实验发现带回下一轮方案。'], text:['Compare the results and retain useful checkpoints, recipes and findings from unsuccessful branches.', '比较实验结果，保存有效模型、数据配方，以及未成功分支中值得复用的发现。'], asset:'NEXT ROUND / Model + recipe + experimental memory'}
];

function feedbackFigure(host) {
  if (!host) return {render() {}};
  let index = 0;
  let playing = false;
  let visible = false;
  let timer = null;

  function stop() {
    playing = false;
    clearTimeout(timer);
    timer = null;
  }

  function schedule() {
    clearTimeout(timer);
    if (!playing || !visible || document.hidden || reducedMotion.matches) return;
    timer = setTimeout(() => {
      index = (index + 1) % stages.length;
      render();
      schedule();
    }, 3600);
  }

  function choose(next, focus) {
    stop();
    index = next;
    render(focus);
  }

  function render(focus) {
    host.classList.add('method-figure', 'method-feedback');
    host.replaceChildren(heading('AGENTIC DATA ENGINEERING', 'Feedback changes the next recipe'));
    const inputs = node('div', 'mf-feedback-inputs');
    ['Evaluation errors', 'Sample-level KL', 'Semantic slices'].forEach(text => inputs.append(node('span', '', text)));
    inputs.append(node('span', 'mf-feedback-input-note', String.raw`\( \mathrm{CE}(y,p)=H(y)+\mathrm{KL}(y\Vert p) \)`));

    const loop = node('div', 'mf-feedback-loop');
    loop.setAttribute('role', 'group');
    loop.setAttribute('aria-label', tr('Research loop stages', '研发闭环阶段'));
    stages.forEach((stage, i) => {
      const button = node('button', i === index ? 'is-current' : '');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(index === i));
      button.setAttribute('aria-label', tr('Stage ' + (i + 1) + ': ' + stage.label, '阶段 ' + (i + 1) + '：' + stage.label));
      button.append(node('span', 'mf-loop-number', String(i + 1).padStart(2, '0')), node('strong', '', stage.label));
      button.onclick = () => choose(i, i);
      loop.append(button);
      if (i < stages.length - 1) loop.append(arrow());
    });

    const detail = node('div', 'mf-feedback-detail');
    detail.setAttribute('role', 'status');
    detail.setAttribute('aria-live', playing ? 'off' : 'polite');
    detail.append(node('span', 'mf-stage-index', stages[index].asset), node('h4', '', tr(...stages[index].title)), node('p', '', tr(...stages[index].text)));

    const architecture = architectureCanvas(feedbackArchitectureSVG(index), 'feedback-architecture.svg', 'Agentic Data Engineering architecture');

    const controls = node('div', 'mf-controls');
    const play = node('button', 'mf-play', playing ? tr('Pause loop', '暂停闭环') : tr('Play loop', '播放闭环'));
    play.type = 'button';
    play.setAttribute('aria-pressed', String(playing));
    play.disabled = reducedMotion.matches;
    play.onclick = () => {
      if (playing) stop();
      else playing = true;
      render('play');
      schedule();
    };
    const next = node('button', '', tr('Next stage →', '下一阶段 →'));
    next.type = 'button';
    next.onclick = () => choose((index + 1) % stages.length, 'next');
    controls.append(play, next, node('small', '', reducedMotion.matches ? tr('Select a stage to inspect the loop.', '可选择阶段查看闭环内容。') : tr('Four stages, then the next experiment.', '四个阶段之后，进入下一次实验。')));
    host.append(architecture, inputs, loop, detail, controls, caption('KL values are endpoints from recorded training windows. Arrows describe the research workflow, not a measured learning curve.', 'KL 数值来自原稿中记录的训练窗口起止值。箭头表示研发流程，不表示实测学习曲线。'));
    renderMath(host);
    if (typeof focus === 'number') loop.querySelectorAll('button')[focus]?.focus({preventScroll:true});
    if (focus === 'play') play.focus({preventScroll:true});
    if (focus === 'next') next.focus({preventScroll:true});
  }

  const observer = new IntersectionObserver(entries => {
    visible = entries.some(entry => entry.isIntersecting);
    if (!visible && playing) { stop(); render(); }
    else schedule();
  }, {threshold:.12});
  observer.observe(host);
  const visibility = () => { if (document.hidden && playing) { stop(); render(); } };
  const preference = () => { if (reducedMotion.matches) stop(); render(); };
  document.addEventListener('visibilitychange', visibility);
  reducedMotion.addEventListener('change', preference);
  window.addEventListener('pagehide', () => {
    stop(); observer.disconnect();
    document.removeEventListener('visibilitychange', visibility);
    reducedMotion.removeEventListener('change', preference);
  }, {once:true});
  render();
  return {render};
}

const harnessRows = [
  ['Tool execution', 61.67, 60],
  ['Resource allocation', 71.67, 60],
  ['Context & memory', 79.49, 39],
  ['Permission boundaries', 93.22, 59],
  ['Completion & evidence', 98.04, 51],
  ['Uncertainty & recovery', 100.00, 26]
];

function harnessFigure(host) {
  if (!host) return;
  host.classList.add('method-figure', 'method-harness');
  host.replaceChildren(heading('HARNESSJEVBENCH', 'Control decisions, by responsibility', 'Piccolo-27B · Hard task accuracy (%)'));
  const chart = node('div', 'mf-bar-chart');
  chart.setAttribute('role', 'list');
  chart.setAttribute('aria-label', tr('Piccolo-27B accuracy across six Harness responsibilities. Scores are displayed as percentages, with task counts.', 'Piccolo-27B 在六类 Harness 控制职责中的准确率；逐行展示百分比与任务数。'));
  harnessRows.forEach(([label, value, count]) => {
    const row = node('div', 'mf-bar-row');
    row.setAttribute('role', 'listitem');
    row.setAttribute('aria-label', label + ': ' + value.toFixed(2) + '% accuracy; ' + count + ' tasks');
    const name = node('div', 'mf-bar-label');
    name.append(node('strong', '', label), node('small', '', 'n = ' + count));
    const track = node('div', 'mf-bar-track');
    const bar = node('span', 'mf-bar');
    bar.style.transform = 'scaleX(' + value / 100 + ')';
    track.append(bar);
    row.append(name, track, node('span', 'mf-bar-value', value.toFixed(2)));
    chart.append(row);
  });
  const footer = node('div', 'mf-chart-footer');
  footer.append(node('span', '', '295 Hard tasks'), node('span', '', 'Accuracy ↑'), node('span', '', '0 → 100%'));
  host.append(chart, footer, caption('Six responsibility groups cover 295 determinate-answer tasks from the 325-task benchmark design. Hard accuracy uses task-level macro averaging.', '六类职责合计 295 个确定答案任务，来自共 325 个任务的基准设计。Hard 准确率按任务宏平均计分。'));
}

const dataRows = [
  ['Staged data admission', 90],
  ['Processing-plan selection', 90],
  ['Artifact quality', 80],
  ['Information sufficiency', 100],
  ['Verification & disclosure', 80],
  ['Execution control', 60]
];

function dataFigure(host) {
  if (!host) return;
  host.classList.add('method-figure', 'method-data');
  host.replaceChildren(heading('DATAJEVBENCH', 'Decisions throughout the data workflow', '500 tasks · 480 choice + 20 ordered score'));
  const chart = node('div', 'mf-bar-chart mf-task-chart');
  chart.setAttribute('role', 'list');
  chart.setAttribute('aria-label', tr('DataJevBench task composition across six workflow stages. Bars show task counts, not model scores.', 'DataJevBench 六类任务结构；条形长度表示题目数量，不代表模型成绩。'));
  dataRows.forEach(([label, count], i) => {
    const row = node('div', 'mf-bar-row');
    row.setAttribute('role', 'listitem');
    row.setAttribute('aria-label', label + ': ' + count + ' tasks');
    const name = node('div', 'mf-bar-label');
    name.append(node('small', 'mf-task-id', 'D' + (i + 1)), node('strong', '', label));
    const track = node('div', 'mf-bar-track');
    const bar = node('span', 'mf-bar');
    bar.style.transform = 'scaleX(' + count / 100 + ')';
    track.append(bar);
    row.append(name, track, node('span', 'mf-bar-value', String(count)));
    chart.append(row);
  });
  const footer = node('div', 'mf-chart-footer');
  footer.append(node('span', '', 'TASK COMPOSITION'), node('span', '', '0 → 100 tasks / group'));
  const reference = node('div', 'mf-data-reference');
  reference.append(node('span', 'mf-stage-index', 'PICCOLO-27B / SELECTED RESULTS'));
  const results = node('div');
  results.append(node('p', '', 'Artifact quality: 91.25%'), node('p', '', 'Information sufficiency: 81.00%'));
  reference.append(results);
  host.append(chart, footer, reference, caption('Task counts follow the current registered evaluation. The two accuracy figures are selected Piccolo-27B results; the bars above describe the evaluation set.', '题数采用当前登记评测。两项准确率为 Piccolo-27B 的分场景结果，上方条形图展示任务结构。'));
}

export function mountMethodFigures({preparation, feedback, harness, data}) {
  const feedbackView = feedbackFigure(feedback);
  function render() {
    preparationFigure(preparation);
    feedbackView.render();
    harnessFigure(harness);
    dataFigure(data);
  }
  preparationFigure(preparation);
  harnessFigure(harness);
  dataFigure(data);
  return {render};
}
