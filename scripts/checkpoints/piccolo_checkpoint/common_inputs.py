"""Request validation, asset binding, candidate mappings and prompt construction."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, TypedDict
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecisionText = str | dict[str, Any] | list[Any]
MAX_CHOICE_OPTIONS = 255
MAX_SCORE_LEVELS = 10


class _JsonModel(BaseModel):
    @model_validator(mode="after")
    def _finite_json(self):
        json.dumps(self.model_dump(exclude_unset=True), allow_nan=False)
        return self


class _Question(_JsonModel):
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
    criteria: dict[str, DecisionText | None] = Field(min_length=1, max_length=MAX_CHOICE_OPTIONS)


class SystemOneScoreQuestion(_Question):
    type: Literal["score"]
    criteria: list[DecisionText] = Field(min_length=1, max_length=MAX_SCORE_LEVELS)


SystemOneQuestion = Annotated[
    SystemOneNoulQuestion | SystemOneChoiceQuestion | SystemOneScoreQuestion,
    Field(discriminator="type"),
]


class SystemOneInputs(_JsonModel):
    model_config = ConfigDict(extra="forbid")
    assets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    state: DecisionText
    questions: dict[str, SystemOneQuestion] = Field(min_length=1)


class SystemOneTextRequest(SystemOneInputs):
    model: str


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
    criteria = {
        "true": "The proposition is true.",
        "false": "The proposition is false.",
        **(criteria or {}),
    }
    return list(criteria.items())


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


def image_source_name(asset, source: str | bytes) -> str:
    """Return the source string expected by custom image loaders."""
    if isinstance(source, str):
        return source
    fmt = "jpeg" if asset["format"] == "jpg" else asset["format"]
    return f"data:image/{fmt};base64,{asset['data_base64']}"


def image_sources(assets) -> dict[str, str]:
    """Validate asset descriptors and return their original loader source strings."""
    return {
        key: image_source_name(assets[key], source) for key, source in _validated_sources(assets)
    }


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


# Strings are literal text. Integers are one-based indices into asset_order.
FieldParts = tuple[str | int, ...]


@dataclass(frozen=True)
class _AssetRef:
    asset_id: str


_ReferenceParts = tuple[str | _AssetRef, ...]


def _reference_pattern(asset_ids) -> re.Pattern[str] | None:
    if not asset_ids:
        return None
    return re.compile(
        "(?<!\\w)(?:"
        + "|".join(re.escape(key) for key in sorted(asset_ids, key=len, reverse=True))
        + ")(?!\\w)"
    )


def _string_parts(text: str, pattern: re.Pattern[str]):
    cursor = 0
    for match in pattern.finditer(text):
        if cursor < match.start():
            yield text[cursor : match.start()]
        yield _AssetRef(match.group())
        cursor = match.end()
    if cursor < len(text):
        yield text[cursor:]


def _json_key(key) -> str:
    if isinstance(key, str):
        return _compact_json(key)
    # Let json.dumps handle coercion and validation of non-string Python keys.
    return _compact_json({key: None}).removeprefix("{").removesuffix(":null}")


def _json_parts(value, pattern: re.Pattern[str]):
    if isinstance(value, str):
        yield '"'
        for part in _string_parts(value, pattern):
            # The template's Image N text needs no JSON escaping.
            yield _compact_json(part)[1:-1] if isinstance(part, str) else part
        yield '"'
    elif isinstance(value, Mapping):
        yield "{"
        for index, (key, item) in enumerate(value.items()):
            if index:
                yield ","
            yield _json_key(key)
            yield ":"
            yield from _json_parts(item, pattern)
        yield "}"
    elif isinstance(value, list):
        yield "["
        for index, item in enumerate(value):
            if index:
                yield ","
            yield from _json_parts(item, pattern)
        yield "]"
    else:
        yield _compact_json(value)


def _reference_parts(value, pattern: re.Pattern[str] | None) -> _ReferenceParts:
    if value is None:
        return ()
    if pattern is None:
        text = render_text(value)
        return (text,) if text else ()
    if isinstance(value, str):
        return tuple(_string_parts(value, pattern))

    parts: list[str | _AssetRef] = []
    literal: list[str] = []
    for part in _json_parts(value, pattern):
        if isinstance(part, str):
            literal.append(part)
        else:
            if literal:
                parts.append("".join(literal))
                literal.clear()
            parts.append(part)
    if literal:
        parts.append("".join(literal))
    return tuple(parts)


@dataclass(frozen=True)
class PiccoloInputs:
    jev_request: JevRequest
    question_key: str
    asset_order: tuple[str, ...]

    @property
    def state_is_asset_only(self) -> bool:
        state = self.jev_request["state"]
        return isinstance(state, dict) and all(
            isinstance(value, str) and value in self.asset_order for value in state.values()
        )


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    description: FieldParts | None


@dataclass(frozen=True)
class PreparedDecision:
    prompt: PiccoloInputs
    candidates: tuple[Candidate, ...]
    image_sources: tuple[str | bytes, ...]
    state_parts: FieldParts | None
    instruction_parts: FieldParts


@dataclass(frozen=True)
class PreparedRequest:
    payload: JevRequest
    image_sources: dict[str, str | bytes]
    _asset_pattern: re.Pattern[str] | None = field(repr=False)
    _state_parts: _ReferenceParts = field(repr=False)


def prepare_request(payload: JevRequest) -> PreparedRequest:
    """Validate and prepare data shared by every question in the request."""
    SystemOneInputs.model_validate(payload)
    sources = dict(_validated_sources(payload.get("assets", {})))
    pattern = _reference_pattern(sources)
    return PreparedRequest(payload, sources, pattern, _reference_parts(payload["state"], pattern))


def prepare_decision(request: PreparedRequest, question_key: str) -> PreparedDecision:
    """Prepare one question while retaining the original request for Jinja."""
    payload = request.payload
    pattern = request._asset_pattern
    question = payload["questions"][question_key]
    options = question_options(question)
    is_noul = question["type"] == "noul"
    if is_noul:
        options.reverse()
    if len(options) > len(DEFAULT_CHOICE_LABELS):
        raise ValueError("Piccolo candidates exceed the checkpoint candidate inventory")

    state = request._state_parts
    instructions = _reference_parts(question.get("instructions"), pattern)
    criteria = question.get("criteria") or {}
    # Default noul descriptions are literal text even if an asset ID occurs in them.
    descriptions = tuple(
        None
        if description is None
        else _reference_parts(description, None if is_noul and key not in criteria else pattern)
        for key, description in options
    )
    order = dict.fromkeys(
        part.asset_id
        for parts in (state, instructions, *descriptions)
        if parts is not None
        for part in parts
        if isinstance(part, _AssetRef)
    )
    for key in request.image_sources:
        order.setdefault(key)
    asset_order = tuple(order)
    indices = {key: index for index, key in enumerate(asset_order, start=1)}

    def number_refs(parts: _ReferenceParts) -> FieldParts:
        return tuple(indices[part.asset_id] if isinstance(part, _AssetRef) else part for part in parts)

    labels = DEFAULT_CHOICE_LABELS[: len(options)]
    prompt = PiccoloInputs(payload, question_key, asset_order)
    return PreparedDecision(
        prompt=prompt,
        candidates=tuple(
            Candidate(key, label, None if description is None else number_refs(description))
            for (key, _), label, description in zip(options, labels, descriptions, strict=True)
        ),
        image_sources=tuple(request.image_sources[key] for key in asset_order),
        state_parts=None if prompt.state_is_asset_only else number_refs(state),
        instruction_parts=number_refs(instructions),
    )
