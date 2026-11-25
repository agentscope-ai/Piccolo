"""Five-size shared-depth runtime. No model weights or inference prompts changed."""
import functools,json,os,weakref
from pathlib import Path
_installed=False

def install():
 global _installed
 if _installed:return
 profile=json.loads(Path(os.environ['PICCOLO_LOOP_PROFILE']).read_text())
 recipe=profile['recipe']; model_config=json.loads((Path(os.environ['PICCOLO_CHECKPOINT'])/'config.json').read_text())
 depth=model_config['text_config']['num_hidden_layers']
 assert recipe['language_layer_calls']==depth+sum(e-s for s,e in recipe['blocks'])*(len(recipe['per_block_pass_alphas'])-1)
 for s,e in recipe['blocks']:assert 0<=s<e<=depth
 from .v35_sglang_loop import install as language_install
 language_install()
 vision=recipe['vision'];vdepth=model_config['vision_config']['depth']
 if vision['blocks']:
  # Currently archived 9B profile loops exactly one vision block.
  assert all(e==s+1 for s,e in vision['blocks']), 'Multi-block vision recurrence requires a separately tested adapter'
  import torch
  from sglang.srt.models.qwen3_vl import Qwen3VLMoeVisionModel,Qwen3_VisionBlock
  native_init=Qwen3VLMoeVisionModel.__init__;native_forward=Qwen3VLMoeVisionModel.forward;native_block=Qwen3_VisionBlock.forward
  target={s for s,e in vision['blocks']};alphas=vision['per_block_pass_alphas']
  @functools.wraps(native_init)
  def init(self,*args,**kwargs):
   native_init(self,*args,**kwargs)
   assert len(self.blocks)==vdepth
   for i,block in enumerate(self.blocks):block._piccolo_loop_index=i;block._piccolo_loop_parent_ref=weakref.ref(self)
   self._piccolo_vision_counts=[0]*vdepth
  @functools.wraps(native_block)
  def block_forward(self,x,*args,**kwargs):
   ref=getattr(self,'_piccolo_loop_parent_ref',None)
   parent=ref() if ref is not None else None
   if parent is None:return native_block(self,x,*args,**kwargs)
   i=self._piccolo_loop_index
   if i not in target:
    parent._piccolo_vision_counts[i]+=1
    return native_block(self,x,*args,**kwargs)
   for alpha in alphas:
    # Native SGLang vision blocks update x in-place; a clone is essential.
    before=x.clone();parent._piccolo_vision_counts[i]+=1
    y=native_block(self,x,*args,**kwargs)
    x=(before.float()+float(alpha)*(y.float()-before.float())).to(y.dtype)
   return x
  @functools.wraps(native_forward)
  def forward(self,*args,**kwargs):
   self._piccolo_vision_counts=[0]*len(self.blocks)
   out=native_forward(self,*args,**kwargs)
   expected=[len(alphas) if i in target else 1 for i in range(len(self.blocks))]
   assert self._piccolo_vision_counts==expected,(self._piccolo_vision_counts,expected)
   if not getattr(self,'_piccolo_reported',False):
    print('PICCOLO_VISION_LOOP_ACTIVE',json.dumps({'vision_counts':self._piccolo_vision_counts,'vision_layer_calls':sum(expected),'recipe':vision}),flush=True);self._piccolo_reported=True
   return out
  Qwen3VLMoeVisionModel.__init__=init;Qwen3VLMoeVisionModel.forward=forward;Qwen3_VisionBlock.forward=block_forward
 _installed=True
 print('PICCOLO_LOOP_PROFILE',json.dumps({'size':profile.get('name'), 'recipe':recipe,'language_depth':depth,'vision_depth':vdepth}),flush=True)
