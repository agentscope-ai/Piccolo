"""Public Python engine API, usable without FastAPI or a model service.

RL clients use engine.model_input(state) for the current decision view, or
engine.observe(state) for the full public/replay contract; never engine.public(state). Native realtime and browser engines expose their original runner
and verifier through EngineSpec rather than a substitute turn-based simulator.
"""
def __getattr__(name):
    # Registry startup loads plugins. They may import this public facade while
    # its first registry import is in progress, after the registry API exists.
    if name in {'EngineSpec','get_engine','get_archived_engine','list_engines','register_engine'}:
        import jev_engine_registry
        return getattr(jev_engine_registry,name)
    raise AttributeError(name)

from jev_engine_registry import EngineSpec, get_engine, get_archived_engine, list_engines, register_engine
from jev_engine_environment import Environment, RealtimeRuntime, INTERFACE_REVISION

__all__ = ['EngineSpec','Environment','RealtimeRuntime','INTERFACE_REVISION',
           'get_engine','get_archived_engine','list_engines','register_engine']
