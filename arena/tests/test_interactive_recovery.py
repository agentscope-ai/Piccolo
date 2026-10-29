"""Inference errors must not manufacture losses in the interactive games."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from blink_arena.app import create_app
from blink_arena.schemas import AppConfig
from jev_demo_decision_stability import _failure
from jev_demo_showcases import interactive_model_error


@pytest.mark.parametrize('game,route', [
    ('snake_navigation', 'snake'), ('tetris_placement', 'tetris'),
    ('merge_2048', None),
])
def test_model_failure_preserves_unstarted_game_and_allows_retry(tmp_path, game, route):
    app = create_app(data=tmp_path, config=AppConfig())
    async def failed(*args, **kwargs):
        raise HTTPException(503, {'code': 'upstream_unavailable'})
    app.state.providers.predict = failed
    with TestClient(app) as client:
        client.post('/api/v1/connections', json={'model_id': 'test', 'name': 'Test',
            'served_model': 'test', 'adapter': 'decision'})
        initial = client.post('/api/showcases/new', json={'kind': game, 'seed': 42}).json()
        ident = initial['session_id']
        response = client.post('/api/showcases/step', headers={'X-Demo-Model': 'test'},
            json={'session_id': ident, 'revision': initial['revision'], 'model': True})
        assert response.status_code == 503, response.text
        detail = response.json()['detail']
        assert detail.get('cause', detail['code']) == 'upstream_unavailable'
        # Tick/read the same session: transport failure has not set a loss.
        if route:
            state = client.post('/api/showcases/'+route+'/tick', json={'session_id': ident}).json()
            assert not state['world']['outcome']
            assert not state['busy']
        # Restore actual callback behavior and issue a legal manual action.
        action = next(iter(initial['choices']))
        retry = client.post('/api/showcases/step', json={'session_id': ident,
            'revision': initial['revision'], 'action': action, 'model': False})
        assert retry.status_code == 200, retry.text
        if route:
            assert retry.json()['applied']
        else:
            assert retry.json()['world']['steps'] > initial['world']['steps']


def test_repeat_error_preserves_bounded_cause_without_provider_text():
    error = _failure(HTTPException(429, {'code': 'rate_limited', 'private': 'fixture-secret'}), 1)
    assert error.status_code == 429
    assert error.detail['cause'] == 'rate_limited'
    assert error.detail['sample_index'] == 1
    assert 'fixture-secret' not in str(error.detail)
    sanitized = interactive_model_error(HTTPException(503, {'code': 'upstream_unavailable',
                                                           'private': 'fixture-secret'}))
    assert sanitized.detail == {'code': 'upstream_unavailable'}
