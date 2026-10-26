"""Browser-owned model connections. The server receives metadata and decision results only."""
import asyncio
import time
from fastapi import HTTPException
from .schemas import ModelConfig

class Connections:
    def __init__(self, providers):
        self.providers = providers
        self.entries = {}

    def owned(self, ident, owner):
        entry = self.entries.get(ident)
        return bool(entry and entry['owner'] == owner)

    def require(self, ident, owner):
        if not self.owned(ident, owner): raise HTTPException(403, 'This browser does not own this model connection')
        return self.entries[ident]

    def add(self, body, owner):
        if body.model_id in self.providers.models:
            raise HTTPException(409, 'Model ID already registered; use another ID or disconnect first')
        if len(self.entries) >= 64: raise HTTPException(429, 'Connection limit reached')
        spec = ModelConfig(id=body.model_id, name=body.name, adapter=body.adapter,
                           served_model=body.served_model,
                           timeout_seconds=body.timeout_seconds, json_mode=body.json_mode)
        entry = {'owner': owner, 'transport': body.transport, 'created_at': time.time(),
                 'queue': asyncio.Queue(maxsize=128), 'pending': {}, 'last_poll': time.monotonic()}
        self.entries[spec.id] = entry
        self.providers.models[spec.id] = spec
        self.providers.slots[spec.id] = asyncio.Semaphore(spec.concurrency)
        self.providers.availability[spec.id] = lambda: time.monotonic()-entry['last_poll'] <= 45
        async def dispatch(request):
            if time.monotonic()-entry['last_poll'] > 45:
                raise HTTPException(503, 'Model browser disconnected; reconnect before evaluating')
            if request.request_id in entry['pending']:
                raise HTTPException(409, 'Duplicate pending request ID')
            future = asyncio.get_running_loop().create_future()
            entry['pending'][request.request_id] = future
            try:
                entry['queue'].put_nowait(request.model_dump(mode='json'))
                return await asyncio.wait_for(future, timeout=spec.timeout_seconds)
            except asyncio.QueueFull:
                raise HTTPException(429, 'Browser request queue full') from None
            except asyncio.TimeoutError:
                raise HTTPException(504, 'Browser model request timed out') from None
            finally:
                entry['pending'].pop(request.request_id, None)
        self.providers.browser_relays[spec.id] = dispatch
        return {'id': spec.id, 'name': spec.name, 'provider': spec.adapter, 'transport': body.transport,
                'served_model': spec.served_model, 'ready': True, 'credentials_persisted': False}

    async def poll(self, ident, owner):
        entry = self.require(ident, owner)
        entry['last_poll'] = time.monotonic()
        rows = []
        try: rows.append(await asyncio.wait_for(entry['queue'].get(), timeout=10))
        except asyncio.TimeoutError: pass
        while len(rows) < 32:
            try: rows.append(entry['queue'].get_nowait())
            except asyncio.QueueEmpty: break
        return {'requests': [r for r in rows if r['request_id'] in entry['pending']]}

    def complete(self, ident, owner, body):
        entry = self.require(ident, owner)
        future = entry['pending'].get(body.request_id)
        if future is None or future.done(): return {'accepted': False, 'reason': 'request_expired'}
        if body.error: future.set_exception(HTTPException(502, 'Browser model request failed: '+body.error))
        else: future.set_result(body.result)
        return {'accepted': True}

    def remove(self, ident, owner):
        entry = self.require(ident, owner)
        for future in entry['pending'].values():
            if not future.done(): future.set_exception(HTTPException(503, 'Model connection closed'))
        self.entries.pop(ident)
        self.providers.models.pop(ident, None)
        self.providers.invalidate(ident)
        self.providers.slots.pop(ident, None)
        self.providers.browser_relays.pop(ident, None)
        self.providers.availability.pop(ident, None)

    def visible(self, owner):
        rows = []
        for model in self.providers.public_models():
            if not self.owned(model['id'], owner): continue
            entry = self.entries[model['id']]
            ready = time.monotonic()-entry['last_poll'] <= 45
            rows.append({**model, 'transport': entry['transport'], 'ready': ready, 'configured': ready})
        return rows
