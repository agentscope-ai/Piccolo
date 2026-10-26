"""Environment contract and thin adapters for the existing Jev engines.

This module owns no physics, provider, web server, training runtime, or data
directory. A state is the native engine state; ``observe`` is the exact public
TrainingRecord. Browser engines require a bound driver of their real bridge.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from importlib import import_module
from typing import Any, Mapping, Protocol, runtime_checkable

INTERFACE_REVISION = 'jev.engine.environment.v1'


@runtime_checkable
class Environment(Protocol):
    def reset(self, seed: int | None, options: Mapping[str, Any] | None = None) -> Any: ...
    def legal_actions(self, state: Mapping[str, Any]) -> dict[str, str]: ...
    def observe(self, state: Mapping[str, Any]) -> dict[str, Any]: ...
    def step(self, state: Mapping[str, Any], action: str, **kwargs: Any) -> Any: ...
    def public(self, state: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]: ...
    def outcome(self, state: Mapping[str, Any], side: Any = None) -> str | None: ...


@runtime_checkable
class RealtimeRuntime(Protocol):
    """Session clock contract used by HTTP and native realtime plugins.

    ``capture`` catches up physics and freezes one decision's public record.
    ``commit`` catches up again before checking expiry/terminal/piece identity;
    it returns applied/arrival_state/reason, never silently substitutes an
    action. Inference does not stop tick(). ``observed`` is required for engines
    whose intent belongs to a specific piece/entity; otherwise it may be ignored.
    """
    CLOCK_CONTRACT: str
    MIN_DECISION_SECONDS: float
    MODEL_TIMEOUT_SECONDS: float

    def start(self, session: dict, now: float | None = None) -> Any: ...
    def tick(self, session: dict, now: float | None = None) -> Any: ...
    def capture(self, session: dict) -> tuple[dict, dict | None]: ...
    def commit(self, session: dict, action: str, controller: str = 'model',
               observed: dict | None = None) -> dict: ...
    def fail(self, session: dict, reason: str) -> dict: ...


def validate_seed(seed: int | None) -> None:
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 4294967295):
        raise ValueError('seed must be uint32 or None for a standard board start')


def _options(options, allowed):
    value = dict(options or {})
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError('unsupported reset options: ' + ', '.join(sorted(unknown)))
    return value


@dataclass(frozen=True)
class LazyEnvironment:
    """Load a standard environment only when used, preserving its exact API.

    Catalog discovery must not import optional rule libraries. The factory is
    stateless: the serialized game state remains the only per-session state.
    """
    module_name: str
    factory: str

    @property
    def environment(self):
        return getattr(import_module(self.module_name), self.factory)()

    def reset(self, seed, options=None): return self.environment.reset(seed, options)
    def legal_actions(self, state): return self.environment.legal_actions(state)
    def observe(self, state): return self.environment.observe(state)
    as_record = observe
    def step(self, state, action, **kwargs): return self.environment.step(state, action, **kwargs)
    raw_step = step
    def public(self, state, **kwargs): return self.environment.public(state, **kwargs)
    def outcome(self, state, side=None): return self.environment.outcome(state, side)
    def reference_action(self, state): return self.environment.reference_action(state)


@dataclass(frozen=True)
class ModuleEnvironment:
    """Adapt existing functional native engines without caching their functions.

    Dynamic lookup preserves monkeypatches and live module ownership. Action
    history is recorded exactly once here, matching the original showcase
    facade; realtime engines already record it themselves.
    """
    kind: str
    module_name: str
    family: str = 'showcase'
    fresh_with_kind: bool = True
    adapt: bool = True
    remember_effects: bool = True
    archived: bool = False
    record_without_reference: bool = False

    @property
    def module(self):
        return import_module(self.module_name)

    def reset(self, seed, options=None):
        validate_seed(seed)
        settings = _options(options, ('opponent',))
        if settings.get('opponent', 'human') not in ('human', 'rule'):
            raise ValueError('unknown opponent')
        if seed is None:
            raise ValueError('this engine requires an explicit seed')
        if self.family == 'agent':
            return self.module.fresh(self.kind, seed, settings.get('opponent', 'human'))
        return self.module.fresh(self.kind, seed) if self.fresh_with_kind else self.module.fresh(seed)

    def legal_actions(self, state):
        return self.module.choices(state)

    def observe(self, state):
        kwargs = {'include_reference': False} if self.record_without_reference else {}
        record = self.module.as_record(state, **kwargs)
        if self.adapt:
            from jev_gameplay_contract import adapt_record
            record = adapt_record(record, calibrate=False) if self.archived else adapt_record(record)
        return record

    as_record = observe

    def raw_step(self, state, action, **kwargs):
        card_ids = kwargs.pop('card_ids', None)
        controller = kwargs.pop('controller', 'model')
        if kwargs:
            raise TypeError('unsupported action arguments: ' + ', '.join(sorted(kwargs)))
        if card_ids is not None and self.kind != 'doudizhu':
            raise ValueError('仅斗地主支持具体牌选择')
        if self.family == 'realtime':
            return self.module.step(state, action, controller=controller)
        if self.family == 'social':
            return self.module.step(state, action, card_ids=card_ids)
        return self.module.step(state, action)

    def step(self, state, action, **kwargs):
        if not self.remember_effects:
            return self.raw_step(state, action, **kwargs)
        from jev_game_control import remember_effect
        before = (self.observe(state) if len(self.legal_actions(state)) >= 2 else
                  {'state': {key: state.get(key) for key in ('kind', 'event', 'steps', 'outcome')}})
        after = self.raw_step(state, action, **kwargs)
        terminal = after.get('outcome') or (after.get('handoff') if self.family == 'agent' else False)
        after_record = ({'state': {key: after.get(key) for key in ('kind', 'event', 'steps', 'outcome')}}
                        if terminal or len(self.legal_actions(after)) < 2 else self.observe(after))
        return remember_effect(state, after, action, before, after_record)

    def public(self, state, **kwargs):
        function = getattr(self.module, 'public', None)
        if function is not None:
            return function(state, **kwargs) if self.family == 'realtime' else function(state)
        # Legacy renderer fields remain intact. Private RNG state never crosses
        # the boundary. Model input is always observe(), never this UI snapshot.
        return {key: copy.deepcopy(value) for key, value in state.items() if not key.startswith('_')}

    def outcome(self, state, side=None):
        result = self.public(state).get('outcome') if self.family == 'agent' else state.get('outcome')
        opposite = side in (1, '1', 2, '2') if self.kind == 'doudizhu' else side in (1, '1')
        if opposite and result in ('win', 'loss'):
            return 'loss' if result == 'win' else 'win'
        return result


@dataclass(frozen=True)
class BoardEnvironment:
    kind: str
    module_name: str = 'jev_demo_games'

    @property
    def module(self):
        return import_module(self.module_name)

    def reset(self, seed, options=None):
        validate_seed(seed)
        settings = _options(options, ('opening_plies',))
        return self.module.fresh(self.kind, seed, **settings)

    def legal_actions(self, state):
        return {action: action for action in self.module.legal(state)}

    def observe(self, state):
        # Gomoku deliberately exposes a bounded legal candidate subset. Do not
        # replace its option_order with the larger board.legal() list.
        return self.module.as_record(state)[0]

    as_record = observe

    def step(self, state, action, **kwargs):
        if kwargs:
            raise TypeError('board actions do not accept extra arguments')
        return self.module.move(state, action)

    raw_step = step

    def public(self, state, **kwargs):
        return self.module.visible(state)

    def outcome(self, state, side=None):
        winner = state.get('winner')
        if winner in (None, 'draw'):
            return winner
        return 'win' if winner == (side or 'X') else 'loss'


@dataclass(frozen=True)
class RobotGraspEnvironment(ModuleEnvironment):
    """Expose the retained task-space engine without a reference answer.

    The old showcase serializer assumes every game has a public catalog row;
    this internal embodied task intentionally has none. Physics/actions still
    delegate to the unchanged task-space engine.
    """
    def observe(self, state):
        from jev_gameplay_contract import adapt_record
        robot = import_module('jev_showcase_robot')
        options = self.legal_actions(state)
        visible = {key: copy.deepcopy(value) for key, value in state.items()
                   if key not in ('seed', 'outcome', 'score') and not key.startswith('_')}
        visible['rules'] = robot.RULES
        return adapt_record({
            'schema_version': 'jev.training.v1', 'id': 'live-robot-grasp',
            'group_id': 'live-robot-grasp', 'state': visible,
            'questions': {'decision': {'type': 'choice',
                'instructions': '为安全抓取并放置物体，机械臂下一步应执行哪个动作？',
                'criteria': options, 'option_order': list(options)}},
            'labels': {},
            'provenance': {'data_source': 'cues_robot_task_space_simulator_v1',
                           'source_id': 'live', 'source_split': 'demo'},
            'metadata': {'domain': 'embodied', 'sub_domain': self.kind,
                         'scenario': 'task_space_pick_place'},
        })

    as_record = observe


class DriverRequired(RuntimeError):
    """An external engine must execute through its real browser/worker driver."""


@dataclass(frozen=True)
class BrowserEnvironment:
    """Observation adapter with explicit dependency injection of real execution.

    The driver implements reset(seed, options), step(state, action, **kwargs).
    It may return awaitables (e.g. Playwright). No driver means that only pure
    observation/public/outcome operations are available. This prevents an
    accidental switch to an unrelated Python simulator for a browser world.
    """
    kind: str
    record_module: str
    driver: Any = None

    def bind(self, driver):
        return replace(self, driver=driver)

    def reset(self, seed, options=None):
        validate_seed(seed)
        if self.driver is None:
            raise DriverRequired(f'{self.kind} requires its real browser bridge')
        return self.driver.reset(seed, dict(options or {}))

    def legal_actions(self, state):
        if self.outcome(state):
            return {}
        return dict(self.observe(state)['questions']['decision']['criteria'])

    def observe(self, state):
        from jev_gameplay_contract import adapt_record
        record = adapt_record(import_module(self.record_module).as_record(state))
        # Preserve the exact request-time clock descriptor, including any
        # browser realtime metadata unknown to older contract adapters.
        if isinstance(state.get('timing'), dict):
            record['state']['observation']['timing'] = copy.deepcopy(state['timing'])
        return record

    as_record = observe

    def step(self, state, action, **kwargs):
        if self.driver is None:
            raise DriverRequired(f'{self.kind} requires its real browser bridge')
        return self.driver.step(state, action, **kwargs)

    def public(self, state, **kwargs):
        # The bridge supplies only its public snapshot. Never inspect closure
        # state, unseen tiles, future random events or a reference solution.
        return copy.deepcopy(state)

    def outcome(self, state, side=None):
        if state.get('outcome'):
            return state['outcome']
        if self.kind == 'terraria_survival' and state.get('wins', 0):
            return 'win'
        return None


@dataclass(frozen=True)
class WorkerEnvironment(BrowserEnvironment):
    """The same public record, executed by an injected standalone engine core."""
    def reset(self, seed, options=None):
        validate_seed(seed)
        if self.driver is None:
            raise DriverRequired(f'{self.kind} requires a shared-core execution driver')
        return self.driver.reset(seed, dict(options or {}))

    def step(self, state, action, **kwargs):
        if self.driver is None:
            raise DriverRequired(f'{self.kind} requires a shared-core execution driver')
        return self.driver.step(state, action, **kwargs)
