# 新增七个游戏的前端与 RL 接入

2026 年 10 月 19 日合入用户选定的七个游戏。游戏列表、专用页面、共享六方法引擎、双方席位控制、RL 决策 ticket、终局奖励与精确回放使用同一套规则。本次只接入这七项，既有游戏与其他并行改动保留。公开目录以 `/api/v1/games` 为准。

## 游戏与规则

| 游戏 ID | 名称 | 原生规则库 | 席位 | 决策上限 | 规则说明 |
| --- | --- | --- | ---: | ---: | --- |
| checkers | 西洋跳棋 | OpenSpiel 2.0.2 | 2 | 300 | 标准 8×8 开局，原生强制吃子和升王 |
| go | 围棋 | OpenSpiel 2.0.2 | 2 | 360 | 9×9、白贴 7.5；连续停着后原生计分 |
| xiangqi | 中国象棋 | OpenSpiel 2.0.2 | 2 | 400 | 标准 9×10 开局和原生将军、终局规则 |
| guess_the_number | 猜数字 | TextArena 0.7.3 | 1 | 10 | v0 的 1–20 整数范围，仅公开更大或更小提示 |
| minesweeper | 扫雷 | TextArena 0.7.3 | 1 | 100 | v0 的 8×8、10 雷；首击后按原生安全区布雷 |
| sudoku | 数独 | TextArena 0.7.3 | 1 | 240 | v0 的 clues=60、唯一解生成；先选空格，再选数字 |
| uno | UNO纸牌 | RLCard 1.2.0 | 2 | 300 | 双人原生牌堆、出牌、抽牌、变色和结算 |

上限是共享引擎决策预算；数独的选格和填数分别计入预算。原生游戏的终止条件和原生预算仍生效。上游来自依赖包，未把 GitHub 源码快照的 commit 冒充为当前 wheel 构建身份；每条记录登记实际包版本。

西洋跳棋、围棋、中国象棋保留标准开局；不同 seed 不会随机改摆棋子。种子用于规则对手和对局复现。其余游戏按原生规则用 seed 控制目标、盘面或洗牌；种子不进入模型可见 state。

## 前端和隐私

新增游戏进入 Featured，并分别归入 Board、Table、Arcade & puzzles。棋盘、数字、手牌和公开历史由服务端 public 状态绘制；棋盘点击和动作按钮提交的都是同一组原生合法动作。

中国象棋使用红黑圆形棋子和木色交叉线棋盘，包含楚河汉界、九宫斜线及炮兵位标记。点击己方可走棋子后显示选子圆环和合法落点；棋子位置与服务端行列一一对应，桌面和手机共用原生动作 ID。

UNO 在人工换位时显示交接遮罩。换位前不返回下一位玩家的私有观测，也不保留上一位的输入面板。手动交接使用现有 `/api/showcases/reveal`；版本化会话 API 使用：

```json
{"revision": 1, "reveal": true}
```

将上述请求发送到 `POST /api/v1/sessions/{session_id}/steps`。交接请求不能同时包含动作、模型调用或 ticks。规则对手模式由引擎自动执行对方的合法动作，回到当前玩家后再返回观测。

规则对手是可复现的合法动作随机基线 `seeded_legal_random_v1`，没有使用隐藏手牌、未揭晓动作、雷图或数独答案选动作。它不是棋力评测结论。

## 共享引擎

`blink_arena.engine.get_engine(kind)` 返回默认已注册的 EngineSpec，不需要设置插件环境变量。实现位于 `jev_selected_games.py`，协议仍是 `reset / legal_actions / observe / step / public / outcome`。

数独数字候选只根据公开行、列、宫约束生成；原生引擎检查实际填数。扫雷列出所有未揭开格子，不能通过雷图移除危险选项。UNO 在进入原生 step 前拒绝非法 ID，避免 RLCard 自动随机替换非法动作。所有候选保留确定次序，并限制在现有单 token Choice 容量内。

持久状态是 JSON 动作日志，原生状态只缓存在进程内。日志可从 seed 迭代恢复，不依赖缓存或递归深度；缓存上限为 128 个状态。TextArena 的随机状态在锁内隔离并在调用后恢复，避免并发游戏互相影响。

## RL 接入

7 项均声明 `rl_runner=jev_selected_games_rl:play` 和 `rl_verify=jev_selected_games_rl:verify`。`/api/v1/rollouts`、便携 Python callback runner 和 CuES Sampler 使用同一实现，不经过网页点击。

单人模式为 `environment`。双人模式支持 `rule_engine` 与外部配置的 `qwen3.8-max` 对手；`side=0/1` 决定受控席位。只有受控席位的真实决策进入学生 trace；单一合法动作记为 forced 执行，不生成策略请求。模型对手需要调用方显式提供对手 callback，本次未调用真实模型。

终局奖励复用既有合同：胜 +1、负 −1、和 0；预算耗尽 −1。没有给猜得接近、揭开格子、选中空格等操作新增过程奖励。原生部分得分不冒充完整胜利。

回放逐项核对初始状态、行动席位、公开观测、候选、原生动作、受控 trace、规则对手选择与最终状态。修改 trace 会导致校验失败。数独选格阶段仍是真实模型 Choice，未使用答案替模型选择空格或数字。

`config/selected-games-rewards.json` 是这七项的显式奖励配置。CuES 的 `jev_gameplay_rl_v3.py` 新增 `--reward-config`，仅采样这七个原生环境时不要求前端资产服务。现有训练覆盖、评测隔离、原模型保持和奖励准入检查仍保留。

另备 CuES 的 `docs/assets/selected-games/rl-plan-expanded.json` 和 `task-weights-expanded.json`：按当前公开注册表冻结正式采样范围，包含新增7项和并行启用的国际象棋，保留原有质量门槛与重点游戏配额。通过 `JEV_RL_PLAN_PATH` 和 `--weights` 显式选择，未改写已有运行目录或默认现场计划；本次没有启动训练。

## 验证

本机完整检查覆盖：

- BlinkArena 全量 pytest，包括七项原生协议、隐私、种子与并发、HTTP 会话、双方 RL 席位、奖励结算、篡改拒绝及 240 步冷启动回放。
- 当前 HTML/JS 的 Chromium 检查：7 项可发现、专用渲染、人工操作、fixture 模型操作；私有游戏换位与分类导航同时检查。
- 现有 Qwen tokenizer 与 SFT/RL formatter 的单 token Choice：7 游戏及数独两个阶段均通过。
- CuES 注册表、奖励、RL 控制入口、前端集成与共享 episode runner 的回归。

验证使用 fixture 策略，没有真实模型成绩。线上测试按前端下线约定未执行；没有发布或重启公网／DSW 前端，也没有运行采样任务、优化器或 GPU 训练。

安装新增依赖后可复验：

```bash
python -m pip install -e '.[test]'
python -m pytest
python tests/selected_games_browser.py
```

浏览器检查需要已有 Chromium；输出目录可通过 `JEV_SELECTED_TEST_OUT` 设置。检查汇总和截图保存在外层 `data/jev-selected-games-integration-20261019/`。

2026-10-19 界面修订：按用户要求移除重复石头剪刀布的当前注册、入口和 RL 配置；历史采集与运行产物保留。UNO 使用彩色牌面及原生变色候选，围棋在交叉点落子；大富翁、德扑、斗地主的 Canvas 按屏幕像素密度绘制，保留逻辑坐标点击。修订验证见外层 `data/jev-selected-games-ui-20261019-v2/`。
