import unittest
import httpx
from fastapi.testclient import TestClient
from blink_arena.systemone import SystemOneClient, create_bridge


class SystemOneTests(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_action_ids_and_explicit_option_order(self):
        client = SystemOneClient('http://model/v1/systemone')
        await client.http.aclose()

        def handler(request):
            import json
            body = json.loads(request.content)
            self.assertEqual(list(body['questions']['decision']['criteria']), ['move-9', 'move-2'])
            self.assertNotIn('labels', body)
            return httpx.Response(200, json={'model': 'jev-policy', 'answers': {'decision': {
                'type': 'choice', 'choice': 'move-2',
                'probabilities': {'move-9': .2, 'move-2': .8}}}})

        client.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.close)
        result = await client.predict({'state': {'visible': True}, 'questions': {'decision': {
            'type': 'choice', 'instructions': 'Choose',
            'criteria': {'move-2': 'two', 'move-9': 'nine'},
            'option_order': ['move-9', 'move-2']}}, 'labels': {'decision': 'move-9'}}, 'decision')
        self.assertEqual(result['value'], 'move-2')
        self.assertEqual([r['value'] for r in result['distribution']], ['move-9', 'move-2'])

    async def test_rejects_wrong_model_and_incomplete_probabilities(self):
        record = {'state': {}, 'questions': {'q': {'type': 'choice', 'instructions': 'Choose',
                  'criteria': {'a': 'A', 'b': 'B'}}}}
        for data in [
            {'model': 'other', 'answers': {}},
            {'model': 'jev-policy', 'answers': {'q': {'type': 'choice', 'choice': 'a',
                                                    'probabilities': {'a': 1}}}},
            {'model': 'jev-policy', 'answers': {'q': {'type': 'choice', 'choice': 'a',
                                                    'probabilities': {'a': .1, 'b': .9}}}},
        ]:
            client = SystemOneClient('http://model/v1/systemone')
            await client.http.aclose()
            client.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))
            try:
                with self.assertRaises(ValueError):
                    await client.predict(record, 'q')
            finally:
                await client.close()


class BridgeTests(unittest.TestCase):
    def test_private_network_preflight_and_single_legal_action(self):
        with TestClient(create_bridge('http://unreachable.invalid/v1/systemone')) as client:
            origin = 'http://127.0.0.1:8080'
            response = client.options('/decide', headers={'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type,x-request-id',
                'Access-Control-Request-Private-Network': 'true'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['access-control-allow-origin'], origin)
            self.assertEqual(response.headers['access-control-allow-private-network'], 'true')
            response = client.post('/decide', json={'request_id': 'r1', 'model': 'jev-policy',
                'observation': {}, 'question': {'instructions': 'Only legal move',
                'options': [{'id': 'pass', 'label': 'Pass'}]}})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['action'], 'pass')
            self.assertEqual(response.json()['request_id'], 'r1')
            response = client.options('/decide', headers={'Origin': 'https://unrelated.example',
                'Access-Control-Request-Method': 'POST'})
            self.assertEqual(response.status_code, 400)
