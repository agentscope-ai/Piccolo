# Piccolo models

Piccolo provides structured decision probabilities for automatic tool review and context compaction. All nine repositories below are public on Hugging Face, with Apache-2.0 weights and preserved FlexDM attribution.

| Size | Complete checkpoint | Q8_0 GGUF | Q4_K_M GGUF |
| --- | --- | --- | --- |
| 4B | [Piccolo-4B](https://huggingface.co/agentscope-ai/Piccolo-4B) | [Piccolo-4B-Q8_0](https://huggingface.co/agentscope-ai/Piccolo-4B-Q8_0) | [Piccolo-4B-Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-4B-Q4_K_M) |
| 9B | [Piccolo-9B](https://huggingface.co/agentscope-ai/Piccolo-9B) | [Piccolo-9B-Q8_0](https://huggingface.co/agentscope-ai/Piccolo-9B-Q8_0) | [Piccolo-9B-Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-9B-Q4_K_M) |
| 27B | [Piccolo-27B](https://huggingface.co/agentscope-ai/Piccolo-27B) | [Piccolo-27B-Q8_0](https://huggingface.co/agentscope-ai/Piccolo-27B-Q8_0) | [Piccolo-27B-Q4_K_M](https://huggingface.co/agentscope-ai/Piccolo-27B-Q4_K_M) |

QwenPaw integration is tracked in [draft PR #8463](https://github.com/agentscope-ai/QwenPaw/pull/8463). Use its [local model guide](https://github.com/Xinji-Mai/QwenPaw/blob/codex/blink-local-decision/docs/local-piccolo.md): install the adapted llama.cpp runtime, download a Piccolo GGUF, click **Start**, and select the default **Decision model**. Automatic review and decision-model compaction have separate opt-in settings. The catalog recommends Q8_0; published Q4_K_M variants are available by their Hugging Face IDs.

Inference uses bidirectional prompt attention in the full-attention layers, the exact `flex_twice` layout, and candidate-token probabilities. Ordinary causal chat inference does not implement this contract. The original checkpoints include `piccolo_inference.py` and `piccolo_layout.py` for reference inference.

Q4 model cards disclose synthetic regressions of 265 requests / 556 judgments per size, quantization differences, and limitations. These are not independent task benchmarks or calibrated safety results. Historical Arena trajectories retain their original checkpoint identities and are separate from this model release.

Playground: [Decision](https://decisionplayground.agentscope.io/). Source: [agentscope-ai/Piccolo](https://github.com/agentscope-ai/Piccolo).
