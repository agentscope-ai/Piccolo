# Piccolo：为智能体工作流提供快速决策

今天，我们发布 **Piccolo**，一个强大、快速、高性价比的决策模型系列，提供 **4B、9B、27B** 三个尺寸。Piccolo-27B 在 JevBench Public 上取得 **92.21%** 的准确率，在 Decision Index Public 上取得 **68.29** 分。

从智能体的工具审核与上下文筛选，到数据处理环境中的关键决策，再到游戏场景下的连续判断，Piccolo 理解当前状态、比较候选项，返回程序可以直接使用的结果与概率。我们通过交互展示、评测结果和本地接入，呈现它的能力与实际用法。

<p align="center">
  <a href="https://decisionplayground.agentscope.io/">🌐 Decision</a> ·
  <a href="https://github.com/agentscope-ai/Piccolo"><img src="../assets/brands/github.svg" width="20" height="20" alt=""> GitHub</a> ·
  <a href="https://huggingface.co/agentscope-ai/Piccolo-27B"><img src="../assets/brands/huggingface.svg" width="20" height="20" alt=""> Hugging Face</a> ·
  <a href="https://modelscope.cn/models/agentscope-ai/Piccolo-27B"><img src="../assets/brands/modelscope.png" width="20" height="20" alt=""> ModelScope · 即将发布</a>
</p>

**完整权重、BF16 GGUF、Q8_0 与 Q4_K_M 均已在 Hugging Face 发布**，采用 Apache-2.0。ModelScope 镜像尚未发布。[选择模型与下载](MODELS.md)。

## 01 看见连续决策

移动、跳跃、落子。模型根据当前局面选择动作，环境随之变化，下一次判断由此开始。下面八段完整回放展示决策如何连续推动一局游戏，右侧呈现记录中的候选概率与最终选择。

<table>
  <tr>
    <td width="50%" align="center"><img src="../assets/showcase/mario.gif" width="100%" alt="马里奥"></td>
    <td width="50%" align="center"><img src="../assets/showcase/snake.gif" width="100%" alt="贪吃蛇"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><img src="../assets/showcase/completed/merge-2048.gif" width="100%" alt="2048"></td>
    <td width="50%" align="center"><img src="../assets/showcase/completed/sokoban.gif" width="100%" alt="推箱子"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><img src="../assets/showcase/completed/tetris.gif" width="100%" alt="俄罗斯方块"></td>
    <td width="50%" align="center"><img src="../assets/showcase/jump-jump.gif" width="100%" alt="跳一跳"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><img src="../assets/showcase/hex.gif" width="100%" alt="Hex"></td>
    <td width="50%" align="center"><img src="../assets/showcase/dots-and-boxes.gif" width="100%" alt="点格棋"></td>
  </tr>
</table>

[前往 Decision 体验 →](https://decisionplayground.agentscope.io/)

回放保留原实验身份与终局，来源见 [Showcase 说明](SHOWCASE.md)。动画节奏用于展示，不代表推理延迟。

## 02 评测：三个尺寸，不同能力选择

我们观察了 Piccolo 在 JevBench Public、Decision Index Public、HarnessJevBench Hard 与 DataJevBench 上的决策表现：

| 模型 | HarnessJevBench Hard ↑ | DataJevBench ↑ | JevBench Public ↑ | Decision Index Public ↑ |
| --- | ---: | ---: | ---: | ---: |
| **Piccolo-27B** | **82.03%** | **82.40%** | **92.21%** | **68.29** |
| Piccolo-9B | 69.49% | 68.80% | 89.61% | 60.63 |
| Piccolo-4B | 65.59% | 69.60% | 87.01% | 57.31 |

这些成绩对应当前已发布的完整 Hugging Face 权重。Piccolo-27B 在四项评测中均取得三个尺寸中的最高分；9B 与 4B 在 JevBench Public 上分别达到 **89.61%** 与 **87.01%**，为资源有限的部署提供更多选择。量化后的候选概率存在变化，Q4/Q8 的数值回归与完整权重的 benchmark 成绩分开记录。[评测说明与来源](../evaluation/README.md) · [完整在线榜单](https://decisionplayground.agentscope.io/)。

## 03 训练方法：让反馈驱动下一轮数据

**Piccolo 的训练，将模型优化转化为“好数据”的迭代问题：定位当前模型需要的监督信号，组织相应素材，再用训练反馈更新下一轮数据配方。** Agent 据此选择数据、设计实验和比较结果，让每轮训练承接已有发现。

### 从多源材料到数据观测切片

训练材料从 **665 万条原始来源记录**中整理，覆盖分类、检索、数理推理、偏好判断与工具使用；同时从环境中的状态变化、行动选择和约束关系构造决策任务。不同来源统一为 **“状态、问题、候选项、目标分布”**：硬标签表达确定选择，软标签保留评分、偏好和判断分歧。

数据治理处理重复、答案依据、候选差异、位置偏置与训练评测重叠。基于 [Data-Juicer](https://github.com/datajuicer/data-juicer) 的切片能力，标签体系包含 **13 个标注维度、551 个预定义取值**，其中领域细分为 **334 类**，能力包含 **144 个标签**。领域、能力、难度和任务形式的交叉，让配方调整落到具体判断上。

**把逐题学习信号与语义标签关联，就能观察模型正在学会什么。** 对软标签，交叉熵可分解为目标分布熵和模型偏差：

$$
\mathrm{CE}(y,p)=H(y)+\mathrm{KL}(y\Vert p).
$$

下降较快的切片用于观察有效学习区间，低位稳定的切片进入回放与采样调整，高偏差或波动较大的切片进入答案复核、难度分析和定向补充。切片提供诊断线索，后续训练与评测检验调整是否有效。

### 在实验循环中选择数据与方法

基于 [Agentic Data Engineering](https://github.com/datajuicer/agentic-data-engineering)，人类给出目标、预算与数据使用范围，Agent 完成 **方案设计 → 构建与实验 → 结果反馈 → 诊断与更新**。DataJuicer-Panel 将数据版本、父模型、训练配置与实验结果连接起来，积累可查询的血缘与经验；[DataJuicer-Sandbox](https://github.com/datajuicer/data-juicer-sandbox) 承接数据处理、训练与评测的实际执行。

| 数据动作 | 具体处理 |
| --- | --- |
| 删除与降采样 | 清理错误、重复材料，调整充分学习的同质样本曝光 |
| 筛选与配比 | 按标签、语义相似度和学习状态组合背景、定向及回放数据 |
| 审计与改写 | 补齐条件、校正答案、重构干扰项并调整候选位置 |
| 定向合成 | 围绕能力缺口、任务机制与难度构造新题，再核验和模型试答 |

这些动作可以在一份方案中组合。Agent 对照总分和分项变化选择后续分支，保留有效配方与适用条件，让模型、数据和实验记录共同成为下一轮起点。

### 让训练和推理使用同一个决策接口

Piccolo 直接学习候选之间的判断：在回答位置读取候选分数，以候选分布交叉熵训练。推理使用源自 [FlexDM](https://github.com/1000luca/FlexDM) 的 `flex_twice` 输入布局，在 Qwen3.5 全注意力层采用**双向 prompt attention**，保留线性注意力层的原有计算；读取单 token 候选的 logits，以温度 1 归一化为概率。

模型不需要先生成解释，再让程序提取答案。结构化接口将候选概率转为选择、二元判断或有序评分，供 Harness 使用。输入模板、候选映射和注意力方式在训练与推理两端保持一致。[推理说明](../inference/README.md)。

## 04 QwenPaw：本地部署的决策模型

工具审核和上下文筛选会随着智能体执行反复发生。主对话模型负责理解任务、规划与生成内容，Piccolo 接收当前判断所需的背景和候选项，返回结构化结果与概率，Harness 再结合已有规则执行。

### 自动审核：把操作风险拆成具体问题

QwenPaw 在工具执行前通过 `assess_tool_call()` 收集工具名称、操作类型、目标、参数名称、沙箱状态与已有风险信号，向决策模型提出四类问题：

| 判断维度 | 内容 |
| --- | --- |
| 操作影响 | 只读、常规变更、高风险，还是信息不足 |
| 数据破坏 | 是否可能删除或覆盖已有用户数据 |
| 敏感信息暴露 | 是否可能读取凭据或将敏感信息传出本机 |
| 权限变化 | 是否可能扩大权限或削弱安全边界 |

模型返回分类、概率与置信度，程序依据固定阈值决定是否请求人工审批。原有权限规则和人工确认回退继续生效。

### 上下文压缩：保留后续还会用到的原文

长对话中的工具结果、日志和代码容易占满窗口。摘要可以保留讨论主线，却可能丢掉订单号、报错细节或具体数值。决策模型围绕当前任务判断 **“这份工具结果，接下来还用得上吗？”**，帮助压缩流程在摘要之外保留重要原文。

这类判断的价值在于：用有限上下文保留下一步需要的证据，减少重新检索历史内容的次数。实际保留质量仍取决于任务、阈值与上下文预算。

### 下载、启动，沿用 Jev 的启用位置

Piccolo 复用 QwenPaw-Flash 的本地 GGUF 下载与运行管理，以及 Jev 原有的决策模型配置入口，无需额外 Skill 或独立服务地址。当前接入在 **[QwenPaw Draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463)**，先按 [指南](QWENPAW.md)安装该分支与兼容 Piccolo 的 llama.cpp 运行时。

1. **下载并启动决策模型。** 在 **模型 → QwenPaw Local → 决策模型** 中选择合适的 BF16 或 Q8_0 版本，下载后点 **启动**，到 **模型 → 默认模型 → 决策模型** 确认。Q4_K_M 可使用对应 Hugging Face 仓库 ID 自定义下载。

   ![模型下载](../assets/qwenpaw/zh-model-download.jpg)

2. **启用自动审核。** 在会话模型菜单打开 **使用决策模型**，将工具审批设为 **决策模型模式**。

   ![自动审核](../assets/qwenpaw/zh-automatic-review.jpg)

3. **启用上下文压缩。** 在 **运行配置 → 上下文容量** 中启用上下文压缩，再打开 **决策模型压缩** 开关。

   ![上下文压缩](../assets/qwenpaw/zh-context-compaction.jpg)

[中英文全屏截图](../assets/qwenpaw/README.md)可用于官网或后续文章。启动模型与启用功能是独立步骤。内置 llama.cpp 只管理一个运行中的模型，对话可以使用其他提供商。本地决策减少额外远端请求，让用于判断的工具元数据与历史片段在本机处理；主对话模型及其他工具的数据流由各自配置决定。

## 05 面向真实工作流的评测

### HarnessJevBench

[HarnessJevBench](https://github.com/agentscope-ai/HarnessJevBench) 面向工具执行、资源调度、上下文管理、权限边界、完成验收与异常恢复等 Harness 控制职责。任务提供明确状态、证据与执行规则，检验模型能否完整核对约束。

评测同时观察**决策准确率**与**概率分布距离 TV**。Piccolo-27B 在表中 Hard 子集的准确率为 **82.03%**。其改进空间仍包括细粒度规则语义、多重约束组合及上下文证据保留。完整任务集与确定答案子集的分母不同，具体口径见 [评测记录](../evaluation/README.md)。

### DataJevBench

[DataJevBench](https://github.com/datajuicer/DataJevBench) 面向数据工作流，覆盖数据准入、处理方案选择、产物质量、分析就绪、产物核验与披露、任务执行控制。v0.5 包含 **500 道任务**：480 道选择题与 20 道有序评分题，涵盖中英文。

Piccolo-27B 总体准确率为 **82.40%（412/500）**，数据产物质量评价与信息充分性判断分别达到 **91.25%** 和 **81.00%**。该基准结合准确率、ECE 与 Brier 分数，帮助分析模型在不同任务上的正确性与概率质量。

## 06 下一步

我们希望让决策模型成为连接模型、执行与反馈的共同基础。接下来将继续拓展任务覆盖，完善审核与压缩的实际工作流评测，并补充训练配方与数据材料。

**TODO：补充标明硬件、上下文长度与批量设置的延迟、吞吐及内存实测；公开训练配方和数据说明。**

欢迎从 [Decision 官网](https://decisionplayground.agentscope.io/)开始体验，在 [GitHub](https://github.com/agentscope-ai/Piccolo) 查看实现，在 [Hugging Face](https://huggingface.co/agentscope-ai/Piccolo-27B) 下载模型。
