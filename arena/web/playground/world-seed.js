/* Shared by the actual browser games and browser RL runner. Never part of an observation. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.JevWorldSeed=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const VERSION = 'world-seed-v1';
  function normalize(value) {
    if (value === undefined) return crypto.getRandomValues(new Uint32Array(1))[0];
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 0xffffffff)
      throw new RangeError('seed 必须是 0 到 4294967295 的整数');
    return value;
  }
  function stream(seed, domain) {
    let state = normalize(seed);
    for (const c of domain) state = Math.imul(state ^ c.charCodeAt(0), 16777619) >>> 0;
    return () => {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = Math.imul(state ^ (state >>> 15), 1 | state);
      t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function marioLayoutV1(seed) {
    const random = stream(seed, 'mario/map/v1'), shift = () => Math.floor(random() * 5) - 2;
    const pits = [20, 43, 66].map(x => x + shift());
    const pipes = [13, 34, 56, 78].map(x => x + shift());
    const bricks = [7, 27, 49, 73, 84].map(x => x + shift());
    // Same three width-three pits, four two-tile pipes, five enemies and two
    // mushrooms. Patrols stay on supported floor, never across a shifted pit.
    const patrols = [
      [17, pipes[0] + 2, pits[0] - 1],
      [30, pits[0] + 4, pipes[1] - 1],
      [39, pipes[1] + 3, pits[1] - 1],
      [60, pipes[2] + 3, pits[2] - 1],
      [82, pipes[3] + 3, 88],
    ].map(([x, a, b]) => [Math.max(a, Math.min(b, x)), a, b]);
    return {pits, pipes, bricks, patrols, mushrooms: [bricks[1] + 1, bricks[3] + 1],
      plantOffsets: pipes.map(() => Math.floor(random() * 180))};
  }

  const MARIO_REVISION = 'mario-map-v2-curriculum';
  const PROFILES = Object.freeze({
    easy: {width: [48, 64], pits: [1, 2], pipes: [1, 2], pitWidth: [1, 2],
      bricks: [3, 5], brickLength: 4, enemies: [1, 3], mushrooms: [3, 5]},
    medium: {width: [72, 88], pits: [2, 3], pipes: [2, 3], pitWidth: [2, 3],
      bricks: [4, 6], brickLength: 4, enemies: [3, 5], mushrooms: [2, 4]},
    hard: {width: [96, 128], pits: [3, 4], pipes: [4, 5], pitWidth: [3, 3],
      bricks: [5, 7], brickLength: 5, enemies: [5, 8], mushrooms: [1, 2]},
  });

  function legacyLayout(seed, revision) {
    const layout = marioLayoutV1(seed);
    return {...layout, width: 96, goalColumn: 91,
      pitWidths: layout.pits.map(() => 3), brickLengths: layout.bricks.map(() => 3),
      profile: 'legacy', generator_revision: revision};
  }

  function marioLayout(seed, options = {}) {
    seed = normalize(seed);
    if (!options || typeof options !== 'object' || Array.isArray(options))
      throw new TypeError('Mario layout options must be an object');
    if (Object.keys(options).some(key => key !== 'generator_revision'))
      throw new RangeError('Unknown Mario layout option');
    const revision = options.generator_revision === undefined ? MARIO_REVISION : options.generator_revision;
    if (revision === VERSION) return legacyLayout(seed, VERSION);
    if (revision !== MARIO_REVISION) throw new RangeError('Unknown Mario generator revision');
    const profile = ['easy', 'medium', 'hard', 'legacy'][seed % 4];
    if (profile === 'legacy') return legacyLayout(seed, MARIO_REVISION);
    const config = PROFILES[profile], random = stream(seed, 'mario/map/v2/curriculum');
    const integer = (a, b) => a + Math.floor(random() * (b - a + 1));
    const shuffle = values => {
      for (let i = values.length - 1; i > 0; i--) {
        const j = integer(0, i); [values[i], values[j]] = [values[j], values[i]];
      }
      return values;
    };
    const count = bounds => integer(bounds[0], bounds[1]);
    const hazards = shuffle([
      ...Array.from({length: count(config.pits)}, () => ({kind: 'pit', width: count(config.pitWidth)})),
      ...Array.from({length: count(config.pipes)}, () => ({kind: 'pipe', width: 2})),
    ]);
    // Every obstacle separates grounded rooms. Brick rooms reserve three empty
    // columns on either side of a group, leaving the original jump corridor
    // unobstructed. Other rooms still have a three-column landing platform.
    const roomCount = hazards.length + 1;
    const brickCount = integer(config.bricks[0], Math.min(config.bricks[1], roomCount));
    const brickRooms = new Set(shuffle(Array.from({length: roomCount}, (_, i) => i)).slice(0, brickCount));
    const roomWidths = Array.from({length: roomCount}, (_, i) => brickRooms.has(i) ? 8 : 3);
    const minimumWidth = 4 + 5 + hazards.reduce((sum, h) => sum + h.width, 0)
      + roomWidths.reduce((sum, w) => sum + w, 0);
    const width = integer(Math.max(config.width[0], minimumWidth), config.width[1]);
    for (let spare = width - minimumWidth; spare > 0; spare--)
      roomWidths[integer(0, roomCount - 1)]++;
    const layout = {pits: [], pipes: [], bricks: [], patrols: [], mushrooms: [], plantOffsets: [],
      width, goalColumn: width - 5, pitWidths: [], brickLengths: [], profile,
      generator_revision: MARIO_REVISION};
    const rooms = [];
    let cursor = 4;
    for (let i = 0; i < roomCount; i++) {
      const end = cursor + roomWidths[i] - 1;
      rooms.push({start: cursor, end});
      if (brickRooms.has(i)) {
        const length = integer(2, Math.min(config.brickLength, roomWidths[i] - 6));
        layout.bricks.push(integer(cursor + 3, end - 2 - length));
        layout.brickLengths.push(length);
      }
      cursor = end + 1;
      if (i < hazards.length) {
        const hazard = hazards[i];
        if (hazard.kind === 'pit') {
          layout.pits.push(cursor); layout.pitWidths.push(hazard.width);
        } else {
          layout.pipes.push(cursor); layout.plantOffsets.push(integer(0, 179));
        }
        cursor += hazard.width;
      }
    }
    // Each patrol stays within one grounded room, with a full tile of margin
    // at both ends. Never put an enemy in the initial spawn room.
    const enemyCount = integer(config.enemies[0], Math.min(config.enemies[1], hazards.length));
    for (const i of shuffle(Array.from({length: hazards.length}, (_, j) => j + 1)).slice(0, enemyCount)) {
      const room = rooms[i], a = room.start + 1, b = room.end - 1;
      layout.patrols.push([integer(a, b), a, b]);
    }
    layout.patrols.sort((left, right) => left[0] - right[0]);
    const mushroomCount = integer(config.mushrooms[0], Math.min(config.mushrooms[1], brickCount));
    layout.mushrooms = shuffle(layout.bricks.map(x => x + 1)).slice(0, mushroomCount).sort((a, b) => a - b);
    return layout;
  }
  const TERRAMAI_REVISION = 'terramai-map-v2-diverse';
  function terramaiLayout(seed, options = {}) {
    seed = normalize(seed);
    if (!options || typeof options !== 'object' || Array.isArray(options))
      throw new TypeError('Terramai layout options must be an object');
    if (Object.keys(options).some(key => key !== 'generator_revision'))
      throw new RangeError('Unknown Terramai layout option');
    const revision = options.generator_revision === undefined ? TERRAMAI_REVISION : options.generator_revision;
    if (revision === VERSION) return {generator_revision: VERSION, profile: 'legacy'};
    if (revision !== TERRAMAI_REVISION) throw new RangeError('Unknown Terramai generator revision');
    const random = stream(seed, 'terraria/layout/v2');
    const integer = (a, b) => a + Math.floor(random() * (b - a + 1));
    const profile = ['foothills', 'caverns', 'ravines'][seed % 3];
    const surface = [], pits = [], platforms = [], enemySites = [];
    const base = integer(33, 47), segment = integer(14, 26);
    let start = base, target = base;
    for (let x = 0; x < 240; x++) {
      if (x % segment === 0) {start = target; target = integer(28, 55);}
      surface.push(Math.round(start + (target - start) * (x % segment) / segment));
    }
    // Vary actual surface depressions, not a private visual decoration. All
    // walls remain ordinary diggable material; bottom bedrock is untouched.
    const pitCount = integer(profile === 'ravines' ? 5 : 2, profile === 'ravines' ? 9 : 5);
    for (let i = 0; i < pitCount; i++) {
      const x = integer(20, 214), width = integer(2, 5), depth = integer(4, profile === 'ravines' ? 10 : 7);
      if (pits.some(p => x < p.x + p.width + 5 && x + width + 5 > p.x)) continue;
      pits.push({x, width, depth});
      for (let dx = 0; dx < width; dx++) surface[x + dx] = Math.min(68, surface[x + dx] + depth);
    }
    for (let x = 2; x <= 9; x++) surface[x] = base; // stable spawn footing and headroom
    const platformCount = integer(2, 7);
    for (let i = 0; i < platformCount; i++) {
      const x = integer(16, 215), width = integer(3, 7);
      if (platforms.some(p => x < p.x + p.width + 3 && x + width + 3 > p.x)) continue;
      const y = Math.max(16, Math.min(...surface.slice(x, x + width)) - integer(4, 7));
      platforms.push({x, width, y});
    }
    const enemyCount = integer(2, 5);
    for (let i = 0; i < enemyCount; i++)
      enemySites.push({x: integer(22 + i * 34, 48 + i * 34), kind: random() < .6 ? 'slime' : 'zombie'});
    return {generator_revision: TERRAMAI_REVISION, profile, surface, pits, platforms, enemySites,
      caveCount: integer(profile === 'caverns' ? 34 : 20, profile === 'caverns' ? 48 : 34),
      treeChance: integer(3, 10) / 100, oreScale: integer(70, 145) / 100,
      chestCount: integer(4, 10), lavaCount: integer(8, 22), miasmaCount: integer(1, 5),
      surfaceFoodCount: integer(6, 14)};
  }
  // Layout identity stays outside public observations. Physics/play streams
  // and the exact legacy map generator remain available for historical replay.
  return Object.freeze({version: VERSION, normalize, stream, marioLayoutV1, marioLayout, terramaiLayout});
});
