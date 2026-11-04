#!/usr/bin/env node
// Render the readable English article in-place; content.js remains the copy source.
// Run from any directory: node scripts/render_blog.mjs [--check]
import {readFile, writeFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {article, renderSectionParagraphs} from '../web/blog/content.js';
import {dataArchitectureSVG, dataArchitectureMobileSVG, feedbackArchitectureSVG, researchLoopSVG, researchLoopMobileSVG, evolutionOverviewSVG} from '../web/blog/architecture.js';
import {evolutionMilestones} from '../web/blog/evolution.js';
import katex from '../web/blog/vendor/katex/katex.min.js';

const target = fileURLToPath(new URL('../web/piccolo.html', import.meta.url));
const copy = article.en;
const escape = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);
const prose = text => {
  let result = '', offset = 0;
  for (const match of String(text).matchAll(/\\\(([\s\S]+?)\\\)/g)) {
    result += escape(text.slice(offset, match.index));
    result += katex.renderToString(match[1], {output:'htmlAndMathml', throwOnError:true, trust:false});
    offset = match.index + match[0].length;
  }
  return result + escape(text.slice(offset));
};
const paragraph = text => `<p>${prose(text)}</p>`;
const paragraphs = values => values.map(paragraph).join('\n');

function replaceOnce(html, pattern, replacement, label) {
  const matches = [...html.matchAll(new RegExp(pattern.source, 'g'))];
  if (matches.length !== 1) throw new Error(`Expected one ${label}; found ${matches.length}.`);
  return html.replace(pattern, replacement);
}

// Initial installation only accepts an explicitly empty slot. Subsequent runs
// update bounded marker regions and cannot consume the surrounding figures.
function region(html, name, content, emptySlot) {
  const start = `<!-- blog:${name}:start -->`;
  const end = `<!-- blog:${name}:end -->`;
  const startAt = html.indexOf(start), endAt = html.indexOf(end);
  if (startAt < 0 && endAt < 0) {
    if (!emptySlot) throw new Error(`Missing render region ${name}.`);
    return replaceOnce(html, emptySlot, (_match, opening, closing) => `${opening}${start}\n${content}\n${end}${closing}`, name);
  }
  if (startAt < 0 || endAt < startAt || html.indexOf(start, startAt + start.length) >= 0 || html.indexOf(end, endAt + end.length) >= 0) {
    throw new Error(`Invalid render markers for ${name}.`);
  }
  return html.slice(0, startAt + start.length) + '\n' + content + '\n' + html.slice(endAt);
}

function renderSection(html, section) {
  if (!/^[a-z]+$/.test(section.id)) throw new Error('Unexpected section id.');
  const id = section.id;
  const pattern = new RegExp(`(<section class="research-section" id="${id}">)([\\s\\S]*?)(<\\/section>)`);
  const split = section.leadParagraphs ?? (section.media ? section.paragraphs.length : id === 'decision' ? 0 : 2);
  const sectionParagraphs = (start, end) => renderSectionParagraphs(section, start, end, prose);
  const heading = section.headingLevel === 3 ? 'h3' : 'h2';
  const head = `<span class="section-kicker">${escape(section.kicker)}</span>\n<${heading} class="section-title">${escape(section.title)}</${heading}>\n${sectionParagraphs(0, split)}`;
  const tail = `<div class="section-tail">\n${sectionParagraphs(split)}${section.takeaway ? `\n<p class="section-takeaway">${escape(section.takeaway)}</p>` : ''}\n</div>`;
  return replaceOnce(html, pattern, (_match, opening, existing, closing) => {
    let body = region(existing, `copy-${id}`, head, new RegExp(`(<div class="section-copy" data-section="${id}">)(<\\/div>)`));
    if (!body.includes(`<!-- blog:tail-${id}:start -->`)) {
      if (body.includes('class="section-tail"')) throw new Error(`Unmarked existing tail in ${id}.`);
      body += `\n<!-- blog:tail-${id}:start -->\n${tail}\n<!-- blog:tail-${id}:end -->\n`;
    } else body = region(body, `tail-${id}`, tail);
    return opening + body + closing;
  }, `section ${id}`);
}

export function renderBlog(html) {
  html = html.replace(/<section class="research-section" id="arena">[\s\S]*?<\/section>/g, '');
  const title = `${copy.title} ${copy.subtitle} · AgentScope Research`;
  html = replaceOnce(html, /<title>[^<]*<\/title>/, () => `<title>${escape(title)}</title>`, 'document title');
  html = replaceOnce(html, /<meta name="description" content="[^"]*">/, () => `<meta name="description" content="${escape(copy.deck)}">`, 'description');
  html = replaceOnce(html, /<meta property="og:title" content="[^"]*">/, () => `<meta property="og:title" content="${escape(title)}">`, 'Open Graph title');
  html = replaceOnce(html, /<meta property="og:description" content="[^"]*">/, () => `<meta property="og:description" content="${escape(copy.deck)}">`, 'Open Graph description');
  html = replaceOnce(html, /(<h1 id="articleTitle">)[\s\S]*?(<\/h1>)/, (_match, start, end) => `${start}<span class="piccolo-wordmark"><span class="piccolo-wordmark-text">${escape(copy.title)}</span><img src="./blog/assets/piccolo-wordmark.svg" width="352" height="104" alt="" aria-hidden="true"></span><em>${escape(copy.subtitle)}</em>${end}`, 'article title');
  html = replaceOnce(html, /(<p class="article-deck" id="articleDeck">)[^<]*(<\/p>)/, (_match, start, end) => start + escape(copy.deck) + end, 'article deck');
  html = replaceOnce(html, /(<span id="readTime">)[^<]*(<\/span>)/, (_match, start, end) => start + escape(copy.readTime) + end, 'read time');
  html = region(html, 'intro', paragraphs(copy.intro), /(<div id="articleIntro" class="article-intro">)(<\/div>)/);
  for (const section of copy.sections) html = renderSection(html, section);
  const contents = copy.contents.map((entry, index) => {
    const parent = `<a class="toc-section-title" href="#${escape(entry.id)}"${entry.children ? ' data-toc-group="true"' : ''}><span>${String(index + 1).padStart(2, '0')}</span>${escape(entry.label)}</a>`;
    const children = (entry.children ?? []).map((child, childIndex) => `<a class="toc-subsection" href="#${escape(child.id)}"><span>${index + 1}.${childIndex + 1}</span>${escape(child.label)}</a>`).join('\n');
    return `<div class="toc-group">${parent}${children}</div>`;
  }).join('\n');
  html = region(html, 'contents', contents, /(<nav id="articleContents" aria-label="Article contents">)(<\/nav>)/);
  const directions = copy.futureDirections.map((direction, index) => `<div class="future-item"><span>${String(index + 1).padStart(2, '0')}</span><div><h3>${escape(direction.title)}</h3>${paragraph(direction.text)}</div></div>`).join('\n');
  html = region(html, 'directions', directions, /(<div id="futureDirections" class="future-directions">)(<\/div>)/);
  const sources = copy.sources.map(source => {
    if (!/^https:\/\//.test(source.url)) throw new Error(`Expected an HTTPS resource: ${source.label}.`);
    return `<div class="article-source"><a href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.label)} ↗</a>${paragraph(source.description)}</div>`;
  }).join('\n');
  html = region(html, 'sources', sources, /(<div id="sourceList">)(<\/div>)/);
  html = html.replace(/(<div class="math-display" data-latex="([^"]*)">)[\s\S]*?(<\/div>)/g,
    (_match, opening, latex, closing) => opening + katex.renderToString(latex, {displayMode:true,output:'htmlAndMathml',throwOnError:true,trust:false}) + closing);
  html = replaceOnce(html, /<noscript>[\s\S]*?<\/noscript>/, () => '<noscript><p class="noscript-note">The English article is readable without JavaScript. Enable JavaScript for Chinese text and interactive figures. / 无需 JavaScript 即可阅读英文正文；启用后可切换中文并使用交互图示。</p></noscript>', 'JavaScript fallback');
  return html;
}

const options = process.argv.slice(2);
if (options.some(option => option !== '--check') || options.length > 1) throw new Error('Usage: node scripts/render_blog.mjs [--check]');
const original = await readFile(target, 'utf8');
// Version the whole module graph, not just its entry point. Otherwise a browser
// revisiting an older branch can combine new blog.js with cached dependencies.
const modules = (await readdir(new URL('../web/blog/', import.meta.url)))
  .filter(name => name.endsWith('.js')).sort().map(name => './blog/' + name);
const assetPattern = /((?:src|href)=")(\.\/(?:blog|showcase)\/[a-zA-Z0-9_./-]+\.(?:js|css))(?:\?[^"\s]*)?(")/g;
// The embedded animations pass this same revision to their page, script and style.
const showcaseAssets = ['./showcase/index.html', './showcase/app.js', './showcase/style.css'];
const assets = [...new Set([...modules,...showcaseAssets,...[...original.matchAll(assetPattern)].map(match=>match[2])])].sort();
const payloads = await Promise.all(assets.map(async path => [path,await readFile(new URL('../web/' + path.slice(2), import.meta.url))]));
const digest = createHash('sha256');
for (const [path,bytes] of payloads) digest.update(path).update('\0').update(bytes).update('\0');
const revision = digest.digest('hex').slice(0,16);
const imports = Object.fromEntries(modules.map(path => [path,path+'?v='+revision]));
function renderWithAssets(html) {
  html = renderBlog(html).replace(assetPattern, (_match,prefix,path,suffix) => prefix+path+'?v='+revision+suffix);
  return replaceOnce(html, /<script type="importmap" id="blogModuleImports">[\s\S]*?<\/script>/,
    () => '<script type="importmap" id="blogModuleImports">'+JSON.stringify({imports})+'</script>', 'module import map');
}
const rendered = renderWithAssets(original);
if (renderWithAssets(rendered) !== rendered) throw new Error('Article rendering must be idempotent.');
if (options.includes('--check')) {
  if (original !== rendered) {
    console.error('Blog HTML is out of date. Run node scripts/render_blog.mjs.');
    process.exitCode = 1;
  } else console.log('Blog HTML matches the English source copy.');
} else if (original !== rendered) {
  await writeFile(target, rendered);
  console.log(`Rendered English article: ${target}`);
} else console.log('Blog HTML already matches the English source copy.');

// The index is a separate page; version its small asset set independently.
const indexTarget = new URL('../web/blog.html', import.meta.url);
const indexOriginal = await readFile(indexTarget, 'utf8');
const indexAssetPattern = /((?:src|href)=")(\.\/(?:blog-index\.(?:css|js)|blog\/(?:nav\.css|locale\.js)))(?:\?[^"\s]*)?(")/g;
const indexAssets = [...new Set([...indexOriginal.matchAll(indexAssetPattern)].map(match => match[2]))].sort();
const indexDigest = createHash('sha256');
for (const path of indexAssets) {
  indexDigest.update(path).update('\0').update(await readFile(new URL('../web/' + path.slice(2), import.meta.url))).update('\0');
}
const indexRevision = indexDigest.digest('hex').slice(0,16);
const indexRendered = indexOriginal.replace(indexAssetPattern, (_match, prefix, path, suffix) => prefix + path + '?v=' + indexRevision + suffix);
if (indexOriginal !== indexRendered) {
  if (options.includes('--check')) {
    console.error('Blog index assets are out of date. Run node scripts/render_blog.mjs.');
    process.exitCode = 1;
  } else {
    await writeFile(indexTarget, indexRendered);
    console.log('Versioned Blog index assets.');
  }
}

// Standalone figures remain usable without JavaScript and can be opened at full size.
for (const [file, source] of Object.entries({
  'data-architecture.svg': dataArchitectureSVG(),
  'data-architecture-mobile.svg': dataArchitectureMobileSVG(),
  'feedback-architecture.svg': feedbackArchitectureSVG(),
  'research-loop.svg': researchLoopSVG(),
  'research-loop-mobile.svg': researchLoopMobileSVG(),
  '27b-evolution.svg': evolutionOverviewSVG(evolutionMilestones),
})) {
  const path = new URL('../web/blog/assets/' + file, import.meta.url);
  const expected = source + '\n';
  const current = await readFile(path, 'utf8').catch(error => {
    if (error.code === 'ENOENT') return '';
    throw error;
  });
  if (current === expected) continue;
  if (options.includes('--check')) {
    console.error('Architecture figure is out of date: ' + file);
    process.exitCode = 1;
  } else {
    await writeFile(path, expected);
    console.log('Rendered architecture figure: ' + file);
  }
}
