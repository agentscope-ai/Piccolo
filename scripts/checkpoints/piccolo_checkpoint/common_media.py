"""Image decoding and Qwen3.5 prompt encoding for Piccolo."""

import base64
import os
from io import BytesIO

import httpx
from PIL import Image, UnidentifiedImageError
from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessorKwargs
from transformers.utils.chat_template_utils import _compile_jinja_template

from .common_inputs import PreparedDecision, render_text


def load_image_source(source, *, download=None):
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        if download is None:
            response = httpx.get(
                source, timeout=float(os.getenv("REQUEST_TIMEOUT", "3")), follow_redirects=True
            )
            response.raise_for_status()
            source = response.content
        else:
            source = download(source)
    elif isinstance(source, str) and source.startswith("data:"):
        source = base64.b64decode(source.split(",", 1)[1], validate=True)
    if isinstance(source, bytes):
        source = BytesIO(source)
    try:
        image = source if isinstance(source, Image.Image) else Image.open(source)
        image.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError(f"Could not decode image: {error}") from error
    return image


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
        field_parts=decision.field_parts,
        render_text=render_text,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=enable_thinking,
        add_vision_id=add_vision_id,
    )


def encode_prompt(processor, decision: PreparedDecision, *, image_loader):
    """Prepare image tensors once and expand their placeholders before tokenization."""
    images = [image_loader(source) for source in decision.image_sources]
    kwargs = processor._merge_kwargs(
        Qwen3VLProcessorKwargs,
        tokenizer_init_kwargs=processor.tokenizer.init_kwargs,
        return_tensors="pt",
        padding=False,
        truncation=False,
        add_special_tokens=False,
    )
    template = processor.chat_template
    if isinstance(template, dict):
        template = template.get("default")
    if template is None:
        raise ValueError("Piccolo requires a default decision template")
    text = render_prompt(template, decision)
    pixels = processor.image_processor(images=images, **kwargs["images_kwargs"]) if images else {}
    if text.count(processor.image_token) != len(images):
        raise ValueError("Rendered image placeholders do not match request images")
    if images:
        merge = processor.image_processor.merge_size**2
        replacements = [
            processor.image_token * (int(grid.prod()) // merge) for grid in pixels["image_grid_thw"]
        ]
        parts = text.split(processor.image_token)
        text = parts[0] + "".join(
            image + part for image, part in zip(replacements, parts[1:], strict=True)
        )
    text_kwargs = dict(kwargs["text_kwargs"])
    text_kwargs.pop("return_mm_token_type_ids", None)
    encoded = processor.tokenizer([text], **text_kwargs)
    processor._check_special_mm_tokens([text], encoded, modalities=["image"])
    encoded.update(pixels)
    return encoded
