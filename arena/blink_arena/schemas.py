"""Versioned public contracts; unknown fields and non-finite numbers fail closed."""
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator, model_serializer

Identifier = Annotated[str, Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$')]
Probability = Annotated[float, Field(ge=0, le=1)]

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class ModelConfig(Contract):
    """Browser registration metadata; no network destination or credentials."""
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    adapter: Literal['decision', 'openai']
    served_model: str = Field(min_length=1, max_length=200)
    timeout_seconds: float = Field(default=120, ge=1, le=600)
    concurrency: int = Field(default=1, ge=1, le=32)
    json_mode: bool = True

class AppConfig(Contract):
    schema_version: Literal['jev.config.v1'] = 'jev.config.v1'
    concurrency: int = Field(default=32, ge=1, le=64)

class Option(Contract):
    id: str = Field(min_length=1, max_length=256)
    label: str = Field(max_length=16000)

class Question(Contract):
    id: str = 'decision'
    instructions: str = Field(max_length=40000)
    options: list[Option] = Field(min_length=1, max_length=1024)

    @model_validator(mode='after')
    def unique_options(self):
        if len({o.id for o in self.options}) != len(self.options): raise ValueError('duplicate option ID')
        return self

class DecisionInput(Contract):
    schema_version: Literal['jev.decision.v1'] = 'jev.decision.v1'
    request_id: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=200)
    game: str | None = None
    observation: dict[str, Any]
    question: Question

class DecisionOutput(Contract):
    schema_version: Literal['jev.decision.v1'] = 'jev.decision.v1'
    request_id: str
    model: str
    action: str
    probabilities: dict[str, Probability] | None = None
    usage: dict[str, int] = Field(default_factory=dict)

class DecisionCall(Contract):
    model_id: Identifier
    input: DecisionInput

class ConnectionCreate(Contract):
    model_id: Identifier
    name: str = Field(min_length=1, max_length=200)
    served_model: str = Field(min_length=1, max_length=200)
    adapter: Literal['decision', 'openai']
    transport: Literal['browser'] = 'browser'
    json_mode: bool = True
    timeout_seconds: float = Field(default=120, ge=1, le=600)
    concurrency: int = Field(default=1, ge=1, le=32)

    @field_validator('name')
    @classmethod
    def public_display_name(cls, value):
        from .privacy import public_text
        return public_text(value)

class RelayResult(Contract):
    request_id: str
    result: DecisionOutput | None = None
    error: Literal['connection_failed', 'invalid_response', 'timeout', 'cancelled',
                   'authentication_failed', 'rate_limited', 'endpoint_not_found',
                   'upstream_unavailable'] | None = None

    @model_validator(mode='after')
    def one_result(self):
        if (self.result is None) == (self.error is None): raise ValueError('provide result or error')
        return self

class EvaluationCreate(Contract):
    model_ids: list[Identifier] = Field(min_length=2, max_length=16)
    games: list[Identifier] | None = Field(default=None, min_length=1, max_length=128)
    seeds: int = Field(default=1, ge=1, le=3)
    seed_base: int = Field(default=42, ge=0, le=2147483644)
    concurrency: int = Field(default=32, ge=1, le=64)

    @model_validator(mode='after')
    def unique(self):
        if len(set(self.model_ids)) != len(self.model_ids): raise ValueError('duplicate model ID')
        if self.games and len(set(self.games)) != len(self.games): raise ValueError('duplicate game')
        return self

class SessionCreate(Contract):
    game: Identifier
    seed: int = Field(default=42, ge=0, le=4294967295)

class SessionStep(Contract):
    reveal: bool = False
    reference: bool = False
    revision: int = Field(ge=0)
    action: str | None = None
    model_id: Identifier | None = None
    ticks: int = Field(default=0, ge=0, le=120)

    @model_validator(mode='after')
    def action_or_model(self):
        if self.reveal:
            if self.action is not None or self.model_id is not None or self.ticks or self.reference:
                raise ValueError('seat handoff cannot include another action')
            return self
        if sum((self.action is not None, self.model_id is not None, self.reference)) > 1:
            raise ValueError('choose action, model_id or reference')
        if self.action is None and self.model_id is None and not self.reference and not self.ticks:
            raise ValueError('step requires action, model_id, reference or ticks')
        return self

class Axis(Contract):
    id: Identifier
    label_en: str
    label_zh: str
    score: float | None = None
    metric: str | None = None
    samples: int | None = Field(default=None, ge=0)

class LeaderboardRow(Contract):
    model_id: Identifier
    model_name: str
    logo: str | None = Field(default=None, max_length=2048)
    score: float | None = None
    status: Literal['complete', 'running', 'error', 'pending'] = 'complete'
    metrics: dict[str, float | None] = Field(default_factory=dict)
    axes: list[Axis] = Field(default_factory=list)
    samples: int = Field(default=0, ge=0)
    # External leaderboards may publish a score without per-request error counts.
    errors: int | None = Field(default=0, ge=0)
    evaluated_at: str | None = None
    protocol: str = 'imported'
    notes: list[str] = Field(default_factory=list)

    @field_validator('logo')
    @classmethod
    def valid_logo(cls, value):
        from urllib.parse import urlsplit
        from .privacy import public_text
        if not value:
            return None
        if any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value or value.startswith('//'):
            raise ValueError('logo must be an HTTP(S) URL or a local web asset path')
        parsed = urlsplit(value)
        if (parsed.scheme and parsed.scheme not in ('http', 'https')) or parsed.username or parsed.password:
            raise ValueError('unsupported logo URL')
        if parsed.scheme and not parsed.hostname:
            raise ValueError('logo URL must include a host')
        if not parsed.scheme and (not parsed.path or '..' in parsed.path.split('/')):
            raise ValueError('invalid local logo path')
        public_text(value.split('://', 1)[-1])
        return value

    @model_serializer(mode='wrap')
    def optional_logo(self, handler):
        data = handler(self)
        if self.logo is None:
            data.pop('logo', None)
        return data

class LeaderboardDocument(Contract):
    schema_version: Literal['jev.leaderboard.v1'] = 'jev.leaderboard.v1'
    benchmark_id: Literal['jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench', 'arena']
    title: str
    version: str
    metric: str
    score_scale: tuple[float, float] = (0, 1)
    higher_is_better: bool = True
    axis_scale: tuple[float, float] = (0, 1)
    rows: list[LeaderboardRow]

    @model_validator(mode='after')
    def valid_scales_and_rows(self):
        from .privacy import assert_public_document
        public = self.model_dump(mode='json')
        # Logo is a separately validated public image URL; all result metadata
        # retains the existing prohibition on machine paths and service URLs.
        for row in public['rows']:
            row.pop('logo', None)
        assert_public_document(public)
        if self.score_scale[0] >= self.score_scale[1] or self.axis_scale[0] >= self.axis_scale[1]:
            raise ValueError('invalid score scale')
        if len({r.model_id for r in self.rows}) != len(self.rows): raise ValueError('duplicate model ID')
        for row in self.rows:
            if row.score is not None and not self.score_scale[0] <= row.score <= self.score_scale[1]: raise ValueError('score outside scale')
            if len({a.id for a in row.axes}) != len(row.axes): raise ValueError('duplicate axis ID')
            for axis in row.axes:
                if axis.score is not None and not self.axis_scale[0] <= axis.score <= self.axis_scale[1]: raise ValueError('axis score outside scale')
        return self
