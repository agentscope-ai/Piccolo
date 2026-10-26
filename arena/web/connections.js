/* Display aliases only. IDs, checkpoint identities and scoring records stay intact. */
window.JevModelLabels=(()=>{
 const tr=(en,zh)=>window.JevI18n?.t(en,zh)??en;
 // These are the user's release names, not dates inferred from filenames.
 // Both legacy SFT checkpoints are registered under the 20261010 directory.
 const releases={
  'oneshot27b-100k-iter999':{name:'Blink 27B SFT-1012',step:1000},
  'oneshot27b-100k-iter1971':{name:'Blink 27B SFT-1012',step:1972},
  'oneshot27b-gameplay-terminal-rl4':{name:'Blink 27B RL-1012'},
  'oneshot27b-control-reviewed-sft-iter310':{name:'Blink 27B SFT-1015'},
  'oneshot27b-game-rl-native-iter17':{name:'Blink 27B RL-1019-iter17'}
 };
 const families={'qwen3.6-35b-a3b':'Qwen3.6 35B-A3B','qwen3.8-27b':'Qwen3.8 27B','qwen3.8-max':'Qwen3.8 Max'};
 const text=value=>typeof value==='string'?value:'';
 function model(id,fallback,identity){
  const record=id&&typeof id==='object'?id:null;
  if(record){identity=identity||record.model_identity||record.identity||record;fallback=fallback??record.name??record.model;id=record.id??record.model_key??record.model_id??record.source_model;}
  if(fallback&&typeof fallback==='object'){identity=identity||fallback;fallback=undefined;}
  const supplied=identity&&typeof identity==='object'?identity:{};
  const info=supplied.model_identity||supplied.identity||supplied;
  const keys=[id,info.source_model,info.model_key,info.model_id,info.requested_model,info.served_model].map(text).filter(Boolean).map(value=>value.toLowerCase());
  const fallbackLabel=(text(fallback)||text(record?.name)||text(record?.model)||text(id)||tr('Unknown model','未知模型')).replace(/QwenJev|OneShot/gi,'Blink');
  const provider=text(info.provider||supplied.provider).toLowerCase();
  const path=text(info.model_path||info.checkpoint||info.checkpoint_path||supplied.checkpoint).toLowerCase();
  let release=keys.map(key=>releases[key]).find(Boolean);
  // Explicit recorded training generations may also identify archived rows whose ID differs.
  const newGeneration=path.match(/(?:^|\/)jev_(sft|rl)_27b_[^/]*_20261015(?:-v\d+)?\//);
  if(newGeneration)release={name:'Blink 27B '+newGeneration[1].toUpperCase()+'-1015'};
  else if(/(?:^|\/)jev_rl_27b_gameplay_20261012\//.test(path))release={name:'Blink 27B RL-1012'};
  else if(!release&&/(?:^|\/)jev_sft_27b_100k_20261010\//.test(path)){
   const iter=path.match(/\/iter_(0000999|0001971)_hf(?:\/|$)/);
   release={name:'Blink 27B SFT-1012',...(iter?{step:Number(iter[1])+1}:{})};
  }
  const fromId=keys.some(key=>key.startsWith('dashscope-')||key.endsWith('-dashscope'))?'dashscope'
    :keys.some(key=>key in releases||key==='qwen3.8-27b-base'||key==='qwen3.6-35b-a3b-base')||release?'local':'';
  const source=provider==='dashscope'?'dashscope':['local','local_sglang','sglang','vllm'].includes(provider)?'local'
    :provider==='official'||keys.includes('jev-official')?'official':fromId;
  const suffix=source==='dashscope'?' · DashScope':source==='local'?tr(' · Local',' · 本地'):source==='official'?' · API':'';
  if(release)return release.name+(release.step?tr(' · step '+release.step,' · '+release.step+' 步'):'')+suffix;
  if(keys.includes('rule-engine-v1')||provider==='rule_engine')return tr('Rule engine','规则引擎');
  for(const key of keys){const family=families[key.replace(/^dashscope-/,'').replace(/-dashscope$/,'').replace(/-base$/,'')];if(family&&source)return family+suffix;}
  if(source==='official')return fallbackLabel==='jev-official'? 'Jev API':fallbackLabel;
  return fallbackLabel;
 }
 return {model};
})();
/* Temporary, browser-owned connections. No credentials are written to storage. */
window.ConnectUI = (() => {
  'use strict';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const get = id => document.getElementById(id);
  const bridges = new Map();
  // Retain only opaque model IDs from older deployments, never filesystem paths.
  try { const remembered = localStorage.getItem('jev_demo_model'); if (remembered && !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$/.test(remembered)) localStorage.removeItem('jev_demo_model'); } catch { /* Storage may be disabled. */ }
  let models = [], lastHealth = null, revision = 0, working = false, messageState = null;
  const headers = model => model ? {'X-Demo-Model': model} : {};
  const selectedModel = () => typeof modelName === 'undefined' ? get('modelSelect')?.value || '' : modelName;
  const activeWork = () => working || (typeof busy !== 'undefined' && busy) || (typeof batchRunning !== 'undefined' && batchRunning) || (typeof showcaseBusy !== 'undefined' && showcaseBusy);
  const modelLabel = model => model.transport ? (model.name || model.id) : window.JevModelLabels.model(model.id, model.name, model);
  const messages = {
    loading: ['Loading connections…', '正在读取连接…'],
    saving: ['Connecting…', '正在连接…'],
    connected: ['Connected. Select a game to use this model.', '已连接，选择游戏即可使用此模型。'],
    disconnected: ['Connection removed. Its key has been cleared.', '连接已移除，密钥已清除。'],
    invalid_endpoint: ['Enter a complete HTTP(S) endpoint without credentials, query parameters or a fragment.', '请输入完整 HTTP(S) 接口地址，不含账号密码、查询参数或锚点。'],
    same_origin_endpoint: ['Use a model API on a separate origin from this game site.', '请使用与游戏站点独立的模型接口地址，避免向游戏服务器发送密钥。'],
    invalid_model: ['Fill in the model ID, display name and exact served model.', '请填写模型 ID、展示名和实际服务模型名。'],
    invalid_id: ['Model ID may contain letters, digits, dots, underscores and hyphens; start with a letter or digit.', '模型 ID 只能包含字母、数字、点、下划线和连字符，并以字母或数字开头。'],
    invalid_timeout: ['Timeout must be between 1 and 600 seconds.', '超时应在 1 至 600 秒之间。'],
    invalid_key: ['API keys cannot contain line breaks, control characters or non-ASCII characters.', 'API key 不能包含换行、控制字符或非 ASCII 字符。'],
    conflict: ['This model ID is already connected. Disconnect it first or use another ID.', '该模型 ID 已有连接，请先断开或使用其他 ID。'],
    active_evaluation: ['Pause the active evaluation before disconnecting this model.', '请先暂停正在运行的评测，再断开此模型。'],
    forbidden: ['This browser cannot manage that connection.', '当前浏览器无法管理该连接。'],
    invalid_request: ['The connection settings were rejected. Check the fields and try again.', '连接参数未通过校验，请检查填写内容。'],
    connection_failed: ['Connection unavailable. Check the service, network and CORS settings for browser mode.', '连接不可用，请检查服务、网络，以及浏览器直连所需的跨域设置。'],
    report_failed: ['A model result could not reach the game server. Check the connection.', '模型结果未能送达游戏服务器，请检查网络连接。'],
    bridge_disconnected: ['The browser connection has expired. Connect again to use the model.', '浏览器连接已失效，请重新连接后使用模型。'],
    wait: ['Wait for the current action to finish.', '请等待当前操作结束。']
  };
  function message(code, bad = false) {
    messageState = code ? {code, bad} : null;
    const box = get('connectionMessage');
    if (!box) return;
    box.textContent = code ? tr(...(messages[code] || messages.connection_failed)) : '';
    box.classList.toggle('is-error', bad);
  }
  async function request(path = '', body, method, signal) {
    let response;
    try {
      response = await fetch('./api/v1/connections' + path, {method: method || (body === undefined ? 'GET' : 'POST'), credentials: 'same-origin', cache: 'no-store', signal, ...(body !== undefined ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});
    } catch { throw Object.assign(new Error('connection_failed'), {code: 'connection_failed'}); }
    if (!response.ok) throw Object.assign(new Error('connection_failed'), {code: response.status === 409 ? (method === 'DELETE' ? 'active_evaluation' : 'conflict') : response.status === 403 ? 'forbidden' : response.status === 422 ? 'invalid_request' : 'connection_failed'});
    if (response.status === 204) return {};
    try { return await response.json(); } catch { throw Object.assign(new Error('connection_failed'), {code: 'connection_failed'}); }
  }
  function renderConnections() {
    const list = get('connectedModels');
    if (!list) return;
    list.replaceChildren();
    if (!models.length) {
      const empty = document.createElement('p'); empty.className = 'connection-empty';
      empty.textContent = tr('No model connected. You can still play manually.', '尚未连接模型，可以先手动试玩。'); list.append(empty); return;
    }
    for (const model of models) {
      const row = document.createElement('div'); row.className = 'connected-model';
      const info = document.createElement('div'); info.className = 'connected-model-info';
      const name = document.createElement('strong'); name.textContent = modelLabel(model);
      const detail = document.createElement('span'); detail.textContent = model.id + ' · ' + tr('Browser direct', '浏览器直连') + (model.ready === false ? tr(' · Reconnect', ' · 需重连') : '');
      info.append(name, detail);
      const use = document.createElement('button'); use.type = 'button'; use.className = 'connection-use';
      use.textContent = model.id === selectedModel() ? tr('Selected', '已选择') : tr('Use', '使用');
      use.disabled = working || model.id === selectedModel();
      use.onclick = async () => { if (activeWork()) { message('wait', true); return; } await chooseModel(model.id); renderConnections(); };
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'connection-remove';
      remove.textContent = tr('Disconnect', '断开'); remove.disabled = working;
      remove.setAttribute('aria-label', tr('Disconnect ', '断开 ') + modelLabel(model));
      remove.onclick = () => disconnect(model.id);
      row.append(info, use, remove); list.append(row);
    }
  }
  function fields() {
    get('connectionStorageNote').textContent = tr('The browser calls your model API directly. Endpoint and key stay in this page’s memory. Reconnect after refreshing; the API must allow CORS.', '浏览器直接调用模型接口，地址和密钥仅留在当前页面内存。刷新后需重新连接，接口需允许跨域。');
    get('connectionJsonModeRow').hidden = get('connectionAdapter').value !== 'openai';
    get('connectionEndpoint').placeholder = get('connectionAdapter').value === 'openai' ? 'https://your-model.example/v1/chat/completions' : 'https://your-model.example/decide';
  }
  function lock(value) {
    working = value;
    get('connectionForm').setAttribute('aria-busy', String(value));
    for (const control of get('connectionForm').querySelectorAll('input, select, button')) control.disabled = value;
    renderConnections();
  }
  function clearKey() { const field = get('connectionApiKey'); field.value = ''; field.type = 'password'; get('showConnectionKey').textContent = tr('Show', '显示'); }
  async function refresh() {
    const result = await request();
    const fresh = Array.isArray(result) ? result : (result.models || result.connections || []);
    if (!Array.isArray(fresh)) throw Object.assign(new Error('connection_failed'), {code: 'connection_failed'});
    models = fresh;
    for (const [id, bridge] of bridges) if (!models.some(model => model.id === id)) { bridge.stop(); bridges.delete(id); }
    renderConnections();
  }
  async function open() {
    if (working) return;
    clearKey(); message(''); fields(); renderConnections();
    if (!get('connectionDialog').open) get('connectionDialog').showModal();
    try { await refresh(); } catch (error) { message(error.code, true); }
  }
  function close() { if (!working) { clearKey(); get('connectionDialog').close(); } }
  async function chooseModel(id) {
    revision++;
    if (typeof switchModel === 'function') await switchModel(id);
    else { get('modelSelect').value = id; if (typeof health === 'function') await health(); }
  }
  function syncModels(healthData) {
    lastHealth = healthData;
    models = Array.isArray(healthData.models) ? healthData.models : [];
    const top = get('modelSelect'), current = selectedModel();
    for (const model of models) if (typeof modelChoices !== 'undefined') modelChoices[model.id] = modelLabel(model);
    let saved = ''; try { saved = localStorage.getItem('jev_demo_model') || ''; } catch { /* Storage can be unavailable in private browsing. */ }
    const desired = [current, saved, healthData.default_model, models[0]?.id].find(id => id && models.some(model => model.id === id)) || '';
    top.replaceChildren(...(models.length ? models.map(model => new Option(modelLabel(model), model.id)) : [new Option(tr('Manual play · Connect a model', '手动试玩 · 可连接模型'), '')]));
    top.value = desired;
    top.disabled = !models.length || (typeof batchRunning !== 'undefined' && batchRunning);
    renderConnections();
    return desired;
  }
  async function save(event) {
    event.preventDefault();
    if (activeWork()) { message('wait', true); return; }
    const form = get('connectionForm'); if (!form.reportValidity()) return;
    const spec = {model_id: get('connectionModelId').value.trim(), name: get('connectionName').value.trim(), served_model: get('connectionServedModel').value.trim(), adapter: get('connectionAdapter').value, transport: 'browser', endpoint: get('connectionEndpoint').value.trim(), api_key: get('connectionApiKey').value.trim(), json_mode: get('connectionJsonMode').checked, timeout_seconds: Number(get('connectionTimeout').value)};
    if (!spec.model_id || !spec.name || !spec.served_model) { message('invalid_model', true); return; }
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$/.test(spec.model_id)) { message('invalid_id', true); return; }
    if (!Number.isFinite(spec.timeout_seconds) || spec.timeout_seconds < 1 || spec.timeout_seconds > 600) { message('invalid_timeout', true); return; }
    try { spec.endpoint = window.JevConnectionTransport.endpoint(spec.endpoint); } catch (error) { message(error.code === 'same_origin_endpoint' ? error.code : 'invalid_endpoint', true); return; }
    if (/[^\x20-\x7e]/.test(spec.api_key)) { message('invalid_key', true); return; }
    lock(true); message('saving');
    try {
      // Explicit metadata whitelist: endpoint and key never enter a same-origin request.
      const body = {model_id: spec.model_id, name: spec.name, served_model: spec.served_model,
        adapter: spec.adapter, transport: 'browser', json_mode: spec.json_mode, timeout_seconds: spec.timeout_seconds};
      await request('', body);
      bridges.set(spec.model_id, window.JevConnectionTransport.createBridge({...spec, onStatus: code => {
        if (code === 'disconnected') { bridges.delete(spec.model_id); revision++; }
        message(code === 'disconnected' ? 'bridge_disconnected' : code, true);
        if (typeof health === 'function') void health();
      }}));
      // Only the browser bridge owns these credentials.
      spec.api_key = ''; clearKey();
      await refresh(); lock(false); await chooseModel(spec.model_id); message('connected');
      get('connectionForm').reset(); fields(); get('connectionModelId').focus();
    } catch (error) { message(error.code || 'connection_failed', true); }
    finally { spec.api_key = ''; clearKey(); lock(false); }
  }
  async function disconnect(id) {
    if (activeWork()) { message('wait', true); return; }
    lock(true);
    try {
      await request('/' + encodeURIComponent(id), undefined, 'DELETE');
      bridges.get(id)?.stop(); bridges.delete(id); models = models.filter(model => model.id !== id);
      revision++; clearKey(); lock(false);
      if (selectedModel() === id) await chooseModel(models[0]?.id || '');
      else if (typeof health === 'function') await health();
      renderConnections(); message('disconnected');
    } catch (error) { message(error.code || 'connection_failed', true); }
    finally { lock(false); }
  }
  function repaintLocale() {
    if (!get('connectionDialog')) return;
    if (lastHealth) syncModels(lastHealth); else renderConnections();
    fields(); get('showConnectionKey').textContent = get('connectionApiKey').type === 'password' ? tr('Show', '显示') : tr('Hide', '隐藏');
    if (messageState) message(messageState.code, messageState.bad);
  }
  document.addEventListener('DOMContentLoaded', () => {
    get('connectionSettings').onclick = open;
    get('connectCancel').onclick = close;
    get('connectionForm').onsubmit = save;
    get('connectionAdapter').onchange = fields;
    get('connectionDialog').addEventListener('cancel', event => { if (working) event.preventDefault(); else clearKey(); });
    get('connectionDialog').addEventListener('close', clearKey);
    get('showConnectionKey').onclick = () => { const field = get('connectionApiKey'); field.type = field.type === 'password' ? 'text' : 'password'; get('showConnectionKey').textContent = field.type === 'password' ? tr('Show', '显示') : tr('Hide', '隐藏'); };
    fields(); renderConnections();
  });
  window.addEventListener('pagehide', () => { for (const bridge of bridges.values()) bridge.stop(); bridges.clear(); clearKey(); });
  window.JevI18n?.onChange(repaintLocale);
  return {headers, syncModels, modelLabel, open, get provider() { return 'custom'; }, get revision() { return revision; }, get configured() { return models.some(model => model.id === selectedModel() && model.ready !== false); }};
})();
