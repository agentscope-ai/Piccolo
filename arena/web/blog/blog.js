import {article, renderSectionParagraphs} from './content.js';
import {comparisonGroups, barPercent} from './evidence.js';
import {mountGallery, mountHero} from './gallery.js';
import {mountWorkflowDemo} from './workflow-demos.js';
import {mountBenchmarkRadars} from './benchmark-radars.js';
import {renderMath} from './math.js';

const locale = window.JevI18n;
const tr = (en, zh) => locale.t(en, zh);
const $ = id => document.getElementById(id);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const make = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
};
function button(text, selected, callback) {
  const node = make('button', '', text);
  node.type = 'button';
  node.setAttribute('aria-pressed', String(selected));
  node.onclick = callback;
  return node;
}
function animateChange(node) {
  if (reducedMotion.matches || document.hidden || !node?.animate) return;
  node.animate([{opacity: .4, transform: 'translateY(5px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 240, easing: 'cubic-bezier(.2,.7,.2,1)'});
}

// Text slots change in place so language changes preserve the replay and figure state.
function renderCopy() {
  const expanded = new Set([...document.querySelectorAll('.section-copy>.research-details[open]')]
    .map(node=>node.closest('.research-section').id));
  const copy = article[locale.lang];
  document.title = `${copy.title} ${copy.subtitle} · AgentScope Research`;
  document.querySelector('meta[name="description"]').content = copy.deck;
  const wordmark=make('span','piccolo-wordmark');
  const lettering=make('img');
  lettering.src='./blog/assets/piccolo-wordmark.svg';
  lettering.width=352;lettering.height=104;lettering.alt='';
  lettering.setAttribute('aria-hidden','true');
  wordmark.append(make('span','piccolo-wordmark-text',copy.title),lettering);
  $('articleTitle').replaceChildren(wordmark,make('em','',copy.subtitle));
  $('articleDeck').textContent = copy.deck;
  $('readTime').textContent = copy.readTime;
  $('articleIntro').replaceChildren(...copy.intro.map(text => make('p', '', text)));
  const toc = $('articleContents');
  const active = toc.querySelector('[aria-current="location"]')?.getAttribute('href');
  toc.replaceChildren();
  copy.sections.forEach((section, index) => {
    const slot = document.querySelector(`[data-section="${section.id}"]`);
    slot.replaceChildren(make('span', 'section-kicker', section.kicker), make(section.headingLevel === 3 ? 'h3' : 'h2', 'section-title', section.title));
    const split = section.leadParagraphs ?? (section.media ? section.paragraphs.length : section.id === 'decision' ? 0 : 2);
    const paragraphNodes=(start,end)=>{
      const template=document.createElement('template');
      template.innerHTML=renderSectionParagraphs(section,start,end);
      return [...template.content.childNodes];
    };
    slot.append(...paragraphNodes(0,split));
    if(expanded.has(section.id))slot.querySelector('.research-details')?.setAttribute('open','');
    let tail = document.querySelector(`#${section.id} > .section-tail`);
    if (!tail) { tail = make('div', 'section-tail'); $(section.id).append(tail); }
    tail.replaceChildren(...paragraphNodes(split));
    if (section.takeaway) tail.append(make('p', 'section-takeaway', section.takeaway));
  });
  copy.contents.forEach((entry,index)=>{
    const group=make('div','toc-group');
    const link=make('a','toc-section-title',entry.label);
    link.href='#'+entry.id;
    link.prepend(make('span','',String(index+1).padStart(2,'0')));
    if(entry.children)link.dataset.tocGroup='true';
    if(link.getAttribute('href')===active)link.setAttribute('aria-current','location');
    group.append(link);
    entry.children?.forEach((child,childIndex)=>{
      const nested=make('a','toc-subsection',child.label);
      nested.href='#'+child.id;
      nested.prepend(make('span','',(index+1)+'.'+(childIndex+1)));
      if(nested.getAttribute('href')===active)nested.setAttribute('aria-current','location');
      group.append(nested);
    });
    toc.append(group);
  });
  $('futureDirections').replaceChildren(...copy.futureDirections.map((direction, i) => {
    const item = make('div', 'future-item');
    const body = make('div');
    body.append(make('h3', '', direction.title), make('p', '', direction.text));
    item.append(make('span', '', `0${i + 1}`), body);
    return item;
  }));
  $('sourceList').replaceChildren(...copy.sources.map(source => {
    const item = make('div', 'article-source');
    const link = make('a', '', `${source.label} ↗`);
    link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    item.append(link, make('p', '', source.description));
    return item;
  }));
}

let snapshot = null, benchmarkId = 'jevbench';
const benchmarkScope = {
  jevbench: ['Accuracy · 231 questions', '准确率 · 231 道题'],
  decisionindex: ['Index · 0–100 · grouped by evaluation scope', '指数 · 0–100 · 按评测范围分组'],
  harnessjevbench: ['Task macro accuracy · 295 Hard tasks', '任务宏平均准确率 · 295 个 Hard 任务'],
  datajevbench: ['Accuracy · 500 tasks', '准确率 · 500 道任务'],
};
const benchmarkNotes = {
  jevbench: ['Piccolo refreshed on 2 November, Public-231 protocol; external results retain their original dates. Invalid or missing answers remain in the denominator.', 'Piccolo 于 11 月 2 日复测，采用 Public-231 协议；外部模型保留原日期，无效与缺失答案保留在分母中。'],
  decisionindex: ['Piccolo reports text research evaluations; external models retain official Public results. The two groups have different evaluation scopes and do not form a comparable ranking. Piccolo scores use the variant selected for this benchmark.', 'Piccolo 展示研发文本评测成绩，外部模型保留官方 Public 结果；两组评测范围不同，不作同口径排名。Piccolo 系列采用该评测项所选版本。'],
  harnessjevbench: ['295 Hard tasks / 303 questions, task macro averaging. Soft-distribution scores are evaluated separately.', '295 个 Hard 任务 / 303 个问题，按任务宏平均计分；软分布单独评估。'],
  datajevbench: ['All 500 tasks remain in the denominator. Original probabilities use a sum tolerance of 1e-3, without renormalization.', '全部 500 道任务保留在分母中；原始概率和容差为 1e-3，不做重新归一化。'],
};
function renderBenchmarks(focus = false) {
  if (!snapshot) return;
  const host = $('benchmarkFigure'); host.setAttribute('aria-busy', 'false'); host.replaceChildren();
  const tabs = make('div', 'benchmark-tabs');
  tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', tr('Select a benchmark', '选择评测基准'));
  snapshot.benchmarks.forEach(benchmark => tabs.append(button(benchmark.title.replace(' Public', ''), benchmark.id === benchmarkId, () => { benchmarkId = benchmark.id; renderBenchmarks(true); })));
  const benchmark = snapshot.benchmarks.find(item => item.id === benchmarkId);
  const groups = comparisonGroups(benchmark);
  const rows = groups.flatMap(group => group.rows);
  const scored = rows.filter(row => barPercent(row, benchmark.scale) !== null).length;
  const heading = make('div', 'benchmark-heading'); const copy = make('div');
  copy.append(make('h3', '', `${benchmark.title} v${String(benchmark.version).replace(/^v/i, '')}`), make('p', '', tr(...benchmarkScope[benchmark.id])));
  heading.append(copy, make('span', '', tr(`${scored} / ${rows.length} models scored`, `${scored} / ${rows.length} 个模型有成绩`)));
  const charts = make('div', 'benchmark-groups');
  groups.forEach(group => {
   const list = make('ol', 'article-chart');
   if (group.id !== 'comparable') {
    const labels = {
      'research-text': ['Piccolo · Text research evaluation', 'Piccolo · 研发文本评测'],
      public: ['External models · Public', '外部模型 · Public'],
      unspecified: ['Evaluation scope not reported', '评测范围未报告'],
    };
    const title = tr(...(labels[group.id] ?? labels.unspecified));
    charts.append(make('h4', 'benchmark-scope-title', title));
    list.setAttribute('aria-label', title);
   }
   group.rows.forEach(row => {
    const percent = barPercent(row, benchmark.scale);
    const own = row.model_key === 'blink-27b-1028', family = /^Piccolo/.test(row.model);
    const li = make('li', own ? 'chart-own' : family ? 'chart-family' : '');
    const publisher = window.JevModelLogo?.resolve({model_id: row.model_key, model_name: row.model});
    const identity = make(publisher?.url ? 'a' : 'span', 'chart-identity');
    if (publisher?.url) {
      identity.href = family ? 'https://github.com/agentscope-ai/Piccolo' : publisher.url; identity.target = '_blank'; identity.rel = 'noopener noreferrer';
      identity.title = `${publisher.name} · ${tr('Official page', '官方页面')}`;
    }
    if (publisher?.logo) { const image = make('img'); image.src = publisher.logo; image.width = 18; image.height = 18; image.alt = ''; image.loading = 'lazy'; identity.append(image); }
    identity.append(make('span', '', row.model));
    const track = make('span', 'chart-track'); track.setAttribute('aria-hidden', 'true');
    if (percent !== null) { const fill = make('span', 'chart-fill'); fill.style.display = 'block'; fill.style.width = `${percent}%`; track.append(fill); }
    else track.append(make('span', 'chart-empty', tr('Not reported', '暂无成绩')));
    const displayScore = benchmark.id === 'decisionindex' && percent !== null ? row.score.toFixed(2) : row.score_display;
    const score = make('span', 'chart-score', percent === null ? '—' : displayScore);
    if (percent === null) li.setAttribute('aria-label', tr(`${row.model}: result not reported`, `${row.model}：暂无成绩`));
    li.append(identity, track, score); list.append(li);
   });
   charts.append(list);
  });
  const note = make('p', 'benchmark-notes', tr(...benchmarkNotes[benchmark.id]));
  const link = make('a', 'figure-link', tr('Open full leaderboard ↗', '查看完整榜单 ↗'));
  link.href = `https://decisionplayground.agentscope.io/?view=leaderboard&benchmark=${benchmark.id}`;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  const original = make('a', 'figure-link', tr('Original benchmark ↗', '原始评测与榜单 ↗'));
  original.href = {jevbench: 'https://github.com/fstandhartinger/jevbench', decisionindex: 'https://huggingface.co/spaces/multimodalart/jev-decision-index', harnessjevbench: 'https://github.com/agentscope-ai/HarnessJevBench', datajevbench: 'https://github.com/datajuicer/DataJevBench'}[benchmark.id];
  original.target = '_blank'; original.rel = 'noopener noreferrer';
  host.append(tabs, heading, charts, note, link, original);
  $('benchmarkCaption').textContent = article[locale.lang].benchmarkNotes;
  if (focus) { [...tabs.children].find(node => node.getAttribute('aria-pressed') === 'true')?.focus({preventScroll: true}); animateChange(charts); }
}
async function loadBenchmarks() {
  const host = $('benchmarkFigure'); host.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('./blog/benchmark-snapshot.json', {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw Error('snapshot unavailable');
    const next = await response.json();
    if (!Array.isArray(next.benchmarks) || next.benchmarks.length !== 4 || next.benchmarks.some(benchmark => !Array.isArray(benchmark.rows) || !benchmarkScope[benchmark.id])) throw Error('invalid snapshot');
    snapshot = next; renderBenchmarks();
  } catch {
    host.setAttribute('aria-busy', 'false'); host.replaceChildren(make('p', 'figure-loading', tr('The benchmark snapshot is unavailable.', '评测快照暂时无法读取。')));
    host.append(button(tr('Try again', '重新加载'), false, loadBenchmarks));
  }
}

function render() { renderCopy(); renderBenchmarks(); locale.translate(); renderMath(); }
render();
loadBenchmarks();
locale.onChange(render);
const radars=mountBenchmarkRadars({harness:$('harnessFigure'),data:$('dataFigure')});
const features=[mountGallery($('decisionGallery'),{gamesOnly:true}),mountGallery($('harnessRecording'),{ids:['qwenpaw-audit']}),mountGallery($('dataRecording'),{ids:['data-judge']}),mountWorkflowDemo($('harnessDemo'),'harness'),mountWorkflowDemo($('dataDemo'),'data'),radars];
locale.onChange(()=>{features.forEach(feature=>feature.render());renderMath();});
renderMath();
document.addEventListener('DOMContentLoaded',()=>renderMath(),{once:true});
mountHero($('heroRecording'));
document.addEventListener('visibilitychange',()=>{if(document.hidden)document.querySelectorAll('.method-media video').forEach(video=>video.pause());});
const videoObserver=new IntersectionObserver(entries=>{
  for(const entry of entries)if(!entry.isIntersecting)entry.target.pause();
});
function observeResearchVideos(){
  videoObserver.disconnect();
  document.querySelectorAll('.method-media video').forEach(video=>videoObserver.observe(video));
}
observeResearchVideos();
locale.onChange(observeResearchVideos);

// Intersection observers keep the directory useful without a continuous scroll handler.
const sections = [$('articleIntro'),...document.querySelectorAll('.research-section')];
const observer = new IntersectionObserver(entries => {
  const entry = entries.filter(item => item.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (!entry) return;
  document.querySelectorAll('#articleContents a').forEach(link => {
    if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  $('readingProgress').style.transform = `scaleX(${(sections.indexOf(entry.target) + 1) / sections.length})`;
}, {rootMargin: '-10% 0px -65% 0px', threshold: 0});
sections.forEach(section => observer.observe(section));
window.addEventListener('pagehide',()=>{observer.disconnect();videoObserver.disconnect();},{once:true});
