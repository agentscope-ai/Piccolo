/* Shared presentation translation for public benchmarks. */
(function(){
  const tr=(en,zh,params)=>window.JevI18n?.t(en,zh,params)??en;
  function createPresentationTranslator(entries,skip='') {
    const originals=new WeakMap();
    const phrases=Object.keys(entries).sort((a,b)=>b.length-a.length);
    const pattern=new RegExp('(?<![A-Za-z0-9_])(?:'+phrases.map(text=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')(?![A-Za-z0-9_])','g');
    function translate(text) {
      const zh=text.replace(pattern,match=>entries[match])
        .replace(/View ([\d,]+) dimensions and sample counts/g,'查看 $1 个维度与样本量')
        .replace(/Inspect (?=[A-Za-z])/g,'查看 ');
      return tr(text,zh);
    }
    function update(node,key,read,write) {
      const stored=originals.get(node)||{},current=read(),old=stored[key];
      const source=old&&current===old.output?old.source:current,output=translate(source);
      if(current!==output)write(output);
      stored[key]={source,output};originals.set(node,stored);
    }
    return function localize(root) {
      if(!root)return;
      const excluded='code,pre,[data-i18n-raw],[data-i18n-en]'+(skip?','+skip:'');
      const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()) {
        const node=walker.currentNode;
        if(!node.parentElement?.closest(excluded))update(node,'text',()=>node.nodeValue,value=>{node.nodeValue=value;});
      }
      [root,...root.querySelectorAll('[title],[aria-label]')].forEach(node=>{
        if(node.matches(excluded)||node.closest('code,pre'))return;
        for(const name of ['title','aria-label'])if(node.hasAttribute(name)&&!node.hasAttribute('data-i18n-'+name+'-en'))update(node,name,()=>node.getAttribute(name),value=>node.setAttribute(name,value));
      });
    };
  }
  const uiTranslations={"All games":"全部游戏","Load more":"更多对局","Waiting":"等待中","Evaluation running":"评测进行中","Pausing":"暂停中","Paused":"已暂停","Interrupted":"已中断","Complete with failures":"已完成（含失败）","Complete with errors":"已完成（含错误）","Complete":"已完成","Evaluation error":"评测错误","Registered":"已登记","Queued":"排队中","Pending":"待评测","Running":"进行中","Error":"错误","Blocked":"已阻塞","Scoring":"计分中","Archived":"归档","Incomplete":"未完成","Submitting…":"提交中…","Evaluate current model":"评测当前模型","Loading model…":"读取模型中…","Checking eligibility…":"检查准入中…","This connection is not supported.":"当前连接暂不支持。","Connect the model first.":"请先连接模型。","This model cannot join yet.":"当前模型暂不能加入。","Pause":"暂停","Resume":"继续","Refresh":"刷新","Final game score":"游戏最终成绩","Final score":"最终成绩","Completion first":"优先比较是否通关","lower is better":"越低越好","higher is better":"越高越好","Gates reached; final horizontal position breaks ties":"已到达关卡数；平分时比较最终横向位置","Platforms reached":"已到达平台数","Lines cleared":"消除行数","Food collected":"吃到的食物数","Merge points":"合并得分","Boxes on targets":"目标上的箱子数","Level progress (%); native score breaks ties":"关卡进度（%）；平分时比较原生得分","Distance (m); remaining durability breaks ties":"行驶距离（米）；平分时比较剩余耐久度","Native payoff against the dealer":"对庄家的原生收益","board games":"棋盘游戏","Final-score comparison":"最终成绩比较","evaluation progress":"评测进度","Per-game only":"仅分游戏计分","Incomplete coverage":"覆盖未完成","Not evaluated":"未评测","Overall · game-weighted":"综合 · 游戏等权","Overall ranking":"综合排名","Axis starts at 0":"坐标轴从 0 开始","Participant":"参赛者","Failures":"失败数","Native score":"原生得分","Budget exhausted":"预算耗尽","Win":"胜","Loss":"负","Draw":"平局","Failure":"失败","Compare in order":"依次比较","Record":"记录","new record":"新记录","Error · unscored":"错误 · 未计分","Awaiting result":"等待结果","Same-seed final score":"同种子最终成绩","Updated":"更新于","Request failed":"请求失败","Could not load Arena":"天梯加载失败","Requesting pause…":"正在请求暂停…","Resuming…":"正在继续…","Action failed":"操作失败","Rule engine":"规则引擎","Local base":"本地基座","Gameplay RL":"游戏 RL","Reviewed SFT / iter":"审核数据 SFT / 迭代","Model":"模型","Othello 6×6":"黑白棋 6×6","Othello 8×8":"黑白棋 8×8","Gomoku":"五子棋","Hex":"六角棋","Dots and Boxes":"点格棋","Terraria":"泰拉瑞亚","Jump Jump":"跳一跳","Tetris":"俄罗斯方块","Snake":"贪吃蛇","Sokoban":"推箱子","Mario":"马里奥","Racing":"赛车","Dou Dizhu":"斗地主","Texas Hold’em":"德州扑克","Property Tycoon":"地产大亨","Liar’s Dice":"吹牛骰子","Blackjack":"二十一点","Golden Flower":"炸金花","Pig Dice":"小猪骰子","games":"游戏","decisions":"次决策","wins":"获胜","Seed":"种子","vs.":"对阵"};
  Object.assign(uiTranslations,{'Realtime: 1 decision; other games: 3 probes':'实时游戏单次决策；其他游戏三次判断','shorter time breaks ties':'同进度用时较短优先','Elapsed':'用时','Level progress (%)':'关卡进度（%）','Gates reached':'已到达关卡数','Distance (m)':'行驶距离（米）'});
  Object.assign(uiTranslations,{'Chess':'国际象棋','Checkers':'西洋跳棋','Xiangqi':'中国象棋','Guess the Number':'猜数字','Minesweeper':'扫雷','Sudoku':'数独'});
  window.JevArenaI18n={createPresentationTranslator,entries:uiTranslations};
})();
