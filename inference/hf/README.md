# Piccolo HF guide

[Back to the inference overview](../README.md)

This guide covers Transformers inference for Piccolo and PiccoloLoop. Both load
their model, processor and template from the checkpoint, without installing this
repository's model definitions or serving plugin. See the overview for shared
[inputs and outputs](../README.md#inputs-and-outputs).

## Installation

```bash
python -m pip install -r inference/hf/requirements.txt
```

The example defaults to `device="cuda:0"`, `dtype=torch.bfloat16` and SDPA. For CPU
inference, set `device="cpu"` and `dtype=torch.float32`. Avoid optional GPU-only
FLA or causal-conv1d packages in a CPU environment, since Transformers may select
kernels that cannot run on CPU.

## Using Transformers

[example.py](example.py) is a complete minimal example. Set `model_path`, `device`,
`dtype` and `payload`, then run it from the repository root:

```bash
python inference/hf/example.py
```

The example calls `AutoProcessor.from_pretrained()` and
`AutoModel.from_pretrained()`, encodes requests with `processor.encode_request()`,
and runs the model forward pass. Piccolo and PiccoloLoop use the same flow.

`encode_request()` returns one encoded item per question. For a single question,
you can also use `processor(payload)`. Image requests pass through the complete
multimodal model. Probabilities always follow `item.option_keys`. The model and
processor support independent reloading after `save_pretrained()`.

### Optional OCR

With a checkpoint exported using the current tools, install
`opencv-python-headless` and `pyclipper`, then load the two PP-OCRv5 models
once and pass the backend when encoding:

```python
ocr = processor.load_ocr(
    "/models/PP-OCRv5_mobile_det_safetensors",
    "/models/en_PP-OCRv5_mobile_rec_safetensors",
    device="cuda:0",
)
items = processor.encode_request(payload, ocr=ocr)
```

The default device is CPU. Model paths can be omitted when the
[detector](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_safetensors) and
[English recognizer](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_safetensors)
are in the local Hugging Face cache. Image requests include one transcription
per image in prompt order and still pass the original image inputs to the model.

## Requests and results

To use an existing request file, replace the example's `payload` with:

```python
import json
from pathlib import Path

payload = json.loads(Path("examples/request.json").read_text())
```

Inputs contain `state`, `questions` and optional `assets`. They do not need the
`model` field used by HTTP requests.

| Field | Meaning |
| --- | --- |
| `item.question_id` | Current question ID |
| `item.option_keys` | Candidate order |
| `item.inputs` | Encoded tensors ready to pass to the model |
| `result.logits` | Candidate scores |
| `result.probabilities` | Probabilities normalized over the candidate set |

Candidate projection uses only the requested LM-head rows. Projection and softmax
run in FP32 with autocast disabled; the backbone retains its configured dtype.
This policy also applies to PiccoloLoop.

HF `noul` probabilities use false, true order. The model does not generate answer
tokens, and the checkpoint's processor rejects prompts exceeding its context limit.

## PiccoloLoop

PiccoloLoop uses the same calls as Piccolo, without a separate profile or extra
inference parameters. Language and vision blocks execute according to the
checkpoint configuration, with one weight set per physical layer.

Each loop block completes all its passes before proceeding to later layers.
Every pass computes `h_next = h + alpha × (block(h) - h)` in FP32 and casts the
result back to the input dtype. Candidate scoring is unchanged; inference does
not use `generate()` or reuse KV/GDN caches.

To choose loop ranges or prepare a checkpoint, see the checkpoint tools'
[loop configuration](../../scripts/checkpoints/README.md#loop-configuration).
Existing checkpoints load their bundled inference code. To adopt an updated
readout implementation, re-export the checkpoint with the current checkpoint
tools; updating this repository alone does not update existing checkpoint code.
