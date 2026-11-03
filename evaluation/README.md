# 发布评测

Piccolo 在四项决策评测上的成绩如下。分数、指标与来源文件记录在 [results.json](results.json)。

| 模型 | HarnessJevBench Hard ↑ | DataJevBench ↑ | JevBench Public ↑ | Decision Index Public ↑ |
| --- | ---: | ---: | ---: | ---: |
| Piccolo-27B | 84.41% | 82.60% | 92.21% | 68.59 |
| Piccolo-9B | 68.81% | 69.40% | 89.61% | 60.86 |
| Piccolo-4B | 62.03% | 70.60% | 87.01% | 58.00 |

## 评测与来源

- [JevBench Public](../arena/leaderboard/jevbench.json)：决策准确率，27B 为 213/231。
- [Decision Index](../arena/leaderboard/decisionindex.json)：100 分制综合指标。
- [HarnessJevBench](../arena/leaderboard/harnessjevbench.json)：Hard 决策准确率，并记录 Soft 问题的分布距离 TV。
- [DataJevBench](../arena/leaderboard/datajevbench.json)：500 道题，27B 答对 413 题，同时记录 Brier 与 ECE。

[在线榜单](https://decisionplayground.agentscope.io/) · [HarnessJevBench](https://github.com/agentscope-ai/HarnessJevBench) · [DataJevBench](https://github.com/datajuicer/DataJevBench)

## 复现与本地测量

评测命令见 [HarnessJevBench 复现说明](https://github.com/agentscope-ai/HarnessJevBench/blob/main/skills/harnessjevbench-eval/references/reproducibility.md) 和 [DataJevBench 复现说明](https://github.com/datajuicer/DataJevBench/blob/main/docs/reproducibility.md)。

BF16、Q8_0 与 Q4_K_M 的转换和数值对照记录在各自模型卡。Q4_K_M 的合成回归包含每个尺寸 265 个请求、556 个判断，覆盖工具审核、上下文保留和评分。macOS 延迟与上下文压缩测量见 [QwenPaw 本地测量](../docs/QWENPAW.md#macos-本地延迟)。
