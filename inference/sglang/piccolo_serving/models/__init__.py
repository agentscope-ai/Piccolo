"""Select the adapter for an explicitly tagged Piccolo architecture."""

from .piccolo.adapter import PiccoloAdapter
from .piccolo_loop.adapter import PiccoloLoopAdapter

ADAPTERS = {
    "piccolo_qwen3_5": PiccoloAdapter,
    "piccolo_qwen3_5_loop": PiccoloLoopAdapter,
}


def create_adapter(model_config):
    return ADAPTERS[model_config.hf_config.model_type](model_config)
