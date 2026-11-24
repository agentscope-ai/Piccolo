"""SGLang execution for PiccoloLoop using native Qwen3.5 kernels and physical weights."""

import torch
from sglang.srt.layers.layer_boundary.residual import batch as residual
from sglang.srt.model_executor.forward_context import get_attn_backend
from sglang.srt.models.qwen3_5 import (
    Qwen3_5ForCausalLM,
    Qwen3_5ForConditionalGeneration,
)
from torch import nn

from .execution import execution_segments, mix_hidden


def reset_gdn_state(layer_index):
    """Depth recurrence is independent of the previous sequence scan."""
    backend = get_attn_backend().linear_attn_backend
    pool = backend.req_to_token_pool
    indices = backend.forward_metadata.mamba_cache_indices.long()
    if not bool((indices >= 0).all()):
        raise ValueError("PiccoloLoop requires valid full-prefill GDN state slots")
    cache = pool.mamba2_layer_cache(layer_index)
    cache.temporal.index_fill_(0, indices, 0)
    for state in cache.conv:
        state.index_fill_(0, indices, 0)


class PiccoloLoopBody(Qwen3_5ForCausalLM):
    def __init__(self, config, quant_config=None, prefix="", is_nextn=False):
        if quant_config is not None or is_nextn:
            raise ValueError("PiccoloLoop supports unquantized inference without MTP")
        super().__init__(config, quant_config, prefix, is_nextn)
        if self.pp_group.world_size != 1:
            raise ValueError("PiccoloLoop requires PP=1")

    @torch.no_grad()
    def forward(
        self,
        input_ids,
        positions,
        forward_batch,
        input_embeds=None,
        pp_proxy_tensors=None,
        input_deepstack_embeds=None,
    ):
        mode = forward_batch.forward_mode
        if mode.is_idle():
            return super().forward(
                input_ids,
                positions,
                forward_batch,
                input_embeds,
                pp_proxy_tensors,
                input_deepstack_embeds,
            )
        if not mode.is_extend() or any(int(x) for x in forward_batch.extend_prefix_lens_cpu):
            raise ValueError("PiccoloLoop supports zero-prefix complete prefill only")
        if self.layers_to_capture or (
            input_deepstack_embeds is not None and input_deepstack_embeds.numel()
        ):
            raise ValueError("PiccoloLoop does not support speculative/deepstack captures")
        hidden = self.embed_tokens(input_ids) if input_embeds is None else input_embeds
        residual.start(forward_batch)
        hidden = residual.fold(hidden, forward_batch)
        for start, end, alphas in execution_segments(len(self.layers), self.config.loop_section):
            for alpha in alphas:
                # Both fused norms and native vision blocks may mutate their inputs.
                before = hidden.clone() if len(alphas) > 1 or alpha != 1 else None
                for index in range(start, end):
                    if index in self.config.linear_layer_ids:
                        reset_gdn_state(index)
                    hidden = self.layers[index](
                        positions=positions,
                        hidden_states=hidden,
                        forward_batch=forward_batch,
                        captured_last_layer_outputs=None,
                    )
                    # Match HF's BF16 residual rounding after each physical layer.
                    hidden = residual.fold(hidden, forward_batch)
                if before is not None:
                    hidden = mix_hidden(before, hidden, alpha)
                    hidden = residual.set_written(hidden, forward_batch)
        return residual.final_norm(hidden, forward_batch, self.norm, skip_empty=True)


class VisionSegment(nn.Module):
    def __init__(self, layers, alphas):
        super().__init__()
        # The physical ModuleList is the sole owner of parameters/state_dict keys.
        object.__setattr__(self, "physical_layers", layers)
        self.alphas = alphas

    def forward(self, hidden, *args, **kwargs):
        for alpha in self.alphas:
            before = hidden.clone()
            for layer in self.physical_layers:
                hidden = layer(hidden, *args, **kwargs)
            hidden = mix_hidden(before, hidden, alpha)
        return hidden


class VisionLoopLayers(nn.ModuleList):
    def __init__(self, layers, section):
        super().__init__(layers)
        self.section = section

    def __iter__(self):
        for start, end, alphas in execution_segments(len(self), self.section):
            layers = [self[index] for index in range(start, end)]
            if len(alphas) == 1 and alphas[0] == 1:
                yield from layers
            else:
                yield VisionSegment(layers, alphas)


class PiccoloLoopForConditionalGeneration(Qwen3_5ForConditionalGeneration):
    def __init__(self, config, quant_config=None, prefix=""):
        vision_section = config.vision_config.loop_section
        if vision_section["blocks"]:
            from sglang.srt.environ import envs

            # Native vision initialization and forward both read this setting.
            envs.SGLANG_VIT_ENABLE_CUDA_GRAPH.set(False)
        super().__init__(config, quant_config, prefix, language_model_cls=PiccoloLoopBody)
        if vision_section["blocks"]:
            self.visual.blocks = VisionLoopLayers(list(self.visual.blocks), vision_section)


EntryClass = PiccoloLoopForConditionalGeneration
