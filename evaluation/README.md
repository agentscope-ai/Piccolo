# 发布评测

以下成绩对应当前在 Hugging Face 发布的完整 Piccolo 权重，发布方已确认对应关系。固定 checkpoint revision、原始模型 ID、benchmark 版本、数值和来源文件 SHA 记录在 [results.json](results.json)；本轮文档整理没有重新运行这些 benchmark。

| 模型 | HarnessJevBench Hard ↑ | DataJevBench ↑ | JevBench Public ↑ | Decision Index Public ↑ |
| --- | ---: | ---: | ---: | ---: |
| Piccolo-27B | 82.03% | 82.40% | 92.21% | 68.29 |
| Piccolo-9B | 69.49% | 68.80% | 89.61% | 60.63 |
| Piccolo-4B | 65.59% | 69.60% | 87.01% | 57.31 |

## 口径与来源

- [JevBench Public 1.2](../arena/leaderboard/jevbench.json)：准确率，当前各模型分母见 `accuracy_n`；27B 为 213/231。
- [Decision Index Public 0.3](../arena/leaderboard/decisionindex.json)：100 分制综合指标，不是百分比准确率；不要混用 `raw_index` 与最终 `score`。
- [HarnessJevBench V0.5](../arena/leaderboard/harnessjevbench.json)：表格使用 Hard 准确率；27B 的 `accuracy_n=295`。全体任务、Hard 问题、有效作答与 Soft 分布任务的分母不同，`soft_tv` 单独记录。
- [DataJevBench V0.5](../arena/leaderboard/datajevbench.json)：500 道题，27B 答对 412 题，另记录 Brier 与 ECE。

[在线榜单](https://decisionplayground.agentscope.io/) · [HarnessJevBench](https://github.com/agentscope-ai/HarnessJevBench) · [DataJevBench](https://github.com/datajuicer/DataJevBench)。展示用历史轨迹保留自身 checkpoint 身份，见 [Showcase 来源](../docs/SHOWCASE.md)，不能由精选轨迹计算总体成功率。

## 转换和量化

三种 BF16 GGUF 经过完整 checkpoint 的小样本候选概率对照；Q8_0、Q4_K_M 的模型卡记录各自证据。Q4 扩大数值回归使用每个尺寸 **265 请求、556 判断**，覆盖自动审核、上下文保留和评分，并比较标准量化与敏感张量保护方案，最终发布标准 Q4_K_M。

这些合成回归用于测量数值误差和决策变化，不等于独立任务基准、风险校准或安全认证。上表不声称量化版本具有相同成绩。

**TODO：公开完整 benchmark 复现命令与逐题报告，补齐硬件、运行设置、延迟、内存、审核误拦／漏拦和实际压缩质量评测。**
