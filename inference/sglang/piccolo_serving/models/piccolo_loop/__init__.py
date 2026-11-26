"""Register PiccoloLoop's SGLang execution class when its checkpoint is selected."""

from functools import cache


@cache
def register():
    from sglang.srt.models.registry import ModelRegistry

    ModelRegistry.register(__name__, strict=True)
