const test = require('node:test');
const assert = require('node:assert/strict');
const taxonomy = require('../web/playground/game-categories.js');
const published = require('../leaderboard/arena-elo.json');
const scope = require('../config/game-scope.json');
const activeGames=published.fixed_config.games.filter(game=>!scope.excluded_games.includes(game.id));

test('every active game has exactly one category and a matching icon',()=>{
  const ids=taxonomy.groups.flatMap(group=>group.games);
  assert.equal(ids.length,17);
  assert.equal(new Set(ids).size,17);
  assert.deepEqual([...ids].sort(),activeGames.map(game=>game.id).sort());
  assert.deepEqual(taxonomy.groups.map(group=>group.zh),['概率','策略','长程','实时']);
  for(const id of ids){assert.ok(taxonomy.category(id));assert.notEqual(taxonomy.icon(id),'🎮');}
});

test('radar preserves all game identities and places each category in its own quadrant',()=>{
  const games=activeGames;
  const before=JSON.stringify(games),layout=taxonomy.layout(games);
  assert.equal(layout.axes.length,17);
  assert.equal(layout.sectors.length,4);
  assert.equal(JSON.stringify(games),before);
  const angles=new Set();
  for(const sector of layout.sectors){
    const axes=layout.axes.filter(axis=>axis.group===sector.id);
    assert.equal(axes.length,sector.count);
    assert.ok(Math.abs(sector.end-sector.start-Math.PI/2)<1e-9);
    for(const axis of axes){
      assert.ok(axis.angle>sector.start && axis.angle<sector.end);
      assert.ok(!angles.has(axis.angle));angles.add(axis.angle);
      assert.equal(axis.game,games.find(game=>game.id===axis.game.id));
    }
  }
});

test('unknown game kinds keep the original chart instead of losing data',()=>{
  assert.equal(taxonomy.layout([{id:'future-game'}]),null);
  assert.equal(taxonomy.category('future-game'),null);
});
