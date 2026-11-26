"""Request validation, asset binding, candidate mappings and prompt construction."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, TypedDict
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecisionText = str | dict[str, Any] | list[Any]
MAX_SCORE_LEVELS = 10
DEFAULT_CHOICE_LABELS = tuple(
    (
        "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z AA AB AC AD AE AF AG"
        " AH AI AJ AK AL AM AN AO AP AQ AR AS AT AU AV AW AX AY AZ BA BB BC BD BE"
        " BF BG BH BI BJ BK BL BM BN BO BP BR BS BT BU BV BW BX BY CA CB CC CD CE"
        " CF CG CH CI CK CL CM CN CO CP CR CS CT CU CV CW CX CY DA DB DC DD DE DF"
        " DG DH DI DJ DK DL DM DN DO DP DR DS DT DU DV DW DX DY EA EB EC ED EE EF"
        " EG EH EI EK EL EM EN EO EP EQ ER ES ET EU EV EW EX EZ FA FB FC FD FE FF"
        " FG FH FI FK FL FM FN FO FP FR FS FT FU FW FX FY GA GB GC GD GE GF GG GH"
        " GI GL GM GN GO GP GR GS GT GU GV GW GX GY HA HB HC HD HE HF HG HH HI HK"
        " HL HM HN HO HP HQ HR HS HT HU HV HW HX HY HZ IA IB IC ID IE IF IG IH II"
        " IJ IK IL IM IN IO IP IQ IR IS IT IU IV IW IX IZ JA JB JC JD JE JI JJ JK"
        " JM JO JP JR JS JT"
    ).split()
)


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instructions: DecisionText | None = None


class SystemOneNoulCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    true: DecisionText | None = None
    false: DecisionText | None = None


class SystemOneNoulQuestion(_Question):
    type: Literal["noul"]
    criteria: SystemOneNoulCriteria | None = None


class SystemOneChoiceQuestion(_Question):
    type: Literal["choice"]
    criteria: dict[str, DecisionText | None] = Field(min_length=1, max_length=len(DEFAULT_CHOICE_LABELS))


class SystemOneScoreQuestion(_Question):
    type: Literal["score"]
    criteria: list[DecisionText] = Field(min_length=1, max_length=MAX_SCORE_LEVELS)


SystemOneQuestion = Annotated[
    SystemOneNoulQuestion | SystemOneChoiceQuestion | SystemOneScoreQuestion,
    Field(discriminator="type"),
]


class SystemOneInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    state: DecisionText
    questions: dict[str, SystemOneQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def _finite_json(self):
        json.dumps(self.model_dump(exclude_unset=True), allow_nan=False)
        return self


class SystemOneTextRequest(SystemOneInputs):
    model: str

    def prepare(self) -> PreparedRequest:
        """Prepare the validated HTTP body without validating its JSON again."""
        return _prepare_payload(self.model_dump(exclude={"model"}, exclude_unset=True))


def _compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def render_text(value) -> str:
    """Serialize structured content only at the prompt boundary."""
    if value is None:
        return ""
    return value if isinstance(value, str) else _compact_json(value)


def question_options(question):
    """Semantic option order; model-specific answer tokens are assigned later."""
    kind = question["type"]
    criteria = question.get("criteria")
    if kind == "choice":
        return list(criteria.items())
    if kind == "score":
        return [(str(i), value) for i, value in enumerate(criteria)]
    criteria = criteria or {}
    return [("false", criteria.get("false")), ("true", criteria.get("true"))]


def _validated_sources(assets):
    """Yield validated sources, keeping the bytes produced by strict Base64 decoding."""
    if not isinstance(assets, Mapping):
        raise ValueError("Piccolo assets must be an object")
    if any(
        not isinstance(key, str) or not key.strip() or len(key.encode()) > 1024 for key in assets
    ):
        raise ValueError(
            "Piccolo asset references must be nonempty strings of at most 1024 UTF-8 bytes"
        )
    if sum(len(key.encode()) for key in assets) > 65536:
        raise ValueError("Piccolo asset references exceed 65536 UTF-8 bytes")
    for key, asset in assets.items():
        if not isinstance(asset, Mapping) or set(asset) - {
            "type",
            "format",
            "data_base64",
            "part",
            "path",
            "url",
        }:
            raise ValueError(
                "Piccolo image assets accept type, format, data_base64, part, url and offline path"
            )
        if asset.get("type", "image") != "image":
            raise ValueError("Piccolo assets support images only")
        if "part" in asset:
            raise ValueError(
                "Piccolo cannot resolve multipart parts; materialize them as data_base64"
            )
        if "url" in asset:
            if set(asset) - {"type", "url"}:
                raise ValueError("Piccolo URL image assets accept only type and url")
            value = asset["url"]
            if not isinstance(value, str) or not value.startswith(("http://", "https://")):
                raise ValueError("Piccolo image url must use HTTP or HTTPS")
            try:
                parsed = urlparse(value)
                valid = bool(parsed.hostname) and (parsed.port is None or parsed.port > 0)
            except ValueError:
                valid = False
            if not valid or value.strip() != value:
                raise ValueError("Piccolo image url must have a valid HTTP/HTTPS host")
            yield key, value
            continue
        if "path" in asset:
            if set(asset) != {"type", "path"}:
                raise ValueError("Local Piccolo image assets require only type and path")
            value = asset["path"]
            if not isinstance(value, str) or not value.strip() or "://" in value:
                raise ValueError("Piccolo image path must name a local file")
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise ValueError("Resolve relative Piccolo image paths at the dataset boundary")
            yield key, str(path)
            continue
        fmt, data = (asset.get("format"), asset.get("data_base64"))
        if fmt not in {"png", "jpg", "jpeg"} or not isinstance(data, str) or (not data):
            raise ValueError("Piccolo image assets require png/jpg/jpeg format and data_base64")
        try:
            decoded = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Piccolo data_base64 must be standard base64 without a data: prefix"
            ) from error
        yield key, decoded


class JevRequest(TypedDict):
    state: DecisionText
    questions: dict[str, dict[str, Any]]
    assets: NotRequired[dict[str, dict[str, Any]]]


def _reference_pattern(asset_ids) -> re.Pattern[str] | None:
    """Match literal substrings, preferring the longest ID at the same position."""
    if not asset_ids:
        return None
    return re.compile("|".join(re.escape(key) for key in sorted(asset_ids, key=len, reverse=True)))


def _asset_references(value, pattern: re.Pattern[str]) -> Iterator[str]:
    """Yield matching IDs from string values in encounter order."""
    if isinstance(value, str):
        yield from (match.group() for match in pattern.finditer(value))
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _asset_references(item, pattern)
    elif isinstance(value, list):
        for item in value:
            yield from _asset_references(item, pattern)


@dataclass(frozen=True)
class PiccoloInputs:
    jev_request: JevRequest
    question_key: str
    asset_order: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    description: DecisionText | None


@dataclass(frozen=True)
class PreparedDecision:
    prompt: PiccoloInputs
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class PreparedRequest:
    payload: JevRequest
    image_sources: dict[str, str | bytes]
    _asset_pattern: re.Pattern[str] | None = field(repr=False)
    _state_asset_ids: tuple[str, ...] = field(repr=False)


def prepare_request(payload: JevRequest) -> PreparedRequest:
    """Validate and prepare data shared by every question in the request."""
    payload = deepcopy(payload)
    SystemOneInputs.model_validate(payload)
    return _prepare_payload(payload)


def _prepare_payload(payload: JevRequest) -> PreparedRequest:
    sources = dict(_validated_sources(payload.get("assets", {})))
    pattern = _reference_pattern(sources)
    state_ids = (
        tuple(dict.fromkeys(_asset_references(payload["state"], pattern)))
        if pattern is not None
        else ()
    )
    return PreparedRequest(payload, sources, pattern, state_ids)


def prepare_decision(request: PreparedRequest, question_key: str) -> PreparedDecision:
    """Prepare one question while retaining the original request for Jinja."""
    payload = request.payload
    pattern = request._asset_pattern
    question = payload["questions"][question_key]
    options = question_options(question)

    order = dict.fromkeys(request._state_asset_ids)
    if pattern is not None:
        order.update(dict.fromkeys(_asset_references(question.get("instructions"), pattern)))
        for _, description in options:
            order.update(dict.fromkeys(_asset_references(description, pattern)))
    for key in request.image_sources:
        order.setdefault(key)

    labels = DEFAULT_CHOICE_LABELS[: len(options)]
    return PreparedDecision(
        prompt=PiccoloInputs(payload, question_key, tuple(order)),
        candidates=tuple(
            Candidate(key, label, description)
            for (key, description), label in zip(options, labels, strict=True)
        ),
    )
