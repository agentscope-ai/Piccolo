# Piccolo reference inference

The entry point detects the checkpoint format. Current HF exports use their
bundled `AutoProcessor` and `AutoModel`; the reference script requires neither
a serving runtime nor a training package. It forwards text and image tensors
through the complete multimodal model. The checkpoint supplies its prompt,
image budgets, context limit and attention implementation.

From the repository root:

```bash
python -m pip install -r inference/reference/requirements.txt
python inference/reference/piccolo_inference.py \
  --model /models/Piccolo-current --request examples/request.json \
  --device cuda:0 --output result.json
```

Current exports contain `config.json` with `model_type=piccolo_qwen3_5`, processor
and tokenizer assets, `chat_template.jinja`, bundled AutoClass Python modules
and full Safetensors weights. `decision-inference.json` is not required.
Inputs accept `state`, `questions` and optional `assets`, as in the
[SGLang request examples](../sglang/README.md#requests). Image assets may be
referenced from state or questions. No prompt truncation or answer generation
is performed.

For each question, `results` contains `option_keys`, `candidate_ids`, `input_ids`
and `bidirectional_prompt.candidate_logits` / `probabilities`. Read probabilities
in `option_keys` order: current HF noul candidates are `false`, then `true`.
The script does not reverse them to the server's internal yes/no order.
`layout.source=checkpoint` identifies the current prompt path. Historical scores
obtained with a different prompt are not measurements of the current layout.

CPU inference uses `--device cpu --dtype float32`. Use a CPU environment without
optional GPU-only FLA or causal-conv1d packages; those packages may otherwise be
selected by Transformers even for CPU tensors.

## Historical full checkpoints

Published release checkpoints using `model_type=qwen3_5` and
`decision-inference.json` automatically use [piccolo_legacy.py](legacy/piccolo_legacy.py).
That path retains its text-only Flex layout, 3,000-token reread threshold,
`Answer: (` readout and `--compare-causal` option. Its CLI and result format
remain available through the same entry point. Current HF exports reject
`--compare-causal`, since their model implementation fixes the attention policy.

Do not mix the two checkpoint layouts. Converting a historical checkpoint
requires explicitly selecting a frozen template and budgets; see the
[checkpoint migration instructions](../hf/README.md#historical-full-checkpoint-conversion).
The legacy Flex layout retains its [MIT notice](THIRD_PARTY_LICENSES.md).
