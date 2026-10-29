import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.hosted_model import HostedModel, MODEL_ID, TOKEN_ENDPOINT
from blink_arena.schemas import DecisionInput

KEY = 'fixture-only-long-lived-key'
TOKEN = 'fixture-only-temporary-token'


def request():
    return DecisionInput(request_id='round-1', model='pre-fin_service_2',
        observation={'hand': [8, 2], 'dealer': 'Q', 'hidden': None},
        question={'instructions': 'Choose', 'options': [
            {'id': 'hit', 'label': '要牌'}, {'id': 'stand', 'label': '停牌'}]})


def answer():
    return {'output': {'model': 'jev-1026', 'answers': {'decision': {
        'type': 'choice', 'choice': 'hit', 'probabilities': {'hit': .8, 'stand': .2}}}},
        'usage': {'input_tokens': 187, 'output_tokens': 1}}


async def mocked_client(respond):
    client = HostedModel()
    await client.http.aclose()
    client.http = httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False)
    return client


@pytest.mark.parametrize('envelope', ['output', 'root', 'chat'])
def test_hosted_request_and_response_contract(monkeypatch, envelope):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        calls = []
        async def respond(req):
            calls.append(str(req.url))
            if str(req.url) == TOKEN_ENDPOINT:
                assert req.method == 'POST' and req.content == b''
                assert req.headers['authorization'] == 'Bearer ' + KEY
                return httpx.Response(200, json={'token': TOKEN, 'expires_at': 123456})
            assert req.headers['authorization'] == 'Bearer ' + TOKEN
            assert KEY not in req.content.decode()
            body = json.loads(req.content)
            assert body['model'] == 'pre-fin_service_2' and body['parameters'] == {}
            assert body['input']['state'] == json.dumps(request().observation,
                ensure_ascii=False, sort_keys=True, allow_nan=False)
            assert body['input']['questions']['decision']['option_order'] == ['hit', 'stand']
            data = answer()
            if envelope == 'root': data = data['output']
            if envelope == 'chat':
                data = {'output': {'choices': [{'message': {'content': json.dumps(data['output'])}}]}}
            return httpx.Response(200, json=data)
        client = await mocked_client(respond)
        try:
            result = await client.decide(request())
            assert result.action == 'hit' and result.request_id == 'round-1'
            assert result.model == 'pre-fin_service_2'
            assert result.probabilities == {'hit': .8, 'stand': .2}
            assert calls == [TOKEN_ENDPOINT, client.endpoint]
        finally: await client.close()
    asyncio.run(run())


def test_each_parallel_decision_gets_its_own_temporary_token(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        issued, used = [], []
        async def respond(req):
            if str(req.url) == TOKEN_ENDPOINT:
                token = f'{TOKEN}-{len(issued)}'
                issued.append(token)
                await asyncio.sleep(.01)
                return httpx.Response(200, json={'token': token})
            used.append(req.headers['authorization'].removeprefix('Bearer '))
            return httpx.Response(200, json=answer())
        client = await mocked_client(respond)
        try:
            await asyncio.gather(*(client.decide(request()) for _ in range(5)))
            await client.decide(request())
            assert len(issued) == len(set(used)) == 6 and set(issued) == set(used)
            assert not hasattr(client, 'token')
        finally: await client.close()
    asyncio.run(run())


@pytest.mark.parametrize('stage', ['exchange', 'generation'])
@pytest.mark.parametrize('status,response,code', [
    (401, {'message': KEY + TOKEN}, 'authentication_failed'),
    (429, {'message': KEY + TOKEN}, 'rate_limited'),
    (302, {'message': KEY + TOKEN}, 'upstream_unavailable'),
    (200, {'code': 'InvalidApiKey', 'message': KEY + TOKEN}, 'authentication_failed'),
    (200, {'code': {'message': KEY + TOKEN}}, 'upstream_unavailable'),
    (200, [], 'invalid_response'),
])
def test_provider_errors_never_expose_credentials(monkeypatch, stage, status, response, code):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        calls = []
        def respond(req):
            calls.append(str(req.url))
            if str(req.url) == TOKEN_ENDPOINT and stage == 'generation':
                return httpx.Response(200, json={'token': TOKEN})
            return httpx.Response(status, json=response, headers={'Location': 'https://example.org/'})
        client = await mocked_client(respond)
        try:
            with pytest.raises(HTTPException) as exc: await client.decide(request())
            assert exc.value.detail == {'code': code}
            assert len(calls) == (1 if stage == 'exchange' else 2)
        finally: await client.close()
    asyncio.run(run())


@pytest.mark.parametrize('token', [None, '', 'bad\r\nheader', 42, {'key': KEY}])
def test_invalid_exchange_tokens_stop_before_generation(monkeypatch, token):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        def respond(req):
            assert str(req.url) == TOKEN_ENDPOINT
            return httpx.Response(200, json={'token': token})
        client = await mocked_client(respond)
        try:
            with pytest.raises(HTTPException) as exc: await client.decide(request())
            assert exc.value.detail == {'code': 'invalid_response'}
        finally: await client.close()
    asyncio.run(run())


@pytest.mark.parametrize('decision', [
    {'choice': 'illegal'},
    {'choice': 'hit', 'probabilities': {'hit': 1}},
    {'choice': 'hit', 'probabilities': {'hit': float('nan'), 'stand': 0}},
    {'choice': 'hit', 'probabilities': {'hit': .9, 'stand': .9}},
])
def test_invalid_decisions_are_rejected(monkeypatch, decision):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        def respond(req):
            data = {'token': TOKEN} if str(req.url) == TOKEN_ENDPOINT else {
                'output': {'answers': {'decision': decision}}}
            return httpx.Response(200, content=json.dumps(data))
        client = await mocked_client(respond)
        try:
            with pytest.raises(HTTPException) as exc: await client.decide(request())
            assert exc.value.detail == {'code': 'invalid_response'}
        finally: await client.close()
    asyncio.run(run())


def test_expired_token_failure_does_not_poison_next_call(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    async def run():
        count = 0
        def respond(req):
            nonlocal count
            if str(req.url) == TOKEN_ENDPOINT:
                count += 1
                return httpx.Response(200, json={'token': f'{TOKEN}-{count}'})
            if count == 1:
                return httpx.Response(401, json={'message': 'Expired ' + TOKEN})
            assert req.headers['authorization'] == f'Bearer {TOKEN}-2'
            return httpx.Response(200, json=answer())
        client = await mocked_client(respond)
        try:
            with pytest.raises(HTTPException) as exc: await client.decide(request())
            assert exc.value.detail == {'code': 'authentication_failed'}
            assert (await client.decide(request())).action == 'hit'
            assert count == 2
        finally: await client.close()
    asyncio.run(run())


def test_timeout_bounds_exchange_and_generation_together(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    monkeypatch.setenv('JEV_HOSTED_TIMEOUT', '1')
    async def run():
        async def respond(req):
            await asyncio.sleep(.6)
            return httpx.Response(200, json={'token': TOKEN} if str(req.url) == TOKEN_ENDPOINT else answer())
        client = await mocked_client(respond)
        try:
            with pytest.raises(HTTPException) as exc: await client.decide(request())
            assert exc.value.status_code == 504 and exc.value.detail == {'code': 'timeout'}
        finally: await client.close()
    asyncio.run(run())


def test_hosted_model_is_public_but_not_browser_manageable(tmp_path, monkeypatch):
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)
    monkeypatch.setenv('JEV_TOKEN', 'obsolete-token-must-not-be-used')
    app = create_app(data=tmp_path, seed=tmp_path/'missing')
    with TestClient(app) as client:
        models = client.get('/api/v1/models').json()['models']
        assert models[0]['id'] == MODEL_ID and not models[0]['ready'] and models[0]['managed']
        assert models[0]['name'] == 'Piccolo'
        # Branding changes the public name while the registered connection stays compatible.
        assert MODEL_ID == 'oneshot-hosted'
        assert client.get('/api/health').json()['default_model'] == MODEL_ID
        assert client.delete('/api/v1/connections/'+MODEL_ID).status_code == 403
        assert client.get('/api/v1/connections/'+MODEL_ID+'/requests').status_code == 403
        assert client.post('/api/v1/connections/'+MODEL_ID+'/results',
            json={'request_id': 'fake', 'error': 'timeout'}).status_code == 403
        response = client.post('/api/v1/decisions', json={'model_id': MODEL_ID, 'input': request().model_dump()})
        assert response.status_code == 503 and response.json()['detail']['code'] == 'hosted_model_not_configured'


def test_hosted_calls_work_across_owners_without_secret_in_responses(tmp_path, monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', KEY)
    app = create_app(data=tmp_path, seed=tmp_path/'missing')
    app.state.hosted_model.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda req:
        httpx.Response(200, json={'token': TOKEN} if str(req.url) == TOKEN_ENDPOINT else answer())))
    with TestClient(app) as client:
        for _ in range(2):
            client.cookies.clear()
            r = client.post('/api/v1/decisions', json={'model_id': MODEL_ID, 'input': request().model_dump()})
            assert r.status_code == 200 and r.json()['action'] == 'hit'
            assert KEY not in r.text and TOKEN not in r.text
        for path in ['/api/health', '/api/v1/models', '/api/v1/connections', '/api/openapi.json']:
            text = client.get(path).text
            assert KEY not in text and TOKEN not in text
