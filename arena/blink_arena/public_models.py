"""Private, headless evaluation clients; never used by the public browser relay."""
import asyncio
import copy
import json
import math
import os
from pathlib import Path
import random
import time

import httpx


class AccessError(ValueError):
    def __init__(self, code, status=None):
        super().__init__(code)
        self.code, self.status = code, status


def load_credentials(path, names):
    """Read only the explicitly configured credential variables, in memory."""
    result = {name: os.environ[name] for name in names if os.environ.get(name)}
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines():
            key, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and key in names and key not in result:
                result[key] = value.strip().strip('"').strip("'")
    return result


def clean(value, secrets=()):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return value
    if isinstance(value, list):
        return [clean(v, secrets) for v in value]
    if isinstance(value, dict):
        return {k: clean(v, secrets) for k, v in value.items()
                if k.lower() not in ('authorization', 'api_key', 'token', 'credential')}
    return value


def participant(row):
    c = row['config']
    expected = c.get('expected_returned_models') or [row['access_id']]
    if len(expected) != 1:
        raise ValueError('one_exact_served_model_required')
    return {'id': row['id'], 'name': row['name'], 'provider': 'decision',
            'served_model': expected[0]}


def decode(row, record, qid, body):
    expected = participant(row)
    if body.get('model') != expected['served_model']:
        raise AccessError('returned_model_version_changed')
    if set(body.get('answers', {})) != {qid}:
        raise AccessError('answer_support_mismatch')
    q = record['questions'][qid]
    answer = body['answers'][qid]
    probs, original_action = answer.get('probabilities'), answer.get('choice')
    policy = row['config'].get('probability_policy', 'native-roundoff')
    if (answer.get('type') != 'choice'
            or not isinstance(probs, dict) or set(probs) != set(q['criteria'])
            or any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1
                   for p in probs.values())):
        raise AccessError('invalid_candidate_distribution')
    total = math.fsum(probs.values())
    tolerance = .02 if policy == 'public-compatible' else 1e-5
    # Public's documented rounding band preserves relative provider mass.
    # Full support, finite values and the raw response remain mandatory.
    if total <= 0 or abs(total - 1) > tolerance + 1e-12:
        raise AccessError('invalid_probability_sum')
    action = (min(probs, key=lambda k: (-probs[k], k))
              if policy == 'public-compatible' else original_action)
    if action not in q['criteria']:
        raise AccessError('invalid_candidate_choice')
    if probs[action] < max(probs.values()) - 1e-7:
        raise AccessError('choice_not_argmax')
    order = q.get('option_order') or list(q['criteria'])
    usage = body.get('usage') or {}
    if not usage:
        metadata = (body.get('native_response') or {}).get('metadata') or {}
        counts = [m['input_tokens'] for m in metadata.values()
                  if isinstance(m, dict) and type(m.get('input_tokens')) is int]
        if counts:
            usage = {'input_tokens': sum(counts)}
    return {**expected, 'model': row['id'], 'value': action, 'type': 'choice',
            'label': str(q['criteria'][action]), 'usage': usage,
            'probability_coverage': {'complete': True},
            'probability_method': 'native_provider_distribution',
            'probability_roundoff': {'original_sum': total, 'normalized': total != 1,
                                     'policy': policy, 'tolerance': tolerance,
                                     'original_choice': original_action, 'selected_choice': action,
                                     'choice_corrected': original_action != action},
            'distribution': [{'value': k, 'label': str(q['criteria'][k]),
                              'probability': probs[k] / total} for k in order]}


class PublicClients:
    def __init__(self, roster, *, concurrency=20, per_model_concurrency=5,
                 timeout=900, max_attempts=4, on_request=None):
        self.roster = roster
        self.rows = roster['models']
        self.secrets = load_credentials(roster.get('credential_file'), {
            r['config']['key_env'] for r in self.rows.values()
            if r.get('config', {}).get('key_env')})
        self.capacity = asyncio.Semaphore(concurrency)
        self.model_capacity = {i: asyncio.Semaphore(per_model_concurrency) for i in self.rows}
        self.endpoints = {i: list(r.get('config', {}).get('endpoints') or [r.get('config', {}).get('endpoint')])
                          for i, r in self.rows.items()}
        self.endpoint_capacity = {}
        for ident, row in self.rows.items():
            native = row.get('config', {}).get('adapter') in ('clef', 'strands', 'native_expansion')
            for endpoint in self.endpoints[ident]:
                self.endpoint_capacity[(ident, endpoint)] = asyncio.Semaphore(1 if native else per_model_concurrency)
        self.endpoint_active = {}
        self.max_attempts, self.timeout = max_attempts, timeout
        self.http = httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False)
        self.on_request = on_request or (lambda row: None)
        self.active = self.peak = 0
        self.blocked, self.failures = {}, {}
        self.blocked_until = {}
        self.model_active = {i: 0 for i in self.rows}
        self.model_peak = {i: 0 for i in self.rows}

    async def close(self):
        await self.http.aclose()

    async def health(self, ident):
        row = self.rows[ident]
        if ident in self.blocked:
            if time.monotonic() < self.blocked_until.get(ident, float('inf')):
                return {'ready': False, 'reason': self.blocked[ident]}
            self.blocked.pop(ident)
            self.blocked_until.pop(ident, None)
            self.failures[ident] = 0
        if row.get('role') == 'awaiting_rl_checkpoint':
            return {'ready': False, 'reason': 'awaiting_rl_checkpoint'}
        if not row.get('enabled', True):
            return {'ready': False, 'reason': 'disabled_in_this_cohort'}
        c = row['config']
        if c.get('key_env'):
            return {'ready': bool(self.secrets.get(c['key_env'])),
                    'reason': 'probe_required' if self.secrets.get(c['key_env']) else 'missing_credential'}
        endpoints = c.get('endpoints') or [c.get('endpoint')]
        if not endpoints[0]:
            return {'ready': False, 'reason': 'local_service_not_started'}
        checks = [await self._native_health(row, endpoint) for endpoint in endpoints]
        available = [endpoint for endpoint, check in zip(endpoints, checks) if check['ready']]
        if available:
            self.endpoints[ident] = available
        return {'ready': bool(available), 'reason': 'health_verified' if available else checks[0]['reason'],
                'model': participant(row)['served_model'], 'available_replicas': len(available),
                'replicas': checks}

    async def _native_health(self, row, endpoint):
        c = row['config']
        try:
            r = await self.http.get(endpoint.removesuffix('/v1/systemone') + '/health', timeout=3)
            r.raise_for_status()
            body = r.json()
            if body.get('model') != participant(row)['served_model']:
                raise AccessError('health_model_mismatch')
            if c.get('checkpoint'):
                actual_path = body.get('model_path')
                if c['adapter'] == 'startlux_http':
                    # Official health reports the backend separately. Verify
                    # its read-only model listing, not only the display name.
                    models = await self.http.get(c['engine_endpoint'].rstrip('/') + '/v1/models', timeout=3)
                    models.raise_for_status()
                    served = models.json().get('data', [])
                    actual_path = served[0].get('root') if len(served) == 1 else None
                    if actual_path is None and len(served) == 1:
                        actual_path = served[0].get('id')
                if actual_path != c['checkpoint']:
                    raise AccessError('health_checkpoint_mismatch')
            return {'ready': True, 'reason': 'health_verified', 'model': body['model']}
        except Exception as exc:
            return {'ready': False, 'reason': getattr(exc, 'code', type(exc).__name__)}

    async def predict(self, record, qid, model=None):
        if model in self.blocked:
            raise AccessError('model_access_circuit_open')
        row = self.rows[model]
        c = row['config']
        q = record['questions'][qid]
        order = q.get('option_order') or list(q['criteria'])
        if len(order) != len(q['criteria']) or set(order) != set(q['criteria']):
            raise AccessError('invalid_option_order')
        wire = {'type': q['type'], 'instructions': q['instructions'],
                'criteria': {k: q['criteria'][k] for k in order}}
        # A state is a JSON value: stabilize object key serialization without
        # changing any value, array order or the separately controlled choices.
        state = json.loads(json.dumps(record['state'], ensure_ascii=False,
                                      sort_keys=True, allow_nan=False))
        payload = {'model': c.get('model_id') or row['access_id'],
                   'state': state, 'questions': {qid: wire}}
        if c['adapter'] == 'startlux_http':
            settings = c['profiles']['evaluated']
            payload.update({k: settings[k] for k in
                            ('think_mode', 'gate', 'think_budget', 'mix', 'allow_none', 'none_check')})
        headers = {}
        if c.get('key_env'):
            key = self.secrets.get(c['key_env'])
            if not key:
                raise AccessError('missing_credential')
            headers['Authorization'] = 'Bearer ' + key
        began = time.monotonic()
        for attempt in range(self.max_attempts):
            event = {'model': model, 'attempt': attempt, 'started_at': time.time(),
                     'status': 'error', 'record': copy.deepcopy(record),
                     'state_serialization': 'canonical-object-keys-preserve-values-and-array-order'}
            queued = time.monotonic()
            async with self.model_capacity[model], self.capacity:
                if model in self.blocked:
                    raise AccessError('model_access_circuit_open')
                endpoint = min(self.endpoints[model], key=lambda ep: self.endpoint_active.get((model, ep), 0))
                endpoint_key = (model, endpoint)
                self.endpoint_active[endpoint_key] = self.endpoint_active.get(endpoint_key, 0)+1
                try:
                    await self.endpoint_capacity[endpoint_key].acquire()
                except BaseException:
                    self.endpoint_active[endpoint_key] -= 1
                    raise
                started = time.monotonic()
                event.update(queue_seconds=started-queued, endpoint=endpoint)
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.model_active[model] += 1
                self.model_peak[model] = max(self.model_peak[model], self.model_active[model])
                retry = False
                transport_failure = False
                retry_after = 0.
                try:
                    configured_timeout = (c.get('profiles') or {}).get('evaluated', {}).get('timeout_seconds', self.timeout)
                    response = await self.http.post(endpoint, json=payload, headers=headers, timeout=configured_timeout)
                    event['http_status'] = response.status_code
                    # Headers are never retained. Scrub provider error echoes.
                    try:
                        body = response.json()
                        event['response'] = clean(body, self.secrets.values())
                    except ValueError:
                        body = None
                        event['response_text'] = clean(response.text[:2000], self.secrets.values())
                    if response.status_code != 200:
                        retry = response.status_code in (408, 425, 429, 500, 502, 503, 504, 507, 509, 529)
                        try:
                            retry_after = max(0., min(60., float(response.headers.get('retry-after', '0'))))
                        except ValueError:
                            pass
                        raise AccessError('http_' + str(response.status_code), response.status_code)
                    if not isinstance(body, dict):
                        raise AccessError('invalid_json_response')
                    result = decode(row, record, qid, body)
                    self.failures[model] = 0
                    result['latency_seconds'] = time.monotonic() - began
                    event.update(status='ok', usage=result['usage'], probability_audit=result['probability_roundoff'])
                    return result
                except asyncio.CancelledError:
                    event.update(status='cancelled', error='request_cancelled')
                    raise
                except httpx.TransportError as exc:
                    retry = True
                    transport_failure = True
                    error = AccessError(type(exc).__name__)
                    event['error'] = error.code
                except AccessError as exc:
                    error = exc
                    event['error'] = error.code
                except (KeyError, TypeError, ValueError) as exc:
                    error = AccessError('invalid_response_schema:' + type(exc).__name__)
                    event['error'] = error.code
                finally:
                    self.active -= 1
                    self.model_active[model] -= 1
                    self.endpoint_active[endpoint_key] -= 1
                    self.endpoint_capacity[endpoint_key].release()
                    event['seconds'] = time.monotonic() - started
                    event['elapsed_seconds'] = time.monotonic()-queued
                    self.on_request(clean(event, self.secrets.values()))
            if not retry or attempt == self.max_attempts-1:
                # Stop dispatch on lost access or repeated infrastructure
                # failures; do not turn an outage into thousands of losses.
                infrastructure = transport_failure or error.status in (401, 402, 403, 408, 429, 500, 502, 503, 504, 529)
                if infrastructure:
                    self.failures[model] = self.failures.get(model, 0)+1
                    if error.status in (401, 402, 403) or self.failures[model] >= 3:
                        self.blocked[model] = error.code
                        self.blocked_until[model] = (float('inf') if error.status in (401, 402, 403)
                                                     else time.monotonic()+max(60, retry_after))
                raise error
            await asyncio.sleep(max(retry_after, min(8., 2**attempt)) + random.uniform(0., .2))
