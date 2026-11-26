"""Qwen3.5 prompt rendering, image tensor ordering and tokenization."""

import json

import torch
from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessorKwargs
from transformers.utils.chat_template_utils import _compile_jinja_template

from .common_inputs import PreparedDecision, render_text

# Checkpoint consumers use this import path to load image sources.
from .piccolo_images import load_image_source  # noqa: F401


def _vision_overview_text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def render_prompt(
    template: str,
    decision: PreparedDecision,
    *,
    add_generation_prompt: bool = True,
    enable_thinking: bool = False,
    add_vision_id: bool = False,
) -> str:
    return _compile_jinja_template(template).render(
        prompt=decision.prompt,
        candidates=decision.candidates,
        state_parts=decision.state_parts,
        instruction_parts=decision.instruction_parts,
        render_text=render_text,
        vision_overview_text=_vision_overview_text,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=enable_thinking,
        add_vision_id=add_vision_id,
    )


def prompt_encoding_kwargs(processor):
    return processor._merge_kwargs(
        Qwen3VLProcessorKwargs,
        tokenizer_init_kwargs=processor.tokenizer.init_kwargs,
        return_tensors="pt",
        padding=False,
        truncation=False,
        add_special_tokens=False,
    )


class EncodedImages:
    """Reuse Qwen image tensors across questions, packing them in each prompt's order."""

    def __init__(self, asset_order, pixels):
        self._batches = {asset_order: pixels}
        self._by_asset = {}
        if asset_order:
            grid = pixels["image_grid_thw"]
            patches = pixels["pixel_values"].split(grid.prod(dim=1).tolist())
            self._by_asset = dict(zip(asset_order, zip(patches, grid, strict=True), strict=True))

    def for_order(self, asset_order):
        if asset_order not in self._batches:
            patches, grids = zip(*(self._by_asset[key] for key in asset_order), strict=True)
            self._batches[asset_order] = {
                "pixel_values": torch.cat(patches),
                "image_grid_thw": torch.stack(grids),
            }
        return self._batches[asset_order]


def encode_prompt(processor, decision: PreparedDecision, *, pixels, text_kwargs):
    """Expand image placeholders and tokenize one complete prompt."""
    template = processor.chat_template
    if isinstance(template, dict):
        template = template.get("default")
    if template is None:
        raise ValueError("Piccolo requires a default decision template")
    text = render_prompt(template, decision)
    if text.count(processor.image_token) != len(decision.prompt.asset_order):
        raise ValueError("Rendered image placeholders do not match request images")
    if pixels:
        merge = processor.image_processor.merge_size**2
        replacements = [
            processor.image_token * (int(grid.prod()) // merge) for grid in pixels["image_grid_thw"]
        ]
        parts = text.split(processor.image_token)
        text = parts[0] + "".join(
            image + part for image, part in zip(replacements, parts[1:], strict=True)
        )
    text_kwargs = dict(text_kwargs)
    text_kwargs.pop("return_mm_token_type_ids", None)
    encoded = processor.tokenizer([text], **text_kwargs)
    processor._check_special_mm_tokens([text], encoded, modalities=["image"])
    encoded.update(pixels)
    return encoded
