/* Reproducible game conditions. Seeds are UI metadata, never model observations. */
(() => {
  'use strict';
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en;
  const el = id => document.getElementById(id);
  let isBoard = false, shown = null;
  const randomSeed = () => crypto.getRandomValues(new Uint32Array(1))[0];
  function value() {
    const raw = el('playSeed').value.trim();
    if (!/^(0|[1-9][0-9]*)$/.test(raw)) throw Error(tr("Enter an integer seed from 0 to 4294967295.","种子请输入 0 到 4294967295 的整数。"));
    const seed = Number(raw);
    if (!Number.isSafeInteger(seed) || seed > 4294967295) throw Error(tr("Enter an integer seed from 0 to 4294967295.","种子请输入 0 到 4294967295 的整数。"));
    return seed;
  }
  // A seed is opt-in for this reset only; ordinary restarts and game changes
  // never inherit a previous seeded opening or a draft in the input field.
  function request(board = false, replay = false, mode = 'standard') {
    if (replay || mode === 'standard') return {};
    return {seed: value()};
  }
  function show(info, board = false, visible = true, mode = 'standard') {
    isBoard = board;
    el('playSeedTools').classList.toggle('hidden', !visible);
    if (!visible) return;
    if (info?.seed != null) el('playSeed').value = String(info.seed);
    shown={mode:info?.mode === 'dataset_replay' ? info.mode : mode,seed:el('playSeed').value};
    renderStatus();
  }
  function renderStatus(){
    if(!shown)return;
    el('playSeedStatus').textContent=shown.mode==='dataset_replay'?tr('Sample replay · Seed not applied','样例回放 · 种子未应用')
      :shown.mode==='standard'?tr('Standard start','标准开局'):tr('Seed ','种子 ')+shown.seed;
  }
  window.JevI18n?.onChange(renderStatus);
  function setBusy(disabled) {
    for (const id of ['playSeed','playSeedApply','playSeedRandom','playSeedStandard']) el(id).disabled = disabled;
  }
  async function restart(mode) {
    if (typeof busy !== 'undefined' && busy || typeof showcaseBusy !== 'undefined' && showcaseBusy) return;
    try {
      if (mode === 'random') el('playSeed').value = String(randomSeed());
      if (mode !== 'standard') value();
      if (typeof stopAuto === 'function') stopAuto();
      if (isBoard) await startGame(undefined, null, mode); else await newShowcase(null, mode);
    } catch (e) { if (typeof error === 'function') error(e); }
  }
  el('playSeed').value = String(randomSeed());
  el('playSeedApply').onclick = () => restart('seeded');
  el('playSeedRandom').onclick = () => restart('random');
  el('playSeedStandard').onclick = () => restart('standard');
  window.JevSeedUI = {request, show, setBusy};
})();
