"""Image decoding and Qwen3.5 prompt encoding for Piccolo."""

import base64
import os
from io import BytesIO

import httpx
from PIL import Image, UnidentifiedImageError
from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessorKwargs


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


def encode_prompt(processor, messages, *, image_loader):
    """Prepare image tensors once and expand their placeholders before tokenization."""
    images = [
        image_loader(block["image"])
        for message in messages
        for block in message["content"]
        if block["type"] == "image"
    ]
    kwargs = processor._merge_kwargs(
        Qwen3VLProcessorKwargs,
        tokenizer_init_kwargs=processor.tokenizer.init_kwargs,
        return_tensors="pt",
        padding=False,
        truncation=False,
        add_special_tokens=False,
    )
    text = processor.apply_chat_template(
        messages,
        chat_template=processor.chat_template,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
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
