import asyncio
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.engine import get_engine, list_engines
from blink_arena.game_scope import project_arena
from blink_arena.paths import REPO
from blink_arena.schemas import AppConfig
from jev_control_scope import policy, record_exclusion, require_active_game
from jev_demo_game_evaluation import KINDS
from jev_engine_rollout_backend import RolloutBackend, RolloutError

REMOVED = ('othello_8x8', 'gomoku_19x19', 'racing_sprint', 'goofspiel', 'pig_dice', 'go')


@pytest.mark.parametrize('kind', REMOVED)
def test_removed_engine_rl_and_training_record_are_rejected(kind):
    assert kind not in {e.kind for e in list_engines()}
    assert kind not in KINDS
    with pytest.raises(ValueError):
        get_engine(kind)
    with pytest.raises(ValueError, match='game_removed'):
        require_active_game(kind)
    with pytest.raises(RolloutError):
        RolloutBackend._start_job(dict(game=kind, episode_id='test', seed=42,
            policy_version='fixture', request_token='test'))
    assert record_exclusion({'metadata': {'sub_domain': kind}}) == 'excluded_native_game'


def test_retirement_does_not_match_reasoning_text_by_keyword():
    assert record_exclusion({'state': {'text': 'go / 五子棋 / racing_sprint'},
                             'metadata': {'sub_domain': 'reasoning'}}) is None
    assert require_active_game('othello_6x6') == 'othello_6x6'
    assert len(KINDS) == 22
    assert 'jump_jump' not in KINDS  # Already hidden by the frontend, still an engine.
    assert get_engine('jump_jump')


def test_retired_racing_direct_rl_entry_is_closed():
    import jev_racing_rl
    with pytest.raises(ValueError, match='game_removed'):
        asyncio.run(jev_racing_rl.play(None, {}))


def test_http_catalog_and_creation_use_active_scope(tmp_path):
    with TestClient(create_app(data=tmp_path, config=AppConfig())) as client:
        for route in ('/api/catalog', '/api/v1/games', '/api/showcases', '/api/engines'):
            payload = client.get(route)
            assert payload.status_code == 200
            value = payload.json()
            # /api/engines explicitly separates offline archives from live engines.
            live = value.get('engines', value) if isinstance(value, dict) else value
            for kind in REMOVED:
                assert '"' + kind + '"' not in json.dumps(live)
        for kind in REMOVED:
            for route, body in (
                ('/api/game/new', {'kind': kind, 'seed': 42}),
                ('/api/showcases/new', {'kind': kind, 'seed': 42}),
                ('/api/v1/sessions', {'game': kind, 'seed': 42}),
            ):
                assert client.post(route, json=body).status_code in (404, 422)
        assert client.post('/api/showcases/racing/tick', json={'session_id':'fixture'}).status_code == 404


def test_historical_score_projection_has_new_denominator_and_keeps_source():
    source = json.loads((REPO / 'leaderboard/arena.json').read_text())
    before = deepcopy(source)
    result = project_arena(source)
    assert source == before
    assert not set(REMOVED) & result['by_game'].keys()
    assert result['game_scope']['historical_subset']
    assert not result['game_scope']['new_evaluation']
    if source.get('snapshot', {}).get('control_audit'):
        assert result['source_control_audit'] == source['snapshot']['control_audit']
    for row in result['overall']:
        games = [g for table in result['by_game'].values() for g in table if g['id'] == row['id']]
        assert row['required_games'] == len(result['by_game'])
        assert row['played'] == sum(g.get('played', 0) for g in games)
        if row['rating'] is not None:
            assert row['rating'] == pytest.approx(sum(g['rating'] for g in games)/len(games))
    assert project_arena(result) == result


def test_imported_aggregate_counters_are_not_multiplied_across_game_axes():
    item={'id':'model','rating':1000.,'played':16,'wins':8,'losses':8}
    saved={'source':'imported_ratings','overall':[item],
           'by_game':{k:[dict(item)] for k in ('othello_6x6','hex_7x7','go')}}
    result=project_arena(saved)
    assert result['overall'][0]['rating'] == 1000.
    assert result['overall'][0]['played'] is None
    assert result['overall'][0]['match_counts_available'] is False
    assert result['by_game']['hex_7x7'][0]['wins'] is None


def test_frozen_rl_bundle_can_bind_its_own_scope_file(tmp_path):
    from pathlib import Path
    import os
    import subprocess
    import sys
    from jev_control_scope import POLICY
    scope = tmp_path / 'frozen-scope.json'
    scope.write_bytes(POLICY.read_bytes())
    env = dict(os.environ, JEV_GAME_SCOPE_PATH=str(scope), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    script = """from blink_arena.engine import get_engine
import jev_control_scope as scope
from pathlib import Path
import os
assert scope.POLICY == Path(os.environ['JEV_GAME_SCOPE_PATH'])
assert get_engine('othello_6x6').kind == 'othello_6x6'
try: scope.require_active_game('go')
except ValueError: pass
else: raise AssertionError('retired game admitted')
"""
    subprocess.run([sys.executable, '-c', script], env=env, check=True, capture_output=True)
