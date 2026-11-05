"""Lifecycle policy applied without changing SGLang source files."""

import inspect
import logging
import os
from contextvars import ContextVar

_MODEL = ContextVar("piccolo_initializing_model", default=None)
logger = logging.getLogger(__name__)


def adapter_of(model):
    return getattr(model, "_piccolo_adapter", None)


def initialize_model(previous, model, *args, **kwargs):
    # Restrict configuration adaptation to this instance's private HF copy.
    token = _MODEL.set(model)
    try:
        return previous(model, *args, **kwargs)
    finally:
        _MODEL.reset(token)


def configure_model(previous, config, *args, **kwargs):
    model = _MODEL.get()
    if (
        model is not None
        and config is getattr(model, "hf_config", None)
        and config.model_type == "piccolo_qwen3_5"
    ):
        from .model import create_piccolo_adapter

        model._piccolo_adapter = create_piccolo_adapter(model)
        return model.hf_text_config
    return previous(config, *args, **kwargs)


def configure_server(server_args, previous):
    from sglang.srt.arg_groups.overrides import model_config_of

    adapter = adapter_of(model_config_of(server_args))
    if adapter is not None:
        adapter.configure_server_args(server_args)
    return previous(server_args)


def validate_request(previous, manager, obj, input_ids):
    adapter = adapter_of(manager.model_config)
    if adapter is not None:
        adapter.validate_request(manager, obj, input_ids)
    return previous(manager, obj, input_ids)


def validate_decisions(previous, serving, model):
    adapter = adapter_of(serving.tokenizer_manager.model_config)
    if adapter is not None:
        return f"{serving.route} requires /v1/systemone with the frozen Piccolo prompt"
    return previous(serving, model)


def execute_warmup(server_args):
    import requests
    from sglang.srt.entrypoints import http_server

    manager = http_server.get_global_state().tokenizer_manager
    if http_server._wait_for_http_server(server_args) is None:
        return False
    adapter = adapter_of(manager.model_config)
    path, payload = adapter.warmup_request(manager)
    headers = {"Authorization": f"Bearer {server_args.api_key}"} if server_args.api_key else {}
    timeout = http_server.envs.SGLANG_WARMUP_TIMEOUT.get()
    try:
        response = requests.post(
            server_args.url() + path,
            json=payload,
            headers=headers,
            timeout=timeout if timeout > 0 else 600,
            verify=http_server.ssl_verify_of(server_args),
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Piccolo classification warmup failed")
        http_server.kill_process_tree(os.getpid())
        return False
    manager.server_status = http_server.ServerStatus.Up
    return True


def warmup(previous, server_args, *args, **kwargs):
    from sglang.srt.entrypoints.http_server import get_global_state

    adapter = adapter_of(get_global_state().tokenizer_manager.model_config)
    if adapter is None:
        return previous(server_args, *args, **kwargs)
    # Override the callback rather than changing native readiness/cleanup logic.
    bound = inspect.signature(previous).bind(server_args, *args, **kwargs)
    bound.arguments["execute_warmup_func"] = execute_warmup
    return previous(*bound.args, **bound.kwargs)


_registered = False


def register():
    global _registered
    if _registered:
        return
    from sglang.srt.arg_groups.resolution_hooks import register_resolution_hook
    from sglang.srt.entrypoints import http_server
    from sglang.srt.plugins.hook_registry import HookRegistry, HookType

    from .serving import install_lifespan

    if "execute_warmup_func" not in inspect.signature(http_server._wait_and_warmup).parameters:
        raise RuntimeError("Piccolo requires the native warmup callback hook")

    targets = {
        "sglang.srt.configs.model_config.ModelConfig.__init__": initialize_model,
        "sglang.srt.configs.model_config.get_hf_text_config": configure_model,
        (
            "sglang.srt.managers.tokenizer_manager.TokenizerManager._validate_one_request"
        ): validate_request,
        (
            "sglang.srt.entrypoints.openai.serving_decisions.OpenAIServingDecisions."
            "_validate_server"
        ): validate_decisions,
        "sglang.srt.entrypoints.http_server._wait_and_warmup": warmup,
    }
    for target, hook in targets.items():
        HookRegistry.register(target, hook, HookType.AROUND)
    register_resolution_hook("handle_model_specific_adjustments")(configure_server)
    install_lifespan()
    _registered = True
