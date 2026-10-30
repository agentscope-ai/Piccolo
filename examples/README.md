# 最小决策示例

[request.json](request.json) 提供只读工具操作背景，询问是否可能删除或覆盖数据。它不会执行工具，只读取模型候选概率。

## 完整 checkpoint

在仓库根目录执行；先准备具备足够内存／显存的 Python 环境。以下命令会下载完整 4B 权重：

```bash
python -m pip install -r inference/reference/requirements.txt huggingface_hub
hf download agentscope-ai/Piccolo-4B --revision ae30995bef9b0f0fa7d12adf517c63cdbc4d10d2 --local-dir Piccolo-4B
python inference/reference/piccolo_inference.py \
  --model Piccolo-4B --request examples/request.json --device cuda:0 --output result.json
```

CPU 参考路径使用 `--device cpu --dtype float32`，需要更多内存。脚本不依赖文本生成或额外服务，保持完整提示与双向注意力。结果包含 `attention_mode`、`layout` 与 `results`；`results[0].option_keys` 对应 `results[0].bidirectional_prompt.probabilities`。检查 `attention_mode=bidirectional_prompt`、候选概率有限且总和约为 1。具体数值由模型实际推理产生，此处不虚构固定输出。

## QwenPaw

按 [下载与启用指南](../docs/QWENPAW.md)启动模型后，在 QwenPaw Python 环境运行：

```bash
python scripts/check_qwenpaw_local.py
```

成功时输出 `status=local_decision_interface_ok`、实际 `returned_model` 与合成样本的审批／上下文结果。失败时退出码非零，并提示检查模型选择与运行时，不回显服务错误中的潜在敏感内容。

[推理协议](../inference/README.md) · [评测范围](../evaluation/README.md)。
