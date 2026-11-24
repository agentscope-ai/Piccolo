# Piccolo SGLang guide

[Back to the inference overview](../README.md)

This guide covers plugin installation, server startup and `/v1/systemone` calls.
Piccolo and PiccoloLoop share the same interface. See the overview for common
[inputs and outputs](../README.md#inputs-and-outputs).

## Installation and startup

Prepare a compatible SGLang runtime with native SystemOne candidate scoring,
processor-output multimodal inputs and bidirectional Qwen3.5 full attention.
The plugin requires no runtime source patch:

```bash
python -m pip install ./inference/sglang
bash inference/sglang/scripts/launch_sglang.sh /models/Piccolo 0 18604
```

The three positional arguments are checkpoint path, GPU and port. The launcher
uses BF16, TP1 and a 32K context, binds to `127.0.0.1`, and derives the served
model name from the checkpoint directory name. Append native SGLang arguments
after the positional arguments. `HOST` controls the bind address;
`CONTEXT_LENGTH` and `MEM_FRACTION_STATIC` control context and memory budgets.
Use the native `--api-key` argument for authentication.

The plugin name is `piccolo`. Include it in `SGLANG_PLUGINS` for manual launches.
For Python API use, call `sglang.srt.plugins.load_plugins()` before constructing
ModelConfig or ServerArgs.

The distribution is `piccolo-serving`; the Python package is `piccolo_serving`.

## HTTP requests

The request model name must match the server. This example uses `/models/Piccolo`:

```bash
curl --fail-with-body http://127.0.0.1:18604/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{"model":"Piccolo","state":"The sky is blue.","questions":{"q":{"type":"noul","instructions":"Is the sky blue?"}}}'
```

For image requests, use the overview's assets format and add the same `model`
field. HTTP image sources support HTTP/HTTPS URLs and `data_base64`;
client-supplied local paths are rejected.

Responses contain `model`, `answers` and `usage`. Answers are keyed by question ID:

| Type | Main fields |
| --- | --- |
| `choice` | `choice`, candidate `probabilities`, `confidence` |
| `noul` | `noul`, the probability that the proposition is true |
| `score` | `score`, level `probabilities`, `confidence`, `legend` |

Candidate scoring generates no answer tokens, so `usage.output_tokens` is 0.
Image I/O happens outside the shared processor lock, preventing slow downloads
from blocking other requests' encoding.

## Runtime constraints

The plugin adapts only explicitly tagged Piccolo and PiccoloLoop checkpoints;
other models retain native settings. Both architectures disable prefix reuse and
chunked prefill. Complete prompts must fit in one prefill; overlong inputs fail.
Configuration, request schemas and input processing come from the checkpoint.
The serving package does not depend on checkpoint preparation tools.

Piccolo uses the native Qwen3.5 execution class. PiccoloLoop selects a dedicated
class from `loop_config` and requires:

- Unquantized inference, TP=PP=1 and `kv_cache_dtype=auto`.
- Physical `layer_types` matching the runtime's `full_attention_interval`.
- No MTP, deepstack or incremental generation.
- Disabled language CUDA graphs, empty GDN scan states per pass, and materialized residuals between physical layers.

When vision loop blocks are nonempty, the execution class disables vision CUDA
graphs before constructing the vision model. Piccolo and language-only PiccoloLoop
do not change `SGLANG_VIT_ENABLE_CUDA_GRAPH`; no manual setting is needed.

The plugin uses runtime lifecycle interfaces. After changing runtimes, verify
server initialization and representative text/image requests on the deployment GPU.

## Source layout

Paths below are relative to `inference/sglang/piccolo_serving/`:

| Path | Responsibility |
| --- | --- |
| `plugin.py` | Register initialization, request validation, server configuration and warmup hooks |
| `models/__init__.py` | Select the adapter by checkpoint type |
| `models/piccolo/adapter.py` | Adapt native Qwen3.5 configuration and enforce complete-prompt constraints |
| `models/piccolo_loop/adapter.py` | Configure loop execution and its additional constraints |
| `models/piccolo_loop/modeling.py`, `execution.py` | Execute native recurrence, schedule layers and mix hidden states in FP32 |
| `encoding.py` | Use checkpoint schemas and processors to prepare native scoring inputs |
| `serving.py` | Bind HTTP routes and convert structured responses |

Each architecture has its own package. Piccolo reuses the native model and needs
no separate `modeling.py`.
