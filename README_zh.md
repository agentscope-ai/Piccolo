<p align="center"><img src="arena/web/playground/logos/blink.svg" width="72" alt="Blink"></p>

<h1 align="center">Blink</h1>
<p align="center"><strong>让决策动起来。</strong></p>
<p align="center"><a href="https://decisionplayground.agentscope.io/">Decision · 官网</a> · <a href="README.md">English</a> / 简体中文 · <a href="docs/blog.md">项目 Blog</a> · <a href="arena/README.md">Arena 文档</a></p>

Blink 把**观察、动作与反馈**连接成可以检查的决策过程。Blink Arena 汇集交互游戏、共享环境规则、模型评测和轨迹回放。你可以访问 [Decision 官网](https://decisionplayground.agentscope.io/)，也可以在本机运行仓库内的 Arena。

**发布状态：**当前仓库包含 Arena 源码、历史回放与安全审批接入框架。Blink 模型权重、模型卡、专用推理与训练方案、正式发布评测仍在准备中。回放保留原 checkpoint 名称，用于标识历史实验，不代表待发布 Blink 模型的身份或成绩。

## 看见决策过程

从 JevArena 的新版 Showcase 引入四局完整历史对局。交互播放器可以查看观察、候选动作、原记录选择与执行反馈，支持拖动进度、倍速、逐步播放和直接查看结局。

| 2048 · 达到任务目标 128 | 推箱子 · 两个箱子全部归位 |
| --- | --- |
| [![2048 完整回放](assets/showcase/completed/merge-2048.gif)](arena/web/playground/data/home-decision.json) | [![推箱子完整回放](assets/showcase/completed/sokoban.gif)](arena/web/playground/data/home-decision.json) |
| **黑白棋 · 完成 6×6 对局** | **俄罗斯方块 · 消除四行** |
| [![黑白棋完整回放](assets/showcase/completed/othello.gif)](arena/web/playground/data/home-decision.json) | [![俄罗斯方块完整回放](assets/showcase/completed/tetris.gif)](arena/web/playground/data/home-decision.json) |

这是**精选通关样例**，不能据此计算总体成功率或比较模型优劣。四局共有 116 次记录转换、89 次模型调用；对手落子和自动执行单独标记。动图按固定节奏采样已保存状态，播放速度不表示推理延迟。交互播放器保留全部记录步骤及俄罗斯方块执行帧。每局 checkpoint、种子、终局和采样方法见 [来源与复现](docs/SHOWCASE.md)。[早期轨迹](arena/web/showcase/manifest.json) 也继续保留，包括一次俄罗斯方块失败记录。

## 快速体验

### 只看 Showcase

只需 Python 3，无需模型、API key 或后端服务：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory arena/web
```

打开 **http://127.0.0.1:8080/completed-showcase.html**。支持中英文。启动完整 Arena 前，先停止这个静态服务器，避免占用同一端口。

### 运行 Blink Arena

需要 Python 3.12 和 Node.js 22：

```bash
cd arena
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
bash scripts/run.sh
```

打开 **http://127.0.0.1:8080/**，可手动试玩、浏览已导入成绩和查看回放。有兼容模型服务时，通过页面的模型连接表单接入；接口格式与 CORS 要求见 [API 文档](arena/docs/API.md)。进一步使用见 [Arena 启动说明](arena/README.md)、[共享引擎](arena/docs/ENGINE.md) 和 [Rollout 接口](arena/docs/ROLLOUT.md)。

## 现在有什么，后续补什么

| 组件 | 已包含 | 待补齐 |
| --- | --- | --- |
| Arena | 前端、HTTP API、共享游戏引擎、历史成绩和回放 | 已支持范围见 [Arena 文档](arena/README.md) |
| 模型 | 历史回放保留原模型身份 | [模型卡、权重与条款](models/README.md) |
| 推理 | Arena 可连接已有兼容服务 | [Blink 模型推理与服务方案](inference/README.md) |
| 训练与数据 | 共享环境、Rollout 接口 | [训练方案](training/README.md)、[数据发布说明](data/README.md) |
| 评测 | Arena 现有评测代码与历史结果 | [正式发布配置与结果](evaluation/README.md) |
| 示例 | 手动试玩、回放检查、安全审批接入框架 | [Blink 模型端到端示例](examples/README.md) |

上述待补齐模块已建立目录与 Coming soon README；占位文件不代表实现已交付。

## 动作安全审批

[blink-safety-review Skill](skills/blink-safety-review/SKILL.md) 提供发布下载助手、决策客户端和可选的 QwenPaw ToolGuard 适配器，用于对待执行工具动作给出 `allow`、`ask_user`、`deny` 建议。

当前 [模型发布清单](skills/blink-safety-review/assets/release.json) 保持未配置，不会默认下载或启用模型。Skill 不执行被审查动作，不代替用户批准；模型支持的审批能力还需单独验证，游戏 Showcase 不能代替这类评测。模型和服务适配器确定后，按 [QwenPaw 接入说明](skills/blink-safety-review/references/qwenpaw.md) 完成宿主接入。

## 目录

```text
arena/                      独立 Arena 应用、共享引擎与归档
assets/showcase/             可重现动图、预览图和逐帧来源
docs/                       Blog、来源、发布范围与验证记录
scripts/                    展示渲染与前端验证脚本
skills/blink-safety-review/  动作安全审批接入框架
models/                     Coming soon：模型卡、权重与条款
inference/                  Coming soon：Blink 推理与服务
training/                   Coming soon：训练方案与配置
data/                       Coming soon：数据说明与发布
evaluation/                 Coming soon：发布评测与结果
examples/                   Coming soon：Blink 模型接入示例
```

## 复现与参与

在 Python 3.12 下离线检查完整轨迹，无需连接模型：

```bash
cd arena
python3.12 scripts/export_home_decision.py --check
python3.12 -m unittest tests.test_home_decision -v
```

安装 Playwright、Chromium 和 `ffmpeg` 后，从仓库根目录运行 `python scripts/render_completed_showcase.py` 重新生成新动图。旧版素材的复现方式见 [Showcase 文档](docs/SHOWCASE.md)。

反馈问题时请附上游戏、种子、复现步骤及可分享的脱敏回放；修改展示时保留原参与者 ID 和终局结果。测试范围与已知问题见 [验证记录](docs/VERIFICATION.md)，后续发布材料见 [仓库说明](docs/REPOSITORY.md)。

## 来源与许可

Arena 及完整对局 Showcase 由 JevArena 迁入。历史 `jev.*` 协议、`JEV_*` 环境变量及 checkpoint ID 保持兼容。第三方代码、玩法参考、规则库与字体见 [第三方说明](arena/docs/THIRD_PARTY.md)。项目级代码许可和模型权重条款仍待确定；当前没有新增项目级许可授权。
