/* Display-only bilingual labels. Native state, action IDs, inputs and replies stay unchanged. */
window.JevPlayText=(()=>{
 const names={tic_tac_toe:'Tic-tac-toe',connect_four:'Connect Four',othello_6x6:'Othello 6×6',othello_8x8:'Othello 8×8',gomoku_19x19:'Gomoku',hex_7x7:'Hex',dots_and_boxes_3x3:'Dots & Boxes',terraria_survival:'Terraria',mario_platformer:'Mario',jump_jump:'Jump Jump',tetris_placement:'Tetris',snake_navigation:'Snake',merge_2048:'2048',sokoban_puzzle:'Sokoban',doudizhu:'Dou Dizhu',texas_holdem:'Texas Holdem',property_tycoon:'Property Tycoon',liars_dice:"Liar’s Dice",goofspiel:'Goofspiel',blackjack:'Blackjack',zha_jin_hua:'Zha Jin Hua',pig_dice:'Pig',racing_sprint:'Rally Sprint',emotion_context:'Emotion',support_routing:'Support Routing',mbti_text:'MBTI Text Test',robot_pick_cola:'Pick & Lift',chess:'Chess',breakthrough:'Breakthrough',mancala:'Mancala'};
 Object.assign(names,{checkers:'Checkers',go:'Go · 9×9',xiangqi:'Chinese Chess',guess_the_number:'Guess the Number',minesweeper:'Minesweeper',sudoku:'Sudoku',uno:'UNO'});
 const goals={terraria_survival:'Reach the portal on the right.',mario_platformer:'Reach the flag.',jump_jump:'Land on 8 platforms.',snake_navigation:'Collect 6 apples. Keep moving; avoid walls, rocks and your tail.',tetris_placement:'Clear 4 lines within 40 pieces.',merge_2048:'Make a 128 tile within 120 moves.',sokoban_puzzle:'Place both boxes on targets within 80 moves.',doudizhu:'Empty your hand before either farmer.',texas_holdem:'Win the pot.',property_tycoon:'Have more assets after 20 rounds.',liars_dice:'Catch a bluff or survive a challenge.',goofspiel:'Win more prize points across 7 rounds.',blackjack:'Beat the dealer without exceeding 21.',zha_jin_hua:'Win the three-card pot.',pig_dice:'Reach 50 points first.',racing_sprint:'Reach 900 m within 300 s with health remaining.',robot_pick_cola:'Pick up the red cola and lift it safely.'};
 Object.assign(goals,{checkers:'Capture or block all opposing pieces.',go:'Win on territory and captures. Both players pass to score; White receives komi.',xiangqi:'Checkmate the opposing general with legal moves.',guess_the_number:'Find the hidden integer from 1 to 20 within 10 distinct guesses.',minesweeper:'Reveal every safe cell without hitting a mine or running out of moves.',sudoku:'Complete the grid correctly before the move limit. Incorrect numbers end the game.',uno:'Match the color or face and be first to empty your hand.'});
 const rules={chess:'Standard chess. White moves first. Checkmate wins; stalemate and standard draw conditions apply.',breakthrough:'Move a pawn one square forward or diagonally forward. Capture diagonally. Reach the opposite edge or capture all opposing pawns to win.',mancala:'Sow seeds counterclockwise, skipping the opposing store. Finish in your store for another turn. Finish in your empty pit to capture an occupied opposite pit. Most seeds wins.',liars_dice:'Each player has 3 private dice. Bid a minimum quantity and face. Raise the quantity, or the face at the same quantity. Sixes are wild except when bidding sixes. Challenge: the bidder loses if the total is too low; otherwise the challenger loses.',goofspiel:'Bid each card from 1–7 once. Both bids reveal together; the higher bid wins the prize. Ties discard the prize. Remaining cards are public, sealed bids are private. The last card plays automatically. Most points after 7 rounds wins.',blackjack:'Hit or stand. Aces count as 1 or 11; face cards count as 10. Above 21 loses. The dealer hits through 16 and stands on 17, including soft 17. No splits or doubles. Equal totals draw.'};
 const labels={'对手':'Opponent','已密封出牌':'Bid sealed','玩家一':'Player 1','玩家二':'Player 2','规则对手':'Rule opponent','本地双人':'Two players','固定庄家':'Dealer','你':'You','庄家':'Dealer','白方':'White','黑方':'Black','行动次数':'Moves','决策次数':'Decisions','对局方式':'Mode','玩家一得分':'Player 1 score','玩家二得分':'Player 2 score','玩家一奖分':'Player 1 points','玩家二奖分':'Player 2 points','和局':'Draw','新的一局，开始吧':'Ready','玩家一已密封出牌，请玩家二接手':'Player 1 sealed a bid. Pass to Player 2.','梧桐街':'Plane St','银杏街':'Ginkgo St','枫林路':'Maple Rd','柳荫路':'Willow Rd','桃源里':'Peach Lane','竹影巷':'Bamboo Lane','松涛路':'Pine Rd','海棠街':'Begonia St','起点':'Start','机会':'Chance','税务':'Tax','地铁站':'Metro','车站':'Station','休息':'Rest','小王':'LJ','大王':'HJ','弃牌':'Fold','过牌':'Check','不出／过牌':'Pass','要牌':'Hit','停牌':'Stand','质疑上家':'Call liar','轮到你出牌':'Your turn','双方各投入 10 筹码；可以闷牌或先看牌。':'Ante: 10 each. Play blind or peek.','你先手，选择掷骰或收分。':'Your turn. Roll or bank.','你看了底牌；以后每次下注需要双倍筹码。':'Cards revealed. Your bets now cost double.','你加注；对手看牌后跟注。':'You raised; opponent called after peeking.','你跟注；对手看牌后跟注。':'You called; opponent called after peeking.','掷出 1，本轮分数作废；轮到对手。':'Rolled 1. Unbanked points lost; opponent’s turn.','已收分，轮到对手。':'Points banked; opponent’s turn.','现在轮到你。':'Your turn.','地主获胜！':'Landlord wins!','农民获胜。':'Farmers win!','你赢下底池！':'You win the pot!','对手赢下底池。':'Opponent wins the pot.','平局，平分底池。':'Draw. Pot split.','你弃牌，对手赢下底池。':'You folded. Opponent wins the pot.','你破产了。':'You are bankrupt.','对手破产，你赢了！':'Opponent bankrupt. You win!','你先达到 50 分，获胜！':'You reached 50. You win!','对手先达到 50 分，你输了。':'Opponent reached 50. You lose.','模型':'Model','玩家':'Player','参考':'Planner','你 · 地主':'You · Landlord','地主':'Landlord','农民1':'Farmer 1','农民2':'Farmer 2'};

 const translations={"Othello 6×6":"黑白棋 6×6","Othello 8×8":"黑白棋 8×8","Gomoku":"五子棋","Dots & Boxes":"点格棋","Terraria":"泰拉瑞亚","Mario":"马里奥","Jump Jump":"跳一跳","2048":"2048","Sokoban":"推箱子","Rally Sprint":"赛车","Connect three":"先连成三子","Connect four":"四子连线","Compact strategy":"小棋盘策略","Classic strategy":"经典翻子对弈","Five in a row":"五子连线","Connect opposite edges":"连接对边","Close boxes to score":"封格得分","Time your jump":"把握落点","Rotate and clear":"旋转与消行","Collect apples":"安全吃苹果","Merge tiles":"合并数字","Push boxes to targets":"箱子归位","Three-player card strategy":"三人出牌策略","Heads-up poker":"双人扑克","Buy, build and trade":"买地与经营","Explore and survive":"探索与生存","Platform adventure":"平台闯关","Pick and lift":"夹取并抬升","Understand emotion":"理解表达","Route requests":"判断处理队列","Real-time decisions":"实时决策","Joy":"喜悦","Sadness":"难过","Anger":"愤怒","Fear":"担忧","Surprise":"惊讶","Gratitude":"感激","Disgust":"厌恶","Neutral":"中性","Mixed emotions":"混合情绪","Uncertain":"信息不足","Account security":"账户安全","Billing and refunds":"账单与退款","Technical support":"技术支持","Delivery":"物流配送","Cancellation":"取消服务","Clarification":"澄清诉求","Hidden-dice strategy":"暗骰博弈","Bidding strategy":"竞价博弈","Probability strategy":"概率博弈","Probability play":"概率玩法","Roll or bank":"掷骰或收分","Featured":"精选","Board":"棋盘","Table":"牌桌","Arcade & puzzles":"街机与谜题","Simulation & text":"模拟与文本","All":"全部","Play now":"开始试玩","No matching games.":"没有找到对应玩法。"," scenarios":" 个场景","Mario failed to load. Refresh the page.":"马里奥加载失败，请刷新页面","Terraria failed to load. Refresh the page.":"泰拉瑞亚加载失败，请刷新页面。","Move left":"向左移动","Move right":"向右移动","Jump left":"向左跳跃","Jump right":"向右跳跃","Jump":"原地跳跃","Wait":"等待落地","Jump and ":"跳跃并","move / aim":"移动／瞄准","Ready":"等待操作","CuES synthetic data":"合成数据 · CuES 自建","Source ↗":"来源 ↗","Difficulty: ":"样例难度 ","Unrated":"待判定","Sample ":"样例 ","Explore right and reach the portal. Mining and bosses are optional.":"向右探索并抵达胜利之门；挖矿与 Boss 是可选挑战","Arrow keys move and aim. K mines, X attacks, C places blocks, Space jumps. The world keeps running during model responses.":"方向键移动与瞄准；K 挖矿、X 攻击、C 放置、空格跳跃。等待模型时世界继续运行。","Portal reached. Keep your gear and explore the next world.":"已通过胜利之门！装备保留，可以探索下一世界。","Guardian defeated and gate reached. Episode complete; reset to play again.":"已击败守门 Boss 并进入胜利之门！本局完成，重置后可重新开局。","Mine and upgrade, defeat the gate guardian, then enter the portal.":"采矿与战斗升级装备，击败守门 Boss 后进入胜利之门。","Respawning…":"角色倒下，正在重生…","Respawned. Keep exploring.":"已重生，继续探索","Cross the gaps and reach the flag.":"跳过深坑、踩退敌人，抵达右侧旗杆","A / D or arrows move. W / Space jumps. The world keeps running while the model responds.":"A / D 或方向键移动，W / 空格跳跃。等待模型时世界继续运行。","Health":"生命值","Ore":"已采矿石","Decisions":"决策次数","New world":"新世界","Jump too":"同时跳跃","Progress":"闯关进度","Coins":"收集金币","Restart":"重新开局","Cards left":"剩余手牌","Turns":"已出回合","Your chips":"你的筹码","Pot":"底池","Scores":"双方总分","Unbanked":"本轮暂存","Round":"回合","Your cash":"我的现金","Largest tile":"最大方块","Score":"本局分数","Moves":"行动次数","Boxes on target":"箱子归位","Holding":"夹持中","Target":"目标","Pieces":"已落方块","Lines":"已消行","You win!":"你赢了！","Game over":"本局结束","Play again":"再开一局","Hold to charge · Release to jump":"按住蓄力 · 松开跳跃","Charge time":"蓄力时长","Hold Space or the button to charge, then release. Or set a duration and press Jump.":"按住按钮或空格蓄力；也可以拖动时长后点击“跳”。","Drop column":"方块落下列","← / → choose a column. ↑ rotates. Space drops. The outline previews the landing.":"← → 选择列 · ↑ 旋转 · 空格落下；虚线是当前落点。","Arrows move. Q lifts, E lowers, Space grasps. Demo uses a rule planner.":"方向键移动；Q 抬升、E 下降、空格夹取。","Arrows or WASD slide tiles. Merge equal values and keep room to move.":"方向键或 WASD 滑动；相同数字碰撞时合并，尽量保留空位。","Arrows or WASD move. Push boxes onto targets; avoid dead corners.":"方向键或 WASD 移动；箱子只能推不能拉，推进墙角可能立即结束本局。","Arrows or WASD move. Avoid walls, obstacles and your own body.":"方向键或 WASD 移动；撞到墙、障碍或自己会结束本局。","Incomplete Sokoban movement receipt. Start a new game.":"推箱子逐格执行回执不完整，请重新开局；本次没有补造路径。","Game restarted":"本局已重开","Game ended":"对局已结束","Player respawned; a new observation is needed":"角色死亡或重生，需重新观察","World changed":"已进入新世界","Cancelled":"操作已取消","Response skipped · ":"回复未执行 · "," · World advanced ":" · 等待期间世界推进 "," frames":" 帧","Execution details":"执行反馈","Model thinking · World running":"模型思考中 · 世界持续运行","Planner chose ":"参考规划器选择 ","; no model call.":"；本步未调用模型。","Only one legal action; applied automatically.":"当前只有一个候选动作，本步自动执行。","Autoplay":"模型连玩","Demo":"参考演示","Customer message":"客户来信","Text":"一段真实表达","Choose the right support queue":"理解当前诉求，选择处理队列","Identify emotion in context":"结合上下文，理解文字中的情绪","Request":"用户的请求","Text to analyze":"这段话说了什么","Support queue":"处理队列","Emotions":"情绪候选","Route request ↗":"建议分流 ↗","Identify emotion ↗":"识别情绪 ↗","Which team should handle this?":"该由谁处理？","What emotion does this text express?":"这段话是什么心情？","Unavailable":"未返回","Model choice · ":"模型选择 · ","Observed token probability ":"已观测 token 原始概率 ","Candidate probability ":"候选概率 ","Analyzing…":"判断中…","Select cards and confirm, or choose a legal combination below.":"点选下方手牌组合，再确认出牌；也可从快速选牌中挑选合法组合。","Virtual chips only. Opponent cards are revealed at showdown.":"只使用虚拟筹码；对手底牌会在摊牌时揭晓。","Peeking doubles your bets. Opponent cards stay hidden until showdown.":"看牌前是闷牌，看牌后下注翻倍；对手底牌仅在结算时揭示。","A roll of 1 loses the unbanked points. Bank to end your turn.":"每次掷出 1 的概率为 1/6；收分后换对手。","You are green; your opponent is orange. Roll, then buy or upgrade.":"绿色代表你，暖橙代表对手；掷骰后可以购买或升级地产。","Your cards":"你的手牌","Select a legal combination":"选择合法牌型","Play cards ↗":"确认出牌 ↗","Quick selection":"快速选牌","Choose a legal combination":"选择合法出牌组合","Choose a combination…":"选择合法组合…","Selected ":"已选 "," cards · Ready":" 张 · 可以出牌"," cards · Invalid combination":" 张 · 组合暂不合法","Your move":"你的操作","Risk or bank":"风险决策","Choose an action":"选择下一步","Extraversion":"交流互动","Introversion":"内在思考","Sensing":"具体经验","Intuition":"抽象关联","Thinking":"逻辑标准","Feeling":"价值与人际影响","Judging":"规划收束","Perceiving":"开放调整","MBTI Text Test":"MBTI 文本测试","Explore the tendencies expressed in a piece of text.":"看看文字中的表达倾向。","16 types":"16 类","Your text":"你的文字","Add a description, journal entry, conversation or thought.":"可以是一段自我描述、日记、对话，或你此刻的一句话。","Results describe this text, not the author’s fixed personality.":"结果表示这段文字的倾向，不等同于作者的固定人格。","Try an example":"试试示例","Analyze text ↗":"分析文本 ↗","TEXT TENDENCY":"文本倾向","Start with a few words":"写下第一句话","Uses the selected model":"使用页面当前连接的模型","16 candidate types":"16 类候选","Probabilities appear after analysis":"判断后展示模型返回的概率","Source and model input":"来源与模型输入","Original TrainingRecord":"原始 TrainingRecord","Model input · messages / assistant suffix":"模型实际输入 · messages / assistant suffix","Model input":"模型输入","Source":"来源","16 types · Observed token probabilities":"16 类 · 已观测 token 原始概率","16 types · Normalized probabilities":"16 类 · 候选归一化概率","Partial response · Missing values stay missing":"部分返回 · 缺失项保持缺失","Complete · 16 / 16":"完整返回 · 16 / 16","Ready to analyze":"等待判断","Reading…":"模型正在阅读…","Add some text first.":"先写下一句话再试试。","Please shorten the text to 8,000 characters. It will not be truncated.":"文字超过 8,000 字，请缩短后再试；不会自动截断。","Reading your text…":"正在读取这段文字…","Model: ":"模型：","Time: ":"耗时 "," s":" 秒","Analysis complete":"分析完成","Sent API schema":"实际发送的官方 schema 请求","This API does not return its internal prompt. See the original record above.":"当前接口没有返回内部渲染输入；原始记录见上方。","Model request failed. Please retry.":"模型请求失败，请稍后再试。","The selection changed; the previous response was skipped.":"玩法或模型已切换，上一条回复未应用。","This weekend I want to organize my notes alone and connect a few seemingly unrelated ideas. When opinions differ, I compare the reasoning behind each option and leave room to adjust as new information arrives.":"周末我想先独自整理笔记，把几个看似无关的想法连起来。遇到分歧时，我会比较各方案的逻辑，再留一些空间根据新信息调整。","16-type classification":"16 类倾向分类"," characters":" 字","You · Landlord":"你 · 地主","Farmer A":"农民 A","Farmer B":"农民 B","Farmer ":"农民 "," · Played":" · 已出牌","Waiting":"等待行动","Dou Dizhu · Turn ":"斗地主 · 回合 "," cards":" 张","PUBLIC CARDS":"公开出牌","Trick over · New lead":"本轮结束 · 等待重新领出","Select cards below":"选择手牌"," leads":" 领出","Your hand · Landlord":"你的手牌 · 地主","No play":"尚未出牌","Dou Dizhu table. Public cards: ":"斗地主牌桌；本轮桌面 ",". Select cards from your hand below.":"。点击底部手牌选择出牌组合。","Preflop":"翻牌前","Flop":"翻牌","Turn":"转牌","River":"河牌","Opponent":"对手"," chips":" 筹码"," · Community cards":" · 公共牌","Your hand":"你的手牌","To call":"待跟注","Check available":"无需跟注","Texas Holdem table: opponent above, community cards in the center, your hand below.":"德州扑克牌桌；上方是对手和暗牌，中间是底池与公共牌，下方是你的手牌","Zha Jin Hua · Three-card poker":"炸金花  ·  三张牌博弈","Virtual chips":"仅虚拟筹码"," · Stake ":" · 档位 ","Seen":"已看牌","Blind":"闷牌","Three-card poker. Opponent cards are revealed only at showdown.":"炸金花牌桌；你的手牌按看牌状态显示，对手手牌只在摊牌后揭示","Pig · First to 50":"掷骰猪  ·  谁先拿到 50 分？","Rule opponent":"规则对手","Banked points":"累计分数","Unbanked points":"本轮暂存","Last roll: ":"上次骰点：","No roll yet":"尚未掷骰","Pig scoreboard: banked points on each side; unbanked points in the center.":"掷骰猪计分盘；左右是双方总分，中间是你的本轮暂存分","Your assets":"你的资产","Opponent assets":"对手资产","Cash":"现金"," properties":" 处地产","At ":"位于 ","Start":"起点","Chance":"机会","Tax":"税务","Transit":"交通","Rest":"休息","Property Tycoon":"大富翁"," rounds":" 回合","Last roll":"上次掷出","Buy this property":"可以购买当前地块","Upgrade this property":"可以升级当前地块","Roll to move":"掷骰前进","End turn":"结束回合","Property Tycoon. You are green; your opponent is orange.":"大富翁棋盘；绿色是你的地产和棋子，橙色是对手，中心显示回合与骰点","Round ":"回合 ","Turn: ":"轮到 ","Check":"过牌","Virtual points":"虚拟得分","Two players":"本地双人"," points":" 分","Clubs":"梅花","Diamonds":"方块","Hearts":"红桃","Spades":"黑桃","Dealer hole card":"庄家暗牌","Hidden card":"未公开的牌","Hidden":"暗牌","Breakthrough":"兵卒突围","Chess":"国际象棋"," board":"棋盘"," empty":" 空格"," White ":" 白"," Black ":" 黑"," · Choose a marked square":" · 点击标记格落子","Select a piece, then a destination":"点击己方棋子，再选择落点"," pit, ":" 号坑，"," seeds":" 颗种子"," · Upper row":" · 上排","Player 2":"玩家二","Store":"得分仓","Player 1":"玩家一"," · Lower row":" · 下排","Revealed dice":"本局揭晓","Last bid":"上一次叫数"," dice":" 枚","Waiting for the first bid":"等待第一次叫数"," · Private dice":"的骰子 · 仅本方可见","Sixes are wild · Six dice in total":"6 为万能点 · 双方共 6 枚骰子","Last revealed bids":"上一轮公开出牌"," · Prize ":" · 奖分 ","Cards appear once both players seal their bids":"双方出牌后揭示","All seven rounds complete":"七轮竞价结束"," / Prize":" 轮 · 本轮奖分","Opponent cards · ":"对方剩余牌 · "," · Automatic":" · 自动","Prize ":"奖分 ","Dealer cards":"庄家公开牌","Dealer ":"庄家 ","Pass the screen to the next player":"请下一位玩家接手",", your turn":"，轮到你了","Reveal your private view when you are ready.":"准备好后查看手牌。","Reveal my hand":"查看手牌","Promote to":"升变为","At least ":"至少 ","Bid quantity":"叫数数量","Face":"点数","Bid face":"叫数点数","Place bid":"确认叫数","Call liar":"质疑上家","Raise the quantity, or raise the face at the same quantity.":"加数量，或同数量加点数；不能重复或降低上次叫数。","Choose your bid":"选择本轮手牌","Play ":"出牌 ","Select and seal a bid":"选择后密封出牌","Seal bid · ":"密封出牌 · ","Both bids reveal together. Tied bids discard the prize.":"双方选择后同时揭示 · 同点出牌则奖分作废","Dealer stands on 17. Aces use the best value.":"庄家 17 点停牌 · A 自动取最有利点数","Legal moves · ":"查看合法动作 · ","Legal moves":"合法动作","Confirm":"确认行动","Choose a highlighted pit. Ending in your store earns another turn.":"点击亮起的己方种子坑 · 最后一颗进己仓可以连走","Select a piece, then its destination. Take turns on this screen.":"点击棋子再点击落点 · 支持本地双人轮流操作","Missed the platform":"这一跳落空了","Distance ":"距离 ","Width ":"宽度 ","Per ms ":"每毫秒 ","Release to jump.":"松开即可跳跃。","Collect three apples":"吃到三颗苹果","Move ":"步数 ","Current piece":"当前方块"," lines":" 行","Rotate, position, drop":"旋转，选择列，然后落下"," pieces":" 块","Merge and grow":"合并数字","Keep room to merge.":"留出合并空间。","Largest":"当前最大","Use arrows or buttons":"方向键或按钮滑动","Push boxes home":"箱子归位","Watch for dead corners.":"避开死角。","On target":"已归位","Moves ":"移动 ","Box":"木箱","Avoid dead corners":"避开墙角死局","Red cola":"红色可乐","Gripper  ":"夹爪  ","Gripper open":"夹爪已打开","One cell per move":"每次移动一格","Right +X":"右 +X","Back −Y":"后 −Y","Tic-tac-toe":"井字棋","Connect Four":"四子棋","Tetris":"俄罗斯方块","Snake":"贪吃蛇","Dou Dizhu":"斗地主","Texas Holdem":"德州扑克","Liar’s Dice":"吹牛骰子","Goofspiel":"竞价夺牌","Blackjack":"21点","Zha Jin Hua":"炸金花","Pig":"掷骰猪","Emotion":"情绪分类","Support Routing":"客服分流","Pick & Lift":"夹取与抬升","Mancala":"播棋","24 scenarios":"24 个场景","Reach the portal on the right.":"抵达右侧胜利之门。","Reach the flag.":"抵达终点旗杆。","Land on 8 platforms.":"连续跳上 8 个平台。","Collect 6 apples. Keep moving; avoid walls, rocks and your tail.":"吃到 6 颗苹果。自动前进，避开墙、石块和身体。","Clear 4 lines within 40 pieces.":"40 块内消除 4 行。","Make a 128 tile within 120 moves.":"120 步内合成 128。","Place both boxes on targets within 80 moves.":"80 步内把两只箱子推到目标。","Empty your hand before either farmer.":"以地主身份先出完手牌。","Win the pot.":"赢下底池。","Have more assets after 20 rounds.":"20 回合后资产超过对手。","Catch a bluff or survive a challenge.":"识破虚报，或让对手质疑失败。","Win more prize points across 7 rounds.":"七轮中赢得更多奖分。","Beat the dealer without exceeding 21.":"不超过 21 点，并胜过庄家。","Win the three-card pot.":"赢下三张牌底池。","Reach 50 points first.":"先达到 50 分。","Reach 900 m within 300 s with health remaining.":"300 秒内跑完 900 米，并保有耐久。","Pick up the red cola and lift it safely.":"夹起红色可乐并安全抬升。","Standard chess. White moves first. Checkmate wins; stalemate and standard draw conditions apply.":"标准国际象棋，白方先行。将死获胜；无子可走及标准和棋条件均适用。","Move a pawn one square forward or diagonally forward. Capture diagonally. Reach the opposite edge or capture all opposing pawns to win.":"兵向正前或斜前走一格，斜前可吃子。抵达对方底线或吃光对方兵获胜。","Sow seeds counterclockwise, skipping the opposing store. Finish in your store for another turn. Finish in your empty pit to capture an occupied opposite pit. Most seeds wins.":"逆时针播种，跳过对手得分仓。最后一颗落入己仓可连走；落入己方空坑可捕获对坑种子。种子多者胜。","Each player has 3 private dice. Bid a minimum quantity and face. Raise the quantity, or the face at the same quantity. Sixes are wild except when bidding sixes. Challenge: the bidder loses if the total is too low; otherwise the challenger loses.":"双方各三枚暗骰。叫至少几枚、几点；增加数量，或同数量提高点数。6 为万能点，叫 6 时仅数 6。质疑时数量不足则叫数者负，否则质疑者负。","Bid each card from 1–7 once. Both bids reveal together; the higher bid wins the prize. Ties discard the prize. Remaining cards are public, sealed bids are private. The last card plays automatically. Most points after 7 rounds wins.":"各有 1–7 七张牌，每张只用一次。双方密封出牌，同时揭示；大者获奖分，同点奖分作废。剩余牌公开、当轮出牌保密。最后一张自动出牌，七轮后总分高者胜。","Hit or stand. Aces count as 1 or 11; face cards count as 10. Above 21 loses. The dealer hits through 16 and stands on 17, including soft 17. No splits or doubles. Equal totals draw.":"选择要牌或停牌。A 算 1 或 11，花牌算 10，超过 21 即负。庄家 16 及以下要牌、17 及以上停牌（含软 17）。不分牌、不加倍，同点和局。","TEXT LAB · 16 TYPES":"文本实验室 · 16 类","You":"你","Dealer":"庄家","White":"白方","Black":"黑方","Mode":"对局方式","Player 1 score":"玩家一得分","Player 2 score":"玩家二得分","Player 1 points":"玩家一奖分","Player 2 points":"玩家二奖分","Draw":"和局","Bid sealed":"已密封出牌","Your turn":"轮到你","Your turn.":"轮到你。","Landlord":"地主","Farmer 1":"农民1","Farmer 2":"农民2","F":"农","Y":"你","R":"对","Roll":"掷骰","Bank":"收分","Peek":"看牌","Fold":"弃牌","Call":"跟注","Raise":"加注","Showdown":"比牌","Buy":"购买","Upgrade":"升级","Skip":"跳过","Pass":"不出","Hit":"要牌","Stand":"停牌","Up":"上","Down":"下","Left":"左","Right":"右","Forward":"前","Back":"后","Grasp":"夹取","Release":"松开","Move":"移动","Mine":"挖矿","Attack":"攻击","Place":"放置","Your turn. Roll or bank.":"轮到你，选择掷骰或收分。","Ante: 10 each. Play blind or peek.":"双方各投入 10 筹码；可以闷牌或看牌。","Cards revealed. Your bets now cost double.":"已看牌，此后下注翻倍。","You raised; opponent called after peeking.":"你加注，对手看牌后跟注。","You called; opponent called after peeking.":"你跟注，对手看牌后跟注。","Rolled 1. Unbanked points lost; opponent’s turn.":"掷出 1，本轮分数作废，轮到对手。","Points banked; opponent’s turn.":"已收分，轮到对手。","Landlord wins!":"地主获胜！","Farmers win!":"农民获胜！","You win the pot!":"你赢下底池！","Opponent wins the pot.":"对手赢下底池。","Draw. Pot split.":"平局，平分底池。","You folded. Opponent wins the pot.":"你弃牌，对手赢下底池。","You are bankrupt.":"你破产了。","Opponent bankrupt. You win!":"对手破产，你赢了！","You reached 50. You win!":"你先达到 50 分，获胜！","Opponent reached 50. You lose.":"对手先达到 50 分，你输了。","Player 1 sealed a bid. Pass to Player 2.":"玩家一已密封出牌，请玩家二接手。","Buy this property or skip":"购买地块或跳过","Upgrade this property or skip":"升级地块或跳过","End your turn":"结束回合","Plane St":"梧桐街","Ginkgo St":"银杏街","Maple Rd":"枫林路","Willow Rd":"柳荫路","Peach Lane":"桃源里","Bamboo Lane":"竹影巷","Pine Rd":"松涛路","Begonia St":"海棠街","Metro":"地铁站","Station":"车站","LJ":"小王","HJ":"大王","HOP":"跳跃","ORCHARD":"果园","BLOCKS":"方块","MERGE / 2048":"合并 / 2048","WAREHOUSE / 02":"仓库 / 02","PICK & LIFT":"夹取与抬升","PRIVATE TABLE":"牌桌","VIRTUAL CHIPS  ·  HEADS UP":"虚拟筹码 · 双人","PROPERTY TOUR":"地产经营","PRIZE":"奖分","21 POINTS":"21 点","CARD TABLE":"牌桌","POKER TABLE":"扑克","PIXEL ADVENTURE":"像素冒险","PIXEL SANDBOX":"像素沙盒","NUMBER PUZZLE":"数字谜题","WAREHOUSE PUZZLE":"仓库谜题","REALTIME RACING":"实时赛车","ROBOTICS":"机械臂","LANGUAGE":"语言","PLAY":"试玩","Select cards, then confirm.":"选好手牌后确认出牌。","Opponent cards reveal at showdown.":"对手手牌在摊牌时揭示。","Roll, then buy or upgrade.":"掷骰后购买或升级地产。","Charge ":"蓄力 ","Rotation ":"旋转 "," · Column ":" · 列 ","Bid ":"出牌 ","Sealed bid · ":"密封出牌 · "," · Bids ":" · 出牌 "," · Pass":" · 不出"," · Virtual chips":" · 虚拟筹码"," samples":" 条样例"," · Ready":" · 可出牌"," · Invalid combination":" · 组合不合法","Bet ":"下注 ","Call ":"跟注 ","Raise ":"加注 ","Bank ":"收分 "," ■ Stop":" ■ 停止","■ Stop ":"■ 停止","Stop ":"停止","autoplay":"连玩","demo":"演示","ms":"毫秒","Card table":"牌桌","Game":"游戏","Piece ":"方块 ","Rotate":"旋转","Drop":"落下","Missing probabilities are unavailable; observed values are not normalized.":"缺失概率不补值；已观测值不归一化。","Probabilities describe relative preference, not calibrated accuracy.":"概率表示相对偏好，不代表校准后的准确率。"};
 Object.assign(translations,{'Capture or block all opposing pieces.':'吃光对方棋子或使其无棋可走。','Win on territory and captures. Both players pass to score; White receives komi.':'以地盘和提子争胜。双方连续停着后计分，白方获得贴目。','Checkmate the opposing general with legal moves.':'通过合法着法将死对方将帅。','Find the hidden integer from 1 to 20 within 10 distinct guesses.':'10 次不重复猜测内，找到 1 到 20 中的隐藏整数。','Reveal every safe cell without hitting a mine or running out of moves.':'在步数耗尽前揭开全部安全格，避开地雷。','Complete the grid correctly before the move limit. Incorrect numbers end the game.':'在步数耗尽前正确填满数独，填错即结束。','Match the color or face and be first to empty your hand.':'匹配颜色或牌面，先出完手牌获胜。'});
 Object.assign(translations,{'Checkers':'西洋跳棋','Go · 9×9':'围棋 · 9×9','Chinese Chess':'中国象棋','Guess the Number':'猜数字','Minesweeper':'扫雷','Sudoku':'数独','Checkers strategy':'跳吃与升王','9×9 territory':'争夺地盘','Chinese chess':'楚河汉界','Higher or lower':'判断大小','Reveal safe cells':'安全排雷','Fill the grid':'填满数独','Match colors and numbers':'匹配颜色与数字'});
 Object.assign(translations,{'Falling blocks':'实时落块','REALTIME TETRIS':'实时俄罗斯方块','Rotate clockwise':'顺时针旋转','Rotate counterclockwise':'逆时针旋转','Soft drop':'软降','Hard drop':'直落','Hold input':'保持当前操作',Realtime:'实时','Collect six apples':'吃到六颗苹果','Keep moving':'持续前进'});
 const isChinese=()=>window.JevI18n?.lang==='zh';
 const reverse=Object.fromEntries(Object.entries(translations).map(([en,zh])=>[zh,en]));
 const escapePattern=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const expression=map=>new RegExp(Object.keys(map).sort((a,b)=>b.length-a.length).map(key=>(/^[A-Za-z]/.test(key)?'(?<![A-Za-z])':'')+escapePattern(key)+(/[A-Za-z]$/.test(key)?'(?![A-Za-z])':'')).join('|'),'g');
 const toChinese=expression(translations),toEnglish=expression(reverse);
 function ui(value){
  const source=String(value??'');
  if(isChinese()){if(translations[source])return window.JevI18n?.t(source,translations[source])??translations[source];return source.replace(toChinese,part=>translations[part]);}
  if(!/[\u3400-\u9fff]/.test(source))return source;
  return reverse[source]||source.replace(toEnglish,part=>reverse[part]);
 }
 function html(markup){
  const template=document.createElement('template');template.innerHTML=String(markup??'');
  const walker=document.createTreeWalker(template.content,NodeFilter.SHOW_TEXT);let node;
  while((node=walker.nextNode())){if(!node.parentElement?.closest('pre,code,textarea,script,style'))node.nodeValue=ui(node.nodeValue);}
  template.content.querySelectorAll('[aria-label],[placeholder],[title]').forEach(element=>{for(const attr of ['aria-label','placeholder','title'])if(element.hasAttribute(attr))element.setAttribute(attr,ui(element.getAttribute(attr)));});
  return template.innerHTML;
 }
 function text(value){
  const input=String(value??'');if(isChinese())return ui(input);if(labels[input])return labels[input];
  let out=input;
  for(const [before,after] of Object.entries(labels).sort((a,b)=>b[0].length-a[0].length))out=out.split(before).join(after);
  return out.replace(/至少 (\d+) 枚「(\d+)」/g,'At least $1 × $2').replace(/密封出牌 · /g,'Sealed bid · ').replace(/奖分 (\d+) · 出牌 /g,'Prize $1 · Bids ').replace(/；最后一轮自动亮牌/g,'; final round automatic').replace(/播种 · (\d+) 号坑/g,'Sow pit $1').replace(/(Player [12]|White|Black|You|Dealer|Rule opponent)获胜/g,'$1 wins').replace(/下注 (\d+)/g,'Bet $1').replace(/跟注 (\d+)/g,'Call $1').replace(/加注 (\d+)/g,'Raise $1').replace(/掷出 (\d+)，本轮暂存 (\d+) 分。/g,'Rolled $1. Unbanked: $2.').replace(/(You|Opponent)掷出 (\d+)，到达/g,'$1 rolled $2, reached ').replace(/，轮到You/g,', your turn');
 }
 function actionEnglish(kind,id,value){
  if(kind==='jump_jump')return 'Charge '+id+' ms';
  if(kind==='tetris_placement'){const manual={left:'Left',right:'Right',rotate_cw:'Rotate clockwise',rotate_ccw:'Rotate counterclockwise',soft_drop:'Soft drop',hard_drop:'Hard drop',wait:'Hold input'};if(manual[id])return manual[id];const [rotation,column]=String(id).split(':');return 'Rotation '+rotation+' · Column '+column;}
  if(['up','down','left','right','forward','backward','grasp','open'].includes(id))return {up:'Up',down:'Down',left:'Left',right:'Right',forward:'Forward',backward:'Back',grasp:'Grasp',open:'Release'}[id];
  if(kind==='sokoban_puzzle'&&String(id).startsWith('push:')){const [,x,y,direction,gx,gy]=String(id).split(':');return 'Push box ('+x+', '+y+') '+direction+' toward ('+gx+', '+gy+')';}
  if(kind==='blackjack')return id==='0'?'Hit':id==='1'?'Stand':text(value);
  if(kind==='goofspiel')return 'Bid '+(Number(id)+1);
  if(kind==='liars_dice')return id==='36'?'Call liar':'At least '+(Math.floor(Number(id)/6)+1)+' × '+(Number(id)%6+1);
  if(kind==='doudizhu')return id==='pass'?'Pass':text(value);
  const simple={fold:'Fold',check:'Check',call:'Call',raise:'Raise',peek:'Peek',compare:'Showdown',roll:'Roll',hold:'Bank',buy:'Buy',build:'Upgrade',skip:'Skip',next:'End turn',showdown:'Showdown'};
  if(simple[id]){const amount=String(value??'').match(/\d+/)?.[0];return simple[id]+(amount&&['call','raise','hold'].includes(id)?' '+amount:'');}
  return text(value??id);
 }
 function action(kind,id,value){return ui(actionEnglish(kind,id,value));}
 function event(kind,g){
  if(isChinese())return g.outcome?ui({win:'You win!',loss:'Game over',draw:'Draw'}[g.outcome]||g.outcome_label):g.event||ui('Your turn');
  if(g.outcome)return {win:'You win!',loss:'Game over',draw:'Draw'}[g.outcome]||text(g.outcome_label);
  const translated=text(g.event||'');
  if(!/[\u3400-\u9fff]/.test(translated))return translated;
  if(kind==='property_tycoon')return {roll:'Roll to move',buy:'Buy this property or skip',build:'Upgrade this property or skip',next:'End your turn'}[g.phase]||'Your turn';
  return 'Your turn';
 }
 return {names,ui,html,name:(kind,fallback)=>ui(names[kind]||text(fallback)),goal:(kind,fallback)=>ui(goals[kind]||text(fallback)),rules:(kind,fallback)=>ui(rules[kind]||text(fallback)),action,text,event};
})();
/* Canvas scenes: visuals interpolate actual rule-engine states; no predicted moves are fabricated. */
const PlayDraw=(()=>{
 const palette=['#74a9a0','#c8a2c8','#ecb56f','#83b9cf','#a9be74'];
 const SH={I:[[0,0],[1,0],[2,0],[3,0]],O:[[0,0],[1,0],[0,1],[1,1]],T:[[0,0],[1,0],[2,0],[1,1]],S:[[1,0],[2,0],[0,1],[1,1]],Z:[[0,0],[1,0],[1,1],[2,1]],J:[[0,0],[0,1],[1,1],[2,1]],L:[[2,0],[0,1],[1,1],[2,1]]};
 let c;
 const rr=(x,y,w,h,r,color)=>{c.fillStyle=color;c.beginPath();c.roundRect(x,y,w,h,r);c.fill()};
 const txt=(s,x,y,size=18,color='#70897c',weight=400)=>{c.fillStyle=color;c.font=weight+' '+size+'px '+getComputedStyle(document.body).fontFamily;c.fillText(JevPlayText.ui(s),x,y)};
 const circle=(x,y,r,col)=>{c.fillStyle=col;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill()};
 const ellipse=(x,y,rx,ry,col)=>{c.fillStyle=col;c.beginPath();c.ellipse(x,y,rx,ry,0,0,Math.PI*2);c.fill()};
 const poly=(ps,color)=>{c.fillStyle=color;c.beginPath();ps.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.fill()};
 const line=(ps,color,width=2)=>{c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.lineJoin='round';c.beginPath();ps.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.stroke()};
 const mix=(a,b,t)=>a+(b-a)*t;
 function rotations(name){let shape=SH[name].map(p=>[...p]),result=[];for(let i=0;i<4;i++){const xmin=Math.min(...shape.map(p=>p[0])),ymin=Math.min(...shape.map(p=>p[1]));shape=shape.map(([x,y])=>[x-xmin,y-ymin]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);if(!result.some(x=>JSON.stringify(x)===JSON.stringify(shape)))result.push(shape);shape=shape.map(([x,y])=>[-y,x])}return result}
 function landing(g,rot,col){const shape=rotations(g.piece)[rot],fits=y=>shape.every(([x,dy])=>x+col>=0&&x+col<10&&y+dy<g.board.length&&!g.board[y+dy][x+col]);if(!shape||!fits(0))return [];let y=0;while(fits(y+1))y++;return shape.map(([x,dy])=>[x+col,y+dy])}
 function pill(s,x,y,color='#ffffffc9'){const w=String(s).length*10+28;rr(x,y,w,32,16,color);txt(s,x+14,y+22,13,'#698175',550)}
 function platform(x,y,w,col,side){ellipse(x+10,y+65,w*.62,19,'#72948616');poly([[x-w/2,y],[x,y+24],[x,y+80],[x-w/2,y+56]],side);poly([[x,y+24],[x+w/2,y],[x+w/2,y+56],[x,y+80]],col);poly([[x,y-24],[x+w/2,y],[x,y+24],[x-w/2,y]],'#e9f1e8');line([[x-w/2,y],[x,y+24],[x+w/2,y]],'#ffffffaa',2)}
 function pawn(x,y,height=0,squash=1){ellipse(x,y+7,20,8,'#344e4623');const py=y-height;rr(x-12,py-40*squash,24,36*squash,11,'#31574f');circle(x,py-46*squash,13,'#24483f');circle(x-3,py-50*squash,4,'#477566');line([[x-6,py-25*squash],[x-6,py-12*squash]],'#709488',2)}
 function jump(g,o){const old=o.before,anim=!!old,t=o.progress??1,scene=anim?old:g;c.fillStyle='#edf3ec';c.fillRect(0,0,900,540);circle(755,94,117,'#e4ece1');circle(38,430,135,'#e5eee4');for(let i=0;i<7;i++){c.strokeStyle='#dfe9dc';c.lineWidth=1;c.beginPath();c.moveTo(i*180-180,540);c.lineTo(i*180+400,0);c.stroke()}
 txt('HOP',38,47,14,'#849987',650);txt(String(g.score).padStart(2,'0'),755,68,42,'#567761',600);txt('/ 08',817,67,17,'#92a48e');
 const distance=scene.target-scene.position,scale=Math.min(2.05,450/distance),sx=200,sy=365,px=v=>sx+(v-scene.position)*scale,py=v=>sy-(v-scene.position)*.47;
 platform(sx,sy,105,'#9ab59b','#789d89');platform(px(scene.target),py(scene.target),Math.max(43,scene.width*scale),'#87b09d','#659382');
 ellipse(px(scene.target),py(scene.target),9,4,'#90b798');
 c.setLineDash([4,9]);line([[sx+30,sy-14],[px(scene.target)-25,py(scene.target)-14]],'#abc2ae',2);c.setLineDash([]);
 let pos=scene.position,h=0;if(anim){const final=scene.position+Number(o.action)*scene.gain;pos=mix(scene.position,final,t);h=Math.sin(t*Math.PI)*135;if(g.outcome==='loss'&&t>.75)h-=100*(t-.75)/.25}
 pawn(px(pos),py(pos),h,o.charging?Math.max(.55,1-o.charging*.4):1);
 if(!anim&&g.outcome==='loss'){txt('Missed the platform',360,175,24,'#aa8270',600)}
 pill('Distance '+Math.round(distance),40,475);pill('Width '+scene.width,198,475);pill('Per ms '+scene.gain,360,475);txt('Release to jump.',617,498,16,'#91a28e');
 }
 function apple(x,y,r=12){circle(x-r*.35,y,r*.77,'#d98569');circle(x+r*.35,y,r*.77,'#de9074');line([[x,y-r*.55],[x+2,y-r*1.35]],'#7c8860',3);ellipse(x+7,y-r*1.12,7,3,'#9bb084');circle(x-6,y-4,3,'#efb49a')}
 function snake(g,o){const mobile=c.canvas.width===540;c.fillStyle='#f2f5ed';c.fillRect(0,0,c.canvas.width,c.canvas.height);circle(52,435,100,'#e7eede');circle(827,103,140,'#e9efdf');const target=g.food_target||3;txt('ORCHARD',35,43,14,'#83916e',600);txt(String(g.score).padStart(2,'0')+' / '+String(target).padStart(2,'0'),mobile?395:730,44,mobile?28:23,'#72875d',600);
 const size=(mobile?450:420)/g.n,scale=size/42,ox=mobile?45:240,oy=mobile?85:67;rr(ox-14,oy-14,size*g.n+28,size*g.n+28,23,'#dce7ce');rr(ox-5,oy-5,size*g.n+10,size*g.n+10,15,'#f6f8ee');
 for(let y=0;y<g.n;y++)for(let x=0;x<g.n;x++)rr(ox+x*size,oy+y*size,size,size,0,(x+y)%2?'#f0f4e7':'#eaf0df');
 for(const [x,y]of g.obstacles){rr(ox+x*size+4*scale,oy+y*size+9*scale,size-8*scale,size-12*scale,6*scale,'#a6af91');rr(ox+x*size+4*scale,oy+y*size+4*scale,size-8*scale,size-12*scale,6*scale,'#c0c9ac');line([[ox+x*size+12*scale,oy+y*size+10*scale],[ox+x*size+24*scale,oy+y*size+10*scale]],'#dce2cd',2*scale)}
 if(!g.outcome||g.outcome!=='win')apple(ox+(g.food[0]+.5)*size,oy+(g.food[1]+.5)*size,14*scale);
 const body=g.body.map(([x,y],i)=>{const p=o.before?.body[Math.min(i,o.before.body.length-1)];return p?[mix(p[0],x,o.progress??1),mix(p[1],y,o.progress??1)]:[x,y]}).map(([x,y])=>[ox+(x+.5)*size,oy+(y+.5)*size]);
 if(body.length>1)line([...body].reverse(),'#809e61',29*scale);body.slice(1).reverse().forEach(([x,y],i)=>circle(x,y,14*scale,i%2?'#84a065':'#8ca970'));
 const [hx,hy]=body[0];circle(hx,hy,18*scale,g.event==='collision'?'#b77966':'#62834b');const dir={up:[0,-1],right:[1,0],down:[0,1],left:[-1,0]}[g.direction];for(const side of [-1,1]){const ex=hx+(dir[0]*7-dir[1]*side*7)*scale,ey=hy+(dir[1]*7+dir[0]*side*7)*scale;circle(ex,ey,4.4*scale,'#f6f7df');circle(ex+dir[0]*scale,ey+dir[1]*scale,2*scale,'#344629')}
 if(mobile){txt('Move '+g.steps,45,585,24,'#72875d');txt(g.started?g.elapsed.toFixed(1)+' s':'Ready',375,585,24,'#72875d');return;}
 txt(target===6?'Collect six apples':'Collect three apples',35,232,19,'#8c9b79');for(let i=0;i<target;i++){apple(55+i%3*42,265+Math.floor(i/3)*35,12);if(i<g.score)circle(55+i%3*42,284+Math.floor(i/3)*35,3,'#62834b')}
 txt('Move '+g.steps,710,260,18,'#8c9b79');if(g.engine_revision){txt(g.started?g.elapsed.toFixed(1)+' s':'Ready',710,295,20,'#72875d');txt('Keep moving',710,330,15,'#8c9b79')}
 }
 function tile(x,y,s,col,ghost=false){if(ghost){c.strokeStyle=col;c.lineWidth=2;c.setLineDash([5,4]);c.strokeRect(x+3,y+3,s-6,s-6);c.setLineDash([]);return}rr(x+2,y+2,s-4,s-4,2,col);rr(x+5,y+4,s-10,4,0,'#ffffff47');rr(x+5,y+s-7,s-10,3,0,'#00000012')}
 function tetris(g,o){c.fillStyle='#f7f4e7';c.fillRect(0,0,900,540);circle(795,459,160,'#e5ecd9');txt('BLOCKS',35,43,14,'#718d7b',700);
 const s=32,ox=210,oy=87;rr(ox-14,oy-14,348,412,3,'#6d9484');rr(ox-5,oy-5,330,394,2,'#e8efdf');
 g.board.forEach((row,y)=>row.forEach((v,x)=>{if(v)tile(ox+x*s,oy+y*s,s,'#668fa0');else{c.fillStyle=(x+y)%2?'#f3f6e9':'#e9f0e2';c.fillRect(ox+x*s,oy+y*s,s,s);c.strokeStyle='#bdd3bd';c.lineWidth=.8;c.strokeRect(ox+x*s,oy+y*s,s,s)}}));
 const shape=rotations(g.piece)[o.rot||0],col=o.col??4;for(const [x,y]of landing(g,o.rot||0,col))tile(ox+x*s,oy+y*s,s,'#b591b8',true);
 const color=palette[Object.keys(SH).indexOf(g.piece)%palette.length];shape.forEach(([x,y])=>tile(ox+(x+col)*s,oy+(y+(o.dropProgress||0)*Math.max(0,(landing(g,o.rot||0,col)[0]?.[1]||0)-(shape[0]?.[1]||0)))*s,s,color));
 txt('Current piece',602,128,15,'#698a77');shape.forEach(([x,y])=>tile(602+x*29,155+y*29,29,color));txt(String(g.lines).padStart(2,'0'),602,302,49,'#426f60',700);txt('/ 04 lines',679,302,17,'#809a82');txt('Rotate, position, drop',601,357,15,'#718d7b');txt('Piece '+g.steps,601,385,14,'#8ca48b');
 }
 function merge2048(g,o={}){
  c.fillStyle='#f7f0e7';c.fillRect(0,0,900,540);
  if(window.innerWidth>620){circle(62,489,155,'#eedfcc');circle(856,42,145,'#f0e3d3');txt('MERGE / 2048',38,50,14,'#ac7956',750);txt('Merge and grow',38,123,30,'#604b3c',750);txt('Keep room to merge.',40,155,15,'#9b806d');rr(38,204,166,102,19,'#fff9f0');txt('Score',58,237,14,'#a78974');txt(g.score,56,284,37,'#754e38',750);rr(38,323,166,102,19,'#fff9f0');txt('Largest',58,356,14,'#a78974');txt(Math.max(...g.board.flat())+' / 128',56,402,29,'#754e38',750)}
  const x0=c.canvas.width===540?38:253,y0=48,s=105,gap=8;rr(x0-13,y0-13,4*s+5*gap+18,4*s+5*gap+18,23,'#b9aa98');
  const colors={2:'#eee4da',4:'#eee1c9',8:'#f3b27a',16:'#f69664',32:'#f77c5f',64:'#f75f3b',128:'#edd073',256:'#eccb61',512:'#e8c553'};
  const paint=(v,x,y,scale=1)=>{const px=x0+x*(s+gap),py=y0+y*(s+gap),inset=s*(1-scale)/2;rr(px+inset,py+inset,s*scale,s*scale,12,v?(colors[v]||'#5c6269'):'#d2c5b5');if(v){c.textAlign='center';c.textBaseline='middle';txt(v,px+s/2,py+s/2+2,(v>=128?34:40)*scale,v>=8?'#fffaf3':'#71685e',800);c.textAlign='left';c.textBaseline='alphabetic'}};
  if(o.tileMotion){for(let y=0;y<4;y++)for(let x=0;x<4;x++)paint(0,x,y);for(const m of o.tileMotion)paint(m.value,mix(m.x,m.tx,o.progress),mix(m.y,m.ty,o.progress));}
  else g.board.forEach((row,y)=>row.forEach((v,x)=>paint(v,x,y)));

  if(window.innerWidth>620){rr(739,207,125,116,18,'#fff9f0');txt('Target',761,243,14,'#a78974');txt('128',756,292,40,'#ad6f43',800);txt('Move '+g.steps+' / 120',740,368,15,'#987c67');txt('Use arrows or buttons',725,455,15,'#967d6b')}
 }
 function sokoban(g,o={}){
  c.fillStyle='#ecf3f2';c.fillRect(0,0,900,540);
  if(window.innerWidth>620){circle(848,461,145,'#dfeae7');circle(79,88,135,'#e2edeb');txt('WAREHOUSE / 02',38,50,14,'#5f898b',750);txt('Push boxes home',38,123,29,'#2d565e',750);txt('Watch for dead corners.',40,156,15,'#6c8b90');rr(36,230,175,101,18,'#fff');txt('On target',58,263,14,'#77969a');txt(g.score+' / '+g.targets.length,57,310,35,'#317c84',760);rr(36,346,175,75,18,'#fff');txt('Moves '+g.steps+' / 80',58,391,20,'#547d80',700)}
  const size=55,ox=242,oy=48,walls=new Set(g.walls.map(p=>p.join(','))),goals=new Set(g.targets.map(p=>p.join(',')));
  rr(ox-12,oy-12,size*8+24,size*8+24,21,'#a7c1c2');
  for(let y=0;y<8;y++)for(let x=0;x<8;x++){const px=ox+x*size,py=oy+y*size,key=x+','+y;rr(px+2,py+2,size-4,size-4,6,walls.has(key)?'#52737a':(x+y)%2?'#f4f7f2':'#edf4ef');if(walls.has(key)){rr(px+8,py+8,size-16,7,3,'#7b9699');continue}if(goals.has(key)){circle(px+size/2,py+size/2,15,'#83b6aa');circle(px+size/2,py+size/2,8,'#d7eee0')}}
  // Consecutive frames differ by one legal grid move, never a straight-line
  // shortcut from the start of a push intent to its final standing square.
  const progress=o.progress??1,old=o.before;
  const oldBoxes=old?new Set(old.boxes.map(p=>p.join(','))):null,newBoxes=new Set(g.boxes.map(p=>p.join(',')));
  const source=old?.boxes.find(p=>!newBoxes.has(p.join(',')));
  for(const target of g.boxes){const key=target.join(','),moving=source&&!oldBoxes.has(key),pos=moving?target.map((n,j)=>mix(source[j],n,progress)):target,px=ox+pos[0]*size,py=oy+pos[1]*size;
   rr(px+7,py+7,size-14,size-14,8,goals.has(key)?'#55a797':'#d8a971');rr(px+12,py+12,size-24,size-24,4,goals.has(key)?'#79bcaf':'#e3bb8a');line([[px+17,py+17],[px+size-17,py+size-17]],'#fff7e980',3);line([[px+size-17,py+17],[px+17,py+size-17]],'#fff7e980',3);
  }
  const player=old?g.player.map((n,j)=>mix(old.player[j],n,progress)):g.player;
  const px=ox+(player[0]+.5)*size,py=oy+(player[1]+.5)*size;ellipse(px,py+14,17,7,'#25464b36');circle(px,py,17,'#368c95');circle(px-6,py-5,3,'#fff');circle(px+6,py-5,3,'#fff');rr(px-7,py+6,14,3,2,'#d6efed');
  if(window.innerWidth>620){txt('■  Box',726,235,16,'#9d754e',700);txt('◎  Target',726,278,16,'#558e83',700);txt('●  You',726,321,16,'#3d8790',700);txt('Avoid dead corners',725,455,15,'#6b8d8f')}
 }
 function robot(g,o){c.fillStyle='#f2f5f6';c.fillRect(0,0,900,540);circle(770,60,170,'#e8eff2');txt('PICK & LIFT',35,42,13,'#8ba0aa',650);pill('Target  Red cola',655,22,'#fff');
 const p=([x,y,z=0])=>[455+(x-y)*39,220+(x+y)*18-z*38];
 const box=(x,y,z,w,d,h,top='#c5d5dc',left='#adbec9',right='#d3dfe4')=>{poly([p([x,y,z]),p([x+w,y,z]),p([x+w,y,z+h]),p([x,y,z+h])],left);poly([p([x+w,y,z]),p([x+w,y+d,z]),p([x+w,y+d,z+h]),p([x+w,y,z+h])],right);poly([p([x,y,z+h]),p([x+w,y,z+h]),p([x+w,y+d,z+h]),p([x,y+d,z+h])],top)};
 ellipse(450,456,332,39,'#6c859a0d');box(-.8,-.8,-1.25,7.6,7.6,.5,'#e3ebed','#c5d0d5','#d1dce0');
 for(let i=0;i<=6;i++){line([p([i,0,-.74]),p([i,6,-.74])],'#c8d6dba6',1);line([p([0,i,-.74]),p([6,i,-.74])],'#c8d6dba6',1)}
 c.setLineDash([3,6]);line(g.trail.map(q=>p([q[0],q[1],-.73])),'#87b4aa80',2);c.setLineDash([]);
 for(const [x,y]of g.obstacles)box(x-.36,y-.36,-.7,.72,.72,1.9,'#e7c89c','#cda879','#dfbb8e');
 const target=p([g.target[0],g.target[1],-.72]);ellipse(target[0],target[1],30,14,'#bfd9d470');c.strokeStyle='#89b8aa';c.lineWidth=1;c.beginPath();c.ellipse(target[0],target[1],29,13,0,0,Math.PI*2);c.stroke();
 const tool=o.before?g.tool.map((n,i)=>mix(o.before.tool[i],n,o.progress)):g.tool;const held=g.holding&&(!o.before||o.before.holding||o.progress>.8);
 function can(pos,water){const [x,y]=p(pos),h=water?46:38,r=water?10:13;ellipse(x+8,y+22,r+4,6,'#45647916');rr(x-r,y-h/2,r*2,h,5,water?'#a8cee0':'#c96b62');ellipse(x,y-h/2,r,4,water?'#d0e9f1':'#d9dedb');ellipse(x,y+h/2-1,r,3,water?'#7daec5':'#b95f58');rr(x-r,y-7,r*2,15,0,water?'#dfedf0':'#f4e5d6');txt(water?'H₂O':'COLA',x-r+3,y+4,water?8:8,water?'#7f9eaa':'#ba675e',650);if(water)rr(x-5,y-h/2-8,10,9,3,'#81aabc')}
 can(g.water,true);if(!held)can(g.target,false);
 const base=[-1.6,3,0],shoulder=[-1.6,3,1.0],L1=4.5,L2=4.5,dx=tool[0]-shoulder[0],dy=tool[1]-shoulder[1],dz=tool[2]-shoulder[2],r=Math.hypot(dx,dy),d=Math.max(.001,Math.hypot(r,dz));const a=Math.atan2(dz,r)+Math.acos(Math.max(-1,Math.min(1,(L1*L1+d*d-L2*L2)/(2*L1*d))));const elbow=[shoulder[0]+dx/(r||1)*L1*Math.cos(a),shoulder[1]+dy/(r||1)*L1*Math.cos(a),shoulder[2]+L1*Math.sin(a)];
 const bp=p(base);ellipse(bp[0],bp[1]+23,48,18,'#aebec9');rr(bp[0]-30,bp[1]-4,60,24,8,'#cad6df');ellipse(bp[0],bp[1]-5,30,11,'#e3eaf0');
 const joints=[p(shoulder),p(elbow),p(tool)];line([p(base),p(shoulder)],'#768f9f',29);line(joints,'#7f95a3',26);line(joints,'#f4f6f6',18);line(joints,'#d4e0e5',7);
 joints.forEach((q,i)=>{circle(q[0],q[1],i===2?10:15,'#8ca2b0');circle(q[0],q[1],i===2?5:9,'#e7eef0');circle(q[0],q[1],4,'#6c95a6')});
 const [gx,gy]=joints[2],spread=held?11:20;line([[gx,gy],[gx,gy+16]],'#7f96a4',8);line([[gx,gy+13],[gx-spread,gy+13],[gx-spread,gy+31],[gx-spread+5,gy+35]],'#7991a0',5);line([[gx,gy+13],[gx+spread,gy+13],[gx+spread,gy+31],[gx+spread-5,gy+35]],'#7991a0',5);if(held)can([tool[0],tool[1],tool[2]-.55],false);
 txt('Gripper  '+g.tool.join(' · '),35,500,14,'#8199a6');txt(g.holding?'Holding':'Gripper open',35,475,15,g.holding?'#5a9686':'#91a5ad',500);txt('One cell per move',708,493,14,'#a0aeb5');
 const a0=p([4,6,-.74]),ax=p([6,6,-.74]),ay=p([4,4,-.74]);line([a0,ax],'#acbdc2',2);txt('Right +X',ax[0]+8,ax[1]+10,11,'#91a6af');line([a0,ay],'#acbdc2',2);txt('Back −Y',ay[0]+8,ay[1],11,'#91a6af');
 }
 function draw(g,o={}){if(window.JevTetrisRenderer?.supports(g)){window.JevTetrisRenderer.draw(g,o);return;}const canvas=document.getElementById('showcaseCanvas'),mobileSnake=g.kind==='snake_navigation'&&g.engine_revision&&window.innerWidth<=620,mobileMerge=g.kind==='merge_2048'&&window.innerWidth<=620,w=mobileSnake||mobileMerge?540:900,h=mobileSnake?620:540;if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}c=canvas.getContext('2d');c.clearRect(0,0,900,540);c.textAlign='left';c.textBaseline='alphabetic';if(g.kind==='jump_jump')jump(g,o);else if(g.kind==='snake_navigation')snake(g,o);else if(g.kind==='tetris_placement')tetris(g,o);else if(g.kind==='merge_2048')merge2048(g,o);else if(g.kind==='sokoban_puzzle')sokoban(g,o);else if(g.kind==='robot_pick_cola')robot(g,o)}
 return {draw,rotations,landing};
})();

// Shared transitions paint the same recorded before/after states in play and replay.
window.JevSceneTransition=(()=>{
 function tileMotion(before,action){
  const movements=[];
  for(let line=0;line<4;line++){
   const positions=Array.from({length:4},(_,i)=>action==='right'?[3-i,line]:action==='up'?[line,i]:action==='down'?[line,3-i]:[i,line]);
   const cells=positions.map(([x,y])=>({x,y,value:before.board[y][x]})).filter(p=>p.value);
   let destination=0;
   for(let i=0;i<cells.length;i++){
    const [tx,ty]=positions[destination++];movements.push({...cells[i],tx,ty});
    if(cells[i+1]?.value===cells[i].value)movements.push({...cells[++i],tx,ty});
   }
  }
  return movements;
 }
 function draw(before,after,action,progress){
  if(progress>=1){PlayDraw.draw(after);return;}
  if(after.kind==='tetris_placement'){
   const [rot,col]=String(action).split(':').map(Number);
   PlayDraw.draw(before,{rot:rot||0,col:Number.isFinite(col)?col:4,dropProgress:Math.min(1,progress/.86)});
  }else if(after.kind==='merge_2048'){
   if(progress<.85)PlayDraw.draw(before,{tileMotion:tileMotion(before,action),progress:Math.min(1,progress/.85)});
   else PlayDraw.draw(after);
  }else PlayDraw.draw(after,{before,progress,action});
 }
 function animate(before,after,action){
  return new Promise(resolve=>{let start;function tick(now){start??=now;const p=Math.min(1,(now-start)/300);draw(before,after,action,p);if(p<1)requestAnimationFrame(tick);else resolve();}requestAnimationFrame(tick);});
 }
 return {draw,animate};
})();
window.JevNativeSceneDraw=(state,options)=>PlayDraw.draw(state,options);

// Each replay owns its document and rendering state. No gameplay API is loaded.
if(!window.__JEV_REPLAY_FRAME__)window.JevReplayRenderer=(()=>{
 const base=new URL('../',document.currentScript.src),version='tetris-realtime-20261016-v1';
 const asset=path=>new URL(path+'?v='+version,base).href;
 const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const boardKinds=new Set(['othello_6x6','othello_8x8','gomoku_19x19','hex_7x7','dots_and_boxes_3x3']);
 const clone=value=>value==null?value:structuredClone(value);
 const mix=(a,b,p)=>Number.isFinite(a)&&Number.isFinite(b)?a+(b-a)*p:b;
 function interpolate(a,b,p){
  if(!a||p>=1)return b;
  const out={...a};
  for(const key of ['z','x','speed','lateral_velocity','elapsed','frame'])out[key]=mix(a[key],b[key],p);
  if(a.player&&!Array.isArray(a.player)&&b.player){out.player={...a.player};for(const key of ['x','y','vx','vy'])out.player[key]=mix(a.player[key],b.player[key],p);out.player.facing=b.player.facing;}
  function entities(left,right){
   if(!Array.isArray(left)||!Array.isArray(right)||left.length!==right.length)return left;
   return left.map((item,index)=>{const next=right[index];if(!next||item.kind!==next.kind||Math.hypot((next.x||0)-(item.x||0),(next.y||0)-(item.y||0))>64)return item;return {...item,x:mix(item.x,next.x,p),y:mix(item.y,next.y,p)};});
  }
  if(a.enemies&&b.enemies)out.enemies=entities(a.enemies,b.enemies);
  if(a.replay_scene&&b.replay_scene)out.replay_scene={...a.replay_scene,enemies:entities(a.replay_scene.enemies,b.replay_scene.enemies)};
  // Discrete contacts, health, maps, cards and outcomes change at their recorded frame.
  return out;
 }
 async function mount(host,{kind,lang='en'}={}){
  const iframe=document.createElement('iframe'),world=kind==='mario_platformer'||kind==='terraria_survival',board=boardKinds.has(kind);
  iframe.className='jev-native-replay';iframe.title=lang==='zh'?'游戏动画回放':'Animated game replay';iframe.setAttribute('sandbox','allow-scripts allow-same-origin');
  iframe.style.cssText='display:block;width:100%;border:0;background:#f4f6ed;border-radius:12px;';
  iframe.style.aspectRatio=board?'760 / 700':kind==='mario_platformer'?'900 / 448':'900 / 540';
  iframe.style.minHeight=board?'0':'210px';if(board){iframe.style.maxWidth='calc(58vh * 760 / 700)';iframe.style.margin='0 auto';}
  host.replaceChildren(iframe);
  const ready=new Promise((resolve,reject)=>{iframe.onload=resolve;iframe.onerror=()=>reject(Error('Replay renderer could not load'));});
  if(world)iframe.src=asset('playground/'+(kind==='mario_platformer'?'mario.html':'terraria.html'))+'&replay=1';
  else{
   const bootstrap=`window.__JEV_REPLAY_FRAME__=true;window.showcaseBusy=true;window.esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));window.JevI18n={lang:${JSON.stringify(lang)},t(en,zh){return this.lang==='zh'?(zh??en):en},onChange(){},register(){}};window.api=()=>Promise.reject(Error('Read-only replay'));`;
   iframe.srcdoc='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+['playground/playground.css','playground/agent-games.css','playground/pixel-theme.css','playground/typography.css'].map(path=>'<link rel="stylesheet" href="'+escape(asset(path))+'">').join('')+'<style>html,body{margin:0;padding:0;width:100%;min-width:0;background:#f4f6ed;overflow:hidden}*{box-sizing:border-box}canvas{display:block;width:100%;height:auto;margin:0;border:0;pointer-events:none}#agentGameStage{padding:12px;pointer-events:none;min-height:0}.hidden,[hidden]{display:none!important}.agent-turn{font-size:14px}button{pointer-events:none}</style></head><body><canvas id="showcaseCanvas" width="900" height="540"></canvas><canvas id="board" width="760" height="700" hidden></canvas><div id="agentGameStage" class="hidden"></div><div id="agentRules" hidden></div><div id="showcaseActions" hidden></div><div id="keyboardHint" hidden></div><script>'+bootstrap+'</script>'+['playground/renderers.js','playground/tetris-renderer.js','playground/social-games.js','playground/agent-games.js','playground/racing.js'].map(path=>'<script src="'+escape(asset(path))+'"></script>').join('')+'</body></html>';
  }
  await ready;
  const win=iframe.contentWindow,doc=iframe.contentDocument;
  if(world?typeof (kind==='mario_platformer'?win.JevMario:win.JevTerramai)?.renderReplay!=='function':typeof win.JevNativeSceneDraw!=='function')throw Error('Native replay renderer is unavailable');
  let raf=0,settle=null,destroyed=false,current=null,last=null,epoch=0;
  if(world){
   const style=doc.createElement('style');style.textContent=kind==='mario_platformer'?'html,body,#wrap{margin:0!important;padding:0!important;width:100%!important;max-width:none!important;background:#dceee4}#wrap>:not(canvas){display:none!important}#game{display:block!important;width:100%!important;height:auto!important;border:0!important;border-radius:0!important;pointer-events:none}':'html,body,#tw-wrap{margin:0!important;padding:0!important;width:100%!important;max-width:none!important;background:#dceee4}#tw-wrap>:not(canvas){display:none!important}#tw-canvas{display:block!important;width:100%!important;height:auto!important;border:0!important;border-radius:0!important;pointer-events:none}';doc.head.append(style);
   const canvas=doc.getElementById(kind==='mario_platformer'?'game':'tw-canvas');
   canvas.width=kind==='mario_platformer'?900:352;canvas.height=kind==='mario_platformer'?448:240;
   iframe.style.aspectRatio=canvas.width+' / '+canvas.height;
  }
  const canvas=doc.getElementById(board?'board':world?(kind==='mario_platformer'?'game':'tw-canvas'):'showcaseCanvas');
  if(board){canvas.hidden=false;doc.getElementById('showcaseCanvas').hidden=true;}
  function size(){if(!world&&win.AgentGames?.has(kind)){iframe.style.aspectRatio='auto';iframe.style.height=Math.max(260,doc.getElementById('agentGameStage').scrollHeight+24)+'px';}}
  function paint(state,options={}){
   if(!state||destroyed)return;if(typeof state!=='object')throw Error('No complete game snapshot for this frame');state={...state,kind:state.kind||kind};current=state;
   if(world){(kind==='mario_platformer'?win.JevMario:win.JevTerramai)?.renderReplay(state);return;}
   if(board){win.JevBoardDraw({...state,game:state.game||kind,legal:state.legal||[]},canvas);return;}
   if(win.AgentGames?.has(kind)){win.AgentGames.render({...state,handoff:false},{});size();return;}
   if(kind==='racing_sprint'){win.JevRacing.draw(state);return;}
   win.JevNativeSceneDraw(state,options);if(kind==='tetris_placement')iframe.style.aspectRatio=canvas.width+' / '+canvas.height;
  }
  function stop(){epoch++;if(raf)cancelAnimationFrame(raf);raf=0;if(!world&&win.JevCardTable?.stop)win.JevCardTable.stop();for(const animation of doc.getAnimations())animation.pause();if(settle){const done=settle;settle=null;done();}}
  function update(payload){
   if(destroyed)return Promise.resolve();
   if(payload.reason==='locale'){if(win.JevI18n)win.JevI18n.lang=payload.lang;paint(current||payload.state);return Promise.resolve();}
   stop();if(win.JevI18n)win.JevI18n.lang=payload.lang||lang;
   const state=clone(payload.state),before=clone(payload.reason==='resume'?current:payload.previousState),step=payload.step||{};last=payload;
   if(!state){return Promise.resolve();}
   if(!payload.animate||!before){paint(state);for(const animation of doc.getAnimations())animation.finish();return Promise.resolve();}
   const duration=Math.max(180,payload.durationMs||700),token=epoch;
   if(!world&&win.JevCardTable?.supports(kind)){
    paint(before);
    return new Promise((resolve,reject)=>{settle=resolve;win.JevCardTable.animate(before,state).then(()=>{if(token!==epoch)return;current=state;settle=null;resolve();}).catch(error=>{if(token===epoch){settle=null;reject(error);}});});
   }
   if(!world&&win.AgentGames?.has(kind)){
    paint(before);paint(state);const stage=doc.getElementById('agentGameStage');
    const targets=stage.querySelectorAll('.die,.playing-card,.auction-public-play,.bid-display');
    const animations=[...(targets.length?targets:[stage])].map(el=>el.animate([{opacity:.4,transform:'translateY(-8px) scale(.96)'},{opacity:1,transform:'none'}],{duration:Math.min(500,duration),easing:'ease-out'}));
    return new Promise(resolve=>{settle=resolve;Promise.all(animations.map(a=>a.finished.catch(()=>{}))).then(()=>{if(token===epoch){settle=null;resolve();}});});
   }
   let recorded=step.execution_frames||state.execution_frames;
   if(!Array.isArray(recorded)||!recorded.length)recorded=state.execution_trace?.frames;
   if(Array.isArray(recorded)&&recorded.length){const base=step.execution_frames_delta?(step.arrival_state||step.before_state||before):state;recorded=recorded.map(s=>({...base,...s}));if(!recorded[0].kind)recorded[0].kind=kind;}
   let oldImage=null;
   const transition=['jump_jump','snake_navigation','sokoban_puzzle','tetris_placement','merge_2048'].includes(kind);
   if(!world&&!transition&&kind!=='racing_sprint'){paint(before);oldImage=doc.createElement('canvas');oldImage.width=canvas.width;oldImage.height=canvas.height;oldImage.getContext('2d').drawImage(canvas,0,0);}
   let started=null;
   return new Promise((resolve,reject)=>{settle=resolve;function tick(now){try{
    if(token!==epoch||destroyed)return;started??=now;const p=Math.min(1,(now-started)/duration),smooth=p*p*(3-2*p);
    if(recorded?.length>1){
     let part=p*(recorded.length-1),i=Math.min(recorded.length-2,Math.floor(part)),q=part-i;if(kind==='tetris_placement'&&win.JevTetrisRenderer?.supports(state)){const first=Number(recorded[0].elapsed),last=Number(recorded.at(-1).elapsed),time=first+(last-first)*p;i=0;while(i<recorded.length-2&&Number(recorded[i+1].elapsed)<=time)i++;const span=Number(recorded[i+1].elapsed)-Number(recorded[i].elapsed);q=span>0?Math.min(1,Math.max(0,(time-Number(recorded[i].elapsed))/span)):1;}const a=recorded[i],b=recorded[i+1];
     if(kind==='sokoban_puzzle'||kind==='snake_navigation'||kind==='tetris_placement'&&win.JevTetrisRenderer?.supports(state))paint(b,{before:a,progress:q});else paint(interpolate(a,b,q));
    }else if(world||kind==='racing_sprint')paint(interpolate(before,state,p));
    else if(kind==='tetris_placement'||kind==='merge_2048'){win.JevSceneTransition.draw(before,state,payload.action,smooth);current=p>=1?state:before;}
    else if(transition)paint(state,{before,progress:smooth,action:payload.action});
    else{paint(state);const ctx=canvas.getContext('2d');ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1-smooth;ctx.drawImage(oldImage,0,0,canvas.width,canvas.height);ctx.restore();}
    if(p<1)raf=requestAnimationFrame(tick);else{raf=0;paint(state);settle=null;resolve();}
   }catch(error){raf=0;settle=null;reject(error);}}raf=requestAnimationFrame(tick);});
  }
  // Deterministic sampling for complete timeline exports, using the live renderers.
  function sample({before,after,action},progress){
   stop();const p=Math.max(0,Math.min(1,progress));
   if(p===0){paint(before);return;}if(p===1){paint(after);return;}
   if(world){paint(interpolate(before,after,p));return;}
   if(kind==='merge_2048'){win.JevSceneTransition.draw(before,after,action,p);return;}
   if(['jump_jump','snake_navigation','sokoban_puzzle','tetris_placement'].includes(kind)){
    paint(after,{before,progress:p,action});return;
   }
   paint(p<.5?before:after);
  }
  return {update,sample,stop,destroy(){stop();destroyed=true;iframe.remove();},get frame(){return iframe;}};
 }
 return {mount};
})();

/* Shared production board painter, also used by isolated replay. */
window.JevBoardDraw=function(g,canvas){if(!g)return [];const ctx=canvas.getContext('2d'),n=g.n,kind=g.game;let points=[];ctx.clearRect(0,0,760,700);points=[];ctx.font='15px '+getComputedStyle(document.body).fontFamily;ctx.textAlign='center';ctx.textBaseline='middle';const stone=(x,y,side,r)=>{ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=side==='X'?'#253141':'#fff';ctx.fill();ctx.strokeStyle=side==='X'?'#152031':'#a3adb7';ctx.lineWidth=1.5;ctx.stroke()};
if(canvas.id==='board'&&window.JevParticipants?.isDuel()&&JevParticipants.isBoard()){
 ctx.save();for(let i=0;i<2;i++){const active=JevParticipants.activeSeat(i);ctx.font=(active?'700 ':'500 ')+'13px '+getComputedStyle(document.body).fontFamily;ctx.fillStyle=active?'#216c4e':'#61776a';ctx.fillText(JevParticipants.seatMarker(i,i?'O':'X'),i?555:205,12,330)}ctx.restore();
 canvas.setAttribute('aria-label',[0,1].map(i=>JevParticipants.seatMarker(i,i?'O':'X')).join('; '));
}
if(kind==='dots_and_boxes_3x3'){const d=150,ox=155,oy=115;ctx.fillStyle='#f5f8fb';ctx.fillRect(90,50,580,580);for(let r=1;r<=3;r++)for(let c=1;c<=3;c++){const owner=g.boxes[`${r},${c}`];if(owner){ctx.fillStyle=owner==='X'?'#dbe8fc':'#e3efea';ctx.fillRect(ox+(c-1)*d+5,oy+(r-1)*d+5,d-10,d-10);ctx.fillStyle='#5e7290';ctx.fillText(owner,ox+(c-.5)*d,oy+(r-.5)*d)}}for(const t of ['H','V'])for(let r=1;r<=(t==='H'?4:3);r++)for(let c=1;c<=(t==='H'?3:4);c++){const a=`${t}${r},${c}`,x=ox+(c-1)*d,y=oy+(r-1)*d,x2=x+(t==='H'?d:0),y2=y+(t==='V'?d:0);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x2,y2);ctx.strokeStyle=g.edges[a]?(g.edges[a]==='O'?'#77a993':'#426aa4'):'#dbe1e8';ctx.lineWidth=g.edges[a]?8:5;ctx.stroke();points.push({x:(x+x2)/2,y:(y+y2)/2,action:a,radius:60})}for(let r=0;r<4;r++)for(let c=0;c<4;c++){ctx.fillStyle='#33465e';ctx.beginPath();ctx.arc(ox+c*d,oy+r*d,7,0,Math.PI*2);ctx.fill()}return points}
if(kind==='hex_7x7'){const d=66,ox=78,oy=130;for(let r=0;r<n;r++)for(let c=0;c<n;c++){const x=ox+(c+r*.5)*d,y=oy+r*d*.866;ctx.beginPath();for(let k=0;k<6;k++){const a=(60*k+30)*Math.PI/180;const xx=x+36*Math.cos(a),yy=y+36*Math.sin(a);k?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy)}ctx.closePath();ctx.fillStyle=g.board[r][c]==='X'?'#33465e':g.board[r][c]==='O'?'#d6e5ff':'#fff';ctx.fill();ctx.strokeStyle='#becce0';ctx.lineWidth=2;ctx.stroke();ctx.fillStyle=g.board[r][c]==='X'?'#fff':'#7c8da2';ctx.fillText(String.fromCharCode(97+c)+(n-r),x,y);points.push({x,y,action:String.fromCharCode(97+c)+(n-r),radius:34})}ctx.fillStyle='#547299';ctx.fillText((window.JevPlayText?.ui||String)("X: left–right  ·  O: top–bottom"),380,630);return points}
const rows=g.board.length,step=Math.min(600/n,580/rows),w=n*step,h=rows*step,ox=(760-w)/2+step/2,oy=(700-h)/2+step/2;ctx.fillStyle=kind==='gomoku_19x19'?'#f0dfbe':kind.startsWith('othello')?'#dfeee5':'#e8eff8';ctx.fillRect(ox-step*.6,oy-step*.6,w+step*.2,h+step*.2);for(let r=0;r<rows;r++)for(let c=0;c<n;c++){const x=ox+c*step,y=oy+r*step;ctx.strokeStyle=kind==='gomoku_19x19'?'#c5ac82':'#c1cfd6';ctx.lineWidth=1;if(kind==='gomoku_19x19'){ctx.beginPath();ctx.moveTo(ox,y);ctx.lineTo(ox+(n-1)*step,y);ctx.moveTo(x,oy);ctx.lineTo(x,oy+(rows-1)*step);ctx.stroke()}else{ctx.strokeRect(x-step/2,y-step/2,step,step)}let action=kind==='tic_tac_toe'?String(r*3+c):kind==='connect_four'?'C'+(c+1):kind==='gomoku_19x19'?`${c+1},${n-r}`:String.fromCharCode(97+c)+(n-r);points.push({x,y,action,radius:step*.48});const side=g.board[r][c];if(side!=='.')stone(x,y,side,step*.36);else if(g.legal.includes(action)&&kind.startsWith('othello')){ctx.beginPath();ctx.arc(x,y,step*.055,0,Math.PI*2);ctx.fillStyle='#7aa891';ctx.fill()}}ctx.fillStyle='#81909e';ctx.font=`${Math.max(10,Math.min(14,step*.23))}px ${getComputedStyle(document.body).fontFamily}`;for(let c=0;c<n;c++)ctx.fillText(kind==='connect_four'?'C'+(c+1):kind==='gomoku_19x19'?c+1:String.fromCharCode(97+c),ox+c*step,Math.max(20,oy-step*.8));for(let r=0;r<rows;r++)ctx.fillText(n-r,ox-step*.82,oy+r*step);return points;};

window.dispatchEvent(new Event('jev-board-renderer-ready'));
