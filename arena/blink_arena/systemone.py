"""JEV System One client and a loopback bridge for browser decision clients."""
import asyncio
import copy
import math
import time

import httpx


class SystemOneClient:
    def __init__(self, endpoint, model='jev-policy', *, concurrency=4, timeout=90):
        self.endpoint, self.model = endpoint, model
        self.http = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self.capacity = asyncio.Semaphore(concurrency)

    async def close(self):
        await self.http.aclose()

    async def predict(self, record, qid, model=None):
        if model is not None and model != self.model:
            raise ValueError('requested_model_mismatch')
        question = copy.deepcopy(record['questions'][qid])
        if question['type'] != 'choice':
            raise ValueError('game_decision_requires_choice')
        criteria = question['criteria']
        order = question.get('option_order', list(criteria))
        if len(order) != len(criteria) or set(order) != set(criteria):
            raise ValueError('invalid_candidate_order')
        payload = {'model': self.model, 'state': record['state'], 'questions': {qid: {
            'type': 'choice', 'instructions': question['instructions'],
            'criteria': {key: criteria[key] for key in order}}}}
        started = time.perf_counter()
        async with self.capacity:
            response = await self.http.post(self.endpoint, json=payload)
        if response.status_code != 200:
            raise ValueError('systemone_http_' + str(response.status_code))
        data = response.json()
        if data.get('model') != self.model:
            raise ValueError('served_model_mismatch')
        answer = data['answers'][qid]
        probabilities, action = answer.get('probabilities'), answer.get('choice')
        if (answer.get('type') != 'choice' or action not in criteria
                or not isinstance(probabilities, dict) or set(probabilities) != set(criteria)
                or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                       for p in probabilities.values())
                or not math.isclose(math.fsum(probabilities.values()), 1., abs_tol=1e-7, rel_tol=0)):
            raise ValueError('invalid_systemone_choice')
        if probabilities[action] < max(probabilities.values()) - 1e-12:
            raise ValueError('systemone_choice_not_argmax')
        return {'model': self.model, 'served_model': data['model'], 'value': action,
                'label': str(criteria[action] or action), 'type': 'choice',
                'distribution': [{'value': key, 'label': str(criteria[key] or key),
                                  'probability': probabilities[key]} for key in order],
                'input_tokens': data.get('usage', {}).get('input_tokens'),
                'usage': data.get('usage', {}),
                'latency_seconds': time.perf_counter() - started,
                'systemone_response': data}


def create_bridge(endpoint, model='jev-policy'):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from .schemas import DecisionInput

    client = SystemOneClient(endpoint, model)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
        allow_origins=['http://127.0.0.1:8080'],
        allow_methods=['POST', 'GET'], allow_headers=['Content-Type', 'X-Request-ID'],
        allow_private_network=True)

    async def decide(body: dict):
        try:
            parsed = DecisionInput.model_validate(body)
            if parsed.model != model:
                raise ValueError('requested_model_mismatch')
            q = parsed.question
            options = {option.id: option.label for option in q.options}
            if len(options) != len(q.options):
                raise ValueError('duplicate_option_ids')
            if len(options) == 1:
                action = next(iter(options))
                return {'schema_version': 'jev.decision.v1', 'request_id': parsed.request_id,
                        'model': model, 'action': action, 'probabilities': {action: 1.}, 'usage': {}}
            result = await client.predict({'state': parsed.observation, 'questions': {q.id: {
                'type': 'choice', 'instructions': q.instructions, 'criteria': options}}}, q.id)
            return {'schema_version': 'jev.decision.v1', 'request_id': parsed.request_id,
                    'model': model, 'action': result['value'],
                    'probabilities': {row['value']: row['probability'] for row in result['distribution']},
                    'usage': {k: v for k, v in result['usage'].items() if type(v) is int}}
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, 'Invalid model request or response') from None
        except httpx.HTTPError:
            raise HTTPException(502, 'System One service unavailable') from None

    app.post('/decide')(decide)

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'model': model, 'adapter': 'jev.decision.v1-to-systemone'}

    return app


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:30100/v1/systemone')
    parser.add_argument('--model', default='jev-policy')
    parser.add_argument('--port', type=int, default=30101)
    args = parser.parse_args()
    uvicorn.run(create_bridge(args.endpoint, args.model), host='127.0.0.1', port=args.port,
                access_log=False)


if __name__ == '__main__':
    main()
