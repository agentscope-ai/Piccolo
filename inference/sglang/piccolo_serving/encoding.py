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
        export_required = "Re-export the checkpoint with the current Piccolo tools before serving"
        if not all(
            callable(getattr(self.processor, method, None))
            for method in ("encode_request", "prepare_media")
        ):
            raise RuntimeError(export_required)
        # These modules are bundled with the selected checkpoint's processor.
        package = type(self.processor).__module__.rpartition(".")[0]
        inputs = import_module(".common_inputs", package)
        self.request_schema = inputs.SystemOneTextRequest
        if not callable(getattr(self.request_schema, "prepare", None)):
            raise RuntimeError(export_required)
        self.load_request_images = import_module(".piccolo_images", package).load_request_images
        self.processor.max_length = min(
            self.processor.max_length, manager.context_len, manager.max_req_input_len
        )
        self.lock = threading.Lock()
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
        if any("path" in asset for asset in body.assets.values()):
            raise ValueError("Image assets require HTTP/HTTPS url or data_base64, not local paths")
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
