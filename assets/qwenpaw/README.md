# QwenPaw 三步配置截图

2026-10-29 从本机 QwenPaw 预览重新截图，供 Piccolo Blog、公众号与小红书复用。三张均为 1290 × 747 的原始浏览器 JPEG；未拼接或重绘界面。

| 步骤 | 配图 | 画面内容 |
| --- | --- | --- |
| 1. 下载 Piccolo | [原图](zh-model-download.jpg) | QwenPaw Local 决策模型列表，显示 Piccolo-4B-Q8_0 与 Piccolo-9B-Q8_0 的下载入口 |
| 2. 选择决策模型审批 | [原图](zh-automatic-review.jpg) | 运行配置的工具审批模式，已选中“决策模型模式” |
| 3. 启用决策模型压缩 | [原图](zh-context-compaction.jpg) | 已展开“决策模型压缩”，启用开关为开启状态 |

画面用于说明配置步骤。截图期间没有下载或启动模型，也没有执行审批或压缩任务。拍摄后将预览的工具审批恢复为原有“自动模式”，决策模型压缩恢复关闭；原有上下文压缩总开关保持开启。

图片大小、摘要和可见状态见 [截图清单](screenshots-20261029.json)。[Blog](../../docs/piccolo-blog.md) 已按三个步骤引用新版图片。

## 工具审批实录

[观看中英文结算审计回放](https://decisionplayground.agentscope.io/piccolo.html#qwenpaw-showcase)。9.6 秒加速片段来自真实 QwenPaw 会话。Qwen Plus 调用工具核对流水与银行记录，本地 Piccolo-4B-Q4_K_M 放行表结构查询，对读取逐笔流水和覆盖日报请求人工确认。确认后，QwenPaw 将净额从 ¥276 修正为 ¥188。

[DataJevHarness 样本筛选](https://decisionplayground.agentscope.io/piccolo.html#datajev-showcase) 是独立的 8.4 秒模拟动画。
