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
    image_source_name,
    prepare_decision,
    prepare_request,
)
from .common_media import EncodedImages, encode_prompt, prompt_encoding_kwargs
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
        return self._encode_questions(payload, None, images)

    def encode_question(
        self,
        payload: JevRequest | PreparedRequest,
        question_key: str,
        *,
        images: Mapping[str, Image.Image] | None = None,
    ) -> EncodedDecision:
        """Encode one question from a raw request or reuse its prepared data."""
        return self._encode_questions(payload, (question_key,), images)[0]

    def _encode_questions(self, payload, question_keys, images):
        request = payload if isinstance(payload, PreparedRequest) else prepare_request(payload)
        keys = request.payload["questions"] if question_keys is None else question_keys
        decisions = [prepare_decision(request, key) for key in keys]
        kwargs = prompt_encoding_kwargs(self)
        asset_order = decisions[0].prompt.asset_order
        encoded_images = self._encode_images(request, asset_order, images, kwargs["images_kwargs"])
        return [
            self._encode_decision(decision, encoded_images, kwargs["text_kwargs"])
            for decision in decisions
        ]

    def _encode_images(self, request: PreparedRequest, asset_order, images, image_kwargs):
        if not asset_order:
            return EncodedImages(asset_order, {})
        limit = self.image_processor.size["longest_edge"]
        loader = None
        if images is not None:
            sources = (images[key] for key in asset_order)
        else:
            sources = (request.image_sources[key] for key in asset_order)
            loader = self.image_loader
            if loader:
                assets = request.payload.get("assets", {})
                sources = (
                    image_source_name(assets[key], source)
                    for key, source in zip(asset_order, sources, strict=True)
                )
        ordered_images = [
            load_piccolo_image(source, limit, image_loader=loader) for source in sources
        ]
        return EncodedImages(asset_order, self.image_processor(images=ordered_images, **image_kwargs))

    def _encode_decision(self, decision: PreparedDecision, images: EncodedImages, text_kwargs):
        encoded = encode_prompt(
            self,
            decision,
            pixels=images.for_order(decision.prompt.asset_order),
            text_kwargs=text_kwargs,
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
