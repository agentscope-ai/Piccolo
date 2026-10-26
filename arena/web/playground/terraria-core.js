/* The original Terramai engine, shared by browser UI and Node rollouts.
 * No DOM, canvas, scheduler or model service belongs to this module.
 * Only snapshot()/prepare() project model-visible information. renderState()
 * is an explicit private UI projection and must never enter model input.
 */
(function(root, factory){
  if(typeof module==='object' && module.exports)module.exports=factory(require('./world-seed.js'));
  else root.JevTerramaiCore=factory(root.JevWorldSeed);
})(typeof globalThis!=='undefined'?globalThis:this, function(defaultSeedSource){
  'use strict';
  function create(options){
  options=options||{};
  var seedSource=options.seedSource||defaultSeedSource;
  if(!seedSource||typeof seedSource.normalize!=='function'||typeof seedSource.stream!=='function')
    throw new TypeError('Terramai requires the shared seed source');
  var now=options.now||(()=>performance.now());
  var isHidden=typeof options.visibility==='function'?options.visibility:()=>false;
  var tr=options.translate||((en)=>en);
  function hud(){if(options.onHud)options.onHud();}
  function clearKeys(){keys={};if(options.onClearKeys)options.onClearKeys();}
  /* ---------------- constants ---------------- */
  var TS = 16, WW = 240, WH = 100;
  var GRAV = 0.55, MAXFALL = 11, MOVE = 1.8, JUMP = 8.9;
  var AIR = 0, DIRT = 1, GRASS = 2, STONE = 3, COPPER = 4, IRON = 5, GOLD = 6, DIAMOND = 7,
      GEM = 8, WOOD = 9, LEAF = 10, BEDROCK = 11, GOAL = 12, CHEST = 13, LAVA = 14, MIASMA = 15;
  var SOLID = { 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 11: 1 };
  var HARD = { 1: 10, 2: 10, 3: 24, 4: 28, 5: 34, 6: 40, 7: 55, 8: 45, 9: 16, 10: 4 };
  var ORE_PTS = { 4: 1, 5: 2, 6: 3, 7: 5 };
  var ORE_NAME = { 4: "Copper", 5: "Iron", 6: "Gold", 7: "Diamond" };
  var BASECOL = { 1: "#6e4a28", 2: "#6e4a28", 3: "#6b6f76", 4: "#6b6f76", 5: "#6b6f76", 6: "#6b6f76",
                  7: "#5d6166", 8: "#5d6166", 9: "#5b3b22", 10: "#2f7d2a", 11: "#23252b", 12: "#ffd54a", 13: "#7a4a1e", 14: "#e2581f", 15: "#5d7a3a" };
  var NUG = { 4: "#c47a3a", 5: "#d8cfc0", 6: "#ffd24a", 7: "#6ee6f2", 8: "#b06ef2" };
  var MAPCOL = { 0: "#181c24", 1: "#6e4a28", 2: "#3e9e3a", 3: "#6b6f76", 4: "#c47a3a", 5: "#d8cfc0",
                 6: "#ffd24a", 7: "#6ee6f2", 8: "#b06ef2", 9: "#5b3b22", 10: "#2f7d2a", 11: "#0c0d10", 12: "#ffd54a", 13: "#e8a33d", 14: "#ff6a2a", 15: "#79a83f" };

  var world = new Uint8Array(WW * WH), explored = new Uint8Array(WW * WH), exploredCount = 0;
  function idx(x, y) { return y * WW + x; }
  function inb(x, y) { return x >= 0 && x < WW && y >= 0 && y < WH; }
  function get(x, y) { return inb(x, y) ? world[idx(x, y)] : BEDROCK; }
  function setT(x, y, v) { if (inb(x, y)) world[idx(x, y)] = v; }
  function isSolid(x, y) { return !!SOLID[get(x, y)]; }
  var jevAwaiting=false,episodeGeneration=0;
  var conditionSeed, mapRandom, playRandom, cosmeticRandom, generating=false, environmentLayout;
  function setSeed(seed,generationOptions) {
    conditionSeed=seedSource.normalize(seed);
    environmentLayout=seedSource.terramaiLayout(conditionSeed,generationOptions);
    mapRandom=seedSource.stream(conditionSeed,'terraria/map/v1');
    playRandom=seedSource.stream(conditionSeed,'terraria/play/v1');
    cosmeticRandom=seedSource.stream(conditionSeed,'terraria/cosmetic/v1');
  }
  setSeed(options.seed,options.generationOptions);
  function random() { return (generating ? mapRandom : playRandom)(); }
  function rnd(a, b) { return a + random() * (b - a); }
  function cosmeticRnd(a, b) { return a + cosmeticRandom() * (b - a); }

  /* ---------------- world generation (procedural + guaranteed solvable) ---------------- */
  var spawn = { x: 0, y: 0 }, goal = { x: 0, y: 0 }, surf = [], chests = [], clouds = [];
  function generate() {
    generating=true;
    world.fill(AIR); explored.fill(0); exploredCount = 0; surf = []; chests = [];
    var h = (WH * 0.40) | 0, x, y;
    for (x = 0; x < WW; x++) {
      if(environmentLayout.surface) h=environmentLayout.surface[x];
      else {
        if (random() < 0.35) h += random() < 0.5 ? -1 : 1;
        h += Math.round(Math.sin(x * 0.06) * 0.5);
        h = Math.max((WH * 0.26) | 0, Math.min((WH * 0.58) | 0, h));
      }
      surf[x] = h;
      for (y = h; y < WH; y++) {
        var t = (y === h) ? GRASS : (y < h + 4 ? DIRT : STONE);
        if (y >= WH - 2) t = BEDROCK;
        setT(x, y, t);
      }
      if (random() < (environmentLayout.treeChance||0.05) && x > 7 && x < WW - 4) {        // trees
        var th = 4 + (random() * 3 | 0), k, lx, ly;
        for (k = 1; k <= th; k++) setT(x, h - k, WOOD);
        for (lx = -2; lx <= 2; lx++) for (ly = -2; ly <= 0; ly++)
          if (Math.abs(lx) + Math.abs(ly + 1) < 3) setT(x + lx, h - th + ly, LEAF);
      }
    }
    var w, s, ox, oy;
    for (w = 0; w < (environmentLayout.caveCount||30); w++) {                                  // cave worms
      var cx = rnd(6, WW - 6), cy = rnd(WH * 0.42, WH - 4), ang = rnd(0, 6.28), len = rnd(30, 100);
      for (s = 0; s < len; s++) {
        ang += rnd(-0.4, 0.4); cx += Math.cos(ang); cy += Math.sin(ang) * 0.7;
        var r = rnd(1.2, 2.6);
        for (ox = -3; ox <= 3; ox++) for (oy = -3; oy <= 3; oy++) {
          var tx = (cx + ox) | 0, ty = (cy + oy) | 0;
          if (ox * ox + oy * oy <= r * r && inb(tx, ty) && get(tx, ty) !== BEDROCK && ty < WH - 2) setT(tx, ty, AIR);
        }
      }
    }
    for (var i = 0; i < world.length; i++) {                    // ore: rarer overall, gold/diamond richer with depth
      if (world[i] !== STONE) continue;
      var yy = (i / WW) | 0, xx = i % WW, d = yy - (surf[xx] || 0), rr = random();
      var df = Math.min(1, d / 55), oreScale=environmentLayout.oreScale||1;
      if (d > 2 && d < 22 && rr < 0.03*oreScale) world[i] = COPPER;
      else if (d > 8 && d < 40 && rr < 0.035*oreScale) world[i] = IRON;
      else if (d > 24 && rr < (0.012 + 0.05 * df)*oreScale) world[i] = GOLD;
      else if (d > 38 && rr < (0.008 + 0.055 * df)*oreScale) world[i] = DIAMOND;
      else if (d > 34 && rr < (0.01 + 0.03 * df)*oreScale) world[i] = GEM;
    }
    for (var tr = 0; tr < 500 && chests.length < (environmentLayout.chestCount||7); tr++) {     // treasure chests, denser toward the right
      var qx = rnd(12, WW - 6) | 0, qy = rnd(WH * 0.42, WH - 4) | 0;
      if (random() > Math.pow(qx / WW, 1.4)) continue;
      if (get(qx, qy) === AIR && get(qx, qy - 1) === AIR && get(qx, qy + 1) === STONE) {
        var far = true;
        for (var ci = 0; ci < chests.length; ci++) if (Math.abs(chests[ci].x - qx) < 18) far = false;
        if (far) { setT(qx, qy, CHEST); chests.push({ x: qx, y: qy }); }
      }
    }
    for (var lp = 0; lp < (environmentLayout.lavaCount||16); lp++) {                           // lava pools in the deep caves
      var lx0 = rnd(8, WW - 10) | 0, ly0 = rnd(WH * 0.62, WH - 4) | 0, span = 3 + (random() * 6 | 0);
      for (var ly2 = ly0 + 1; ly2 >= ly0; ly2--)
        for (var lx = lx0; lx < Math.min(WW - 2, lx0 + span); lx++)
          if (get(lx, ly2) === AIR && (isSolid(lx, ly2 + 1) || get(lx, ly2 + 1) === LAVA)) setT(lx, ly2, LAVA);
    }
    for (var mz = 0; mz < (environmentLayout.miasmaCount||3); mz++) {                            // miasma pockets: poison gas guarding rich veins
      var mcx = rnd(WW * 0.3, WW - 12) | 0, mcy = rnd(WH * 0.45, WH * 0.8) | 0, mr = 4 + (random() * 5 | 0);
      for (var my2 = mcy - mr; my2 <= mcy + mr; my2++) for (var mx2 = mcx - mr; mx2 <= mcx + mr; mx2++) {
        if (!inb(mx2, my2)) continue;
        if ((mx2 - mcx) * (mx2 - mcx) + (my2 - mcy) * (my2 - mcy) <= mr * mr && get(mx2, my2) === AIR) setT(mx2, my2, MIASMA);
      }
      for (var my3 = mcy - mr - 2; my3 <= mcy + mr + 2; my3++) for (var mx3 = mcx - mr - 2; mx3 <= mcx + mr + 2; mx3++) {   // poison vault: rich ore in the gas walls
        if (!inb(mx3, my3) || get(mx3, my3) !== STONE) continue;
        if ((mx3 - mcx) * (mx3 - mcx) + (my3 - mcy) * (my3 - mcy) <= (mr + 2) * (mr + 2) && random() < 0.22) {
          var rr2 = random();
          setT(mx3, my3, rr2 < 0.45 ? GOLD : (rr2 < 0.8 ? DIAMOND : GEM));
        }
      }
    }
    items.length = 0;
    for (var fi = 0; fi < (environmentLayout.surfaceFoodCount||9); fi++) {                            // surface snacks
      var fx2 = rnd(10, WW - 10) | 0, fk = ["apple", "apple", "meat", "shroom", "honey"][(random() * 5) | 0];
      spawnItem(fx2 * TS + 8, (surf[fx2] - 2) * TS, fk);
    }
    for (var fj = 0, fc = 0; fj < 200 && fc < 6; fj++) {        // cave mushrooms & honey
      var mx = rnd(10, WW - 10) | 0, my = rnd(WH * 0.45, WH - 4) | 0;
      if (get(mx, my) === AIR && isSolid(mx, my + 1)) { spawnItem(mx * TS + 8, my * TS + 4, random() < 0.7 ? "shroom" : "honey"); fc++; }
    }
    if(environmentLayout.surface) {
      // Usable spawn/guardian/gate footing after cave carving; no solved route.
      [5, (WW*.72)|0, WW-10, WW-3].forEach(function(cx){
        for(var ax=cx-2;ax<=cx+3;ax++)if(inb(ax,surf[ax])){
          for(var ay=surf[ax]-5;ay<surf[ax];ay++)setT(ax,ay,AIR);
          setT(ax,surf[ax],GRASS);setT(ax,surf[ax]+1,DIRT);
        }
      });
      environmentLayout.platforms.forEach(function(p){
        for(var ax=p.x;ax<p.x+p.width;ax++)setT(ax,p.y,GRASS);
      });
    }
    var sx = 5; spawn.x = sx * TS + 2; spawn.y = (surf[sx] - 3) * TS;
    for (var cy2 = surf[sx] - 5; cy2 < surf[sx]; cy2++) { setT(sx, cy2, AIR); setT(sx + 1, cy2, AIR); }
    var gx = WW - 3, gy = Math.max(2, (surf[WW - 3] || 40) - 1); // VICTORY GATE on the surface at the far right
    goal.x = gx; goal.y = gy;
    setT(gx, gy, GOAL); setT(gx, gy - 1, GOAL);
    ensureSolvable();
    clouds = [];
    for (var cl = 0; cl < 10; cl++) clouds.push({ x: cosmeticRnd(0, WW * TS), y: cosmeticRnd(20, 150), w: cosmeticRnd(60, 150), v: cosmeticRnd(0.08, 0.25) });
    generating=false;
  }
  /* BFS over non-bedrock (everything else diggable => reachable); carve tunnel as fallback */
  function ensureSolvable() {
    var stx = (spawn.x / TS) | 0, sty = (spawn.y / TS) | 0;
    var seen = new Uint8Array(WW * WH), q = [idx(stx, sty)]; seen[q[0]] = 1;
    for (var qi = 0; qi < q.length; qi++) {
      var c = q[qi], cx = c % WW, cy = (c / WW) | 0;
      var xs = [cx + 1, cx - 1, cx, cx], ys = [cy, cy, cy + 1, cy - 1];
      for (var n = 0; n < 4; n++) {
        if (inb(xs[n], ys[n])) {
          var ni = idx(xs[n], ys[n]);
          if (!seen[ni] && world[ni] !== BEDROCK) { seen[ni] = 1; q.push(ni); }
        }
      }
    }
    if (!seen[idx(goal.x, goal.y)]) {
      var x1 = stx, y1 = sty;
      while (x1 !== goal.x || y1 !== goal.y) {
        if (get(x1, y1) !== GOAL) setT(x1, y1, AIR);
        if (x1 < goal.x) x1++; else if (x1 > goal.x) x1--;
        else if (y1 < goal.y) y1++; else y1--;
      }
      setT(goal.x, goal.y, GOAL);
    }
  }

  /* ---------------- state ---------------- */
  var P = { x: 0, y: 0, w: 10, h: 20, vx: 0, vy: 0, ground: false, face: 1, hp: 100, maxhp: 100, inv: 0, dead: 0 };
  var gear = { pick: 1, sword: 1, armor: 0, gems: 0, pts: 0, dirt: 5, swordMul: 1, pickMul: 1, armorMul: 1, potAtk: 0, potArm: 0 };
  var enemies = [], drops = [], parts = [], msgs = [];
  var stat = { ore: 0, gem: 0, chest: 0, kill: 0 };
  function freshProgression() { return {revision:'terramai-progression-v1',ore_mined:0,ore_points_earned:0,
    player_attack_hits:0,player_attack_damage:0,player_kills:0,player_direct_kills:0,
    ordinary_player_kills:0,player_boss_kills:0,guardian_player_kills:0,
    environment_assisted_kills:0,combat_points_earned:0,death_count:0,respawn_count:0}; }
  var progression=freshProgression(),guardianDefeatedByPlayer=false,guardianDefeatedVia=null,combatEvents=[];
  var jevEpisodeManaged=false,jevEpisodeTerminal=false;
  var items = [], buffs = { speed: 0, power: 0, shield: 0, regen: 0 };
  var FOOD = {
    apple:  { icon: "🍎", heal: 15, buff: null },
    meat:   { icon: "🍖", heal: 30, buff: null },
    shroom: { icon: "🍄", heal: 10, buff: "speed" },
    honey:  { icon: "🍯", heal: 5,  buff: "regen" },
    pshard: { icon: "⚔️", heal: 0,  buff: "power" },
    star:   { icon: "⭐", heal: 0,  buff: "shield" }
  };
  var BUFF_NAME = { speed: "Speed", power: "Power", shield: "Shield", regen: "Regen" };
  var agent = { on: true, state: "EXPLORE", think: "Waking up…", tgt: null,
                path: null, pi: 0, pathT: 0, digT: null, digP: 0, atk: 0, stuck: 0, lx: 0, decideT: 0, jumpCD: 0, exdir: 1, since: 0, anchor: null, avoidT: 0, badTs: [], camp: null, campT: 0, escapeT: 0, progSig: "", progT: 0 };
  var cam = { x: 0, y: 0 }, keys = {}, wins = 0, deaths = 0, frame = 0, regenT = 0, showMap = false;
  var evt = { name: "", label: "", t: 0, timer: 1900 };
  var lastHitF = -9999;                                       // last frame we took or dealt damage (for out-of-combat regen)
  var gateFails = 0;                                          // deaths while challenging the gate boss raise the power bar
  var initialPlayer=JSON.stringify(P), initialGear=JSON.stringify(gear), initialAgent=JSON.stringify(agent);
  // Full episode reset: counters, cooldowns and prior deaths must not leak into
  // a nominally identical seed. A world reached after victory keeps old rules.
  function resetEpisode(seed,generationOptions) {
    var nextSeed=seedSource.normalize(seed);
    seedSource.terramaiLayout(nextSeed,generationOptions); // validate before changing pending execution
    jevRelease();setSeed(nextSeed,generationOptions);
    P=JSON.parse(initialPlayer);gear=JSON.parse(initialGear);agent=JSON.parse(initialAgent);agent.on=false;
    wins=0;deaths=0;frame=0;lastHitF=-9999;gateFails=0;msgs=[];cam={x:0,y:0};
    progression=freshProgression();combatEvents=[];
    Object.keys(stat).forEach(function(k){stat[k]=0});
    newWorld(false);clearKeys();last=now();accumulator=0;
  }
  function say(t) { agent.think = t; }
  function msg(t) { msgs.push({ t: t, life: 220 }); if (msgs.length > 4) msgs.shift(); }

  function resetPlayer(respawning) { if(respawning)progression.respawn_count++;P.x = spawn.x; P.y = spawn.y; P.vx = P.vy = 0; P.hp = P.maxhp; P.dead = 0; P.inv = 60; agent.path = null; agent.tgt = null; jevClearIntentTarget(); jevSurfaceAnchor=null; }
  function die() {
    if (P.dead) return;
    P.dead = 110; deaths++; progression.death_count++;jevClearIntentTarget();
    var nb = nearestEnemy();
    if (agent.state === "SEEK_GOAL" || (nb && nb.e.boss && nb.d < TS * 12)) { gateFails++; msg("📉 That boss is beyond me — develop more first (bar +" + gateFails + ")."); }
    msg("💀 Died (" + deaths + ") — gear is safe, respawning…");
    say("Ouch. Respawning…");
    burst(P.x + P.w / 2, P.y + P.h / 2, "#e05555", 14);
  }

  /* ---------------- physics ---------------- */
  function hitSolid(x, y, w, h) {
    var x0 = (x / TS) | 0, y0 = (y / TS) | 0, x1 = ((x + w - 0.01) / TS) | 0, y1 = ((y + h - 0.01) / TS) | 0;
    for (var ty = y0; ty <= y1; ty++) for (var tx = x0; tx <= x1; tx++) if (isSolid(tx, ty)) return true;
    return false;
  }
  function unstick(e) { var n = 0; while (hitSolid(e.x, e.y, e.w, e.h) && n++ < 40) e.y -= TS / 2; }
  function step(e, dtf) {
    e.vy = Math.min(e.vy + GRAV * dtf, MAXFALL);
    var nx = e.x + e.vx * dtf;
    if (!hitSolid(nx, e.y, e.w, e.h)) e.x = nx;
    else if (!hitSolid(e.x, e.y, e.w, e.h)) { var d1 = e.vx > 0 ? 1 : -1; while (!hitSolid(e.x + d1 * 0.5, e.y, e.w, e.h)) e.x += d1 * 0.5; e.vx = 0; }
    else { unstick(e); e.vx = 0; }
    var ny = e.y + e.vy * dtf; e.ground = false;
    if (!hitSolid(e.x, ny, e.w, e.h)) e.y = ny;
    else if (!hitSolid(e.x, e.y, e.w, e.h)) { var d2 = e.vy > 0 ? 1 : -1; while (!hitSolid(e.x, e.y + d2 * 0.5, e.w, e.h)) e.y += d2 * 0.5; if (e.vy > 0) e.ground = true; e.vy = 0; }
    else { unstick(e); e.vy = 0; }
  }

  /* ---------------- mining ---------------- */
  function upCost(lv) { return 3 + lv; }                       // upgrades get pricier the higher the level
  function gearCap() { return 2 * (10 + wins); }               // gear cap = twice the gate boss level (bosses grow each world)
  function tryArmorUp() { while (gear.armor < gearCap() && gear.gems >= (gear.armor + 1) * 2) { gear.armor++; msg("🛡️ Armor Lv." + gear.armor); } }
  function levelUp() {
    for (; ;) {
      var t = null;
      if (gear.pick <= gear.sword && gear.pick < gearCap()) t = "pick";
      else if (gear.sword < gearCap()) t = "sword";
      else if (gear.armor < gearCap()) t = "armor";
      else break;
      var c = upCost(gear[t]);
      if (gear.pts < c) break;
      gear.pts -= c; gear[t]++;
      msg("⬆️ " + (t === "pick" ? "Pickaxe" : (t === "sword" ? "Sword" : "Armor")) + " Lv." + gear[t]);
    }
  }
  function gainOre(t) {
    gear.pts += ORE_PTS[t]; stat.ore++;
    progression.ore_mined++;progression.ore_points_earned+=ORE_PTS[t];
    msg("⛏️ " + ORE_NAME[t] + "!");
    levelUp();
  }
  function tryMine(tx, ty) {
    var t = get(tx, ty);
    if (!HARD[t]) return false;
    var d = Math.hypot((tx + 0.5) * TS - (P.x + P.w / 2), (ty + 0.5) * TS - (P.y + P.h / 2));
    if (d > TS * 3) return false;
    if (!agent.digT || agent.digT.x !== tx || agent.digT.y !== ty) { agent.digT = { x: tx, y: ty }; agent.digP = 0; }
    agent.digP += (1 + gear.pick * 0.8) * gear.pickMul; agent.mineF = frame; agent.stuck = Math.max(0, agent.stuck - 6);
    if (frame % 5 === 0) burst((tx + 0.5) * TS, (ty + 0.5) * TS, BASECOL[t] || "#999", 1);
    if (agent.digP >= HARD[t]) {
      agent.digT = null; agent.digP = 0; agent.stuck = 0;
      if (ORE_PTS[t]) gainOre(t);
      else if (t === GEM) {
        gear.gems++; stat.gem++; msg("💎 Amethyst! (" + gear.gems + ")");
        tryArmorUp();
      }
      else if (t === DIRT || t === GRASS || t === STONE) gear.dirt = Math.min(99, gear.dirt + 1);
      setT(tx, ty, AIR);
    }
    return true;
  }

  /* ---------------- chests ---------------- */
  function openChest(tx, ty) {
    setT(tx, ty, AIR);
    for (var i = 0; i < chests.length; i++) if (chests[i].x === tx && chests[i].y === ty) { chests.splice(i, 1); break; }
    stat.chest++;
    burst((tx + 0.5) * TS, (ty + 0.5) * TS, "#ffd24a", 18);
    var eqC = Math.min(0.25, 0.10 + wins * 0.03), potC = Math.min(0.15, 0.05 + wins * 0.02);
    var roll = random();
    if (roll < eqC) {                                            // rare gear: multiplier equipment, replaced only if stronger
      var slot = ["sword", "pick", "armor"][(random() * 3) | 0], mkey = slot + "Mul";
      var mul = Math.round((1.1 + random() * (0.3 + wins * 0.1)) * 10) / 10;
      if (mul > gear[mkey]) { gear[mkey] = mul; msg("🧰⚡ " + (slot === "sword" ? "Blade" : (slot === "pick" ? "Pickaxe" : "Plate")) + " of Power ×" + mul.toFixed(1) + " equipped!"); say("Legendary loot!"); }
      else msg("🧰 A weaker " + slot + " (×" + mul.toFixed(1) + ") — kept mine.");
    }
    else if (roll < eqC + potC) {                                // magic potion: PERMANENT stat boost
      var pr = random();
      if (pr < 0.34) { gear.potAtk += 2; msg("🧪 Potion of Strength! +2 attack (permanent)"); }
      else if (pr < 0.67) { P.maxhp += 15; P.hp = Math.min(P.maxhp, P.hp + 15); msg("🧪 Potion of Vitality! +15 max ❤️"); }
      else { gear.potArm += 1; msg("🧪 Potion of Iron Skin! +1 armor (permanent)"); }
    }
    else if (roll < eqC + potC + 0.18 && gear.pick < gearCap()) { gear.pick++; msg("🧰 Chest: shiny pickaxe! ⛏️Lv." + gear.pick); }
    else if (roll < eqC + potC + 0.34 && gear.sword < gearCap()) { gear.sword++; msg("🧰 Chest: sharp sword! 🗡️Lv." + gear.sword); }
    else if (roll < eqC + potC + 0.47 && gear.armor < gearCap()) { gear.armor++; msg("🧰 Chest: armor plate! 🛡️Lv." + gear.armor); }
    else if (roll < eqC + potC + 0.58) {
      if (random() < 0.6) { buffs.power = 1200; msg("🧰 Chest: ⚔️ DOUBLE DAMAGE (20s)!"); }
      else { buffs.shield = 900; msg("🧰 Chest: ⭐ SHIELD (15s)!"); }
    }
    else if (roll < eqC + potC + 0.7) { gear.gems += 3; msg("🧰 Chest: 3 gems! 💎" + gear.gems); }
    else { P.hp = Math.min(P.maxhp, P.hp + 40); msg("🧰 Chest: heart! +40 ❤️"); }
    say("Treasure chest! Lucky me.");
  }
  function checkChest() {
    var tx0 = ((P.x - 4) / TS) | 0, tx1 = ((P.x + P.w + 4) / TS) | 0;
    var ty0 = ((P.y - 4) / TS) | 0, ty1 = ((P.y + P.h + 4) / TS) | 0;
    for (var ty = ty0; ty <= ty1; ty++) for (var tx = tx0; tx <= tx1; tx++)
      if (get(tx, ty) === CHEST) openChest(tx, ty);
  }

  /* ---------------- enemies (slime / zombie / bat) ---------------- */
  var EK = {
    slime:  { w: 14, h: 11, hp: 14, dmg: 8,  col: "#63c74d" },
    zombie: { w: 12, h: 20, hp: 30, dmg: 13, col: "#7d9e5a" },
    bat:    { w: 12, h: 8,  hp: 8,  dmg: 6,  col: "#7a5da8" }
  };
  function spawnEnemy(force) {
    if (enemies.length >= (force ? 12 : 8)) return;
    for (var tr = 0; tr < 24; tr++) {
      var tx = rnd(2, WW - 2) | 0, ty = rnd(4, WH - 4) | 0;
      if (get(tx, ty) !== AIR || get(tx, ty - 1) !== AIR) continue;
      var d = Math.hypot(tx * TS - P.x, ty * TS - P.y);
      if (d < TS * 14 || d > TS * 48) continue;
      var depth = ty - (surf[tx] || 0), kind;
      if (depth > 6) kind = random() < 0.45 ? "bat" : (random() < 0.5 ? "slime" : "zombie");
      else kind = random() < 0.6 ? "slime" : "zombie";
      if (kind !== "bat" && !isSolid(tx, ty + 1)) continue;
      var k = EK[kind];
      var lv = Math.max(1, Math.min(8, 1 + Math.floor(depth / 9) + Math.floor((tx / WW) * 3) + (random() < 0.3 ? 1 : 0)));
      var ehp = Math.round((k.hp + wins * 3) * (1 + 0.7 * (lv - 1)));
      enemies.push({ kind: kind, x: tx * TS + 1, y: ty * TS + (TS - k.h) - 1, w: k.w, h: k.h, lv: lv,
                     vx: 0, vy: 0, ground: false, hp: ehp, maxhp: ehp, hop: rnd(10, 50), face: 1, t: rnd(0, 6.28) });
      return;
    }
  }
  function spawnBossAt(tx, groundY, kind, lv, gateGuardian) {
    var k = EK[kind], sc = 2.1, w = k.w * sc, h = k.h * sc;
    var ehp = Math.round((k.hp + 30) * (1 + 0.7 * (lv - 1)) * 2.4);
    enemies.push({ kind: kind, boss: true, gateGuardian:!!gateGuardian, x: tx * TS + 1, y: groundY * TS - h - 1, w: w, h: h, lv: lv,
                   vx: 0, vy: 0, ground: false, hp: ehp, maxhp: ehp, hop: rnd(20, 60), face: -1, t: rnd(0, 6.28) });
  }
  function spawnBosses() {
    for (var tr = 0; tr < 300; tr++) {                          // deep boss guarding the diamond depths
      var bx = rnd(WW * 0.35, WW * 0.65) | 0, by = rnd(WH * 0.7, WH - 4) | 0;
      if (get(bx, by) === AIR && get(bx, by - 1) === AIR && isSolid(bx, by + 1)) { spawnBossAt(bx, by + 1, "slime", 7 + wins); break; }
    }
    var rx2 = (WW * 0.72) | 0; spawnBossAt(rx2, surf[rx2] || 40, "zombie", 8 + wins);   // mid-right surface boss
    var gx2 = WW - 10; spawnBossAt(gx2, surf[gx2] || 40, "zombie", 10 + wins, true);    // only this guardian unlocks the gate
  }
  function spawnSeededOrdinaryEnemies() {
    (environmentLayout.enemySites||[]).forEach(function(site){
      var tx=site.x,ty=surf[tx]-1,k=EK[site.kind];
      if(get(tx,ty)!==AIR||get(tx,ty-1)!==AIR||!isSolid(tx,ty+1))return;
      var lv=Math.max(1,1+Math.floor(tx/WW*3)),hp=Math.round((k.hp+wins*3)*(1+.7*(lv-1)));
      enemies.push({kind:site.kind,x:tx*TS+1,y:(ty+1)*TS-k.h-1,w:k.w,h:k.h,lv:lv,
        vx:0,vy:0,ground:false,hp:hp,maxhp:hp,hop:rnd(10,50),face:1,t:rnd(0,6.28)});
    });
  }
  function updEnemies(dtf) {
    for (var i = enemies.length - 1; i >= 0; i--) {
      var s = enemies[i], k = EK[s.kind];
      var dx = P.x - s.x, dy = P.y - s.y, dist = Math.hypot(dx, dy);
      s.face = dx > 0 ? 1 : -1;
      if (s.kind === "slime") {
        if (s.ground) { s.vx *= 0.8; s.hop -= dtf;
          if (dist < TS * 16 && s.hop <= 0) { s.vx = s.face * rnd(1.2, 2.2); s.vy = -rnd(4, 6.5); s.hop = rnd(40, 85); } }
        step(s, dtf);
      } else if (s.kind === "zombie") {
        if (dist < TS * 20) {
          s.vx = s.face * 0.85;
          var fx = ((s.x + (s.face > 0 ? s.w + 2 : -3)) / TS) | 0, fy = ((s.y + s.h - 2) / TS) | 0;
          if (s.ground && isSolid(fx, fy) && !isSolid(fx, fy - 1)) s.vy = -7.2;
        } else s.vx *= 0.8;
        step(s, dtf);
      } else {                                                   // bat: flies, ignores gravity
        s.t += 0.08 * dtf;
        var sp = dist < TS * 18 ? 1.5 : 0.5;
        var mx = (dx / (dist || 1)) * sp * dtf, my = (dy / (dist || 1)) * sp * dtf + Math.sin(s.t) * 0.9 * dtf;
        if (!hitSolid(s.x + mx, s.y, s.w, s.h)) s.x += mx;
        if (!hitSolid(s.x, s.y + my, s.w, s.h)) s.y += my;
      }
      if (s.y > WH * TS + 40) { if(s.hp>0)s.lethalDamageSource='environment_fall';s.hp = 0; }
      if (get(((s.x + s.w / 2) / TS) | 0, ((s.y + s.h / 2) / TS) | 0) === LAVA) { var aliveBeforeLava=s.hp>0;s.hp -= 0.7 * dtf;if(aliveBeforeLava&&s.hp<=0)s.lethalDamageSource='environment_lava';if (frame % 9 === 0) burst(s.x + s.w / 2, s.y, "#ff9c40", 1); }
      if (!P.dead && P.inv <= 0 &&
          Math.abs((s.x + s.w / 2) - (P.x + P.w / 2)) < (s.w + P.w) / 2 &&
          Math.abs((s.y + s.h / 2) - (P.y + P.h / 2)) < (s.h + P.h) / 2) {
        var dmg = Math.max(2, Math.round(k.dmg * (1 + 0.55 * ((s.lv || 1) - 1)) + wins - gear.armor * 2 * gear.armorMul - gear.potArm * 2));
        if (s.boss) dmg = Math.round(dmg * 0.8);
        if (buffs.shield > 0) dmg = 0;
        P.hp -= dmg; P.inv = 45; P.vx = (dx > 0 ? -1 : 1) * 3; P.vy = -3; lastHitF = frame;
        burst(P.x + P.w / 2, P.y + P.h / 2, "#e05555", 6);
        if (P.hp <= 0) die();
      }
      if (s.hp <= 0) {
        burst(s.x + s.w / 2, s.y + s.h / 2, k.col, 10);
        var credited=(s.playerDamage||0)>0,direct=credited&&s.lethalDamageSource==='player_attack';
        if(credited){
          stat.kill++;progression.player_kills++;progression.combat_points_earned+=(s.lv||1);
          if(direct)progression.player_direct_kills++;else progression.environment_assisted_kills++;
          if(s.boss)progression.player_boss_kills++;else progression.ordinary_player_kills++;
          if(s.gateGuardian){guardianDefeatedByPlayer=true;guardianDefeatedVia=direct?'player_attack':'player_assisted_environment';progression.guardian_player_kills++;}
          gear.pts += (s.lv || 1); levelUp();
          if ((s.lv || 1) >= 3) { gear.gems++; msg("💎 Lv" + s.lv + " " + s.kind + " dropped a gem! (" + gear.gems + ")"); tryArmorUp(); }
          else msg("⚔️ " + s.kind + " Lv" + (s.lv || 1) + " down! +" + (s.lv || 1) + " pts");
          if (s.boss) { gear.gems += 5; msg("👑 BOSS DOWN! +5 💎"); }
        }
        // Attribute only real player damage. Unseen passive enemy deaths are
        // neither player progression nor a source of hidden-location feedback.
        if(credited||Math.abs(s.x-P.x)<TS*12&&Math.abs(s.y-P.y)<TS*9&&jevVisibleTile(Math.floor(s.x/TS),Math.floor(s.y/TS))!==-1){
          combatEvents.push({frame:frame,enemy_id:jevEntityId(s),kind:s.kind,boss:!!s.boss,gate_guardian:!!s.gateGuardian,
            player_damage:s.playerDamage||0,lethal_source:s.lethalDamageSource||'unattributed',credited_to_player:credited,
            attribution:credited?(direct?'player_direct':'player_assisted_environment'):'environment_only'});combatEvents=combatEvents.slice(-8);
        }
        if (s.boss) { spawnItem(s.x + s.w / 2, s.y, "star"); spawnItem(s.x + s.w / 2 + 8, s.y, "meat"); }
        var dr = random();
        if (s.kind === "zombie" && dr < 0.55) spawnItem(s.x + s.w / 2, s.y, "meat");
        else if (s.kind === "slime" && dr < 0.5) spawnItem(s.x + s.w / 2, s.y, dr < 0.18 ? "pshard" : "shroom");
        else if (s.kind === "bat" && dr < 0.5) spawnItem(s.x + s.w / 2, s.y, dr < 0.15 ? "star" : "apple");
        if ((s.lv || 1) >= 4 && random() < 0.3) spawnItem(s.x + s.w / 2, s.y - 4, "star");
        enemies.splice(i, 1);
      }
    }
  }
  function attackRectangle(aim,x,y,w,h){
    var dx=aim==='left'?-1:aim==='right'?1:0,dy=aim==='up'?-1:aim==='down'?1:0;
    return {x:dx>0?x+w:dx<0?x-28:x-6,y:dy<0?y-28:dy>0?y+h:y-6,w:dx?28:w+12,h:dy?28:h+12};
  }
  function attackIntersects(rect,enemy){
    return enemy.x+enemy.w>rect.x&&enemy.x<rect.x+rect.w&&enemy.y+enemy.h>rect.y&&enemy.y<rect.y+rect.h;
  }
  function attack() {
    if (agent.atk > 0 || P.dead) return;
    agent.atk = 26;
    var aim=jevAim|| (P.face>0?'right':'left'),dx=aim==='left'?-1:aim==='right'?1:0,dy=aim==='up'?-1:aim==='down'?1:0;
    var rect=attackRectangle(aim,P.x,P.y,P.w,P.h);
    for (var i = 0; i < enemies.length; i++) {
      var e=enemies[i];
      if(attackIntersects(rect,e)){var priorHP=e.hp,damage=((5+gear.sword*4)*gear.swordMul+gear.potAtk)*(buffs.power>0?2:1);e.hp-=damage;
        if(priorHP>0&&damage>0){var dealt=Math.min(priorHP,damage);e.playerDamage=(e.playerDamage||0)+dealt;e.lastPlayerHitFrame=frame;progression.player_attack_hits++;progression.player_attack_damage+=dealt;if(e.hp<=0)e.lethalDamageSource='player_attack';}
        e.vx=dx*4;e.vy=dy*4-2;agent.stuck=0;lastHitF=frame;burst(e.x+e.w/2,e.y+e.h/2,'#ffe9a3',5)}
    }
  }

  /* ---------------- drops & particles ---------------- */
  function updDrops(dtf) {
    for (var i = drops.length - 1; i >= 0; i--) {
      var d = drops[i]; step(d, dtf); d.vx *= 0.92;
      if (!P.dead && Math.abs(d.x - P.x) < 16 && Math.abs(d.y - P.y) < 24) {
        gear.pick = Math.max(gear.pick, d.bag.pick); gear.sword = Math.max(gear.sword, d.bag.sword); gear.armor = Math.max(gear.armor, d.bag.armor);
        msg("🎒 Recovered your equipment!"); burst(d.x, d.y, "#ffd24a", 8); jevCollectedItems.push({id:jevEntityId(d),kind:"equipment",frame:frame});jevCollectedItems=jevCollectedItems.slice(-12);drops.splice(i, 1);
      }
    }
  }
  /* ---------------- food & buff items ---------------- */
  function spawnItem(x, y, kind) { items.push({ x: x, y: y, vx: rnd(-1, 1), vy: -2, w: 8, h: 8, ground: false, kind: kind, life: 3600 }); }
  function updItems(dtf) {
    for (var i = items.length - 1; i >= 0; i--) {
      var it = items[i]; step(it, dtf); it.vx *= 0.9; it.life -= dtf;
      if (it.life <= 0 || get((it.x / TS) | 0, (it.y / TS) | 0) === LAVA) { items.splice(i, 1); continue; }
      if (!P.dead && Math.abs(it.x - (P.x + P.w / 2)) < 15 && Math.abs(it.y - (P.y + P.h / 2)) < 20) {
        var f = FOOD[it.kind];
        if (f.heal) P.hp = Math.min(P.maxhp, P.hp + f.heal);
        if (f.buff) { buffs[f.buff] = 720; msg(f.icon + " " + BUFF_NAME[f.buff] + " buff (12s)!"); say("Power-up!"); }
        else { msg(f.icon + " +" + f.heal + " ❤️"); say("Yum!"); }
        burst(it.x, it.y, "#aef29a", 8);jevCollectedItems.push({id:jevEntityId(it),kind:"food",frame:frame});jevCollectedItems=jevCollectedItems.slice(-12);
        items.splice(i, 1);
      }
    }
    for (var b in buffs) if (buffs[b] > 0) buffs[b] -= dtf;
  }
  function burst(x, y, c, n) { for (var i = 0; i < n; i++) parts.push({ x: x, y: y, vx: cosmeticRnd(-2, 2), vy: cosmeticRnd(-3, 0.5), l: cosmeticRnd(15, 35), c: c }); }
  function updParts(dtf) {
    for (var i = parts.length - 1; i >= 0; i--) {
      var p = parts[i]; p.x += p.vx * dtf; p.y += p.vy * dtf; p.vy += 0.2 * dtf; p.l -= dtf;
      if (p.l <= 0) parts.splice(i, 1);
    }
  }

  /* ============================================================================
     AGENT BRAIN — a finite state machine that switches between behaviors, each
     driven by BFS pathfinding (Dijkstra with digging cost) + frontier exploration.
     States: EXPLORE (frontier) · SEEK_GOAL · FIGHT · FLEE · DIG · SURFACE
     ============================================================================ */
  var THINKS = {
    EXPLORE: ["Frontier ahead — let's map it.", "Unknown tiles that way →", "Exploring the dark…", "New ground to chart."],
    SEEK_GOAL: ["Path to the Grand Gem locked in.", "Following the route to treasure.", "Almost at the prize…"],
    FIGHT: ["Hostile! Engaging.", "En garde, creature!", "Combat mode."],
    FLEE: ["Too risky — retreating.", "Fall back and heal!", "Nope, running."],
    DIG: ["Tunnelling downward…", "Digging for ore."],
    SURFACE: ["Heading back up for air.", "To the surface!"],
    CHEST: ["A chest! Gimme that loot.", "Treasure nearby — on my way.", "Free loot, don't mind if I do."],
    MINE: ["Mining ore to upgrade.", "Need better gear — digging.", "More ore, more power."],
    GEMS: ["Gem hunting — armor time.", "Sparkly things, come to me."],
    HUNT: ["Hunting something my size.", "Monster farming time."],
    HEAL: ["Low HP — need a snack.", "Retreat, recover, return."],
    PILLAR: ["Building my way up!", "Stacking dirt — going up."],
    WIN: ["Grand Gem secured! 🎉", "Loot acquired!"]
  };
  function pickThink(st) { var p = THINKS[st] || THINKS.EXPLORE; return p[(cosmeticRandom() * p.length) | 0]; }
  function badTarget(x, y) {
    for (var i = 0; i < agent.badTs.length; i++) { var b = agent.badTs[i]; if (Math.abs(b.x - x) <= 3 && Math.abs(b.y - y) <= 3) return true; }
    return false;
  }
  function banTarget() {                                     // blacklist an unreachable target so we don't re-pick it
    if (agent.tgt) { agent.badTs.push({ x: agent.tgt.x, y: agent.tgt.y, life: 900 }); if (agent.badTs.length > 4) agent.badTs.shift(); }
    agent.path = null; agent.tgt = null;
  }
  function agentPower() { return 1 + gear.sword * gear.swordMul + gear.armor * 0.6 * gear.armorMul + gear.pick * 0.2 * gear.pickMul + gear.potAtk * 0.3 + gear.potArm * 0.5 + (P.maxhp - 100) / 50; }
  function beatable(e) { return !e || (e.lv || 1) <= agentPower() + 0.6; }
  function nearestBeatableEnemy() {
    var b = null, bd = 1e9;
    for (var i = 0; i < enemies.length; i++) { if (!beatable(enemies[i])) continue; var d = Math.hypot(enemies[i].x - P.x, enemies[i].y - P.y); if (d < bd) { bd = d; b = enemies[i]; } }
    return b ? { e: b, d: bd } : null;
  }
  function nearestEnemy() {
    var b = null, bd = 1e9;
    for (var i = 0; i < enemies.length; i++) { var d = Math.hypot(enemies[i].x - P.x, enemies[i].y - P.y); if (d < bd) { bd = d; b = enemies[i]; } }
    return b ? { e: b, d: bd } : null;
  }
  function nearestKnownChest() {
    var b = null, bd = 1e9, pcx = (P.x / TS) | 0, pcy = (P.y / TS) | 0;
    for (var i = 0; i < chests.length; i++) {
      var c = chests[i]; if (!explored[idx(c.x, c.y)] || get(c.x, c.y) !== CHEST || badTarget(c.x, c.y)) continue;
      var d = Math.abs(c.x - pcx) + Math.abs(c.y - pcy); if (d < bd) { bd = d; b = c; }
    }
    return b ? { x: b.x, y: b.y, d: bd } : null;
  }
  function nearestKnownOre() {
    var b = null, bd = 1e9, pcx = (P.x / TS) | 0, pcy = (P.y / TS) | 0;
    for (var y = Math.max(1, pcy - 26); y < Math.min(WH - 1, pcy + 26); y++)
      for (var x = Math.max(1, pcx - 34); x < Math.min(WW - 1, pcx + 34); x++) {
        var ii = idx(x, y); if (!explored[ii]) continue; var t = world[ii];
        if ((!ORE_PTS[t] && t !== GEM) || badTarget(x, y)) continue;
        var d = Math.abs(x - pcx) + Math.abs(y - pcy); if (d < bd) { bd = d; b = { x: x, y: y }; }
      }
    return b;
  }
  function nearestFood() {
    var b = null, bd = 1e9;
    for (var i = 0; i < items.length; i++) { var f = FOOD[items[i].kind]; if (!f || !f.heal) continue; var d = Math.abs(items[i].x - P.x) + Math.abs(items[i].y - P.y); if (d < bd) { bd = d; b = items[i]; } }
    return b ? { x: (b.x / TS) | 0, y: (b.y / TS) | 0, d: bd / TS } : null;
  }
  function nearestKnownGem() {
    var b = null, bd = 1e9, pcx = (P.x / TS) | 0, pcy = (P.y / TS) | 0;
    for (var y = Math.max(1, pcy - 26); y < Math.min(WH - 1, pcy + 26); y++)
      for (var x = Math.max(1, pcx - 34); x < Math.min(WW - 1, pcx + 34); x++) {
        var ii = idx(x, y); if (!explored[ii] || world[ii] !== GEM || badTarget(x, y)) continue;
        var d = Math.abs(x - pcx) + Math.abs(y - pcy); if (d < bd) { bd = d; b = { x: x, y: y }; }
      }
    return b;
  }

  /* ---- Dijkstra path over tiles (AIR cheap, diggable costs ~hardness, bedrock blocked) ---- */
  function passCost(t) { if (t === AIR || t === GOAL || t === CHEST) return 1; if (t === MIASMA) return 30; if (t === LAVA) return 90; if (t === BEDROCK) return Infinity; if (HARD[t]) return 4 + HARD[t] * 0.5; return Infinity; }
  function bfsPath(sx, sy, gx, gy) {
    if (!inb(sx, sy) || !inb(gx, gy)) return null;
    var N = WW * WH, dist = new Float32Array(N), prev = new Int32Array(N);
    dist.fill(Infinity); prev.fill(-1);
    var start = idx(sx, sy), goalI = idx(gx, gy); dist[start] = 0;
    var heap = [[0, start]];
    function push(d, i) { heap.push([d, i]); var c = heap.length - 1; while (c > 0) { var p = (c - 1) >> 1; if (heap[p][0] <= heap[c][0]) break; var t = heap[p]; heap[p] = heap[c]; heap[c] = t; c = p; } }
    function pop() { var top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; var c = 0; for (; ;) { var l = 2 * c + 1, r = l + 1, s = c; if (l < heap.length && heap[l][0] < heap[s][0]) s = l; if (r < heap.length && heap[r][0] < heap[s][0]) s = r; if (s === c) break; var t = heap[s]; heap[s] = heap[c]; heap[c] = t; c = s; } } return top; }
    var exp = 0;
    while (heap.length) {
      var cur = pop(), cd = cur[0], ci = cur[1];
      if (cd > dist[ci]) continue;
      if (ci === goalI || ++exp > 12000) break;
      var cx = ci % WW, cy = (ci / WW) | 0, nx = [cx + 1, cx - 1, cx, cx], ny = [cy, cy, cy + 1, cy - 1];
      for (var k = 0; k < 4; k++) {
        if (!inb(nx[k], ny[k])) continue;
        var ni = idx(nx[k], ny[k]), c2 = passCost(world[ni]);
        if (c2 === Infinity) continue;
        var nd = cd + c2; if (nd < dist[ni]) { dist[ni] = nd; prev[ni] = ci; push(nd, ni); }
      }
    }
    if (!isFinite(dist[goalI])) return null;
    var path = [], p = goalI, guard = 0;
    while (p !== -1 && guard++ < 5000) { path.push({ x: p % WW, y: (p / WW) | 0 }); p = prev[p]; }
    path.reverse(); return path;
  }
  /* ---- frontier: nearest explored-air tile bordering the unknown (BFS over explored air) ---- */
  function nearestFrontier() {
    var sx = (P.x / TS) | 0, sy = (P.y / TS) | 0;
    if (!inb(sx, sy)) return null;
    var seen = new Uint8Array(WW * WH), q = [idx(sx, sy)]; seen[q[0]] = 1;
    for (var qi = 0; qi < q.length && qi < 8000; qi++) {
      var c = q[qi], cx = c % WW, cy = (c / WW) | 0, xs = [cx + 1, cx - 1, cx, cx], ys = [cy, cy, cy + 1, cy - 1], k, ni;
      for (k = 0; k < 4; k++) if (inb(xs[k], ys[k]) && !explored[idx(xs[k], ys[k])] && world[idx(xs[k], ys[k])] !== BEDROCK) {
        if ((cx !== sx || cy !== sy) && cy + 2 >= (surf[cx] || 0) && !badTarget(cx, cy)) return { x: cx, y: cy };
      }
      for (k = 0; k < 4; k++) {
        if (!inb(xs[k], ys[k])) continue; ni = idx(xs[k], ys[k]);
        if (seen[ni]) continue; seen[ni] = 1;
        var t = world[ni];
        if (explored[ni] && (t === AIR || t === GOAL || t === CHEST)) q.push(ni);
      }
    }
    return null;
  }
  function randFar() {
    for (var i = 0; i < 40; i++) {
      var tx = ((P.x / TS) | 0) + ((rnd(8, 40) | 0) * (random() < 0.75 ? agent.exdir : -agent.exdir)), ty = ((P.y / TS) | 0) + (rnd(-4, 28) | 0);
      tx = Math.max(2, Math.min(WW - 3, tx)); ty = Math.max(2, Math.min(WH - 3, ty));
      if (world[idx(tx, ty)] !== BEDROCK) return { x: tx, y: ty };
    }
    return { x: goal.x, y: goal.y };
  }
  function enemyStandTile(e) {                              // reachable ground spot near an enemy (not a floating air tile)
    var ex = Math.max(1, Math.min(WW - 2, ((e.x + e.w / 2) / TS) | 0)), ey = Math.max(1, Math.min(WH - 2, ((e.y + e.h - 2) / TS) | 0));
    for (var y = ey; y < WH - 1; y++) { if (get(ex, y) !== BEDROCK && !isSolid(ex, y) && isSolid(ex, y + 1)) return { x: ex, y: y }; }
    return { x: ex, y: ey };
  }
  function chooseTarget(st, ne) {
    if (st === "FLEE" && ne) return { x: Math.max(2, Math.min(WW - 3, ((P.x / TS) | 0) + (P.x < ne.e.x ? -16 : 16))), y: (P.y / TS) | 0 };
    if (st === "FIGHT" && ne) return enemyStandTile(ne.e);
    if (st === "CHEST") { var ch = nearestKnownChest(); return ch ? { x: ch.x, y: ch.y } : (nearestFrontier() || randFar()); }
    if (st === "HEAL") {
      var fd = nearestFood(); if (fd && fd.d < 45) return { x: fd.x, y: fd.y };
      var away = ne ? (P.x < ne.e.x ? -1 : 1) : -1;
      var hx = Math.max(3, Math.min(WW - 4, ((P.x / TS) | 0) + away * 18));
      return { x: hx, y: Math.max(2, (surf[hx] || 40) - 1) };
    }
    if (st === "MINE") { var o = nearestKnownOre(); return o ? o : { x: Math.max(2, Math.min(WW - 3, ((P.x / TS) | 0) + agent.exdir * 6)), y: Math.min(WH - 3, ((P.y / TS) | 0) + 10) }; }
    if (st === "GEMS") { var g = nearestKnownGem(); return g ? g : { x: (P.x / TS) | 0, y: Math.min(WH - 3, ((P.y / TS) | 0) + 14) }; }
    if (st === "HUNT") { var be = nearestBeatableEnemy(); return be ? enemyStandTile(be.e) : (nearestFrontier() || randFar()); }
    if (st === "SEEK_GOAL") return { x: goal.x, y: goal.y };
    if (st === "DIG") return { x: (P.x / TS) | 0, y: Math.min(WH - 3, ((P.y / TS) | 0) + 16) };
    if (st === "PILLAR") return { x: (P.x / TS) | 0, y: Math.max(2, ((P.y / TS) | 0) - 12) };
    if (st === "SURFACE") { var cx = Math.max(0, Math.min(WW - 1, (P.x / TS) | 0)); return { x: cx, y: Math.max(2, (surf[cx] || 40) - 1) }; }
    return nearestFrontier() || randFar();
  }
  function decide() {
    if (P.dead) return;
    if (agent.escapeT > 0) {                                    // breakout mode: tunnel down & away, ignore fear and food
      agent.state = "EXPLORE";
      if (!agent.tgt || !agent.path || agent.pi >= agent.path.length) {
        var edir = agentPower() >= 6 ? 1 : (random() < 0.5 ? -1 : 1);
        var ex2 = Math.max(3, Math.min(WW - 4, ((P.x / TS) | 0) + edir * (28 + (random() * 12 | 0))));
        var ey2 = Math.min(WH - 3, ((P.y / TS) | 0) + 8 + ((random() * 8) | 0));
        agent.tgt = { x: ex2, y: ey2 };
        agent.path = bfsPath(((P.x + P.w / 2) / TS) | 0, ((P.y + P.h - 2) / TS) | 0, ex2, ey2); agent.pi = 0;
      }
      return;
    }
    var ne = nearestEnemy(), hpr = P.hp / P.maxhp;
    var chest = nearestKnownChest();
    var strong = ne && !beatable(ne.e);
    if (agentPower() >= 6) agent.exdir = 1;   // well geared: default push to the right
    var o2 = nearestKnownOre(), pcx2 = (P.x / TS) | 0, pcy2 = (P.y / TS) | 0;
    var oreNear = o2 && (Math.abs(o2.x - pcx2) + Math.abs(o2.y - pcy2)) < 14;
    if (hpr < 0.35) agent.lowHP = true; else if (hpr > 0.65) agent.lowHP = false;   // hysteresis: stay in recovery mode until truly healed
    var st;
    if (ne && ne.d < TS * 6 && (agent.lowHP || strong)) st = "FLEE";
    else if (agent.lowHP) st = "HEAL";
    else if (ne && ne.d < TS * 7 && !strong && agent.avoidT <= 0) st = "FIGHT";
    else if (agentPower() >= 10 + wins + gateFails && hpr > 0.5) st = "SEEK_GOAL";
    else if (chest && chest.d < 40) st = "CHEST";
    else if (oreNear) st = "MINE";
    else st = "EXPLORE";
    var wl = agent.campT > 720 && st !== "FLEE" && st !== "FIGHT";      // loitered ~12s in one area: force a long-range move
    if (wl) st = "EXPLORE";
    var changed = st !== agent.state; agent.state = st;
    if (changed) { agent.path = null; agent.since = 0; say(pickThink(st)); }
    else agent.since++;
    if (st === "EXPLORE" && agent.since > 26) { agent.exdir = -agent.exdir; agent.since = 0; agent.tgt = null; agent.path = null; }   // break explore loops
    if (agent.replanT === undefined) agent.replanT = 0;
    agent.replanT--;
    var noPath = !agent.path || agent.pi >= agent.path.length;
    if (noPath || agent.replanT <= 0 || agent.stuck > 110) {
      var t = chooseTarget(st, ne); agent.tgt = t;
      if (t) { agent.path = bfsPath(((P.x + P.w / 2) / TS) | 0, ((P.y + P.h - 2) / TS) | 0, t.x, t.y); agent.pi = 0; }
      agent.replanT = 40; agent.hopN = 0; if (agent.stuck > 110) agent.stuck = 60;
    }
    if (wl) {
      agent.badTs.push({ x: (P.x / TS) | 0, y: (P.y / TS) | 0, life: 1800 }); if (agent.badTs.length > 4) agent.badTs.shift();
      var fxq = Math.max(3, Math.min(WW - 4, ((P.x / TS) | 0) + agent.exdir * (25 + (random() * 14 | 0))));
      var fyq = Math.max(3, Math.min(WH - 3, ((P.y / TS) | 0) - 5 + ((random() * 18) | 0)));
      agent.tgt = { x: fxq, y: fyq };
      agent.path = bfsPath(((P.x + P.w / 2) / TS) | 0, ((P.y + P.h - 2) / TS) | 0, fxq, fyq); agent.pi = 0;
      agent.replanT = 60; agent.campT = 0; agent.camp = { x: P.x, y: P.y };
      say("Been here too long — moving on!");
    }
  }
  function followPath() {}
  function moveToward(txp, typ) {
    var mid = ((P.x + P.w / 2) / TS) | 0, footY = ((P.y + P.h - 3) / TS) | 0, headY = ((P.y + 3) / TS) | 0;
    var pcx = (P.x + P.w / 2) / TS, pcy = (P.y + P.h / 2) / TS, dx = (txp + 0.5) - pcx, dy = (typ + 0.5) - pcy;
    if (Math.abs(dx) > 0.45) {
      P.face = dx > 0 ? 1 : -1; P.vx = P.face * MOVE;
      var fx = mid + P.face, bf = isSolid(fx, footY), bh = isSolid(fx, headY);
      if (bf || bh) {
        var stepUp = bf && !bh && !isSolid(fx, footY - 1) && !isSolid(fx, headY - 1) && !isSolid(mid, headY - 1);
        if (stepUp && P.ground && agent.jumpCD <= 0) { P.vy = -JUMP; agent.jumpCD = 16; }
        else tryMine(fx, bh ? headY : footY);
      }
    } else P.vx *= 0.6;
    if (dy < -1.2) {
      var uy = ((P.y - 3) / TS) | 0;
      if (isSolid(mid, uy)) { if (agent.mineF !== frame && tryMine(mid, uy)) agent.hopN = 0; }
      else if (isSolid(mid, uy - 1) && get(mid, uy - 1) !== BEDROCK) { if (agent.mineF !== frame && tryMine(mid, uy - 1)) agent.hopN = 0; }   // ceiling one gap above: dig it instead of bonking
      else if (P.ground && agent.jumpCD <= 0) {
        P.vy = -JUMP; agent.jumpCD = 18;
        if ((agent.hopN || 0) >= 1) P.vx = (random() < 0.5 ? -1 : 1) * MOVE * 0.6;   // wiggle sideways so repeated hops shift position
        agent.wantUp = dy < -1.8;                              // deep ascent: pillar a dirt block at the apex
        agent.hopN = (agent.hopN || 0) + 1;
        if (agent.hopN > 6) { agent.hopN = 0; banTarget(); agent.exdir = -agent.exdir; }   // truly unreachable: blacklist & re-target
      }
    } else if (dy > 0.8 && Math.abs(dx) < 1.6) {
      var by = ((P.y + P.h + 2) / TS) | 0;
      if (isSolid(mid, by) && get(mid, by) !== BEDROCK && agent.mineF !== frame) tryMine(mid, by);
      else if (!isSolid(mid, by) && P.ground) {                 // hole is open below but we're perched on its edge
        var hc = (mid + 0.5) * TS - (P.x + P.w / 2);
        if (hc > 1) P.vx = 0.9; else if (hc < -1) P.vx = -0.9;
        else if (agent.mineF !== frame) {                       // centered yet still supported: chew the edge tile under us
          var lft = ((P.x + 1) / TS) | 0, rgt = ((P.x + P.w - 1) / TS) | 0;
          if (lft !== mid && isSolid(lft, by) && get(lft, by) !== BEDROCK) tryMine(lft, by);
          else if (rgt !== mid && isSolid(rgt, by) && get(rgt, by) !== BEDROCK) tryMine(rgt, by);
        }
      }
    }
  }
  function nextWaypoint() {
    if (!agent.path || agent.pi >= agent.path.length) return null;
    var pcx = (P.x + P.w / 2) / TS, pcy = (P.y + P.h / 2) / TS, guard = 0;
    while (agent.pi < agent.path.length - 1 && guard++ < 300) {
      var n = agent.path[agent.pi];
      if (Math.abs((n.x + 0.5) - pcx) < 1.15 && Math.abs((n.y + 0.5) - pcy) < 1.5) agent.pi++; else break;
    }
    return agent.path[agent.pi];
  }
  function act(dtf) {
    if (P.dead) return;
    if (agent.jumpCD > 0) agent.jumpCD -= dtf;
    if (agent.avoidT > 0) agent.avoidT -= dtf;
    if (agent.escapeT > 0) agent.escapeT -= dtf;
    var sig = Math.round(P.hp) + "|" + gear.pick + "|" + gear.sword + "|" + gear.armor + "|" + gear.gems + "|" + gear.dirt + "|" + stat.ore + "|" + stat.chest + "|" + stat.kill + "|" + exploredCount + "|" + wins + "|" + ((P.x / (TS * 8)) | 0) + "|" + ((P.y / (TS * 8)) | 0);
    if (sig !== agent.progSig) { agent.progSig = sig; agent.progT = 0; }
    else if ((agent.progT += dtf) > 3600) {                    // 60s with ZERO progress (hp/gear/loot/map/position): deadlock
      agent.progT = 0; agent.escapeT = 600;
      agent.path = null; agent.tgt = null;
      agent.badTs.push({ x: (P.x / TS) | 0, y: (P.y / TS) | 0, life: 1800 }); if (agent.badTs.length > 4) agent.badTs.shift();
      msg("⛏️ Deadlock detected — breakout expedition!"); say("Enough! Digging my way out of here.");
    }
    if (get(((P.x + P.w / 2) / TS) | 0, ((P.y + P.h - 4) / TS) | 0) === LAVA) {   // in lava: swim out!
      if (agent.jumpCD <= 0) { P.vy = -JUMP * 0.8; agent.jumpCD = 8; }
      P.vx = agent.exdir * MOVE; say("Hot hot hot!");
    }
    for (var bi = agent.badTs.length - 1; bi >= 0; bi--) { agent.badTs[bi].life -= dtf; if (agent.badTs[bi].life <= 0) agent.badTs.splice(bi, 1); }
    if (!agent.anchor) agent.anchor = { x: P.x, y: P.y };
    if (P.ground && Math.hypot(P.x - agent.anchor.x, P.y - agent.anchor.y) > TS * 1.5) { agent.anchor.x = P.x; agent.anchor.y = P.y; agent.stuck = 0; }
    else agent.stuck += dtf;                                  // jump arcs don't count: only grounded displacement resets the timer
    if (!agent.camp) agent.camp = { x: P.x, y: P.y };
    if (Math.hypot(P.x - agent.camp.x, P.y - agent.camp.y) > TS * 6) { agent.camp.x = P.x; agent.camp.y = P.y; agent.campT = 0; }
    else agent.campT += dtf;                                  // loitering timer: too long near one spot => wanderlust
    var ne = nearestEnemy();
    if (ne && ne.d < TS * 2.6) { P.face = ne.e.x > P.x ? 1 : -1; attack(); }
    if (ne && ne.d < TS * 3.5 && !agent.lowHP && agent.avoidT <= 0 && agent.escapeT <= 0) {   // close-range melee
      var fmid = ((P.x + P.w / 2) / TS) | 0, ffoot = ((P.y + P.h - 3) / TS) | 0, fhead = ((P.y + 3) / TS) | 0, edx = ne.e.x - P.x;
      if (agent.atk > 10 && ne.d < TS * 1.4) { P.vx = (edx > 0 ? -1 : 1) * MOVE * 0.8; }        // kite while the sword recovers
      else if (Math.abs(edx) > TS * 0.6) {
        P.face = edx > 0 ? 1 : -1; P.vx = P.face * MOVE;
        var ffx = fmid + P.face;
        if (isSolid(ffx, ffoot) || isSolid(ffx, fhead)) {
          if (P.ground && agent.jumpCD <= 0 && !isSolid(ffx, ffoot - 1) && !isSolid(fmid, fhead - 1)) { P.vy = -JUMP; agent.jumpCD = 16; }
          else tryMine(ffx, isSolid(ffx, fhead) ? fhead : ffoot);
        }
      } else P.vx *= 0.6;
      if (ne.e.y + ne.e.h < P.y + 2 && P.ground && agent.jumpCD <= 0 && !isSolid(fmid, ((P.y - 3) / TS) | 0)) { P.vy = -JUMP; agent.jumpCD = 16; }  // hop at bats only with clear headroom
      if (agent.stuck > 120) { agent.avoidT = 300; agent.stuck = 0; agent.anchor = { x: P.x, y: P.y }; }   // enemy unreachable: disengage for a while
      return;
    }
    var wp = nextWaypoint();
    var tx = wp ? wp.x : (agent.tgt ? agent.tgt.x : null), ty = wp ? wp.y : (agent.tgt ? agent.tgt.y : null);
    if (tx !== null) moveToward(tx, ty); else P.vx *= 0.6;
    if (agent.wantUp && !P.ground && P.vy > -2.5) {            // near jump apex: pack a dirt block underfoot (pillar up)
      var pbx = ((P.x + P.w / 2) / TS) | 0, pby = (((P.y + P.h) / TS) | 0) + 1;
      if (get(pbx, pby) === AIR && gear.dirt > 0) {
        setT(pbx, pby, DIRT); gear.dirt--; burst((pbx + 0.5) * TS, (pby + 0.5) * TS, "#6e4a28", 5);
        agent.hopN = 0; agent.stuck = Math.max(0, agent.stuck - 40);
        if (gear.dirt === 0) msg("🧱 Out of dirt blocks!");
      }
      agent.wantUp = false;
    }
    if (agent.stuck > 45 && tx !== null && agent.mineF !== frame) {
      var mid = ((P.x + P.w / 2) / TS) | 0, cy = ((P.y + P.h / 2) / TS) | 0, ddx = tx - mid, ddy = ty - cy;
      var dgx, dgy;                                          // mine ONE tile per frame so digP accumulates
      if (Math.abs(ddx) >= Math.abs(ddy)) { dgx = mid + (ddx >= 0 ? 1 : -1); dgy = ((P.y + P.h - 3) / TS) | 0; if (!isSolid(dgx, dgy)) dgy = ((P.y + 3) / TS) | 0; }
      else if (ddy < 0) { dgx = mid; dgy = ((P.y - 3) / TS) | 0; }
      else { dgx = mid; dgy = ((P.y + P.h + 2) / TS) | 0; }
      if (!isSolid(dgx, dgy) || get(dgx, dgy) === BEDROCK) {
        if (ddy < 0) { dgx = -1; }                             // up-target with open air above: digging the floor won't help
        else {
          dgx = mid; dgy = ((P.y + P.h + 2) / TS) | 0;
          if (!isSolid(dgx, dgy)) { var l2 = ((P.x + 1) / TS) | 0, r2 = ((P.x + P.w - 1) / TS) | 0; if (isSolid(l2, dgy) && get(l2, dgy) !== BEDROCK) dgx = l2; else if (isSolid(r2, dgy) && get(r2, dgy) !== BEDROCK) dgx = r2; }
        }
      }
      if (dgx >= 0) tryMine(dgx, dgy);
    }
    if (agent.stuck > 100) {                                   // last resort: random wander to shake out of odd geometry
      if (!agent.wanderT || agent.wanderT <= 0) { agent.wanderT = 30 + random() * 40; agent.wanderD = random() < 0.5 ? -1 : 1; }
      agent.wanderT -= dtf;
      P.vx = agent.wanderD * MOVE * (0.6 + random() * 0.5); P.face = agent.wanderD;
      if (P.ground && agent.jumpCD <= 0 && random() < 0.2) { P.vy = -JUMP; agent.jumpCD = 14; }
    }
    if (agent.stuck > 170) { banTarget(); agent.exdir = -agent.exdir; agent.stuck = 0; agent.anchor = { x: P.x, y: P.y }; agent.wanderT = 0; }
  }

  /* ---------------- fog / goal / world reset ---------------- */
  function reveal() {
    var cx = (P.x / TS) | 0, cy = (P.y / TS) | 0, R = 9;
    // Surface skyline is visible; underground remains explored through local observations.
    if(cy <= (surf[cx] || 0)+2) for(var sx=Math.max(0,cx-30);sx<=Math.min(WW-1,cx+30);sx++)
      for(var sy=Math.max(0,cy-25);sy<=Math.min(WH-1,surf[sx]);sy++)
        if(!explored[idx(sx,sy)]){explored[idx(sx,sy)]=1;exploredCount++;}

    for (var y = cy - R; y <= cy + R; y++) for (var x = cx - R; x <= cx + R; x++)
      if (inb(x, y) && !explored[idx(x, y)] && (x - cx) * (x - cx) + (y - cy) * (y - cy) <= R * R) { explored[idx(x, y)] = 1; exploredCount++; }
  }
  function checkGoal() {
    if (get(goal.x, goal.y) !== GOAL || P.dead || P.hp<=0 || !guardianDefeatedByPlayer) return;
    var d = Math.hypot((goal.x + 0.5) * TS - (P.x + P.w / 2), (goal.y + 0.5) * TS - (P.y + P.h / 2));
    if (d < TS * 1.8) {
      setT(goal.x, goal.y, AIR); setT(goal.x, goal.y - 1, AIR); wins++;
      if(jevEpisodeManaged)jevEpisodeTerminal=true;
      msg(jevEpisodeManaged?tr("🚪 VICTORY GATE cleared! Episode complete.","🚪 已穿越胜利之门！本局完成。"):"🚪 VICTORY GATE cleared! World " + wins + " done — fresh start incoming."); say(pickThink("WIN"));
      burst((goal.x + 0.5) * TS, (goal.y + 0.5) * TS, "#ffd54a", 34); regenT = 280;
    }
  }
  /* ---------------- random world events: meteor / monster wave / supply drop ---------------- */
  function revealAt(cx, cy, R) {
    for (var y = cy - R; y <= cy + R; y++) for (var x = cx - R; x <= cx + R; x++)
      if (inb(x, y) && !explored[idx(x, y)] && (x - cx) * (x - cx) + (y - cy) * (y - cy) <= R * R) { explored[idx(x, y)] = 1; exploredCount++; }
  }
  function meteorStrike() {
    var cx = Math.max(6, Math.min(WW - 7, ((P.x / TS) | 0) + ((rnd(10, 26) | 0) * (random() < 0.5 ? 1 : -1))));
    var cy = Math.max(6, Math.min(WH - 8, surf[cx] || 40));
    for (var y = cy - 3; y <= cy + 3; y++) for (var x = cx - 4; x <= cx + 4; x++) {
      if (!inb(x, y) || get(x, y) === BEDROCK) continue;
      var dd = (x - cx) * (x - cx) + (y - cy) * (y - cy);
      if (dd <= 8) setT(x, y, AIR);
      else if (dd <= 16 && get(x, y) !== AIR && random() < 0.55) setT(x, y, random() < 0.6 ? GOLD : DIAMOND);
    }
    for (var i = 0; i < 42; i++) parts.push({ x: (cx + cosmeticRnd(-3, 3)) * TS, y: (cy + cosmeticRnd(-4, 0)) * TS, vx: cosmeticRnd(-3, 3), vy: cosmeticRnd(-5, -0.5), l: cosmeticRnd(25, 60), c: i % 2 ? "#ff9c40" : "#ffd54a" });
    revealAt(cx, cy, 7);
    msg("☄️ Meteor strike! Rare ore exposed."); evt.name = "meteor"; evt.label = "METEOR STRIKE — rare ore!"; evt.t = 620;
  }
  function monsterWave() {
    for (var i = 0; i < 3; i++) spawnEnemy(true);
    msg("👹 Monster wave incoming!"); evt.name = "wave"; evt.label = "MONSTER WAVE!"; evt.t = 620;
  }
  function supplyDrop() {
    for (var tr = 0; tr < 24; tr++) {
      var cx = Math.max(3, Math.min(WW - 4, ((P.x / TS) | 0) + ((rnd(6, 18) | 0) * (random() < 0.5 ? 1 : -1))));
      var cy = (surf[cx] || 40) - 1;
      if (!inb(cx, cy) || get(cx, cy) !== AIR) continue;
      setT(cx, cy, CHEST); chests.push({ x: cx, y: cy }); revealAt(cx, cy, 5);
      burst((cx + 0.5) * TS, (cy + 0.5) * TS, "#ffd24a", 14);
      msg("🎁 Supply chest dropped nearby!"); evt.name = "supply"; evt.label = "SUPPLY DROP — free chest!"; evt.t = 620;
      return;
    }
  }
  function updEvents(dtf) {
    if (evt.t > 0) { evt.t -= dtf; if (evt.t <= 0) evt.name = ""; }
    evt.timer -= dtf;
    if (evt.timer <= 0) {
      evt.timer = rnd(1700, 3200);
      var r = random();
      if (r < 0.34) meteorStrike(); else if (r < 0.67) monsterWave(); else supplyDrop();
    }
  }
  function newWorld(keepGear, keepWins) {
    episodeGeneration++;
    jevEpisodeManaged=false;jevEpisodeTerminal=false;
    enemies.length = 0; drops.length = 0; parts.length = 0;
    guardianDefeatedByPlayer=false;guardianDefeatedVia=null;
    generate(); spawnBosses(); spawnSeededOrdinaryEnemies();
    if (!keepGear) { gear.pick = 1; gear.sword = 1; gear.armor = 0; gear.gems = 0; gear.pts = 0; gear.dirt = 5;
      gear.swordMul = 1; gear.pickMul = 1; gear.armorMul = 1;
      if (!keepWins) { wins = 0; deaths = 0; progression=freshProgression();combatEvents=[];gear.potAtk = 0; gear.potArm = 0; P.maxhp = 100; } }   // potions persist across cleared worlds
    gateFails = 0;
    resetPlayer(); agent.state = "EXPLORE"; agent.path = null; agent.stuck = 0; regenT = 0; showMap = false;
    evt.name = ""; evt.label = ""; evt.t = 0; evt.timer = 1900;
    buffs.speed = 0; buffs.power = 0; buffs.shield = 0; buffs.regen = 0;
    msg("🌍 New world (procedurally generated, solvable ✔)"); say("A fresh world to conquer!");
  }

  /* ---------------- manual controls ---------------- */
  function aimTile() {
    var mx=Math.floor((P.x+P.w/2)/TS),hy=Math.floor((P.y+3)/TS),fy=Math.floor((P.y+P.h-3)/TS);
    // The player is taller than one tile: near the bottom of a tile, y-2 can
    // still be inside the player's own head tile. Aim at the tile above it.
    if(jevAim==='up')return [mx,Math.floor(P.y/TS)-1];
    if(jevAim==='down')return [mx,Math.floor((P.y+P.h+2)/TS)];
    var tx=jevAim==='left'?Math.floor((P.x-2)/TS):Math.floor((P.x+P.w+2)/TS);
    return [tx,isSolid(tx,hy)?hy:fy];
  }
  function manual() {
    var L=keys.ArrowLeft||keys.a,R=keys.ArrowRight||keys.d,U=keys.ArrowUp||keys.w,D=keys.ArrowDown||keys.s;
    if(U)jevAim='up';else if(D)jevAim='down';else if(L)jevAim='left';else if(R)jevAim='right';
    if(L){P.vx=-MOVE;P.face=-1}else if(R){P.vx=MOVE;P.face=1}else P.vx*=.7;
    if(P.ground&&keys[' '])P.vy=-JUMP;
    if(keys.x||keys.j)attack();
    var tile=aimTile();
    if(keys.z||keys.k)tryMine(tile[0],tile[1]);
    if((keys.c||keys.b)&&gear.dirt>0&&(P.placeCD||0)<=0){
      var tx=tile[0],ty=tile[1];
      if(get(tx,ty)===AIR&&!(tx*TS<P.x+P.w&&tx*TS+TS>P.x&&ty*TS<P.y+P.h&&ty*TS+TS>P.y)){setT(tx,ty,DIRT);gear.dirt--;P.placeCD=12;burst((tx+.5)*TS,(ty+.5)*TS,'#6e4a28',4)}
    }
    if((P.placeCD||0)>0)P.placeCD--;
  }

  function update(dtf) {
    // A completed model episode is absorbing. Before completion, inference
    // waits still run the original physics, hazards, enemies and respawns.
    if(jevEpisodeTerminal)return;
    frame++;
    if (P.dead > 0) { P.dead -= dtf; if (P.dead <= 0) resetPlayer(true); }
    else {
      if (agent.on) { jevRuleFrames++;if (agent.decideT === undefined) agent.decideT = 0; agent.decideT -= dtf; if (agent.decideT <= 0) { jevRuleDecisions++;decide(); agent.decideT = 12; } act(dtf); }
      else {if(jevFrames>0)jevAppliedFrames++;manual();}
      if (buffs.speed > 0) P.vx *= 1.35;
      step(P, dtf);
      if (buffs.regen > 0) P.hp = Math.min(P.maxhp, P.hp + 0.05 * dtf);
      if (P.hp < P.maxhp && frame - lastHitF > 480) {          // out-of-combat regen: 8s untouched => slow heal
        P.hp = Math.min(P.maxhp, P.hp + 0.07 * dtf);
        if (frame % 30 === 0) burst(P.x + P.w / 2, P.y + 2, "#8fe388", 1);
      }
      var footT = get(((P.x + P.w / 2) / TS) | 0, ((P.y + P.h - 4) / TS) | 0);
      if (footT === LAVA) {
        P.hp -= (buffs.shield > 0 ? 0.6 : 1.6) * dtf; lastHitF = frame;
        if (frame % 7 === 0) burst(P.x + P.w / 2, P.y + 2, "#ff9c40", 2);
        if (P.hp <= 0) die();
      } else if (footT === MIASMA) {                           // poison gas: steady drain
        P.hp -= (buffs.shield > 0 ? 0.06 : 0.16) * dtf; lastHitF = frame;
        if (frame % 12 === 0) burst(P.x + P.w / 2, P.y + 2, "#a5d16b", 1);
        if (P.hp <= 0) die();
      }
      if (P.y > WH * TS + 40) { P.hp = 0; die(); }
      reveal(); checkChest(); checkGoal();if(jevEpisodeTerminal)return;
    }
    if (P.inv > 0) P.inv -= dtf;
    if (agent.atk > 0) agent.atk -= dtf;
    if (frame % 140 === 0) spawnEnemy();
    updEnemies(dtf); updDrops(dtf); updItems(dtf); updParts(dtf); updEvents(dtf);
    for (var i = msgs.length - 1; i >= 0; i--) { msgs[i].life -= dtf; if (msgs[i].life <= 0) msgs.splice(i, 1); }
    if (regenT > 0) { regenT -= dtf; if (regenT <= 0) newWorld(false, true); }
    if (frame % 10 === 0) hud();
  }
  var last=0,accumulator=0;
  function tick(ts){
    if(typeof ts!=='number'||!Number.isFinite(ts))throw new TypeError('tick requires a finite monotonic timestamp');
    accumulator=Math.min(50,accumulator+(ts-last||0));last=ts;
    if(jevActive&&!isHidden()&&(!jevModelStepping||jevFrames>0)){
      while(accumulator>=1000/60){
        if(jevModelStepping&&jevFrames<=0){accumulator=0;break;}
        accumulator-=1000/60;
        jevAdvance();
        if(frame%6===0)jevPublish();
      }
    }else accumulator=0;
    return frame;
  }
  function advanceTo(target){
    if(!Number.isSafeInteger(target)||target<frame)throw new RangeError('invalid replay target frame');
    var safety=0;
    while(frame<target){
      if(++safety>200000||jevEpisodeTerminal)throw new Error('unreachable_archived_frame');
      jevAdvance();
    }
    if(frame!==target)throw new Error('archived_frame_mismatch');
    return frame;
  }
  // Jev adapter: original physics/rendering; original built-in AI stays disabled.
  var jevEntityIds=new WeakMap(),jevEntitySeq=0,jevCollectedItems=[],jevKnownGuardians={};
  function jevEntityId(e){if(!jevEntityIds.has(e))jevEntityIds.set(e,++jevEntitySeq);return jevEntityIds.get(e)}
  var jevLastDamageFrame=-99999,jevTool=null;
  var jevControl={effects:[],status:'idle',subgoal:null,event:null,no_progress_count:0},jevStart=null,jevElapsed=0,jevVisited={},jevKnownSurfaces={};
  var jevActive=false, jevLocked=false, jevModelStepping=false, jevFrames=0, jevAction=null, jevResolve=null, jevHistory=[], jevPositions=[], jevCalls=0, jevSurfaceAnchor=null;
  var jevAim='right',jevKeys={},jevNames={},jevEffects=[],jevBefore=null,jevRuleFrames=0,jevRuleDecisions=0,jevAppliedFrames=0;
  ['left','right','up','down'].forEach(function(d){['move','mine','attack','place'].forEach(function(tool){[false,true].forEach(function(jump){var id=(jump?'jump_':'')+tool+'_'+d,k=[{left:'ArrowLeft',right:'ArrowRight',up:'ArrowUp',down:'ArrowDown'}[d]];if(tool!=='move')k.push({mine:'k',attack:'x',place:'c'}[tool]);if(jump)k.push(' ');jevKeys[id]=k;jevNames[id]=(jump?'Jump + ':'')+{move:'Move / aim',mine:'Mine',attack:'Attack',place:'Place'}[tool]+' '+d})})});jevKeys.wait=[];jevNames.wait='Wait';['explore_right','explore_left','approach_guardian','fight_guardian','return_surface','cross_gap_right','clear_right','fight_nearest','recover','reach_known_goal','pass_enemy_right','retreat_left','collect_visible','collect_visible_gem'].forEach(function(a){jevKeys[a]=[];jevNames[a]=a});

  function jevRememberObservedGuardians(obs){
    // Called only at the model's observation boundary. Internal executor frames
    // must not create a history of enemies the model has never actually seen.
    (obs.enemies||[]).filter(function(e){return e.gate_guardian}).forEach(function(e){
      var g=Object.assign({},e,e.geometry||{});
      jevKnownGuardians[e.id]={id:e.id,x:g.x,y:g.y,width:g.width,height:g.height,last_seen_frame:obs.frame};
    });
  }
  function jevGuardianTarget(obs,allowMemory){
    var p=Object.assign({},obs.player,obs.player.geometry||{});
    var guardians=obs.enemies.filter(function(e){return e.gate_guardian}).sort(function(a,b){
      return Math.hypot(a.x-p.x,a.y-p.y)-Math.hypot(b.x-p.x,b.y-p.y)||a.id-b.id;
    });
    if(guardians.length){var e=guardians[0],g=Object.assign({},e,e.geometry||{});return {kind:'guardian',id:e.id,x:g.x,y:g.y,width:g.width,height:g.height,last_seen_frame:obs.frame,visible:true}}
    var history=allowMemory?(obs.known_guardians||[]).slice().sort(function(a,b){return b.last_seen_frame-a.last_seen_frame||a.id-b.id}):[];
    return history.length?Object.assign({},history[0],{kind:'guardian',visible:false}):null;
  }

  function jevVisibleTile(x,y){return inb(x,y)&&explored[idx(x,y)]?get(x,y):-1}
  function jevToolTargets(){
    var mx=Math.floor((P.x+P.w/2)/TS),hy=Math.floor((P.y+3)/TS),fy=Math.floor((P.y+P.h-3)/TS),result={};
    ['left','right','up','down'].forEach(function(d){
      var tx=d==='left'?Math.floor((P.x-2)/TS):d==='right'?Math.floor((P.x+P.w+2)/TS):mx;
      var ty=d==='up'?Math.floor(P.y/TS)-1:d==='down'?Math.floor((P.y+P.h+2)/TS):SOLID[jevVisibleTile(tx,hy)]?hy:fy;
      var t=jevVisibleTile(tx,ty);result[d]={tile:[tx,ty],value:t,solid:!!SOLID[t],mineable:!!HARD[t],hardness:HARD[t]||0};
    });
    return result;
  }
  function jevSnapshot(){
    var px=Math.floor((P.x+P.w/2)/TS),py=Math.floor((P.y+P.h/2)/TS),tiles=[];
    var recent=jevPositions.slice(-8);
    if(!recent.length||recent[recent.length-1][0]!==px||recent[recent.length-1][1]!==py)recent.push([px,py]);
    recent=recent.slice(-8);
    for(var y=py-6;y<=py+7;y++){var row=[];for(var x=px-10;x<=px+10;x++)row.push(inb(x,y)&&explored[idx(x,y)]?get(x,y):-1);tiles.push(row)}
    var visibleGrass=[];
    for(var rowIndex=0;rowIndex<tiles.length;rowIndex++)for(var colIndex=0;colIndex<tiles[rowIndex].length;colIndex++)
      if(tiles[rowIndex][colIndex]===GRASS)visibleGrass.push([px-10+colIndex,py-6+rowIndex]);
    visibleGrass.forEach(function(cell){jevKnownSurfaces[cell.join(',')]=frame});
    if(visibleGrass.length){visibleGrass.sort(function(a,b){return Math.abs(a[0]-px)+Math.abs(a[1]-py)-Math.abs(b[0]-px)-Math.abs(b[1]-py)});jevSurfaceAnchor=visibleGrass[0]}
    var visibleEnemies=enemies.filter(function(e){return Math.abs(e.x-P.x)<TS*12&&Math.abs(e.y-P.y)<TS*9&&explored[idx(Math.floor(e.x/TS),Math.floor(e.y/TS))]}).map(function(e){return {id:jevEntityId(e),x:+(e.x/TS).toFixed(1),y:+(e.y/TS).toFixed(1),width:+(e.w/TS).toFixed(2),height:+(e.h/TS).toFixed(2),geometry:{x:e.x/TS,y:e.y/TS,width:e.w/TS,height:e.h/TS},kind:e.kind,hp:e.hp,boss:!!e.boss,gate_guardian:!!e.gateGuardian,player_damage_received:e.playerDamage||0,level:e.lv}}).slice(0,10);
    return structuredClone({control:{executor_revision:'visible-hierarchy-v18-targeted-navigation',deadline_frames:jevControl.deadline_frames||0,target:jevControl.target||null,path:jevControl.path||[],intermediate_events:jevControl.intermediate_events||[],subgoal:jevControl.subgoal,status:jevControl.status,recent_effects:jevControl.effects,events:jevControl.event?[jevControl.event]:[],no_progress_count:jevControl.no_progress_count,failed_targets:jevControl.failed_targets||[],fallback_actions:jevRuleDecisions,target_surface:jevControl.target_surface||null,target_surface_owner:jevControl.target_surface_owner||null,execution_stage:jevControl.execution_stage||null,failure_reason:jevControl.failure_reason||null,execution_counts:jevControl.execution_counts||{mined:0,placed:0}},known_guardians:Object.keys(jevKnownGuardians).map(function(id){return Object.assign({},jevKnownGuardians[id])}),visited_tiles:Object.keys(jevVisited).slice(-64),known_surface_route:Object.keys(jevKnownSurfaces).slice(-64).map(function(key){return {cell:key.split(',').map(Number),last_seen_frame:jevKnownSurfaces[key],certainty:'previously_observed; may change'}}),player:{x:+(P.x/TS).toFixed(1),y:+(P.y/TS).toFixed(1),width:P.w/TS,height:P.h/TS,geometry:{x:P.x/TS,y:P.y/TS},vx:+(P.vx/TS).toFixed(3),vy:+(P.vy/TS).toFixed(3),invulnerable_frames:P.inv,tile:[px,py],hp:Math.round(P.hp),max_hp:P.maxhp,on_ground:P.ground,facing:P.face,aim:jevAim,respawning:P.dead>0},equipment:JSON.parse(JSON.stringify(gear)),stats:JSON.parse(JSON.stringify(stat)),wins:wins,deaths:deaths,
      objective:{revision:'terramai-gate-guardian-v1',gate_requires_guardian:true,gate_unlocked:guardianDefeatedByPlayer,
        guardian_defeated_by_player:guardianDefeatedByPlayer,guardian_defeated_via:guardianDefeatedVia,
        visible_guardian_ids:visibleEnemies.filter(function(e){return e.gate_guardian}).map(function(e){return e.id})},
      progression:JSON.parse(JSON.stringify(progression)),recent_combat_events:combatEvents.slice(-8),episode_terminal:jevEpisodeTerminal,
      known_goal:explored[idx(goal.x,goal.y)]&&get(goal.x,goal.y)===GOAL?[goal.x,goal.y]:null,last_known_surface:jevSurfaceAnchor,recent_player_tiles:recent,
      map:{origin:[px-10,py-6],tiles:tiles,legend:{'-1':'未知',0:'空气',1:'泥土',2:'草地',3:'石头',4:'铜',5:'铁',6:'金',7:'钻石',8:'宝石',9:'木头',10:'树叶',11:'基岩',12:'胜利之门',13:'宝箱',14:'熔岩',15:'毒雾'}},
      enemies:visibleEnemies,
      execution_audit:{model_decisions:jevCalls,deterministic_action_frames:jevAppliedFrames,rule_takeover_frames:jevRuleFrames,rule_takeover_count:jevRuleDecisions,builtin_ai_active:agent.on},
      collected_items:jevCollectedItems.slice(-12),tool_targets:jevToolTargets(),last_effects:jevEffects.slice(-6),
      visible_collectibles:items.filter(function(it){return Math.abs(it.x-P.x)<TS*12&&Math.abs(it.y-P.y)<TS*9&&jevVisibleTile(Math.floor(it.x/TS),Math.floor(it.y/TS))!==-1}).map(function(it){var f=FOOD[it.kind];return {id:jevEntityId(it),x:+(it.x/TS).toFixed(1),y:+(it.y/TS).toFixed(1),kind:it.kind,heal:f.heal||0,buff:f.buff||null}}),
      visible_equipment_drops:drops.filter(function(d){return Math.abs(d.x-P.x)<TS*12&&Math.abs(d.y-P.y)<TS*9&&jevVisibleTile(Math.floor(d.x/TS),Math.floor(d.y/TS))!==-1}).map(function(d){return {id:jevEntityId(d),x:+(d.x/TS).toFixed(1),y:+(d.y/TS).toFixed(1)}}),
      active_buffs:JSON.parse(JSON.stringify(buffs)),recovery_wait_frames:Math.max(0,480-(frame-lastHitF)),
      last_actions:jevHistory.slice(-6),decisions:jevCalls,frame:frame,
      timing:{mode:jevActive?(jevModelStepping?'model_step':'realtime'):'paused',clock_contract:jevModelStepping?'stepped-v1':'realtime-v1',awaiting_model:jevAwaiting,inference_world_paused:jevModelStepping,visibility_paused:isHidden(),waiting_input:'release_keys',frames_per_second:60,action_frames:360,intent_max_frames:360,atomic_action_frames:36,event_interrupts:true,note:jevModelStepping?'模型分步：观察和推理时暂停；原子动作36帧，意图最多360帧，目标完成/未知边界/不可恢复受阻时返回，动作间暂停。':jevAwaiting?'模型实时：推理等待期间世界继续运行，按键已松开；重力、敌人和事件持续推进。':'实时：世界持续运行，动作完成后角色、敌人和事件仍持续推进。'}});
  }
  function jevClearIntentTarget(){
    // Death/respawn invalidates execution targets, never explored world memory.
    if(!jevControl)return;
    jevControl.target_surface=null;jevControl.target_surface_owner=null;
    jevControl.target=null;jevControl.path=[];jevControl.subgoal=null;
  }
  function jevReturnSurfaceAnchor(obs){
    // Keep in sync with return_surface_anchor in the public Python contract.
    var c=obs.control||{},anchor=c.target_surface,events=c.events||[],m=obs.map;
    function validSupport(cell){
      if(!Array.isArray(cell)||cell.length!==2)return false;
      var row=m.tiles[cell[1]-m.origin[1]],tile=row&&row[cell[0]-m.origin[0]];
      // Out-of-view/unknown historical anchors remain uncertain memory; an
      // observed removed support is invalid, including the fallback anchor.
      return tile===undefined||tile===-1||!!SOLID[tile];
    }
    var retain=c.target_surface_owner==='return_surface'&&c.status!=='completed'&&!obs.player.respawning&&validSupport(anchor);
    if(events.some(function(e){return ['goal_reached','goal_door_entered','death_or_respawn','respawned'].indexOf(e)>=0}))retain=false;
    return retain?anchor:validSupport(obs.last_known_surface)?obs.last_known_surface:null;
  }
  function jevVisiblePath(obs,gx,gy) {
    var sx=obs.player.tile[0],sy=obs.player.tile[1],m=obs.map;
    function inb(x,y){return x>=m.origin[0]&&y>=m.origin[1]&&y<m.origin[1]+m.tiles.length&&x<m.origin[0]+m.tiles[0].length}
    function publicTile(x,y){return inb(x,y)?m.tiles[y-m.origin[1]][x-m.origin[0]]:-1}
    if (!inb(sx, sy) || !inb(gx, gy)) return null;
    var N = WW * WH, dist = new Float32Array(N), prev = new Int32Array(N);
    dist.fill(Infinity); prev.fill(-1);
    var start = idx(sx, sy), goalI = idx(gx, gy); dist[start] = 0;
    var heap = [[0, start]];
    function push(d, i) { heap.push([d, i]); var c = heap.length - 1; while (c > 0) { var p = (c - 1) >> 1; if (heap[p][0] <= heap[c][0]) break; var t = heap[p]; heap[p] = heap[c]; heap[c] = t; c = p; } }
    function pop() { var top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; var c = 0; for (; ;) { var l = 2 * c + 1, r = l + 1, s = c; if (l < heap.length && heap[l][0] < heap[s][0]) s = l; if (r < heap.length && heap[r][0] < heap[s][0]) s = r; if (s === c) break; var t = heap[s]; heap[s] = heap[c]; heap[c] = t; c = s; } } return top; }
    var exp = 0;
    while (heap.length) {
      var cur = pop(), cd = cur[0], ci = cur[1];
      if (cd > dist[ci]) continue;
      if (ci === goalI || ++exp > 12000) break;
      var cx = ci % WW, cy = (ci / WW) | 0, nx = [cx + 1, cx - 1, cx, cx], ny = [cy, cy, cy + 1, cy - 1];
      for (var k = 0; k < 4; k++) {
        if (!inb(nx[k], ny[k])) continue;
        var ni = idx(nx[k], ny[k]), t2=publicTile(nx[k],ny[k]), c2=t2<0?Infinity:passCost(t2);
        if (c2 === Infinity) continue;
        var nd = cd + c2; if (nd < dist[ni]) { dist[ni] = nd; prev[ni] = ci; push(nd, ni); }
      }
    }
    if (!isFinite(dist[goalI])) return null;
    var path = [], p = goalI, guard = 0;
    while (p !== -1 && guard++ < 5000) { path.push({ x: p % WW, y: (p / WW) | 0 }); p = prev[p]; }
    path.reverse(); return path;
  }

  function jevEscapeHazardAtStart(action) {
    if (['return_surface','cross_gap_right'].indexOf(action)<0) return null;
    // Only continue damage already visible and in contact when the model's
    // selected escape starts. Newly encountered terrain is a fresh decision.
    var obs=jevSnapshot(),m=obs.map,x=Math.floor((P.x+P.w/2)/TS),y=Math.floor((P.y+P.h-4)/TS);
    var row=m.tiles[y-m.origin[1]],kind=row&&row[x-m.origin[0]];
    if(kind!==LAVA&&kind!==MIASMA)return null;
    var cells={};m.tiles.forEach(function(r,dy){r.forEach(function(t,dx){if(t===kind)cells[(m.origin[0]+dx)+','+(m.origin[1]+dy)]=true})});
    return {kind:kind,cells:cells};
  }
  function jevContinuedKnownEnvironmentDamage(oldHP,oldInv) {
    var h=jevStart&&jevStart.escape_hazard;
    if(!h||P.inv>oldInv)return false; // enemy contact must still interrupt escape
    var x=Math.floor((P.x+P.w/2)/TS),y=Math.floor((P.y+P.h-4)/TS);
    if(!h.cells[x+','+y]||jevVisibleTile(x,y)!==h.kind)return false;
    var maximum=h.kind===LAVA?(buffs.shield>0?.6:1.6):(buffs.shield>0?.06:.16);
    return oldHP-P.hp<=maximum+1e-6;
  }
  function jevTerrainChange(x,y,before,after){
    if(!jevAction||!jevStart||before<0||after<0||before===after)return;
    var cells=jevStart.terrain_changes||(jevStart.terrain_changes={}),key=x+','+y;
    if(!cells[key])cells[key]={before:before,after:after};else cells[key].after=after;
  }
  function jevProgressState(){
    var cells=jevStart&&jevStart.terrain_changes||{},changed=Object.keys(cells).filter(function(k){return cells[k].before!==cells[k].after}).sort();
    return {x:P.x,y:P.y,deaths:deaths,hp:P.hp,ore:stat.ore,gem:stat.gem,chest:stat.chest,kill:stat.kill,attack_damage:progression.player_attack_damage,
      pick:gear.pick,sword:gear.sword,armor:gear.armor,terrain:changed.map(function(k){return k+':'+cells[k].after}).join(';'),terrain_cells:changed.length,
      dig:agent.digT?agent.digT.x+','+agent.digT.y:null,dig_progress:agent.digP||0};
  }
  function jevMeaningfulProgress(before,after){
    if(!before||before.deaths!==after.deaths)return false;
    if(Math.hypot(after.x-before.x,after.y-before.y)>=TS*.25||after.terrain!==before.terrain)return true;
    if(['hp','ore','gem','chest','kill','pick','sword','armor','attack_damage'].some(function(k){return after[k]>before[k]+.01}))return true;
    return !!after.dig&&after.dig===before.dig&&after.dig_progress>before.dig_progress;
  }
  function jevAdvance(){
          if(jevEpisodeTerminal)return;
          var grounded=P.ground,oldDeaths=deaths,oldHP=P.hp,oldInv=P.inv,wasRespawning=P.dead>0;
          jevTool=null;
          if (jevFrames > 0 && jevAction) { keys = {}; (jevNames[jevAction]===jevAction?jevIntentKeys(jevAction):jevKeys[jevAction]).forEach(function(k){keys[k]=1}); }
          if(jevTool&&jevTool.kind==='mine'){var beforeMine=gear.dirt,beforeTile=jevVisibleTile(jevTool.x,jevTool.y);tryMine(jevTool.x,jevTool.y);jevTerrainChange(jevTool.x,jevTool.y,beforeTile,jevVisibleTile(jevTool.x,jevTool.y));if(gear.dirt>beforeMine)jevControl.execution_counts.mined+=gear.dirt-beforeMine}
          update(1);
          var cell=Math.floor((P.x+P.w/2)/TS)+','+Math.floor((P.y+P.h/2)/TS);jevVisited[cell]=(jevVisited[cell]||0)+1;
          if(jevFrames>0){jevElapsed++;jevFrames--;
            if(jevStart&&wins>jevStart.wins){jevControl.event='goal_door_entered';jevFrames=0;jevFinish();return}
            if(jevNames[jevAction]!==jevAction){if(!jevFrames)jevFinish();return}
            if(deaths>oldDeaths||P.dead>0&&jevAction!=='recover'){jevControl.event='death_or_respawn';jevFrames=0}
            else if(wasRespawning&&P.dead<=0){jevControl.event='respawned';jevFrames=0}
            // Intent boundaries have priority over an incidental damage event.
            if(['unknown_frontier','target_missing','blocked_unknown_surface','goal_reached','goal_locked_guardian','resources_unavailable','blocked_ceiling','threat_detected','target_completed'].indexOf(jevControl.event)>=0)jevFrames=0;
            if(P.hp<oldHP-.01){
              jevLastDamageFrame=frame;
              var knownEscapeDamage=jevContinuedKnownEnvironmentDamage(oldHP,oldInv);
              jevControl.intermediate_events.push({event:'damage',frame:frame,hp:P.hp,known_environment_escape:knownEscapeDamage});
              if(jevFrames>0&&!knownEscapeDamage&&['pass_enemy_right','retreat_left','fight_nearest','fight_guardian'].indexOf(jevAction)<0){jevControl.event='danger_changed';jevControl.failure_reason='new_or_unaccepted_damage';jevFrames=0}
            }
            // These checks must remain live under sustained environmental damage.
            if(jevFrames>0&&!grounded&&P.ground){jevControl.intermediate_events.push({event:'landed',frame:frame});if(jevAction==='cross_gap_right'){jevControl.event='landed';jevFrames=0}}
            if(jevFrames>0&&jevElapsed%90===0&&jevAction!=='recover'){var z=jevControl.progress_checkpoint,now=jevProgressState();if(z&&!jevMeaningfulProgress(z,now)){jevControl.event='blocked';jevControl.failure_reason=jevAction==='fight_nearest'||jevAction==='fight_guardian'?'selected_enemy_no_hit_or_approach_progress_for_90_frames':'no_effective_motion_resource_or_terrain_progress_for_90_frames';jevFrames=0}jevControl.progress_checkpoint=now}
            if(!jevFrames){if(!jevControl.event)jevControl.event='expired';jevFinish()}
          }
  }
  function jevIntentKeys(action){
    // B: fulfil the selected intent with public geometry and original tool costs.
    // No world array, surf[] or unexplored cells are queried for a route.
    if(P.dead>0){jevControl.execution_stage='respawning';if(action!=='recover')jevControl.event='death_or_respawn';return []}
    var obs=jevSnapshot(),m=obs.map,p=Object.assign({},obs.player,obs.player.geometry||{}),tx=p.tile[0],ty=p.tile[1];
    if(action==='reach_known_goal'&&obs.known_goal&&!obs.objective.gate_unlocked&&Math.hypot(obs.known_goal[0]+.5-p.x-p.width/2,obs.known_goal[1]+.5-p.y-p.height/2)<1.8){jevControl.event='goal_locked_guardian';jevControl.failure_reason='gate_requires_player_defeated_guardian';return []}
    function seen(x,y){var row=m.tiles[y-m.origin[1]];return row&&x-m.origin[0]>=0&&x-m.origin[0]<row.length?row[x-m.origin[0]]:-1}
    function solid(t){return !!SOLID[t]}
    function mine(x,y){var t=seen(x,y);if(!HARD[t])return false;var d=Math.hypot(x+.5-p.x-p.width/2,y+.5-p.y-p.height/2);if(d>3)return false;jevTool={kind:'mine',x:x,y:y};return true}
    function material(){
      var options=[];for(var y=m.origin[1];y<m.origin[1]+m.tiles.length;y++)for(var x=m.origin[0];x<m.origin[0]+m.tiles[0].length;x++){
        var t=seen(x,y);if(t!==1&&t!==2&&t!==3)continue;if(jevControl.target_surface&&jevControl.target_surface[0]===x&&jevControl.target_surface[1]===y)continue;
        // Do not dismantle the support this same selected intent just built.
        if(jevStart&&jevStart.placed_supports&&jevStart.placed_supports[x+','+y])continue;
        var d=Math.hypot(x+.5-p.x-p.width/2,y+.5-p.y-p.height/2);
        // Never mine the block supporting our feet to obtain ascent material.
        if(d<=3&&!(x*TS<P.x+P.w&&x*TS+TS>P.x&&y*TS>=P.y+P.h-.1&&y*TS<=P.y+P.h+TS))options.push({x:x,y:y,d:d,cost:HARD[t]});
      }
      options.sort(function(a,b){return a.cost-b.cost||a.d-b.d||a.x-b.x||a.y-b.y});
      if(options.length){mine(options[0].x,options[0].y);return true}return false;
    }
    function place(x,y){
      if(gear.dirt<=0||seen(x,y)!==0||(P.placeCD||0)>0||Math.hypot(x+.5-p.x-p.width/2,y+.5-p.y-p.height/2)>3)return false;
      if(x*TS<P.x+P.w&&x*TS+TS>P.x&&y*TS<P.y+P.h&&y*TS+TS>P.y)return false;
      setT(x,y,DIRT);jevTerrainChange(x,y,0,DIRT);gear.dirt--;P.placeCD=12;jevControl.execution_counts.placed++;
      if(jevStart){jevStart.placed_supports=jevStart.placed_supports||{};jevStart.placed_supports[x+','+y]=true}return true;
    }
    function alignTargetHeight(g){
      // Deterministic execution of the selected approach/combat target only.
      // Every dig/place uses current public tiles, native costs and tool reach.
      var horizontal=g.x+g.width/2-p.x-p.width/2,vertical=g.y+g.height/2-p.y-p.height/2;
      if(Math.abs(horizontal)>1.8)return null;
      if(vertical>2.4){
        jevControl.execution_stage='descend_to_selected_enemy';
        var floorY=Math.floor(p.y+p.height+.1);
        for(var x=Math.floor(p.x);x<=Math.floor(p.x+p.width-.001);x++){
          var value=seen(x,floorY);
          if(value===-1){jevControl.event='unknown_frontier';jevControl.failure_reason='selected_enemy_descent_unknown';return []}
          if(solid(value)){if(mine(x,floorY))return [];jevControl.event='blocked';jevControl.failure_reason='selected_enemy_descent_unmineable';return []}
        }
        return jevKeys.move_down;
      }
      if(vertical<-2.4){
        jevControl.execution_stage='ascend_to_selected_enemy';
        var ceiling=Math.floor(p.y)-1,top=p.on_ground?ceiling-2:ceiling;
        for(var y=ceiling;y>=top;y--)for(var x=Math.floor(p.x);x<=Math.floor(p.x+p.width-.001);x++){
          var value=seen(x,y);
          if(value===-1){jevControl.event='unknown_frontier';jevControl.failure_reason='selected_enemy_ascent_unknown';return []}
          if(solid(value)){
            if(mine(x,y))return [];
            // A higher tile outside tool reach must not prohibit a jump that
            // can put the original sword in range beneath that platform.
            if(y===ceiling){jevControl.event='blocked_ceiling';jevControl.failure_reason='selected_enemy_ascent_unmineable';return []}
          }
        }
        if(!p.on_ground&&P.vy>=0)place(tx,Math.ceil(p.y+p.height-1e-7));
        if(gear.dirt<=0&&p.on_ground&&!material()){jevControl.event='resources_unavailable';jevControl.failure_reason='selected_enemy_ascent_material_unavailable';return []}
        return p.on_ground?jevKeys.jump_move_up:jevKeys.move_up;
      }
      return null;
    }
    var target=jevControl.target;
    if(!target){
      if(action==='approach_guardian'||action==='fight_guardian'){
        target=jevGuardianTarget(obs,action==='approach_guardian');
        if(!target||obs.objective.guardian_defeated_by_player){jevControl.event='target_missing';jevControl.failure_reason='no_observed_living_guardian';return []}
      }else if(['fight_nearest','pass_enemy_right','retreat_left'].indexOf(action)>=0){
        var es=obs.enemies.slice().sort(function(a,b){return Math.hypot(a.x-p.x,a.y-p.y)-Math.hypot(b.x-p.x,b.y-p.y)||a.id-b.id});
        if(!es.length){jevControl.event='target_missing';return []}target={kind:'enemy',id:es[0].id,x:es[0].x,y:es[0].y};
      }else if((action==='collect_visible'||action==='collect_visible_gem')){
        var cs=[];if(action==='collect_visible'){obs.visible_collectibles.forEach(function(c){cs.push({kind:'pickup',id:c.id,x:c.x,y:c.y,priority:0})});obs.visible_equipment_drops.forEach(function(c){cs.push({kind:'pickup',id:c.id,x:c.x,y:c.y,priority:1})});}
        for(var ry=0;ry<m.tiles.length;ry++)for(var rx=0;rx<m.tiles[ry].length;rx++){var v=m.tiles[ry][rx];if(action==='collect_visible_gem'?v===GEM:v===13||v>=4&&v<=8)cs.push({kind:v===13?'chest':'ore',tile:v,x:m.origin[0]+rx,y:m.origin[1]+ry,priority:v===13?2:3})}
        cs.sort(function(a,b){return a.priority-b.priority||Math.hypot(a.x-p.x,a.y-p.y)-Math.hypot(b.x-p.x,b.y-p.y)||a.x-b.x||a.y-b.y});
        if(!cs.length){jevControl.event='target_missing';return []}target=cs[0];target.initial_ore=obs.stats.ore;target.initial_gem=obs.stats.gem;target.initial_chest=obs.stats.chest;target.initial_hp=p.hp;target.initial_gear=JSON.stringify(obs.equipment);target.initial_buffs=JSON.stringify(obs.active_buffs);
      }else if(action==='explore_right'||action==='explore_left'||action==='clear_right'||action==='cross_gap_right'){var choices=[],sign=action==='explore_left'?-1:1;for(var step=1;step<=8;step++){var xx=tx+sign*step;for(var yy=ty-3;yy<=ty+2;yy++)if(seen(xx,yy)===0&&seen(xx,yy-1)===0&&solid(seen(xx,yy+1)))choices.push({kind:'visible_surface_waypoint',x:xx,y:yy})}choices.sort(function(a,b){return sign*(b.x-a.x)||Math.abs(a.y-ty)-Math.abs(b.y-ty)});target=choices[0]||{kind:'visible_horizontal_frontier',x:tx+sign,y:ty};var ep=jevVisiblePath(obs,target.x,target.y);jevControl.path=ep?ep.slice(0,24):[];}
      if(target){jevControl.target=target;jevControl.subgoal={intent:action,target:target};}
    }
    // Newly visible threats return strategy to the model before first contact.
    // Selected combat/pass/retreat intents already accept their enemy target.
    if((action==='explore_right'||action==='reach_known_goal')&&obs.enemies.some(function(e){return e.x+e.width>p.x-1&&e.x-p.x<7&&Math.abs(e.y-p.y)<5})){jevControl.event='threat_detected';return []}
    if(action==='explore_left'&&obs.enemies.some(function(e){return e.x<p.x+p.width+1&&p.x-e.x-e.width<7&&Math.abs(e.y-p.y)<5})){jevControl.event='threat_detected';return []}
    if(target&&(target.kind==='visible_surface_waypoint'||target.kind==='visible_horizontal_frontier')&&(action==='explore_left'?p.x<=target.x:p.x>=target.x)){jevControl.event='target_completed';return []}
    if((action==='collect_visible'||action==='collect_visible_gem')){
      var exists=target.kind==='ore'||target.kind==='chest'?seen(Math.floor(target.x),Math.floor(target.y))===target.tile:obs.visible_collectibles.concat(obs.visible_equipment_drops).some(function(c){return c.id===target.id});
      if(!exists){var gained=target.kind==='ore'?(target.tile===8?obs.stats.gem>target.initial_gem:obs.stats.ore>target.initial_ore):target.kind==='chest'?obs.stats.chest>target.initial_chest:obs.collected_items.some(function(c){return c.id===target.id});jevControl.event=gained?'target_completed':'target_missing';if(!gained)jevControl.failure_reason='resource_left_view_or_disappeared_without_verified_gain';return []}
      if(target.kind==='ore'&&mine(Math.floor(target.x),Math.floor(target.y))){jevControl.execution_stage='collect_mining';return []}
      var route=jevVisiblePath(obs,Math.floor(target.x),Math.floor(target.y));jevControl.path=route?route.slice(0,24):[];
      if(!route){jevControl.event='target_missing';jevControl.failure_reason='no_public_path_to_resource';return []}
    }
    var d=action==='explore_left'?'left':'right',tool='move',jump=false,anchor=action==='return_surface'?jevControl.target_surface:obs.last_known_surface,head=Math.floor(p.y),foot=Math.floor(p.y+p.height-.01),enemyDescent=false;
    if(action==='approach_guardian'){
      var guardian=obs.enemies.find(function(e){return e.id===target.id&&e.gate_guardian});
      if(guardian){var live=Object.assign({},guardian,guardian.geometry||{});Object.assign(target,{x:live.x,y:live.y,width:live.width,height:live.height,visible:true})}
      else target.visible=false;
      if(obs.enemies.some(function(e){return e.id!==target.id&&Math.abs(e.x-p.x)<2&&Math.abs(e.y-p.y)<3})){jevControl.event='threat_detected';return []}
      if(guardian){var body={x:target.x*TS,y:target.y*TS,w:target.width*TS,h:target.height*TS};
        if(['left','right','up','down'].some(function(a){return attackIntersects(attackRectangle(a,p.x*TS,p.y*TS,p.width*TS,p.height*TS),body)})){jevControl.event='target_completed';jevControl.execution_stage='guardian_in_native_attack_range';return []}
      }else if(Math.hypot(target.x+target.width/2-p.x-p.width/2,target.y+target.height/2-p.y-p.height/2)<1.5){jevControl.event='target_missing';jevControl.failure_reason='last_seen_guardian_not_reacquired';return []}
      d=target.x+target.width/2<p.x+p.width/2?'left':'right';
      var aligned=alignTargetHeight(target);if(aligned!==null)return aligned;
      enemyDescent=target.y>p.y+2;
      jevControl.execution_stage=guardian?'approach_visible_guardian':'search_last_observed_guardian_position';
    }
    if(action==='reach_known_goal'){
      var door=obs.known_goal;if(!door){jevControl.event='target_missing';jevControl.failure_reason='goal_not_observed';return []}
      anchor=[door[0],door[1]+1];jevControl.target_surface=anchor;jevControl.target_surface_owner='reach_known_goal';
      var gx=door[0]+.5-(p.x+p.width/2),gy=door[1]+.5-(p.y+p.height/2);
      if(gy>1.6&&Math.abs(gx)<.7){
        jevControl.execution_stage='descend_to_known_door';var floorY=Math.floor((P.y+P.h+2)/TS);
        for(var fx=Math.floor(p.x);fx<=Math.floor(p.x+p.width-.01);fx++)if(solid(seen(fx,floorY))){if(mine(fx,floorY))return [];jevControl.event='blocked_ceiling';jevControl.failure_reason='unmineable_known_goal_descent';return []}
        return jevKeys.move_down;
      }
      if(p.y+p.height<=anchor[1]+.2){d=gx<-.1?'left':'right';if(Math.abs(gx)<.3)return jevKeys.move_down}
    }
    if(action==='recover'){jevControl.execution_stage=p.respawning?'respawning':'rest';return []}
    if(['fight_nearest','fight_guardian','pass_enemy_right','retreat_left'].indexOf(action)>=0){
      var combat=action==='fight_nearest'||action==='fight_guardian';
      var enemy=obs.enemies.find(function(e){return e.id===target.id});
      if(!enemy){var defeated=combat&&obs.recent_combat_events.some(function(e){return e.enemy_id===target.id&&e.credited_to_player});jevControl.event=defeated?'target_completed':'target_missing';return []}
      var eg=combat?Object.assign({},enemy,enemy.geometry||{}):enemy,ex=eg.x+eg.width/2-(p.x+p.width/2),ey=eg.y+eg.height/2-(p.y+p.height/2),gap=Math.max(0,Math.abs(ex)-(eg.width+p.width)/2);
      if(action==='pass_enemy_right'&&p.x>enemy.x+enemy.width+8){jevControl.event='target_completed';return []}
      if(action==='retreat_left'&&p.x+p.width<enemy.x-7){jevControl.event='target_completed';return []}
      d=action==='retreat_left'?'left':action==='pass_enemy_right'?'right':ex<0?'left':'right';
      if(combat){
        var aims=['left','right','up','down'],body={x:eg.x*TS,y:eg.y*TS,w:eg.width*TS,h:eg.height*TS};
        var hits=aims.filter(function(aim){return attackIntersects(attackRectangle(aim,p.x*TS,p.y*TS,p.width*TS,p.height*TS),body)});
        var preferred=Math.abs(ey)>Math.abs(ex)?(ey<0?'up':'down'):d;
        if(hits.length){jevAim=hits.indexOf(preferred)>=0?preferred:hits[0];jevControl.execution_stage='attack_in_range';return ['x']}
        var aligned=alignTargetHeight(eg);if(aligned!==null)return aligned;
        enemyDescent=ey>2.4;
        // Align with the real native sword rectangle, never the old square gap.
        // The selected target and combat strategy remain the model's choice.
        tool='move';jevAim=preferred;
        var verticalGap=Math.max(0,Math.abs(ey)-(eg.height+p.height)/2);
        if(ey<0&&verticalGap>=28/TS&&p.on_ground){
          for(var jx=Math.floor(p.x);jx<=Math.floor(p.x+p.width-.001);jx++){
            var ceiling=seen(jx,Math.floor(p.y)-1);
            if(ceiling===-1){jevControl.event='unknown_frontier';jevControl.failure_reason='selected_enemy_jump_headroom_unknown';return []}
            if(solid(ceiling)){jevControl.event='blocked_ceiling';jevControl.failure_reason='selected_enemy_jump_blocked_by_visible_ceiling';return []}
          }
          jump=true;jevControl.execution_stage='jump_toward_selected_enemy';
          if(Math.abs(ex)<.25)return jevKeys.jump_move_up;
        }
        if(!jump)jevControl.execution_stage='approach_selected_enemy';
      }else{
        jevControl.execution_stage=action==='pass_enemy_right'?'pass_selected_enemy':'retreat_from_selected_enemy';
        if(p.on_ground&&gap<3.5&&seen(tx,Math.floor(p.y)-1)===0)jump=true;
      }
    }else if(action==='return_surface'||action==='reach_known_goal'||(action==='explore_right'||action==='explore_left')&&anchor&&p.y+p.height>anchor[1]+2){
      if(action==='explore_right'||action==='explore_left'){
        // A visible surface corridor is part of the selected exploration goal.
        // If the body fell below it, regain its height before tunnelling onward.
        var forward=[],sign=action==='explore_left'?-1:1;for(var gy=m.origin[1];gy<m.origin[1]+m.tiles.length;gy++)for(var gx=m.origin[0];gx<m.origin[0]+m.tiles[0].length;gx++)if(seen(gx,gy)===2&&sign*(gx-tx)>=0&&sign*(gx-tx)<=8)forward.push([gx,gy]);
        forward.sort(function(a,b){return Math.abs(a[0]-tx)+Math.abs(a[1]-ty)-Math.abs(b[0]-tx)-Math.abs(b[1]-ty)});
        if(forward.length)anchor=forward[0];
      }
      if(!anchor){jevControl.event='blocked_unknown_surface';jevControl.failure_reason='no_observed_surface';return []}
      if(action==='return_surface'&&p.y+p.height<=anchor[1]+.2&&Math.abs(p.x-anchor[0])<=3){
        if(p.on_ground){jevControl.event='goal_reached';return []}
        jevControl.execution_stage='land_at_surface';if(P.vy>=0)place(tx,Math.max(Math.ceil((P.y+P.h)/TS-1e-7),anchor[1]));return jevKeys.move_up;
      }
      if(p.y+p.height>anchor[1]+.2){
        jevControl.execution_stage='ascend';
        // Place support immediately after a ceiling collision; otherwise the
        // digging time can consume the jump while the character falls back.
        if(!p.on_ground&&P.vy>=0)place(tx,Math.max(Math.ceil((P.y+P.h)/TS-1e-7),anchor[1]));
        var ceiling=Math.floor(p.y)-1;
        var top=p.on_ground?ceiling-2:ceiling;
        for(var cy=ceiling;cy>=top;cy--)for(var hx=Math.floor(p.x);hx<=Math.floor(p.x+p.width-.01);hx++)if(solid(seen(hx,cy))){
          if(mine(hx,cy))return [];
          if(cy===ceiling){jevControl.event='blocked_ceiling';jevControl.failure_reason='unmineable_visible_ceiling';return []}
        }
        if(gear.dirt<=0){
          jevControl.execution_stage='gather_ascent_material';if(material())return [];
          // A wide cave can put every wall outside tool reach. Move toward a
          // currently observed material tile, then recheck actual tool reach.
          var targets=[];for(var yy=m.origin[1];yy<m.origin[1]+m.tiles.length;yy++)for(var xx=m.origin[0];xx<m.origin[0]+m.tiles[0].length;xx++)if([1,2,3].indexOf(seen(xx,yy))>=0&&Math.abs(xx-tx)>0)targets.push({x:xx,y:yy,d:Math.hypot(xx-tx,yy-ty)});
          targets.sort(function(a,b){return a.d-b.d||Math.abs(a.x-anchor[0])-Math.abs(b.x-anchor[0])||a.x-b.x});
          if(targets.length){var sd=targets[0].x<tx?'left':'right',sx=sd==='left'?-1:1;if(seen(tx+sx,ty)===0||[1,2,3].indexOf(seen(tx+sx,ty))>=0){jevControl.execution_stage='approach_visible_material';return jevKeys[(p.on_ground?'jump_':'')+'move_'+sd]}}
          jevControl.event='resources_unavailable';jevControl.failure_reason='no_visible_reachable_building_material';return []
        }
        // Jump and add one non-overlapping support block only during descent.
        // Each block is charged and passes the same placement/collision rules.
        if(!p.on_ground&&P.vy>=0)place(tx,Math.max(Math.ceil((P.y+P.h)/TS-1e-7),anchor[1]));
        return p.on_ground?jevKeys.jump_move_up:jevKeys.move_up;
      }
      d=action==='explore_left'||(action==='return_surface'||action==='reach_known_goal')&&anchor[0]<tx?'left':'right';
    }
    var resourceDescent=enemyDescent;
    if((action==='collect_visible'||action==='collect_visible_gem')){
      var next=(jevControl.path||[]).find(function(c){return Math.abs(c.x-tx)+Math.abs(c.y-ty)>1})||target;
      d=next.x<tx?'left':'right';
      // Follow the visible downward resource path instead of bridging it shut.
      resourceDescent=next.y>ty;
      if(target.y>ty+1&&Math.abs(target.x-tx)<2){for(var mx=Math.floor(p.x);mx<=Math.floor(p.x+p.width-.01);mx++)if(mine(mx,Math.floor(p.y+p.height+.1))){jevControl.execution_stage='descend_to_resource';return []}}
      if(next.y<ty-1&&p.on_ground)jump=true;
    }
    var dx=d==='right'?1:d==='left'?-1:0,frontHead=seen(tx+dx,head),frontFoot=seen(tx+dx,foot),supportY=Math.ceil(p.y+p.height-1e-7),below=seen(tx+dx,supportY);
    if(dx&&(frontHead===-1||frontFoot===-1)){jevControl.event='unknown_frontier';return []}
    if(dx&&(solid(frontHead)||solid(frontFoot))){
      if(p.on_ground&&!solid(frontHead)&&seen(tx+dx,head-1)===0){jump=true;jevControl.execution_stage='step_over'}
      else {var by=solid(frontHead)?head:foot;if(mine(tx+dx,by)){jevControl.execution_stage='clear_obstacle';return []}jevControl.event='blocked_ceiling';jevControl.failure_reason='unmineable_visible_obstacle';return []}
    }
    if(action==='clear_right'){tool='mine';jevControl.execution_stage='clear_right'}
    // Bridge a visible drop before walking into it. This follows explore/over-gap
    // intent, does not turn an exploration decision into a separate strategy.
    if(dx&&p.on_ground&&(below===0||below===14||below===15)&&!(resourceDescent&&below===0)){
      jevControl.execution_stage='bridge_gap';
      if(gear.dirt<=0){if(action!=='pass_enemy_right'&&action!=='retreat_left'&&material())return [];jump=true}
      else if(below===0){place(tx+dx,supportY);if(seen(tx+dx,supportY)===0)return []}
      else jump=true;
    }
    if(action==='cross_gap_right'&&p.on_ground)jump=true;
    var id=(jump?'jump_':'')+tool+'_'+d;return jevKeys[id]||[];
  }
  function jevPublish(){if(options.onPublish)options.onPublish(jevSnapshot());}
  function jevFinish(){
    if(jevAction&&jevStart){
      var progress=jevProgressState(),meaningful=jevMeaningfulProgress(jevStart.progress,progress);
      jevControl.no_progress_count=meaningful?0:jevControl.no_progress_count+1;
      if(!jevControl.event&&jevFrames>0){jevControl.event='cancelled';jevControl.failure_reason='selected_intent_cancelled_before_completion'}
      var event=jevControl.event||'action_complete';
      if(event==='expired'){jevControl.status='expired';jevControl.failure_reason=jevControl.failure_reason||'action_deadline_exhausted'}
      else if(['danger_changed','threat_detected','death_or_respawn','cancelled'].indexOf(event)>=0){jevControl.status='interrupted';jevControl.failure_reason=jevControl.failure_reason||event}
      else if(jevControl.failure_reason||['target_missing','unknown_frontier','blocked_unknown_surface','goal_locked_guardian','resources_unavailable','blocked_ceiling','blocked'].indexOf(event)>=0){jevControl.status='blocked';jevControl.failure_reason=jevControl.failure_reason||event}
      else jevControl.status='completed';
      var target=jevControl.target;
      if(target&&['collect_visible','collect_visible_gem','fight_nearest','fight_guardian','approach_guardian'].indexOf(jevAction)>=0){
        var remembered=jevControl.failed_targets||(jevControl.failed_targets=[]),key=target.kind+':'+(target.id===undefined?'':target.id)+(target.kind==='enemy'?'':':'+target.x+','+target.y);
        var old=remembered.find(function(r){return r.key===key&&r.intent===jevAction});
        if(event==='target_completed')jevControl.failed_targets=remembered.filter(function(r){return r!==old});
        else if(jevControl.status==='blocked'||jevControl.status==='expired'){
          if(!old){old={key:key,intent:jevAction,target:{kind:target.kind,x:target.x,y:target.y},failures:0};if(target.tile!==undefined)old.target.tile=target.tile;if(target.id!==undefined)old.target.id=target.id;remembered.push(old)}
          old.failures++;old.last_reason=jevControl.failure_reason;old.last_frame=frame;old.last_meaningful_progress=meaningful;
          jevControl.failed_targets=remembered.slice(-12);
        }
      }
      jevControl.effects.push({action:jevAction,delta_x:+((P.x-jevStart.x)/TS).toFixed(1),delta_y:+((P.y-jevStart.y)/TS).toFixed(1),frames:jevElapsed,deaths:deaths-jevStart.deaths,support_blocks:jevControl.execution_counts.placed-jevStart.placed,material_gathered:jevControl.execution_counts.mined-jevStart.mined,net_terrain_changes:progress.terrain_cells,meaningful_progress:meaningful,hp_delta:+(P.hp-jevStart.hp).toFixed(2),execution_stage:jevControl.execution_stage,status:jevControl.status,failure_reason:jevControl.failure_reason,event:event});
      jevControl.effects=jevControl.effects.slice(-6);jevControl.intermediate_events=(jevControl.intermediate_events||[]).slice(-12);
    }
    if(jevAction&&jevBefore){jevEffects.push({action:jevAction,delta_x:+((P.x-jevBefore.x)/TS).toFixed(2),delta_y:+((P.y-jevBefore.y)/TS).toFixed(2),delta_hp:Math.round(P.hp-jevBefore.hp),delta_blocks:gear.dirt-jevBefore.dirt,delta_ore:stat.ore-jevBefore.ore,delta_chests:stat.chest-jevBefore.chest,delta_kills:stat.kill-jevBefore.kill,deaths:deaths-jevBefore.deaths,frames:frame-jevBefore.frame,event:jevControl.event||'action_complete',status:jevControl.status,failure_reason:jevControl.failure_reason,meaningful_progress:meaningful,net_terrain_changes:progress.terrain_cells,no_displacement:Math.hypot(P.x-jevBefore.x,P.y-jevBefore.y)<TS*.25});jevEffects=jevEffects.slice(-6);jevBefore=null}
    if(jevAction){jevPositions.push([Math.floor((P.x+P.w/2)/TS),Math.floor((P.y+P.h/2)/TS)]);jevPositions=jevPositions.slice(-8)}jevFrames=0;jevAction=null;jevLocked=false;accumulator=0;clearKeys();hud();if(jevResolve){var cb=jevResolve;jevResolve=null;cb(jevSnapshot())}
  }
  function jevRelease(){jevAwaiting=false;jevModelStepping=false;jevFinish()}
  var bridge={snapshot:jevSnapshot,prepare:function(options){var clock=options&&options.clock!==undefined?options.clock:'step';if(clock!=='step'&&clock!=='realtime')throw new RangeError('unknown simulation clock');if(jevEpisodeTerminal)return jevSnapshot();jevEpisodeManaged=true;jevFinish();jevModelStepping=clock==='step';jevAwaiting=true;jevLocked=true;agent.on=false;clearKeys();hud();jevRememberObservedGuardians(jevSnapshot());return jevSnapshot()},release:jevRelease,
    activate:function(v){jevActive=v;if(!v)jevRelease();last=now();accumulator=0},
    condition:function(){return {seed:conditionSeed,generator_version:environmentLayout.generator_revision,generator_revision:environmentLayout.generator_revision,profile:environmentLayout.profile,generation:episodeGeneration}},
    reset:function(seed,generationOptions){resetEpisode(seed,generationOptions);agent.on=false;jevHistory=[];jevPositions=[];jevCalls=0;jevSurfaceAnchor=null;jevAim='right';jevEffects=[];jevBefore=null;jevRuleFrames=0;jevRuleDecisions=0;jevAppliedFrames=0;jevEntityIds=new WeakMap();jevEntitySeq=0;jevCollectedItems=[];jevKnownGuardians={};jevVisited={};jevKnownSurfaces={};jevControl={effects:[],status:'idle',subgoal:null,event:null,no_progress_count:0};jevStart=null;jevTool=null;jevElapsed=0;jevLastDamageFrame=-99999;reveal();hud();return jevSnapshot()},
    act:function(action){if(!jevKeys[action])return Promise.reject(Error(tr("Unknown action","未知动作")));if(!jevActive)return Promise.reject(Error(tr("Open Terraria first","请先打开泰拉瑞亚")));if(jevEpisodeTerminal)return Promise.resolve(jevSnapshot());jevEpisodeManaged=true;jevAwaiting=false;jevFinish();agent.on=false;jevLocked=true;jevCalls++;jevHistory.push(action);say(jevNames[action]);keys={};jevKeys[action].forEach(function(k){keys[k]=1});jevAction=action;if(action==='return_surface'){var surface=jevReturnSurfaceAnchor(jevSnapshot());jevControl.target_surface=surface?surface.slice():null;jevControl.target_surface_owner=surface?'return_surface':null}else{jevControl.target_surface=null;jevControl.target_surface_owner=null}jevControl.execution_counts=jevControl.execution_counts||{mined:0,placed:0};jevStart={x:P.x,y:P.y,deaths:deaths,wins:wins,hp:P.hp,mined:jevControl.execution_counts.mined,placed:jevControl.execution_counts.placed,escape_hazard:jevEscapeHazardAtStart(action)};jevStart.progress=jevProgressState();jevElapsed=0;jevControl.target=null;jevControl.path=[];jevControl.intermediate_events=[];jevControl.progress_checkpoint=jevStart.progress;jevControl.deadline_frames=action==='return_surface'||action==='reach_known_goal'||action==='approach_guardian'?360:action==='recover'?300:240;jevControl.subgoal=jevControl.target_surface?{intent:action,target:jevControl.target_surface.slice()}:action;jevControl.status='executing';jevControl.event=null;jevControl.failure_reason=null;jevControl.execution_stage='start';jevBefore={x:P.x,y:P.y,hp:P.hp,dirt:gear.dirt,ore:stat.ore,chest:stat.chest,kill:stat.kill,deaths:deaths,frame:frame};jevFrames=jevNames[action]===action?jevControl.deadline_frames:36;hud();return new Promise(function(resolve){jevResolve=resolve})}
  };
  // Playback paints only recorded public observations; no world updates or input.
  bridge.renderReplay=function(s){
    if(!s||!s.player||!s.map||!s.map.tiles)return;
    jevActive=false;clearKeys();agent.on=false;
    world.fill(AIR);explored.fill(0);
    var origin=s.map.origin||[0,0];
    s.map.tiles.forEach(function(row,y){row.forEach(function(v,x){var tx=origin[0]+x,ty=origin[1]+y;if(inb(tx,ty)&&v>=0){world[idx(tx,ty)]=v;explored[idx(tx,ty)]=1;}})});
    P.x=s.player.x*TS;P.y=s.player.y*TS;P.hp=s.player.hp;P.maxhp=s.player.max_hp||100;P.face=s.player.facing||1;P.ground=!!s.player.on_ground;P.dead=s.player.respawning?1:0;P.inv=0;
    frame=s.frame||0;gear=Object.assign(gear,s.equipment||{});stat=Object.assign(stat,s.stats||{});wins=s.wins||0;deaths=s.deaths||0;
    var visual=s.replay_scene||{};
    enemies=(visual.enemies||[]).map(function(e){return Object.assign({},e)});
    if(visual.surface)surf=visual.surface.slice();
    if(visual.player)['vx','vy','w','h','inv'].forEach(function(key){if(visual.player[key]!==undefined)P[key]=visual.player[key];});
    agent.atk=visual.agent&&visual.agent.atk||0;agent.digT=visual.agent&&visual.agent.digT||null;agent.digP=visual.agent&&visual.agent.digP||0;agent.think='';
    if(!visual.surface&&s.last_known_surface)for(var i=0;i<WW;i++)surf[i]=s.last_known_surface[1];
    if(s.known_goal){goal.x=s.known_goal[0];goal.y=s.known_goal[1];}
    drops=[];items=[];parts=[];msgs=[];evt.t=0;showMap=false;
  };
  // These scheduling/UI methods never implicitly observe the world.
  bridge.tick=tick;
  bridge.advanceTo=advanceTo;
  bridge.terminal=function(){return {outcome:jevEpisodeTerminal?'win':null,wins:wins,frame:frame};};
  bridge.setKeys=function(next){keys={};Object.keys(next||{}).forEach(function(k){if(next[k])keys[k]=1;});};
  bridge.clearKeys=clearKeys;
  bridge.setManualMode=function(mode){
    if(jevLocked)return;
    clearKeys();agent.mode=mode==='manual'?'manual':'auto';agent.on=agent.mode==='auto';
    say(agent.on?"I've got this — exploring.":"Human takes the wheel!");hud();
  };
  bridge.renderState=function(){
    return structuredClone({world:world,explored:explored,exploredCount:exploredCount,
      surf:surf,spawn:spawn,goal:goal,chests:chests,clouds:clouds,P:P,gear:gear,agent:agent,
      enemies:enemies,drops:drops,items:items,parts:parts,msgs:msgs,stat:stat,buffs:buffs,
      wins:wins,deaths:deaths,frame:frame,evt:evt,
      jevActive:jevActive,jevLocked:jevLocked,jevModelStepping:jevModelStepping,
      jevAwaiting:jevAwaiting,jevFrames:jevFrames,agentPower:agentPower()});
  };
  bridge.reset(conditionSeed,options.generationOptions);
  return bridge;
  }
  return Object.freeze({create:create,revision:'terramai-shared-core-v1'});
});
