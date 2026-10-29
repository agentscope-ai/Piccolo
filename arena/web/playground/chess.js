/* International chess view. Legal UCI moves, rule facts and results belong to the
 * shared backend; this module only selects and displays those published moves. */
window.JevChessUI = (() => {
  'use strict';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const el = id => document.getElementById(id);
  const pieceGlyph = {K:'♔',Q:'♕',R:'♖',B:'♗',N:'♘',P:'♙',k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
  const pieceName = {k:['King','王'],q:['Queen','后'],r:['Rook','车'],b:['Bishop','象'],n:['Knight','马'],p:['Pawn','兵']};
  const seats = {white:'human', black:'rule'};
  let root = null, view = null, from = null, promotions = [], flipped = false;
  let running = false, timer = null, generation = 0, lastPosition = null, lastDecision = null;

  function node(tag, text, cls) {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function active() { return selectedPlay === 'chess' && showcaseKind?.kind === 'chess'; }
  function color(g = view?.state) { return g?.current_player === 1 ? 'black' : 'white'; }
  function sideName(side) { return side === 'white' ? tr('White', '白方') : tr('Black', '黑方'); }
  function controllerName(controller) {
    return controller === 'model' ? tr('Model', '模型') : ['rule','reference','rule_engine'].includes(controller) ? tr('Rule engine', '规则引擎') : controller === 'qwen3.8-max' ? 'Qwen3.8-max' : tr('Human', '人类');
  }
  function currentController() { return window.JevParticipants?.isDuel() ? (['human','rule'].includes(JevParticipants.controller())?JevParticipants.controller():'model') : seats[color()]; }
  function input(decision) {
    return decision ? {state:decision.observation, prompt:decision.question.instructions, option:decision.question.criteria} : null;
  }
  function adapted(s) {
    return {session_id:s.session_id, revision:s.revision, world:{...s.state,outcome_label:status(s.state)}, choices:s.legal_actions,
      goal:s.engine.goal, environment:{seed:s.seed}, input:input(s.decision)};
  }
  function moves() {
    return Object.entries(view?.legal_actions || {}).flatMap(([action,label]) => {
      const m = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/.exec(action);
      return m ? [{action,label,from:m[1],to:m[2],promotion:m[3] || null}] : [];
    });
  }
  function stop() { running = false; clearTimeout(timer); timer = null; if (active()) controls(showcaseBusy); }
  function hide() { if (root) root.hidden = true; from = null; promotions = []; }
  function panel() {
    if (!root) { root = node('section', undefined, 'jev-chess'); root.id = 'chessStage'; el('showcaseCanvas').after(root); }
    root.hidden = false; root.replaceChildren(); return root;
  }
  function status(g) {
    if (g.outcome) {
      const reason = g.termination || g.termination_reason || g.reason;
      if (g.outcome === 'budget_exhausted') return tr('Move budget reached · Unfinished','步数预算耗尽 · 未完成对局');
      const reasons = {checkmate:tr('Checkmate','将死'),stalemate:tr('Stalemate','逼和'),insufficient_material:tr('Insufficient material','子力不足和棋'),
        fivefold_repetition:tr('Fivefold repetition','五次重复和棋'),seventyfive_moves:tr('75-move rule','75 回合规则和棋'),
        threefold_repetition:tr('Threefold repetition','三次重复和棋'),fifty_moves:tr('50-move rule','50 回合规则和棋'),
        claimed_threefold:tr('Claimed threefold repetition','申领三次重复和棋'),claimed_fifty_moves:tr('Claimed 50-move rule','申领五十回合和棋'),
        budget_exhausted:tr('Move budget reached','步数预算耗尽')};
      const winner = g.result === '1-0' ? 'white' : g.result === '0-1' ? 'black' : null;
      return (winner ? sideName(winner) + ' · ' + tr('wins','获胜') : tr('Draw','和棋')) + (reason ? ' · ' + (reasons[reason] || reason) : '');
    }
    return sideName(color(g)) + ' · ' + tr('to move','行棋') + (g.in_check || g.check ? ' · ' + tr('Check!','被将军！') : '');
  }
  function apply(action) {
    if (showcaseBusy || !active() || !(action in (view?.legal_actions || {}))) return;
    from = null; promotions = []; step(action, false);
  }
  function choose(square) {
    if (showcaseBusy || view?.terminal || currentController() !== 'human') return;
    const legal = moves();
    const matches = legal.filter(m => m.from === from && m.to === square);
    if (matches.length) {
      if (matches.some(m => m.promotion)) { promotions = matches; render(); root.querySelector('.jev-chess-promotion button')?.focus(); }
      else apply(matches[0].action);
      return;
    }
    from = from !== square && legal.some(m => m.from === square) ? square : null;
    promotions = []; render(); root.querySelector('[data-square="' + square + '"]')?.focus();
  }
  function seatControls(p) {
    if(window.JevParticipants?.isDuel())return;
    const row = node('div', undefined, 'jev-chess-seats');
    for (const side of ['white','black']) {
      const label = node('label', sideName(side));
      const select = node('select'); select.id = 'chessSeat-' + side;
      for (const value of ['human','model','rule']) { const option = node('option', controllerName(value)); option.value = value; select.append(option); }
      select.value = seats[side];
      select.onchange = () => { seats[side] = select.value; from = null; promotions = []; render(); schedule(); };
      label.append(select); row.append(label);
    }
    const flip = node('button', tr('Flip board','翻转棋盘'), 'jev-chess-flip'); flip.type = 'button';
    flip.onclick = () => { flipped = !flipped; render(); }; row.append(flip); p.append(row);
    p.append(node('p', tr('Model seats use the connection selected above. Seat changes apply to the next move.', '模型席位使用页面上方当前连接。席位设置从下一步生效。'), 'jev-chess-note'));
  }
  function render() {
    if (!active() || !view) { hide(); return; }
    const g = view.state, p = panel(), position = view.session_id + ':' + view.revision;
    if (lastPosition !== position) { from = null; promotions = []; lastPosition = position; }
    el('showcaseCanvas').classList.add('hidden'); window.JevSelectedGames?.hide();
    if (el('enginePublicState')) el('enginePublicState').hidden = true;
    seatControls(p);
    const heading = node('div', status(g), 'jev-chess-status'); if(window.JevParticipants?.isDuel()){heading.innerHTML=JevParticipants.badges([sideName('white'),sideName('black')]);if(g.outcome||g.in_check||g.check)heading.append(node('span',' · '+status(g)));} heading.setAttribute('role','status'); heading.setAttribute('aria-live','polite'); p.append(heading);
    const legal = moves(), grid = node('div', undefined, 'jev-chess-board');
    grid.setAttribute('role','group'); grid.setAttribute('aria-label',tr('Chess board','国际象棋棋盘'));
    const ranks = flipped ? [1,2,3,4,5,6,7,8] : [8,7,6,5,4,3,2,1];
    const files = [...'abcdefgh']; if (flipped) files.reverse();
    const last = typeof g.last_move === 'string' ? g.last_move : g.last_move?.uci;
    ranks.forEach((rank,ri) => files.forEach((file,ci) => {
      const square = file + rank, piece = g.board?.[8-rank]?.[file.charCodeAt(0)-97];
      const b = node('button', undefined, 'jev-chess-square ' + ((file.charCodeAt(0)-97 + rank) % 2 ? 'light' : 'dark'));
      b.type = 'button'; b.dataset.square = square;
      const name = pieceName[piece?.toLowerCase()];
      b.setAttribute('aria-label', square + ' · ' + (name ? sideName(piece === piece.toUpperCase() ? 'white' : 'black') + ' ' + tr(...name) : tr('empty','空格')));
      b.setAttribute('aria-pressed', String(from === square));
      b.classList.toggle('selected', from === square);
      b.classList.toggle('legal', !!from && legal.some(m => m.from === from && m.to === square));
      b.classList.toggle('last-move', !!last && [last.slice(0,2),last.slice(2,4)].includes(square));
      b.classList.toggle('check', !!(g.in_check || g.check) && piece === (color(g) === 'white' ? 'K' : 'k'));
      if (pieceGlyph[piece]) { const glyph = node('span', pieceGlyph[piece], 'jev-chess-piece ' + (piece === piece.toUpperCase() ? 'white' : 'black')); glyph.setAttribute('aria-hidden','true'); b.append(glyph); }
      if (ci === 0) b.append(node('span', String(rank), 'jev-chess-rank'));
      if (ri === 7) b.append(node('span', file, 'jev-chess-file'));
      b.onclick = () => choose(square); grid.append(b);
    })); p.append(grid);
    if (promotions.length) {
      const chooser = node('div', undefined, 'jev-chess-promotion'); chooser.setAttribute('role','group');
      chooser.setAttribute('aria-label',tr('Choose promotion piece','选择升变棋子'));
      chooser.append(node('strong',tr('Promote to:','升变为：')));
      for (const m of promotions) { const b = node('button',tr(...pieceName[m.promotion])); b.dataset.promotion = m.promotion; b.onclick = () => apply(m.action); chooser.append(b); }
      const cancel = node('button',tr('Cancel','取消')); cancel.onclick = () => { promotions = []; render(); }; chooser.append(cancel); p.append(chooser);
    }
    const hint = g.outcome ? status(g) : currentController() === 'human'
      ? (from ? from + ' · ' + tr('Choose a highlighted destination.','请选择高亮落点。') : tr('Choose a piece, then a legal destination.','先选择棋子，再选择合法落点。'))
      : controllerName(currentController()) + ' · ' + tr('Use the seat step button or start seat autoplay.','可单步执行，或开始按席位连玩。');
    p.append(node('p',hint,'jev-chess-hint'));
    renderMoves(p,g); renderActions(); controls(showcaseBusy);
    el('showcaseGoal').textContent = showcaseSession.goal;
    el('keyboardHint').textContent = tr('Legal moves are supplied by the engine. Tab/Enter also selects squares; promotion is always explicit.', '合法着法由引擎提供。可用 Tab / Enter 选择格子，升变时必须明确选择棋子。');
    renderEvidence();
  }
  function cachedDecision() {
    return lastDecision?.generation === generation && lastDecision.session_id === view?.session_id ? lastDecision : null;
  }
  function renderEvidence(force=false) {
    if (!active() || !view || !playTabVisible) return;
    const cached = cachedDecision(), result = cached?.response.result;
    const key = generation + ':' + view.session_id + ':' + view.revision;
    if (!force && el('chessDecisionContext')?.dataset.position === key) return;
    const fields = el('showcaseFields'); fields.replaceChildren();
    const context = node('section'); context.id = 'chessDecisionContext'; context.dataset.position = key;
    context.append(node('p',cached ? tr('Decision context before the move · Canonical candidate order','落子前决策上下文 · 规范候选顺序') : tr('Current decision context · Canonical candidate order','当前决策上下文 · 规范候选顺序'),'notice'));
    const canonical = node('div'); canonical.innerHTML = showcaseInputs(cached ? cached.input : input(view.decision)); context.append(canonical); fields.append(context);
    if (result) {
      const representative = result.representative_sample_index ?? 0;
      const actual = node('section'); actual.id = 'chessSentInput';
      actual.append(node('p',tr('Actual request supporting the final action · Probe ','支持最终动作的真实请求 · 第 ') + (representative+1) + tr('',' 次判断'),'notice'));
      const request = node('pre',pretty(result.model_input?.schema_input || result.model_input || tr('Provider did not return its request.','服务未返回实际请求。'))); actual.append(request); fields.append(actual);
      const samples = result.decision_stability?.samples || [];
      if (samples.length) {
        const orders = node('section'); orders.id = 'chessProbeOrders';
        orders.append(node('p',tr('Measured candidate orders for all probes','各次真实判断的候选顺序'),'notice'));
        for (const sample of samples) orders.append(node('pre',pretty({probe:sample.sample_index+1,selected_action:sample.value,option_order:sample.order})));
        fields.append(orders);
      }
    }
    if (cached) {
      const {response,actor,controller,actionName} = cached;
      if (!cached.logged) {
        const actorLabel = sideName(actor) + ' · ' + (response.forced ? tr('Forced move','唯一合法动作') : controllerName(response.controller || controller));
        decisionLog(response.controller || controller,actionName,actorLabel,response.result); cached.logged = true;
      }
      if (result) {
        el('showcaseResult').innerHTML = resultHtml(result);
        const index = result.representative_sample_index;
        if (Number.isInteger(index)) el('showcaseResult').prepend(node('div',tr('Candidate probabilities come from supporting probe ','候选概率来自支持最终动作的第 ') + (index+1) + tr('; probes are aligned by action ID for stability.',' 次判断；三次结果按动作 ID 对齐计算稳定性。'),'notice'));
      } else {
        const notice = node('div',response.forced ? tr('Only one legal action; applied automatically.','唯一合法动作，由引擎直接执行。') : controllerName(response.controller || controller) + ' · ' + actionName,'notice');
        el('showcaseResult').replaceChildren(notice);
      }
      el('decisionDetails').open = true;
    }
  }
  function restore() {
    if (!active() || !view || !playTabVisible) return;
    showcaseSession = adapted(view); renderShowcaseGame();
  }
  function renderMoves(p,g) {
    const history = g.move_history || g.history || [];
    const details = node('details',undefined,'jev-chess-history'); details.open = true;
    details.append(node('summary',tr('Moves','棋谱') + ' · ' + history.length));
    if (!history.length) details.append(node('p',tr('No moves yet.','尚未行棋。')));
    if (g.opening_plies) details.append(node('p',tr('Seeded opening moves: ','种子开局已走：') + g.opening_plies + tr(' plies',' 半回合') + ' · ' + (g.moves_uci || []).slice(0,g.opening_plies).join(' '),'jev-chess-note'));
    const list = node('ol');
    for (const h of history) {
      const li = node('li');
      li.append(node('span',typeof h === 'string' ? h : sideName(h.actor === 1 ? 'black' : 'white') + ' · ' + (h.san || h.uci || h.action || ''),'jev-chess-san'));
      if (typeof h === 'object') li.append(node('small',h.controller === 'deterministic_execution' ? tr('Forced move','唯一合法动作') : controllerName(h.controller)));
      list.append(li);
    }
    details.append(list); p.append(details);
  }
  function renderActions() {
    const box = el('showcaseActions'); box.replaceChildren();
    if (!view || view.terminal) return;
    if (currentController() !== 'human') {
      const b = node('button',controllerName(currentController()) + ' · ' + tr('Play this turn','执行本回合'));
      b.id = 'chessSeatStep'; b.onclick = () => step(null,currentController() === 'model',currentController() === 'rule'); box.append(b);
    }
    const extra = Object.entries(view.legal_actions).filter(([action]) => !/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(action));
    for (const [action,label] of extra) { const b = node('button',label); b.dataset.action = action; b.onclick = () => apply(action); box.append(b); }
    const details = node('details',undefined,'jev-chess-actions'); details.append(node('summary',tr('All legal moves','全部合法着法') + ' · ' + moves().length));
    for (const m of moves()) { const b = node('button',m.label); b.dataset.action = m.action; b.onclick = () => apply(m.action); details.append(b); }
    box.append(details);
  }
  function controls(disabled) {
    if (!active() || !root || !view) return;
    const terminal = view.terminal;
    root.querySelectorAll('select,.jev-chess-flip').forEach(n => n.disabled = disabled);
    root.querySelectorAll('.jev-chess-square,.jev-chess-promotion button').forEach(n => n.disabled = disabled || terminal || currentController() !== 'human');
    el('showcaseActions').querySelectorAll('[data-action]').forEach(n => n.disabled = disabled || terminal || currentController() !== 'human');
    if (el('chessSeatStep')) el('chessSeatStep').disabled = disabled || terminal || currentController() === 'model' && !modelReady;
    el('showcaseModel').disabled = disabled || terminal || !modelReady;
    el('showcaseAuto').disabled = !running && (disabled || terminal || Object.values(seats).includes('model') && !modelReady);
    el('showcaseAuto').textContent = running ? tr('■ Stop seat autoplay','■ 停止连玩') : tr('▶ Seat autoplay','▶ 按席位连玩');
  }
  async function create(seed = 0) {
    stop(); const creatingGeneration = ++generation;
    from = null; promotions = []; lastPosition = null; lastDecision = null;
    const previous = view;
    const created = await api('v1/sessions',{game:'chess',seed});
    if (creatingGeneration !== generation) throw Error(tr('A newer chess game replaced this request.','这次开局请求已被新的对局替代。'));
    view = created;
    if (previous && previous.session_id !== view.session_id) {
      // Release only this UI's old in-memory session after the replacement exists.
      fetch('./api/v1/sessions/' + encodeURIComponent(previous.session_id), {method:'DELETE',headers:ConnectUI.headers(modelName)}).catch(() => {});
    }
    return adapted(view);
  }
  async function step(action,model,reference=false) {
    if (!active() || !view || showcaseBusy || view.terminal) return false;
    const episode = view.session_id, expectedGeneration = generation, before = input(view.decision), actor = color();
    const controller = reference ? 'reference' : model ? 'model' : 'human';
    const body = {revision:view.revision};
    if (reference) body.reference = true; else if (model) body.model_id = modelName; else body.action = action;
    showcaseBusy = true; showcaseControls(true); clearError();
    try {
      const response = await api('v1/sessions/' + encodeURIComponent(episode) + '/steps',body);
      if (expectedGeneration !== generation || view.session_id !== episode) return false;
      view = response;
      lastDecision = {generation:expectedGeneration,session_id:episode,response,actor,controller,logged:false,
        input:response.previous_input || input(response.previous_decision) || before,
        actionName:response.action_name || response.action || action};
      // Background completion still advances this game's public session. The
      // UI restores the matching decision receipt only when this tab is shown.
      if (active()) { showcaseSession = adapted(view); if (playTabVisible) restore(); }
      if (view.terminal && active()) stopAuto();
      return true;
    } catch (e) { error(e); stopAuto(); return false; }
    finally { showcaseBusy = false; showcaseControls(false); schedule(); }
  }
  function schedule() {
    if(window.JevParticipants?.isDuel()){JevParticipants.schedule();return;}
    clearTimeout(timer); timer = null;
    if (!running || !active() || !playTabVisible || showcaseBusy || !view || view.terminal || currentController() === 'human') return;
    timer = setTimeout(() => {
      timer = null;
      if (!running || !active() || !playTabVisible) return;
      const controller = currentController();
      if (controller === 'model' && !modelReady) { stopAuto(); controls(false); return; }
      if (controller !== 'human') step(null,controller === 'model',controller === 'rule');
    },200);
  }
  function autoplay() {
    if (running) { stopAuto(); controls(false); return; }
    if (!view || view.terminal || showcaseBusy) return;
    running = true; showcaseAuto = true; autoTicket++; controls(false); schedule();
  }
  window.JevI18n?.onChange(() => { if (active()) { render(); renderEvidence(true); } });
  return {active,create,step,render,restore,controls,autoplay,stop,hide};
})();
