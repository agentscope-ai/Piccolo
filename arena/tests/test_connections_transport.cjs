/* Run with node --test tests/test_connections_transport.cjs; no network or model required. */
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/connections-transport.js'), 'utf8');
function load(fetch = () => { throw Error('Unexpected request'); }) {
  const context = {URL, AbortController, setTimeout, clearTimeout, fetch, document: {baseURI: 'https://jev.example/app/'}};
  vm.createContext(context); vm.runInContext(source, context);
  return context.JevConnectionTransport;
}
const request = id => ({schema_version: 'jev.decision.v1', request_id: id, model: 'served-model', game: 'test', observation: {turn: 1}, question: {id: 'turn', instructions: 'Choose', options: [{id: 'left', label: 'Left'}, {id: 'right', label: 'Right'}]}});
const result = id => ({schema_version: 'jev.decision.v1', request_id: id, model: 'served-model', action: 'left', probabilities: {left: 0.6, right: 0.4}, usage: {total_tokens: 9}});
const json = data => ({ok: true, status: 200, json: async () => data});
const until = async predicate => { for (let n = 0; n < 100; n++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 10)); } throw Error('Condition timed out'); };
function never(signal) { return new Promise((resolve, reject) => { if (signal.aborted) reject(Error('aborted')); else signal.addEventListener('abort', () => reject(Error('aborted')), {once: true}); }); }

test('complete endpoint rejects embedded credentials, query and fragments', () => {
  const t = load(); assert.equal(t.endpoint('https://model.example/v1/chat/completions'), 'https://model.example/v1/chat/completions');
  for (const value of ['file:///tmp/model', 'javascript:alert(1)', 'https://user:secret@model.example/api', 'https://model.example/api?key=secret', 'https://model.example/api#secret']) assert.throws(() => t.endpoint(value), /invalid_endpoint/);
});
test('decision response requires exact identity and legal action', () => {
  const t = load(); assert.equal(t.validateResult(request('a'), result('a')).action, 'left');
  for (const bad of [{...result('b')}, {...result('a'), model: 'different'}, {...result('a'), action: 'illegal'}, {...result('a'), unexpected: 'field'}]) assert.throws(() => t.validateResult(request('a'), bad), /invalid_response/);
});
test('partial, invalid or unnormalized measured probabilities are rejected', () => {
  const t = load();
  for (const probabilities of [{left: 1}, {left: 0.5, right: 0.4}, {left: 2, right: -1}, {left: NaN, right: 1}, {left: '0.5', right: 0.5}]) assert.throws(() => t.validateResult(request('a'), {...result('a'), probabilities}), /invalid_response/);
});
test('OpenAI transport ignores self-reported confidence and verifies model', () => {
  const t = load();
  const payload = t.payloadFor(request('a'), {adapter: 'openai', json_mode: false});
  assert.equal(payload.model, 'served-model'); assert.equal(payload.response_format, undefined); assert.equal(payload.stream, false);
  const answer = {model: 'served-model', choices: [{message: {content: '{"action":"left","probabilities":{"left":1,"right":0}}'}}], usage: {total_tokens: 3, details: {cached: 1}}};
  const decoded = t.decode(request('a'), {adapter: 'openai'}, answer);
  assert.equal(decoded.probabilities, null); assert.equal(decoded.usage.total_tokens, 3); assert.equal(decoded.usage.details, undefined);
  assert.throws(() => t.decode(request('a'), {adapter: 'openai'}, {...answer, model: 'alias'}), /invalid_response/);
});
test('all browser models share a 32-request limit and never send keys to relay endpoints', async () => {
  let active = 0, max = 0, dispatched = 0;
  const reported = [], releases = [], polled = new Set();
  const t = load(async (url, options) => {
    const uri = new URL(url);
    if (uri.hostname === 'model.example') {
      assert.equal(options.credentials, 'omit'); assert.equal(options.headers.Authorization, 'Bearer test-only-secret');
      const req = JSON.parse(options.body); active++; dispatched++; max = Math.max(max, active);
      await new Promise(resolve => releases.push(resolve)); active--; return json(result(req.request_id));
    }
    assert.equal(uri.origin, 'https://jev.example');
    assert.equal(options.headers?.Authorization, undefined); assert.ok(!JSON.stringify(options).includes('test-only-secret'));
    if (uri.pathname.endsWith('/requests')) {
      if (polled.has(uri.pathname)) return never(options.signal);
      polled.add(uri.pathname); return json({requests: Array.from({length: 20}, (_, i) => request(uri.pathname + i))});
    }
    reported.push(JSON.parse(options.body)); return json({accepted: true});
  });
  const config = {served_model: 'served-model', adapter: 'decision', endpoint: 'https://model.example/decide', api_key: 'test-only-secret', timeout_seconds: 5};
  const first = t.createBridge({...config, model_id: 'first'}), second = t.createBridge({...config, model_id: 'second'});
  try {
    await until(() => active === 32); assert.equal(dispatched, 32); releases.splice(0).forEach(release => release());
    await until(() => dispatched === 40); releases.splice(0).forEach(release => release());
    await until(() => reported.length === 40); assert.equal(max, 32); assert.ok(reported.every(body => body.result?.action === 'left'));
  } finally { first.stop(); second.stop(); }
});
test('bridge sanitizes upstream failures without returning provider body', async () => {
  let polled = false; const reports = [];
  const t = load(async (url, options) => {
    const uri = new URL(url);
    if (uri.hostname === 'model.example') return {ok: false, status: 401, json: async () => ({detail: 'private provider error'})};
    if (uri.pathname.endsWith('/requests')) { if (polled) return never(options.signal); polled = true; return json({requests: [request('failed')]}); }
    reports.push(JSON.parse(options.body)); return json({accepted: true});
  });
  const bridge = t.createBridge({model_id: 'one', served_model: 'served-model', adapter: 'decision', endpoint: 'https://model.example/decide', timeout_seconds: 5});
  try { await until(() => reports.length === 1); assert.equal(reports[0].error, 'connection_failed'); assert.equal(reports[0].request_id, 'failed'); assert.ok(!JSON.stringify(reports).includes('private')); }
  finally { bridge.stop(); }
});
test('timeout returns the bounded timeout code', async () => {
  let polled = false; const reports = [];
  const t = load(async (url, options) => {
    const uri = new URL(url);
    if (uri.hostname === 'model.example') return never(options.signal);
    if (uri.pathname.endsWith('/requests')) { if (polled) return never(options.signal); polled = true; return json({requests: [request('slow')]}); }
    reports.push(JSON.parse(options.body)); return json({accepted: true});
  });
  const bridge = t.createBridge({model_id: 'slow', served_model: 'served-model', adapter: 'decision', endpoint: 'https://model.example/decide', timeout_seconds: 0.02});
  try { await until(() => reports.length === 1); assert.equal(reports[0].error, 'timeout'); }
  finally { bridge.stop(); }
});

test('a proxy transport cannot be created and the game origin cannot receive a model key', () => {
  let requests = 0;
  const t = load(() => { requests++; throw Error('Unexpected request'); });
  const config = {model_id: 'forbidden', served_model: 'served-model', adapter: 'openai', endpoint: 'https://model.example/v1/chat/completions', api_key: 'test-only-secret'};
  for (const transport of ['proxy', 'server', 'dsw', 'local', null]) assert.throws(() => t.createBridge({...config, transport}), /unsupported_transport/);
  assert.throws(() => t.createBridge({...config, transport: 'browser', endpoint: 'https://jev.example/api/v1/decisions'}), /same_origin_endpoint/);
  assert.equal(requests, 0);
});
