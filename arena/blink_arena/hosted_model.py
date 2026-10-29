"""Server-owned Piccolo connection. Credentials never enter public metadata."""
import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .schemas import DecisionOutput, ModelConfig

MODEL_ID = 'oneshot-hosted'
DEFAULT_ENDPOINT = 'https://poc-dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'
TOKEN_ENDPOINT = 'https://dashscope.aliyuncs.com/api/v1/tokens?expire_in_seconds=60'


def valid_credential(value):
    return isinstance(value, str) and bool(value) and all(32 < ord(c) < 127 for c in value)


class HostedModel:
    def __init__(self):
        self.api_key = os.environ.get('DASHSCOPE_API_KEY', '').strip()
        self.endpoint = os.environ.get('JEV_HOSTED_ENDPOINT', DEFAULT_ENDPOINT)
        url = urlsplit(self.endpoint)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ValueError('JEV_HOSTED_ENDPOINT must be an HTTPS URL without credentials or query')
        if self.api_key and not valid_credential(self.api_key):
            raise ValueError('Invalid DASHSCOPE_API_KEY format')
        self.spec = ModelConfig(id=MODEL_ID, name='Piccolo', adapter='decision',
            served_model=os.environ.get('JEV_HOSTED_MODEL', 'pre-fin_service_2'),
            concurrency=int(os.environ.get('JEV_HOSTED_CONCURRENCY', '5')),
            timeout_seconds=float(os.environ.get('JEV_HOSTED_TIMEOUT', '60')))
        self.http = httpx.AsyncClient(timeout=self.spec.timeout_seconds, follow_redirects=False)

    @property
    def ready(self):
        return bool(self.api_key)

    async def close(self):
        await self.http.aclose()

    async def _post(self, endpoint, credential, payload=None):
        response = await self.http.post(endpoint,
            **({'content': b''} if payload is None else {'json': payload}),
            headers={'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'})
        if not response.is_success:
            # Never expose provider bodies, URLs, request headers or credentials.
            code = {401: 'authentication_failed', 403: 'authentication_failed',
                    429: 'rate_limited', 504: 'timeout'}.get(response.status_code, 'upstream_unavailable')
            raise HTTPException(429 if response.status_code == 429 else 502, {'code': code})
        try:
            if len(response.content) > 4 * 1024 * 1024:
                raise ValueError('oversized response')
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('expected object')
        except (ValueError, TypeError):
            raise HTTPException(502, {'code': 'invalid_response'}) from None
        if data.get('code') or data.get('success') is False:
            code = {'InvalidApiKey': 'authentication_failed',
                    'AccessDenied': 'authentication_failed',
                    'Throttling': 'rate_limited'}.get(str(data.get('code')), 'upstream_unavailable')
            raise HTTPException(429 if code == 'rate_limited' else 502, {'code': code})
        return data

    async def _exchange_and_generate(self, payload):
        # Acquire only after Providers grants a concurrency slot. Never cache or
        # persist the 60-second token, including between calls from the same seat.
        data = await self._post(TOKEN_ENDPOINT, self.api_key)
        token = data.get('token')
        if not valid_credential(token):
            raise HTTPException(502, {'code': 'invalid_response'})
        return await self._post(self.endpoint, token, payload)

    async def decide(self, body):
        if not self.ready:
            raise HTTPException(503, {'code': 'hosted_model_not_configured'})
        q = body.question
        payload = {'model': self.spec.served_model, 'input': {
            # Match the training formatter and retain nulls across the gateway.
            'state': json.dumps(body.observation, ensure_ascii=False, sort_keys=True, allow_nan=False),
            'questions': {'decision': {'type': 'choice', 'instructions': q.instructions,
                'criteria': {o.id: o.label for o in q.options},
                'option_order': [o.id for o in q.options]}}}, 'parameters': {}}
        try:
            data = await asyncio.wait_for(self._exchange_and_generate(payload), self.spec.timeout_seconds)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            raise HTTPException(504, {'code': 'timeout'}) from None
        except httpx.HTTPError:
            raise HTTPException(502, {'code': 'upstream_unavailable'}) from None
        try:
            output = data.get('output', data)
            if isinstance(output, str):
                output = json.loads(output)
            if 'choices' in output:
                output = json.loads(output['choices'][0]['message']['content'])
            # The gateway alias is pre-fin_service_2, while output.model is
            # jev-1026. Public result identity remains the registered alias.
            answers = output.get('answers', output)
            answer = answers['decision']
            if answer.get('type', 'choice') != 'choice':
                raise ValueError('unsupported answer')
            action = answer.get('choice', answer.get('value'))
            usage = data.get('usage') or output.get('usage') or {}
            result = DecisionOutput(request_id=body.request_id, model=body.model,
                action=action, probabilities=answer.get('probabilities'),
                usage={k: v for k, v in usage.items() if k in {'input_tokens', 'output_tokens',
                    'prompt_tokens', 'completion_tokens', 'total_tokens'} and type(v) is int and v >= 0})
            from .providers import Providers
            return Providers.validate_result(body, result)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, HTTPException):
            raise HTTPException(502, {'code': 'invalid_response'}) from None
