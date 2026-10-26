"""Browser-only connection boundaries: no provider network or credentials."""
import asyncio
import time

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from blink_arena.connections import Connections
from blink_arena.providers import Providers
from blink_arena.schemas import AppConfig, ConnectionCreate, DecisionInput, DecisionOutput, ModelConfig, RelayResult


def setting(**extra):
    return ConnectionCreate(**({'model_id': 'model', 'name': 'Model', 'served_model': 'model',
                               'adapter': 'decision', 'transport': 'browser'} | extra))


def request():
    return DecisionInput(request_id='repeat', model='model', observation={}, question={
        'instructions': 'Pick', 'options': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}]})


@pytest.mark.parametrize('extra', [
    {'api_key': 'fixture-secret'}, {'api_key': None}, {'endpoint': 'http://model.invalid/decide'},
    {'endpoint': None}, {'transport': 'proxy'}, {'transport': 'server'}, {'api_key_env': 'FIXTURE_SECRET'},
])
def test_connection_registration_rejects_every_server_provider_setting(extra):
    with pytest.raises(ValidationError):
        setting(**extra)


@pytest.mark.parametrize('extra', [{'endpoint': 'http://model.invalid'}, {'api_key': 'fixture-secret'}, {'api_key_env': 'FIXTURE_SECRET'}])
def test_internal_model_registry_also_cannot_hold_credentials(extra):
    with pytest.raises(ValidationError):
        ModelConfig(id='model', name='Model', adapter='decision', served_model='model', **extra)


def test_application_configuration_and_runtime_have_no_model_client_or_secret_store():
    with pytest.raises(ValidationError):
        AppConfig(models=[])
    providers = Providers(AppConfig())
    assert not any(hasattr(providers, field) for field in ('client', 'temporary_keys', 'endpoints'))


def test_queued_request_cannot_use_a_replaced_browser_connection():
    async def run():
        providers = Providers(AppConfig(concurrency=1))
        connections = Connections(providers)
        connections.add(setting(), 'owner')
        sent = []
        async def dispatch(body):
            sent.append(body)
            raise AssertionError('A replaced connection must not dispatch')
        providers.browser_relays['model'] = dispatch
        await providers.global_slots.acquire()
        job = asyncio.create_task(providers.decide('model', request()))
        await asyncio.sleep(0)
        connections.remove('model', 'owner')
        connections.add(setting(), 'owner')
        providers.browser_relays['model'] = dispatch
        providers.global_slots.release()
        with pytest.raises(HTTPException) as exc:
            await job
        assert exc.value.status_code == 503 and not sent
        await providers.close()
    asyncio.run(run())


def test_disconnect_cancels_inflight_browser_dispatch():
    async def run():
        providers = Providers(AppConfig())
        connections = Connections(providers)
        connections.add(setting(), 'owner')
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def dispatch(body):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        providers.browser_relays['model'] = dispatch
        job = asyncio.create_task(providers.decide('model', request()))
        await entered.wait()
        connections.remove('model', 'owner')
        with pytest.raises(HTTPException) as exc:
            await job
        assert exc.value.status_code == 503
        assert cancelled.is_set() and not providers.models and not providers.inflight
        await providers.close()
    asyncio.run(run())


def test_browser_failure_accepts_only_a_bounded_error_code():
    with pytest.raises(ValidationError):
        RelayResult(request_id='repeat', error='provider returned fixture-secret')
    async def run():
        providers = Providers(AppConfig())
        connections = Connections(providers)
        connections.add(setting(), 'owner')
        job = asyncio.create_task(providers.decide('model', request()))
        await connections.poll('model', 'owner')
        connections.complete('model', 'owner', RelayResult(request_id='repeat', error='connection_failed'))
        with pytest.raises(HTTPException) as exc:
            await job
        assert exc.value.status_code == 502
        assert exc.value.detail == 'Browser model request failed: connection_failed'
        await providers.close()
    asyncio.run(run())


def test_duplicate_browser_request_id_does_not_replace_pending_request():
    async def run():
        providers = Providers(AppConfig())
        connections = Connections(providers)
        connections.add(setting(), 'owner')
        first = asyncio.create_task(providers.decide('model', request()))
        await connections.poll('model', 'owner')
        with pytest.raises(HTTPException) as exc:
            await providers.decide('model', request())
        assert exc.value.status_code == 409
        assert len(connections.entries['model']['pending']) == 1
        connections.complete('model', 'owner', RelayResult(request_id='repeat', result={
            'request_id': 'repeat', 'model': 'model', 'action': 'a'}))
        assert (await first).action == 'a'
        await providers.close()
    asyncio.run(run())


def test_expired_browser_is_rejected_before_dispatch():
    async def run():
        providers = Providers(AppConfig())
        connections = Connections(providers)
        connections.add(setting(), 'owner')
        connections.entries['model']['last_poll'] = time.monotonic() - 46
        sent = []
        async def dispatch(body):
            sent.append(body)
        providers.browser_relays['model'] = dispatch
        assert not providers.configured('model')
        assert not connections.visible('owner')[0]['ready']
        with pytest.raises(HTTPException) as exc:
            await providers.decide('model', request())
        assert exc.value.status_code == 503 and not sent
        await providers.close()
    asyncio.run(run())


@pytest.mark.parametrize('extra', [
    {'request_id': 'wrong'}, {'model': 'fixture-private-value'}, {'action': 'illegal'},
    {'probabilities': {'a': 1}}, {'probabilities': {'a': 0.5, 'b': 0.500001}},
])
def test_browser_response_identity_action_and_distribution_fail_closed(extra):
    response = DecisionOutput(**({'request_id': 'repeat', 'model': 'model', 'action': 'a'} | extra))
    with pytest.raises(HTTPException) as exc:
        Providers.validate_result(request(), response)
    assert exc.value.status_code == 502
    assert 'fixture-private-value' not in exc.value.detail
