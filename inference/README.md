# 推理与本地接入

Piccolo 已发布完整 Safetensors 和三种 GGUF 精度，见 [模型矩阵](../docs/MODELS.md)。日常本地使用复用 [QwenPaw 管理的兼容 llama.cpp](../docs/QWENPAW.md)，完整 checkpoint 则使用本目录 [参考实现](reference/piccolo_inference.py)。

## 参考推理

```bash
python -m pip install -r inference/reference/requirements.txt huggingface_hub
hf download agentscope-ai/Piccolo-4B --revision ae30995bef9b0f0fa7d12adf517c63cdbc4d10d2 --local-dir Piccolo-4B
python inference/reference/piccolo_inference.py \
  --model Piccolo-4B --request examples/request.json --device cuda:0
```

在仓库根目录执行。模型目录必须包含 `decision-inference.json`、tokenizer 与全部权重。CPU 可用 `--device cpu --dtype float32`，但需更多内存。[最小请求与输出解释](../examples/README.md)。参考实现包含直接读取输出层候选行、注意力掩码与提示编译逻辑；FlexDM 布局保留 [MIT 声明](reference/THIRD_PARTY_LICENSES.md)。

## 推理协议

- **输入：**原生 `state` 与完整 `questions`，使用 `flex_twice` 布局。重复布局在整个请求的一遍 token 预算不超过 3,000 且每行能放入上下文时使用。
- **注意力：**Qwen3.5 全注意力层对完整 prompt 使用双向注意力；线性注意力层维持原计算。
- **输出：**在 `Answer: (` 位置读取单 token 候选 logits，以温度 1 softmax，等价于重新归一化候选 logprob。不生成回答文本。
- **运行：**禁用前缀缓存复用、因果分块预填充与静默截断。QwenPaw 当前每行完整提示预算为 8,192 token。

普通因果聊天接口或未适配 Ollama 不实现这套协议。GGUF 里的 `blink` 是既有序列化格式标识，不是旧下载／缓存别名。

## 证据与限制

模型卡保留完整 checkpoint 对照、BF16 精度事实和 Q4/Q8 数值回归；参考推理不是额外的任务能力评测。正式成绩与量化数值检查分开列于 [evaluation/](../evaluation/README.md)。硬件性能、概率校准与实际审核／压缩质量仍需进一步测量。
