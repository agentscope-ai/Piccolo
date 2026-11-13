# Piccolo inference on SGLang

Independent native plugin for `/v1/systemone` text and image scoring. It consumes
current Piccolo HF exports and the shared [HF component](../hf/README.md).
The runtime must support native SystemOne candidate scoring, processor-output
multimodal input and bidirectional Qwen3.5 full attention. No runtime source
patch is required.

From the repository root, after installing a compatible SGLang runtime:

```bash
python -m pip install ./inference/hf ./inference/sglang
piccolo-checkpoint validate /models/Piccolo-current
bash inference/sglang/scripts/launch_sglang.sh /models/Piccolo-current 0 18604
```

The script serves text and vision with BF16, TP1, 32K context and localhost by
default. Append native SGLang arguments after the three positional arguments.
Set `HOST` to expose a server deliberately and use `--api-key` for authentication.
The plugin name is `piccolo`; manual launches must include it in `SGLANG_PLUGINS`.
For direct library use, call `sglang.srt.plugins.load_plugins()` before creating
ModelConfig or ServerArgs.

| Module | Responsibility |
| --- | --- |
| `plugin.py` | Register lifecycle hooks and adapt initialization, validation and warmup. |
| `model.py` | Adapt the private HF configuration and enforce Piccolo execution constraints. |
| `encoding.py` | Load request images before locking the shared processor, then prepare native inputs. |
| `serving.py` | Bind the schema and native SystemOne handler, preserve route dependencies and convert responses. |

Only explicit `piccolo_qwen3_5` checkpoints are adapted. Other models retain
native settings and handlers. Full attention is bidirectional; GDN remains
causal. Prefix reuse and chunked prefill are disabled. Overlong requests fail
without truncation. Candidate scoring generates zero answer tokens. Image
I/O happens outside the processor lock, allowing text requests to proceed while
another request waits for an image.

The plugin uses runtime lifecycle internals. When changing runtimes, verify server initialization and representative
text/image requests on the deployment GPU. Checkpoint format,
conversion and model code belong to the HF component, not the adapter.

## Requests

```bash
curl --fail-with-body http://127.0.0.1:18604/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{"model":"Piccolo-current","state":"The sky is blue.","questions":{"q":{"type":"noul","instructions":"Is the sky blue?"}}}'
```

For vision, reference image asset IDs from state or question fields:

```json
{
  "model": "Piccolo-current",
  "state": {"image": "photo"},
  "questions": {"q": {"type": "noul", "instructions": "Is the image red?"}},
  "assets": {"photo": {"type": "image", "format": "png", "data_base64": "..."}}
}
```

Image assets support HTTP/HTTPS `url` and `data_base64`; client-supplied local
paths are rejected. The historical `/v1/decisions` vision payload is replaced by
this asset protocol. Legacy full checkpoints require
[explicit conversion](../hf/README.md#historical-full-checkpoint-conversion).
