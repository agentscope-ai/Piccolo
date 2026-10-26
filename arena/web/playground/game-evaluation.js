(function () {
  const start = document.getElementById('gameEvaluationStart');
  const status = document.getElementById('gameEvaluationStatus');
  const body = document.getElementById('gameEvaluationRows');
  if (!start || !status || !body) return;

  const opponentName = {
    'qwen3.8-max': 'Qwen3.8-Max',
    rule_engine: '规则引擎',
    environment: '游戏环境'
  };
  const gameNames = {
    terraria_survival: '泰拉瑞亚', jump_jump: '跳一跳',
    tetris_placement: '俄罗斯方块', snake_navigation: '贪吃蛇',
    merge_2048: '2048', sokoban_puzzle: '推箱子',
    mario_platformer: '马里奥', doudizhu: '斗地主',
    texas_holdem: '德州扑克', property_tycoon: '大富翁',
    liars_dice: '诈唬骰子', goofspiel: 'Goofspiel',
    blackjack: '21 点', zha_jin_hua: '炸金花', pig_dice: '掷骰猪'
  };
  let polling = false;
  function render(data) {
    const running = data.state === 'running';
    start.disabled = running || !!data.other_model_running;
    start.textContent = running ? '评测运行中…' : '开始 8 局评测';
    if (data.state === 'idle') {
      status.textContent = '当前模型尚未开始 · ' + data.by_kind.length + ' 个玩法，每个 8 局' + (data.archived_model?' · 历史 '+data.archived_model+' 成绩单独保留':'');
    } else {
      const label = { running: '运行中', complete: '已完成', interrupted: '已中断，可继续', error: '发生错误' }[data.state] || data.state;
      status.textContent = label + ' · 当前模型 ' + data.model + ' · ' + data.completed + ' / ' + data.planned
        + ' 局 · 胜 ' + data.wins + ' 局' + (data.error ? ' · ' + data.error : '');
    }
    body.innerHTML = data.by_kind.map(row => {
      const modes = Object.entries(row.opponents).map(([key, part]) => {
        const planned = Object.keys(row.opponents).length === 2 ? 4 : 8;
        return (opponentName[key] || key) + ' · ' + part.wins + '胜 / ' +
          part.completed + '已评 / ' + planned + '计划';
      }).join(' + ');
      const result = row.completed ? '胜 ' + row.wins + ' / 负 ' + row.losses + ' / 和 ' + row.draws
        + (row.errors ? ' / 错误 ' + row.errors : '') : '等待';
      const title = gameNames[row.kind] || names[row.kind] || row.kind;
      return '<tr><td>' + esc(title) + '</td><td>' + esc(modes) + '</td><td>' +
        row.completed + ' / 8</td><td><strong>' + row.wins + ' / 8</strong></td><td>' + result + '</td></tr>';
    }).join('');
  }
  async function refresh() {
    if (polling) return;
    polling = true;
    try {
      render(await api('game-evaluation'));
    } catch (error) {
      status.textContent = '评测状态读取失败：' + error.message;
    } finally {
      polling = false;
    }
  }
  start.onclick = async function () {
    start.disabled = true;
    status.textContent = '正在启动并检查对手模型连接…';
    try {
      await api('game-evaluation/start', {});
      await refresh();
    } catch (error) {
      status.textContent = '启动失败：' + error.message;
      start.disabled = false;
    }
  };
  refresh();
  setInterval(refresh, 5000);
})();
