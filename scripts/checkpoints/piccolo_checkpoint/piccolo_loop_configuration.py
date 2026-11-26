"""Piccolo loop architecture identity and strict structural configuration."""

from transformers.models.qwen3_5.configuration_qwen3_5 import Qwen3_5VisionConfig

from .loop_utils import normalize_loop_config
from .piccolo_configuration import PiccoloConfig, PiccoloTextConfig


class PiccoloLoopTextConfig(PiccoloTextConfig):
    model_type = "piccolo_qwen3_5_loop_text"


class PiccoloLoopVisionConfig(Qwen3_5VisionConfig):
    model_type = "piccolo_qwen3_5_loop_vision"


class PiccoloLoopConfig(PiccoloConfig):
    model_type = "piccolo_qwen3_5_loop"
    has_no_defaults_at_init = True
    sub_configs = {
        **PiccoloConfig.sub_configs,
        "text_config": PiccoloLoopTextConfig,
        "vision_config": PiccoloLoopVisionConfig,
    }

    def __init__(self, loop_config=None, **kwargs):
        for key in ("text_config", "vision_config"):
            if isinstance(kwargs.get(key), dict):
                kwargs[key] = {k: v for k, v in kwargs[key].items() if k != "model_type"}
        super().__init__(**kwargs)
        self.loop_config = normalize_loop_config(
            loop_config, self.text_config.num_hidden_layers, self.vision_config.depth
        )
        if getattr(self.vision_config, "deepstack_visual_indexes", []):
            raise ValueError("PiccoloLoop does not support deepstack visual features")
        self.use_cache = self.text_config.use_cache = False
        self.text_config.loop_section = self.loop_config["text"]
        self.vision_config.loop_section = self.loop_config["vision"]

    def to_dict(self):
        result = super().to_dict()
        for key in ("text_config", "vision_config"):
            result[key].pop("loop_section", None)
        return result


PiccoloLoopConfig.register_for_auto_class()
