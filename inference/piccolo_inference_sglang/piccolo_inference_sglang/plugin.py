"""Register the endpoint through SGLang's general plugin hook."""
from sglang.srt.plugins.hook_registry import HookRegistry, HookType


def register():
    HookRegistry.register(
        "sglang.srt.entrypoints.http_server._setup_and_run_http_server",
        install_endpoint,
        HookType.BEFORE,
    )


def install_endpoint(server_args, *args, **kwargs):
    from sglang.srt.entrypoints.http_server import app
    from .serving import SystemOne
    from .vision import Vision

    handler = SystemOne(
        server_args.tokenizer_path or server_args.model_path,
        server_args.served_model_name or server_args.model_path,
    )
    # This plugin explicitly selects the evaluated Flex layout in place of the
    # built-in SystemOne layout. Keep SGLang's other routes and auth middleware.
    app.router.routes[:] = [
        route for route in app.router.routes
        if getattr(route, "path", None) != "/v1/systemone"
    ]
    app.add_api_route("/v1/systemone", handler.handle, methods=["POST"], name="piccolo_systemone")
    vision = Vision(
        server_args.served_model_name or server_args.model_path,
        server_args.tokenizer_path or server_args.model_path,
    )
    app.router.routes[:] = [
        route for route in app.router.routes
        if getattr(route, "path", None) not in ("/v1/decisions", "/v1/decisions/runtime")
    ]
    app.add_api_route("/v1/decisions", vision.handle, methods=["POST"], name="piccolo_decisions")
    app.add_api_route("/v1/decisions/runtime", vision.runtime_handle, methods=["GET"], name="piccolo_vision_runtime")
    app.router.add_event_handler("shutdown", vision.close)
    app.openapi_schema = None
