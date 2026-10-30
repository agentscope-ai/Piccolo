#!/usr/bin/env python3
"""Check the selected native llama.cpp decision model using synthetic inputs.

Run with the patched QwenPaw environment. No standalone Piccolo service, key,
endpoint, weight download, tool execution, or configuration write is needed.
"""

import argparse
import asyncio
import json
import sys


async def check_provider(provider, model):
    from qwenpaw.security.decision_model import _QUESTIONS, _interpret
    from reme.components.as_decision_model import AgentScopeAsDecisionModel

    if provider.id not in {"qwenpaw-local"}:
        raise ValueError("Select a Piccolo-capable llama.cpp decision model first")
    provider.validate_model_selection(model, "decision")
    review = await provider.evaluate(
        model=model,
        state={
            "schema": "tool-risk-v4",
            "tool": "write_file",
            "operation": "write",
            "target": "/tmp/piccolo-protocol-example.txt",
            "parameter_names": ["content", "path"],
            "sandboxed": True,
            "baseline_ask": True,
            "risk_signals": [],
        },
        questions=_QUESTIONS,
    )
    assessment = _interpret(review, baseline_ask=True)
    classifier = await provider.as_decision_model_async(model, max_retries=0)
    component = AgentScopeAsDecisionModel()
    component.model = classifier
    try:
        result = await component(
            state={"task": "Report the test exit code", "tool_result": "exit_code=0"},
            questions={
                "keep": {"type": "binary", "instructions": "Relevant to this task?"}
            },
        )
    finally:
        try:
            await component.close()
        finally:
            await classifier.client.aclose()
    return {
        "status": "local_decision_interface_ok",
        "provider": provider.id,
        "requested_model": model,
        "returned_model": review.model,
        "approval_sample_needs_approval": assessment.needs_approval,
        "context_sample_probability": result.content["keep"].probability,
        "probability_source": "candidate_token_logits",
        "model_quality_evaluated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        help="Use this agent's decision selection; otherwise use the global default",
    )
    args = parser.parse_args()
    try:
        from qwenpaw.config.config import load_agent_config
        from qwenpaw.providers.typesafe_provider import resolve_decision_model

        slot = (
            load_agent_config(args.agent_id).decision_model if args.agent_id else None
        )
        provider, model = resolve_decision_model(slot)
        result = asyncio.run(check_provider(provider, model))
    except Exception as exc:
        # Do not print credentials, request bodies or server-controlled errors.
        print(
            f"Local decision check failed ({type(exc).__name__}). "
            "Check the selected model and the setup in docs/QWENPAW.md.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
