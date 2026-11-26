# Piccolo checkpoint tools

These tools convert complete Qwen3.5 VL Safetensors checkpoints into Piccolo or
PiccoloLoop HF format. This directory also contains export sources, input
templates and structural validation tools. HF and SGLang inference in
`inference/` do not depend on this directory.

## Directory responsibilities

| Path | Contents |
| --- | --- |
| `checkpoint.py` | Script entry point for conversion and validation |
| `piccolo_checkpoint/checkpoint.py` | Conversion, asset export and weight structure validation |
| `piccolo_checkpoint/*_configuration.py`, `*_modeling.py` | Model sources bundled with checkpoints |
| `piccolo_checkpoint/piccolo_processing.py`, `common_*.py`, `piccolo_images.py`, `piccolo_ocr.py` | Input processing sources bundled with checkpoints |
| `piccolo_checkpoint/piccolo_qwen35.jinja` | Decision template source |

Export copies the required sources into the checkpoint root, preserving module
names such as `piccolo_configuration`, `piccolo_modeling`,
`piccolo_loop_configuration`, `piccolo_loop_modeling` and `piccolo_processing`.
Inference loads the files inside the checkpoint.

## Installation and usage

Install the tools and their dependencies from the repository root:

```bash
python -m pip install ./scripts/checkpoints
```

Use the installed `piccolo-checkpoint` command or the script entry point below.

### Piccolo

```bash
python scripts/checkpoints/checkpoint.py convert /models/Qwen35-source /models/Piccolo \
  --template scripts/checkpoints/piccolo_checkpoint/piccolo_qwen35.jinja \
  --image-min-pixels 65536 --image-max-pixels 1638400 --max-length 32768
```

### PiccoloLoop

Follow the [loop configuration](#loop-configuration) format and save the value of
`loop_config` to a local JSON file, such as `/path/to/loop-config.json`. The file
contains only that object, without the outer model identity fields.

```bash
python scripts/checkpoints/checkpoint.py convert /models/Qwen35-source /models/Piccolo-loop \
  --loop-config /path/to/loop-config.json \
  --template scripts/checkpoints/piccolo_checkpoint/piccolo_qwen35.jinja \
  --image-min-pixels 65536 --image-max-pixels 1638400 --max-length 32768
```

`--loop-config` selects the loop architecture. The example ranges below apply
only to the corresponding 24-layer 2B recipe; supply appropriate ranges for other
models. Reconverting a loop checkpoint preserves its architecture and loop
configuration by default. Piccolo exports reject loop configurations.

### Structural validation

```bash
python scripts/checkpoints/checkpoint.py validate /models/Piccolo-loop
```

Validation loads the checkpoint's AutoConfig, AutoProcessor and AutoModel, then
checks the frozen template, shard index, parameter names and shapes. Safetensors
headers supply weight shapes, and the model is constructed on the meta device,
without loading full weight tensors. Structural validation does not establish
numerical equivalence or model quality.

## Conversion boundaries

The source must provide complete Qwen3.5 VL weights and processor/tokenizer assets.
GGUF is not supported. The output directory must be new; failed conversions
remove that output while preserving the source. Weights are hardlinked when
possible and copied otherwise. Treat linked weights as immutable.

Changing the template changes inference semantics; historical published scores
do not validate a new configuration. Conversion does not change pinned model
revisions in the release manifest. Third-party notices are retained in
[licenses](piccolo_checkpoint/licenses/).

## Loop configuration

Checkpoints retain standard HF weights, tokenizer, processor and
`chat_template.jinja` files. The `auto_map` in `config.json` points to independent
Python modules bundled with the checkpoint:

```json
{
  "model_type": "piccolo_qwen3_5_loop",
  "architectures": ["PiccoloLoopModel"],
  "auto_map": {
    "AutoConfig": "piccolo_loop_configuration.PiccoloLoopConfig",
    "AutoModel": "piccolo_loop_modeling.PiccoloLoopModel"
  },
  "loop_config": {
    "text": {
      "blocks": [
        {"layers": [8, 12], "alphas": [1, 0.375]},
        {"layers": [12, 16], "alphas": [1, 0.375]}
      ]
    },
    "vision": {"blocks": []}
  }
}
```

This is a configuration fragment. A complete configuration also includes the
language and vision towers and special token settings. `loop_config` is required;
`{}` means neither tower has additional recurrence. There is no separate
configuration format version field.

| Field | Constraints |
| --- | --- |
| `text`, `vision` | Optional; omitted towers default to `{"blocks": []}` |
| `blocks` | Required when a tower is explicitly provided; an ordered list |
| `layers` | Two integers defining a zero-based half-open range `[start,end)`, within the physical depth |
| `alphas` | A nonempty list of finite values in `[0,1]`, including the first pass |

Blocks must be ordered and disjoint; adjacent blocks are allowed. Unknown fields,
nested blocks and learnable coefficients are unsupported. Physical language
depth comes from `text_config.num_hidden_layers`; vision depth comes from
`vision_config.depth`. Each physical layer's weights are saved once. Recurrence
does not increase the number of parameter layers.

Each block completes all its passes before the next layer or block. Two adjacent
blocks with two passes execute as `A → A → B → B`. Layers outside loop blocks
execute once. Each pass updates hidden states as follows:

```text
h_next = h + alpha × (block(h) - h)
```

Mixing uses FP32 and casts the result back to the input dtype. `[0.5,0.5]` applies
a half-step update on both passes. `[0]` still computes the block but retains its
input at the exit. `[1]` is equivalent to ordinary single-pass execution.
Language and vision recurrence are configured independently. Vision recurrence
runs after patch embedding and before the merger. Each GDN pass starts with an
empty scan state, while hidden states continue from the preceding pass.
