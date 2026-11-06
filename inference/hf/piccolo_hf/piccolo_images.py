"""Piccolo image resizing, for complete prompt inference."""

from io import BytesIO

from PIL import Image

from .common_media import load_image_source


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
