"""Piccolo HTTP schema, responses and native SystemOne route binding."""

import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.routing import APIRoute
from piccolo_hf.common_inputs import SystemOneTextRequest as PiccoloRequest
from sglang.srt.entrypoints.openai.serving_decisions import QuestionView
from sglang.srt.entrypoints.systemone.serving import (
    SystemOneServing,
    _choice_confidence,
    _normalized,
    _score_confidence,
)

from .encoding import PiccoloEncoder


def question_view(question):
    if question.type == "choice":
        return QuestionView(
            kind="choice",
            question=question.instructions,
            names=list(question.criteria),
            details=list(question.criteria.values()),
        )
    if question.type == "noul":
        criteria = question.criteria
        return QuestionView(
            kind="yes_no",
            question=question.instructions,
            names=["yes", "no"],
            details=[criteria.true if criteria else None, criteria.false if criteria else None],
        )
    return QuestionView(
        kind="score",
        question=question.instructions,
        names=[str(i) for i in range(len(question.criteria))],
        details=list(question.criteria),
    )


def answer(view, probabilities, question_id):
    if len(probabilities) != len(view.names) or not all(math.isfinite(p) for p in probabilities):
        raise RuntimeError(f"question {question_id!r} scored invalid values")
    if view.kind == "yes_no":
        return {"type": "noul", "noul": probabilities[0]}
    result = {"type": view.kind, "probabilities": dict(zip(view.names, probabilities, strict=True))}
    normalized = _normalized(probabilities)
    if view.kind == "choice":
        result.update(
            choice=view.names[probabilities.index(max(probabilities))],
            confidence=_choice_confidence(normalized),
        )
    else:
        result.update(
            score=math.fsum(i * p for i, p in enumerate(probabilities)),
            confidence=_score_confidence(normalized),
            legend=dict(zip(view.names, view.details, strict=True)),
        )
    return result


class PiccoloServing(SystemOneServing):
    def __init__(self, chat_serving, *, directory):
        super().__init__(chat_serving)
        self.encoder = PiccoloEncoder(self.tokenizer_manager, directory=directory)

    def _validate_request(self, request):
        if request.model != self.tokenizer_manager.served_model_name:
            return "Unknown served model"
        return None

    def _convert_to_internal_request(self, request, raw_request=None):
        views = [question_view(question) for question in request.questions.values()]
        encoded = self.encoder.encode_request(request)
        return encoded, (request, views)

    async def _handle_non_streaming_request(self, adapted_request, processed, raw_request):
        request, views = processed
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
                    key: answer(view, probabilities, key)
                    for key, view, probabilities in zip(
                        request.questions, views, result.scores, strict=True
                    )
                },
                "usage": {"input_tokens": result.prompt_tokens, "output_tokens": 0},
            }
        )


def bind_systemone_adapter(app: FastAPI, serving) -> None:
    async def decisions(request, raw_request: Request):
        return await raw_request.app.state.systemone_serving.handle_request(request, raw_request)

    decisions.__annotations__["request"] = PiccoloRequest
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
