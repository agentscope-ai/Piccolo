# Decision examples

[request.json](request.json) asks whether a read-only tool operation may delete or overwrite data. The example returns candidate probabilities without executing the tool. The [workflow collection](workflows/README.md) contains 12 bilingual examples from agent and data workflows.

## Full checkpoint

Run from the repository root in a Python environment with sufficient memory for the 4B weights:

```bash
python -m pip install -r inference/reference/requirements.txt huggingface_hub
hf download agentscope-ai/Piccolo-4B --revision ae30995bef9b0f0fa7d12adf517c63cdbc4d10d2 --local-dir Piccolo-4B
python inference/reference/piccolo_inference.py \
  --model Piccolo-4B --request examples/request.json --device cuda:0 --output result.json
```

For CPU inference, use `--device cpu --dtype float32`. The output includes `attention_mode`, `layout` and `results`. Each `option_keys` list corresponds to `bidirectional_prompt.probabilities`; the probabilities sum to one.

## QwenPaw

After [starting a local model](../docs/QWENPAW.md), run this check in the QwenPaw Python environment:

```bash
python scripts/check_qwenpaw_local.py
```

A successful check reports `status=local_decision_interface_ok`, the returned model identity and the synthetic review and context-retention results. A failed check exits with a nonzero status.

[Inference protocol](../inference/README.md) · [Evaluation](../evaluation/README.md)
