"""Decision Index HTTP adapter for the native Piccolo Vision endpoint."""
import os

from decision_index.engines.base import Engine, Unsupported, validate
from decision_index.engines.http import CAPACITY_MARKERS
from decision_index.vision import images as image_io
from decision_index.vision.engines import ThreadClients, resize_policy

MAX_PIXELS = 1638400


class VisionEngine(Engine):
    name = "piccolo-vision-sglang"
    latency = "Complete HTTP request including image encoding, OCR when enabled, prompt construction, SGLang vision encoding and candidate readout, including service waits; excludes warmed model loading."

    def __init__(self, base_url, model, image_root=None, timeout=900, require_ocr=False, **options):
        super().__init__(**options)
        self.model, self.image_root = model, image_root
        headers = {}
        token = os.environ.get("DECISION_INDEX_API_KEY")
        if token:
            headers["Authorization"] = "Bearer " + token
        self.clients = ThreadClients(base_url=base_url, timeout=timeout, headers=headers)
        response = self.clients.get().get("/server_info")
        response.raise_for_status()
        settings = response.json()
        self.backend_settings = {key: settings[key] for key in (
            "dtype", "quantization", "kv_cache_dtype", "context_length",
            "json_model_override_args", "mm_process_config", "disable_radix_cache",
            "chunked_prefill_size", "disable_cuda_graph", "mm_preprocess_cache_size_mb",
            "enable_mm_global_cache", "model_path", "version")}
        response=self.clients.get().get('/v1/decisions/runtime')
        response.raise_for_status()
        self.vision_settings=response.json()
        if isinstance(require_ocr,str):
            if require_ocr.lower() not in ('true','false','1','0'):raise ValueError('Invalid require_ocr')
            require_ocr=require_ocr.lower() in ('true','1')
        if require_ocr and not self.vision_settings['ocr']['enabled']:
            raise RuntimeError('This evaluation requires OCR; the server has OCR disabled')
        if settings.get('quantization') not in (None,'none') or settings.get('dtype') not in ('bfloat16','bf16'):
            raise RuntimeError('Vision submission requires the BF16, unquantized server')
        self.provenance = dict(
            kind="http-piccolo-vision", base_url=base_url, path="/v1/decisions",
            model=model, max_pixels=MAX_PIXELS, image_resize=resize_policy(MAX_PIXELS),
            vision_format="question_list_text_images_text", prompt_revision=self.vision_settings['prompt_revision'],
            visible_fields=["state", "questions", "images", "prompt"],
            backend_settings=self.backend_settings,
            ocr=self.vision_settings['ocr'],
        )

    def __call__(self, state, questions, images=(), prompt=None):
        urls = [image_io.data_url(ref, self.image_root, MAX_PIXELS) for ref in images]
        response = self.clients.get().post("/v1/decisions", json=dict(
            model=self.model, state=state, questions=questions, images=urls, prompt=prompt))
        if response.status_code in (400, 413, 422) and any(
            marker in response.text for marker in CAPACITY_MARKERS
        ):
            raise Unsupported(response.text)
        response.raise_for_status()
        raw = response.json()
        validate(questions, raw)
        return {key: raw[key] for key in ("model", "answers", "usage")}, raw

    def runtime(self):
        return dict(backend_settings=self.backend_settings,vision_settings=self.vision_settings)

    def close(self):
        self.clients.close()
