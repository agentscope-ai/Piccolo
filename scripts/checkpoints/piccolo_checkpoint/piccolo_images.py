"""Load and resize Piccolo image sources."""

import base64
import os
from io import BytesIO

import httpx
from PIL import Image, UnidentifiedImageError


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


def load_piccolo_image(url, max_pixels, *, image_loader=None):
    image = (image_loader or load_image_source)(url)
    width, height = image.size
    if width * height > max_pixels:
        scale = (max_pixels / (width * height)) ** 0.5
        w, h = max(1, int(width * scale)), max(1, int(height * scale))
        while w * h > max_pixels:
            if w >= h:
                w -= 1
            else:
                h -= 1
        fmt = "PNG" if image.format == "PNG" else "JPEG"
        mode = (
            "RGBA"
            if fmt == "PNG" and ("A" in image.mode or "transparency" in image.info)
            else "RGB"
        )
        resized = image.convert(mode).resize((w, h), Image.Resampling.LANCZOS)
        stream = BytesIO()
        resized.save(stream, fmt, **({"quality": 95} if fmt == "JPEG" else {}))
        image = Image.open(BytesIO(stream.getvalue()))
    return image.convert("RGB")
