"""Read, export and validate complete Piccolo HF checkpoints."""

import argparse
import json
import os
import shutil
from pathlib import Path

MODULES = (
    "piccolo_configuration",
    "piccolo_modeling",
    "piccolo_processing",
    "common_inputs",
    "common_media",
    "piccolo_images",
)


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def read_hf_inference_assets(directory):
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text())
    if config.get("model_type") != "piccolo_qwen3_5" or config.get("architectures") != [
        "PiccoloModel"
    ]:
        raise ValueError("Expected a current Piccolo HF checkpoint")
    if config.get("auto_map", {}).get("AutoModel") not in {
        "piccolo_modeling.PiccoloModel",
        "modeling_piccolo.PiccoloModel",
    }:
        raise ValueError("Incomplete Piccolo HF model configuration")
    processor = json.loads((directory / "processor_config.json").read_text())
    if not isinstance(processor.get("auto_map", {}).get("AutoProcessor"), str):
        raise ValueError("Incomplete HF processor export")
    template = (directory / "chat_template.jinja").read_text()
    from transformers.utils.chat_template_utils import _compile_jinja_template

    if not template.strip():
        raise ValueError("Frozen chat template must not be empty")
    _compile_jinja_template(template)
    image = processor.get("image_processor")
    if image is None:
        image = json.loads((directory / "preprocessor_config.json").read_text())
    size = image["size"]
    low, high = size["shortest_edge"], size["longest_edge"]
    if type(low) is not int or type(high) is not int or not 0 < low <= high:
        raise ValueError("Invalid Piccolo image budget")
    limit = processor.get("max_length")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("max_length must be a positive integer")
    return {
        "model_type": "piccolo_qwen3_5",
        "processor_options": {} if limit is None else {"max_length": limit},
        "image_size": {"shortest_edge": low, "longest_edge": high},
    }, template


def write_hf_inference_assets(
    directory, *, template, image_size, processor_options=None, model_type="piccolo_qwen3_5"
):
    if model_type != "piccolo_qwen3_5":
        raise ValueError("Only Piccolo exports are supported")
    options = dict(processor_options or {})
    if options.keys() - {"max_length"}:
        raise ValueError("Piccolo processor options accept only max_length")
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text())
    if config.get("model_type") not in {"qwen3_5", "piccolo_qwen3_5"}:
        raise ValueError("Expected Qwen3.5 VL weights")
    config.update(
        model_type="piccolo_qwen3_5",
        architectures=["PiccoloModel"],
        use_cache=False,
        auto_map={
            "AutoConfig": "piccolo_configuration.PiccoloConfig",
            "AutoModel": "piccolo_modeling.PiccoloModel",
        },
    )
    config["text_config"].update(model_type="piccolo_qwen3_5_text", use_cache=False)
    _write_json(directory / "config.json", config)
    processor_path = directory / "processor_config.json"
    processor = json.loads(processor_path.read_text()) if processor_path.exists() else {}
    for name in (
        "system_prompt",
        "answer_prefix",
        "enable_thinking",
        "choice_labels",
        "max_length",
    ):
        processor.pop(name, None)
    processor.update(
        processor_class="PiccoloProcessor",
        auto_map={"AutoProcessor": "piccolo_processing.PiccoloProcessor"},
        **options,
    )
    if "image_processor" in processor:
        processor["image_processor"]["size"] = dict(image_size)
    image_path = directory / "preprocessor_config.json"
    if image_path.exists():
        image = json.loads(image_path.read_text())
        image["size"] = dict(image_size)
        _write_json(image_path, image)
    if "image_processor" not in processor and not image_path.exists():
        raise ValueError("Piccolo requires image processor assets")
    _write_json(processor_path, processor)
    (directory / "chat_template.jinja").write_text(template, encoding="utf-8")
    for name in ("tokenizer_config.json", "processor_config.json"):
        path = directory / name
        if path.exists():
            data = json.loads(path.read_text())
            data.pop("chat_template", None)
            if name == "tokenizer_config.json":
                data.pop("auto_map", None)
                data.pop("processor_class", None)
            _write_json(path, data)
    for name in (
        "generation_config.json",
        "jev_template.json",
        "piccolo.json",
        "sglang_runtime.json",
        "chat_template.json",
        "decision-inference.json",
    ):
        (directory / name).unlink(missing_ok=True)
    for module in MODULES:
        shutil.copy2(Path(__file__).with_name(module + ".py"), directory / (module + ".py"))
    read_hf_inference_assets(directory)
    readme = directory / "README.md"
    if readme.exists() and not (directory / "BASE_MODEL_README.md").exists():
        readme.replace(directory / "BASE_MODEL_README.md")
    readme.write_text(
        "---\nlibrary_name: transformers\ntags:\n- custom_code\n- piccolo\n---\n\n"
        "# Piccolo checkpoint\n\n"
        "Full attention is bidirectional; GDN remains causal. Complete prompts only, "
        "without incremental generation or KV caching. Load with AutoProcessor and "
        "AutoModel using trust_remote_code=True. Iterate processor.encode_request(payload) "
        "and pass each item's inputs to the model. Probabilities follow item.option_keys.\n",
        encoding="utf-8",
    )


def validate_checkpoint(directory):
    """Check assets and every required tensor using headers and a meta-device model."""
    import torch
    from safetensors import safe_open
    from transformers import AutoConfig, AutoModel, AutoProcessor

    directory = Path(directory)
    metadata, _ = read_hf_inference_assets(directory)
    # AutoClass loading also verifies bundled Python modules and tokenizer assets.
    config = AutoConfig.from_pretrained(directory, trust_remote_code=True, local_files_only=True)
    processor = AutoProcessor.from_pretrained(
        directory, trust_remote_code=True, local_files_only=True
    )
    processor.encode_request({"state": "validation", "questions": {"q": {"type": "noul"}}})
    shapes, owners = {}, {}
    for path in sorted(directory.glob("*.safetensors")):
        with safe_open(path, framework="pt", device="cpu") as tensors:
            for key in tensors.keys():
                if key in shapes:
                    raise ValueError(f"Duplicate checkpoint tensor: {key}")
                shapes[key] = tuple(tensors.get_slice(key).get_shape())
                owners[key] = path.name
    index_path = directory / "model.safetensors.index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())["weight_map"]
        for key, shard in index.items():
            if owners.get(key) != shard:
                raise ValueError(f"Missing or inconsistent weight shard for {key}: {shard}")
    if not shapes:
        raise ValueError("Full safetensors weights are required")
    with torch.device("meta"):
        expected = AutoModel.from_config(config, trust_remote_code=True, attn_implementation="sdpa")
    aliases = {}
    for name, parameter in expected.named_parameters(remove_duplicate=False):
        aliases.setdefault(id(parameter), []).append(name)
    for names in aliases.values():
        present = next((name for name in names if name in shapes), None)
        if present is None:
            raise ValueError(f"Missing checkpoint tensor: {names[0]}")
        for name in names:
            if name in shapes and shapes[name] != tuple(expected.get_parameter(name).shape):
                raise ValueError(f"Wrong tensor shape for {name}: {shapes[name]}")
    return metadata


def convert(source, output, *, template, image_size, max_length=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir() or output == source or source in output.parents:
        raise ValueError("Use an existing source and a separate output directory")
    if output.exists():
        raise ValueError("Output directory must not exist")
    low, high = image_size["shortest_edge"], image_size["longest_edge"]
    if type(low) is not int or type(high) is not int or not 0 < low <= high:
        raise ValueError("Invalid image pixel budget")
    assets = {
        "config.json",
        "processor_config.json",
        "preprocessor_config.json",
        "video_preprocessor_config.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "vocab.txt",
        "merges.txt",
        "tokenizer.model",
        "spiece.model",
        "model.safetensors.index.json",
        "README.md",
        "LICENSE",
        "NOTICE",
    }
    output.mkdir()
    try:
        for path in source.iterdir():
            if not path.is_file() or (path.name not in assets and path.suffix != ".safetensors"):
                continue
            target = output / path.name
            if path.suffix == ".safetensors":
                try:
                    os.link(path, target)
                    continue
                except OSError:
                    pass
            shutil.copy2(path, target)
        write_hf_inference_assets(
            output,
            template=template,
            image_size=image_size,
            processor_options={} if max_length is None else {"max_length": max_length},
        )
        validate_checkpoint(output)
    except Exception:
        shutil.rmtree(output)
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("directory", type=Path)
    migrate = commands.add_parser("convert")
    migrate.add_argument("source", type=Path)
    migrate.add_argument("output", type=Path)
    migrate.add_argument("--template", type=Path, required=True)
    migrate.add_argument("--image-min-pixels", type=int, required=True)
    migrate.add_argument("--image-max-pixels", type=int, required=True)
    migrate.add_argument("--max-length", type=int)
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate_checkpoint(args.directory), indent=2))
    else:
        print(
            convert(
                args.source,
                args.output,
                template=args.template.read_text(),
                image_size={
                    "shortest_edge": args.image_min_pixels,
                    "longest_edge": args.image_max_pixels,
                },
                max_length=args.max_length,
            )
        )


if __name__ == "__main__":
    main()
