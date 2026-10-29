const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../web/playground/environment-seed-ui.js'), 'utf8');
const controlIds = ['playSeed', 'playSeedApply', 'playSeedRandom', 'playSeedStandard'];

function load() {
  const controls = Object.fromEntries(controlIds.map(id => [id, {disabled: false, value: ''}]));
  const workspaceStates = [];
  const context = vm.createContext({
    window: {JevPlayWorkspace: {setBusy(value) { workspaceStates.push(value); }}},
    document: {getElementById(id) {
      assert.ok(controls[id], `Unexpected element: ${id}`);
      return controls[id];
    }},
    crypto: {getRandomValues(values) { return values.fill(12345); }},
  });
  // Match the separate scripts' shared lexical bindings, rather than window properties.
  vm.runInContext(`let busy = false, showcaseBusy = false;
    globalThis.setRequests = (board, showcase) => { busy = board; showcaseBusy = showcase; };`, context);
  vm.runInContext(source, context, {filename: 'environment-seed-ui.js'});
  return {
    setRequests: context.setRequests,
    setBusy: context.window.JevSeedUI.setBusy,
    assertLocked(expected) {
      assert.equal(workspaceStates.at(-1), expected, 'workspace switcher and browse button');
      for (const id of controlIds) assert.equal(controls[id].disabled, expected, id);
    },
  };
}

for (const [name, board, showcase] of [['board', true, false], ['showcase', false, true]]) {
  test(`${name} request cannot be unlocked by the idle renderer; completion restores controls`, () => {
    const ui = load();
    ui.setRequests(board, showcase);
    ui.setBusy(true);
    ui.assertLocked(true);

    // A health or language redraw of the other game family reports false.
    ui.setBusy(false);
    ui.assertLocked(true);

    ui.setRequests(false, false);
    ui.setBusy(false);
    ui.assertLocked(false);
  });
}

test('finishing one of two requests keeps controls locked until the other finishes', () => {
  const ui = load();
  ui.setRequests(true, true);
  ui.setBusy(true);
  ui.assertLocked(true);
  ui.setRequests(false, true);
  ui.setBusy(false);
  ui.assertLocked(true);
  ui.setRequests(false, false);
  ui.setBusy(false);
  ui.assertLocked(false);
});

test('an explicit request-start lock applies before shared flags change', () => {
  const ui = load();
  ui.setBusy(true);
  ui.assertLocked(true);
  ui.setBusy(false);
  ui.assertLocked(false);
});
