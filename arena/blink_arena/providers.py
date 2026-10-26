"""Schedule browser-owned inference using an observation-only contract.

This module has no HTTP model client, network destination or credential store.
"""
import asyncio
import time
import uuid
from fastapi import HTTPException
from .schemas import AppConfig, DecisionInput, DecisionOutput, Question, Option

class Providers:
    def __init__(self, config: AppConfig):
        self.config = config
        self.models = {}
        self.slots = {}
        self.global_slots = asyncio.Semaphore(config.concurrency)
        self.browser_relays = {}
        self.availability = {}
        self.inflight = {}

    async def close(self):
        tasks = [task for group in self.inflight.values() for task in group]
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        self.inflight.clear()

    def configured(self, ident):
        return bool(ident in self.models and ident in self.browser_relays
                    and self.availability.get(ident, lambda: False)())

    def public_models(self):
        return [{'id': m.id, 'name': m.name, 'provider': m.adapter, 'served_model': m.served_model,
                 'ready': self.configured(m.id), 'configured': self.configured(m.id)} for m in self.models.values()]

    async def decide(self, ident, body: DecisionInput):
        spec = self.models.get(ident)
        if not spec: raise HTTPException(404, 'Unknown configured model')
        if body.model != spec.served_model: raise HTTPException(422, 'Model identity differs from registry')
        if not self.configured(ident): raise HTTPException(503, 'Model connection unavailable; reconnect before evaluating')
        # The captured registration object is the generation token. A queued
        # call may never run under a removed/replaced browser connection.
        slot = self.slots.get(ident)
        if slot is None: raise HTTPException(503, 'Model connection closed')
        async with self.global_slots, slot:
            if self.models.get(ident) is not spec: raise HTTPException(503, 'Model connection changed')
            if not self.configured(ident): raise HTTPException(503, 'Model connection unavailable; reconnect before evaluating')
            task = asyncio.create_task(self._request(ident, spec, body))
            self.inflight.setdefault(ident, set()).add(task)
            try:
                return await task
            except asyncio.CancelledError:
                if self.models.get(ident) is not spec: raise HTTPException(503, 'Model connection closed') from None
                raise
            finally:
                self.inflight.get(ident, set()).discard(task)

    def invalidate(self, ident):
        for task in self.inflight.pop(ident, set()): task.cancel()

    async def _request(self, ident, spec, body):
        relay = self.browser_relays.get(ident)
        if relay is None: raise HTTPException(503, 'Browser model connection unavailable')
        result = await relay(body)
        return self.validate_result(body, result)

    @staticmethod
    def validate_result(body, result):
        legal = {o.id for o in body.question.options}
        if result.request_id != body.request_id or result.model != body.model or result.action not in legal:
            raise HTTPException(502, 'Model response identity or action does not match request')
        if result.probabilities is not None:
            if set(result.probabilities) != legal or abs(sum(result.probabilities.values())-1) > 1e-7:
                raise HTTPException(502, 'Probabilities must cover every option and sum to one')
        return result

    async def predict(self, record, qid, model=None):
        began = time.perf_counter()
        spec = self.models.get(model)
        if not spec: raise HTTPException(404, 'Unknown configured model')
        q = record['questions'][qid]
        order = q.get('option_order') or list(q['criteria'])
        if set(order) != set(q['criteria']): raise HTTPException(422, 'Invalid option order')
        kind = record.get('metadata', {}).get('sub_domain') or record.get('state', {}).get('kind')
        request = DecisionInput(request_id=uuid.uuid4().hex, model=spec.served_model, game=kind,
                                observation=record['state'], question=Question(id=qid, instructions=q['instructions'],
                                options=[Option(id=str(k), label=str(q['criteria'][k])) for k in order]))
        result = await self.decide(model, request)
        probs = result.probabilities
        return {'model': model, 'model_label': spec.name, 'provider': spec.adapter,
                'served_model': result.model, 'question_id': qid, 'type': 'choice', 'value': result.action,
                'label': q['criteria'][result.action], 'latency_seconds': time.perf_counter()-began,
                'distribution': [{'value': o.id, 'label': o.label, 'probability': probs[o.id] if probs else None,
                                  'observed': probs is not None, 'logprob': None} for o in request.question.options],
                'probability_coverage': {'complete': probs is not None},
                'probability_method': 'provider_complete_distribution' if probs else 'unavailable',
                'candidate_probability_note': 'Provider distribution' if probs else 'This adapter did not return measured candidate probabilities.',
                'model_input': {'format': 'jev.decision.v1', 'schema_input': request.model_dump(mode='json')},
                'usage': result.usage, 'source': record.get('provenance', {}), 'comparison': None}
