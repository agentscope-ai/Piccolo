/* Player identities select controllers; native engines own legal moves and turns. */
window.JevParticipants = (() => {
  const social = new Set(['doudizhu','texas_holdem','property_tycoon','zha_jin_hua']);
  const duels = new Set(['othello_6x6','hex_7x7','dots_and_boxes_3x3','chess','checkers','xiangqi','uno','liars_dice',...social]);
  const tr = (en,zh) => window.JevI18n?.t(en,zh) ?? en;
  const el = id => document.getElementById(id);
  const seats = [null, 'human', 'rule'];
  const fixedViews = new Set([...social,'uno','liars_dice']);
  let manualView = null;
  const selectIds = ['participantFirst','participantOpponent','participantThird'];
  let running = false, timer = null, game = null, optionKey = '';
  const isDuel = () => typeof selectedPlay !== 'undefined' && duels.has(selectedPlay);
  const isBoard = () => isDuel() && !!catalog?.games.some(g => g.id === selectedPlay) && selectedPlay !== 'chess';
  const world = () => isBoard() ? gameState?.game : showcaseSession?.world;
  function actor() {
    const g = world();
    if (isBoard()) return g?.turn === 'O' ? 1 : 0;
    return Number(g?.current_player ?? g?.player ?? g?.turn ?? 0);
  }
  const player = index => seats[index] ?? (index === 0 ? (modelName || 'human') : 'human');
  const controller = () => isDuel() ? player(actor()) : modelName;
  const ready = id => id === 'rule' || ConnectUI.models.some(m => m.id === id && m.ready);
  const label = id => id === 'human' ? tr('Me','我') : id === 'rule' ? tr('Rule engine','规则引擎') : ConnectUI.modelLabel(ConnectUI.models.find(m => m.id === id) || {id,name:id});
  const seatCount = () => selectedPlay === 'doudizhu' ? 3 : 2;
  const seatLabel = index => selectedPlay === 'doudizhu' ? [tr('Landlord','地主'),tr('Farmer A','农民一'),tr('Farmer B','农民二')][index] : tr('Player ','玩家') + (index + 1);
  const viewSeat = () => manualView ?? Math.max(0,Array.from({length:seatCount()},(_,i)=>i).findIndex(i=>player(i)==='human'));
  const canAct = () => controller()==='human' && (!fixedViews.has(selectedPlay) || viewSeat()===actor() && !world()?.handoff);
  const seatText = (index,role=seatLabel(index)) => role+' · '+label(player(index));
  const activeSeat = index => isDuel() && !terminal() && actor()===index;
  const seatMarker = (index,role) => (activeSeat(index)?'▶ ':'')+seatText(index,role);
  const badges = (roles=Array.from({length:seatCount()},(_,i)=>seatLabel(i))) => roles.map((role,i)=>'<span class="participant-seat" data-seat="'+i+'" aria-current="'+activeSeat(i)+'">'+esc(seatMarker(i,role))+'</span>').join(' ');
  function requestBody(path,body) {
    if(!body || !fixedViews.has(body.kind||selectedPlay) || !/^showcases\/(new|step|reveal|view)$/.test(path))return body;
    if(path==='showcases/new')manualView=null;
    return {...body,view_seat:viewSeat()};
  }
  const terminal = () => !!(world()?.outcome || world()?.winner);
  const blocked = () => busy || showcaseBusy || batchRunning;
  const newOptions = kind => social.has(kind) ? {duel:true,opponent:'human'} : duels.has(kind) ? {opponent:'human'} : {};
  function requestModel(path, body) {
    if (isDuel() && (path === 'game/move' || path === 'showcases/step' || /^v1\/sessions\/[^/]+\/steps$/.test(path))) {
      return ['human','rule'].includes(controller()) ? modelName : controller();
    }
    return modelName;
  }
  function refresh() {
    const row = el('participantControls'); if (!row || typeof modelName === 'undefined') return;
    const duel = isDuel(); row.hidden = !duel;
    el('gamesView').classList.toggle('has-participants',duel);
    if (game !== selectedPlay) { stop(); game = selectedPlay; manualView=null; }
    const models = ConnectUI.models, key = JSON.stringify(models.map(m => [m.id,m.name,m.ready])) + modelName + selectedPlay + tr('en','zh');
    if (key !== optionKey) {
      optionKey = key;
      for (const [index,id] of selectIds.entries()) {
        const select = el(id), selected = player(index) || 'human';
        const prefix = seatLabel(index) + ' · ';
        select.replaceChildren(new Option(prefix+label('human'),'human'),new Option(prefix+label('rule'),'rule'), ...models.map(m => new Option(prefix+label(m.id)+(m.ready?'':tr(' · Unavailable',' · 未就绪')),m.id)));
        // An expired connection must not silently turn into a different player.
        if (!['human','rule'].includes(selected) && !models.some(m => m.id === selected)) select.add(new Option(prefix+tr('Disconnected model','模型已断开'),selected));
        select.value = selected;
      }
    }
    selectIds.forEach((id,index)=>{
      const select=el(id);select.hidden=index>=seatCount();
      select.disabled=blocked()||running;
      select.setAttribute('aria-label',seatLabel(index));
      select.title=seatLabel(index)+' · '+label(player(index));
    });
    document.querySelector('label[for=humanSide]').hidden=duel;
    if(duel)el('modelSelect').disabled=blocked()||running;
    el('participantStart').disabled = blocked() && !running;
    el('participantStart').textContent = running ? tr('Pause','暂停') : tr('Play','开始');
    if(!duel)el('showcaseModel').textContent=tr('Model step','模型单步');
    if(running&&terminal())stop();
    document.querySelectorAll('#humanSide,#autoReply').forEach(n => { (n.closest('label') || n).hidden = duel; });
    if (duel) {
      el('opponentTools').classList.add('hidden');
      const unavailable = controller() === 'human' || !ready(controller());
      const stepLabel = controller()==='rule' ? tr('Rule step','规则单步') : tr('Model step','模型单步');
      el(isBoard()?'modelMove':'showcaseModel').textContent=stepLabel;
      if (isBoard()) { el('modelMove').disabled = blocked() || terminal() || unavailable; el('passMove').disabled = blocked() || terminal() || controller() !== 'human'; }
      else {
        el('showcaseModel').disabled = blocked() || terminal() || unavailable;
        el('showcaseAuto').disabled = terminal() || (blocked() && !running);
        el('showcaseAuto').textContent = running ? tr('■ Pause match','■ 暂停对战') : tr('▶ Play match','▶ 开始对战');
        if (!canAct()) el('showcaseActions').querySelectorAll('[data-action],#playCards,#legalCardCombo,#placeBid,#bidQuantity,#bidFace,#agentConfirm,#agentLegalMove').forEach(n => n.disabled = true);
      }
    }
    renderHandoff();
  }
  function stop() { running = false; clearTimeout(timer); timer = null; }
  function schedule() {
    clearTimeout(timer); timer = null; refresh();
    if (!running || !isDuel() || !playTabVisible || terminal() || controller() === 'human') return;
    timer = setTimeout(async () => {
      timer = null;
      if (!running || !isDuel() || !playTabVisible || terminal()) return;
      if (blocked()) { schedule(); return; }
      if (!ready(controller())) { stop(); error(Error(tr('This player’s model is unavailable. Connect it or configure Piccolo on the server.','当前席位的模型未就绪，请连接模型或在服务端配置 Piccolo。'))); refresh(); return; }
      const progressed = isBoard() ? await play(null,true) : await showcaseStep(null,true);
      if (!progressed) stop();
      schedule();
    },200);
  }
  function toggle() { if (running) stop(); else if (!blocked() && !terminal()) running = true; schedule(); }
  async function reveal() {
    if (!showcaseSession?.world.handoff) return;
    showcaseSession = await api('showcases/reveal',{session_id:showcaseSession.session_id,revision:showcaseSession.revision});
    renderShowcaseGame();
  }
  function renderHandoff() {
    let root=el('socialDuelBoard');
    const g=world(),needed=isDuel()&&fixedViews.has(selectedPlay)&&g?.kind===selectedPlay&&!terminal()&&controller()==='human'&&(g.handoff||viewSeat()!==actor());
    if(!root&&needed){root=document.createElement('section');root.id='socialDuelBoard';root.className='social-duel-handoff';el('showcaseCanvas').after(root)}
    if(!root)return;
    root.hidden=!needed;root.replaceChildren();if(!needed)return;
    const who=document.createElement('span');who.textContent=seatMarker(actor());root.append(who);
    const button=document.createElement('button');button.id='duelReveal';button.textContent=viewSeat()===actor()?tr('Show my hand','显示我的局面'):tr('Switch to this seat','切换到此席位');root.append(button);
    button.disabled=blocked();button.onclick=async()=>{
      if(blocked())return;showcaseBusy=true;const previous=manualView;manualView=actor();
      try{if(g.handoff)await reveal();else{showcaseSession=await api('showcases/view',{session_id:showcaseSession.session_id,revision:showcaseSession.revision});renderShowcaseGame()}}
      catch(e){manualView=previous;error(e)}finally{showcaseBusy=false;showcaseControls(false);schedule()}
    };
  }
  function renderSocial() {
    const g = showcaseSession?.world;
    if (!g?.duel || !social.has(selectedPlay)) return false;
    const table = g.table;
    el('showcaseCanvas').classList.remove('hidden');
    el('agentGameStage').classList.add('hidden');
    window.JevChessUI?.hide(); window.JevSelectedGames?.hide();
    el('showcaseGoal').textContent=g.kind==='doudizhu'&&table.view_seat>0?tr('Cooperate with the other farmer to finish before the landlord.','与另一名农民合作，先于地主出完手牌。'):JevPlayText.ui(JevPlayText.goal(g.kind,showcaseSession.goal));
    const stats = g.kind==='doudizhu'?[[table.hand_count,'Cards left'],[g.steps,'Turns']]:g.kind==='property_tycoon'?[[table.round+'/20','Round'],[table.cash[0],'Your cash']]:[[table.stacks[0],'Your chips'],[table.pot,'Pot']];
    el('sceneStats').innerHTML=JevPlayText.html(statMarkup(stats));
    el('showcaseOutcome').className=g.outcome?'win':'hidden';
    if(g.outcome) el('showcaseOutcome').textContent=g.kind==='doudizhu'&&['win','loss'].includes(g.outcome)?(g.outcome==='win'?tr('Landlord wins','地主获胜'):tr('Farmers win','农民获胜')):g.outcome==='draw'?tr('Draw','平局'):g.outcome==='budget_exhausted'?tr('Move limit reached','已达回合上限'):label(player(g.outcome==='win'?0:1))+tr(' wins',' 获胜');
    el('showcaseNew').textContent=JevPlayText.ui(g.outcome?'↻ Play again':'↻ Restart');
    el('showcaseFields').innerHTML=showcaseInputs(showcaseSession.input);
    // A seat handoff changes the table, not the completed decision receipt.
    if(g.handoff || g.outcome) {
      window.cardSelection=[]; window.updateCardAction=null;
      el('showcaseActions').replaceChildren();
      el('keyboardHint').textContent='';
    } else renderControls(table);
    PlayDraw.draw(table);
    refresh(); return true;
  }
  document.addEventListener('DOMContentLoaded',()=>{
    const row=document.createElement('div');row.id='participantControls';row.className='participant-controls';row.hidden=true;
    for(const [index,id] of selectIds.entries()) {
      const select=document.createElement('select');select.id=id;
      select.onchange=async()=>{
        stop();const previous=seats[index],previousView=manualView;seats[index]=select.value;manualView=null;
        if(fixedViews.has(selectedPlay)&&showcaseSession?.session_id&&showcaseSession.world.kind===selectedPlay){
          showcaseBusy=true;showcaseControls(true);
          try{showcaseSession=await api('showcases/view',{session_id:showcaseSession.session_id,revision:showcaseSession.revision})}
          catch(e){seats[index]=previous;manualView=previousView;select.value=player(index);error(e)}finally{showcaseBusy=false}
        }
        if(isBoard())renderGame();
        else if(window.JevChessUI?.active())JevChessUI.restore();
        else if(showcaseSession)renderShowcaseGame();
        if(!isBoard())showcaseControls(false);
        refresh();
      };
      row.append(select);
    }
    const start=document.createElement('button');start.id='participantStart';start.type='button';start.onclick=toggle;row.append(start);
    el('connectionSettings').before(row);refresh();
  });
  window.JevI18n?.onChange(()=>{optionKey='';refresh()});
  return {isDuel,isBoard,actor,player,controller,ready,label,viewSeat,canAct,seatText,seatMarker,activeSeat,badges,newOptions,requestBody,requestModel,refresh,schedule,stop,toggle,reveal,renderSocial,get running(){return running}};
})();
