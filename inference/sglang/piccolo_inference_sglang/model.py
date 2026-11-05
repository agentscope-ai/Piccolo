"""Piccolo serving policy; SGLang owns routes and model execution."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


def create_piccolo_adapter(model_config):
    """Create and configure the adapter for a supported Piccolo checkpoint."""
    from transformers.utils.hub import cached_file

    asset = cached_file(model_config.model_path, "config.json", revision=model_config.revision)
    return PiccoloAdapter(model_config, Path(asset).parent)


class PiccoloAdapter:
    def __init__(self, model_config, directory):
        from piccolo_hf.checkpoint import read_hf_inference_assets
        from transformers.utils.hub import cached_file

        for filename in ("chat_template.jinja", "processor_config.json"):
            cached_file(model_config.model_path, filename, revision=model_config.revision)
        cached_file(
            model_config.model_path,
            "preprocessor_config.json",
            revision=model_config.revision,
            _raise_exceptions_for_missing_entries=False,
        )
        metadata, _ = read_hf_inference_assets(directory)
        self.directory = directory
        self.metadata = metadata
        self._configure_model(model_config)

    def _configure_model(self, model_config):
        # SGLang's config supplies hybrid-layer and cache properties used by its
        # Qwen kernels; the Transformers class alone lacks those properties.
        from sglang.srt.configs.qwen3_5 import Qwen3_5Config

        config = model_config.hf_config.to_dict()
        config.pop("model_type", None)
        config.get("text_config", {}).pop("model_type", None)
        config["architectures"] = ["Qwen3_5ForConditionalGeneration"]
        model_config.hf_config = Qwen3_5Config(**config)
        model_config.hf_text_config = model_config.hf_config.text_config
        model_config.hf_text_config.is_causal = False

    def configure_server_args(self, server_args):
        from sglang.srt.arg_groups.overrides import declare_resolution, resolving_view

        validate_server_settings(resolving_view(server_args))
        declare_resolution(
            server_args,
            "piccolo_serving_adapter",
            disable_radix_cache=True,
            chunked_prefill_size=-1,
        )

    def validate_request(self, manager, obj, input_ids):
        from sglang.srt.constants import HEALTH_CHECK_RID_PREFIX
        from sglang.srt.managers.io_struct import GenerateReqInput
        from sglang.srt.runtime_context import get_schedule

        health = isinstance(obj.rid, str) and obj.rid.startswith(HEALTH_CHECK_RID_PREFIX)
        if not health and (
            not isinstance(obj, GenerateReqInput)
            or obj.sampling_params.get("max_new_tokens") != 0
            or not obj.token_ids_logprob
            or obj.logprob_start_len != -1
        ):
            raise ValueError("Piccolo checkpoints require /v1/systemone prompt scoring")
        if len(input_ids) > min(manager.max_req_input_len, get_schedule().max_prefill_tokens):
            raise ValueError("Piccolo prompt must fit in one complete prefill")

    def create_serving(self, chat_serving):
        from .serving import PiccoloServing

        return PiccoloServing(chat_serving, directory=self.directory)

    def warmup_request(self, manager):
        return "/v1/systemone", warmup_request(manager.served_model_name)


def validate_server_settings(settings):
    """Reject modes that alter a complete, independent multimodal prompt."""
    for name in (
        "enable_mis",
        "allow_auto_truncate",
        "language_model_only",
        "speculative_algorithm",
        "encoder_only",
        "language_only",
        "is_embedding",
        "skip_tokenizer_init",
    ):
        if getattr(settings, name, None):
            raise ValueError(f"Piccolo serving does not support {name}")
    if getattr(settings, "disaggregation_mode", "null") != "null":
        raise ValueError("Piccolo serving requires unified prefill execution")


def warmup_request(model):
    """Exercise the real classification and vision path during server startup."""
    stream = BytesIO()
    Image.new("RGB", (32, 32), "red").save(stream, "PNG")
    return {
        "model": model,
        "state": {"image": "warmup-image"},
        "questions": {"warmup": {"type": "noul", "instructions": "Is the image red?"}},
        "assets": {
            "warmup-image": {
                "type": "image",
                "format": "png",
                "data_base64": base64.b64encode(stream.getvalue()).decode(),
            }
        },
    }
