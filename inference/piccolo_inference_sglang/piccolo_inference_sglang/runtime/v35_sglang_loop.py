"""Private SGLang full-prefill recurrence, retaining native FA3/GDN kernels.

No decode/prefix/chunk-cache semantics are supported. Reused depth passes must
all start from zero prefix; GDN prefill receives has_initial_state=False.
"""
import json
import os
from pathlib import Path

_INSTALLED=False



def mix_hidden_fp32(before, after, alpha):
    # Exactly the same FP32 subtract/multiply/add sequence, with one buffer.
    # Avoid allocating several full-sequence FP32 temporaries on long inputs.
    import torch
    mixed=after.float()
    if mixed is after:mixed=mixed.clone()
    mixed.sub_(before)
    mixed.mul_(float(alpha))
    mixed.add_(before)
    return mixed.to(before.dtype)


def install():
    global _INSTALLED
    if _INSTALLED:return
    path=os.environ.get('V35_LOOP_CONFIG')
    if not path or not Path(path).is_file():return
    recipe=json.loads(Path(path).read_text())
    materialize_each=os.environ.get('V35_SGLANG_MATERIALIZE_EACH_LAYER')=='1'
    if not recipe.get('blocks') and not materialize_each:return
    import torch
    from sglang.srt.models.qwen3_5 import Qwen3_5ForCausalLM
    from sglang.srt.layers.layer_boundary.residual import batch as residual_batch
    native=Qwen3_5ForCausalLM.forward
    starts=dict(recipe['blocks']);weights=tuple(recipe['weights'])

    @torch.no_grad()
    def forward(self,input_ids,positions,forward_batch,input_embeds=None,
                pp_proxy_tensors=None,input_deepstack_embeds=None):
        assert self.pp_group.is_first_rank and self.pp_group.is_last_rank
        assert self.flashinfer_mnnvl_cutedsl_fusion is None
        mode=forward_batch.forward_mode
        if mode.is_idle():
            return native(self,input_ids,positions,forward_batch,input_embeds,pp_proxy_tensors,input_deepstack_embeds)
        assert mode.is_extend(),'V35 loops permit full prefill only; no decode'
        prefix=forward_batch.extend_prefix_lens_cpu
        assert all(int(x)==0 for x in prefix),'Cross-depth/prefix states are forbidden'
        assert not self.layers_to_capture
        h=self.embed_tokens(input_ids) if input_embeds is None else input_embeds
        residual_batch.start(forward_batch)
        calls=0;i=self.start_layer;visits={};state_resets=0;state_context=None
        while i<self.end_layer:
            end=starts.get(i,i+1)
            step_weights=weights if i in starts else (1.0,)
            for alpha in step_weights:
                if i in starts:
                    # Fold any deferred/fused residual and retain an owned
                    # snapshot: native fused norms can mutate residual storage.
                    h=residual_batch.fold(h,forward_batch)
                    before=h.clone()
                for j in range(i,end):
                    if visits.get(j,0):
                        # Prefix lengths zero the conv prefill, but the Triton
                        # GDN extend kernel still reads its SSM cache directly.
                        # A second DEPTH pass must start with an empty state.
                        if state_context is None:
                            from sglang.srt.model_executor.forward_context import get_attn_backend
                            backend=get_attn_backend()
                            linear_backend=getattr(backend,'linear_attn_backend',backend)
                            pool=linear_backend.req_to_token_pool
                            indices=linear_backend.forward_metadata.mamba_cache_indices.long()
                            assert bool((indices>=0).all())
                            state_context=(pool,indices)
                        pool,indices=state_context
                        if j in pool.mamba_map:
                            layer_cache=pool.mamba2_layer_cache(j)
                            layer_cache.temporal.index_fill_(0,indices,0)
                            for state in layer_cache.conv:state.index_fill_(0,indices,0)
                            state_resets+=1
                    visits[j]=visits.get(j,0)+1
                    h=self.layers[j](positions=positions,hidden_states=h,forward_batch=forward_batch,
                                   captured_last_layer_outputs=None)
                    if materialize_each:
                        # Match HF's explicit BF16 residual addition before
                        # the next normalization, instead of the fused pair.
                        h=residual_batch.fold(h,forward_batch)
                    calls+=1
                    if input_deepstack_embeds is not None and input_deepstack_embeds.numel()>0 and j<3:
                        sep=self.hidden_size*j
                        h=residual_batch.add_to_output(h,forward_batch,input_deepstack_embeds[:,sep:sep+self.hidden_size])
                if i in starts:
                    h=residual_batch.fold(h,forward_batch)
                    h=mix_hidden_fp32(before,h,alpha)
                    h=residual_batch.set_written(h,forward_batch)
            i=end
        expected=self.end_layer-self.start_layer+(len(weights)-1)*sum(b-a for a,b in recipe['blocks'])
        assert calls==expected,(calls,expected)
        self.v35_last_layer_calls=calls
        self.v35_last_state_resets=state_resets
        if not getattr(self,'v35_execution_reported',False):
            print('V35_SGLANG_LOOP_ACTIVE',json.dumps({'layer_calls':calls,'recipe':recipe,
                  'zero_prefix_only':True,'shared_weights':True,'residual_materialized':True,
                  'gdn_states_explicitly_zeroed_per_repeat':True,'state_resets_per_forward':state_resets,
                  'materialize_every_layer':materialize_each}),flush=True)
            self.v35_execution_reported=True
        return residual_batch.final_norm(h,forward_batch,self.norm,skip_empty=True)

    Qwen3_5ForCausalLM.forward=forward
    _INSTALLED=True
