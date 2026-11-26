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
        self.request_schema = inputs.SystemOneTextRequest
        self.load_request_images = None
        if hasattr(self.request_schema, "prepare"):
            self.load_request_images = import_module(".piccolo_images", package).load_request_images
        else:
            self.prepare_request = getattr(inputs, "prepare_request", None)
            self.image_sources = inputs.image_sources
            self.load_image_source = import_module(".common_media", package).load_image_source
        self.ocr = None
        if os.getenv("PICCOLO_OCR_ENABLED") == "1":
            load_ocr = getattr(self.processor, "load_ocr", None)
            if load_ocr is None:
                raise RuntimeError("OCR requires a checkpoint exported with Torch OCR support")
            model_paths = {
                arg: path
                for arg, env in (
                    ("detector", "PICCOLO_OCR_DET_MODEL"),
                    ("recognizer", "PICCOLO_OCR_REC_MODEL"),
                )
                if (path := os.getenv(env))
            }
            self.ocr = load_ocr(device=os.getenv("PICCOLO_OCR_DEVICE", "cpu"), **model_paths)

    def encode_request(self, body):
        if body.model != self.model_name:
            raise ValueError("Unknown served model")
        if any("path" in asset for asset in body.assets.values()):
            raise ValueError("Image assets require HTTP/HTTPS url or data_base64, not local paths")
        if self.load_request_images is None:
            items = self._encode_older_checkpoint(body)
        else:
            request = body.prepare()
            # Keep downloads and OCR outside the shared processor lock.
            images = self.load_request_images(request.image_sources, download=download_image)
            ocr_texts = None
            if self.ocr is not None and images:
                images, ocr_texts = self.processor.prepare_media(images, ocr=self.ocr)
            with self.lock:
                items = self.processor.encode_request(request, images=images, ocr=ocr_texts)
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

    def _encode_older_checkpoint(self, body):
        raw = body.model_dump(exclude_unset=True)
        assets = raw.get("assets", {})
        payload = {"state": body.state, "questions": raw["questions"], "assets": assets}
        request = self.prepare_request(payload) if self.prepare_request is not None else None
        sources = request.image_sources if request is not None else self.image_sources(assets)
        loaded = {
            source: self.load_image_source(source, download=download_image)
            for source in dict.fromkeys(sources.values())
        }
        if request is not None:
            images = {key: loaded[source] for key, source in sources.items()}
            kwargs = {"ocr": self.ocr.recognize(images)} if self.ocr is not None and images else {}
            with self.lock:
                return self.processor.encode_request(request, images=images, **kwargs)

        # The earliest checkpoints load images by their original source strings.
        with self.lock:
            previous_loader = self.processor.image_loader
            self.processor.image_loader = loaded.__getitem__
            try:
                return self.processor.encode_request(payload)
            finally:
                self.processor.image_loader = previous_loader
