/* Complete, verified winning replays; playback never requests model decisions. */
(() => {
  'use strict';
  const host = document.getElementById('homeDecisionDemo');
  if (!host) return;
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const direction = {left: ['Left', '向左', '←'], up: ['Up', '向上', '↑'], right: ['Right', '向右', '→'], down: ['Down', '向下', '↓']};
  let archive = null, data = null, gameIndex = 0, cursor = 0, phase = 0, playing = false, timer = 0, loading = false;
  let nativeRenderer = null, nativeMount = null, rendererEpoch = 0;
  const nodes = {};
  const effects = new Set();
  function animate(node, frames, options) {
    if (motion.matches || !visible() || typeof node?.animate !== 'function') return;
    const effect = node.animate(frames, options);
    effects.add(effect);
    effect.finished.then(() => effects.delete(effect), () => effects.delete(effect));
  }
  function cancelEffects() {
    for (const effect of effects) effect.cancel();
    effects.clear();
  }
  function make(tag, className, parent, text = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }
  function actionLabel(key, compact = false) {
    if (!key) return tr('Gravity continues', '重力持续推进');
    if (data?.game === 'tetris_placement') {
      const [rotation, column] = key.split(':').map(Number);
      return tr(`Rotate ${rotation * 90}° · column ${column + 1}`, `旋转 ${rotation * 90}° · 第 ${column + 1} 列`);
    }
    if (direction[key]) return tr(direction[key][0], direction[key][1]);
    if (key.startsWith('push:')) {
      const [, x, y, move, gx, gy] = key.split(':');
      if (compact) return `□${x},${y} ${direction[move][2]} · G${gx},${gy}`;
      return tr(`Push [${x},${y}] ${direction[move][0].toLowerCase()} · goal [${gx},${gy}]`, `推箱[${x},${y}]${direction[move][1]} · 目标[${gx},${gy}]`);
    }
    return key === 'pass' ? tr('Pass', '跳过') : key.toUpperCase();
  }
  function visible() {
    const home = document.getElementById('blogView');
    return !document.hidden && home && !home.classList.contains('hidden') && !home.hidden;
  }
  function stop() {
    playing = false; clearTimeout(timer); timer = 0;
    nativeRenderer?.stop();
    if (data) renderControls();
  }
  function complete() { return cursor === data.steps.length - 1 && phase === 2; }
  function advance() {
    if (phase < 2) phase += 1;
    else if (cursor < data.steps.length - 1) { cursor += 1; phase = 0; }
    if (complete()) stop();
    render();
  }
  function schedule() {
    clearTimeout(timer);
    if (!playing || !visible()) { stop(); return; }
    timer = setTimeout(() => {
      if (!visible()) { stop(); return; }
      advance();
      if (playing) schedule();
    }, [650, 500, 950][phase] / Number(nodes.speed?.value || 1));
  }
  function switchGame(index) {
    const next = (index + archive.clips.length) % archive.clips.length;
    if (next === gameIndex) return;
    const offset = index > gameIndex ? 14 : -14;
    stop(); cancelEffects(); gameIndex = next;
    rendererEpoch++; nativeRenderer?.destroy(); nativeRenderer = null; nativeMount = null;
    data = archive.clips[gameIndex]; cursor = 0; phase = 0;
    render();
    animate(nodes.layout, [{opacity: .35, transform: `translateX(${offset}px)`}, {opacity: 1, transform: 'translateX(0)'}], {duration: 300, easing: 'cubic-bezier(.2,.7,.2,1)'});
  }
  function renderControls() {
    nodes.play.textContent = playing ? tr('Pause', '暂停') : complete() ? tr('Replay full game', '重播完整对局') : tr('Play full game', '播放完整对局');
    nodes.play.setAttribute('aria-pressed', String(playing));
    nodes.next.textContent = tr('Next step →', '下一步 →');
    nodes.next.disabled = complete();
    nodes.reset.textContent = tr('Reset', '重置');
    nodes.finish.textContent = tr('See ending', '查看结局'); nodes.finish.disabled = complete();
    nodes.timeline.max = String(data.steps.length - 1); nodes.timeline.value = String(cursor);
    nodes.timeline.setAttribute('aria-label', tr('Replay position', '回放进度'));
    nodes.timeline.setAttribute('aria-valuetext', `${cursor + 1} / ${data.steps.length}`);
    nodes.speed.setAttribute('aria-label', tr('Playback speed', '播放速度'));
  }
  function coordIncludes(list, x, y) { return list.some(p => p[0] === x && p[1] === y); }
  function renderBoard(state, step) {
    const board = nodes.board;
    board.classList.toggle('home-demo-board-native', data.game === 'tetris_placement');
    if (data.game === 'tetris_placement') {
      board.dataset.game = data.game;
      board.setAttribute('aria-label', tr(`Tetris: ${state.lines} lines cleared.`, `俄罗斯方块：已消除 ${state.lines} 行。`));
      nodes.scoreLabel.textContent = tr('Lines cleared', '已消除行数'); nodes.score.textContent = `${state.lines} / 4`;
      nodes.legend.textContent = tr('Recorded gravity, locking and line clears.', '按原记录回放下落、锁定与消行。');
      const epoch = rendererEpoch;
      const paint = () => {
        if (epoch !== rendererEpoch || !nativeRenderer) return;
        const currentStep = data.steps[cursor];
        const currentState = phase === 2 ? currentStep.after : currentStep.before;
        let snapshot = currentStep.before;
        const frames = [snapshot, ...currentStep.execution_frames.map(delta => (snapshot = {...snapshot, ...delta}))];
        nativeRenderer.update({state: currentState, previousState: currentStep.before,
          step: {...currentStep, execution_frames: frames},
          animate: playing && phase === 2 && !motion.matches, durationMs: 850 / Number(nodes.speed?.value || 1),
          action: currentStep.action, lang: window.JevI18n?.lang || 'en'}).catch(() => {
            if (epoch === rendererEpoch) unavailable();
          });
      };
      if (nativeRenderer) paint();
      else if (!nativeMount) {
        nativeMount = window.JevReplayRenderer.mount(board, {kind: data.game, lang: window.JevI18n?.lang || 'en'});
        nativeMount.then(renderer => {
          if (epoch !== rendererEpoch) { renderer.destroy(); return; }
          const style = renderer.frame.contentDocument.createElement('style');
          style.textContent = 'html,body{height:100%;display:grid;place-items:center}canvas{width:auto!important;height:auto!important;max-width:100vw;max-height:100vh}';
          renderer.frame.contentDocument.head.append(style);
          renderer.frame.tabIndex = -1;
          nativeRenderer = renderer; paint();
        }).catch(() => { if (epoch === rendererEpoch) unavailable(); });
      }
      return;
    }
    board.replaceChildren(); board.dataset.game = data.game;
    let size = 4;
    if (data.game === 'sokoban_puzzle') size = state.width;
    else if (data.game === 'snake_navigation' || data.game === 'othello_6x6') size = state.n;
    board.style.setProperty('--home-demo-grid', String(size));
    if (data.game === 'merge_2048') {
      nodes.scoreLabel.textContent = tr('Game score', '游戏积分'); nodes.score.textContent = String(state.score);
      nodes.legend.textContent = tr('Merge matching tiles.', '合并相同数字的方块。');
      board.setAttribute('aria-label', tr('2048 board: ', '2048 棋盘：') + state.board.map(row => row.join(', ')).join('; '));
      state.board.forEach((row, y) => row.forEach((value, x) => {
        const cell = make('span', 'home-demo-cell', board, value ? String(value) : ''); cell.dataset.value = String(value);
        if (phase === 2 && step.before.board[y][x] !== value) cell.classList.add('home-demo-cell-changed');
      }));
    } else if (data.game === 'sokoban_puzzle') {
      nodes.scoreLabel.textContent = tr('On target', '目标上的箱子'); nodes.score.textContent = `${state.score}/${state.targets.length}`;
      nodes.legend.textContent = tr('● Player · □ Box · ◉ Target', '● 玩家 · □ 箱子 · ◉ 目标');
      board.setAttribute('aria-label', tr('Sokoban. Player: ', '推箱子。玩家：') + state.player.join(',') + tr('; boxes: ', '；箱子：') + state.boxes.map(p => p.join(',')).join('; '));
      for (let y = 0; y < state.height; y++) for (let x = 0; x < state.width; x++) {
        const cell = make('span', 'home-demo-map-cell', board);
        if (coordIncludes(state.walls, x, y)) cell.classList.add('home-demo-wall');
        else {
          if (coordIncludes(state.targets, x, y)) cell.classList.add('home-demo-target');
          if (coordIncludes(state.boxes, x, y)) make('i', 'home-demo-box', cell);
          if (state.player[0] === x && state.player[1] === y) make('i', 'home-demo-player', cell);
        }
      }
    } else if (data.game === 'snake_navigation') {
      nodes.scoreLabel.textContent = tr('Apples', '已吃苹果'); nodes.score.textContent = String(state.score);
      nodes.legend.textContent = tr('■ Snake · ◆ Apple · ▧ Obstacle', '■ 蛇身 · ◆ 苹果 · ▧ 障碍');
      board.setAttribute('aria-label', tr('Snake. Head: ', '贪吃蛇。蛇头：') + state.body[0].join(',') + tr('; apple: ', '；苹果：') + state.food.join(',') + (state.outcome === 'loss' ? tr('; collision', '；发生碰撞') : ''));
      for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
        const cell = make('span', 'home-demo-map-cell', board);
        if (coordIncludes(state.obstacles, x, y)) cell.classList.add('home-demo-rock');
        if (coordIncludes(state.body, x, y)) cell.classList.add('home-demo-snake-body');
        if (state.body[0][0] === x && state.body[0][1] === y) { cell.classList.add('home-demo-snake-head'); cell.textContent = direction[state.pending_direction][2]; }
        if (state.food[0] === x && state.food[1] === y) cell.classList.add('home-demo-food');
        if (state.collision_cell?.[0] === x && state.collision_cell?.[1] === y) cell.classList.add('home-demo-collision');
      }
    } else {
      const flat = state.board.flat();
      nodes.scoreLabel.textContent = tr('Black · White', '黑子 · 白子');
      nodes.score.textContent = `${flat.filter(v => v === 'X').length} : ${flat.filter(v => v === 'O').length}`;
      nodes.legend.textContent = tr(`OneShot plays ${data.model_side === 'X' ? 'Black' : 'White'}. Dots mark legal moves.`, `OneShot 执${data.model_side === 'X' ? '黑' : '白'}，圆点为合法位置。`);
      board.setAttribute('aria-label', tr('Othello board: ', '黑白棋棋盘：') + state.board.map(row => row.join(' ')).join('; '));
      state.board.forEach((row, y) => row.forEach((value, x) => {
        const square = String.fromCharCode(97 + x) + (size - y);
        const cell = make('span', 'home-demo-othello-cell', board);
        make('small', 'home-demo-coordinate', cell, square);
        if (value !== '.') make('i', value === 'X' ? 'home-demo-disc home-demo-disc-black' : 'home-demo-disc home-demo-disc-white', cell);
        else if (phase < 2 && step.candidates.includes(square)) make('i', 'home-demo-legal-dot', cell);
        if (phase >= 1 && square === step.action) cell.classList.add('home-demo-last-move');
      }));
    }
  }
  function resultCopy(step) {
    if (complete()) return tr('Game complete · victory.', '对局完成 · 获胜。');
    if (data.game === 'merge_2048') return step.execution.score_delta
      ? tr(`Move executed. +${step.execution.score_delta} merge points.`, `动作已执行，合并积分 +${step.execution.score_delta}。`)
      : tr('Move executed. No new merge points.', '动作已执行，本步没有新增合并积分。');
    if (data.game === 'sokoban_puzzle') return tr(`${step.execution.physical_moves} physical moves; ${step.after.score}/${step.after.targets.length} boxes on targets.`, `执行 ${step.execution.physical_moves} 个移动动作，${step.after.score}/${step.after.targets.length} 个箱子已到目标。`);
    if (data.game === 'snake_navigation') return step.execution.action_applied
      ? tr('Direction accepted. The world advances while the model responds.', '方向输入已生效；模型响应期间，世界持续前进。')
      : tr('Collision while waiting. This input arrived too late and was not executed.', '等待期间发生碰撞；本次输入到达过晚，未执行。');
    if (data.game === 'tetris_placement') return tr(`${step.after.lines}/4 lines cleared; gravity continues during inference.`, `已消除 ${step.after.lines}/4 行；模型响应期间重力持续推进。`);
    return tr(`${step.execution.flipped_discs} opponent discs flipped. The turn passes.`, `翻转 ${step.execution.flipped_discs} 枚对方棋子，轮到对手。`);
  }
  function render() {
    if (!data) return;
    const step = data.steps[cursor], state = phase === 2 ? step.after : step.before;
    host.dataset.phase = String(phase); host.dataset.game = data.game;
    host.setAttribute('aria-label', tr('Recorded game carousel', '真实对局回放轮播'));
    nodes.badge.textContent = tr('COMPLETED GAME', '完整通关回放');
    nodes.counter.textContent = `${String(cursor + 1).padStart(2, '0')} / ${data.steps.length}`;
    nodes.previousGame.setAttribute('aria-label', tr('Previous game', '上一个游戏'));
    nodes.nextGame.setAttribute('aria-label', tr('Next game', '下一个游戏'));
    nodes.gameNav.setAttribute('aria-label', tr('Choose a replay', '选择回放游戏'));
    nodes.gameTabs.setAttribute('aria-label', tr('Recorded games', '回放游戏'));
    nodes.gamePosition.textContent = `${String(gameIndex + 1).padStart(2, '0')} / ${String(archive.clips.length).padStart(2, '0')}`;
    nodes.dots.forEach((button, i) => {
      const clip = archive.clips[i], name = tr(clip.name_en, clip.name_zh);
      button.setAttribute('aria-label', `${name} · ${clip.models[0].name} · ${i + 1}/${archive.clips.length}`);
      button.setAttribute('title', `${name} · ${clip.models[0].name}`); button.setAttribute('aria-pressed', String(i === gameIndex));
      const tab = nodes.gameButtons[i];
      tab.textContent = name; tab.setAttribute('aria-pressed', String(i === gameIndex));
      tab.title = `${name} · ${clip.models[0].name}`;
    });
    nodes.game.textContent = tr(data.name_en, data.name_zh);
    nodes.seed.textContent = `SEED ${data.seed}`;
    nodes.model.textContent = data.models[0].name;
    nodes.model.title = `${data.models[0].id} · ${data.models[0].checkpoint}`;
    nodes.result.textContent = tr('Victory · full replay', '已获胜 · 完整轨迹');
    renderBoard(state, step);
    const observation = {
      merge_2048: ['Read the state and legal moves.', '读取棋盘与合法动作。'],
      sokoban_puzzle: ['Plan a walk, then push a box.', '先走到合适位置，再推动箱子。'],
      snake_navigation: ['The clock keeps running during inference.', '模型思考时，游戏时钟继续推进。'],
      othello_6x6: [step.actor === 'X' ? 'Black to move.' : 'White to move.', step.actor === 'X' ? '本次轮到黑方落子。' : '本次轮到白方落子。'],
      tetris_placement: ['Gravity keeps running during inference.', '模型响应时，重力持续推进。'],
    }[data.game];
    const automatic = step.execution.no_request;
    const actor = automatic ? tr('Continue the chosen plan', '继续执行已有计划')
      : step.origin === 'opponent' ? tr('Fixed opponent moves', '固定对手落子')
      : step.model_call === false ? tr('Only legal move', '执行唯一合法动作') : tr('Choose an action', '从候选动作中选择');
    const names = [
      [tr('Observe the board', '读取当前局面'), tr(...observation)],
      [actor, automatic ? tr('No new model request; the recorded world advances.', '没有新的模型请求，按记录推进世界。') : phase >= 1
        ? (step.action?.startsWith('push:')
          ? tr(`Recorded: push box ${direction[step.action.split(':')[3]][0].toLowerCase()}.`, `归档选择：${direction[step.action.split(':')[3]][1]}推箱。`)
          : tr(`Recorded: ${actionLabel(step.action)}.`, `归档选择：${actionLabel(step.action)}。`))
        : tr(`${step.candidates.length} legal options. What comes next?`, `${step.candidates.length} 个合法候选，接下来选哪一步？`)],
      [tr('See what changed', '观察执行结果'), phase === 2 ? resultCopy(step) : tr('Follow the recorded outcome.', '查看这次选择的实际结果。')],
    ];
    nodes.stages.forEach((item, i) => {
      item.title.textContent = names[i][0]; item.copy.textContent = names[i][1];
      item.node.classList.toggle('home-demo-stage-current', i === phase);
      item.node.classList.toggle('home-demo-stage-done', i < phase);
      item.node.setAttribute('aria-current', i === phase ? 'step' : 'false');
    });
    nodes.candidates.replaceChildren();
    nodes.candidates.setAttribute('aria-label', tr('Legal candidates', '合法候选动作'));
    const candidates = phase >= 1 ? [step.action, ...step.candidates.filter(action => action !== step.action)] : step.candidates;
    for (const action of candidates) {
      if (action == null) continue;
      const chip = make('span', 'home-demo-candidate', nodes.candidates);
      chip.title = actionLabel(action) + ` (${action})`;
      if (direction[action]) make('span', 'home-demo-candidate-arrow', chip, direction[action][2]);
      make('span', '', chip, actionLabel(action, true));
      if (phase >= 1 && action === step.action) {
        chip.classList.add('home-demo-candidate-selected');
        make('span', 'home-demo-choice-mark', chip, phase === 2 && !step.execution.action_applied ? '×' : '✓');
      }
    }
    nodes.candidates.scrollTop = 0;
    nodes.latency.textContent = step.model_call && phase >= 1 && Number.isFinite(step.latency_seconds)
      ? tr(`Recorded decision ${step.latency_seconds.toFixed(2)} s`, `归档决策耗时 ${step.latency_seconds.toFixed(2)} 秒`) + (Number.isInteger(step.repeat_count) ? tr(` · ${step.repeat_count} repeats`, ` · ${step.repeat_count} 次重复决策`) : '')
      : tr('Legal moves verified by the shared engine.', '合法动作已由共享引擎核验。');
    nodes.announcement.textContent = tr(data.name_en, data.name_zh) + ' · ' + tr(`Step ${cursor + 1}/${data.steps.length}. `, `第 ${cursor + 1}/${data.steps.length} 步。`) + names[phase][0] + '. ' + names[phase][1];
    renderControls();
    if (phase === 2) {
      for (const cell of nodes.board.querySelectorAll('.home-demo-cell-changed:not([data-value="0"]),.home-demo-last-move')) {
        animate(cell, [{transform: 'scale(.9)'}, {transform: 'scale(1)'}], {duration: 260, easing: 'ease-out'});
      }
    }
  }
  function build() {
    host.replaceChildren(); host.classList.add('home-demo'); host.setAttribute('role', 'region');
    const top = make('div', 'home-demo-top', host);
    nodes.badge = make('span', 'home-demo-badge', top);
    nodes.gameNav = make('div', 'home-demo-game-nav', top);
    nodes.gameNav.setAttribute('role', 'group');
    nodes.previousGame = make('button', 'home-demo-game-arrow', nodes.gameNav, '←'); nodes.previousGame.type = 'button';
    nodes.gamePosition = make('span', 'home-demo-game-position', nodes.gameNav);
    nodes.dots = archive.clips.map((clip, i) => {
      const dot = make('button', 'home-demo-game-dot', nodes.gameNav); dot.type = 'button'; dot.onclick = () => switchGame(i); return dot;
    });
    nodes.nextGame = make('button', 'home-demo-game-arrow', nodes.gameNav, '→'); nodes.nextGame.type = 'button';
    nodes.previousGame.onclick = () => switchGame(gameIndex - 1); nodes.nextGame.onclick = () => switchGame(gameIndex + 1);
    nodes.gameNav.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault(); switchGame(gameIndex + (event.key === 'ArrowLeft' ? -1 : 1)); nodes.gameButtons[gameIndex].focus({preventScroll: true});
    });
    nodes.gameTabs = make('div', 'home-demo-game-tabs', host);
    nodes.gameTabs.setAttribute('role', 'group');
    nodes.gameButtons = archive.clips.map((clip, i) => {
      const button = make('button', '', nodes.gameTabs);
      button.type = 'button'; button.onclick = () => switchGame(i); return button;
    });
    nodes.gameTabs.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? archive.clips.length - 1 : gameIndex + (event.key === 'ArrowLeft' ? -1 : 1);
      switchGame(next); nodes.gameButtons[gameIndex].focus({preventScroll: true});
    });
    const layout = nodes.layout = make('div', 'home-demo-layout', host);
    const visual = make('div', 'home-demo-visual', layout);
    const boardHeading = make('div', 'home-demo-board-heading', visual);
    const game = make('div', '', boardHeading);
    nodes.game = make('strong', 'home-demo-game', game); nodes.seed = make('small', 'home-demo-seed', game);
    const score = make('div', 'home-demo-score', boardHeading);
    nodes.scoreLabel = make('small', '', score); nodes.score = make('strong', '', score);
    nodes.model = make('small', 'home-demo-model', visual);
    nodes.board = make('div', 'home-demo-board', visual); nodes.board.setAttribute('role', 'img');
    // Horizontal board gestures leave vertical page scrolling available.
    let gesture = null;
    nodes.board.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0) return;
      gesture = {id: event.pointerId, x: event.clientX, y: event.clientY};
    });
    nodes.board.addEventListener('pointerup', event => {
      const start = gesture; gesture = null;
      if (!start || start.id !== event.pointerId) return;
      const dx = event.clientX - start.x, dy = event.clientY - start.y;
      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.6) switchGame(gameIndex + (dx < 0 ? 1 : -1));
    });
    nodes.board.addEventListener('pointercancel', () => { gesture = null; });
    nodes.board.addEventListener('pointerleave', event => { if (event.pointerType === 'mouse') gesture = null; });
    nodes.legend = make('small', 'home-demo-board-legend', visual);
    const decision = make('div', 'home-demo-decision', layout);
    nodes.counter = make('span', 'home-demo-counter', decision);
    nodes.stages = [0, 1, 2].map(i => {
      const node = make('div', 'home-demo-stage', decision);
      make('span', 'home-demo-stage-number', node, `0${i + 1}`);
      const body = make('div', 'home-demo-stage-body', node);
      const title = make('strong', 'home-demo-stage-title', body); const copy = make('p', 'home-demo-stage-copy', body);
      if (i === 1) {
        nodes.candidates = make('div', 'home-demo-candidates', body); nodes.candidates.tabIndex = 0;
        nodes.latency = make('small', 'home-demo-latency', body);
      }
      return {node, title, copy};
    });
    nodes.result = make('small', 'home-demo-result', decision);
    nodes.timeline = make('input', 'home-demo-timeline', decision); nodes.timeline.type = 'range'; nodes.timeline.min = '0'; nodes.timeline.step = '1';
    nodes.timeline.oninput = () => { const position = Number(nodes.timeline.value); stop(); cursor = position; phase = 2; render(); };
    const controls = make('div', 'home-demo-controls', decision);
    nodes.play = make('button', 'home-demo-play', controls); nodes.next = make('button', 'home-demo-next', controls); nodes.reset = make('button', 'home-demo-reset', controls);
    nodes.finish = make('button', 'home-demo-finish', controls);
    nodes.speed = make('select', 'home-demo-speed', controls);
    for (const speed of [1, 2, 4]) { const option = make('option', '', nodes.speed, `${speed}×`); option.value = String(speed); }
    nodes.speed.onchange = () => { if (playing) schedule(); };
    for (const button of [nodes.play, nodes.next, nodes.reset, nodes.finish]) button.type = 'button';
    nodes.play.onclick = () => {
      if (playing) { stop(); return; }
      if (complete()) { cursor = 0; phase = 0; render(); }
      playing = true; renderControls(); schedule();
    };
    nodes.next.onclick = () => { stop(); advance(); }; nodes.reset.onclick = () => { stop(); cursor = 0; phase = 0; render(); };
    nodes.finish.onclick = () => { stop(); cursor = data.steps.length - 1; phase = 2; render(); };
    nodes.announcement = make('p', 'home-demo-sr-only', host); nodes.announcement.setAttribute('role', 'status'); nodes.announcement.setAttribute('aria-live', 'polite');
    render();
  }
  function unavailable() {
    stop(); cancelEffects(); rendererEpoch++; nativeRenderer?.destroy(); nativeRenderer = null; nativeMount = null; data = null;
    host.replaceChildren();
    make('p', 'home-demo-unavailable', host, tr('The recorded games are temporarily unavailable.', '真实回放暂不可用。'));
    const retry = make('button', '', host, tr('Try again', '重新加载')); retry.type = 'button'; retry.onclick = load;
  }
  async function load() {
    if (loading) return; loading = true; host.replaceChildren();
    make('p', 'home-demo-unavailable', host, tr('Loading recorded games…', '正在读取真实回放…'));
    try {
      const response = await fetch('./playground/data/home-decision.json?v=completed4-20261023', {signal: AbortSignal.timeout(10000)});
      if (!response.ok) throw Error('unavailable');
      const candidate = await response.json();
      if (candidate.schema !== 'oneshot.home-decision.v3' || candidate.clips?.length !== 4 || !candidate.clips.every(clip =>
        clip.steps?.length > 0 && clip.recording === 'reconstructed_verified' && clip.result?.status === 'complete'
        && clip.result.outcome === 'win' && clip.result.terminal === true && clip.result.budget_exhausted === false)) throw Error('invalid completed replay');
      archive = candidate; data = archive.clips[gameIndex]; build();
    } catch { unavailable(); }
    finally { loading = false; }
  }
  const home = document.getElementById('blogView');
  if (home) new MutationObserver(() => { if (!visible()) { stop(); cancelEffects(); } }).observe(home, {attributes: true, attributeFilter: ['class', 'hidden']});
  document.addEventListener('visibilitychange', () => { if (!visible()) { stop(); cancelEffects(); } }); motion.addEventListener('change', () => { stop(); cancelEffects(); });
  window.JevI18n?.onChange(() => { if (data) render(); else if (!loading) unavailable(); });
  load();
})();
