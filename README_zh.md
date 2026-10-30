<p align="center"><img src="arena/web/playground/logos/blink.svg" width="72" alt="Piccolo"></p>

<h1 align="center">Piccolo</h1>
<p align="center"><strong>面向智能体工作流的快速决策模型</strong></p>
<p align="center">
  <a href="https://decisionplayground.agentscope.io/">🌐 Decision</a> ·
  <a href="https://github.com/agentscope-ai/Piccolo"><img src="assets/brands/github.svg" width="20" height="20" alt=""> GitHub</a> ·
  <a href="https://huggingface.co/agentscope-ai/Piccolo-27B"><img src="assets/brands/huggingface.svg" width="20" height="20" alt=""> Hugging Face</a> ·
  <a href="https://modelscope.cn/models/agentscope-ai/Piccolo-27B"><img src="assets/brands/modelscope.png" width="20" height="20" alt=""> ModelScope · 即将发布</a>
</p>
<p align="center"><a href="README.md">English</a> / 简体中文 · <a href="docs/piccolo-blog.md">发布 Blog</a> · <a href="docs/MODELS.md">模型说明</a> · <a href="LICENSE">Apache-2.0</a></p>

Piccolo 是一个 **4B、9B、27B 决策模型系列**。给定当前状态、问题与候选项，它返回程序可以直接使用的结构化判断与候选概率，适用于工具审核、上下文筛选、数据工作流和交互环境。**Piccolo-27B 在 JevBench Public 上取得 92.21% 的准确率，在 Decision Index Public 上取得 68.29 分。** 访问 [Decision 官网](https://decisionplayground.agentscope.io/)体验，或通过 QwenPaw 在本地使用。

## 模型下载

以下 **12 个 Hugging Face 仓库均已发布**，权重采用 Apache-2.0：

| 模型 | 完整 Safetensors | BF16 GGUF | Q8_0 GGUF | Q4_K_M GGUF |
| --- | --- | --- | --- | --- |
| Piccolo-4B | [HF](https://huggingface.co/agentscope-ai/Piccolo-4B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-4B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-4B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-4B-Q4_K_M) |
| Piccolo-9B | [HF](https://huggingface.co/agentscope-ai/Piccolo-9B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-9B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-9B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-9B-Q4_K_M) |
| Piccolo-27B | [HF](https://huggingface.co/agentscope-ai/Piccolo-27B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-27B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-27B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-27B-Q4_K_M) |

`-BF16` GGUF 从完整 Safetensors 直接转换，部分归一化和递归状态张量保留 F32；Q8_0、Q4_K_M 用较小体积换取一定数值精度损失。下载分片模型时，须将**全部 GGUF 分片放在同一目录**。[完整模型说明、固定 revision 与限制](docs/MODELS.md)。

[ModelScope / Piccolo-27B](https://modelscope.cn/models/agentscope-ai/Piccolo-27B) 为预留镜像地址，**尚未发布**，当前请从 Hugging Face 下载。

## 评测表现

| 模型 | HarnessJevBench Hard ↑ | DataJevBench ↑ | JevBench Public ↑ | Decision Index Public ↑ |
| --- | ---: | ---: | ---: | ---: |
| **Piccolo-27B** | **82.03%** | **82.40%** | **92.21%** | **68.29** |
| Piccolo-9B | 69.49% | 68.80% | 89.61% | 60.63 |
| Piccolo-4B | 65.59% | 69.60% | 87.01% | 57.31 |

以上成绩对应当前发布的完整 Hugging Face 权重。量化版本另有数值回归，表格不代表 Q4/Q8 重新运行同一套 benchmark 的成绩。[评测口径与来源快照](evaluation/README.md) · [在线榜单](https://decisionplayground.agentscope.io/)。

## 方法：让反馈驱动下一轮训练

Piccolo 将模型优化组织为 **诊断 → 数据选择与构造 → 训练评测 → 更新配方** 的循环。多源材料统一为“状态、问题、候选项、目标分布”，结合语义切片与逐题学习信号，定位值得继续学习的数据。Agent 据此调整配比、补充能力缺口并比较实验。训练与推理使用一致的候选接口、双向 prompt attention 和源自 FlexDM 的 `flex_twice` 布局。方法和应用见 [发布 Blog](docs/piccolo-blog.md)。

## 看见连续决策

八段完整归档回放呈现模型的连续动作，右侧展示记录中的候选概率。交互播放器支持暂停、拖动与逐步查看。

<table>
  <tr>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/mario.json"><img src="assets/showcase/mario.gif" width="100%" alt="Mario"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/snake.json"><img src="assets/showcase/snake.gif" width="100%" alt="Snake"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/merge-2048.gif" width="100%" alt="2048 · target 128"></a></td>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/sokoban.gif" width="100%" alt="Sokoban"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/tetris.gif" width="100%" alt="Tetris"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/jump-jump.json"><img src="assets/showcase/jump-jump.gif" width="100%" alt="Jump Jump"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/hex.json"><img src="assets/showcase/hex.gif" width="100%" alt="Hex"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/dots-and-boxes.json"><img src="assets/showcase/dots-and-boxes.gif" width="100%" alt="Dots &amp; Boxes"></a></td>
  </tr>
</table>

回放保留原 checkpoint 身份和终局，与上方发布模型的 benchmark 表分开记录。GIF 播放速度不代表模型推理延迟。[来源与复现说明](docs/SHOWCASE.md)。

## QwenPaw：本地部署的决策模型

接入位于 **[QwenPaw Draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463)**，需要该分支与配套的 **Piccolo llama.cpp 运行时**。先按 [安装指南](docs/QWENPAW.md)准备运行环境；并非所有已发布的 QwenPaw 版本都已支持。

1. 打开 **模型 → QwenPaw Local → 决策模型**，下载适合设备的 Piccolo BF16 或 Q8_0 GGUF，点击 **启动**，到 **模型 → 默认模型 → 决策模型** 确认选择。Q4_K_M 也已发布，可按仓库 ID 自定义下载。

   ![本地模型下载](assets/qwenpaw/zh-model-download.jpg)

2. 在会话模型菜单启用 **使用决策模型**，将工具审批模式设为 **决策模型模式**。

   ![自动审核入口](assets/qwenpaw/zh-automatic-review.jpg)

3. 在 **运行配置 → 上下文容量** 中启用上下文压缩，再打开独立的 **决策模型压缩** 开关。

   ![上下文压缩入口](assets/qwenpaw/zh-context-compaction.jpg)

启动模型不会自动开启审核与压缩。内置 llama.cpp 同时运行**一个模型**，对话模型可以使用其他提供商。原生审批阈值和人工确认回退继续生效。[中英文全屏截图](assets/qwenpaw/README.md)。

Piccolo 在全注意力层使用双向 prompt attention，保留线性注意力层计算，直接读取候选 token 的 logits 并归一化，通过原生 `/v1/systemone` 返回结果，不生成回答文本。普通因果聊天接口不实现这一协议。[参考推理与请求示例](inference/README.md)。

## 本地运行 Arena

只读预览仅需 Python 3：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory arena/web
```

打开 **http://127.0.0.1:8080/completed-showcase.html** 或 **http://127.0.0.1:8080/showcase.html**。运行完整应用前停止静态服务，使用 Python 3.12 与 Node.js 22：

```bash
cd arena
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
bash scripts/run.sh
```

打开 **http://127.0.0.1:8080/**。详见 [Arena 文档](arena/README.md)、[API](arena/docs/API.md) 和 [共享引擎](arena/docs/ENGINE.md)。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| [models/](models/README.md) | 已发布模型入口与固定 revision 清单 |
| [inference/](inference/README.md) | 完整 checkpoint 参考推理与原生协议 |
| [examples/](examples/README.md) | 最小决策请求与本地调用 |
| [evaluation/](evaluation/README.md) | 发布权重的成绩及证据范围 |
| [arena/](arena/README.md) | 交互应用、引擎、榜单和回放 |
| [docs/piccolo-blog.md](docs/piccolo-blog.md) | 公众号与小红书共用的发布母稿 |
| [training/](training/README.md)、[data/](data/README.md) | Coming soon：训练配方与数据集 |

## 复现与贡献

```bash
cd arena
python3.12 scripts/export_home_decision.py --check
python3.12 -m unittest tests.test_home_decision -v
```

素材复现见 [Showcase 说明](docs/SHOWCASE.md)。反馈问题时附玩法、种子、步骤及脱敏回放，保留原参与者身份与终局。[验证记录](docs/VERIFICATION.md) · [变更说明](CHANGELOG.md)。

## 许可与署名

仓库自有代码采用 **[Apache-2.0](LICENSE)**，已发布模型权重也采用 Apache-2.0。第三方组件保留各自许可，详见 [NOTICE](NOTICE)、[Arena 第三方说明](arena/docs/THIRD_PARTY.md) 与 [FlexDM MIT 声明](inference/reference/THIRD_PARTY_LICENSES.md)。Arena 改编自 JevArena，历史 `jev.*` 协议、`JEV_*` 环境变量与回放 ID 保留。
