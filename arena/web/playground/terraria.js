/* ============================================================================
   TERRAMAI — a Terraria-like 2D pixel sandbox that an AI agent auto-plays.
   Client-side engine + agent brain: BFS pathfinding + frontier exploration + FSM.
   ============================================================================ */
(function () {
  "use strict";
  // Share only the UI locale with the same-origin parent; game state stays local.
  const uiLocale=(()=>{try{return window.parent.JevI18n||window.JevI18n;}catch{return window.JevI18n;}})();
  const tr=(en,zh)=>uiLocale?.t(en,zh)??en;
  var replayOnly=new URLSearchParams(location.search).get("replay")==="1"||!!window.__JEV_REPLAY_FRAME__;
  var canvas = document.getElementById("tw-canvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");

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

  var core, cam={x:0,y:0},showMap=false;
  var world,explored,exploredCount,surf,spawn,goal,chests,clouds,P,gear,agent,enemies,drops,items,parts,msgs,stat,buffs,wins,deaths,frame,evt;
  var jevActive=false,jevLocked=false,jevModelStepping=false,jevAwaiting=false,jevFrames=0,power=0;
  var cosmeticRandom,lastGeneration=null;
  var FOOD={apple:{icon:'🍎'},meat:{icon:'🍖'},shroom:{icon:'🍄'},honey:{icon:'🍯'},pshard:{icon:'⚔️'},star:{icon:'⭐'}};
  function idx(x,y){return y*WW+x;}
  function inb(x,y){return x>=0&&x<WW&&y>=0&&y<WH;}
  function get(x,y){return inb(x,y)?world[idx(x,y)]:BEDROCK;}
  function agentPower(){return power;}
  function beatable(e){return !e||(e.lv||1)<=power+.6;}
  function refresh(){
    if(!core)return;
    var generation=core.condition().generation;
    if(generation!==lastGeneration){showMap=false;renderTicks=0;lastGeneration=generation;}
    var s=core.renderState();
    ({world,explored,exploredCount,surf,spawn,goal,chests,clouds,P,gear,agent,enemies,drops,items,parts,msgs,stat,buffs,wins,deaths,frame,evt,
      jevActive,jevLocked,jevModelStepping,jevAwaiting,jevFrames}=s);power=s.agentPower;
  }
  /* ---------------- pixel textures (Terraria-ish, procedurally baked) ---------------- */
  var TEX = {};
  function shade(hex, f) {
    var n = parseInt(hex.slice(1), 16), r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    r = Math.max(0, Math.min(255, r * f | 0)); g = Math.max(0, Math.min(255, g * f | 0)); b = Math.max(0, Math.min(255, b * f | 0));
    return "rgb(" + r + "," + g + "," + b + ")";
  }
  function makeTex(t) {
    var c = document.createElement("canvas"); c.width = TS; c.height = TS;
    var g = c.getContext("2d"), base = BASECOL[t] || "#888", i, px, py;
    g.fillStyle = base; g.fillRect(0, 0, TS, TS);
    for (i = 0; i < 30; i++) {                                  // grainy noise
      px = (cosmeticRandom() * TS) | 0; py = (cosmeticRandom() * TS) | 0;
      g.fillStyle = shade(base, cosmeticRandom() < 0.5 ? 0.82 : 1.15);
      g.fillRect(px, py, 1 + (cosmeticRandom() * 2 | 0), 1);
    }
    if (t === GRASS) {                                          // green turf + blades
      g.fillStyle = "#3e9e3a"; g.fillRect(0, 0, TS, 5);
      g.fillStyle = "#57c04f";
      for (i = 0; i < 6; i++) { px = (cosmeticRandom() * TS) | 0; g.fillRect(px, 0, 1, 2 + (cosmeticRandom() * 3 | 0)); }
      g.fillStyle = "#2c7a2a"; g.fillRect(0, 4, TS, 1);
    }
    if (NUG[t]) {                                               // ore nuggets
      g.fillStyle = NUG[t];
      for (i = 0; i < 5; i++) {
        px = 2 + (cosmeticRandom() * (TS - 5)) | 0; py = 2 + (cosmeticRandom() * (TS - 5)) | 0;
        g.fillRect(px, py, 2 + (cosmeticRandom() * 2 | 0), 2);
        g.fillStyle = shade(NUG[t], 1.3); g.fillRect(px, py, 1, 1); g.fillStyle = NUG[t];
      }
    }
    if (t === WOOD) { g.fillStyle = shade(base, 0.7); for (i = 2; i < TS; i += 5) g.fillRect(i, 0, 1, TS); }
    if (t === LEAF) { g.fillStyle = "#54b04a"; for (i = 0; i < 8; i++) g.fillRect((cosmeticRandom() * TS) | 0, (cosmeticRandom() * TS) | 0, 2, 2); }
    if (t === BEDROCK) { g.fillStyle = "#101114"; for (i = 0; i < 5; i++) g.fillRect((cosmeticRandom() * TS) | 0, (cosmeticRandom() * TS) | 0, 4, 2); }
    if (t === GOAL) {
      g.fillStyle = "#fff3c0"; g.fillRect(3, 3, TS - 6, TS - 6);
      g.fillStyle = "#ffea8a"; g.fillRect(5, 5, TS - 10, TS - 10);
      g.fillStyle = "#fff"; g.fillRect(4, 4, 2, 2);
    }
    if (t === CHEST) {
      g.fillStyle = "#8a5a26"; g.fillRect(1, 3, TS - 2, TS - 4);
      g.fillStyle = "#6e4419"; g.fillRect(1, 3, TS - 2, 2); g.fillRect(1, TS - 3, TS - 2, 2);
      g.fillStyle = "#ffd24a"; g.fillRect(1, 7, TS - 2, 2); g.fillRect(TS / 2 - 1, 6, 3, 5);
      g.fillStyle = "#3a2508"; g.fillRect(TS / 2, 8, 1, 2);
    }
    if (t === LAVA) {                                           // molten glow
      g.fillStyle = "#e2581f"; g.fillRect(0, 0, TS, TS);
      g.fillStyle = "#ff9c40"; for (i = 0; i < 6; i++) g.fillRect((cosmeticRandom() * TS) | 0, (cosmeticRandom() * TS) | 0, 3, 2);
      g.fillStyle = "#ffd54a"; for (i = 0; i < 3; i++) g.fillRect((cosmeticRandom() * TS) | 0, (cosmeticRandom() * TS) | 0, 2, 1);
    }
    if (t !== GOAL && t !== CHEST) {                            // beveled edges
      g.fillStyle = "rgba(255,255,255,0.14)"; g.fillRect(0, 0, TS, 1); g.fillRect(0, 0, 1, TS);
      g.fillStyle = "rgba(0,0,0,0.22)"; g.fillRect(0, TS - 1, TS, 1); g.fillRect(TS - 1, 0, 1, TS);
    }
    return c;
  }
  function buildTex() {
    for (var t = 1; t <= 14; t++) { TEX[t] = [makeTex(t), makeTex(t), makeTex(t)]; }
  }

  /* ---------------- HUD (DOM) ---------------- */
  function hud() {
    if(!core)return;refresh();
    var hb = document.getElementById("tw-hpbar"); if (hb) hb.style.width = Math.max(0, P.hp / P.maxhp * 100) + "%";
    var ge=document.getElementById("tw-gear");if(ge)ge.textContent=tr("Pick ","镐 ")+gear.pick+tr(" · Sword "," · 剑 ")+gear.sword+tr(" · Armor "," · 甲 ")+gear.armor+tr(" · Gems "," · 宝石 ")+gear.gems+tr(" · Blocks "," · 方块 ")+gear.dirt+tr(" · Wins "," · 通关 ")+wins;
    var stt = document.getElementById("tw-state"), stDisp = String(agent.state).replace("SEEK_GOAL", "SEEK");
    if (stt) stt.textContent = !agent.on ? (jevModelStepping ? (jevFrames ? tr("Model step · 36 frames","模型分步 · 36 帧") : tr("Model step · Paused","模型分步 · 已暂停")) : (jevAwaiting ? tr("Model thinking · World continues","模型思考中 · 世界继续运行") : tr("Live","实时"))) : ("BFS+Frontier+FSM · " + stDisp);
  }


  // Translate cached messages only while painting: no changes to game/model data.
  const visibleLabels={"Waking up…": "准备出发…", "Ouch. Respawning…": "哎呀，正在复活…", "Legendary loot!": "传奇战利品！", "Treasure chest! Lucky me.": "找到宝箱了！", "Power-up!": "获得强化！", "Yum!": "好吃！", "Frontier ahead — let's map it.": "前方是未知区域，去探索。", "Unknown tiles that way →": "那边尚未探索 →", "Exploring the dark…": "探索黑暗…", "New ground to chart.": "探索新区域。", "Path to the Grand Gem locked in.": "已找到通往宝石的路径。", "Following the route to treasure.": "沿着路线寻找宝藏。", "Almost at the prize…": "快找到宝藏了…", "Hostile! Engaging.": "发现敌人，准备战斗！", "En garde, creature!": "来战吧，怪物！", "Combat mode.": "进入战斗。", "Too risky — retreating.": "太危险，先撤退。", "Fall back and heal!": "后退并恢复！", "Nope, running.": "先跑为敬。", "Tunnelling downward…": "向下挖掘…", "Digging for ore.": "挖掘矿石。", "Heading back up for air.": "返回地面透口气。", "To the surface!": "返回地面！", "A chest! Gimme that loot.": "发现宝箱，拿上战利品。", "Treasure nearby — on my way.": "附近有宝藏，出发。", "Free loot, don't mind if I do.": "免费的宝藏，我就收下了。", "Mining ore to upgrade.": "采矿升级装备。", "Need better gear — digging.": "需要更好的装备，继续挖。", "More ore, more power.": "矿石越多，力量越强。", "Gem hunting — armor time.": "寻找宝石升级护甲。", "Sparkly things, come to me.": "闪亮的宝石，到我这来。", "Hunting something my size.": "寻找合适的对手。", "Monster farming time.": "开始打怪。", "Low HP — need a snack.": "血量较低，找点食物。", "Retreat, recover, return.": "撤退、恢复、再回来。", "Building my way up!": "搭路向上！", "Stacking dirt — going up.": "堆起方块，向上走。", "Grand Gem secured! 🎉": "获得大宝石！🎉", "Loot acquired!": "战利品到手！", "Been here too long — moving on!": "这里待够了，继续前进！", "Enough! Digging my way out of here.": "挖条路离开这里！", "Hot hot hot!": "好烫好烫！", "A fresh world to conquer!": "新的世界等着探索！", "I've got this — exploring.": "交给我，开始探索。", "Human takes the wheel!": "由你接管！", "Ready to explore.": "准备开始探索。", "Explore with the keyboard or model. M opens the map.": "键盘或模型探索 · M 打开地图。", "🧪 Potion of Strength! +2 attack (permanent)": "🧪 力量药水！永久攻击 +2", "🧪 Potion of Vitality! +15 max ❤️": "🧪 活力药水！生命上限 +15 ❤️", "🧪 Potion of Iron Skin! +1 armor (permanent)": "🧪 铁皮药水！永久护甲 +1", "🧰 Chest: ⚔️ DOUBLE DAMAGE (20s)!": "🧰 宝箱：⚔️ 双倍伤害（20 秒）！", "🧰 Chest: ⭐ SHIELD (15s)!": "🧰 宝箱：⭐ 护盾（15 秒）！", "🧰 Chest: heart! +40 ❤️": "🧰 宝箱：生命 +40 ❤️", "👑 BOSS DOWN! +5 💎": "👑 首领已击败！+5 💎", "🎒 Recovered your equipment!": "🎒 找回了装备！", "⛏️ Deadlock detected — breakout expedition!": "⛏️ 遭遇死路，尝试突围！", "🧱 Out of dirt blocks!": "🧱 没有泥土方块了！", "☄️ Meteor strike! Rare ore exposed.": "☄️ 陨石坠落！发现稀有矿石。", "👹 Monster wave incoming!": "👹 怪物潮来袭！", "🎁 Supply chest dropped nearby!": "🎁 附近掉落补给宝箱！", "🌍 New world (procedurally generated, solvable ✔)": "🌍 新世界 · 随机生成 ✔", "METEOR STRIKE — rare ore!": "陨石坠落 · 稀有矿石！", "MONSTER WAVE!": "怪物潮来袭！", "SUPPLY DROP — free chest!": "补给空投 · 免费宝箱！", "Wait": "等待"};
  const visibleFragments={"That boss is beyond me — develop more first (bar +": "首领太强，先提升装备（门槛 +", ").": "）。", "Died (": "死亡（", ") — gear is safe, respawning…": "）· 装备保留，正在复活…", "Amethyst! (": "紫水晶！（", "Armor Lv.": "护甲等级 ", "Pickaxe": "镐", "Sword": "剑", "Armor": "护甲", "Blade": "剑", "Plate": "护甲", "Copper": "铜矿", "Iron": "铁矿", "Gold": "金矿", "Diamond": "钻石", " of Power ×": "强化 ×", " equipped!": " 已装备！", "A weaker ": "更弱的 ", " — kept mine.": " · 保留现有装备。", "Chest: shiny pickaxe! ⛏️Lv.": "宝箱：新镐！⛏️ 等级 ", "Chest: sharp sword! 🗡️Lv.": "宝箱：利剑！🗡️ 等级 ", "Chest: armor plate! 🛡️Lv.": "宝箱：护甲！🛡️ 等级 ", "Chest: 3 gems! 💎": "宝箱：3 颗宝石！💎", " dropped a gem! (": "掉落宝石！（", " down! +": "已击败！+", " pts": " 点", " buff (12s)!": "强化（12 秒）！", "VICTORY GATE cleared! World ": "已穿越胜利之门！世界 ", " done — fresh start incoming.": " 完成，即将进入新世界。", "Jump + ": "跳跃并", "Move / aim": "移动 / 瞄准", "Mine": "挖矿", "Attack": "攻击", "Place": "放置", "left": "左", "right": "右", "up": "上", "down": "下", "sword": "剑", "pick": "镐", "armor": "甲", "slime": "史莱姆", "bat": "蝙蝠", "worm": "蠕虫", "zombie": "僵尸", "Power": "力量", "Strength": "力量", "Speed": "速度", "Shield": "护盾", "Regen": "恢复", " Lv.": " 等级 ", " Lv": " 等级 "};
  function visibleText(value){
    const raw=String(value);
    if(uiLocale?.lang!=='zh')return raw;
    if(visibleLabels[raw])return visibleLabels[raw];
    let text=raw;
    for(const [en,zh] of Object.entries(visibleFragments))text=text.split(en).join(zh);
    return text;
  }

  /* ---------------- render ---------------- */
  function wallColor(x, y) { var d = y - (surf[x] || 0); if (d < 0) return null; if (d < 6) return "#9b846f"; if (d < 26) return "#7e8584"; return "#697b83"; }
  function drawSky(W, H) {
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#5aa6e0"); g.addColorStop(0.55, "#8fc9ef"); g.addColorStop(1, "#d7ecfa");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "rgba(255,255,255,0.85)";                       // clouds
    for (var i = 0; i < clouds.length; i++) {
      var c = clouds[i]; c.x = (c.x + renderTicks*c.v + c.w) % (WW*TS+c.w) - c.w;
      var sxp = c.x - cam.x * 0.3, syp = c.y - cam.y * 0.1;
      ctx.fillRect(sxp, syp, c.w, 12); ctx.fillRect(sxp + 12, syp - 8, c.w - 30, 12); ctx.fillRect(sxp + 24, syp - 14, c.w - 60, 12);
    }
    ctx.fillStyle = "rgba(70,120,80,0.35)";                         // far hill parallax
    ctx.beginPath(); ctx.moveTo(0, H);
    for (var x = 0; x <= WW; x += 4) { var hx = x * TS - cam.x * 0.5, hy = ((surf[Math.min(WW - 1, x)] || 40) + 6) * TS - cam.y * 0.5; ctx.lineTo(hx, hy); }
    ctx.lineTo(WW * TS, H); ctx.closePath(); ctx.fill();
  }
  function drawChar(px, py, face) {
    ctx.fillStyle = "#3a2f28"; ctx.fillRect(px + 1, py + 14, 3, 6); ctx.fillRect(px + 6, py + 14, 3, 6);  // legs
    ctx.fillStyle = "#2f6feb"; ctx.fillRect(px + 1, py + 7, 8, 8);                                        // torso
    ctx.fillStyle = "#1c4fb0"; ctx.fillRect(px + 1, py + 7, 8, 2);
    ctx.fillStyle = "#f3c89b"; ctx.fillRect(px + 1, py + 1, 8, 6);                                        // head
    ctx.fillStyle = "#5a3b22"; ctx.fillRect(px + 1, py, 8, 3);                                            // hair
    ctx.fillStyle = "#20242a"; ctx.fillRect(px + (face > 0 ? 6 : 2), py + 3, 2, 2);                       // eye
    var mining = !!agent.digT && !P.dead;
    if (agent.atk > 16) {
      ctx.strokeStyle = "#e9edf2"; ctx.lineWidth = 2; ctx.beginPath();
      ctx.arc(px + (face > 0 ? 9 : 1), py + 9, 10, face > 0 ? -1.1 : 2.0, face > 0 ? 1.1 : 4.2); ctx.stroke();
    } else {
      var hy = py + 9 + (mining ? Math.sin(frame * 0.5) * 3 : 0);                                          // pickaxe
      ctx.strokeStyle = "#8a5a2b"; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(px + (face > 0 ? 8 : 2), py + 10); ctx.lineTo(px + (face > 0 ? 13 : -3), hy); ctx.stroke();
      ctx.strokeStyle = "#c9ced6"; ctx.beginPath();
      ctx.moveTo(px + (face > 0 ? 11 : -1), hy - 3); ctx.lineTo(px + (face > 0 ? 15 : -5), hy + 2); ctx.stroke();
    }
  }
  function drawEnemy(s) {
    var ex = s.x - cam.x, ey = s.y - cam.y;
    if (s.kind === "slime") {
      var sq = s.ground ? 0 : 2;
      ctx.fillStyle = "#3fae3a"; ctx.fillRect(ex, ey + 3 - sq, s.w, s.h - 3 + sq);
      ctx.fillStyle = "#63c74d"; ctx.fillRect(ex + 1, ey + 2 - sq, s.w - 2, 4);
      ctx.fillStyle = "#fff"; ctx.fillRect(ex + 3, ey + 5 - sq, 3, 3); ctx.fillRect(ex + s.w - 6, ey + 5 - sq, 3, 3);
      ctx.fillStyle = "#123c0e"; ctx.fillRect(ex + 4 + (s.face > 0 ? 1 : 0), ey + 6 - sq, 1.6, 1.6); ctx.fillRect(ex + s.w - 5 + (s.face > 0 ? 1 : 0), ey + 6 - sq, 1.6, 1.6);
    } else if (s.kind === "zombie") {
      ctx.fillStyle = "#3d5a2e"; ctx.fillRect(ex + 1, ey + s.h - 6, 4, 6); ctx.fillRect(ex + s.w - 5, ey + s.h - 6, 4, 6);
      ctx.fillStyle = "#5f7a45"; ctx.fillRect(ex + 1, ey + 6, s.w - 2, s.h - 11);                          // torso
      ctx.fillStyle = "#7d9e5a"; ctx.fillRect(ex + 2, ey, s.w - 4, 7);                                      // head
      ctx.fillStyle = "#233"; ctx.fillRect(ex + 3, ey + 2, 2, 2); ctx.fillRect(ex + s.w - 5, ey + 2, 2, 2);
      ctx.fillStyle = "#5f7a45"; var sw = Math.sin(frame * 0.15) * 2; ctx.fillRect(ex + (s.face > 0 ? s.w - 2 : -2), ey + 7 + sw, 4, 3);   // outstretched arm
    } else {
      var flap = Math.sin(frame * 0.4) * 4;
      ctx.fillStyle = "#5a3f80"; ctx.fillRect(ex + (s.face > 0 ? -3 : s.w - 1), ey + 1, 4, 3 + flap); ctx.fillRect(ex + (s.face > 0 ? s.w - 1 : -3), ey + 1, 4, 3 + flap);
      ctx.fillStyle = "#7a5da8"; ctx.fillRect(ex + 3, ey + 1, s.w - 6, 6);
      ctx.fillStyle = "#ff5a5a"; ctx.fillRect(ex + 4, ey + 2, 1.6, 1.6); ctx.fillRect(ex + s.w - 5, ey + 2, 1.6, 1.6);
    }
    var beat = beatable(s), lv = s.lv || 1;
    if (s.maxhp && s.hp < s.maxhp) { ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(ex, ey - 3, s.w, 2); ctx.fillStyle = beat ? "#63c74d" : "#e05555"; ctx.fillRect(ex, ey - 3, s.w * Math.max(0, s.hp / s.maxhp), 2); }
    ctx.font = "bold 8px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.textAlign = "center";
    ctx.fillStyle = beat ? "#8fe388" : (lv - agentPower() > 1.6 ? "#ff6a6a" : "#ffcf5a");
    ctx.fillText("Lv" + lv, ex + s.w / 2, ey - 5); ctx.textAlign = "left";
    if (s.boss) { ctx.font = "11px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.textAlign = "center"; ctx.fillText("👑", ex + s.w / 2, ey - 14); ctx.textAlign = "left"; }
  }
  function drawMapOverlay(W, H) {
    ctx.fillStyle = "rgba(245,249,231,0.97)"; ctx.fillRect(0, 0, W, H);
    var sc = Math.min((W - 40) / WW, (H - 70) / WH), mw = WW * sc, mh = WH * sc, ox = (W - mw) / 2, oy = 44;
    ctx.fillStyle = "#d7e4dc"; ctx.fillRect(ox - 3, oy - 3, mw + 6, mh + 6);
    for (var y = 0; y < WH; y++) for (var x = 0; x < WW; x++) {
      if (!explored[idx(x, y)]) continue;
      ctx.fillStyle = MAPCOL[world[idx(x, y)]] || "#333"; ctx.fillRect(ox + x * sc, oy + y * sc, Math.ceil(sc), Math.ceil(sc));
    }
    var i;
    for (i = 0; i < chests.length; i++) if (explored[idx(chests[i].x, chests[i].y)]) { ctx.fillStyle = "#ffae42"; ctx.fillRect(ox + chests[i].x * sc - 1, oy + chests[i].y * sc - 1, 4, 4); }
    if (explored[idx(goal.x, goal.y)] && get(goal.x, goal.y) === GOAL) { ctx.fillStyle = "#ffd54a"; ctx.fillRect(ox + goal.x * sc - 2, oy + goal.y * sc - 2, 5, 5); }
    ctx.fillStyle = "#4da3ff"; ctx.fillRect(ox + (P.x / TS) * sc - 2, oy + (P.y / TS) * sc - 2, 5, 5);
    ctx.fillStyle = "#274d43"; ctx.font = "bold 16px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.textAlign = "center";
    ctx.fillText(tr("WORLD MAP  ·  explored ","世界地图 · 已探索 ") + Math.round(100 * exploredCount / (WW * WH)) + tr("%  ·  press M to close","% · 按 M 关闭"), W / 2, 26);
    ctx.font = "12px 'Jev Comic', 'Noto Sans CJK SC', sans-serif";
    ctx.fillText(tr("🔵 you   🟡 Victory Gate   🟠 chest   (unexplored = hidden)","🔵 玩家   🟡 胜利之门   🟠 宝箱   （未探索区域隐藏）"), W / 2, oy + mh + 18);
    ctx.textAlign = "left";
  }
  function render() {
    if(!core)return;refresh();
    var W = canvas.width, H = canvas.height;
    cam.x = Math.max(0, Math.min(WW * TS - W, P.x + P.w / 2 - W / 2));
    cam.y = Math.max(0, Math.min(WH * TS - H, P.y + P.h / 2 - H / 2));
    renderTicks++;drawSky(W, H);
    var x0 = (cam.x / TS) | 0, y0 = (cam.y / TS) | 0, x1 = (((cam.x + W) / TS) | 0) + 1, y1 = (((cam.y + H) / TS) | 0) + 1, tx, ty;
    for (ty = y0; ty <= y1; ty++) for (tx = x0; tx <= x1; tx++) {
      if (!inb(tx, ty)) continue;
      var px = tx * TS - cam.x, py = ty * TS - cam.y, t = world[idx(tx, ty)];
      if (!explored[idx(tx, ty)]) {
        ctx.fillStyle = "#dce7dd"; ctx.fillRect(px, py, TS, TS);
        ctx.fillStyle = "#c4d6ca"; ctx.fillRect(px + 4, py + 4, 4, 4); ctx.fillRect(px + TS - 8, py + TS - 8, 4, 4);
        continue;
      }
      if (t === AIR) { var wc = wallColor(tx, ty); if (wc) { ctx.fillStyle = wc; ctx.fillRect(px, py, TS, TS); } }
      else if (t === MIASMA) {                                  // drifting poison haze
        var wc2 = wallColor(tx, ty); if (wc2) { ctx.fillStyle = wc2; ctx.fillRect(px, py, TS, TS); }
        ctx.fillStyle = "rgba(122,180,60," + (0.20 + 0.10 * Math.sin(frame * 0.05 + tx * 0.7 + ty)).toFixed(2) + ")";
        ctx.fillRect(px, py, TS, TS);
      }
      else if (t === GOAL) {
        var pu = 0.5 + 0.5 * Math.sin(frame * 0.12);
        ctx.fillStyle = "rgba(255,213,74," + (0.15 + 0.25 * pu).toFixed(2) + ")"; ctx.fillRect(px - 6, py - 6, TS + 12, TS + 12);
        ctx.fillStyle = "#ffd54a"; ctx.fillRect(px, py, TS, TS); if (TEX[GOAL]) ctx.drawImage(TEX[GOAL][0], px, py);
      } else if (TEX[t]) {
        ctx.drawImage(TEX[t][(tx * 7 + ty * 3) % 3], px, py);
        if (t === LAVA) { ctx.fillStyle = "rgba(255,170,60," + (0.10 + 0.10 * Math.sin(frame * 0.15 + tx)).toFixed(2) + ")"; ctx.fillRect(px, py - 1, TS, TS + 1); }
        else { var sh = Math.min(0.4, Math.max(0, (ty - (surf[tx] || 0)) * 0.010)); if (sh > 0) { ctx.fillStyle = "rgba(0,0,0," + sh.toFixed(2) + ")"; ctx.fillRect(px, py, TS, TS); } }
      } else { ctx.fillStyle = BASECOL[t] || "#666"; ctx.fillRect(px, py, TS, TS); }
    }
    var i;
    for (i = 0; i < drops.length; i++) { var d = drops[i]; ctx.fillStyle = "#8a5a26"; ctx.fillRect(d.x - cam.x, d.y - cam.y, 10, 9); ctx.fillStyle = "#ffd24a"; ctx.fillRect(d.x - cam.x, d.y - cam.y + 3, 10, 2); }
    ctx.font = "11px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.textAlign = "left";
    for (i = 0; i < items.length; i++) { var itq = items[i]; ctx.fillText(FOOD[itq.kind].icon, itq.x - cam.x - 5, itq.y - cam.y + 4 + Math.sin(frame * 0.1 + i) * 1.5); }
    for (i = 0; i < enemies.length; i++) drawEnemy(enemies[i]);
    if (!P.dead && (P.inv <= 0 || (frame % 6) < 3)) {
      if (gear.armor > 0) { ctx.fillStyle = "rgba(200,220,255,0.85)"; ctx.fillRect(P.x - cam.x, P.y - cam.y + 6, P.w, 3); }
      drawChar(P.x - cam.x, P.y - cam.y, P.face);
    }
    for (i = 0; i < parts.length; i++) { ctx.fillStyle = parts[i].c; ctx.fillRect(parts[i].x - cam.x, parts[i].y - cam.y, 2.5, 2.5); }
    if (!P.dead && agent.think) {                                    // thought bubble
      var label = visibleText(agent.think);
      ctx.font = "11px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; var tw = ctx.measureText(label).width + 12;
      var bx = Math.max(4, Math.min(W - tw - 4, P.x - cam.x + P.w / 2 - tw / 2)), by = Math.max(26, P.y - cam.y - 30);
      ctx.fillStyle = "rgba(255,255,255,0.94)"; ctx.fillRect(bx, by, tw, 18);
      ctx.fillStyle = "#20242a"; ctx.fillText(label, bx + 6, by + 13);
    }
    if (evt.t > 0 && evt.label) {                                    // world-event banner
      var eb = "⚡ " + visibleText(evt.label), ea = Math.min(1, evt.t / 120);
      ctx.font = "bold 13px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; var ew = ctx.measureText(eb).width + 20;
      ctx.globalAlpha = ea; ctx.fillStyle = "rgba(205,92,26,0.93)"; ctx.fillRect(W / 2 - ew / 2, 30, ew, 22);
      ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.fillText(eb, W / 2, 46); ctx.textAlign = "left"; ctx.globalAlpha = 1;
    }
    ctx.font = "12px 'Jev Comic', 'Noto Sans CJK SC', sans-serif";                    // toast messages
    for (i = 0; i < msgs.length; i++) {
      ctx.fillStyle = "rgba(0,0,0," + Math.min(0.55, msgs[i].life / 120).toFixed(2) + ")"; ctx.fillRect(8, H - 22 - i * 20, ctx.measureText(visibleText(msgs[i].t)).width + 12, 17);
      ctx.fillStyle = "rgba(255,255,255," + Math.min(1, msgs[i].life / 60).toFixed(2) + ")"; ctx.fillText(visibleText(msgs[i].t), 14, H - 10 - i * 20);
    }
    var ms = 0.42, mw = WW * ms, mh = WH * ms, mx = W - mw - 8, my = 8;   // corner minimap
    ctx.fillStyle = "rgba(225,238,222,0.9)"; ctx.fillRect(mx - 2, my - 2, mw + 4, mh + 4);
    for (var yy = 0; yy < WH; yy += 2) for (var xx = 0; xx < WW; xx += 2) { if (!explored[idx(xx, yy)]) continue; ctx.fillStyle = MAPCOL[world[idx(xx, yy)]] || "#555"; ctx.fillRect(mx + xx * ms, my + yy * ms, 1.2, 1.2); }
    if (explored[idx(goal.x, goal.y)] && get(goal.x, goal.y) === GOAL) { ctx.fillStyle = "#ffd54a"; ctx.fillRect(mx + goal.x * ms - 1, my + goal.y * ms - 1, 3, 3); }
    ctx.fillStyle = "#4da3ff"; ctx.fillRect(mx + (P.x / TS) * ms - 1, my + (P.y / TS) * ms - 1, 3, 3);
    ctx.fillStyle = "#416b55"; ctx.font = "9px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.fillText(tr("M = map","M = 地图"), mx, my + mh + 9);
    if (showMap) drawMapOverlay(W, H);
    if (P.dead) { ctx.fillStyle = "rgba(0,0,0,0.45)"; ctx.fillRect(0, 0, W, H); ctx.fillStyle = "#fff"; ctx.font = "bold 20px 'Jev Comic', 'Noto Sans CJK SC', sans-serif"; ctx.textAlign = "center"; ctx.fillText(tr("💀 Respawning… (gear is safe)","💀 正在复活…（装备保留）"), W / 2, H / 2); ctx.textAlign = "left"; }
  }

  var renderTicks=0;
  function loop(ts){
    if(replayOnly)return;
    requestAnimationFrame(loop);
    try{core.tick(ts);render();}catch(error){window.jevRenderError=String(error);}
  }
  function jevRelease(){core.release();refresh();}
  function clearHumanKeys(){
    keyboardKeys={};pointerKeys={};
    if(wrap)wrap.querySelectorAll('[data-tw-key]').forEach(button=>button.classList.remove('is-pressed'));
  }
  core=window.JevTerramaiCore.create({seedSource:window.JevWorldSeed,now:()=>performance.now(),
    visibility:()=>document.hidden,translate:tr,onHud:()=>{if(core)hud();},
    onClearKeys:clearHumanKeys,
    onPublish:!replayOnly&&window.parent!==window?(observation)=>window.parent.postMessage(
      {type:'jev-terraria-state',observation},window.location.origin):undefined});
  refresh();
  /* ---------------- input & boot ---------------- */
  var wrap = document.getElementById("tw-wrap"), bMode = document.getElementById("tw-mode"),
      bNew = document.getElementById("tw-new"), bMap = document.getElementById("tw-map"),
      touchControls = document.getElementById("tw-touch");
  var keyboardKeys = {}, pointerKeys = {};
  var CONTROL_KEYS = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " ", "a", "d", "w", "s", "x", "j", "k", "z", "c", "b"];
  function normalizeKey(k) { return k && k.length === 1 ? k.toLowerCase() : k; }
  function editable(el) { return !!(el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))); }
  function focusedGame() { return !!(wrap && wrap.contains(document.activeElement) && !editable(document.activeElement)); }
  function syncKeys() {
    var keys = {};
    Object.keys(keyboardKeys).forEach(function (k) { if (keyboardKeys[k]) keys[k] = 1; });
    Object.keys(pointerKeys).forEach(function (id) { keys[pointerKeys[id].key] = 1; });
    core.setKeys(keys);
  }
  function clearKeys(){clearHumanKeys();core.clearKeys();}
  function focusGame() { canvas.focus({ preventScroll: true }); }
  function updateMapButton() { if (bMap) bMap.setAttribute("aria-pressed", String(showMap)); }
  function toggleMap() { showMap = !showMap; updateMapButton(); }
  canvas.addEventListener("pointerdown", focusGame);
  document.addEventListener("keydown", function (e) {
    refresh();if (!focusedGame() || editable(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    var k = normalizeKey(e.key);
    if (k === "m") { if (!e.repeat) toggleMap(); e.preventDefault(); return; }
    if (jevLocked || agent.on || CONTROL_KEYS.indexOf(k) < 0) return;
    // Keep Space/Enter activation available on toolbar buttons.
    if (k === " " && e.target && e.target.tagName === "BUTTON" && !e.target.hasAttribute("data-tw-key")) return;
    if (jevModelStepping) jevRelease();
    keyboardKeys[k] = 1; syncKeys(); e.preventDefault();
  });
  document.addEventListener("keyup", function (e) {
    var k = normalizeKey(e.key);
    if (keyboardKeys[k]) { delete keyboardKeys[k]; syncKeys(); }
  });
  window.addEventListener("blur", clearKeys);
  document.addEventListener("visibilitychange", function () { if (document.hidden) clearKeys(); });
  if (wrap) wrap.addEventListener("focusout", function (e) { if (!e.relatedTarget || !wrap.contains(e.relatedTarget)) clearKeys(); });
  function applyMode(m) {
    clearKeys();core.setManualMode(m);refresh();
    if (bMode) { bMode.textContent = agent.on ? tr("🤖 Mode: AUTO","🤖 自动模式") : tr("🕹️ Mode: MANUAL","🕹️ 手动模式"); bMode.className = ""; }
    if (touchControls) touchControls.hidden = agent.on;
    hud();
  }
  if (bMode) bMode.addEventListener("click", function () { if(jevLocked)return;applyMode(agent.on ? "manual" : "auto"); focusGame(); });
  if (bNew) bNew.addEventListener("click", function () { window.JevTerramai.reset(); updateMapButton(); focusGame(); });
  if (bMap) bMap.addEventListener("click", function () { toggleMap(); focusGame(); });
  if (wrap) wrap.querySelectorAll("[data-tw-key]").forEach(function (button) {
    var k = button.getAttribute("data-tw-key");
    if (CONTROL_KEYS.indexOf(k) < 0) return;
    button.addEventListener("pointerdown", function (e) {
      refresh();if (!jevActive || jevLocked || agent.on || (e.button !== undefined && e.button !== 0)) return;
      e.preventDefault(); if (jevModelStepping) jevRelease(); focusGame();
      pointerKeys[e.pointerId] = { key: k, button: button }; syncKeys(); button.classList.add("is-pressed");
      if (button.setPointerCapture) button.setPointerCapture(e.pointerId);
    });
    function release(e) {
      delete pointerKeys[e.pointerId]; syncKeys();
      var held = Object.keys(pointerKeys).some(function (id) { return pointerKeys[id].button === button; });
      if (!held) button.classList.remove("is-pressed");
    }
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("lostpointercapture", release);
    // Keyboard and assistive-tech clicks get a brief, usable control press.
    button.addEventListener("click", function (e) {
      refresh();if (!jevActive || jevLocked || agent.on || e.detail !== 0) return;
      if (jevModelStepping) jevRelease(); focusGame(); var id = "click:" + k;
      pointerKeys[id] = { key: k, button: button }; syncKeys();
      window.setTimeout(function () { delete pointerKeys[id]; syncKeys(); }, 180);
    });
  });
  updateMapButton();
  function fit(){if(replayOnly)return;var w=Math.min(900,(canvas.parentElement&&canvas.parentElement.clientWidth)||880);canvas.width=Math.max(480,w);canvas.height=480;ctx.imageSmoothingEnabled=false;}
  window.addEventListener('resize',fit);
  cosmeticRandom=window.JevWorldSeed.stream(core.condition().seed,'terraria/cosmetic/v1');
  buildTex();fit();hud();
  window.JevTerramai=Object.assign({},core,{map:function(){toggleMap();render();},
    reset:function(seed){var state=core.reset(seed);showMap=false;renderTicks=0;updateMapButton();return state;}});
  if(replayOnly)window.JevTerramai.renderReplay=function(s){core.renderReplay(s);showMap=false;render();};
  function repaintLocale(){
    document.documentElement.lang=uiLocale?.lang==='zh'?'zh-CN':'en';
    document.title=tr('Terramai · Explore','Terramai · 探索');
    const labels=[['#tw-map',tr('Map M','地图 M')],['#tw-touch [data-tw-key=" "]',tr('Jump','跳跃')],['#tw-touch [data-tw-key="x"]',tr('Attack','攻击')],['#tw-touch [data-tw-key="k"]',tr('Mine','挖矿')],['#tw-touch [data-tw-key="c"]',tr('Place','放置')],['.tw-status > span:nth-child(2)',tr('Arrows move · Space jumps · X attacks · K + direction mines','方向键移动 · 空格跳跃 · X 攻击 · K + 方向挖矿')]];
    for(const [selector,label] of labels){const node=document.querySelector(selector);if(node)node.textContent=label;}
    canvas.setAttribute('aria-label',tr('Terramai pixel world','Terramai 像素世界'));
    hud();render();
  }
  repaintLocale();
  const stopLocale=uiLocale?.onChange(repaintLocale);
  window.addEventListener('pagehide',()=>{if(typeof stopLocale==='function')stopLocale();},{once:true});
  requestAnimationFrame(loop);
})();
