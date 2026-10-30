"""Exercise the native Jev client against a loopback HTTP fixture."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from scripts.check_qwenpaw_local import check_provider
from qwenpaw.providers.services.qwenpaw import QwenPawProvider
from qwenpaw.providers.typesafe_provider import TypeSafeEvaluationError


@pytest.fixture
def local_service():
    state = SimpleNamespace(mode="ok", requests=[])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append((self.path, body))
            assert self.path == "/v1/systemone"
            assert self.headers.get("Authorization") == "Bearer local"
            assert not self.headers.get("Content-Encoding")
            questions = body["questions"]
            answers = {}
            for name, question in questions.items():
                if question["type"] == "noul":
                    answers[name] = {"type": "noul", "noul": 0.01}
                else:
                    answers[name] = {
                        "type": "choice",
                        "choice": "routine",
                        "confidence": 0.99,
                        "probabilities": {
                            "routine": 0.99,
                            "read_only": 0.01,
                            "risky": 0,
                            "unclear": 0,
                        },
                    }
                    if state.mode == "missing_confidence":
                        answers[name].pop("confidence")
            status = 503 if state.mode == "unavailable" else 200
            response = (
                {"error": {"message": "Loading"}}
                if status == 503
                else {
                    "model": "piccolo-fixture",
                    "answers": answers,
                    "usage": {"input_tokens": 40, "output_tokens": 0},
                }
            )
            content = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.provider = QwenPawProvider(
        id="qwenpaw-local",
        name="Local fixture",
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        models=[
            {"id": "piccolo-fixture", "name": "Piccolo fixture", "model_type": "decision"}
        ],
    )
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_native_local_clients_without_api_key(local_service):
    result = asyncio.run(check_provider(local_service.provider, "piccolo-fixture"))
    assert result["status"] == "local_decision_interface_ok"
    assert result["model_quality_evaluated"] is False
    assert result["approval_sample_needs_approval"] is False
    assert result["context_sample_probability"] == 0.01
    assert [path for path, _ in local_service.requests] == ["/v1/systemone"] * 2


def test_local_checker_rejects_unavailable_model(local_service):
    local_service.mode = "unavailable"
    with pytest.raises((ValueError, TypeSafeEvaluationError)):
        asyncio.run(check_provider(local_service.provider, "piccolo-fixture"))
    assert len(local_service.requests) == 1


def test_missing_confidence_falls_back_to_approval(local_service):
    local_service.mode = "missing_confidence"
    with pytest.raises(TypeSafeEvaluationError):
        asyncio.run(check_provider(local_service.provider, "piccolo-fixture"))
