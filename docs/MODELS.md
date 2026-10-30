# Published Piccolo models

All 12 repositories below are public on Hugging Face and use Apache-2.0. Download links point to the current cards; [the manifest](../models/manifest.json) pins weight-bearing revisions, sizes and LFS SHA-256 checksums.

| Size | Complete Safetensors | BF16 GGUF | Q8_0 GGUF | Q4_K_M GGUF |
| --- | --- | --- | --- | --- |
| 4B | [Safetensors](https://huggingface.co/agentscope-ai/Piccolo-4B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-4B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-4B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-4B-Q4_K_M) |
| 9B | [Safetensors](https://huggingface.co/agentscope-ai/Piccolo-9B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-9B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-9B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-9B-Q4_K_M) |
| 27B | [Safetensors](https://huggingface.co/agentscope-ai/Piccolo-27B) | [BF16](https://huggingface.co/agentscope-ai/Piccolo-27B-BF16) | [Q8_0](https://huggingface.co/agentscope-ai/Piccolo-27B-Q8_0) | [Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-27B-Q4_K_M) |

BF16 is converted directly from the original complete Safetensors checkpoint. It retains some normalization and recurrent-state tensors as F32 and does not pass through integer quantization. GGUF is the text decision path; auxiliary vision/MTP tensors remain in the complete checkpoint. Download all numbered GGUF shards into one directory.

## Local model selection

[QwenPaw Draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463) provides the integration. Use the [setup guide](QWENPAW.md) and its companion patched llama.cpp runtime. The memory-aware catalog includes BF16 and Q8_0; Q4_K_M is available by repository ID.

| Model | Q8_0 catalog memory threshold | BF16 catalog memory threshold | BF16 download size |
| --- | ---: | ---: | ---: |
| 4B | 16 GB | 24 GB | 8.42 GB |
| 9B | 24 GB | 32 GB | 17.92 GB |
| 27B | 48 GB | 80 GB | 53.81 GB |

Thresholds are catalog policy, not measured peak-memory guarantees. The managed runtime serves one model at a time. Starting Piccolo selects the decision slot; automatic review and compaction each have their own opt-in switch.

Inference requires bidirectional prompt attention in full-attention layers, unchanged linear attention, the exact `flex_twice` layout and candidate-token probability readout. It generates no answer tokens. Stock causal chat completion is not equivalent. [Reference inference](../inference/README.md).

## Results and limits

[Benchmark results](../evaluation/README.md) correspond to the published full checkpoints. Quantized model cards separately disclose numerical regressions and limitations; quantization can change probabilities and decisions. The 265-request / 556-judgment synthetic regression is not a safety calibration or independent task benchmark.

## Public entry points

- Website: [Decision](https://decisionplayground.agentscope.io/).
- Source and release notes: [agentscope-ai/Piccolo](https://github.com/agentscope-ai/Piccolo).
- ModelScope: [planned Piccolo-27B mirror](https://modelscope.cn/models/agentscope-ai/Piccolo-27B), **not published yet**; use Hugging Face now.
