/* Shareable destinations from the article. No model requests are initiated. */
(() => {
  const params = new URLSearchParams(location.search);
  const view = params.get('view');
  if (!['blog', 'games', 'leaderboard'].includes(view)) return;
  document.querySelector(`.tabs button[data-tab="${view}"]`)?.click();
  const benchmark = params.get('benchmark');
  if (view === 'leaderboard' && benchmark) window.JevLeaderboard?.open(benchmark);
})();
