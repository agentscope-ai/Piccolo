# Showcase 来源与复现

当前首页使用下文的完整对局展示；早期四条轨迹继续保留。两组均为历史实验，不代表待发布 Blink 模型的成绩。

## 完整对局展示（2026-10-27）

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
- GIF 仅按固定节奏采样状态，不能作为推理速度演示；独立播放器保留全部步骤及 Tetris 执行帧。
- `assets/showcase/completed/render-manifest.json` 记录归档 SHA-256、原转换位置、初态/终态及帧时长。PNG 保留各局终态。

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

## 早期展示（2026-10-26）

展示使用随仓库提供的 `arena/leaderboard/arena-replays.json`，包含 132 场历史对局与 45 条复用 episode。原文件仅压缩 JSON 排版，解析后的内容不变；不重新执行策略、不补跑模型、不重新计分。

选取四类已有完整可视状态的轨迹。原录制类型均为 `reconstructed_verified`：归档状态由原导出器重建并验证；本次直接渲染这些已保存状态，不把它们描述为原始屏幕录像。

| 展示 | 归档位置 | 记录步骤数 | 原结果 |
| --- | --- | ---: | --- |
| 黑白棋 6×6 | `replays["00000"].streams[0]` | 28 | 白方 O 胜 |
| 2048 | `episodes["merge_2048-42-oneshot27b-game-rl-native-iter17"]` | 91 | 916 分；该归档任务目标为 128 方块 |
| 跳一跳 | `episodes["jump_jump-42-oneshot27b-game-rl-native-iter17"]` | 8 | 到达 8 个平台 |
| 俄罗斯方块 | `episodes["tetris_placement-42-oneshot27b-game-rl-native-iter17"]` | 14 | 堆顶失败、0 消行；步骤含环境帧，非 14 次模型判断 |

所有示例 seed 为 42。历史 ID 保留用于精确追溯；它们不是待发布 Blink 模型的 ID。这四条轨迹是展示样本，不能用于计算模型总体成功率。

## 数据和画面

- [轨迹清单](../arena/web/showcase/manifest.json) 记录源 run、源字段、参与者、录制类型、结果。
- `arena/web/showcase/traces/` 保存从原归档逐项复制的完整 stream，导出时检查 JSON 往返相等。
- [渲染清单](../assets/showcase/render-manifest.json) 记录每张动图的原状态位置、封面位置和帧时长。
- 动图最多均匀选 24 帧，包含初态和终态，每帧 500 ms；交互播放器可以查看全部已保存决策状态。
- 画面复用 `arena/web/playground/renderers.js` 的只读回放入口。无模型调用、无自动选动作、无新游戏状态推进。

## 重现

从仓库根目录运行：

```bash
python -m pip install playwright
python -m playwright install chromium
# 系统需已安装 ffmpeg。
python scripts/export_showcase.py
python scripts/render_showcase.py
```

脚本输出 `assets/showcase/*.gif` 和 `*.png`，并关闭临时本机资源服务。字体使用包内 Inter；浏览器环境可能影响抗锯齿，但状态和动作来源保持不变。
