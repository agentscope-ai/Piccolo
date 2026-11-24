"""Independent full-prompt recurrence, with one parameter set per physical layer."""

import torch
from transformers import AutoModel
from transformers.modeling_outputs import BaseModelOutputWithPooling
from transformers.models.qwen3_5.modeling_qwen3_5 import (
    Qwen3_5ForConditionalGeneration,
    Qwen3_5ModelOutputWithPast,
    Qwen3_5VisionModel,
    get_vision_attention_seqlens,
    get_vision_interpolation_indices_and_weights,
    get_vision_position_ids,
)

from .loop_utils import execution_segments, mix_hidden
from .piccolo_loop_configuration import (
    PiccoloLoopConfig,
    PiccoloLoopTextConfig,
    PiccoloLoopVisionConfig,
)
from .piccolo_modeling import PiccoloModel, PiccoloTextModel


class PiccoloLoopTextModel(PiccoloTextModel):
    config_class = PiccoloLoopTextConfig

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
            raise ValueError("PiccoloLoop requires complete prompts without a KV/GDN cache")
        if (input_ids is None) == (inputs_embeds is None):
            raise ValueError("Specify exactly one of input_ids or inputs_embeds")
        hidden = self.embed_tokens(input_ids) if inputs_embeds is None else inputs_embeds
        batch, length = hidden.shape[:2]
        if position_ids is None:
            position_ids = torch.arange(length, device=hidden.device)[None, None].expand(
                4, batch, -1
            )
        elif position_ids.ndim == 2:
            position_ids = position_ids[None].expand(4, -1, -1)
        text_positions = position_ids[0] if position_ids.shape[0] == 4 else None
        rotary_positions = position_ids[1:] if text_positions is not None else position_ids
        masks = self._prepare_attention_masks(hidden, attention_mask, position_ids)
        rotary = self.rotary_emb(hidden, rotary_positions)
        for start, end, alphas in execution_segments(len(self.layers), self.config.loop_section):
            for alpha in alphas:
                before = hidden
                for index in range(start, end):
                    hidden = self.layers[index](
                        hidden,
                        position_embeddings=rotary,
                        attention_mask=masks[self.config.layer_types[index]],
                        position_ids=text_positions,
                        past_key_values=None,
                        use_cache=False,
                        **kwargs,
                    )
                # Ordinary segments have no fusion, matching native BF16 boundaries.
                if len(alphas) > 1 or alpha != 1:
                    hidden = mix_hidden(before, hidden, alpha)
        return Qwen3_5ModelOutputWithPast(last_hidden_state=self.norm(hidden), past_key_values=None)


class PiccoloLoopVisionModel(Qwen3_5VisionModel):
    config_class = PiccoloLoopVisionConfig

    def forward(self, hidden_states, grid_thw, **kwargs):
        indices, weights = get_vision_interpolation_indices_and_weights(
            grid_thw,
            num_grid_per_side=self.num_grid_per_side,
            mode=self.interpolation_mode,
            align_corners=self.interpolation_align_corners,
            spatial_merge_size=self.spatial_merge_size,
            kwargs=kwargs,
        )
        positions = get_vision_position_ids(grid_thw, self.spatial_merge_size, kwargs=kwargs)
        cu_seqlens, max_seqlen = get_vision_attention_seqlens(grid_thw, self.config, kwargs=kwargs)
        hidden = self.patch_embed(hidden_states)
        hidden = hidden + (self.pos_embed(indices) * weights[:, :, None]).sum(1).to(hidden.dtype)
        rotary = self.rotary_pos_emb(hidden, positions)
        for start, end, alphas in execution_segments(len(self.blocks), self.config.loop_section):
            for alpha in alphas:
                before = hidden
                for index in range(start, end):
                    hidden = self.blocks[index](
                        hidden,
                        cu_seqlens=cu_seqlens,
                        max_seqlen=max_seqlen,
                        position_embeddings=rotary,
                        **kwargs,
                    )
                if len(alphas) > 1 or alpha != 1:
                    hidden = mix_hidden(before, hidden, alpha)
        return BaseModelOutputWithPooling(
            last_hidden_state=hidden, pooler_output=self.merger(hidden)
        )


AutoModel.register(PiccoloLoopTextConfig, PiccoloLoopTextModel, exist_ok=True)
AutoModel.register(PiccoloLoopVisionConfig, PiccoloLoopVisionModel, exist_ok=True)


class PiccoloLoopModel(PiccoloModel):
    config_class = PiccoloLoopConfig

    def __init__(self, config):
        # Rebind dynamic AutoConfig instances to this module's local AutoModel registrations.
        config.text_config = PiccoloLoopTextConfig(**config.text_config.to_dict())
        config.vision_config = PiccoloLoopVisionConfig(**config.vision_config.to_dict())
        Qwen3_5ForConditionalGeneration.__init__(self, config)


PiccoloLoopModel.register_for_auto_class("AutoModel")
