"""The evaluated Flex readout, using the in-process SGLang tokenizer manager."""
import asyncio
import hashlib
import json
import math

from fastapi import Request
from starlette.responses import JSONResponse
from transformers import AutoTokenizer
from sglang.srt.managers.io_struct import GenerateReqInput

from .flex_prompt import FlexPromptCompiler, Unsupported


class SystemOne:
    def __init__(self, tokenizer_path, model):
        self.model = model
        self.compiler = FlexPromptCompiler(
            AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True),
            layout="header", read_twice=True, twice_max_tokens=3000,
            max_row_tokens=65535,
        )

    async def handle(self, request: Request):
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "request body must be valid JSON"}, status_code=400)
        if not isinstance(payload, dict) or "state" not in payload:
            return JSONResponse({"error": "request must be an object containing state and questions"}, status_code=400)
        questions = payload.get("questions")
        if not isinstance(questions, dict) or not questions:
            return JSONResponse({"error": "questions must contain at least one question"}, status_code=400)
        for question in questions.values():
            if not isinstance(question, dict) or not {"type", "instructions"} <= question.keys():
                return JSONResponse({"error": "question must contain type and instructions"}, status_code=400)
            if not question["instructions"]:
                return JSONResponse({"error": "instructions must be non-empty"}, status_code=400)
        try:
            return JSONResponse(await self.infer(payload, request))
        except Unsupported as error:
            return JSONResponse({"error": f"maximum context length exceeded: {error}"}, status_code=422)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        except (KeyError, TypeError, RuntimeError, OSError) as error:
            return JSONResponse({"error": str(error)}, status_code=502)

    async def infer(self, payload, request):
        from sglang.srt.entrypoints.http_server import get_global_state

        if payload.get("model", self.model) != self.model:
            raise ValueError("model must match the served model")
        rows, identity = await asyncio.to_thread(
            self.compiler.compile, payload["state"], payload["questions"],
            training_extension=True,
        )
        manager = get_global_state().tokenizer_manager
        slots = asyncio.Semaphore(64)

        async def one(row):
            async with slots:
                obj = GenerateReqInput(
                    input_ids=list(row.input_ids),
                    sampling_params={"max_new_tokens": 1, "temperature": 0},
                    return_logprob=True,
                    token_ids_logprob=list(row.candidate_token_ids),
                )
                response = await manager.generate_request(obj, request).__anext__()
            meta = response["meta_info"]
            scores_by_id = {token_id: score for score, token_id, _ in meta["output_token_ids_logprobs"][0]}
            scores = [scores_by_id[t] for t in row.candidate_token_ids]
            if not all(math.isfinite(x) for x in scores):
                raise ValueError("Nonfinite candidate logprob")
            weights = [math.exp(x - max(scores)) for x in scores]
            probs = [x / sum(weights) for x in weights]
            answer = {"type": row.kind}
            if row.kind == "noul":
                answer["noul"] = probs[row.option_keys.index(True)]
            else:
                answer["confidence"] = 1 + sum(p * math.log(p) for p in probs if p) / math.log(len(probs))
                if row.kind == "choice":
                    answer["probabilities"] = dict(zip(row.option_keys, probs))
                    answer["choice"] = row.option_keys[max(range(len(probs)), key=probs.__getitem__)]
                else:
                    answer["probabilities"] = dict(zip(map(str, range(len(probs))), probs))
                    answer["score"] = sum(i * p for i, p in enumerate(probs))
                    criteria = payload["questions"][row.question_id]["criteria"]
                    descriptions = list(criteria.values()) if isinstance(criteria, dict) else criteria
                    answer["legend"] = dict(zip(map(str, range(len(probs))), descriptions))
            trace = {
                "scores": scores, "labels": list(row.option_keys),
                "candidate_ids": list(row.candidate_token_ids),
                "prompt_sha256": hashlib.sha256(json.dumps(row.input_ids, separators=(",", ":")).encode()).hexdigest(),
            }
            return row.question_id, answer, meta, trace

        results = await asyncio.gather(*(one(row) for row in rows))
        usage = {key: sum(meta[field] for _, _, meta, _ in results)
                 for key, field in [("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"), ("cached_tokens", "cached_tokens")]}
        return {
            "model": self.model, "answers": {k: a for k, a, _, _ in results}, "usage": usage,
            "evaluation_trace": {"flex": identity, "candidate_readouts": {k: t for k, _, _, t in results}},
        }
