#!/usr/bin/env python3
"""Exercise the model connection UI against a running local JevArena backend.

    python tests/browser_connections.py --base-url http://127.0.0.1:8092/
    python tests/browser_connections.py --base-url http://127.0.0.1:8093/jev/

Requires Playwright and Chromium. Starts a temporary, local mock model service;
no real model endpoint or credential is used. Both API formats are called
directly by Chromium; the game backend never receives the endpoint or key. All test connections are
removed on exit. Screenshots go to the repository's ignored var/browser folder.
The reload check waits for the browser connection's 45-second heartbeat lease.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit, urlunsplit
import uuid

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_KEY = 'jev-browser-test-fixture-not-a-real-key'
SERVED_MODEL = 'jev-browser-test-mock'


def normalize_url(value: str) -> str:
    url = urlsplit(value)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise argparse.ArgumentTypeError('base URL must be an HTTP(S) address without credentials, query or fragment')
    return urlunsplit((url.scheme, url.netloc, url.path.rstrip('/') + '/', '', ''))


@contextmanager
def mock_model(base_url: str):
    origin = urlunsplit((*urlsplit(base_url)[:2], '', '', ''))
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def cors(self):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Headers', 'content-type,authorization,x-request-id')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')

        def do_OPTIONS(self):
            self.send_response(204)
            self.cors()
            self.end_headers()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            # Keep only a boolean credential check, never headers or the key.
            seen.append({'path': self.path, 'authorized': self.headers.get('Authorization') == 'Bearer ' + FIXTURE_KEY, 'browser_origin': self.headers.get('Origin') == origin, 'cookies_absent': not self.headers.get('Cookie')})
            if self.path == '/v1/chat/completions':
                question = json.loads(body['messages'][1]['content'])['question']
                result = {'model': body['model'], 'choices': [{'message': {'content': json.dumps({
                    'action': question['options'][0]['id'], 'probabilities': {'self-reported': 1}})}}],
                    'usage': {'total_tokens': 8}}
            elif self.path == '/decide':
                result = {'schema_version': 'jev.decision.v1', 'request_id': body['request_id'],
                          'model': body['model'], 'action': body['question']['options'][0]['id'],
                          'probabilities': None, 'usage': {}}
            else:
                self.send_response(404)
                self.cors()
                self.end_headers()
                return
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.cors()
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def decision(model_id: str) -> dict:
    return {'model_id': model_id, 'input': {
        'schema_version': 'jev.decision.v1', 'request_id': uuid.uuid4().hex,
        'model': SERVED_MODEL, 'game': 'test', 'observation': {'turn': 1},
        'question': {'id': 'pick', 'instructions': 'Choose', 'options': [
            {'id': 'first', 'label': 'First'}, {'id': 'second', 'label': 'Second'}]}}}


async def call(page, payload):
    return await page.evaluate('''async (body) => {
        const response = await fetch('./api/v1/decisions', {method:'POST',
            headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
        return {status:response.status, data:await response.json()};
    }''', payload)


async def check(args, mock_url, seen):
    output = ROOT / 'var' / 'browser' / ('connections-' + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = await context.new_page()
        errors, registrations, relay_results, identities = [], [], [], []
        same_origin_violations, same_origin_requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def record_request(request):
            if urlsplit(request.url)[:2] == urlsplit(args.base_url)[:2]:
                contents = json.dumps({'url': request.url, 'headers': request.headers, 'body': request.post_data})
                same_origin_requests.append(request.method)
                if FIXTURE_KEY in contents:
                    same_origin_violations.append('credential')
                if mock_url in contents:
                    same_origin_violations.append('model_endpoint')
            if request.method != 'POST' or '/api/v1/connections' not in request.url:
                return
            if urlsplit(request.url).path.endswith('/connections'):
                registrations.append(request.post_data_json)
            elif urlsplit(request.url).path.endswith('/results'):
                relay_results.append(request.post_data_json)

        page.on('request', record_request)
        try:
            response = await page.goto(args.base_url, wait_until='domcontentloaded')
            assert response and response.status == 200, 'Frontend page did not load'
            await page.wait_for_function("document.getElementById('status').textContent.includes('Manual')")
            # Old releases may have remembered a path instead of an opaque model ID.
            await page.evaluate("localStorage.setItem('jev_demo_model', '/cpfs/test-fixture/private-checkpoint')")
            await page.reload(wait_until='domcontentloaded')
            await page.wait_for_function("typeof window.ConnectUI !== 'undefined'")
            assert await page.evaluate("localStorage.getItem('jev_demo_model')") is None, 'Legacy model path remained in local storage'
            await page.locator('#connectionSettings').click()
            await page.locator('#connectionApiKey').fill(FIXTURE_KEY)
            await page.locator('#showConnectionKey').click()
            assert await page.locator('#connectionApiKey').get_attribute('type') == 'text'
            await page.locator('#connectCancel').click()
            await page.locator('#connectionSettings').click()
            assert await page.locator('#connectionApiKey').input_value() == ''
            assert await page.locator('#connectionApiKey').get_attribute('type') == 'password'
            await page.locator('#connectionApiKey').fill(FIXTURE_KEY)
            await page.keyboard.press('Escape')
            assert await page.locator('#connectionApiKey').input_value() == '', 'Escape did not clear the key'
            for endpoint in ['https://user:fixture@example.test/api', 'https://example.test/api?api_key=fixture', 'https://example.test/api#fixture', 'http://example.test:0/decide', 'http://example.test:99999/decide', args.base_url + 'api/v1/decisions']:
                rejected = await page.evaluate('''(value) => {
                    try { JevConnectionTransport.endpoint(value); return false; } catch { return true; }
                }''', endpoint)
                assert rejected, 'Endpoint accepted embedded credentials, query or fragment'
            assert await page.locator('#connectionTransport').count() == 0, 'Transport dropdown still exists'
            for adapter in ('openai', 'decision'):
                ident = f'ui-test-direct-{adapter}-{uuid.uuid4().hex[:12]}'
                identities.append(ident)
                await page.locator('#connectionSettings').click()
                await page.locator('#connectionModelId').fill(ident)
                await page.locator('#connectionName').fill(f'{adapter} browser test')
                await page.locator('#connectionServedModel').fill(SERVED_MODEL)
                await page.locator('#connectionAdapter').select_option(adapter)
                await page.locator('#connectionEndpoint').fill(mock_url + ('/v1/chat/completions' if adapter == 'openai' else '/decide'))
                await page.locator('#connectionApiKey').fill(FIXTURE_KEY)
                await page.locator('#connectSave').click()
                await page.wait_for_function("document.getElementById('connectionMessage').textContent.startsWith('Connected.')")
                assert await page.locator('#connectionApiKey').input_value() == '', 'Key input was not cleared'
                await page.locator('#connectCancel').click()
                assert await page.locator('#modelSelect').input_value() == ident
                result = await call(page, decision(ident))
                assert result['status'] == 200, f'{adapter} direct decision failed with HTTP {result["status"]}'
                assert result['data']['action'] == 'first' and result['data']['probabilities'] is None
                assert SERVED_MODEL in await page.locator('#modelPath').text_content()

            assert len(seen) == 2 and all(row['authorized'] and row['browser_origin'] and row['cookies_absent'] for row in seen), 'Mock model did not receive both direct browser requests'
            assert len(registrations) == 2
            allowed = {'model_id', 'name', 'served_model', 'adapter', 'transport', 'json_mode', 'timeout_seconds'}
            assert all(set(row) <= allowed and row.get('transport') == 'browser' for row in registrations), 'Browser registration contained non-metadata fields'
            assert not same_origin_violations, 'Model credentials or endpoint reached the game server'
            assert FIXTURE_KEY not in json.dumps(relay_results), 'Relay results contained the key'
            storage = await page.evaluate('JSON.stringify({local:{...localStorage},session:{...sessionStorage}})')
            assert FIXTURE_KEY not in storage and mock_url not in storage, 'Connection settings were persisted in web storage'
            public = await context.request.get(args.base_url + 'api/v1/connections')
            assert FIXTURE_KEY not in await public.text() and mock_url not in await public.text(), 'Public model list exposed private connection settings'

            # A separate browser owner must not see or invoke these connections.
            other = await browser.new_context()
            try:
                listing = await other.request.get(args.base_url + 'api/v1/connections')
                assert [m['id'] for m in (await listing.json())['models']] == ['oneshot-hosted'], 'Private connections visible to a different browser owner'
                denied = await other.request.post(args.base_url + 'api/v1/decisions', data=decision(identities[1]))
                assert denied.status == 403, 'Different browser owner could invoke the model'
            finally:
                await other.close()

            # Even malformed metadata submissions never include a model key.
            bad = await context.request.post(args.base_url + 'api/v1/connections', data={
                'model_id': 'invalid request ID', 'unexpected': 'invalid metadata'})
            assert bad.status == 422 and FIXTURE_KEY not in await bad.text(), 'Validation error echoed credentials'
            await page.locator('[data-language="zh"]').click()
            assert await page.locator('#status').text_content() == '已连接'
            await page.locator('#connectionSettings').click()
            await page.screenshot(path=str(output / 'desktop.png'))
            for width, height in [(390, 844), (320, 700)]:
                await page.set_viewport_size({'width': width, 'height': height})
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Page overflows at {width}px'
                assert await page.locator('#connectionDialog').evaluate('(el)=>el.scrollWidth <= el.clientWidth'), f'Dialog overflows at {width}px'
                await page.screenshot(path=str(output / f'mobile-{width}.png'))
            await page.locator('#connectCancel').click()

            if not args.skip_reload:
                print('Checking browser reload and heartbeat expiry…', flush=True)
                await page.reload(wait_until='domcontentloaded')
                await page.wait_for_function("typeof window.ConnectUI !== 'undefined'")
                assert FIXTURE_KEY not in await page.evaluate('JSON.stringify({local:{...localStorage},session:{...sessionStorage}})')
                deadline = asyncio.get_running_loop().time() + 55
                while True:
                    listing = await context.request.get(args.base_url + 'api/v1/connections')
                    rows = (await listing.json())['models']
                    direct = [next((model for model in rows if model['id'] == ident), None) for ident in identities]
                    assert all(model is not None for model in direct), 'Browser connection vanished; backend may have restarted during this test'
                    if all(model['ready'] is False for model in direct):
                        break
                    assert asyncio.get_running_loop().time() < deadline, 'Browser connection heartbeat never expired'
                    await asyncio.sleep(1)
                for ident in identities:
                    detached = await call(page, decision(ident))
                    assert detached['status'] == 503, f'Expired browser connection returned HTTP {detached["status"]} instead of 503'
                    assert FIXTURE_KEY not in json.dumps(detached), 'Disconnected error exposed credentials'
                assert len(seen) == 2, 'A model was invoked after its browser credentials were lost'

            assert not errors, 'Browser reported JavaScript errors: ' + '; '.join(errors)
            assert same_origin_requests and not same_origin_violations, 'Model credentials or endpoint reached the game server'
            print(json.dumps({'actual_backend': True, 'openai_browser_direct': True, 'decision_browser_direct': True,
                'same_origin_requests_metadata_only': True,
                'key_isolation': True, 'owner_isolation': True, 'validation_redaction': True,
                'desktop_and_mobile': True, 'reload_checked': not args.skip_reload,
                'url_prefix': urlsplit(args.base_url).path, 'screenshots': str(output)}, ensure_ascii=False))
        finally:
            for ident in identities:
                try:
                    response = await context.request.delete(args.base_url + 'api/v1/connections/' + ident)
                    if response.status not in (200, 204, 403, 404):
                        print(f'Cleanup failed for test connection {ident}: HTTP {response.status}', flush=True)
                except Exception:
                    print(f'Could not clean up test connection {ident}', flush=True)
            await context.close()
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', type=normalize_url, default='http://127.0.0.1:8092/')
    parser.add_argument('--skip-reload', action='store_true', help='Skip the approximately 45-second browser heartbeat expiry check')
    args = parser.parse_args()
    with mock_model(args.base_url) as (mock_url, seen):
        asyncio.run(check(args, mock_url, seen))


if __name__ == '__main__':
    main()
