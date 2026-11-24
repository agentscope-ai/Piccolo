"""Score candidates with the Transformers model and processor bundled in a checkpoint."""

import torch
from transformers import AutoModel, AutoProcessor

model_path = "/models/Piccolo"  # Use the corresponding checkpoint path for PiccoloLoop.
device = "cuda:0"
dtype = torch.bfloat16

payload = {
    "state": "The sky is blue.",
    "questions": {"q": {"type": "noul", "instructions": "Is the sky blue?"}},
}

processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_path,
    trust_remote_code=True,
    dtype=dtype,
    attn_implementation="sdpa",
).to(device).eval()

with torch.inference_mode():
    for item in processor.encode_request(payload):
        result = model(**item.inputs.to(model.device))
        print(item.question_id, item.option_keys, result.logits, result.probabilities)
