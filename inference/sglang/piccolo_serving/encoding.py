"""Checkpoint encoding with image I/O outside the shared processor lock."""

import os
import threading
from importlib import import_module

from transformers import AutoProcessor


def download_image(url):
    from sglang.srt.utils import CLIENT_MEDIA_EXCEPTIONS, download_remote_media

    try:
        return download_remote_media(url, timeout=float(os.getenv("REQUEST_TIMEOUT", "3")))
    except CLIENT_MEDIA_EXCEPTIONS as error:
        raise ValueError(f"Could not download image URL: {error}") from error


class PiccoloEncoder:
    def __init__(self, manager, *, processor=None):
        self.processor = processor or AutoProcessor.from_pretrained(
            manager.model_path,
            revision=getattr(getattr(manager, "server_args", None), "revision", None),
            trust_remote_code=True,
        )
        self.context_length = min(manager.context_len, manager.max_req_input_len)
        self.processor.max_length = min(self.processor.max_length, self.context_length)
        self.model_name = manager.served_model_name
        self.lock = threading.Lock()
        # These modules are bundled with the selected checkpoint's processor.
        package = type(self.processor).__module__.rpartition(".")[0]
        inputs = import_module(".common_inputs", package)
        media = import_module(".common_media", package)
        self.request_schema = inputs.SystemOneTextRequest
        self.prepare_request = getattr(inputs, "prepare_request", None)
        self.image_sources = inputs.image_sources
        self.load_image_source = media.load_image_source

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
        request = self.prepare_request(payload) if self.prepare_request is not None else None
        sources = request.image_sources if request is not None else self.image_sources(assets)
        loaded = {
            source: self.load_image_source(source, download=download_image)
            for source in dict.fromkeys(sources.values())
        }
        with self.lock:
            if request is not None:
                images = {key: loaded[source] for key, source in sources.items()}
                items = self.processor.encode_request(request, images=images)
            else:
                # Published checkpoints without request preparation use a source-string loader.
                previous_loader = self.processor.image_loader
                self.processor.image_loader = loaded.__getitem__
                try:
                    items = self.processor.encode_request(payload)
                finally:
                    self.processor.image_loader = previous_loader
        encoded = []
        questions = []
        for item in items:
            tensors = item.inputs
            tokens = tensors["input_ids"][0].tolist()
            ids = tensors["candidate_token_ids"][0].tolist()
            if not tokens or len(tokens) > self.context_length:
                raise ValueError("Piccolo prompt exceeds context length; no truncation")
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
            questions.append((item.question_id, item.option_keys))
        return iter(encoded), questions
