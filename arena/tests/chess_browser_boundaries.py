"""Focused chess late-response and actual probe-input checks; CPU fixtures only."""
import asyncio
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from playwright.async_api import async_playwright

from blink_arena.app import create_app
from blink_arena.schemas import AppConfig, DecisionOutput

OUT = Path(os.environ.get('JEV_CHESS_TEST_OUT', Path(tempfile.gettempdir()) / 'jev-chess-browser'))
MODEL = 'chess-boundary-fixture'


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parents[1] / 'web'
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(assets)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    calls, replies, errors = [], [], []
    ready, release = asyncio.Event(), asyncio.Event()
    try:
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(data=folder, config=AppConfig())) as client:
            response = client.post('/api/v1/connections', json={'model_id': MODEL, 'name': 'Chess boundary fixture',
                                   'served_model': MODEL, 'adapter': 'decision', 'transport': 'browser'})
            assert response.status_code == 201, response.status_code

            async def fixture(request):
                calls.append(request.model_dump(mode='json'))
                options = request.question.options
                action = next((o.id for o in options if o.id == 'e2e4'), options[0].id)
                return DecisionOutput(request_id=request.request_id, model=request.model, action=action,
                                      probabilities={o.id: float(o.id == action) for o in options})

            client.app.state.providers.browser_relays[MODEL] = fixture
            client.app.state.connections.entries[MODEL]['last_poll'] = time.monotonic()
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
                page = await browser.new_page(viewport={'width': 1400, 'height': 1100})
                page.on('pageerror', lambda e: errors.append(str(e)))

                async def route(route):
                    req = route.request
                    parsed = urlparse(req.url)
                    headers = {'content-type': 'application/json', 'X-Demo-Model': MODEL}
                    result = await asyncio.to_thread(client.request, req.method,
                        parsed.path + ('?' + parsed.query if parsed.query else ''), content=req.post_data, headers=headers)
                    if parsed.path.endswith('/steps') and req.method == 'POST':
                        assert result.status_code == 200
                        replies.append(result.json())
                        ready.set()
                        await asyncio.wait_for(release.wait(), 30)
                    await route.fulfill(status=result.status_code, content_type=result.headers.get('content-type','application/json'), body=result.content)

                await page.route('**/api/**', route)
                await page.goto(f'http://127.0.0.1:{server.server_port}/?model={MODEL}')
                await page.wait_for_function('modelReady && typeof showcaseKinds!=="undefined" && showcaseKinds.some(g=>g.kind==="chess") && !busy')
                await page.locator('#playSeed').fill('0')
                await page.locator('#playSearch').fill('chess')
                await page.locator('#gamePicker [data-kind="chess"]').click()
                await page.wait_for_function('showcaseSession?.world.kind==="chess" && !showcaseBusy')
                initial = await page.evaluate('structuredClone(showcaseSession)')

                # Complete backend inference while its browser response is held.
                await page.locator('#showcaseModel').click()
                await asyncio.wait_for(ready.wait(), 20)
                await page.evaluate('tab("leaderboard")')
                assert await page.evaluate('!playTabVisible && showcaseBusy')
                release.set()
                await page.wait_for_function('!showcaseBusy && showcaseSession.revision===1')
                assert not await page.locator('#chessStage').is_visible()
                await page.evaluate('tab("games")')
                assert await page.locator('#chessStage').is_visible()
                assert await page.evaluate('showcaseSession.world.steps') == 1
                assert await page.locator('#sceneStats strong').first.inner_text() == '1'
                assert 'e2e4' in await page.locator('#lastDecision').text_content()
                assert await page.locator('#showcaseHistory > div').count() == 1
                assert await page.locator('#showcaseResult [data-i18n-result]').count() == 1

                result = replies[0]['result']
                actual = json.loads(await page.locator('#chessSentInput pre').text_content())
                assert actual == result['model_input']['schema_input'] and actual in calls
                sample = result['decision_stability']['samples'][result['representative_sample_index']]
                assert [o['id'] for o in actual['question']['options']] == sample['order']
                assert actual['observation'] == initial['input']['state']
                shown_orders = [json.loads(s) for s in await page.locator('#chessProbeOrders pre').all_text_contents()]
                assert len(shown_orders) == 3
                assert [s['option_order'] for s in shown_orders] == [s['order'] for s in result['decision_stability']['samples']]
                assert initial['input']['state']['observation']['fen'] in await page.locator('#chessDecisionContext').text_content()
                assert 'Canonical candidate order' in await page.locator('#chessDecisionContext').text_content()

                # Repeated hide/show restores the same receipt without double-counting.
                await page.evaluate('tab("leaderboard");tab("games")')
                assert await page.locator('#showcaseHistory > div').count() == 1
                assert json.loads(await page.locator('#chessSentInput pre').text_content()) == actual

                # Deliberately replace the session while an old response is delayed.
                # Production controls prevent this overlap; the generation guard
                # still must prevent a programmatic/new-client replacement leak.
                ready.clear(); release.clear()
                await page.locator('#showcaseModel').click()
                await asyncio.wait_for(ready.wait(), 20)
                await page.evaluate('''async()=>{
                    showcaseSession=await JevChessUI.create(43);
                    clearPlayResult();renderShowcaseGame();
                }''')
                newer = await page.evaluate('structuredClone(showcaseSession)')
                assert newer['session_id'] != initial['session_id']
                release.set()
                await page.wait_for_function('!showcaseBusy')
                assert await page.evaluate('showcaseSession.session_id') == newer['session_id']
                assert await page.evaluate('showcaseSession.revision') == 0
                assert await page.locator('#chessSentInput').count() == 0
                assert await page.locator('#showcaseResult').text_content() == ''
                assert await page.locator('#showcaseHistory > div').count() == 0
                assert newer['world']['fen'] in await page.locator('#chessDecisionContext').text_content()
                assert not errors, errors
                await page.screenshot(path=str(OUT / 'chess-boundary-restored.png'), full_page=True)
                await browser.close()
        result = {'passed': True, 'checks': ['hidden_tab_completion_updates_session_and_restores_sidebar_result',
                  'representative_request_matches_actual_provider_call_and_probability_probe',
                  'canonical_context_distinguished_from_three_actual_orders',
                  'repeated_tab_restore_does_not_duplicate_decision',
                  'late_old_generation_cannot_replace_new_session_or_inputs'],
                  'fixture_prediction_calls': len(calls), 'real_model_calls': 0, 'page_errors': errors,
                  'gpu_used': False, 'public_deployment': False}
        (OUT / 'frontend-boundary-regression.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    asyncio.run(main())
