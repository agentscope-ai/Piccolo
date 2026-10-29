"""Offline browser regression for realtime rendering and world request ownership.

The disposable model connection returns fixtures in the browser; no inference
service is contacted, so concurrent model evaluations are unaffected.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


async def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        for width in (1440, 390):
            page = await browser.new_page(viewport={'width': width, 'height': 1100})
            await page.add_init_script('window.__JEV_TEST_MODE__=true')
            if args.allow_local_network:
                site = urlsplit(args.url)
                await page.context.grant_permissions(['local-network-access'], origin=f'{site.scheme}://{site.netloc}')
            page.on('pageerror', lambda error: errors.append(str(error)))
            ident = 'realtime-recovery-' + str(time.time_ns())
            request_started = asyncio.Event()
            reply_delay = 0.2
            async def model_reply(route):
                body = route.request.post_data_json
                options = body['question']['options']
                action = next((item['id'] for item in options if item['id'] in ('0:0', 'right')), options[0]['id'])
                request_started.set()
                await asyncio.sleep(reply_delay)
                try:
                    await route.fulfill(json={'schema_version': 'jev.decision.v1',
                        'request_id': body['request_id'], 'model': body['model'], 'action': action})
                except Exception:
                    pass  # A terminal/restart can abort this deliberately late fixture.
            await page.route('http://127.0.0.1:39999/fixture-decide', model_reply)
            try:
                await page.goto(args.url, wait_until='domcontentloaded')
                await page.wait_for_function('showcaseKinds.length>0&&!busy&&!showcaseBusy')
                games=await page.locator('#playQuickGame option').evaluate_all('(nodes)=>nodes.map(n=>n.value).filter(Boolean)')
                assert len(set(games)-{'mbti_text'})==22 and 'racing_sprint' not in games
                await page.locator('[data-tab=games]').click()
                await page.evaluate('ConnectUI.open()')
                for key, value in [('connectionModelId', ident), ('connectionName', 'Realtime fixture'),
                                   ('connectionServedModel', 'fixture'),
                                   ('connectionEndpoint', 'http://127.0.0.1:39999/fixture-decide')]:
                    await page.locator('#' + key).fill(value)
                await page.locator('#connectionAdapter').select_option('decision')
                await page.locator('#connectSave').click()
                await page.wait_for_function('ConnectUI.configured')
                await page.locator('#connectCancel').click()

                await page.locator('#playQuickGame').select_option('tetris_placement')
                await page.wait_for_function("selectedPlay==='tetris_placement'&&!showcaseBusy")
                await page.evaluate('''()=>{
                    window.__tetrisDraws=[];
                    const original=JevTetrisRenderer.draw;
                    JevTetrisRenderer.draw=function(g,o){
                        const visual=this.visualState(g,o||{});
                        __tetrisDraws.push({elapsed:g.elapsed,piece:g.active?.piece_id,y:visual.visual_active?.y});
                        return original.call(this,g,o);
                    };
                }''')
                # A first model reply starts gravity, then its persistent target
                # must visibly fall while autoplay continues polling the clock.
                await page.locator('#showcaseAuto').click()
                await page.wait_for_function('showcaseSession.world.started')
                await page.wait_for_timeout(1600)
                first = await page.evaluate('({y:showcaseSession.world.active.y,piece:showcaseSession.world.active.piece_id})')
                await page.locator('#showcaseCanvas').screenshot(path=str(out / f'tetris-{width}-falling-a.png'))
                await page.wait_for_timeout(1500)
                falling = await page.evaluate('''()=>({y:showcaseSession.world.active.y,
                    piece:showcaseSession.world.active.piece_id,autoplay:showcaseAuto,
                    draws:__tetrisDraws.length,visual_positions:new Set(__tetrisDraws.map(d=>d.y)).size})''')
                assert falling['piece'] == first['piece'] and falling['y'] > first['y'], (first, falling)
                assert falling['autoplay'] and falling['draws'] > 10 and falling['visual_positions'] > 4, falling
                await page.locator('#showcaseCanvas').screenshot(path=str(out / f'tetris-{width}-falling-b.png'))
                checks.append({'game': 'tetris_placement', 'width': width, 'check': 'model_autoplay_gravity', **falling})
                await page.evaluate('stopAuto()')
                # Keep a model request in flight while a manually started piece
                # falls. Renderer updates must continue during inference itself.
                await page.locator('#showcaseNew').click()
                await page.wait_for_function('!showcaseBusy&&!showcaseSession.world.started')
                await page.locator('[data-tetris-action=soft_drop]').click()
                await page.wait_for_function('showcaseSession.world.started')
                reply_delay = 3.5
                request_started.clear()
                await page.locator('#showcaseAuto').click()
                await asyncio.wait_for(request_started.wait(), 10)
                during_before = await page.evaluate('({y:showcaseSession.world.active.y,draws:__tetrisDraws.length})')
                await page.wait_for_timeout(1300)
                during = await page.evaluate('({y:showcaseSession.world.active.y,draws:__tetrisDraws.length,busy:showcaseBusy})')
                assert during['busy'] and during['y'] > during_before['y'] and during['draws'] > during_before['draws'], during
                checks.append({'game': 'tetris_placement', 'width': width, 'check': 'gravity_during_inference', **during})
                await page.evaluate('stopAuto()')

                # Reach actual native engine terminals through manual UI inputs,
                # then restart. No terminal state is injected into the frontend.
                for native_kind in ('tetris_placement', 'snake_navigation'):
                    await page.locator('#playQuickGame').select_option(native_kind)
                    await page.wait_for_function('k=>selectedPlay===k&&!showcaseBusy', arg=native_kind)
                    await page.locator('#showcaseNew').click()
                    await page.wait_for_function('!showcaseBusy')
                    session = await page.evaluate('showcaseSession.session_id')
                    if native_kind == 'tetris_placement':
                        for _ in range(20):
                            if await page.evaluate('!!showcaseSession.world.outcome'):
                                break
                            steps = await page.evaluate('showcaseSession.world.steps')
                            await page.locator('[data-tetris-action=hard_drop]').click()
                            await page.wait_for_function('n=>showcaseSession.world.steps>n||showcaseSession.world.outcome', arg=steps)
                            await page.wait_for_timeout(100)
                    elif native_kind == 'snake_navigation':
                        # The seed controls the initial heading; reversing into
                        # the body is correctly disabled by the live controls.
                        await page.locator('[data-snake-direction]:not(:disabled)').first.click()
                    await page.wait_for_function('!!showcaseSession.world.outcome', timeout=15000)
                    assert not await page.locator('#showcaseNew').is_disabled()
                    assert await page.locator('#showcaseModel').is_disabled()
                    assert not await page.evaluate('showcaseBusy')
                    await page.screenshot(path=str(out / f'{native_kind}-{width}-terminal.png'))
                    await page.locator('#showcaseNew').click()
                    await page.wait_for_function('old=>showcaseSession.session_id!==old&&!showcaseSession.world.outcome&&!showcaseBusy', arg=session)
                    checks.append({'game': native_kind, 'width': width, 'check': 'native_terminal_restart'})

                await page.locator('#playQuickGame').select_option('mario_platformer')
                await page.wait_for_function("selectedPlay==='mario_platformer'&&!showcaseBusy")
                state = json.loads((Path(__file__).parent / 'fixtures/mario_large_observation.json').read_text())
                for route in ('engines/mario_platformer/observe', 'showcases/world'):
                    reply_delay = .2
                    result = await page.evaluate('async ([route,state])=>{let r=await api(route,{state,kind:"mario_platformer"});return !!(r.record||r.result)}', [route, state])
                    assert result
                checks.append({'game': 'mario_platformer', 'width': width, 'check': 'complete_large_observation',
                               'bytes': len(json.dumps(state, ensure_ascii=False).encode())})

                # Force a real physics death with a deliberately late model reply.
                # Capture counts before it to detect terminal postMessage loops.
                await page.evaluate('''()=>{
                    window.__terminalMessages=0;
                    window.addEventListener('message',e=>{
                        if(e.data?.type==='jev-mario-state'&&e.data.observation.outcome)__terminalMessages++;
                    });
                    const b=worldBridge();b.fixture({seed:2,player:{y:520},enemies:[],plants:[]});
                    // Synchronize the fixture: public HTTP can take longer than
                    // the one physics frame before death. Resume only once the
                    // delayed model request has actually reached the browser.
                    b.activate(false);
                    worldOutcome=null;
                }''')
                reply_delay = 3.5
                request_started.clear()
                await page.evaluate('void modelShowcaseStep()')
                await asyncio.wait_for(request_started.wait(), 10)
                await page.evaluate('worldBridge().activate(true)')
                await page.wait_for_function("worldOutcome==='loss'&&!showcaseBusy&&!document.getElementById('showcaseNew').disabled", timeout=2000)
                await page.wait_for_timeout(150)
                terminal = await page.evaluate('({messages:__terminalMessages,autoplay:showcaseAuto,busy:showcaseBusy})')
                assert terminal['messages'] < 20 and not terminal['autoplay'] and not terminal['busy'], terminal
                await page.screenshot(path=str(out / f'mario-{width}-terminal.png'))
                await page.locator('#showcaseNew').click()
                await page.wait_for_function('!showcaseBusy&&worldOutcome===null')
                generation = await page.evaluate('worldBridge().condition().generation')
                await page.wait_for_timeout(3700)
                restarted = await page.evaluate('({generation:worldBridge().condition().generation,outcome:worldOutcome,busy:showcaseBusy,error:!document.getElementById("globalError").classList.contains("hidden")})')
                assert restarted == {'generation': generation, 'outcome': None, 'busy': False, 'error': False}, restarted
                checks.append({'game': 'mario_platformer', 'width': width, 'check': 'death_restart_late_reply', **terminal})

                # A manual restart during inference also cancels only its owner;
                # completion of the old request must not release a newer intent.
                reply_delay = 3.5
                request_started.clear()
                await page.evaluate('void modelShowcaseStep()')
                await asyncio.wait_for(request_started.wait(), 10)
                await page.evaluate('newShowcase()')
                await page.wait_for_function('!showcaseBusy')
                generation = await page.evaluate('worldBridge().condition().generation')
                request_started.clear()
                await page.evaluate('void modelShowcaseStep()')
                await asyncio.wait_for(request_started.wait(), 10)
                await page.wait_for_timeout(300)
                assert await page.evaluate('!!worldOperation&&showcaseBusy')
                await page.locator('#marioFrame').element_handle()
                await page.evaluate('''()=>{
                    const frame=document.getElementById('marioFrame').contentWindow,b=frame.JevMario;
                    frame.parent.postMessage({type:'jev-mario-state',generation:b.condition().generation-1,
                        observation:{...b.snapshot(false),outcome:'loss'}},location.origin);
                }''')
                await page.wait_for_timeout(100)
                assert await page.evaluate('worldOutcome===null&&!!worldOperation&&showcaseBusy')
                await page.evaluate('stopAuto()')
                await page.wait_for_timeout(3700)
                assert await page.evaluate('g=>worldBridge().condition().generation===g&&!showcaseBusy&&!worldOperation', generation)
                checks.append({'game': 'mario_platformer', 'width': width, 'check': 'restart_request_ownership'})
            finally:
                await page.request.delete(args.url.rstrip('/') + '/api/v1/connections/' + ident)
                await page.close()
            (out / 'report.json').write_text(json.dumps({'checks': checks, 'page_errors': errors,
                'inference_service_requests': 0}, ensure_ascii=False, indent=2) + '\n')
        await browser.close()
    assert not errors, errors
    print(json.dumps({'checks': len(checks), 'page_errors': errors, 'inference_service_requests': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-local-network', action='store_true', help='Explicitly allow this disposable test browser to access the loopback fixture model')
    asyncio.run(run(parser.parse_args()))
