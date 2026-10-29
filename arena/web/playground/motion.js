/* Quiet, one-time section reveals and positional feedback for result sorting. */
(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const running = new Set();
  const pending = new Set();
  let sortFrame = 0;

  function animate(node, frames, options) {
    if (reduced.matches || document.hidden || typeof node.animate !== 'function') return;
    const animation = node.animate(frames, options);
    running.add(animation);
    const clear = () => running.delete(animation);
    animation.finished.then(clear, clear);
  }

  function cancelAnimations() {
    for (const animation of running) animation.cancel();
    running.clear();
    if (sortFrame) cancelAnimationFrame(sortFrame);
    sortFrame = 0;
  }

  function reveal(node, withMotion = true) {
    if (!pending.has(node)) return;
    pending.delete(node);
    observer?.unobserve(node);
    node.classList.remove('is-motion-pending');
    node.classList.add('is-revealed');
    if (!withMotion) return;
    const opacityOnly = node.dataset.motion === 'fade';
    animate(node, opacityOnly
      ? [{opacity: 0}, {opacity: 1}]
      : [{opacity: 0, transform: 'translateY(14px)'}, {opacity: 1, transform: 'translateY(0)'}], {
      duration: opacityOnly ? 560 : 600,
      delay: Number(node.dataset.motionDelay || 0),
      easing: 'cubic-bezier(.2,.7,.2,1)',
      fill: 'backwards',
    });
  }

  const observer = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) reveal(entry.target);
  }, {threshold: .08, rootMargin: '0px 0px -20px 0px'}) : null;

  const selectors = [
    '.home-intro', '.home-demo-wrap', '.home-section-top', '.home-evidence-copy',
    '.home-comparison', '.home-section-heading', '.home-usecase', '.home-invitation',
  ];
  for (const node of document.querySelectorAll(selectors.join(','))) {
    // Headline coordinates stay stable during the first reveal and page switches.
    node.dataset.motion = node.matches('.home-intro') ? 'fade' : 'rise';
    if (node.matches('.home-demo-wrap')) node.dataset.motionDelay = '100';
    if (node.matches('.home-usecase')) {
      node.dataset.motionDelay = String([...node.parentElement.children].indexOf(node) * 80);
    }
    pending.add(node);
    if (reduced.matches || !observer || document.hidden) reveal(node, false);
    else {
      node.classList.add('is-motion-pending');
      observer.observe(node);
    }
  }

  function rowKey(row) {
    return row.dataset.resultModel || row.dataset.modelSort || row.cells[1]?.textContent.trim();
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('#leaderboardView .lb-sort-button');
    if (!button || reduced.matches || document.hidden) return;
    const table = button.closest('table');
    const body = table?.tBodies[0];
    if (!body) return;
    const before = new Map();
    for (const row of [...body.rows].slice(0, 60)) {
      if (!row.hidden && row.getClientRects().length) before.set(rowKey(row), row.getBoundingClientRect().top);
    }
    cancelAnimations();
    // Sort handlers move the existing rows. Measure after their work, before paint.
    sortFrame = requestAnimationFrame(() => {
      sortFrame = 0;
      if (!table.isConnected || reduced.matches || !table.getClientRects().length) return;
      for (const row of [...body.rows].slice(0, 60)) {
        const previous = before.get(rowKey(row));
        if (previous == null || row.hidden || !row.getClientRects().length) continue;
        const delta = previous - row.getBoundingClientRect().top;
        if (Math.abs(delta) < 1 || Math.abs(delta) > 600) continue;
        animate(row, [{transform: `translateY(${delta}px)`}, {transform: 'translateY(0)'}], {
          duration: 320, easing: 'cubic-bezier(.2,.7,.2,1)',
        });
      }
    });
  }, {capture: true});

  reduced.addEventListener('change', () => {
    if (!reduced.matches) return;
    cancelAnimations();
    for (const node of [...pending]) reveal(node, false);
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) return;
    cancelAnimations();
    for (const node of [...pending]) reveal(node, false);
  });
  window.addEventListener('resize', cancelAnimations, {passive: true});
  window.addEventListener('oneshot:game-ready', cancelAnimations);
  window.JevI18n?.onChange(cancelAnimations);
})();
