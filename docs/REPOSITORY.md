# Piccolo 仓库范围

更新日期：2026-10-27。

## 当前内容

仓库包含可独立运行的 Piccolo Arena、历史结果与回放、JevArena 完整对局 Showcase、素材复现脚本和安全审批接入框架。[Decision](https://decisionplayground.agentscope.io/) 为官网入口；本仓库的验证只覆盖本机版本，不意味着已更新官网部署。

新增 [Blog 母稿](blog.md)，供公众号与小红书复用。文中的粗体 TODO 是发布前待补齐项，不是已有能力。

模型发布相关目录均有 Coming soon README：`models/`（模型卡与权重）、`inference/`（模型服务）、`training/`（训练方案）、`data/`（数据发布）、`evaluation/`（正式评测）、`examples/`（模型接入示例）。Arena 内已有数据、评测和环境 API 仍在原位置，这些预留目录承接正式 Piccolo 版本的材料。

## 初始迁入记录（2026-10-26）

## 前端迁入

- 从当前 JevArena 工作区的可发行文件清单整理，包含现有未提交更新，不回退历史发布副本。
- 前端、HTTP 服务、共享游戏引擎、榜单、公开回放一起放入 `arena/`。
- 项目品牌改为 Piccolo，应用名为 Piccolo Arena；Python 包改为 `blink_arena`，启动脚本、导入、测试和打包入口同步更新。
- 模型展示名称与图标更新；原模型 ID、轨迹 ID、分数、概率、席位与终局结果保留。第三方 benchmark 名称不改。
- `arena-replays.json` 仅改 JSON 排版，从约 159 MiB 缩小至约 32 MiB，保持解析后逐项相等。
- 内网 System One 文档改为通用接入说明，示例端点改为回环地址。虚拟环境、运行数据、日志、内部交接和历史发布目录不进入新仓库。

## 新增内容

- 中英文 README、Piccolo 图标及四组有来源的轨迹 Showcase。
- 独立只读轨迹播放器，复用已有渲染器；导出与渲染脚本可重现 README 动图。
- 初次整理时 `inference/`、`training/` 仅有 `.gitkeep`；现已补充 README，但仍未新增模型推理或训练实现。
- `skills/blink-safety-review/` 提供未来模型发布后的下载助手、动作审查客户端、QwenPaw ToolGuard 附加检查器及导入说明。模型发布清单保持未配置。

初次迁入已按用户要求发布到 `agentscope-ai/Piccolo`。仓库整理不修改原工作区源码，不启动模型，不改变现有 QwenPaw 配置。原应用的历史发布检查记录留在原工作区；本仓库使用 [当前验证记录](VERIFICATION.md)。

## 模型确定后的补齐项

正式发布时还需要模型卡（定位、支持范围和已知限制）、权重地址与固定版本、代码及权重许可、可复现推理入口、训练说明和数据来源说明、评测配置与结果。安全审批用途需单独验证越权识别、误拦与漏拦，并完成 QwenPaw 宿主接入验收；游戏轨迹不能代替这类评测。当前不预填模型架构、参数或能力结论。
