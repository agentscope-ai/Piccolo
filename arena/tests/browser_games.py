#!/usr/bin/env python3
"""Open every packaged game in the manual UI without connecting a model."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
GAMES = [game['id'] for game in json.loads((ROOT / 'leaderboard/arena.json').read_text())['fixed_config']['games']]
WORLDS = {'mario_platformer': ('marioFrame', 'JevMario'), 'terraria_survival': ('terrariaFrame', 'JevTerramai')}
REALTIME = {'mario_platformer', 'terraria_survival', 'snake_navigation', 'tetris_placement'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8093/')
    parser.add_argument('--output', type=Path, default=ROOT / 'var/browser')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report, failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        for name, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            page.goto(args.url, wait_until='networkidle')
            page.locator('[data-tab="games"]').click()
            page.wait_for_function('catalog && showcaseKinds.length > 0 && !busy && !showcaseBusy')
            page.locator('#playBrowseGames').click()
            page.wait_for_selector('#playFilters [data-filter="all"]')
            page.locator('#playFilters [data-filter="realtime"]').click()
            realtime = set(page.locator('#gamePicker [data-kind]').evaluate_all('(nodes) => nodes.map(node => node.dataset.kind)'))
            if realtime != REALTIME:
                failures.append(f'{name}: realtime category does not contain the five registered realtime games')
            page.locator('#playFilters [data-filter="all"]').click()
            available = set(page.locator('#gamePicker [data-kind]').evaluate_all('(nodes) => nodes.map(node => node.dataset.kind)'))
            if available != set(GAMES) | {'mbti_text'}:
                failures.append(f'{name}: picker differs from 21 games plus the MBTI text page')
            page.locator('.play-library-close').click()
            page.locator('#playLibrary').wait_for(state='hidden')
            for game in GAMES:
                try:
                    page.locator('#playQuickGame').select_option(game)
                    page.wait_for_function('kind => selectedPlay === kind && !busy && !showcaseBusy', arg=game, timeout=30000)
                    if page.locator('#playQuickGame').input_value() != game:
                        failures.append(f'{name}/{game}: workspace selection not reflected')
                    selected = page.locator(f'#gamePicker [data-kind="{game}"]')
                    if selected.get_attribute('aria-pressed') != 'true':
                        failures.append(f'{name}/{game}: picker selection not reflected')
                    state = page.evaluate('''() => ({board:catalog.games.some(g=>g.id===selectedPlay),
                        session:!!showcaseSession,world:showcaseKind?.mode==='world'})''')
                    if state['board']:
                        if not page.locator('#boardPlay').is_visible():
                            failures.append(f'{name}/{game}: board panel hidden')
                    elif not page.locator('#showcasesView').is_visible():
                        failures.append(f'{name}/{game}: showcase panel hidden')
                    elif game in WORLDS:
                        frame_id, bridge = WORLDS[game]
                        world = page.locator(f'#{frame_id}').element_handle().content_frame()
                        world.wait_for_function('bridge => !!window[bridge]?.snapshot', arg=bridge)
                        observation = world.evaluate('bridge => window[bridge].snapshot()', bridge)
                        if not observation.get('player') or not observation.get('map'):
                            failures.append(f'{name}/{game}: browser bridge has no playable world')
                    elif not state['session']:
                        failures.append(f'{name}/{game}: manual session missing')
                    dimensions = page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                    if dimensions['scroll'] > dimensions['client'] + 1:
                        failures.append(f'{name}/{game}: page overflow {dimensions}')
                    if game in REALTIME or game == 'doudizhu':
                        page.screenshot(path=str(args.output / f'game-{name}-{game}.png'), full_page=True)
                    report.append({'viewport': name, 'game': game, 'manual_session': state,
                                   'page_width': dimensions})
                except Exception as error:
                    failures.append(f'{name}/{game}: {type(error).__name__}')
            failures.extend(f'{name}: {error}' for error in errors)
            page.close()
        browser.close()
    (args.output / 'games-report.json').write_text(json.dumps({'checks': report, 'failures': failures}, ensure_ascii=False, indent=2) + '\n')
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)
    print(f'{len(report)} manual game views passed: all 21 games, desktop/mobile, real browser world bridges, five-game realtime category; no console errors or page overflow.')


if __name__ == '__main__':
    main()
