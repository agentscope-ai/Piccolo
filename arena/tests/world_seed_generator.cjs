/* Pure JS: the production generator, frozen v1 fixtures, and geometry invariants. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = path.join(__dirname, '../web/playground/world-seed.js');
const context = {window: {}, crypto: {getRandomValues: array => (array[0] = 123456, array)}};
vm.runInNewContext(fs.readFileSync(source, 'utf8'), context, {filename: source});
const api = context.window.JevWorldSeed;
const plain = value => JSON.parse(JSON.stringify(value));
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'world_seed_generator_v1.json')));
const oldFields = ['pits', 'pipes', 'bricks', 'patrols', 'mushrooms', 'plantOffsets'];
const geometry = layout => JSON.stringify([layout.width, layout.goalColumn, layout.pits,
  layout.pitWidths, layout.pipes, layout.bricks, layout.brickLengths, layout.patrols, layout.mushrooms]);
for (const fixture of fixtures.layouts) {
  assert.deepEqual(plain(api.marioLayoutV1(fixture.seed)), fixture.layout);
  const replay = api.marioLayout(fixture.seed, {generator_revision: 'world-seed-v1'});
  assert.equal(replay.generator_revision, 'world-seed-v1');
  assert.equal(replay.width, 96); assert.equal(replay.goalColumn, 91);
  for (const key of oldFields) assert.deepEqual(plain(replay[key]), fixture.layout[key]);
}
for (const fixture of fixtures.streams) {
  const random = api.stream(fixture.seed, fixture.domain);
  assert.deepEqual(Array.from({length: fixture.values.length}, () => random()), fixture.values);
}
assert.equal(api.normalize(undefined), 123456);
for (const value of [-1, 0x100000000, 1.5, '1', null, NaN, Infinity]) {
  assert.throws(() => api.normalize(value));
  assert.throws(() => api.marioLayout(value));
}
for (const options of [null, [], 1, 'legacy', {generator_revision: 'unknown'},
  {generator_revision: null}, {generator_revision: 1}, {profile: 'easy'}])
  assert.throws(() => api.marioLayout(0, options));

const ranges = {
  easy: {width: [48,64], pits: [1,2], pipes: [1,2], patrols: [1,3], bricks: [3,5], mushrooms: [3,5], pitWidth: [1,2], brickLength: [2,4]},
  medium: {width: [72,88], pits: [2,3], pipes: [2,3], patrols: [3,5], bricks: [4,6], mushrooms: [2,4], pitWidth: [2,3], brickLength: [2,4]},
  hard: {width: [96,128], pits: [3,4], pipes: [4,5], patrols: [5,8], bricks: [5,7], mushrooms: [1,2], pitWidth: [3,3], brickLength: [2,5]},
};
const between = (value, range) => assert(value >= range[0] && value <= range[1], `${value} outside ${range}`);
const profiles = {};
function check(seed) {
  const layout = plain(api.marioLayout(seed)), repeated = plain(api.marioLayout(seed));
  assert.deepEqual(layout, repeated, `reset nondeterminism at ${seed}`);
  assert.equal(layout.profile, ['easy','medium','hard','legacy'][seed % 4]);
  assert.equal(layout.generator_revision, 'mario-map-v2-curriculum');
  assert.equal(layout.goalColumn, layout.width - 5);
  assert.equal(layout.pits.length, layout.pitWidths.length);
  assert.equal(layout.bricks.length, layout.brickLengths.length);
  assert.equal(layout.pipes.length, layout.plantOffsets.length);
  if (seed < 128 || seed >= 0x7fffffff) {
    const forcedOld = plain(api.marioLayout(seed, {generator_revision: 'world-seed-v1'}));
    const old = plain(api.marioLayoutV1(seed));
    for (const key of oldFields) assert.deepEqual(forcedOld[key], old[key]);
  }
  if (layout.profile === 'legacy') {
    const old = plain(api.marioLayoutV1(seed));
    for (const key of oldFields) assert.deepEqual(layout[key], old[key]);
    assert.equal(layout.width, 96);
  }
  const floor = Array(layout.width).fill(true), occupied = Array(layout.width).fill(false);
  for (let i = 0; i < layout.pits.length; i++) {
    const start = layout.pits[i], width = layout.pitWidths[i];
    assert(width >= 1 && width <= 3); // no pit wider than the original feasible jump
    assert(start >= 4 && start + width < layout.goalColumn);
    for (let x = start; x < start + width; x++) {
      assert(!occupied[x]); floor[x] = false; occupied[x] = true;
    }
  }
  for (const start of layout.pipes) {
    assert(start >= 4 && start + 2 < layout.goalColumn);
    for (let x = start; x < start + 2; x++) {
      assert(floor[x] && !occupied[x]); occupied[x] = true;
    }
  }
  assert(floor[2] && floor[3] && !occupied[2] && !occupied[3]);
  assert(floor[layout.goalColumn] && !occupied[layout.goalColumn]);
  for (const offset of layout.plantOffsets) assert(Number.isInteger(offset) && offset >= 0 && offset < 180);
  for (const [x, a, b] of layout.patrols) {
    assert(a <= x && x <= b && a >= 0 && b < layout.goalColumn);
    // A 26px enemy footprint is shorter than a 32px tile; all patrol columns
    // must have floor and must not intersect either tile of a pipe.
    for (let column = a; column <= b; column++) assert(floor[column] && !occupied[column]);
  }
  assert.equal(new Set(layout.mushrooms).size, layout.mushrooms.length);
  for (const column of layout.mushrooms) {
    assert(layout.bricks.some(start => start + 1 === column));
    // Legacy can place this block above a shifted pipe. Keep its exact old
    // geometry for replay; the new profiles must provide grounded approaches.
    if (layout.profile !== 'legacy')
      assert(floor[column] && !occupied[column], `mushroom has no grounded approach at seed ${seed}`);
  }
  if (layout.profile !== 'legacy') {
    const range = ranges[layout.profile];
    between(layout.width, range.width);
    for (const key of ['pits','pipes','patrols','bricks','mushrooms']) between(layout[key].length, range[key]);
    for (const width of layout.pitWidths) between(width, range.pitWidth);
    const brickColumns = new Set();
    for (let i = 0; i < layout.bricks.length; i++) {
      const start = layout.bricks[i], length = layout.brickLengths[i];
      between(length, range.brickLength);
      for (let column = start; column < start + length; column++) {
        assert(!brickColumns.has(column)); brickColumns.add(column);
      }
      for (let column = start - 3; column < start + length + 3; column++)
        assert(column >= 4 && column < layout.goalColumn && floor[column] && !occupied[column], 'blocked jump corridor');
    }
  }
  return layout;
}

for (let seed = 0; seed < 4096; seed++) {
  const layout = check(seed);
  if (seed < 128) {
    const stats = profiles[layout.profile] ||= {layouts: new Set(), width: new Set(), pits: new Set(), pipes: new Set(),
      patrols: new Set(), bricks: new Set(), mushrooms: new Set(), pitWidths: new Set(), brickLengths: new Set()};
    stats.layouts.add(geometry(layout)); stats.width.add(layout.width);
    for (const key of ['pits','pipes','patrols','bricks','mushrooms']) stats[key].add(layout[key].length);
    for (const width of layout.pitWidths) stats.pitWidths.add(width);
    for (const length of layout.brickLengths) stats.brickLengths.add(length);
  }
}
for (const seed of [0x7fffffff, 0x80000000, 0xfffffffc, 0xfffffffd, 0xfffffffe, 0xffffffff, 1194110000]) check(seed);
assert.equal(new Set(Array.from({length: 32}, (_, seed) => geometry(api.marioLayout(seed)))).size, 32);
for (const [name, stats] of Object.entries(profiles)) {
  assert.equal(stats.layouts.size, 32, `${name}: repeated geometry`);
  if (name !== 'legacy') for (const key of ['width','pits','pipes','patrols','bricks','mushrooms','brickLengths'])
    assert(stats[key].size >= 2, `${name}: ${key} did not vary`);
}
const mutable = api.marioLayout(0); mutable.pits[0] = 999; mutable.mushrooms.length = 0;
assert.notEqual(api.marioLayout(0).pits[0], 999); assert(api.marioLayout(0).mushrooms.length >= 3);
// Conservative jump reach: original vy=-10, gravity=.5, horizontal speed3.2.
let y = 0, vy = -10, frames = 0;
do { vy += .5; y += vy; frames++; } while (y < 0);
assert(frames * 3.2 > 3 * 32 + 23, 'original jump no longer spans the maximum generated pit');
const summary = {passed: true, seed_cases: 4096 + 7, distinct_first_32: 32,
  legacy_golden_cases: fixtures.layouts.length, prng_golden_cases: fixtures.streams.length,
  jump_reach_pixels: frames * 3.2,
  profiles: Object.fromEntries(Object.entries(profiles).map(([name, stats]) => [name,
    Object.fromEntries(Object.entries(stats).map(([key, values]) => [key, key === 'layouts' ? values.size : [...values].sort((a,b) => a-b)]))]))};
console.log(JSON.stringify(summary, null, 2));
