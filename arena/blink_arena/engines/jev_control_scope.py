"""One explicit, archived scope for the user's current game/body release."""
import json
import os
from pathlib import Path

from blink_arena.paths import REPO
# Set before importing the frozen RL bundle; defaults to the live repository.
POLICY = Path(os.environ['JEV_GAME_SCOPE_PATH']) if os.environ.get('JEV_GAME_SCOPE_PATH') else REPO / "config/game-scope.json"


def policy():
    value = json.loads(POLICY.read_text())
    if value.get('schema') != 'cues.control.active-scope.v1':
        raise ValueError('unknown active game/body scope')
    return value


def active_games(kinds):
    excluded = set(policy()['excluded_games'])
    return tuple(k for k in kinds if k not in excluded)


def require_active_game(kind):
    """Reject stale client/RL plans before starting a new episode."""
    if kind in policy()['excluded_games']:
        raise ValueError('game_removed_from_active_scope: ' + kind)
    return kind


def record_exclusion(record, scope=None):
    """Match native task identity; never delete general reasoning by keywords."""
    scope = scope if scope is not None else policy()
    state = record.get('state', {})
    meta = record.get('metadata', {})
    observed = state.get('observation', state) if isinstance(state, dict) else {}
    candidates = {meta.get('sub_domain'), meta.get('scenario')}
    if isinstance(observed, dict):
        candidates.update((observed.get('kind'), observed.get('game')))
    if candidates & set(scope['excluded_games']):
        return 'excluded_native_game'
    if isinstance(state, dict):
        task = state.get('task', {})
        if isinstance(task, dict):
            shape = task.get('shape') or task.get('scene_id')
            goal = task.get('goal')
            if [shape, goal] in scope['excluded_body_tasks']:
                return 'excluded_native_body_task'
    return None
