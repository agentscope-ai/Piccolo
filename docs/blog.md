# Piccolo：如何让模型在交互环境中做出可执行、可验证的决策？

模型参与游戏、操作工具或完成连续任务，需要根据当前状态选择动作，并接收动作执行后的反馈。当环境继续变化、对手作出回应或一次操作影响后续选择时，决策的合法性、执行时机与最终结果都需要被记录和检查。因此，构建面向交互任务的决策系统，需要同时考虑环境规则、模型接口与结果验证。

Piccolo 围绕“观察—选择—执行—反馈”组织决策过程。当前仓库提供 Piccolo Arena，将交互试玩、共享游戏引擎、模型接入、评测与轨迹回放放到同一套环境中，并整理了八个游戏场景的历史回放展示。后续模型、训练与发布材料将沿这一结构补齐。

**TODO：补充正式 Piccolo 模型的核心定位、架构与规模、训练方法，以及有完整实验支持的主要结论。**

- 体验主页：[Decision](https://decisionplayground.agentscope.io/)
- 代码仓库：[agentscope-ai/Piccolo](https://github.com/agentscope-ai/Piccolo)
- 模型：**TODO：补充权重地址、固定版本与模型卡。**
- 数据集：Coming soon。**TODO：补充可发布范围、数据卡与下载入口。**
- 技术报告：**TODO：补充报告链接与引用信息。**

**TODO：补充项目总览图，展示模型、环境、轨迹与评测之间的关系；确认团队署名、发布日期和仓库对外可见性。**

## 01 决策闭环：观察、选择与执行反馈

在 Piccolo Arena 中，环境将当前可见状态与合法候选组织成决策输入。模型按约定返回动作，环境应用动作并记录后继状态、奖励或终局。下一轮决策再基于实际反馈继续进行。

这一过程包含四个环节：

- **观察：**环境生成模型可以看到的信息和当前合法动作。
- **选择：**模型服务通过约定接口返回动作；回放保留当时的候选与实际选择。
- **执行：**共享引擎按照规则推进状态，并处理自动执行或对手行动。
- **反馈：**记录执行后的变化、终局与计分，供后续决策、评测和复盘使用。

这样的组织方式支持逐步检查：当时有哪些合法选择，模型返回的动作是什么，执行后状态如何变化，以及任务是否真正完成。对于存在实时过程的环境，还需要记录模型响应期间发生的变化，检查动作到达时是否仍然适用。

**TODO：补充正式模型的输入输出示例、决策流程图与服务接口说明；若强调推理效率，需要提供相同硬件、输入长度和统计口径下的延迟数据。**

## 02 共享环境：连接试玩、评测与训练

试玩、评测和训练都需要执行状态转移。Piccolo Arena 将这部分规则放入共享引擎：前端负责呈现局面和接收交互，HTTP 服务管理会话与决策流程，程序化调用通过引擎入口或 Rollout 接口组织对局。

共享规则让页面上的交互与程序化实验有了共同基础。研究者可以先在界面中理解任务，再用环境接口检查策略行为，将执行过程保存为轨迹，并在回放中定位结果变化。对于已经接入的任务，训练调用方也可以复用这些环境接口。

仓库中，`arena/` 包含应用、共享引擎与已有归档；`models/`、`inference/`、`training/`、`data/`、`evaluation/`、`examples/` 分别预留模型、服务、训练、数据、评测与使用示例。尚未交付的模块均以 Coming soon 标记。

**TODO：补充环境覆盖清单与数量、观测和动作空间的分类、支持的训练调用方式，以及“前端—共享引擎—评测—训练”结构图。现有 Rollout 接口之外的完整 Piccolo 训练方案仍需补齐。**

## 03 Showcase：多种交互环境中的决策过程

从马里奥的平台跳跃、数字合并与推箱规划，到连续跳跃、落子与回合对抗，八个展示集中呈现不同环境中的动作与反馈。交互播放器可暂停、拖动进度，查看局面如何随决策改变。

<table>
  <tr>
    <td width="50%" align="center"><a href="../arena/web/showcase/traces/mario.json"><img src="../assets/showcase/mario.gif" width="100%" alt="马里奥"></a></td>
    <td width="50%" align="center"><a href="../arena/web/showcase/traces/snake.json"><img src="../assets/showcase/snake.gif" width="100%" alt="贪吃蛇"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="../arena/web/playground/data/home-decision.json"><img src="../assets/showcase/completed/merge-2048.gif" width="100%" alt="2048 · 目标 128"></a></td>
    <td width="50%" align="center"><a href="../arena/web/playground/data/home-decision.json"><img src="../assets/showcase/completed/sokoban.gif" width="100%" alt="推箱子"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="../arena/web/playground/data/home-decision.json"><img src="../assets/showcase/completed/tetris.gif" width="100%" alt="俄罗斯方块"></a></td>
    <td width="50%" align="center"><a href="../arena/web/showcase/traces/jump-jump.json"><img src="../assets/showcase/jump-jump.gif" width="100%" alt="跳一跳"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="../arena/web/showcase/traces/hex.json"><img src="../assets/showcase/hex.gif" width="100%" alt="Hex 六角棋"></a></td>
    <td width="50%" align="center"><a href="../arena/web/showcase/traces/dots-and-boxes.json"><img src="../assets/showcase/dots-and-boxes.gif" width="100%" alt="点格棋"></a></td>
  </tr>
</table>

以上均为历史实验样例，保留原模型版本与终局结果；2048 的任务目标为 128。动图按固定节奏采样已保存状态，播放速度不表示推理延迟。这些展示用于观察决策过程，不构成总体成功率或待发布 Piccolo 模型的成绩。来源、完整轨迹与验证方式见 [Showcase 说明](SHOWCASE.md)。

**TODO：制作可公开分享的合集视频；根据实际使用情况继续补充更有代表性的交互场景。**

## 04 模型训练与实验结果

完整发布需要提供训练方法、数据处理和实验配置，使读者能够判断结果适用于什么任务、来自哪个模型版本，以及如何复现。目前仓库已提供环境和历史归档，正式 Piccolo 模型的训练材料与评测仍待补齐。

**TODO：训练数据。补充数据来源、许可、构建方式、原始数量、筛选后数量、训练测试去重，以及覆盖范围。**

**TODO：训练方法。补充基础模型、SFT / RL 的实际使用方式、奖励设计、超参数、随机种子、计算预算与 checkpoint 选择标准。**

**TODO：主要结果。补充完整评测表或图，标明任务、样本量、固定模型版本、对照模型、统计口径与不确定性；同时报告失败率和未完成情况。**

**TODO：效率与消融。补充相同条件下的延迟、吞吐或成本测量，以及能够解释训练、数据或决策设计作用的消融实验。**

**TODO：泛化与限制。补充未参与训练的环境或工具场景测试、迁移实验、典型失败案例，以及当前方法的适用边界。**

上述材料应与 `training/`、`data/`、`evaluation/` 中的发布内容对应。正式结果齐备后，再据此撰写本文的实验结论与摘要。

## 05 应用探索：工具动作执行前的安全审查

除游戏环境外，Piccolo 也在准备工具动作安全审查的接入方向：结合用户意图与拟执行操作，在动作执行前给出建议。

仓库中的 `blink-safety-review` 包含发布下载助手、决策客户端，以及可选的 QwenPaw ToolGuard 适配器。接口预留 `allow`、`ask_user`、`deny` 三类建议，用于表达允许、需要询问与拒绝。审查组件不执行被审查的动作，宿主原有工具规则继续生效。

目前模型发布清单仍未配置，真实模型支持的审批能力尚需验证。该用途需要单独检查误拦、漏拦、授权上下文和用户交互，游戏回放提供不了这些结论。

**TODO：补充安全审查模型、威胁范围、真实案例、误拦与漏拦结果、服务不可用时的处理方式，以及 QwenPaw 端到端接入演示。**

## 06 我们的愿景

我们希望把交互环境建设成连接模型、执行与反馈的共同基础，让决策既能被体验，也能被检查，并进一步成为评测和学习的依据。

接下来，我们将围绕模型发布补充推理、训练、数据与评测材料，逐步扩展环境和实际应用场景。每项能力都应附带清楚的任务定义、执行记录和结果依据，让读者能够沿着一次动作追溯到它产生的变化。

欢迎从 [Decision 官网](https://decisionplayground.agentscope.io/) 开始体验，暂停在一个局面，比较自己的选择与回放中的动作。希望进一步了解环境或接口的读者，可以查看 [Piccolo 仓库](https://github.com/agentscope-ai/Piccolo) 和 [中文使用说明](../README_zh.md)。

**TODO：补充正式模型下载入口、代码与权重许可、项目联系人或反馈渠道，以及 Decision 官网二维码。**

---

## 编辑说明与跨平台复用（发布前删除本节）

本文为公众号与小红书的事实母稿。结构参考用户提供的 [Cowork-Gym 推文](https://mp.weixin.qq.com/s/l8SYXeQ52widCOXwUQVFNQ)：问题导入、项目概述、资源入口、编号技术小节、实验与愿景。Piccolo 的事实依据为本仓库的 [轨迹来源](SHOWCASE.md)、[仓库范围](REPOSITORY.md) 和 [验证记录](VERIFICATION.md)。

所有 **TODO** 需补齐、核实或删除后再发布。模型未发布时保留准备状态；正式实验结论需要与完整结果对应。

- **公众号：**沿用正文标题、开头两段和编号小节。配图依次为项目总览、决策流程、Showcase 合集、实验结果、体验入口。实验图在数据齐备后制作。
- **小红书标题：**《让 AI 玩一局，看懂它怎么做决定》。建议 5 张图：封面、决策流程、Showcase 合集上、Showcase 合集下、体验入口。合集沿用正文分组，保留“历史精选样例”和任务目标。
- **小红书配文底稿：**AI 做出一次选择，环境会怎样变化？Piccolo 把观察、动作与反馈放进可回放的决策过程。八个游戏展示从合并、推箱、跳跃到回合对抗的决策过程；你可以暂停、拖动，查看当时有哪些选择，以及动作之后发生了什么。这些是精选历史样例，Piccolo 模型仍在准备中。体验入口：Decision；环境源码与复现说明：Piccolo 仓库。
- **现有素材：**正文使用的八张 GIF 及预览图分布在 `assets/showcase/completed/` 与 `assets/showcase/`，各自附逐帧来源清单。独立播放器的本机启动方式见 [中文 README](../README_zh.md#快速体验)。

**TODO：制作公众号横版封面、小红书竖版图卡、总览图与官网二维码；复核平台版式、团队信息、对外可见链接及所有能力表述。**
