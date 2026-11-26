"""Frozen Piccolo request processor for text and image candidate scoring."""

from collections.abc import Mapping
from dataclasses import dataclass

import torch
from PIL import Image
from transformers.feature_extraction_utils import BatchFeature
from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessor

from .common_inputs import (
    JevRequest,
    PreparedDecision,
    PreparedRequest,
    prepare_decision,
    prepare_request,
)
from .common_media import EncodedImages, encode_prompt, prompt_encoding_kwargs
from .piccolo_images import load_request_images, map_unique_images, normalize_image
from .piccolo_ocr import DETECTOR_ID, MAX_IMAGE_PIXELS, RECOGNIZER_ID, TorchOCR


@dataclass
class EncodedDecision:
    question_id: str
    option_keys: tuple[str, ...]
    inputs: BatchFeature


class PiccoloProcessor(Qwen3VLProcessor):
    @staticmethod
    def load_ocr(detector=DETECTOR_ID, recognizer=RECOGNIZER_ID, *, device="cpu"):
        """Load the optional OCR backend from local directories or the local Hub cache."""
        return TorchOCR(detector, recognizer, device=device)

    def __init__(
        self,
        image_processor=None,
        tokenizer=None,
        video_processor=None,
        chat_template=None,
        max_length=None,
        **kwargs,
    ):
        super().__init__(image_processor, tokenizer, video_processor, chat_template=chat_template)
        self.max_length = self.tokenizer.model_max_length if max_length is None else max_length
        if type(self.max_length) is not int or self.max_length <= 0:
            raise ValueError("max_length must be a positive integer")

    def __call__(self, payload=None, *, question_key=None, **kwargs):
        if isinstance(payload, dict) and "questions" in payload:
            ocr = kwargs.pop("ocr", None)
            if kwargs.pop("return_tensors", "pt") != "pt" or kwargs:
                raise ValueError('Decision encoding accepts only return_tensors="pt"')
            if question_key is None:
                if len(payload["questions"]) != 1:
                    raise ValueError(
                        "Select question_key or use encode_request for multiple questions"
                    )
                question_key = next(iter(payload["questions"]))
            return self.encode_question(payload, question_key, ocr=ocr).inputs
        if payload is not None:
            kwargs["text"] = payload
        return super().__call__(**kwargs)

    def encode_request(
        self,
        payload: JevRequest | PreparedRequest,
        *,
        images: Mapping[str, Image.Image] | None = None,
        ocr: TorchOCR | Mapping[str, str] | None = None,
    ) -> list[EncodedDecision]:
        """Encode questions in order, optionally reusing images keyed by asset ID."""
        return self._encode_questions(payload, None, images, ocr)

    def encode_question(
        self,
        payload: JevRequest | PreparedRequest,
        question_key: str,
        *,
        images: Mapping[str, Image.Image] | None = None,
        ocr: TorchOCR | Mapping[str, str] | None = None,
    ) -> EncodedDecision:
        """Encode one question from a raw request or reuse its prepared data."""
        return self._encode_questions(payload, (question_key,), images, ocr)[0]

    def _encode_questions(self, payload, question_keys, images, ocr):
        request = payload if isinstance(payload, PreparedRequest) else prepare_request(payload)
        keys = request.payload["questions"] if question_keys is None else question_keys
        decisions = [prepare_decision(request, key) for key in keys]
        kwargs = prompt_encoding_kwargs(self)
        asset_order = decisions[0].prompt.asset_order
        if images is None:
            images = load_request_images(request.image_sources)
        images, ocr_texts = self.prepare_media({key: images[key] for key in asset_order}, ocr=ocr)
        if images:
            pixels = self.image_processor(images=list(images.values()), **kwargs["images_kwargs"])
        else:
            pixels = {}
        encoded_images = EncodedImages(asset_order, pixels)
        return [
            self._encode_decision(decision, encoded_images, kwargs["text_kwargs"], ocr_texts)
            for decision in decisions
        ]

    def prepare_media(self, images, *, ocr=None):
        """Normalize decoded images and resolve OCR, sharing pixels when the limits agree."""
        if not images:
            return images, None if isinstance(ocr, TorchOCR) else ocr
        limit = self.image_processor.size["longest_edge"]
        normalized = map_unique_images(images, lambda image: normalize_image(image, limit))
        if isinstance(ocr, TorchOCR):
            ocr = ocr.recognize(normalized if limit == MAX_IMAGE_PIXELS else images)
        return normalized, ocr

    def _encode_decision(self, decision: PreparedDecision, images: EncodedImages, text_kwargs, ocr_texts):
        encoded = encode_prompt(
            self,
            decision,
            pixels=images.for_order(decision.prompt.asset_order),
            text_kwargs=text_kwargs,
            ocr_texts=ocr_texts,
        )
        tokens = encoded["input_ids"][0].tolist()
        if not tokens or len(tokens) > self.max_length:
            raise ValueError("Piccolo prompt exceeds max_length; no truncation")
        ids = [
            self.tokenizer.convert_tokens_to_ids(candidate.label)
            for candidate in decision.candidates
        ]
        if len(set(ids)) != len(ids) or any(
            self.tokenizer.encode(candidate.label, add_special_tokens=False) != [token_id]
            for candidate, token_id in zip(decision.candidates, ids, strict=True)
        ):
            raise ValueError("Piccolo candidates must be distinct single-token labels")
        encoded["mm_token_type_ids"] = torch.tensor(self.create_mm_token_type_ids([tokens]))
        encoded["candidate_token_ids"] = torch.tensor([ids], dtype=torch.long)
        option_keys = tuple(candidate.key for candidate in decision.candidates)
        return EncodedDecision(decision.prompt.question_key, option_keys, BatchFeature(encoded))


PiccoloProcessor.register_for_auto_class()
