"""Request validation, asset binding, candidate mappings and prompt construction."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
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


def render_text(value):
    """Serialize structured content only at the prompt boundary."""
    if value is None:
        return ""
    return (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    )


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


def image_sources(assets):
    """Validate storage descriptors and expose image sources in registry order."""
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
    images = {}
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
            images[key] = value
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
            images[key] = str(path)
            continue
        fmt, data = (asset.get("format"), asset.get("data_base64"))
        if fmt not in {"png", "jpg", "jpeg"} or not isinstance(data, str) or (not data):
            raise ValueError("Piccolo image assets require png/jpg/jpeg format and data_base64")
        try:
            base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Piccolo data_base64 must be standard base64 without a data: prefix"
            ) from error
        images[key] = f"data:image/{('jpeg' if fmt == 'jpg' else fmt)};base64,{data}"
    return images


def _asset_binder(payload):
    """Bind references in JSON values before serialization, leaving keys intact."""
    assets = payload.get("assets", {})
    if not assets:
        return (lambda value: value), {}

    pattern = re.compile(
        "(?<!\\w)(?:"
        + "|".join(re.escape(key) for key in sorted(assets, key=len, reverse=True))
        + ")(?!\\w)"
    )

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, Mapping):
            for key, item in value.items():
                yield str(key)
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    contents = [*strings(payload["state"]), *strings(payload["questions"]), *assets]
    prefix = "__JEV_IMAGE_"
    while any(prefix in text for text in contents):
        prefix += "X"
    markers = {key: f"{prefix}{index}__" for index, key in enumerate(assets)}

    def bind(value):
        if isinstance(value, str):
            if value in markers:
                return markers[value]
            return pattern.sub(lambda match: markers[match.group()], value)
        if isinstance(value, Mapping):
            return {key: bind(item) for key, item in value.items()}
        if isinstance(value, list):
            return [bind(item) for item in value]
        return value

    return bind, markers


def _asset_markers(value, markers):
    """Yield bound image occurrences in value order, leaving object keys as text."""
    if not markers:
        return
    pattern = re.compile("|".join(re.escape(marker) for marker in markers))

    def visit(item):
        if isinstance(item, str):
            yield from (match.group() for match in pattern.finditer(item))
        elif isinstance(item, Mapping):
            for child in item.values():
                yield from visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield from visit(child)

    yield from visit(value)


class JevRequest(TypedDict):
    state: DecisionText
    questions: dict[str, dict[str, Any]]
    assets: NotRequired[dict[str, dict[str, Any]]]


# Strings are literal text. Integers are one-based indices into asset_order.
FieldParts = tuple[str | int, ...]


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
    image_sources: tuple[str, ...]
    field_parts: Callable[[DecisionText | None], FieldParts]


def prepare_decision(payload: JevRequest, question_key: str) -> PreparedDecision:
    """Prepare one question while retaining the original request for Jinja."""
    SystemOneInputs.model_validate(payload)
    sources = image_sources(payload.get("assets", {}))
    bind, markers = _asset_binder(payload)
    question = payload["questions"][question_key]
    # Bind only supplied criteria. The default noul descriptions are literal text.
    bound_question = {**question, "criteria": bind(question.get("criteria"))}
    options = question_options(bound_question)
    if question["type"] == "noul":
        options.reverse()
    if len(options) > len(DEFAULT_CHOICE_LABELS):
        raise ValueError("Piccolo candidates exceed the checkpoint candidate inventory")

    values = [
        bind(payload["state"]),
        bind(question.get("instructions")),
        [description for _, description in options],
    ]
    marker_assets = {marker: key for key, marker in markers.items()}
    order = dict.fromkeys(_asset_markers(values, marker_assets))
    for marker in marker_assets:
        order.setdefault(marker)
    asset_order = tuple(marker_assets[marker] for marker in order)
    indices = {marker: index for index, marker in enumerate(order, start=1)}
    pattern = re.compile("|".join(map(re.escape, indices))) if indices else None

    def split_field(value) -> FieldParts:
        text = render_text(value)
        parts: list[str | int] = []
        cursor = 0
        if pattern is not None:
            for match in pattern.finditer(text):
                if cursor < match.start():
                    parts.append(text[cursor : match.start()])
                parts.append(indices[match.group()])
                cursor = match.end()
        if cursor < len(text):
            parts.append(text[cursor:])
        return tuple(parts)

    def field_parts(value: DecisionText | None) -> FieldParts:
        return split_field(bind(value))

    labels = DEFAULT_CHOICE_LABELS[: len(options)]
    return PreparedDecision(
        prompt=PiccoloInputs(payload, question_key, asset_order),
        candidates=tuple(
            Candidate(key, label, None if description is None else split_field(description))
            for (key, description), label in zip(options, labels, strict=True)
        ),
        image_sources=tuple(sources[key] for key in asset_order),
        field_parts=field_parts,
    )
