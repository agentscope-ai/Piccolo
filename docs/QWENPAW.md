# Piccolo：QwenPaw 本地决策模型

Piccolo 复用 QwenPaw 的 GGUF 下载器、llama.cpp 管理，以及 Jev 原有的决策模型选择、自动审核与上下文压缩入口。完整权重、BF16、Q8_0、Q4_K_M 均已发布在 [Hugging Face](MODELS.md)，不需要额外 Skill、云端密钥或独立 Jev 服务地址。

## 安装支持该模型的版本

接入仍在 **[Draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463)**，尚未合入所有正式版本。可复现的实现为 fork 分支的提交 [`beea377`](https://github.com/Xinji-Mai/QwenPaw/commit/beea37749185553a6897e546eae6b7954717da5b)。先在独立目录获取该版本，再按其开发安装文档准备 QwenPaw：

```bash
git clone --branch codex/blink-local-decision https://github.com/Xinji-Mai/QwenPaw.git QwenPaw-Piccolo
cd QwenPaw-Piccolo
git checkout beea37749185553a6897e546eae6b7954717da5b
```

随后按同一提交的 **[运行时构建与安装说明](https://github.com/Xinji-Mai/QwenPaw/blob/beea37749185553a6897e546eae6b7954717da5b/docs/local-piccolo.md#compatible-runtime)** 构建配套 llama.cpp。该指南固定上游 commit `f4d8af608a6b39946406f9439edfb6e83ca6a923`，并应用 `docs/patches/piccolo-llama.cpp.patch`。停止本地模型后，备份原运行时，将新 `llama-server` 及匹配共享库安装到指南打印的 QwenPaw 运行时目录。

未适配的上游二进制和普通 Ollama 聊天接口不实现 Piccolo 协议。重新安装未适配运行时会移除支持。无需改变用户已有审批或压缩设置来安装运行时。

## 下载与启动

1. 打开 **模型 → QwenPaw Local → 决策模型**，下载适合设备的 BF16 或 Q8_0 模型。如果条目未显示，可在自定义下载中选择 Hugging Face，输入如 `agentscope-ai/Piccolo-4B-BF16`、`agentscope-ai/Piccolo-9B-Q8_0` 或 `agentscope-ai/Piccolo-27B-Q4_K_M`。
2. 下载器获取 GGUF 与推理所需说明，下载所有标准分片；无后缀的 Safetensors 仓库用于完整 checkpoint 参考推理。
3. 下载完成点击 **启动**，再到 **模型 → 默认模型 → 决策模型** 确认选择。智能体专属设置可以覆盖全局默认。

目录按设备内存推荐 BF16 与 Q8_0：

| 尺寸 | Q8_0 推荐门槛 | BF16 推荐门槛 | BF16 下载体积 |
| --- | ---: | ---: | ---: |
| 4B | 16 GB | 24 GB | 8.42 GB |
| 9B | 24 GB | 32 GB | 17.92 GB |
| 27B | 48 GB | 80 GB | 53.81 GB |

这些是目录展示门槛，不是峰值内存实测保证。Q4_K_M 已通过扩大数值回归并发布，可按仓库 ID 下载；其误差与限制见各模型卡。内置 llama.cpp **一次管理一个运行模型**，启动 Piccolo 会替换同一实例中的本地聊天模型；对话可使用其他提供商。

## 沿用 Jev 的启用位置

- **自动审核：**在会话模型菜单的高级选项中打开 **使用决策模型**，并将工具审批设为 **决策模型模式**。智能体默认模式位于 **运行配置 → 执行方式 → 工具审批模式**。
- **上下文压缩：**在 **运行配置 → 上下文容量** 中启用上下文压缩，再展开 **决策模型压缩** 并打开独立开关。

模型列表只负责下载、启动、停止和删除。启动 Piccolo 不会自动开启这两项功能。[中英文全屏截图](../assets/qwenpaw/README.md)记录了入口。

## 本地推理协议

```text
Hugging Face GGUF → QwenPaw 管理的 llama.cpp
                 → /v1/systemone 候选 token 评分
                 → AgentScope Jev → 自动审核 / ReMe 压缩
```

使用 `flex_twice` 布局，在 `Answer: (` 后读取单 token 候选标签的 logits，以温度 1 对候选集合归一化，等价于对候选 token 的 logprob 再归一化。不生成回答文本或概率 JSON。全注意力层使用双向 prompt attention，线性注意力层保持原计算。

每个问题使用完整提示，禁用前缀缓存与上下文滑移，context/batch/microbatch 保持一致；当前 QwenPaw 实现最多 8,192 token（含重复布局），超出预算显式失败并走原有回退，不静默截断。原始 checkpoint 的配置上限与这一运行预算分开理解。

原生审批阈值、人工确认回退与上下文恢复继续生效。候选概率不能视为经过任务校准的安全保证。参考实现与最小请求见 [推理说明](../inference/README.md)，转换与量化证据见各模型卡。

## 检查当前选择

在支持该集成的 QwenPaw Python 环境，从 Piccolo 仓库运行：

```bash
python scripts/check_qwenpaw_local.py
python -m pytest tests/test_qwenpaw_local.py
```

校验脚本只发送合成输入，不执行示例工具、不下载模型、不修改配置。测试连接回环协议替身，不能代替实际模型质量或完整工作流评测。
