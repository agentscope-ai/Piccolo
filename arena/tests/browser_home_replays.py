"""Exercise completed Home replays without connecting a model."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', type=Path, help='Override only the replay asset for a local preview')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    archive = json.loads(args.archive.read_text()) if args.archive else json.load(
        urlopen(args.url.rstrip('/') + '/playground/data/home-decision.json', timeout=30))
    checks, errors, decisions = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in (1440, 390):
            page = browser.new_page(viewport={'width': width, 'height': 1000})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: decisions.append(request.url)
                    if '/decide' in request.url or '/connections/call' in request.url else None)
            if args.archive:
                page.route('**/playground/data/home-decision.json*', lambda route: route.fulfill(
                    content_type='application/json', body=json.dumps(archive)))
            page.goto(args.url, wait_until='networkidle')
            page.locator('[data-tab="blog"]').click()
            page.wait_for_selector('.home-demo-timeline')
            for language in ('en', 'zh'):
                page.locator(f'[data-language="{language}"]').click()
                for index, clip in enumerate(archive['clips']):
                    page.locator('.home-demo-game-tabs button').nth(index).click()
                    assert page.locator('.home-demo-model').inner_text() == clip['models'][0]['name']
                    assert page.locator('.home-demo-timeline').get_attribute('max') == str(len(clip['steps'])-1)
                    page.locator('.home-demo-finish').click()
                    assert page.locator('.home-demo-counter').inner_text().endswith(f'/ {len(clip["steps"])}')
                    assert page.locator('.home-demo-next').is_disabled()
                    assert ('获胜' if language == 'zh' else 'victory') in page.locator('.home-demo-stage-copy').last.inner_text()
                    if clip['game'] == 'tetris_placement':
                        page.wait_for_function("""() => document.querySelector('.jev-native-replay')?.contentDocument?.querySelector('canvas')?.width > 0""")
                        assert page.evaluate("""() => {
                          const frame=document.querySelector('.jev-native-replay'),canvas=frame.contentDocument.querySelector('canvas');
                          return canvas.getBoundingClientRect().height<=frame.clientHeight+1 && canvas.getBoundingClientRect().width<=frame.clientWidth+1;
                        }"""), 'Tetris canvas is cropped'
                    page.locator('#homeDecisionDemo').screenshot(path=str(args.out/f'{width}-{language}-{clip["game"]}.png'))
                    page.locator('.home-demo-reset').click()
                    assert page.locator('#homeDecisionDemo').get_attribute('data-phase') == '0'
                    assert page.locator('.home-demo-timeline').input_value() == '0'
                    assert not page.locator('.home-demo-next').is_disabled()
                    page.locator('.home-demo-timeline').fill(str(len(clip['steps'])//2))
                    assert page.locator('#homeDecisionDemo').get_attribute('data-phase') == '2'
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    checks.append({'width': width, 'language': language, 'game': clip['game'],
                                   'model': clip['models'][0]['name'], 'terminal_win': True,
                                   'seek_reset': True, 'overflow': False})
            # Animate a recorded waiting interval; gravity must visibly move.
            index = next(i for i, clip in enumerate(archive['clips']) if clip['game'] == 'tetris_placement')
            clip = archive['clips'][index]
            auto = next(i for i, step in enumerate(clip['steps']) if i > 0 and
                        step['execution'].get('no_request') and step['after']['steps'] > step['before']['steps'])
            page.locator('.home-demo-game-tabs button').nth(index).click()
            page.locator('.home-demo-reset').click()
            page.locator('.home-demo-timeline').fill(str(auto-1))
            page.locator('.home-demo-next').click()
            page.locator('.home-demo-play').click()
            page.wait_for_function("document.getElementById('homeDecisionDemo').dataset.phase === '2'")
            canvas = "document.querySelector('.jev-native-replay').contentDocument.getElementById('showcaseCanvas')"
            page.wait_for_timeout(100)
            first = page.evaluate(canvas + '.toDataURL()')
            page.wait_for_timeout(350)
            second = page.evaluate(canvas + '.toDataURL()')
            assert first != second, 'Recorded Tetris gravity did not move'
            page.locator('[data-tab="games"]').click()
            page.locator('[data-tab="blog"]').click()
            assert page.locator('.home-demo-play').get_attribute('aria-pressed') == 'false'
            page.emulate_media(reduced_motion='reduce')
            page.locator('.home-demo-finish').click()
            # Rapid game switches while the isolated renderer is mounting.
            for i in (index, 0, index, 1, index, 0):
                page.locator('.home-demo-game-tabs button').nth(i).click()
            page.wait_for_timeout(250)
            assert page.locator('#homeDecisionDemo').get_attribute('data-game') == archive['clips'][0]['game']
            page.locator('.home-demo-game-tabs button').first.focus()
            page.keyboard.press('End')
            assert page.locator('#homeDecisionDemo').get_attribute('data-game') == archive['clips'][-1]['game']
            page.keyboard.press('Home')
            assert page.locator('#homeDecisionDemo').get_attribute('data-game') == archive['clips'][0]['game']
            board = page.locator('.home-demo-board')
            board.dispatch_event('pointerdown', {'isPrimary': True, 'button': 0, 'pointerId': 1, 'clientX': 200, 'clientY': 100})
            board.dispatch_event('pointerup', {'isPrimary': True, 'button': 0, 'pointerId': 1, 'clientX': 100, 'clientY': 100})
            assert page.locator('#homeDecisionDemo').get_attribute('data-game') == archive['clips'][1]['game']
            assert not errors, errors
            page.close()
        browser.close()
    assert not decisions, 'Read-only replay issued a model request'
    report = {'checks': checks, 'errors': errors, 'model_requests': len(decisions),
              'gravity_visible': True, 'rapid_switch': True, 'reduced_motion': True,
              'game_tabs_keyboard': True, 'board_swipe': True}
    (args.out/'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'checks': len(checks), 'errors': len(errors), 'model_requests': len(decisions),
                      'gravity_visible': True}))


if __name__ == '__main__':
    main()
