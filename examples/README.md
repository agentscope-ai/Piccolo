# Decision examples

[request.json](request.json) asks whether a read-only tool operation may delete or overwrite data. The example returns candidate probabilities without executing the tool. The [workflow collection](workflows/README.md) contains 12 bilingual examples from agent and data workflows.

## Using the request example

Load `request.json` and run inference with the Transformers processor and model;
see the [HF guide](../inference/hf/README.md#using-transformers). Shared request
formats and image assets are documented in the
[inference overview](../inference/README.md#inputs-and-outputs).

For HTTP calls, see the [SGLang guide](../inference/sglang/README.md#http-requests).

## QwenPaw

After [starting a local model](../docs/QWENPAW.md), run this check in the QwenPaw Python environment:

```bash
python scripts/check_qwenpaw_local.py
```

A successful check reports `status=local_decision_interface_ok`, the returned model identity and the synthetic review and context-retention results. A failed check exits with a nonzero status.

[Inference protocol](../inference/README.md) · [Evaluation](../evaluation/README.md)
