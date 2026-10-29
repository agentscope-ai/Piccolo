"""Opt-in real-model, one-action audit of every game visible in the frontend."""
import argparse
import asyncio
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from playwright.async_api import async_playwright


async def run(args):
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    checks, page_errors = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1440, 'height': 1100})
        if args.allow_local_network:
            url = urlsplit(args.url)
            await context.grant_permissions(['local-network-access'], origin=f'{url.scheme}://{url.netloc}')
        page = await context.new_page()
        ident = 'systemone-audit-' + str(time.time_ns())
        try:
            await page.goto(args.url, wait_until='domcontentloaded')
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            await page.evaluate("window.JevI18n.setLanguage('zh');window.ConnectUI.open()")
            for key, value in [('connectionModelId', ident), ('connectionName', 'System One audit'),
                               ('connectionServedModel', args.model), ('connectionEndpoint', args.endpoint)]:
                await page.locator('#' + key).fill(value)
            await page.locator('#connectionAdapter').select_option('decision')
            await page.locator('#connectSave').click()
            await page.wait_for_function('window.ConnectUI.configured', timeout=20000)
            await page.locator('#connectCancel').click()
            await page.locator('[data-tab=games]').click()
            await page.evaluate("document.getElementById('autoReply').checked=false")
            await page.wait_for_function('document.querySelectorAll("#playQuickGame option").length>1')
            groups = await page.evaluate('window.JevGameCategories.groups')
            games = [(group['id'], game) for group in groups for game in group['games']]
            for category, game in games:
                if game == 'mbti_text':
                    continue
                began = time.monotonic()
                try:
                    await page.locator('#playGameCategory').select_option(category)
                    await page.locator('#playQuickGame').select_option(game)
                    await page.wait_for_function('k=>selectedPlay===k&&!busy&&!showcaseBusy', arg=game)
                    if await page.locator('#revealHand').is_visible():
                        await page.locator('#revealHand').click()
                        await page.wait_for_function('!showcaseBusy')
                    button = '#modelMove' if await page.locator('#boardPlay').is_visible() else '#showcaseModel'
                    await page.locator(button).click(timeout=15000)
                    await page.wait_for_function('!busy&&!showcaseBusy', timeout=150000)
                    state = await page.evaluate('''()=>({
                        error:document.getElementById('globalError').textContent,
                        error_visible:!document.getElementById('globalError').classList.contains('hidden'),
                        kind:selectedPlay,world:showcaseSession?.world?.kind===selectedPlay?showcaseSession.world:null,
                        can_switch:!document.getElementById('playQuickGame').disabled,
                        decision:document.getElementById('lastDecision').textContent})''')
                    row = {'game': game, 'status': 'error' if state['error_visible'] else 'ok',
                           'seconds': round(time.monotonic() - began, 3), **state}
                    if not state['can_switch']:
                        row['status'] = 'error'
                    await page.screenshot(path=str(out / (game + '.png')), full_page=True)
                except Exception as error:
                    row = {'game': game, 'status': 'error', 'error_type': type(error).__name__,
                           'error': str(error)[:500]}
                checks.append(row)
                (out / 'games.json').write_text(json.dumps({'checks': checks,
                    'page_errors': page_errors}, ensure_ascii=False, indent=2) + '\n')
                print(json.dumps({k: v for k, v in row.items() if k != 'world'}, ensure_ascii=False), flush=True)
        finally:
            # Release this browser's registration; never leave a globally reserved ID.
            try:
                await page.evaluate('''async id=>await fetch('./api/v1/connections/'+encodeURIComponent(id),
                    {method:'DELETE'})''', ident)
            finally:
                await browser.close()
    return int(bool(page_errors) or any(row['status'] != 'ok' for row in checks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--model', default='jev-policy')
    parser.add_argument('--allow-local-network', action='store_true',
                        help='Grant the test browser access to the explicitly supplied loopback bridge')
    parser.add_argument('--output', required=True)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
