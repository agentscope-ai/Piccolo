"""HF configuration identities for Piccolo's complete-prompt classifier."""

from transformers.models.qwen3_5.configuration_qwen3_5 import Qwen3_5Config, Qwen3_5TextConfig


class PiccoloTextConfig(Qwen3_5TextConfig):
    model_type = "piccolo_qwen3_5_text"


class PiccoloConfig(Qwen3_5Config):
    model_type = "piccolo_qwen3_5"
    sub_configs = {**Qwen3_5Config.sub_configs, "text_config": PiccoloTextConfig}


PiccoloConfig.register_for_auto_class()
