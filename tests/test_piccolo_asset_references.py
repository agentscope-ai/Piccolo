"""CPU regressions for literal asset references in exported checkpoint code."""

from importlib import import_module
from pathlib import Path

import pytest


@pytest.fixture
def inputs(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts/checkpoints"))
    return import_module("piccolo_checkpoint.common_inputs")


@pytest.mark.parametrize(
    ("asset_ids", "text", "expected"),
    [
        (("cat",), "category", (1, "egory")),
        (("cat",), "这张cat图片_cat2", ("这张", 1, "图片_", 1, "2")),
        (("a.b",), "xa.b/aXb", ("x", 1, "/aXb")),
        (("cat", "category"), "category", (1,)),
        (("cat", "category"), "categorycat", (1, 2)),
        (("ab", "bc"), "abc", (1, "c")),
        (("cat",), "catcat", (1, 1)),
    ],
)
def test_asset_references_match_literal_substrings(inputs, asset_ids, text, expected):
    payload = {
        "state": text,
        "questions": {"q": {"type": "noul"}},
        "assets": {key: {"type": "image", "path": f"/tmp/{key}.png"} for key in asset_ids},
    }
    decision = inputs.prepare_decision(inputs.prepare_request(payload), "q")
    assert decision.state_parts == expected
