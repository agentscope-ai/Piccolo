"""Checkpoint encoding with image I/O outside the shared processor lock."""

import os
import threading

from piccolo_hf.common_inputs import image_sources
from piccolo_hf.common_media import load_image_source
from transformers import AutoProcessor


def download_image(url):
    from sglang.srt.utils import CLIENT_MEDIA_EXCEPTIONS, download_remote_media

    try:
        return download_remote_media(url, timeout=float(os.getenv("REQUEST_TIMEOUT", "3")))
    except CLIENT_MEDIA_EXCEPTIONS as error:
        raise ValueError(f"Could not download image URL: {error}") from error


class PiccoloEncoder:
    def __init__(self, manager, *, directory=None, processor=None):
        self.processor = processor or AutoProcessor.from_pretrained(
            manager.model_path,
            revision=getattr(getattr(manager, "server_args", None), "revision", None),
            trust_remote_code=True,
        )
        self.context_length = min(manager.context_len, manager.max_req_input_len)
        self.processor.max_length = min(self.processor.max_length, self.context_length)
        self.model_name = manager.served_model_name
        self.lock = threading.Lock()

    def encode_request(self, body):
        if body.model != self.model_name:
            raise ValueError("Unknown served model")
        raw = body.model_dump(exclude_unset=True)
        assets = raw.get("assets", {})
        if any("path" in asset for asset in assets.values()):
            raise ValueError("Image assets require HTTP/HTTPS url or data_base64, not local paths")
        payload = {"state": body.state, "questions": raw["questions"], "assets": assets}
        # Decode each distinct source before locking. Slow downloads do not block
        # text requests or requests whose images are already available.
        images = {
            source: load_image_source(source, download=download_image)
            for source in dict.fromkeys(image_sources(assets).values())
        }
        with self.lock:
            previous_loader = self.processor.image_loader
            self.processor.image_loader = images.__getitem__
            try:
                items = self.processor.encode_request(payload)
            finally:
                self.processor.image_loader = previous_loader
        encoded = []
        for item in items:
            tensors = item.inputs
            tokens = tensors["input_ids"][0].tolist()
            ids = tensors["candidate_token_ids"][0].tolist()
            if not tokens or len(tokens) > self.context_length:
                raise ValueError("Piccolo prompt exceeds context length; no truncation")
            if payload["questions"][item.question_id]["type"] == "noul":
                ids = ids[::-1]
            media = []
            if "pixel_values" in tensors:
                media = [
                    {
                        "format": "processor_output",
                        "input_ids": tensors["input_ids"],
                        "pixel_values": tensors["pixel_values"],
                        "image_grid_thw": tensors["image_grid_thw"],
                    }
                ]
            encoded.append((tokens, ids, media))
        return iter(encoded)
