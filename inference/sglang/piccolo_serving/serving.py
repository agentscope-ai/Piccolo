"""Piccolo HTTP schema, responses and native SystemOne route binding."""

import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.routing import APIRoute
from sglang.srt.entrypoints.systemone.serving import (
    SystemOneServing,
    _choice_confidence,
    _normalized,
    _score_confidence,
)

from .encoding import PiccoloEncoder


def answer(question, option_keys, probabilities, question_id):
    kind = question.type
    if kind == "choice":
        names = list(question.criteria)
    elif kind == "noul":
        names = ["true", "false"]
    else:
        names = [str(i) for i in range(len(question.criteria))]
    if (
        len(probabilities) != len(option_keys)
        or len(option_keys) != len(names)
        or set(option_keys) != set(names)
        or not all(math.isfinite(p) for p in probabilities)
    ):
        raise RuntimeError(f"question {question_id!r} scored invalid values")
    by_key = dict(zip(option_keys, probabilities, strict=True))
    if kind == "noul":
        return {"type": "noul", "noul": by_key["true"]}
    by_key = {key: by_key[key] for key in names}
    probabilities = list(by_key.values())
    result = {"type": kind, "probabilities": by_key}
    normalized = _normalized(probabilities)
    if kind == "choice":
        result.update(
            choice=names[probabilities.index(max(probabilities))],
            confidence=_choice_confidence(normalized),
        )
    else:
        result.update(
            score=math.fsum(i * p for i, p in enumerate(probabilities)),
            confidence=_score_confidence(normalized),
            legend=dict(zip(names, question.criteria, strict=True)),
        )
    return result


class PiccoloServing(SystemOneServing):
    def __init__(self, chat_serving):
        super().__init__(chat_serving)
        self.encoder = PiccoloEncoder(self.tokenizer_manager)

    def _validate_request(self, request):
        if request.model != self.tokenizer_manager.served_model_name:
            return "Unknown served model"
        return None

    def _convert_to_internal_request(self, request, raw_request=None):
        encoded, encoded_questions = self.encoder.encode_request(request)
        return encoded, (encoded_questions, request.questions)

    async def _handle_non_streaming_request(self, adapted_request, processed, raw_request):
        encoded_questions, questions = processed
        _, _, result = await self._score(
            adapted_request=adapted_request,
            raw_request=raw_request,
            temperature=1.0
            if self.decision_config is None
            else self.decision_config["temperature"],
        )
        return ORJSONResponse(
            content={
                "model": self.tokenizer_manager.served_model_name,
                "answers": {
                    key: answer(questions[key], option_keys, probabilities, key)
                    for (key, option_keys), probabilities in zip(
                        encoded_questions, result.scores, strict=True
                    )
                },
                "usage": {"input_tokens": result.prompt_tokens, "output_tokens": 0},
            }
        )


def bind_systemone_adapter(app: FastAPI, serving) -> None:
    async def decisions(request, raw_request: Request):
        return await raw_request.app.state.systemone_serving.handle_request(request, raw_request)

    decisions.__annotations__["request"] = serving.encoder.request_schema
    for index, route in enumerate(app.router.routes):
        if (
            isinstance(route, APIRoute)
            and route.path == "/v1/systemone"
            and "POST" in route.methods
        ):
            app.router.routes[index] = APIRoute(
                route.path,
                decisions,
                methods=route.methods,
                dependencies=route.dependencies,
                response_class=route.response_class,
                response_model=route.response_model,
                name=route.name,
                tags=route.tags,
                summary=route.summary,
                description=route.description,
                responses=route.responses,
                deprecated=route.deprecated,
                include_in_schema=route.include_in_schema,
                operation_id=route.operation_id,
                openapi_extra=route.openapi_extra,
            )
            app.state.systemone_serving = serving
            app.openapi_schema = None
            return
    raise RuntimeError("SGLang SystemOne route is unavailable")


def install_lifespan():
    from sglang.srt.entrypoints import http_server

    app = http_server.app
    if getattr(app.state, "_piccolo_lifespan_installed", False):
        return
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        # Native startup creates chat serving and starts its warmup thread. That
        # thread waits for the HTTP listener, which starts only after we yield.
        async with original(app) as state:
            from .plugin import adapter_of

            adapter = adapter_of(http_server.get_global_state().tokenizer_manager.model_config)
            if adapter is not None:
                serving = adapter.create_serving(app.state.openai_serving_chat)
                bind_systemone_adapter(app, serving)
            yield state

    app.router.lifespan_context = lifespan
    app.state._piccolo_lifespan_installed = True
