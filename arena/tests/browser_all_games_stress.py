"""Browser-only fixture model: multi-seed play, failure recovery and lifecycle audit.

Does not contact the inference service or measure model ability. Private hands
are revealed only by clicking the same explicit handoff controls as a user.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

REALTIME = {'terraria_survival', 'mario_platformer', 'snake_navigation', 'tetris_placement'}


async def run(args):
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    checks, page_errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        for width in args.widths:
            page = await browser.new_page(viewport={'width': width, 'height': 1100})
            if args.allow_local_network:
                site = urlsplit(args.url)
                await page.context.grant_permissions(['local-network-access'], origin=f'{site.scheme}://{site.netloc}')
            page.on('pageerror', lambda e: page_errors.append(str(e)))
            ident = 'all-games-fixture-' + str(time.time_ns())
            mode = 'ok'
            calls = 0
            last_request = None
            async def fixture(route):
                nonlocal calls, last_request
                calls += 1
                body = route.request.post_data_json
                last_request = body
                if args.verify_compact_inputs and body.get('game') in ('othello_6x6', 'hex_7x7'):
                    assert 'model_input_revision' not in body['observation'], 'regressed representation was not restored'
                if args.verify_compact_inputs and body.get('game') in ('mario_platformer', 'terramai_directional'):
                    expected = ('jev.model-input.compact.v1' if body['game'] == 'mario_platformer'
                                else 'jev.model-input.intent.v2')
                    assert body['observation']['model_input_revision'] == expected
                    assert max(len(option['label']) for option in body['question']['options']) < 150
                if mode == 'rate_limited':
                    return await route.fulfill(status=429, json={'error': 'fixture rate limit'})
                action = body['question']['options'][0]['id']
                await asyncio.sleep(.03)
                await route.fulfill(json={'schema_version': 'jev.decision.v1', 'request_id': body['request_id'],
                    'model': body['model'], 'action': action})
            await page.route('http://127.0.0.1:39998/fixture-decide', fixture)
            async def idle():
                await page.wait_for_function('!busy&&!showcaseBusy', timeout=30000)
            async def state():
                return await page.evaluate('''()=>{
                    const board=!document.getElementById('boardPlay').classList.contains('hidden'),
                        world=showcaseKind?.mode==='world'&&selectedPlay===showcaseKind.kind,
                        bridge=world?worldBridge():null;
                    return {game:selectedPlay,board,world,
                        session:board?gameState.session_id:world?bridge.condition().generation:showcaseSession.session_id,
                        revision:board?gameState.revision:world?bridge.snapshot(false).decisions:showcaseSession.revision,
                        terminal:board?!!gameState.game.winner:world?!!worldOutcome:!!showcaseSession.world.outcome,
                        handoff:!board&&!world&&!!showcaseSession.world.handoff,
                        error:!document.getElementById('globalError').classList.contains('hidden'),
                        error_text:document.getElementById('globalError').textContent,
                        busy:busy||showcaseBusy};}''')
            async def reveal():
                for selector in ('#revealHand', '.selected-reveal'):
                    control = page.locator(selector)
                    if await control.is_visible():
                        await control.click(); await idle()
                        return True
                return False
            async def model_step():
                await reveal()
                current = await state()
                if current['terminal']:
                    return current
                before_calls = calls
                await page.locator('#modelMove' if current['board'] else '#showcaseModel').click(timeout=10000)
                await idle()
                result = await state()
                if args.verify_compact_inputs and mode == 'ok' and calls > before_calls and not result['error'] and game in ('mario_platformer', 'terraria_survival'):
                    selector = '#gameFields' if current['board'] else '#showcaseFields'
                    shown = await page.locator(selector + ' .content').first.text_content()
                    assert json.loads(shown) == last_request['observation'], 'input pane differs from the actual model request'
                    row['compact_input_checks'] = row.get('compact_input_checks', 0) + 1
                if result['handoff']:
                    assert not (await page.locator('#showcaseFields').inner_text()).strip(), 'previous private input remained visible at handoff'
                    assert await page.locator('#decisionDetails').get_attribute('open') is None
                    row['private_detail_checks'] = row.get('private_detail_checks', 0) + 1
                return result
            async def seed(value):
                await page.locator('#playSeed').fill(str(value))
                await page.locator('#playSeedApply').click()
                await idle()
            def save():
                (out / 'report.json').write_text(json.dumps({'checks': checks, 'page_errors': page_errors,
                    'inference_service_requests': 0}, ensure_ascii=False, indent=2) + '\n')
            try:
                await page.goto(args.url, wait_until='domcontentloaded')
                await page.wait_for_function('showcaseKinds.length>0&&!busy&&!showcaseBusy')
                await page.evaluate("JevI18n.setLanguage('zh');ConnectUI.open()")
                for key, value in [('connectionModelId', ident), ('connectionName', 'All games fixture'),
                                   ('connectionServedModel', 'fixture'),
                                   ('connectionEndpoint', 'http://127.0.0.1:39998/fixture-decide')]:
                    await page.locator('#' + key).fill(value)
                await page.locator('#connectionAdapter').select_option('decision')
                await page.locator('#connectSave').click()
                await page.wait_for_function('ConnectUI.configured')
                await page.locator('#connectCancel').click()
                await page.locator('[data-tab=games]').click()
                await page.evaluate('document.getElementById("autoReply").checked=false')
                await page.wait_for_function('document.querySelectorAll("#playQuickGame option").length>1')
                games = args.games or await page.locator('#playQuickGame option').evaluate_all('(ns)=>ns.map(n=>n.value).filter(k=>k!=="mbti_text")')
                for game in games:
                    began = time.monotonic()
                    row = {'game': game, 'width': width, 'status': 'running', 'seeds': [], 'steps': 0}
                    try:
                        await page.locator('#playQuickGame').select_option(game)
                        await page.wait_for_function('k=>selectedPlay===k&&!busy&&!showcaseBusy', arg=game)
                        for seed_value in (42, 43):
                            mode = 'ok'
                            await seed(seed_value)
                            assert not (await state())['error'], 'restart retained a stale error'
                            row['seeds'].append(seed_value)
                            # Request failures must release the controls and allow
                            # the same session to make a genuine later model call.
                            mode = 'rate_limited'
                            before_calls = calls
                            for _ in range(8):
                                failed = await model_step()
                                if calls > before_calls or failed['terminal']:
                                    break  # A one-option action makes no request.
                            if calls > before_calls:
                                assert failed['error'] and not failed['busy'], failed
                                assert '限流' in failed['error_text'], failed
                                row['error_recovery'] = row.get('error_recovery', 0) + 1
                                mode = 'ok'
                                recovered = await model_step()
                                assert not recovered['error'] and not recovered['busy'], recovered
                                row['steps'] += 1
                                if not recovered['terminal']:
                                    mode = 'rate_limited'
                                    previous_calls = calls
                                    for _ in range(8):
                                        failed_again = await model_step()
                                        if calls > previous_calls or failed_again['terminal']:
                                            break
                                    if calls > previous_calls:
                                        assert failed_again['error']
                                        mode = 'ok'
                                        await seed(seed_value)
                                        assert not (await state())['error'], 'restart retained a stale error'
                                        row['reset_after_error'] = row.get('reset_after_error', 0) + 1
                            mode = 'ok'
                            for _ in range(3 if game in REALTIME else 8):
                                before = await state()
                                if before['terminal']:
                                    break
                                after = await model_step()
                                assert not after['error'] and not after['busy'], after
                                assert after['revision'] >= before['revision'], (before, after)
                                row['steps'] += 1
                            # Autoplay may stop for a natural terminal or a private
                            # handoff, but it must never submit an unrevealed turn.
                            current = await state()
                            if not current['board'] and not current['terminal']:
                                await reveal()
                                if game == 'chess':
                                    await page.locator('#chessSeat-white').select_option('model')
                                    await page.locator('#chessSeat-black').select_option('rule')
                                await page.locator('#showcaseAuto').click()
                                await page.wait_for_timeout(600 if game not in REALTIME else 1600)
                                handoff = await state()
                                if handoff['handoff']:
                                    assert not await page.evaluate('showcaseAuto'), handoff
                                    row['handoff_pauses'] = row.get('handoff_pauses', 0) + 1
                                await page.evaluate('stopAuto()')
                                await idle()
                                assert not (await state())['error'], await state()
                            await reveal()
                            before_nav = await state()
                            await page.locator('[data-tab=blog]').click()
                            await page.locator('#blogView').wait_for(state='visible')
                            await page.locator('[data-tab=games]').click()
                            await page.locator('#gamesView').wait_for(state='visible')
                            await idle()
                            after_nav = await state()
                            assert after_nav['game'] == game and after_nav['session'] == before_nav['session'], (before_nav, after_nav)
                            assert not after_nav['error']
                            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), 'page overflow'
                        # Reset after playing/ending: controls and the selected
                        # game's visible rendering must be available again.
                        await seed(44)
                        ready = await state()
                        assert not ready['terminal'] and not ready['error'] and not ready['busy'], ready
                        surfaces = page.locator('#boardPlay #board:visible,#showcaseCanvas:visible,#marioFrame:visible,#terrariaFrame:visible,#selectedGameBoard:visible,#chessStage:visible,#agentGameStage:visible')
                        assert await surfaces.count() > 0, 'no visible surface'
                        await surfaces.first.screenshot(path=str(out / f'{game}-{width}.png'))
                        row.update(status='ok', seconds=round(time.monotonic() - began, 3))
                    except Exception as error:
                        row.update(status='error', error_type=type(error).__name__, error=str(error)[:900])
                        await page.screenshot(path=str(out / f'{game}-{width}-error.png'), full_page=True)
                    checks.append(row); save(); print(json.dumps(row, ensure_ascii=False), flush=True)
                    if row['status'] != 'ok':
                        raise AssertionError(row)
            finally:
                await page.request.delete(args.url.rstrip('/') + '/api/v1/connections/' + ident)
                await page.close()
        await browser.close()
    assert not page_errors, page_errors
    print(json.dumps({'passed': len(checks), 'page_errors': page_errors, 'inference_service_requests': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--widths', nargs='+', type=int, default=[1440, 390])
    parser.add_argument('--games', nargs='+')
    parser.add_argument('--verify-compact-inputs', action='store_true')
    parser.add_argument('--allow-local-network', action='store_true', help='Explicitly allow this disposable test browser to access the loopback fixture model')
    asyncio.run(run(parser.parse_args()))
