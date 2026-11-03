/* The publication index shares the site's language preference. */
(() => {
  // Links shared before the article received its own URL keep their section.
  const legacySections = new Set([
    'articleBody', 'articleIntro', 'decision', 'evidence', 'method',
    'preparation', 'rsi', 'learning', 'harness', 'data', 'arena', 'future',
    'articleSources', 'trainingSchema', 'modelEvolution',
    'method-video', 'method-figure-1', 'method-figure-2', 'method-figure-3',
  ]);
  if (legacySections.has(location.hash.slice(1))) {
    const article = new URL('./piccolo.html', location.href);
    article.search = location.search;
    article.hash = location.hash;
    location.replace(article.href);
    return;
  }
  const updateMetadata = () => {
    document.title = window.JevI18n.t('Blog · Piccolo Research', 'Blog · Piccolo 研究');
  };
  updateMetadata();
  window.JevI18n.onChange(updateMetadata);
})();
