# Showcase 来源与复现

README 与 Blog 集中展示八个游戏，按四行两列排列：马里奥、贪吃蛇、2048、推箱子、俄罗斯方块、跳一跳、Hex 与点格棋。动图外不另加游戏名称或图例，画面内的名称保留。黑白棋与五子棋已从正文合集移除，历史归档和复现资料继续保留。以下均为历史实验，不代表待发布 Piccolo 模型的成绩。

导出的动图去掉 `COMPLETED GAME`、序号箭头和游戏切换栏，保留当前游戏、状态、动作与右侧候选框。网页播放器继续保留交互导航。Blog 不再逐个介绍游戏，来源细节统一收录在本文。

## 当前动图：完整时间线与候选动作

### 2026-10-29：补齐真实候选概率

八个游戏右侧新增概率条、百分比与最终选项高亮。已从原始记录恢复全部 **195 次模型判断**的候选概率，并按动作 ID 对齐；另有 14 次 Tetris 自动执行和 1 次点格棋唯一合法动作，不填造模型概率。自动执行时可继续查看上一轮判断，并明确标记没有新请求。

候选较多时默认展示概率最高的六项并确保最终选项可见，其余项合计概率单独标注；网页中可展开全部候选。动图没有额外游戏图例，保留全部 210 次转换和原始动画。

- [公开概率回执](../arena/web/showcase/probabilities/)仅包含候选概率、选择方式与来源摘要；不包含模型服务地址、凭据或私有运行路径。
- 马里奥与俄罗斯方块使用对应原始请求的返回分布，逐条核对请求状态和动作。马里奥先复用原始无损输入压缩，再核对状态。
- 2048、推箱子、跳一跳、Hex 和点格棋沿用原评测流程保存的 `representative_sample_index`，展示支持最终动作的那次真实判断分布，页面标明它在三次判断中的位置；没有将三次分布平均后冒充一次输出。
- 贪吃蛇使用原始成功 rollout 的 `policy.old_probabilities`，按 `candidate_values` 对齐；它是含温度与探索的行为策略分布，采样参数保存在回执中，所选动作沿用实际采样结果。
- `scripts/export_showcase_probabilities.py --check` 检查每步动作、候选集合、概率和、来源摘要及覆盖范围；新导出时传入仓库外的 `--bundle` 和 `--snake-episode`。

### 完整播放

八张动图均使用 [统一播放器](../arena/web/showcase.html)：左侧游戏画面，右侧候选动作、选中项和执行反馈。按记录顺序播放全部 **210 次转换**，没有选择性跳步或截断；保留开局、等待、动作执行与终局。2× 播放并加入短阅读停顿，GIF 为 12 fps，不代表模型实际推理速度。

[完整时间线](../arena/web/showcase/full/) 记录每一步的三个阶段及连续执行帧。马里奥逐一重建第 0–2083 个物理帧，并严格核对所有原始观测、到达与执行边界；贪吃蛇保留全部 49 次身体移动；推箱子保留 14 次实际行走和推箱移动；俄罗斯方块展开全部时钟执行帧。棋盘与跳一跳保留每次原始决策及完整动作过渡。历史棋盘初态本身含已有棋子，播放从归档初态开始。

[渲染清单](../assets/showcase/render-manifest.json) 列出每个阶段对应的 GIF 帧号、完整连续的步骤索引、源文件摘要和时长。初态停留 0.5 秒，终态停留 2 秒。主文档仍为四行两列，不另加图注。

```bash
python scripts/export_mario_showcase.py --check
python scripts/export_snake_showcase.py --check
python scripts/export_full_showcase.py
BLINK_BROWSER_CHANNEL=chrome python scripts/render_showcase.py
```

可用 `--game snake` 等参数只重建指定游戏；没有 `--game` 时重建全部八项。生成目标包含 `assets/showcase/` 和 `assets/showcase/completed/`，沿用 README 的图片路径。

## 完整对局来源（2026-10-27）

从 JevArena 已提交的首页 Showcase 迁入播放器、样式与公开归档，对应来源提交 `5cc08eb`（完整回放数据引入于 `926adff`）。迁入不修改原工作区；数据文件逐字节保留，导出器适配本仓库的 Python 包路径，同时迁入 Tetris v1–v4 时钟版本的渲染兼容。历史 `oneshot.home-decision.v3` schema 和原模型 ID 保留。

| 游戏 | 历史 checkpoint | seed | 记录转换 / 模型调用 | 验证终局 |
| --- | --- | ---: | ---: | --- |
| 2048（目标 128） | SFT v9-a17 | 44 | 65 / 65 | 达到 128，积分 760 |
| 推箱子 | RL R9 / iter_0000031 | 43 | 4 / 4 | 两箱归位，14 步环境移动 |
| 6×6 黑白棋 | RL R6 / iter_0000019 | 47 | 22 / 9 | 模型执 O 获胜 |
| 俄罗斯方块 | GRPO N3 / iter_0000006 | 46 | 25 / 11 | 消除 4 行 |

合计 116 次转换、89 次模型调用。对手、唯一合法动作和不请求模型的执行区间分别标记。四局来自四个不同版本的精选通关记录；不能用于比较版本或推算总体成功率。

- [完整归档](../arena/web/playground/data/home-decision.json) 保留初态、每步候选与动作、后继状态、模型标识、时钟与终局。
- [独立播放器](../arena/web/completed-showcase.html) 与 Arena 的 Blog 页签复用 `home-demo.js`，支持中英文、进度、倍速、终局与键盘切换。Tetris 使用已有只读渲染器。
- 当前 GIF 使用上方统一时间线导出；旧版固定状态采样已替换。原独立播放器及来源归档仍保留。
- `assets/showcase/completed/render-manifest.json` 记录完整渲染清单中对应三张活动素材的源摘要、全部步骤、阶段与帧位置。PNG 保留各局终态。

离线验证不需要模型、训练目录或密钥：

```bash
cd arena
python3.12 scripts/export_home_decision.py --check
python3.12 -m unittest tests.test_home_decision -v
```

验证使用共享引擎检查候选、动作和后继状态，检查自然获胜与预算状态，并核对 Tetris 时钟与执行帧。测试还会主动篡改动作、方块和预算状态，确认伪造结果被拒绝。

生成新展示素材，在仓库根目录执行：

```bash
python -m pip install playwright
python -m playwright install chromium
# 系统需已安装 ffmpeg。
python scripts/render_completed_showcase.py
```

已安装桌面 Chrome 时，新展示渲染和浏览器检查可设置 `BLINK_BROWSER_CHANNEL=chrome`。

浏览器验收可针对本机运行的 Arena：

```bash
python arena/tests/browser_home_replays.py --url http://127.0.0.1:8080 --out var/completed-replay-check
```

针对静态预览服务，可在同一检查命令增加 `--standalone`；两种入口均检查桌面/手机、中英文、四局终态、实际拖动位置、重置、重力动画、键盘切换、滑动与减少动态效果偏好。

更换回放时，导出器支持仓库外私有选择文件，见 `arena/scripts/export_home_decision.py --help`；原评测数据、私有路径和选择文件不得提交。

## 归档展示（2026-10-26，2026-10-27 扩展）

展示使用随仓库提供的 `arena/leaderboard/arena-replays.json`，包含 132 场历史对局与 45 条复用 episode。原文件仅压缩 JSON 排版，解析后的内容不变；不重新执行策略、不补跑模型、不重新计分。

选取七条已有完整可视状态的轨迹。原录制类型均为 `reconstructed_verified`：归档状态由原导出器重建并验证；本次直接渲染这些已保存状态，不把它们描述为原始屏幕录像。

| 展示 | 归档位置 | 记录步骤数 | 原结果 |
| --- | --- | ---: | --- |
| 黑白棋 6×6 | `replays["00000"].streams[0]` | 28 | 白方 O 胜 |
| 2048 | `episodes["merge_2048-42-oneshot27b-game-rl-native-iter17"]` | 91 | 916 分；该归档任务目标为 128 方块 |
| 跳一跳 | `episodes["jump_jump-42-oneshot27b-game-rl-native-iter17"]` | 8 | 到达 8 个平台 |
| 俄罗斯方块 | `episodes["tetris_placement-42-oneshot27b-game-rl-native-iter17"]` | 14 | 堆顶失败、0 消行；步骤含环境帧，非 14 次模型判断 |
| 五子棋 19×19 | `replays["00004"].streams[0]` | 7 | X 胜 |
| Hex 7×7 | `replays["00006"].streams[0]` | 31 | X 胜 |
| 点格棋 3×3 | `replays["00008"].streams[0]` | 14 | O 胜 |

所有示例 seed 为 42，合计 193 条记录步骤。历史 ID 保留用于精确追溯；它们不是待发布 Piccolo 模型的 ID。这七条轨迹是展示样本，不能用于计算模型总体成功率。

## 马里奥完整回放（2026-10-27 新增）

[马里奥公开轨迹](../arena/web/showcase/traces/mario.json) 来自 `oneshot-sft-v9a17-20261022` 的 `mario_platformer-44-oneshot-sft-v9a17-presence-positive-retention`。保留原模型 ID、seed 44、`mario-map-v2-curriculum` 的 easy 地图与实时等待规则。

这局包含 12 次模型调用和执行事件，其中 11 个动作被执行，1 个回复因敌人方向改变被拒绝；终局进度 100%，自然通关，未耗尽预算。拒绝的动作保留原标记，并在播放器中保留动作拒绝标记。这是精选历史样例，不能用于比较模型优劣或推算总体成功率。

导出时用当前仓库的共享引擎重新播放初态、观测、动作到达与终态，严格模式 38 次状态比较通过，未使用浮点容差放宽。原始 episode 的 SHA-256 为 `655f4cf910b9b36f9b3e204b3f905a4a14456c0992c509cf7627aaf483c76088`。公开文件只保留游戏状态、候选、动作、执行结果和复现所需的时钟字段；模型服务配置、私有路径与原始响应均未导出。

在仓库根目录离线复核（Python 3.12、Node.js 与 Arena 依赖）：

```bash
python scripts/export_mario_showcase.py --check
```

更新该样例时可运行 `python scripts/export_mario_showcase.py --episode /path/to/private-episode.json --source-run public-run-id`，再执行下方通用导出与渲染命令。原始输入留在仓库外；公开轨迹自带离线校验所需的事件，无需访问原始输入或调用模型。

## 贪吃蛇通关回放（2026-10-27）

[贪吃蛇公开轨迹](../arena/web/showcase/traces/snake.json) 来自我们自己的 `jev-game-rl-online-20261016-v1` 历史运行，策略标识 `formal-sft310-20261016-v5/policy-0`，seed 为 `1194410000`。原始记录为 `jev.rollout.receipt.v1`，`policy_origin=student`、`on_policy=true`、`rule_takeover_count=0`；这是实际历史 rollout，并非外部基线，也不作为独立评测集成绩。

本局 **51 次决策、49 次身体移动，吃满 6 个苹果自然获胜**，游戏内时钟为 51.1 秒。它替换此前选错的 SFT v9-a17 / seed 43 失败轨迹。导出器用当前共享引擎逐一验证初态、每次观测/到达/执行后状态和终态，共 **155 处公开状态完全相等**；早期归档只存公开投影，缺少的请求间时长由相邻记录的游戏时钟精确恢复。没有重新调用模型或改变原动作。

公开文件保留原始 episode 的 SHA-256、候选、动作和时钟；服务配置、私有路径、原始模型响应不导出。导出器强制要求胜利、目标食物数、自然终局，失败样例不能再通过此入口生成。

```bash
python scripts/export_snake_showcase.py --check
python scripts/export_full_showcase.py --game snake
python scripts/render_showcase.py --game snake
```

更换来源时先用 `--episode /path/to/private-episode.json --source-run public-run-id` 导出经验证的公开轨迹；原始输入不提交。

## 数据和画面

- [轨迹清单](../arena/web/showcase/manifest.json) 记录源 run、源字段、参与者、录制类型、结果；马里奥与贪吃蛇使用条目内单独标明的来源与原始文件摘要。
- `arena/web/showcase/traces/` 包含七条从旧归档逐项复制的完整 stream（检查 JSON 往返相等），以及马里奥、贪吃蛇的公开状态与校验事件。九条归档轨迹共 256 次记录转换；正文只选用其中部分素材。
- [渲染清单](../assets/showcase/render-manifest.json) 记录每张动图的原状态位置、封面位置和帧时长。
- 当前八项 GIF 遍历全部决策与执行区间，具体覆盖位置见 v2 渲染清单；剩余旧素材仅作为历史归档，不在正文合集展示。
- 画面复用 `arena/web/playground/renderers.js` 的只读回放入口。不调用模型或重新选择动作。连续画面由保存的执行帧，或相同引擎按原始动作和时钟重建，边界状态必须与原始记录一致。

## 重现

从仓库根目录运行：

```bash
python -m pip install playwright
python -m playwright install chromium
# 系统需已安装 ffmpeg。
python scripts/export_showcase.py
python scripts/export_full_showcase.py
python scripts/render_showcase.py
```

脚本输出 `assets/showcase/*.gif` 和 `*.png`，并关闭临时本机资源服务。字体使用包内 Inter；浏览器环境可能影响抗锯齿，但状态和动作来源保持不变。
