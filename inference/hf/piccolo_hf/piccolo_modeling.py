"""Native HF Piccolo: bidirectional full layers, causal GDN, no decoding cache."""

from dataclasses import dataclass

import torch
from transformers import AutoModel
from transformers.masking_utils import create_recurrent_attention_mask
from transformers.models.qwen3_5.modeling_qwen3_5 import (
    Qwen3_5ForConditionalGeneration,
    Qwen3_5TextModel,
)
from transformers.utils import ModelOutput

from .piccolo_configuration import PiccoloConfig, PiccoloTextConfig


@dataclass
class CandidateOutput(ModelOutput):
    logits: torch.Tensor | None = None
    probabilities: torch.Tensor | None = None


class PiccoloTextModel(Qwen3_5TextModel):
    config_class = PiccoloTextConfig
    _supports_flash_attn = False

    def __init__(self, config):
        super().__init__(config)
        for layer in self.layers:
            if layer.block_type == "full_attention":
                layer.self_attn.is_causal = False

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        inputs_embeds=None,
        use_cache=False,
        **kwargs,
    ):
        if use_cache or past_key_values is not None:
            raise ValueError("Piccolo requires independent complete prompts without a KV cache")
        if isinstance(attention_mask, dict):
            raise ValueError("Piccolo constructs its own full/GDN masks")
        embeds = inputs_embeds if inputs_embeds is not None else self.embed_tokens(input_ids)
        batch, length = embeds.shape[:2]
        if attention_mask is not None and attention_mask.shape != (batch, length):
            raise ValueError("Piccolo attention_mask must be a 2D padding mask")
        # An explicit noncausal mask is required even if a backend infers its
        # default causality from the inherited Qwen architecture.
        full = torch.zeros((batch, 1, 1, length), dtype=embeds.dtype, device=embeds.device)
        if attention_mask is not None:
            full = full.masked_fill(
                ~attention_mask[:, None, None, :].bool(), torch.finfo(embeds.dtype).min
            )
        text_positions = (
            position_ids[0]
            if position_ids is not None and position_ids.ndim == 3 and position_ids.shape[0] == 4
            else None
        )
        recurrent = create_recurrent_attention_mask(
            config=self.config,
            inputs_embeds=embeds,
            attention_mask=attention_mask,
            past_key_values=None,
            position_ids=text_positions,
        )
        return super().forward(
            input_ids=input_ids,
            inputs_embeds=inputs_embeds,
            attention_mask={"full_attention": full, "linear_attention": recurrent},
            position_ids=position_ids,
            past_key_values=None,
            use_cache=False,
            **kwargs,
        )


# Only the custom text config is registered; native Qwen mappings are untouched.
AutoModel.register(PiccoloTextConfig, PiccoloTextModel, exist_ok=True)


class PiccoloModel(Qwen3_5ForConditionalGeneration):
    config_class = PiccoloConfig
    _supports_flash_attn = False

    @classmethod
    def can_generate(cls):
        return False

    def __init__(self, config):
        # AutoConfig and AutoModel may load their relative modules in separate
        # dynamic-code contexts. Use this module's text config registration.
        config.text_config = PiccoloTextConfig(**config.text_config.to_dict())
        super().__init__(config)

    def forward(self, input_ids=None, attention_mask=None, candidate_token_ids=None, **kwargs):
        if kwargs.get("use_cache") or kwargs.get("past_key_values") is not None:
            raise ValueError("Piccolo does not support incremental decoding")
        if kwargs.get("labels") is not None or candidate_token_ids is None:
            raise ValueError("Piccolo requires candidate_token_ids without training labels")
        kwargs.pop("logits_to_keep", None)
        kwargs.pop("use_cache", None)
        self.model.rope_deltas = None
        output = self.model(
            input_ids=input_ids, attention_mask=attention_mask, use_cache=False, **kwargs
        )
        hidden = output.last_hidden_state
        if attention_mask is None:
            positions = torch.full((hidden.shape[0],), hidden.shape[1] - 1, device=hidden.device)
        else:
            if attention_mask.ndim != 2 or not attention_mask.bool().any(-1).all():
                raise ValueError("Each candidate prompt must have at least one real token")
            indices = torch.arange(hidden.shape[1], device=hidden.device)
            positions = (
                indices.expand_as(attention_mask)
                .masked_fill(~attention_mask.bool(), -1)
                .max(-1)
                .values
            )
        logits = self.lm_head(
            hidden[torch.arange(hidden.shape[0], device=hidden.device), positions]
        )
        ids = torch.as_tensor(candidate_token_ids, device=logits.device, dtype=torch.long)
        if ids.ndim == 1:
            ids = ids.unsqueeze(0).expand(logits.shape[0], -1)
        if ids.ndim != 2 or ids.shape[0] != logits.shape[0] or ids.shape[1] == 0:
            raise ValueError(
                "candidate_token_ids must have shape [candidates] or [batch, candidates]"
            )
        if (ids < 0).any() or (ids >= logits.shape[-1]).any():
            raise ValueError("Candidate token id is outside the model vocabulary")
        if any(row.unique().numel() != row.numel() for row in ids):
            raise ValueError("Candidate token ids must be distinct")
        candidates = logits.gather(-1, ids).float()
        return CandidateOutput(logits=candidates, probabilities=candidates.softmax(-1))

    def generate(self, *args, **kwargs):
        raise ValueError("Piccolo is a prompt classifier; use forward with candidate_token_ids")


PiccoloModel.register_for_auto_class("AutoModel")
