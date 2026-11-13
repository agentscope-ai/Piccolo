# Piccolo HF

Standalone Piccolo configuration, model, processor and checkpoint tools.
SGLang and training packages are not required. The source modules are flat so
exports can copy them directly into an HF directory without an AST packager.
The exported AutoClass names remain `piccolo_configuration.PiccoloConfig`,
`piccolo_modeling.PiccoloModel` and `piccolo_processing.PiccoloProcessor`.

From the repository root:

```bash
python -m pip install ./inference/hf
piccolo-checkpoint validate /models/Piccolo-current
```

Validation loads local configuration and processor assets, checks the frozen
template, verifies shard-index entries and compares required parameter names and
shapes against a model constructed on the meta device. It reads Safetensors
headers without loading the full weight tensors into memory. This verifies
structural completeness; numerical quality still requires inference evaluation.

```python
from transformers import AutoModel, AutoProcessor

processor = AutoProcessor.from_pretrained(path, trust_remote_code=True)
model = AutoModel.from_pretrained(path, trust_remote_code=True, attn_implementation="sdpa")
for item in processor.encode_request(payload):
    result = model(**item.inputs.to(model.device))
    print(item.question_id, item.option_keys, result.probabilities)
```

Text and image requests use the checkpoint's frozen prompt and image budget.
Noul candidates follow false/true order. Full attention is bidirectional, GDN
remains causal, and incremental decoding and KV caching are rejected.

## Historical full checkpoint conversion

Convert into a new directory with explicit inference settings:

```bash
piccolo-checkpoint convert /models/Piccolo-legacy /models/Piccolo-current \
  --template inference/hf/piccolo_hf/piccolo_qwen35.jinja \
  --image-min-pixels 65536 --image-max-pixels 1638400 --max-length 32768
```

The source must contain full Qwen3.5 VL Safetensors weights and processor assets.
GGUF files cannot be converted by this tool. Failed conversions remove the new
output directory; the source is preserved. Weight files are hardlinked when
possible and copied otherwise. Treat linked weights as immutable. License and
notice files are preserved.

Selecting a different template changes inference semantics. Historical published
scores do not validate the new prompt. Released revisions in the model manifest
remain unchanged. Third-party notices are in [licenses](piccolo_hf/licenses/).
