import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import blink_arena
import jev_demo_showcases as showcases


@pytest.mark.parametrize('route', ['/api/engines/mario_platformer/observe', '/api/showcases/world'])
def test_full_large_world_is_accepted_without_dropping_visible_facts(route):
    # A real public observation after eight model actions; the old guard returned 413.
    state = json.loads((Path(__file__).parent / 'fixtures/mario_large_observation.json').read_text())
    assert len(json.dumps(state, ensure_ascii=False)) > 24000
    assert len(json.dumps(state, ensure_ascii=False).encode()) < showcases.WORLD_OBSERVATION_MAX_BYTES
    expected = showcases.get_engine('mario_platformer').model_input(state)
    assert showcases.get_engine('mario_platformer').observe(state)['state']['observation'] == state
    async def predict(record, qid):
        assert record == expected
        return {'value': 'right'}
    app = FastAPI()
    showcases.install(app, '', None, predict, None)
    with TestClient(app) as client:
        response = client.post(route, json={'state': state, 'kind': 'mario_platformer'})
    assert response.status_code == 200, response.text
    if route.endswith('/observe'):
        assert response.json()['record'] == expected
    else:
        assert response.json()['input']['state'] == expected['state']


@pytest.mark.parametrize('route', ['/api/engines/mario_platformer/observe', '/api/showcases/world'])
def test_world_limit_counts_utf8_bytes_and_rejects_before_observation(route):
    state = {'facts': '中' * 90000}
    assert len(json.dumps(state, ensure_ascii=False)) < showcases.WORLD_OBSERVATION_MAX_BYTES
    app = FastAPI()
    showcases.install(app, '', None, None, None)
    with patch.object(showcases, 'get_engine', side_effect=AssertionError('oversized input reached engine')), TestClient(app) as client:
        response = client.post(route, json={'state': state})
    assert response.status_code == 413
