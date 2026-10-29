"""Session contract checks; live HTTP tests opt in with JEV_TEST_URL.

The live tests only create disposable manual sessions and one temporary mock
connection. They never invoke a real model or touch evaluation standings.
"""
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import uuid

import httpx
import pytest

from blink_arena.app import create_app
from blink_arena.schemas import AppConfig
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
from jev_control_scope import active_games
GAMES = tuple(g['id'] for g in json.loads((ROOT / 'leaderboard/arena.json').read_text())['fixed_config']['games'] if active_games([g['id']]))


@pytest.fixture
def client():
    url = os.environ.get('JEV_TEST_URL')
    if not url:
        pytest.skip('Set JEV_TEST_URL to run disposable live sessions, including shared Node engines')
    with httpx.Client(base_url=url.rstrip('/'), timeout=60) as client:
        yield client


def response_json(response, expected=200):
    assert response.status_code == expected, f'HTTP {response.status_code}; content type {response.headers.get("content-type")}'
    assert response.headers.get('content-type', '').startswith('application/json')
    return response.json()


def create_session(client, game):
    return response_json(client.post('/api/v1/sessions', json={'game': game, 'seed': 42}), 201)


def step(client, session, **kwargs):
    return response_json(client.post(f'/api/v1/sessions/{session["session_id"]}/steps',
                                    json={'revision': session['revision'], **kwargs}))


def test_current_games_include_eight_selected_games(tmp_path):
    with TestClient(create_app(data=tmp_path, config=AppConfig())) as client:
        result = response_json(client.get('/api/v1/games'))
        assert result['schema_version'] == 'jev.engine-registry.v1'
        from jev_selected_games import GAMES as selected
        assert {game['kind'] for game in result['games']} == set(GAMES) | set(selected) | {'chess'}
        assert len(result['games']) == 23
        for game in result['games']:
            assert game['interface_revision'] == 'jev.engine.environment.v1'
            assert not game['internal']


def test_legacy_manual_showcase_preserves_owner_with_compressed_response(tmp_path):
    app = create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        initial = response_json(client.post('/api/showcases/new', json={'kind': 'jump_jump', 'seed': 42}))
        action = next(iter(initial['choices']))
        move = {'session_id': initial['session_id'], 'revision': initial['revision'], 'action': action}
        changed = response_json(client.post('/api/showcases/step', json=move))
        assert changed['session_id'] == initial['session_id']
        client.cookies.clear()
        assert client.post('/api/showcases/step', json=move).status_code == 404


@pytest.mark.parametrize('operation', ['tick', 'cancel'])
def test_registry_realtime_control_requires_session_owner(tmp_path, operation):
    app = create_app(data=tmp_path, config=AppConfig())
    with TestClient(app) as client:
        initial = response_json(client.post('/api/showcases/new', json={'kind': 'snake_navigation', 'seed': 42}))
        route = f'/api/engines/snake_navigation/{operation}'
        body = {'session_id': initial['session_id']}
        response_json(client.post(route, json=body))
        client.cookies.clear()
        assert client.post(route, json=body).status_code == 404


@pytest.mark.parametrize('game', GAMES)
def test_all_live_games_create_step_replay_delete(client, game):
    initial = create_session(client, game)
    ident = initial['session_id']
    try:
        assert initial['schema_version'] == 'jev.session.v1'
        assert initial['game'] == game and initial['revision'] == 0
        assert initial['legal_actions'] and not initial['terminal']
        action = next(iter(initial['legal_actions']))
        changed = step(client, initial, action=action)
        assert changed['revision'] == 1 and changed['applied']
        observed = response_json(client.get(f'/api/v1/sessions/{ident}'))
        assert observed['revision'] == 1 and observed['game'] == game
        replay = response_json(client.get(f'/api/v1/sessions/{ident}/replay'))
        assert replay['schema_version'] == 'jev.session-replay.v1'
        assert replay['game'] == game and replay['seed'] == 42
        assert len(replay['steps']) == 1
        if replay.get('private_history_redacted'):
            assert replay['steps'][0]['decision'] is None and replay['steps'][0]['before_state'] is None
        if game == 'goofspiel':
            # The first sealed bid must not be readable by the next hot-seat
            # player through the public replay endpoint.
            assert replay['private_history_redacted'] and replay['steps'][0]['action'] is None
        else:
            assert replay['steps'][0]['action'] == action
        assert replay['steps'][0]['applied']
        assert client.post(f'/api/v1/sessions/{ident}/steps', json={'revision': 0, 'action': action}).status_code == 409
        outsider = httpx.get(str(client.base_url).rstrip('/') + f'/api/v1/sessions/{ident}', timeout=30)
        assert outsider.status_code == 404
    finally:
        response_json(client.delete(f'/api/v1/sessions/{ident}'))
    assert client.get(f'/api/v1/sessions/{ident}').status_code == 404


@pytest.mark.parametrize('game,action,position', [
    ('snake_navigation', 'up', 'body'),
    ('tetris_placement', 'left', 'active'),
])
def test_realtime_starts_with_input_and_moves_while_waiting(client, game, action, position):
    initial = create_session(client, game)
    ident = initial['session_id']
    try:
        idle = step(client, initial, ticks=20)
        assert idle['state']['elapsed'] == 0
        assert not idle['state'].get('started', idle['state'].get('race_started'))
        assert action in idle['legal_actions']
        active = step(client, idle, action=action)
        assert active['state'].get('started', active['state'].get('race_started'))
        waited = step(client, active, ticks=90)
        assert waited['state']['elapsed'] > active['state']['elapsed'] + 0.5
        assert waited['state'][position] != active['state'][position]
        assert waited['action'] is None
        if game == 'snake_navigation':
            assert waited['state']['food_target'] == 6
        if game == 'tetris_placement':
            assert waited['state']['simulation_ticks'] > active['state']['simulation_ticks']
    finally:
        response_json(client.delete(f'/api/v1/sessions/{ident}'))


@pytest.mark.parametrize('game', ['mario_platformer', 'terraria_survival'])
def test_worker_world_uses_real_time_bridge(client, game):
    initial = create_session(client, game)
    ident = initial['session_id']
    try:
        assert initial['engine']['backend'] == 'worker'
        after = step(client, initial, ticks=30)
        assert after['state']['frame'] > initial['state']['frame']
        assert after['state']['player'] and after['state']['map']
        assert after['state']['timing']
    finally:
        response_json(client.delete(f'/api/v1/sessions/{ident}'))


@pytest.mark.parametrize('game,repeats', [('othello_6x6', 1), ('tetris_placement', 1)])
def test_model_session_uses_browser_relay_and_registered_repeat_policy(client, game, repeats):
    model_id = 'session-smoke-' + uuid.uuid4().hex[:12]
    response_json(client.post('/api/v1/connections', json={
        'model_id': model_id, 'name': 'Browser test double', 'served_model': 'test-double',
        'adapter': 'decision', 'transport': 'browser', 'timeout_seconds': 10,
    }), 201)
    initial = create_session(client, game)
    calls = []
    try:
        # The session request waits in a worker while this thread acts as the
        # browser, polling public observations and posting validated decisions.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(step, client, initial, model_id=model_id)
            while len(calls) < repeats:
                batch = response_json(client.get(f'/api/v1/connections/{model_id}/requests'))['requests']
                assert batch, 'No model decision reached the browser relay'
                for body in batch:
                    assert body['game'] == game and body['model'] == 'test-double'
                    assert 'endpoint' not in body and 'api_key' not in body
                    calls.append(body)
                    result = response_json(client.post(f'/api/v1/connections/{model_id}/results', json={
                        'request_id': body['request_id'], 'result': {
                            'schema_version': 'jev.decision.v1', 'request_id': body['request_id'],
                            'model': body['model'], 'action': body['question']['options'][0]['id'],
                        }}))
                    assert result['accepted']
            changed = future.result(timeout=15)
        assert changed['applied'] and changed['result'] is not None
        assert len(calls) == repeats
        assert len({body['request_id'] for body in calls}) == repeats
        assert changed['result']['decision_policy']['repeat_count'] == 1
        assert 'decision_stability' not in changed['result']
    finally:
        response_json(client.delete(f'/api/v1/sessions/{initial["session_id"]}'))
        response_json(client.delete(f'/api/v1/connections/{model_id}'))


def test_explicit_module_plugin_runs_through_standard_session(tmp_path, monkeypatch):
    from jev_engine_registry import load_engine_plugins, unregister_engine
    module = 'session_test_plugin_' + uuid.uuid4().hex
    game = 'session_plugin_' + uuid.uuid4().hex[:12]
    (tmp_path / f'{module}.py').write_text('''
from jev_engine_registry import EngineSpec
class Counter:
    def reset(self, seed, options=None): return {'kind': KIND, 'seed': seed, 'count': 0}
    def legal_actions(self, state): return {} if state['count'] else {'finish': 'Finish'}
    def observe(self, state): return {'state': self.public(state), 'questions': {'decision': {'instructions': 'Finish', 'criteria': self.legal_actions(state)}}}
    def step(self, state, action, **kwargs):
        if action not in self.legal_actions(state): raise ValueError('Illegal action')
        return {**state, 'count': state['count'] + 1}
    def public(self, state, **kwargs): return dict(state)
    def outcome(self, state, side=None): return 'win' if state['count'] else None
def register_engines(register):
    register(EngineSpec(kind=KIND, name='Session plugin test', environment=Counter(), limit=1))
'''.replace('KIND', repr(game)))
    monkeypatch.syspath_prepend(str(tmp_path))
    load_engine_plugins([module])
    try:
        with TestClient(create_app(data=tmp_path / 'data', config=AppConfig())) as client:
            discovered = response_json(client.get('/api/v1/games'))
            descriptor = next(item for item in discovered['games'] if item['kind'] == game)
            assert descriptor['renderer'] == 'generic'
            assert descriptor['source_modules'] == [module]
            initial = create_session(client, game)
            final = step(client, initial, action='finish')
            assert final['terminal'] and final['state']['count'] == 1
            replay = response_json(client.get(f'/api/v1/sessions/{initial["session_id"]}/replay'))
            assert replay['steps'][0]['action'] == 'finish'
            response_json(client.delete(f'/api/v1/sessions/{initial["session_id"]}'))
    finally:
        unregister_engine(game)


@pytest.mark.parametrize('game', ['mario_platformer', 'terraria_survival'])
def test_local_world_session_uses_shared_worker_without_playwright(tmp_path, monkeypatch, game):
    from blink_arena.sessions import Sessions
    async def forbidden_browser(self):
        raise AssertionError('Shared world sessions must not launch Playwright')
    monkeypatch.setattr(Sessions, 'browser_instance', forbidden_browser)
    monkeypatch.setenv('JEV_LEADERBOARD_DIR', str(tmp_path / 'leaderboard'))
    app = create_app(data=tmp_path / 'data', config=AppConfig())
    with TestClient(app) as local:
        initial = create_session(local, game)
        ident = initial['session_id']
        process = app.state.sessions.items[ident]['driver'].process
        try:
            assert initial['engine']['backend'] == 'worker'
            assert app.state.sessions.browser is None
            assert app.state.sessions.playwright is None
            waited = step(local, initial, ticks=12)
            assert waited['state']['frame'] > initial['state']['frame']
            assert waited['state']['player'] and waited['state']['map']
            assert not waited['state']['timing']['inference_world_paused']
            action = 'wait' if 'wait' in waited['legal_actions'] else 'recover'
            assert action in waited['legal_actions']
            changed = step(local, waited, action=action)
            assert changed['applied'] and changed['state']['frame'] > waited['state']['frame']
            replay = response_json(local.get(f'/api/v1/sessions/{ident}/replay'))
            assert replay['game'] == game and replay['seed'] == 42
            assert len(replay['steps']) == 2
            assert replay['steps'][-1]['action'] == action
        finally:
            response_json(local.delete(f'/api/v1/sessions/{ident}'))
        assert process.returncode is not None
        assert ident not in app.state.sessions.items
