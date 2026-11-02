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

[播放视频](https://decisionplayground.agentscope.io/blog/assets/qwenpaw-tool-review.mp4) · [MP4 原文件](tool-review.mp4)

QwenPaw 使用 Qwen Plus 作为对话模型，以本地运行的 Piccolo-4B-Q4_K_M 审核工具调用。视频先展示两个模型的分工，再记录一次完整请求。用户要求统计清单行数，审批通过后，QwenPaw 运行 `wc -l piccolo-showcase-notes.txt`，得到 3 行。画面保留了实际执行时的等待过程。
