# Showcase 来源与复现

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
