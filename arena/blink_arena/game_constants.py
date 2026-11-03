"""Compatibility views derived from the shared engine registry."""
from collections.abc import MutableMapping
from dataclasses import replace
from jev_engine_registry import get_engine, list_engines

# HTTP Playground budgets are separate from fixed engine/RL reference defaults.
PLAYGROUND_LIMITS = {'chess':512, 'xiangqi':500, 'sudoku':960, 'terraria_survival':1200}
PLAYGROUND_SNAKE_FOOD_TARGET = 3

def playground_engine(engine):
    limit = PLAYGROUND_LIMITS.get(engine.kind)
    if engine.kind == 'snake_navigation':
        import jev_snake_realtime as snake
        return replace(engine, goal=snake.goal({'food_target':PLAYGROUND_SNAKE_FOOD_TARGET}))
    return replace(engine, limit=limit) if limit is not None else engine

class EngineLimits(MutableMapping):
    def __init__(self):
        self.overrides = {}

    def __getitem__(self, kind):
        try:
            return self.overrides[kind] if kind in self.overrides else get_engine(kind).limit
        except ValueError as exc:
            raise KeyError(kind) from exc

    def __setitem__(self, kind, value):
        get_engine(kind)
        self.overrides[kind] = value

    def __delitem__(self, kind):
        del self.overrides[kind]

    def __iter__(self):
        return (engine.kind for engine in list_engines())

    def __len__(self):
        return len(list_engines())

    def clear(self):
        self.overrides.clear()

class BrowserWorlds(MutableMapping):
    """Compatibility name for worlds with a frontend renderer, regardless of host."""
    def __init__(self):
        self.overrides = {}

    def __iter__(self):
        return (engine.kind for engine in list_engines() if engine.browser_page and engine.browser_bridge)

    def __len__(self):
        return sum(bool(engine.browser_page and engine.browser_bridge) for engine in list_engines())

    def __getitem__(self, kind):
        if kind in self.overrides:
            return self.overrides[kind]
        try:
            engine = get_engine(kind)
        except ValueError as exc:
            raise KeyError(kind) from exc
        if not engine.browser_page or not engine.browser_bridge:
            raise KeyError(kind)
        return engine.browser_page, engine.browser_bridge, engine.observe

    def __setitem__(self, kind, value):
        if not get_engine(kind).browser_bridge or not get_engine(kind).browser_page:
            raise KeyError(kind)
        self.overrides[kind] = value

    def __delitem__(self, kind):
        del self.overrides[kind]

    def clear(self):
        self.overrides.clear()

LIMITS = EngineLimits()
WORLD = BrowserWorlds()
