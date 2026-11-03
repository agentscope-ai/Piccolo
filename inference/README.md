# Inference and local integration

Piccolo provides full Safetensors checkpoints and three GGUF formats. See the [model matrix](../docs/MODELS.md). For local use, start the compatible llama.cpp runtime managed by [QwenPaw](../docs/QWENPAW.md). For full checkpoints, use the [reference implementation](reference/piccolo_inference.py).

## Reference inference

Run from the repository root:

```bash
python -m pip install -r inference/reference/requirements.txt huggingface_hub
hf download agentscope-ai/Piccolo-4B --revision ae30995bef9b0f0fa7d12adf517c63cdbc4d10d2 --local-dir Piccolo-4B
python inference/reference/piccolo_inference.py \
  --model Piccolo-4B --request examples/request.json --device cuda:0
```

The model directory must contain `decision-inference.json`, the tokenizer and all weight shards. CPU inference uses `--device cpu --dtype float32`. See the [request and output example](../examples/README.md). The implementation includes candidate-row scoring, the attention mask and prompt compilation. The FlexDM layout retains its [MIT notice](reference/THIRD_PARTY_LICENSES.md).

## SGLang server

The [SGLang plugin](piccolo_inference_sglang/README.md) provides `/v1/systemone` for text and `/v1/decisions` for vision, with installation, launch and evaluation commands.

## Decision protocol

- **Input:** native `state` and complete `questions`, using the `flex_twice` layout. Rereading is used when the single-pass request fits within 3,000 tokens and each compiled row fits the context window.
- **Attention:** Qwen3.5 full-attention layers attend bidirectionally over the complete prompt; linear-attention layers retain their original computation.
- **Output:** read single-token candidate logits at `Answer: (` and apply a temperature-1 softmax. No answer text is generated.
- **Runtime:** disable prefix reuse, causal chunked prefill and silent truncation. QwenPaw allows up to 8,192 tokens per compiled prompt row.

Use a runtime that implements this decision protocol. The `blink` identifier in GGUF files is the serialized architecture name.

[Models](../docs/MODELS.md) · [Benchmark results and reproduction](../evaluation/README.md)
