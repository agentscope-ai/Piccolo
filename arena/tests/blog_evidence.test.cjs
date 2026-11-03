/* The article snapshot must remain an honest projection of the registered evidence. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {pathToFileURL} = require('node:url');

const root = path.resolve(__dirname, '..');
const read = name => fs.readFile(path.join(root, name), 'utf8');
const json = async name => JSON.parse(await read(name));
// These browser modules have no dependencies; a data URL keeps this CJS test
// independent of a package-level module-mode setting.
const moduleFrom = async name => import('data:text/javascript;base64,' + Buffer.from(await read(name)).toString('base64'));
const setup = Promise.all([
  json('web/blog/benchmark-snapshot.json'),
  moduleFrom('web/blog/evidence.js'),
  moduleFrom('web/blog/content.js'),
]);
const benchmarkIds = ['jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench'];

test('the Blog index, release article and local assets remain navigable and packaged', async () => {
  const index = await read('web/blog.html');
  const article = await read('web/piccolo.html');
  assert.match(index, /href="\.\/piccolo\.html"/);
  assert.doesNotMatch(index, /id="articleTitle"/);
  assert.match(article, /id="articleTitle"/);
  assert.match(article, /class="article-back" href="\.\/blog\.html"/);
  for (const [file, html] of [['web/blog.html', index], ['web/piccolo.html', article]]) {
    for (const [, href] of html.matchAll(/(?:src|href)="(\.\/[^"#?]+)(?:[?#][^"]*)?"/g)) {
      await fs.access(path.resolve(root, path.dirname(file), href));
    }
  }
  const release = await read('scripts/build_release.py');
  for (const asset of ['web/blog.html','web/piccolo.html','web/blog-index.css','web/blog-index.js']) {
    assert.ok(release.includes("'" + asset + "'"), asset + ' must be required in the release');
  }
});

test('cached entry points cannot resolve unversioned Blog module dependencies', async () => {
  const html = await read('web/piccolo.html');
  const imports = JSON.parse(html.match(/<script type="importmap" id="blogModuleImports">([\s\S]*?)<\/script>/)[1]).imports;
  const base = 'https://example.com/release/';
  const mapped = new Map(Object.entries(imports).map(([key,value]) => [new URL(key,base).href,new URL(value,base).href]));
  const entry = new URL(html.match(/<script type="module" src="([^"]+)"/)[1],base);
  const revision = entry.searchParams.get('v');
  assert.ok(revision);
  for (const [key,value] of Object.entries(imports)) {
    assert.equal(new URL(value,base).searchParams.get('v'),revision,key);
    const code = await read('web/' + key.replace(/^\.\//,''));
    for (const match of code.matchAll(/\b(?:from\s*|import\s*)['"](\.[^'"]+)['"]/g)) {
      const resolved = new URL(match[1],new URL(key,base)).href;
      assert.ok(mapped.has(resolved),key + ' must version ' + match[1]);
    }
  }
  assert.ok(imports['./blog/content.js']);
  assert.ok(imports['./blog/gallery.js']);
  assert.doesNotMatch(html,/<details[^>]+benchmark-complete/);
});

test('benchmark overview keeps the correct cohort, closest external peer and score units', async () => {
  const {benchmarkSummary} = await import(pathToFileURL(path.join(root,'web/blog/benchmark-overview.js')).href);
  const [snapshot] = await setup;
  // Decision Index mixes reported research and official Public scopes.
  // Its groups are checked separately below, without a cross-scope ranking.
  const expected = [[1,11,'2.16'],null,[1,11,'2.03'],[1,11,'1.00']];
  snapshot.benchmarks.forEach((benchmark,index) => {
    if (!expected[index]) return;
    const summary = benchmarkSummary(benchmark);
    assert.deepEqual([summary.rank,summary.scored,summary.delta.toFixed(2)],expected[index]);
    assert.doesNotMatch(summary.peer.model,/^Piccolo/);
  });
  const rows = [
    {model_key:'blink-27b-1028',model:'Piccolo-27B',score:0.8,status:'complete'},
    {model_key:'peer',model:'Peer',score:0.80001,status:'complete'},
    {model_key:'missing',model:'Missing',score:null,status:'pending'},
    {model_key:'invalid',model:'Invalid',score:2,status:'complete'},
  ];
  const summary = benchmarkSummary({scale:1,rows});
  assert.equal(summary.rank,2);
  assert.equal(summary.scored,2);
  assert.equal(summary.tied,false);
  assert.ok(summary.delta<0);
  assert.equal(benchmarkSummary({scale:1,rows:rows.slice(1)}),null);
});

test('the frozen article edition supports its stated scores, scope and cohort rankings', async () => {
  const [snapshot, {rankedRows}] = await setup;
  // This is a dated research article. Future live leaderboard updates must not
  // silently rewrite the evidence used by this edition.
  const facts = {
    jevbench: {version: '1.2', scale: 1, own: 0.922077922077922, rank: 1},
    decisionindex: {version: '0.3', scale: 100, own: 68.59, rank: null},
    harnessjevbench: {version: 'V0.5', scale: 1, own: 0.8440677966101695, rank: 1},
    datajevbench: {version: 'V0.5', scale: 1, own: 0.826, rank: 1},
  };
  assert.equal(snapshot.snapshot_date, '2026-11-02');
  assert.deepEqual(snapshot.benchmarks.map(item => item.id), benchmarkIds);
  for (const benchmark of snapshot.benchmarks) {
    const expectedFact = facts[benchmark.id];
    assert.equal(benchmark.version, expectedFact.version);
    assert.equal(benchmark.scale, expectedFact.scale);
    assert.equal(benchmark.rows.length, 11);
    assert.equal(new Set(benchmark.rows.map(row => row.model_key)).size, 11);
    const own = benchmark.rows.find(row => row.model_key === 'blink-27b-1028');
    assert.equal(own.model, 'Piccolo-27B');
    assert.equal(own.score, expectedFact.own);
    if (expectedFact.rank !== null) {
      assert.equal(rankedRows(benchmark).findIndex(row => row.model_key === own.model_key) + 1, expectedFact.rank);
    }
    for (const row of benchmark.rows) {
      assert.ok(row.model && row.model_key);
      if (row.score !== null) {
        assert.equal(row.status, 'complete');
        assert.ok(Number.isFinite(row.score) && row.score >= 0 && row.score <= benchmark.scale);
      }
      const expected = row.score === null ? '—' : benchmark.scale === 100
        ? `${row.score.toFixed(2)} / 100` : `${(row.score * 100).toFixed(2)}%`;
      assert.equal(row.score_display, expected, `${benchmark.id}/${row.model_key} display`);
    }
  }
});

test('Decision Index separates research and Public scopes without dropping any model', async () => {
  const [snapshot, {comparisonGroups}] = await setup;
  for (const benchmark of snapshot.benchmarks) {
    const groups = comparisonGroups(benchmark);
    const flattened = groups.flatMap(group => group.rows);
    assert.deepEqual(flattened.map(row => row.model_key).sort(), benchmark.rows.map(row => row.model_key).sort());
    if (benchmark.id === 'decisionindex') {
      assert.deepEqual(groups.map(group => [group.id, group.rows.length]), [['research-text',3],['public',8]]);
      for (const group of groups) {
        assert.ok(group.rows.every(row => row.evaluation_scope === group.id));
        const scores = group.rows.filter(row => row.status === 'complete' && row.score !== null).map(row => row.score);
        assert.deepEqual(scores, [...scores].sort((a,b) => b-a));
      }
      assert.ok(groups[0].rows.every(row => /^Piccolo-/.test(row.model)));
      assert.ok(groups[1].rows.every(row => !/^Piccolo-/.test(row.model)));
      assert.equal(groups[1].rows.filter(row => row.score === null).length,4);
    } else {
      assert.deepEqual(groups.map(group => group.id), ['comparable']);
    }
  }
});

test('missing Decision Index results remain missing rather than zero or artificial bars', async () => {
  const [snapshot, {rankedRows, barPercent}] = await setup;
  const benchmark = snapshot.benchmarks.find(item => item.id === 'decisionindex');
  const ranked = rankedRows(benchmark);
  assert.equal(ranked.filter(row => row.status === 'complete' && Number.isFinite(row.score)).length, 7);
  const missing = ranked.filter(row => row.score === null);
  assert.equal(missing.length, 4);
  assert.deepEqual(ranked.slice(-4).map(row => row.model_key), missing.map(row => row.model_key));
  for (const row of missing) {
    assert.equal(row.score_display, '—');
    assert.equal(barPercent(row, benchmark.scale), null);
  }
});

test('zero is a valid completed result while non-finite and pending values cannot outrank it', async () => {
  const [, {rankedRows, barPercent}] = await setup;
  const rows = [
    {model_key: 'pending', score: 90, status: 'pending'},
    {model_key: 'zero', score: 0, status: 'complete'},
    {model_key: 'unknown', score: null, status: 'pending'},
    {model_key: 'bad', score: NaN, status: 'complete'},
    {model_key: 'winner', score: 0.82, status: 'complete'},
  ];
  const before = rows.map(row => ({...row}));
  assert.deepEqual(rankedRows({rows}).slice(0, 2).map(row => row.model_key), ['winner', 'zero']);
  assert.deepEqual(rows, before, 'sorting must not mutate the source evidence');
  assert.equal(barPercent(rows[1], 1), 0);
  assert.equal(barPercent(rows[0], 100), null);
  assert.equal(barPercent(rows[3], 1), null);
  assert.equal(barPercent(rows[4], 0), null);
  assert.equal(barPercent({status: 'complete', score: 68.29}, 100), 68.29);
});

test('both article languages cover the same complete sections, sources and four future directions', async () => {
  const [, , {article}] = await setup;
  const ids = ['decision', 'demogames', 'demoharness', 'demodata', 'evidence', 'method', 'preparation', 'rsi', 'learning', 'harness', 'data', 'arena', 'future'];
  for (const lang of ['en', 'zh']) {
    const copy = article[lang];
    assert.deepEqual(copy.sections.map(section => section.id), ids);
    assert.equal(copy.futureDirections.length, 4);
    assert.match(copy.readTime, /\d+.*\d+.*(?:min|分钟)/);
    for (const section of copy.sections) {
      assert.ok(section.title && section.kicker);
      assert.equal(typeof section.takeaway, 'string');
      assert.ok(section.paragraphs.length >= (section.id === 'future' ? 0 : ['method', 'decision', 'demogames'].includes(section.id) ? 1 : 2));
      assert.ok(section.paragraphs.every(paragraph => paragraph.length > 30));
      if (lang === 'zh' && section.paragraphs.length) assert.match(section.paragraphs.join(''), /[\u4e00-\u9fff]/);
    }
    const directions = copy.futureDirections.map(item => item.title + ' ' + item.text);
    const concepts = lang === 'en' ? [/RSI/, /multimodal|cross.modal|embodied/i, /time|trajector/i, /System 1/] : [/RSI/, /多模态|跨模态|具身/, /长程|跨步骤/, /System 1/];
    concepts.forEach((concept, index) => assert.match(directions[index], concept));
  }
  assert.deepEqual(article.en.sources.map(source => source.url), article.zh.sources.map(source => source.url));
});

test('updated release scores are presented as per-benchmark series results in both languages', async () => {
  const [, , {article}] = await setup;
  for (const lang of ['en', 'zh']) {
    const copy = article[lang];
    const evidence = copy.sections.find(section => section.id === 'evidence').paragraphs.join(' ');
    for (const value of ['92.21%', '68.59', '84.41%', '82.60%']) assert.ok(evidence.includes(value), `${lang}: ${value}`);
    const learning = copy.sections.find(section => section.id === 'learning').paragraphs.join(' ');
    assert.match(learning, /68\.59/);
    assert.match(copy.benchmarkNotes, lang === 'en' ? /selected variants/ : /所选版本/);
    assert.match(copy.benchmarkNotes, /Public/);
    assert.match(copy.benchmarkNotes, lang === 'en' ? /research/i : /研发/);
    assert.match(learning, lang === 'en' ? /full.suite/i : /全集/);
    assert.match(copy.benchmarkNotes, /0[–-]100/);
  }
});

test('article markup covers every translated section', async () => {
  const [, , {article}] = await setup;
  const html = await read('web/piccolo.html');
  for (const {id} of article.en.sections) {
    assert.ok(html.includes(`id="${id}"`));
    assert.ok(html.includes(`data-section="${id}"`));
  }
});

test('the public article contains no internal source URLs, signed tokens or retired brand text', async () => {
  const entries = await fs.readdir(path.join(root, 'web/blog'), {withFileTypes:true});
  const files = ['web/blog.html', 'web/piccolo.html', 'web/blog-index.js', ...entries.filter(entry => entry.isFile()).map(entry => 'web/blog/' + entry.name)];
  for (const file of files) {
    const text = await read(file);
    assert.doesNotMatch(text, /intranetproxy|yuque\.alibaba|_dt_(?:ac|sig|ts)=|\/Users\/towardsun\//i, file);
    assert.doesNotMatch(text, /\b(?:Blink|OneShot)\b/, file);
  }
});

test('all original source media retain their imported bytes and animated GIF frames', async () => {
  const manifest = await json('docs/blog-assets.json');
  assert.equal(manifest.assets.length, 16);
  assert.equal(manifest.assets.filter(asset => asset.path.endsWith('.gif')).length, 9);
  for (const asset of manifest.assets) {
    assert.ok(asset.path.startsWith('web/blog/assets/'));
    const bytes = await fs.readFile(path.join(root, asset.path));
    assert.equal(bytes.length, asset.bytes, asset.name);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), asset.sha256, asset.name);
    if (asset.path.endsWith('.gif')) {
      assert.match(bytes.subarray(0, 6).toString(), /^GIF8[79]a$/);
      assert.ok(asset.frames > 1, asset.name + ' must remain animated');
    }
  }
});

test('the 27B trajectory keeps independent comparisons separate from family results', async () => {
  const {evolutionMilestones} = await moduleFrom('web/blog/evolution.js');
  assert.deepEqual(evolutionMilestones.map(point => point.score), [
    48.91, 56.68, 59.09, 60.92, 62.39, 63.84, 65.47, 66.65, 67.44, 68.33, 68.59
  ]);
  assert.ok(!evolutionMilestones.some(point => [65.05, 66.19, 62.78, 63.11].includes(point.score)));
  for (const language of ['en', 'zh']) {
    const {article} = await moduleFrom('web/blog/content.js');
    const learning = article[language].sections.find(section => section.id === 'learning');
    const text = learning.paragraphs.join(' ');
    for (const value of ['65.05', '66.19', '62.78', '63.11']) assert.ok(text.includes(value));
    const supporting = learning.paragraphs.join(' ');
    for (const value of ['9B','4B','46.78','60.86','39.94','58.00','70.45','73.41','68.19','73.03']) assert.ok(supporting.includes(value), language + ': ' + value);
  }
});

test('the contents follow the release structure with grouped methods and built-in benchmarks', async () => {
  const [, , {article}] = await setup;
  for (const language of ['en', 'zh']) {
    const copy = article[language];
    assert.deepEqual(copy.contents.map(entry => entry.id), ['articleIntro','decision','evidence','method','harness','future']);
    assert.deepEqual(copy.contents.find(entry => entry.id === 'decision').children.map(entry => entry.id), ['demogames','demoharness','demodata']);
    assert.deepEqual(copy.contents.find(entry => entry.id === 'method').children.map(entry => entry.id), ['preparation','rsi','learning']);
    assert.deepEqual(copy.contents.find(entry => entry.id === 'harness').children.map(entry => entry.id), ['harness','data','arena']);
    const method = copy.sections.find(section => section.id === 'method');
    assert.equal(method.headingLevel, 2);
    assert.match((await read('web/piccolo.html')), /id="method-figure-3"/);
    const children = copy.contents.find(entry => entry.id === 'method').children;
    for (const [index, child] of children.entries()) {
      const section = copy.sections.find(section => section.id === child.id);
      assert.equal(section.headingLevel, 3);
      assert.equal(section.title, '4.' + (index + 1) + ' ' + child.label);
      const {renderSectionParagraphs} = await moduleFrom('web/blog/content.js');
      assert.match(renderSectionParagraphs(section), /<h4>/);
      assert.doesNotMatch(renderSectionParagraphs(section), /<h3>/);
    }
  }
});

test('public label examples expose only hard and soft supervision', async () => {
  const examples = await json('web/blog/label-examples.json');
  const {labelVariants} = await moduleFrom('web/blog/schema-data.js');
  assert.equal(examples.length, 6);
  for (const primitive of ['choice','score','noul']) {
    assert.deepEqual(Object.keys(labelVariants[primitive]), ['hard','soft']);
    assert.equal(examples.filter(record => record.questions.judgment.type === primitive).length, 2);
  }
  assert.ok(examples.every(record => ['hard','soft'].includes(record.labels.judgment.label_type)));
});

test('all article LaTeX compiles and the HTML contains pre-rendered accessible formulas', async () => {
  const katex = require('../web/blog/vendor/katex/katex.min.js');
  const [, , {article}] = await setup;
  let count = 0;
  for (const language of ['en','zh']) {
    const text = [...article[language].intro,...article[language].sections.flatMap(section => section.paragraphs)].join(' ');
    for (const match of text.matchAll(/\\\(([\s\S]+?)\\\)/g)) {
      const result = katex.renderToString(match[1], {throwOnError:true,trust:false,output:'htmlAndMathml'});
      assert.match(result, /katex-mathml/);
      assert.match(result, /katex-html/);
      count++;
    }
  }
  assert.ok(count >= 12);
  const html = await read('web/piccolo.html');
  assert.match(html, /class="katex"/);
  assert.match(html, /<math /);
  assert.doesNotMatch(html, /class="katex-error"/);
});

test('radar profiles use six measured accuracy axes and retain their weighted totals', async () => {
  const {benchmarkProfiles} = await moduleFrom('web/blog/benchmark-profiles.js');
  for (const [key, expectedTasks] of [['harness',295],['data',500]]) {
    const profile = benchmarkProfiles[key];
    assert.equal(profile.axes.length, 6);
    assert.equal(profile.axes.reduce((sum,axis)=>sum+axis.samples,0),expectedTasks);
    assert.ok(profile.defaultVisible.length>2);
    assert.ok(profile.defaultVisible.every(id=>profile.models.some(model=>model.id===id)));
    assert.equal(profile.models.length,11);
    const bytes = await fs.readFile(path.join(root,profile.source));
    assert.equal(createHash('sha256').update(bytes).digest('hex'),profile.sourceSha256);
    for (const model of profile.models) {
      assert.equal(model.values.length,6);
      assert.ok(model.values.every(value=>value===null||(Number.isFinite(value)&&value>=0&&value<=1)));
      if (model.values.every(value=>value!==null)) {
        const weighted = model.values.reduce((sum,value,index)=>sum+value*profile.axes[index].samples,0)/expectedTasks;
        assert.ok(Math.abs(weighted-model.metrics.accuracy)<1e-10, key+'/'+model.id);
      }
    }
  }
});


test('Method retains source prose, original figures and video, and omits the removed example', async () => {
  const {article, renderSectionParagraphs, renderInline} = await moduleFrom('web/blog/content.js');
  const expectedLinks = [
    'https://github.com/datajuicer/data-juicer',
    'https://github.com/datajuicer/agentic-data-engineering',
    'https://github.com/datajuicer/data-juicer-sandbox',
  ];
  for (const language of ['en','zh']) {
    const sections = article[language].sections.filter(section => section.media);
    const media = sections.flatMap(section => section.media);
    assert.deepEqual(media.map(item => item.id), ['method-video','method-figure-1','method-figure-2','method-figure-3']);
    assert.ok(media.filter(item=>item.kind==='image').every(item => item.src.endsWith('.png')));
    const rendered = sections.map(section => renderSectionParagraphs(section)).join('\n');
    for (const url of expectedLinks) assert.ok(rendered.includes('href="' + url + '"'), language + ': ' + url);
    assert.equal((rendered.match(/class="method-media-placeholder"/g) ?? []).length, 0);
    assert.equal((rendered.match(/<img /g) ?? []).length, 3);
    assert.doesNotMatch(rendered, /src=""/);
    assert.doesNotMatch(rendered, /id="trainingSchema"/);
    for (const item of media) {
      for (const src of [item.src,item.mobileSrc].filter(Boolean)) await fs.access(path.join(root,'web',src.replace(/^\.\//,'')));
    }
    assert.match(rendered, /scope="col"/);
    assert.equal(sections.find(section => section.id === 'rsi').table.rows.length, 4);
    assert.doesNotMatch(rendered, /WIP|TODO/);
    const prep = sections.find(section => section.id === 'preparation');
    const method = sections.find(section => section.id === 'method');
    assert.match(prep.paragraphs.join(' '), /13/);
    assert.doesNotMatch(method.paragraphs.join(' '), /6,300/);
    assert.match(method.media[0].caption, /6,300/);
    assert.match(method.media[0].caption, language === 'en' ? /[Aa]ll exploratory experiments/ : /全部探索实验/);
    assert.doesNotMatch(JSON.stringify(article[language]), /FlexDM|1000luca|Under Flex|Flex 双向/);
    const learning = sections.find(section => section.id === 'learning');
    assert.match(learning.paragraphs.join(' '), /65\.05[\s\S]*66\.19/);
    assert.doesNotMatch(learning.paragraphTitles.join(' '), /Ongoing exploration|探索中：/);
    for (const section of sections.filter(s => s.details)) {
      const rendered = renderSectionParagraphs(section, 0, section.paragraphs.length)
        + renderSectionParagraphs(section, section.paragraphs.length);
      assert.equal((rendered.match(/<details /g) ?? []).length, 1);
      assert.match(rendered, /<summary>/);
    }
  }
  const html = await read('web/piccolo.html');
  assert.match(html, /<video[^>]+method-piccolo-evolution\.webm/);
  assert.doesNotMatch(html, /id="benchmarkOverview"|id="trainingSchema"/);
  assert.ok(html.indexOf('id="method-figure-3"')>html.indexOf('id="learning"'));
  assert.match(html, /150\+/);
  assert.match(html, /method-model-evolution\.png/);
  assert.equal(renderInline('<img onerror="bad">'), '&lt;img onerror=&quot;bad&quot;&gt;');
  assert.equal(renderInline('A **key finding** and *scope note*.'), 'A <strong>key finding</strong> and <em>scope note</em>.');
  assert.equal(renderInline('**<script>**'), '<strong>&lt;script&gt;</strong>');
  assert.doesNotMatch(renderInline('[unsafe](javascript:alert)'), /<a /);
  assert.match(renderInline('[safe](https://example.com/)'), /rel="noopener noreferrer"/);
  const section = article.en.sections.find(section => section.id === 'preparation');
  const ready = {...section, media: [{...section.media[0], src:'./blog/assets/final-evolution.png'}]};
  assert.match(renderSectionParagraphs(ready), /<img src="\.\/blog\/assets\/final-evolution.png"/);
});

test('final Method assets retain their documented bytes and are included in source packaging', async () => {
  const manifest = await json('docs/blog-assets.json');
  assert.equal(manifest.method_assets.length, 4);
  for (const asset of manifest.method_assets) {
    const bytes = await fs.readFile(path.join(root, asset.path));
    assert.equal(bytes.length, asset.bytes);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), asset.sha256);
  }
  assert.ok((await read('MANIFEST.in')).includes('*.webm'));
});

test('November release synchronizes the selected series scores across public surfaces', async () => {
  const [snapshot] = await setup;
  const expected = {
    'blink-4b-1028': [201/231,58,183/295,353/500],
    'blink-9b-1028': [207/231,60.86,203/295,347/500],
    'blink-27b-1028': [213/231,68.59,249/295,413/500],
  };
  for (const [index,id] of benchmarkIds.entries()) {
    const registered=await json('leaderboard/'+id+'.json');
    for (const [model,values] of Object.entries(expected)) {
      const row=registered.rows.find(r=>r.model_id===model);
      const display=snapshot.benchmarks.find(b=>b.id===id).rows.find(r=>r.model_key===model);
      assert.ok(Math.abs(row.score-values[index])<1e-12,id+'/'+model);
      assert.equal(display.score,row.score);
      assert.equal(display.checkpoint_id,undefined);
      assert.ok(!row.notes.some(note=>/Checkpoint:|Evaluated checkpoint:|input profile:|Owner-confirmed/.test(note)));
    }
  }
});
