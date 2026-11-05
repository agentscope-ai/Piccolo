# Inference and local integration

Piccolo supports local HF inference and SGLang serving. Both current paths read
the prompt, image budgets and context limit from the same HF checkpoint. For
published GGUF models, use the compatible llama.cpp runtime managed by
[QwenPaw](../docs/QWENPAW.md). See the [model matrix](../docs/MODELS.md).

## Current HF reference inference

Run from the repository root with a current Piccolo HF export:

```bash
python -m pip install -r inference/reference/requirements.txt
python inference/reference/piccolo_inference.py \
  --model /models/Piccolo-current --request examples/request.json --device cuda:0
```

The reference uses the checkpoint's bundled `AutoProcessor` and `AutoModel`, with
no serving or training package dependency. Text and image assets pass through
the complete multimodal model. CPU inference uses `--device cpu --dtype float32`;
see the [reference guide](reference/README.md) for requirements and output fields.

HF model sources and checkpoint tools live in the independent [HF component](hf/README.md).

## SGLang server

The [SGLang plugin](sglang/README.md) provides a unified `/v1/systemone` endpoint
for text and vision. It requires current HF exports and native SystemOne scoring,
multimodal input and bidirectional full-attention support in the runtime. The
adapter is installed as an independent plugin; no runtime patch is needed.

## Current decision protocol

- **Input:** `state`, complete `questions` and optional image `assets`, encoded by
  the checkpoint's `chat_template.jinja` and processor settings.
- **Attention:** full-attention layers are bidirectional; linear-attention layers
  retain their original causal computation.
- **Output:** read candidate logits at the last real prompt token and apply a
  temperature-1 softmax over the candidate set. No answer tokens are generated.
- **Runtime:** complete independent prompts, no prefix reuse, chunked prefill or
  silent truncation.

## Historical release checkpoints and GGUF

The fixed model revisions in the release manifest use the historical Flex
protocol. The reference entry point still detects full `qwen3_5` checkpoints
with `decision-inference.json` and delegates to its preserved legacy text path:

```bash
hf download agentscope-ai/Piccolo-4B --revision ae30995bef9b0f0fa7d12adf517c63cdbc4d10d2 --local-dir Piccolo-4B
python inference/reference/piccolo_inference.py \
  --model Piccolo-4B --request examples/request.json --device cuda:0
```

The historical `flex_twice` layout rereads requests whose single-pass input fits
within 3,000 tokens and whose compiled rows fit the context window. Candidate
readout is at `Answer: (`. QwenPaw allows up to 8,192 tokens per compiled row;
`blink` in GGUF files is its serialized architecture name. The Flex layout retains
its [MIT notice](reference/THIRD_PARTY_LICENSES.md).

Historical checkpoints require [explicit migration](hf/README.md#historical-full-checkpoint-conversion)
before current SGLang serving. Changing the prompt creates a different inference
configuration; historical benchmark scores do not validate that configuration.

[Examples](../examples/README.md) · [Models](../docs/MODELS.md) · [Evaluation](../evaluation/README.md)
