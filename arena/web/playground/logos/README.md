# Model logos

用于标识榜单中的模型；第三方资产保留原品牌外观。模型名称为 **Piccolo**，团队与模型标识统一使用 **AgentScope 官方 AS Logo**，保留原始蓝紫渐变。

`agentscope.svg` 为正式资产，逐字节保留官方 README 引用的原始 SVG。`blink.svg`、`blink-light.svg` 和 `blink-favicon.svg` 为历史 URL 的兼容副本，均指向同一图形；`blink-wordmark.svg` 为 AgentScope 标识与 Piccolo 字标的自包含横向组合。旧 `oneshot.svg` 保留供历史归档引用。

官方来源：[AgentScope README](https://github.com/agentscope-ai/agentscope/blob/main/README.md) · [原始 SVG](https://img.alicdn.com/imgextra/i1/O1CN01nTg6w21NqT5qFKH1u_!!6000000001621-55-tps-550-550.svg)。于 2026-10-28 按团队要求采用。

| 文件 | 官网或官方资产来源 |
| --- | --- |
| qwen.png | https://img.alicdn.com/imgextra/i4/O1CN01OXv3EM1FN8t9W4P79_!!6000000000474-2-tps-80-80.png |
| deepseek.ico | https://www.deepseek.com/favicon.ico |
| liquid.ico | https://www.liquid.ai/favicon.ico?favicon.2y0c-hpb4ow2i.ico |
| inception.png | https://framerusercontent.com/images/u3lyX8mBY8mLYJQ0zOr4Y0ucwe4.png |
| typesafe.png | https://framerusercontent.com/images/aNFzSFxM4fjICmnibw7npfZjcQ.png |
| microsoft.ico | https://learn.microsoft.com/favicon.ico |

未明确对应品牌的模型不自动配图。所有图片在本包中本地提供，前端无需访问图标源站。

2026-10-20 新增 StartLux、Strands、Cloudflare、OpenAI、vLLM Semantic Router 与 Perplexity 的官方图标。模型 ID、发布者、官方链接与资产来源的核验记录见 [PUBLISHER_SOURCES.md](PUBLISHER_SOURCES.md)；前端映射保存在 `../model-logo.js`，不改变评测 JSON。Strands 与 vLLM-SR 使用发布团队标识，不使用其 Gemma / Qwen 基础模型的图标。Arena 的 Qwen 模型继续复用本地图标，并链接 [Qwen 官网](https://qwen.ai/)。
