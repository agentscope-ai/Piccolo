# Piccolo inference overview

Piccolo and PiccoloLoop use the same candidate-scoring protocol. Normalized HF
checkpoints support local Transformers inference and HTTP serving through SGLang.

## Getting started

| Task | Guide | Scope |
| --- | --- | --- |
| Local HF inference | [HF guide](hf/README.md) | AutoModel/AutoProcessor, input encoding and result handling |
| HTTP serving | [SGLang guide](sglang/README.md) | Installation, startup, HTTP requests and runtime constraints |
| Checkpoint preparation | [Checkpoint tools](../scripts/checkpoints/README.md) | Qwen3.5 conversion, source packaging, loop configuration and structural validation |

`inference/hf/` contains the Transformers example, dependencies and usage guide.
`inference/sglang/` contains the serving plugin and native execution adapters.
Model, processor and template sources for checkpoint preparation live in
`scripts/checkpoints/`; inference does not depend on those tools.

This overview defines the shared inputs and execution semantics. Each backend
guide covers its own invocation method. Run all commands from the repository root.

## Checkpoint requirements

| Architecture | `model_type` | HF model class |
| --- | --- | --- |
| Piccolo | `piccolo_qwen3_5` | `PiccoloModel` |
| PiccoloLoop | `piccolo_qwen3_5_loop` | `PiccoloLoopModel` |

A complete checkpoint provides `config.json`, Safetensors weights, processor and
tokenizer assets, `chat_template.jinja`, and the Python modules referenced by
`auto_map`. Configuration, input processing and templates are loaded from the
checkpoint. PiccoloLoop defines its language and vision recurrence in
`config.json` through `loop_config`.

The candidate-scoring interface described here requires a normalized Piccolo or
PiccoloLoop checkpoint. For historical models, use the inference code commit
specified in their Hugging Face model cards. Prepare Qwen3.5 checkpoints with
the checkpoint tools before using this interface. Changing the template changes
inference semantics; historical published scores do not validate a new configuration.

Published GGUF models use the compatible llama.cpp runtime managed by
[QwenPaw](../docs/QWENPAW.md). See the [model guide](../docs/MODELS.md) for formats
and pinned revisions.

## Inputs and outputs

HF requests contain `state`, the complete `questions` mapping and optional image
`assets`. HTTP requests add `model`, which must match the served model name.

```json
{
  "state": "The sky is blue.",
  "questions": {
    "q": {"type": "noul", "instructions": "Is the sky blue?"}
  }
}
```

| Question type | `criteria` | Meaning |
| --- | --- | --- |
| `choice` | Mapping from option keys to descriptions | Score and normalize over the candidates |
| `noul` | Optional `true` / `false` descriptions | Estimate the probability that a proposition is true |
| `score` | Ordered list of level descriptions, from lowest to highest | Score the ordered levels |

Images are referenced by asset ID from the state, questions or candidate fields.
Replace `data_base64` below with actual PNG data. An asset may also use
`{"type":"image","url":"https://..."}`.

```json
{
  "state": {"image": "photo"},
  "questions": {
    "q": {"type": "noul", "instructions": "Is the image red?"}
  },
  "assets": {
    "photo": {"type": "image", "format": "png", "data_base64": "..."}
  }
}
```

The model reads candidate logits at the last real prompt token and applies a
softmax over the candidate set at temperature 1. HF probabilities follow the
processor's `option_keys`; `noul` uses false, true order. The HTTP service converts
these scores into structured answers and returns the probability of true for `noul`.

## Execution semantics

- Full-attention layers are bidirectional; GDN layers retain causal scans.
- Each call processes an independent complete prompt, without incremental generation, prefix reuse or silent truncation.
- Models return candidate scores and probabilities without generating answer tokens.
- PiccoloLoop shares physical layer weights across passes. Each GDN pass starts with an empty scan state while hidden states continue from the preceding pass.
