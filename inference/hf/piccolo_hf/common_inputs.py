"""Request validation, asset binding, candidate mappings and prompt construction."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal
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


def bind_assets(payload, *, require_references=True):
    """Validate the whole record, then bind JSON values to private image markers.

    Binding before prompt serialization keeps object keys, labels and template
    literals from becoming image references. Only markers that the selected
    question renders are expanded, so other questions' images are not loaded.
    """
    assets = payload.get("assets", {})
    images = image_sources(assets)
    if not images:
        return (payload["state"], payload["questions"], {})
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
    used = set()

    def reference(key):
        used.add(key)
        return markers[key]

    def bind(value):
        if isinstance(value, str):
            return (
                reference(value)
                if value in assets
                else pattern.sub(lambda m: reference(m.group()), value)
            )
        if isinstance(value, Mapping):
            return {key: bind(item) for key, item in value.items()}
        if isinstance(value, list):
            return [bind(item) for item in value]
        return value

    state = bind(payload["state"])
    questions = {
        key: {
            **question,
            **{
                field: bind(question[field])
                for field in ("instructions", "criteria")
                if field in question
            },
        }
        for key, question in payload["questions"].items()
    }
    if require_references and used != set(assets):
        raise ValueError(f"Unreferenced Piccolo assets: {sorted(set(assets) - used)}")
    return (state, questions, {markers[key]: images[key] for key in assets})


def asset_markers(value, images):
    """Yield bound image occurrences in value order, leaving object keys as text."""
    if not images:
        return
    pattern = re.compile("|".join(re.escape(marker) for marker in images))

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


def prepare_field_parts(value, image_indices=None):
    """Encode one field as text/image-reference parts for a standalone template.

    Values have already been bound by bind_assets. JSON encoding happens once,
    before private markers become explicit references; templates never parse
    markers or receive the image registry. Empty/null fields produce no parts.
    """
    text = render_text(value)
    indices = image_indices or {}
    if not indices:
        return [{"type": "text", "text": text}] if text else []
    pattern = re.compile("|".join(re.escape(marker) for marker in indices))
    parts, cursor = ([], 0)
    for match in pattern.finditer(text):
        if match.start() > cursor:
            parts.append({"type": "text", "text": text[cursor : match.start()]})
        parts.append({"type": "image_ref", "index": indices[match.group()]})
        cursor = match.end()
    if cursor < len(text):
        parts.append({"type": "text", "text": text[cursor:]})
    return parts


@dataclass(frozen=True)
class PiccoloInputs:
    messages: list[dict]
    option_keys: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    asset_ids: tuple[str, ...]


def prepare_piccolo_inputs(payload, question_key):
    """Prepare field parts and media mappings; Jinja lays out the question."""
    SystemOneInputs.model_validate(payload)
    state, questions, images = bind_assets(payload, require_references=False)
    question = questions[question_key]
    options = question_options(question)
    if question["type"] == "noul":
        options = options[::-1]
    if len(options) > len(DEFAULT_CHOICE_LABELS):
        raise ValueError("Piccolo candidates exceed the checkpoint candidate inventory")
    keys, descriptions = zip(*options, strict=True)
    order = list(
        dict.fromkeys(asset_markers([state, question.get("instructions"), descriptions], images))
    )
    order.extend(marker for marker in images if marker not in order)
    labels = DEFAULT_CHOICE_LABELS[: len(keys)]
    indices = {marker: index + 1 for index, marker in enumerate(order)}
    state_is_asset_only = isinstance(state, dict) and all(
        isinstance(value, str) and value in indices for value in state.values()
    )
    variables = {
        "mode": "decision",
        "state": [] if state_is_asset_only else prepare_field_parts(state, indices),
        "state_is_asset_only": state_is_asset_only,
        "instructions": prepare_field_parts(question.get("instructions"), indices),
        "questions": [
            {"instructions": prepare_field_parts(item.get("instructions"))}
            for item in payload["questions"].values()
        ],
        "kind": question["type"],
        "options": [
            {
                "key": key,
                "label": label,
                "has_description": description is not None,
                "content": prepare_field_parts(description, indices),
            }
            for (key, description), label in zip(options, labels, strict=True)
        ],
    }
    markers_to_ids = dict(zip(images, payload.get("assets", {}), strict=True))
    return PiccoloInputs(
        messages=[
            {
                "role": "user",
                "content": [{"type": "image", "image": images[marker]} for marker in order],
                "jev": variables,
            }
        ],
        option_keys=tuple(keys),
        candidate_labels=labels,
        asset_ids=tuple(markers_to_ids[marker] for marker in order),
    )
