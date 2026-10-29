/* Shared presentation groups. Game rules, evaluation order and scores stay native. */
(function (root) {
  'use strict';
  const groups = [
    {id:'probability',en:'Probability',zh:'概率',color:'#b18a62',games:[
      'blackjack','texas_holdem','liars_dice','zha_jin_hua','doudizhu','uno','guess_the_number','minesweeper']},
    {id:'strategy',en:'Strategy',zh:'策略',color:'#6d9084',games:[
      'othello_6x6','hex_7x7','dots_and_boxes_3x3','chess','checkers','xiangqi']},
    {id:'long_horizon',en:'Long horizon',zh:'长程',color:'#9381a2',games:[
      'merge_2048','sokoban_puzzle','property_tycoon','sudoku']},
    {id:'realtime',en:'Realtime',zh:'实时',color:'#bb7e74',games:[
      'terraria_survival','tetris_placement','snake_navigation','mario_platformer']}
  ].map(group=>Object.freeze({...group,games:Object.freeze(group.games)}));
  const icons = Object.freeze({
    blackjack:'🃏',texas_holdem:'🪙',liars_dice:'🎲',zha_jin_hua:'🌸',doudizhu:'🎴',uno:'🌈',guess_the_number:'🔢',minesweeper:'💣',
    othello_6x6:'🐼',hex_7x7:'🐝',dots_and_boxes_3x3:'🔲',chess:'🐴',checkers:'🔴',xiangqi:'🐘',
    merge_2048:'🧮',sokoban_puzzle:'📦',property_tycoon:'🏡',sudoku:'🧩',
    terraria_survival:'🌳',tetris_placement:'🧱',snake_navigation:'🐍',mario_platformer:'🍄'
  });
  const membership = new Map(groups.flatMap(group=>group.games.map(id=>[id,group.id])));
  function category(id) { return membership.get(id) || null; }
  function icon(id) { return icons[id] || '🎮'; }
  function label(group,lang) { return group[lang==='zh'?'zh':'en']; }
  function layout(games) {
    // Unknown future games retain the existing chart, never disappear from it.
    if(games.some(game=>!category(game.id)))return null;
    const available = new Map(games.map(game=>[game.id,game]));
    const axes = [], sectors = [];
    groups.forEach((group,quadrant)=>{
      const members = group.games.filter(id=>available.has(id));
      if(!members.length)return;
      const start = -Math.PI/2+quadrant*Math.PI/2,end = start+Math.PI/2;
      sectors.push({...group,start,end,count:members.length});
      members.forEach((id,index)=>axes.push({game:available.get(id),group:group.id,
        angle:start+(index+.5)*(end-start)/members.length}));
    });
    return {axes,sectors};
  }
  const api = Object.freeze({groups:Object.freeze(groups),category,icon,label,layout});
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root)root.JevGameCategories=api;
})(typeof window==='undefined'?null:window);
