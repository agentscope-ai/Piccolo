"""Frozen Piccolo request processor for text and image candidate scoring."""

from collections.abc import Mapping
from dataclasses import dataclass

import torch
from PIL import Image
from transformers.feature_extraction_utils import BatchFeature
from transformers.models.qwen3_vl.processing_qwen3_vl import Qwen3VLProcessor

from .common_inputs import (
    JevRequest,
    PreparedRequest,
    image_source_name,
    prepare_decision,
    prepare_request,
)
from .common_media import encode_prompt
from .piccolo_images import load_piccolo_image


@dataclass
class EncodedDecision:
    question_id: str
    option_keys: tuple[str, ...]
    inputs: BatchFeature


class PiccoloProcessor(Qwen3VLProcessor):
    image_loader = None

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
            if kwargs.pop("return_tensors", "pt") != "pt" or kwargs:
                raise ValueError('Decision encoding accepts only return_tensors="pt"')
            if question_key is None:
                if len(payload["questions"]) != 1:
                    raise ValueError(
                        "Select question_key or use encode_request for multiple questions"
                    )
                question_key = next(iter(payload["questions"]))
            return self.encode_question(payload, question_key).inputs
        if payload is not None:
            kwargs["text"] = payload
        return super().__call__(**kwargs)

    def encode_request(
        self,
        payload: JevRequest | PreparedRequest,
        *,
        images: Mapping[str, Image.Image] | None = None,
    ) -> list[EncodedDecision]:
        """Encode questions in order, optionally reusing images keyed by asset ID."""
        request = payload if isinstance(payload, PreparedRequest) else prepare_request(payload)
        return [
            self.encode_question(request, key, images=images) for key in request.payload["questions"]
        ]

    def encode_question(
        self,
        payload: JevRequest | PreparedRequest,
        question_key: str,
        *,
        images: Mapping[str, Image.Image] | None = None,
    ) -> EncodedDecision:
        """Encode one question from a raw request or reuse its prepared data."""
        request = payload if isinstance(payload, PreparedRequest) else prepare_request(payload)
        decision = prepare_decision(request, question_key)
        limit = self.image_processor.size["longest_edge"]
        if images is not None:
            ordered_images = [
                load_piccolo_image(images[key], limit) for key in decision.prompt.asset_order
            ]
        else:
            sources = decision.image_sources
            loader = self.image_loader
            if loader:
                assets = request.payload.get("assets", {})
                sources = tuple(
                    image_source_name(assets[key], source)
                    for key, source in zip(decision.prompt.asset_order, sources, strict=True)
                )
            ordered_images = [
                load_piccolo_image(source, limit, image_loader=loader) for source in sources
            ]
        encoded = encode_prompt(self, decision, images=ordered_images)
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
