/* Shared model connection; game-local environment beside the active board. */
(() => {
  'use strict';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const view = document.getElementById('gamesView');
  const panel = view.querySelector('.playground-panel');
  const seed = document.getElementById('playSeedTools');
  const connections = view.querySelector('.playground-connections');
  const tools = view.querySelector('.play-library-tools');
  const picker = document.getElementById('gamePicker');
  let games = [], current = '', disabled = false, category = null;
  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }
  const bar = make('div', 'play-workspace-bar');
  bar.id = 'playWorkspaceBar';
  const switcher = make('div', 'play-workspace-switcher');
  const gameLabel = make('label', 'workspace-label');
  gameLabel.htmlFor = 'playQuickGame';
  const categoryField = make('div', 'workspace-category-field');
  const categoryLabel = make('label', 'workspace-label');
  categoryLabel.htmlFor = 'playGameCategory';
  const categories = make('select');
  categories.id = 'playGameCategory';
  categoryField.append(categoryLabel, categories);
  const gameField = make('div', 'workspace-game-field');
  const switchRow = make('div', 'workspace-switch-row');
  const select = make('select');
  select.id = 'playQuickGame';
  select.disabled = true;
  const browse = make('button', 'workspace-browse');
  browse.id = 'playBrowseGames';
  browse.type = 'button';
  browse.setAttribute('aria-haspopup', 'dialog');
  browse.setAttribute('aria-controls', 'playLibrary');
  gameField.append(gameLabel, select);
  switchRow.append(categoryField, gameField, browse);
  switcher.append(switchRow);
  bar.append(switcher, connections);
  panel.querySelector('.playground-heading').after(bar);
  const modelLabel = connections.querySelector('.model-switch > span');
  modelLabel.removeAttribute('data-i18n-en');
  modelLabel.removeAttribute('data-i18n-zh');
  const sharedNote = make('span', 'workspace-shared-note');
  connections.querySelector('.playground-connection-row').append(sharedNote);

  const library = make('dialog', 'play-library-dialog');
  library.id = 'playLibrary';
  library.setAttribute('aria-labelledby', 'playLibraryTitle');
  const libraryHead = make('div', 'play-library-heading');
  const libraryTitle = make('h2');
  libraryTitle.id = 'playLibraryTitle';
  const close = make('button', 'play-library-close', '×');
  close.type = 'button';
  libraryHead.append(libraryTitle, close);
  const libraryBody = make('div', 'play-library-body');
  libraryBody.append(tools, picker);
  library.append(libraryHead, libraryBody);
  document.body.append(library);
  browse.onclick = () => { library.showModal(); document.getElementById('playSearch').focus({preventScroll: true}); };
  close.onclick = () => library.close();
  library.addEventListener('click', event => {
    if (event.target !== library) return;
    const r = library.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) library.close();
  });
  library.addEventListener('close', () => browse.focus({preventScroll: true}));
  categories.onchange = () => { category = categories.value; render(); };
  select.onchange = async () => {
    if(!select.value)return;
    select.disabled = true;
    try { await window.JevSelectPlay?.(select.value); }
    finally { category = window.JevGameCategories.category(current) || category; render(); }
  };

  const seedHeading = seed.querySelector('.scene-kicker');
  seedHeading.classList.add('workspace-environment-heading');
  seedHeading.append(document.getElementById('playSeedStatus'));
  const description = seed.querySelector('.play-seed-description');
  const help = make('details', 'workspace-seed-help');
  const helpSummary = make('summary');
  help.append(helpSummary, description);
  seed.append(help);
  const environment = make('details', 'workspace-environment');
  const environmentSummary = make('summary');
  environment.append(environmentSummary, seed);
  bar.append(environment);
  // Details belong with the surrounding controls, not below the game canvas.
  document.querySelector('#showcasesView .play-aside').append(document.querySelector('#showcasesView .scene-details'));
  const boardDetails = make('details', 'workspace-result');
  boardDetails.open = true;
  document.getElementById('decisionDetails').open = true;
  const boardSummary = make('summary');
  boardDetails.append(boardSummary, document.getElementById('gameResult'));
  document.querySelector('#boardPlay .play-aside').append(boardDetails, document.getElementById('gameInput'));
  for (const card of view.querySelectorAll('.play-aside > .decision-card')) {
    const disclosure = make('details', 'workspace-decision');
    const summary = make('summary');
    disclosure.append(summary);
    card.before(disclosure);
    disclosure.append(card);
  }
  function render() {
    const taxonomy = window.JevGameCategories;
    if(!category)category = taxonomy.category(current) || taxonomy.category(games[0]?.id) || 'realtime';
    categoryLabel.textContent = tr('CATEGORY', '分类');
    gameLabel.textContent = tr('GAME', '游戏');
    categories.setAttribute('aria-label', tr('Game categories', '游戏分类'));
    categories.replaceChildren();
    for (const group of taxonomy.groups) {
      const option = make('option', '', taxonomy.label(group, window.JevI18n?.lang));
      option.value = group.id;
      categories.append(option);
    }
    categories.value = category;
    categories.disabled = disabled;
    select.setAttribute('aria-label', tr('Switch game', '切换游戏'));
    select.replaceChildren();
    const inCategory = games.filter(game => taxonomy.category(game.id) === category);
    if(!inCategory.some(game => game.id === current)) {
      const placeholder = make('option', '', tr('Choose a game…', '选择具体游戏…'));
      placeholder.value = ''; placeholder.disabled = true; select.append(placeholder);
    }
    for (const game of inCategory) {
      const option = make('option', '', taxonomy.icon(game.id)+'  '+(window.JevPlayText?.ui(game.name) ?? game.name));
      option.value = game.id;
      select.append(option);
    }
    select.value = inCategory.some(game => game.id === current) ? current : '';
    select.disabled = disabled || !inCategory.length;
    browse.textContent = tr('All games', '全部游戏');
    browse.disabled = disabled;
    modelLabel.textContent = tr('Model', '模型');
    sharedNote.textContent = tr('Your selection stays when switching games.', '切换游戏时保留当前模型。');
    libraryTitle.textContent = tr('Choose your next game.', '选择下一个游戏。');
    close.setAttribute('aria-label', tr('Close game library', '关闭游戏目录'));
    helpSummary.textContent = tr('How seeds work', '种子如何生效');
    environmentSummary.textContent = tr('Environment', '环境设置');
    boardSummary.textContent = tr('Decision details', '决策详情');
    for (const id of ['showcaseResult','gameResult']) {
      const result = document.getElementById(id);
      result.setAttribute('role','region'); result.tabIndex = 0;
      result.setAttribute('aria-label',tr('Decision details','决策详情'));
    }
    view.querySelectorAll('.workspace-decision > summary').forEach(node => node.textContent = tr('Latest decision & history', '最近决策与历史'));
  }
  window.JevPlayWorkspace = {
    setGames(items) { games = items; render(); },
    setCurrent(id) { if(current !== id) { boardDetails.open = true; document.getElementById('decisionDetails').open = true; } current = id; category = window.JevGameCategories.category(id) || category; render(); },
    setBusy(value) { disabled = !!value; select.disabled = disabled || !games.length; browse.disabled = disabled; categories.disabled = disabled; },
  };
  // Bound only the sidebar to its remaining viewport space. Never resize games.
  let panelFrame = null;
  function fitDecisionPanels() {
    if(panelFrame !== null) return;
    panelFrame = requestAnimationFrame(() => {
      panelFrame = null;
      for(const aside of view.querySelectorAll('.play-aside')) {
        if(!aside.getClientRects().length) continue;
        const top = aside.getBoundingClientRect().top + window.scrollY;
        const height = Math.max(160, window.innerHeight - top - 12) + 'px';
        if(aside.style.getPropertyValue('--workspace-panel-height') !== height)
          aside.style.setProperty('--workspace-panel-height',height);
      }
    });
  }
  const panelObserver = new ResizeObserver(fitDecisionPanels);
  for(const node of view.querySelectorAll('.play-aside,.scene-header,#playWorkspaceBar')) panelObserver.observe(node);
  window.addEventListener('resize',fitDecisionPanels);
  window.addEventListener('oneshot:game-ready',fitDecisionPanels);
  window.addEventListener('oneshot:game-ready', () => {
    if (library.open) { library.close(); select.focus({preventScroll: true}); }
  });
  const modelDetails = connections.querySelector('.model-details');
  document.addEventListener('pointerdown', event => {
    if (modelDetails.open && !modelDetails.contains(event.target)) modelDetails.open = false;
    if (environment.open && !environment.contains(event.target)) environment.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && modelDetails.open) { modelDetails.open = false; modelDetails.querySelector('summary').focus({preventScroll: true}); }
    if (event.key === 'Escape' && environment.open) { environment.open = false; environmentSummary.focus({preventScroll: true}); }
  });
  document.querySelector('.brand').addEventListener('click', event => {
    event.preventDefault();
    document.querySelector('.tabs [data-tab="blog"]').click();
    window.scrollTo({top: 0, behavior: 'instant'});
  });
  window.JevI18n?.onChange(render);
  render();
})();
