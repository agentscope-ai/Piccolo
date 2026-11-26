"""PiccoloLoop configuration and complete-prefill execution constraints."""

from ..piccolo.adapter import PiccoloAdapter


class PiccoloLoopAdapter(PiccoloAdapter):
    def _configure_model(self, model_config):
        from . import register

        config = super()._configure_model(model_config)
        physical_types = [
            "full_attention" if kind == "attention" else "linear_attention"
            for kind in model_config.hf_text_config.layers_block_type
        ]
        if config["text_config"]["layer_types"] != physical_types:
            raise ValueError(
                "SGLang PiccoloLoop requires physical layer_types to match full_attention_interval"
            )
        register()
        # Native architecture names also drive SGLang's multimodal detection.
        # The registered loop class stays first for execution.
        model_config.hf_config.architectures = [
            "PiccoloLoopForConditionalGeneration",
            "Qwen3_5ForConditionalGeneration",
        ]
        model_config.hf_text_config.loop_section = config["loop_config"]["text"]
        model_config.hf_config.vision_config.loop_section = config["loop_config"]["vision"]
        return config

    def configure_server_args(self, server_args):
        from sglang.srt.arg_groups.overrides import declare_resolution, resolving_view
        from sglang.srt.model_executor.cuda_graph_config import CudaGraphConfig, PhaseConfig

        super().configure_server_args(server_args)
        settings = resolving_view(server_args)
        if settings.quantization or settings.tp_size != 1 or settings.pp_size != 1:
            raise ValueError("PiccoloLoop requires unquantized TP=PP=1 inference")
        if settings.kv_cache_dtype != "auto":
            raise ValueError("PiccoloLoop requires kv_cache_dtype=auto")
        declare_resolution(
            server_args,
            "piccolo_loop_serving_adapter",
            disable_cuda_graph=True,
            # Explicit phase configuration takes precedence over user phase flags.
            cuda_graph_config=CudaGraphConfig(
                prefill=PhaseConfig(backend="disabled"),
                decode=PhaseConfig(backend="disabled"),
            ),
        )


