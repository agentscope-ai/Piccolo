"""Local Piccolo inference using the model and processor bundled with an HF export."""

import argparse
import json
import math
from pathlib import Path


def checkpoint_format(directory):
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text())
    if config.get("model_type") == "piccolo_qwen3_5":
        return "hf"
    if config.get("model_type") == "qwen3_5" and (directory / "decision-inference.json").is_file():
        return "legacy"
    raise ValueError("Expected a current Piccolo HF export or a legacy full Piccolo checkpoint")


def infer_current(directory, payload, *, device="cuda:0", dtype="bfloat16"):
    import torch
    from transformers import AutoModel, AutoProcessor

    if not isinstance(payload, dict) or set(payload) - {"state", "questions", "assets"}:
        raise ValueError("Request accepts only state, questions and optional assets")
    if checkpoint_format(directory) != "hf":
        raise ValueError("Current inference requires a Piccolo HF export")
    processor = AutoProcessor.from_pretrained(
        directory,
        trust_remote_code=True,
        local_files_only=True,
    )
    # Validate and encode every question before allocating the model weights.
    items = processor.encode_request(payload)
    model = (
        AutoModel.from_pretrained(
            directory,
            trust_remote_code=True,
            local_files_only=True,
            dtype=getattr(torch, dtype),
            attn_implementation="sdpa",
        )
        .to(device)
        .eval()
    )
    results = []
    with torch.inference_mode():
        for item in items:
            inputs = item.inputs.to(model.device)
            output = model(**inputs)
            logits = output.logits[0].float().cpu().tolist()
            probabilities = output.probabilities[0].float().cpu().tolist()
            if not all(math.isfinite(x) for x in [*logits, *probabilities]):
                raise ValueError("Non-finite candidate scores")
            if len(probabilities) != len(item.option_keys):
                raise ValueError("Candidate scores do not match the encoded option order")
            results.append(
                {
                    "question_id": item.question_id,
                    "kind": payload["questions"][item.question_id]["type"],
                    "option_keys": item.option_keys,
                    "candidate_ids": inputs["candidate_token_ids"][0].cpu().tolist(),
                    "input_ids": inputs["input_ids"][0].cpu().tolist(),
                    "bidirectional_prompt": {
                        "candidate_logits": logits,
                        "probabilities": probabilities,
                    },
                }
            )
    return {
        "model": Path(directory).name,
        "checkpoint_format": "hf",
        "dtype": dtype,
        "attention_mode": "bidirectional_prompt",
        "linear_attention": "unchanged",
        "prefix_cache": False,
        "chunked_prefill": False,
        "probability_temperature": 1.0,
        "layout": {
            "source": "checkpoint",
            "model_input_tokens": sum(len(row["input_ids"]) for row in results),
        },
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float32"], default="bfloat16")
    parser.add_argument("--output")
    parser.add_argument(
        "--compare-causal",
        action="store_true",
        help="Legacy checkpoints only; current HF exports fix attention semantics",
    )
    args = parser.parse_args()
    if checkpoint_format(args.model) == "legacy":
        from legacy.piccolo_legacy import main as legacy_main

        return legacy_main(args)
    if args.compare_causal:
        parser.error("--compare-causal applies only to legacy checkpoints")
    payload = json.loads(Path(args.request).read_text())
    output = infer_current(args.model, payload, device=args.device, dtype=args.dtype)
    text = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
