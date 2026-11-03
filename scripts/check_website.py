#!/usr/bin/env python3
"""Smoke-test the bundled bilingual article, media and 12 workflow examples."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18086/')
    parser.add_argument('--output', type=Path, default=Path('var/ci/website'))
    parser.add_argument('--browser-executable')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    with sync_playwright() as p:
        launch = {'headless': True}
        if args.browser_executable:
            launch['executable_path'] = args.browser_executable
        browser = p.chromium.launch(**launch)
        for width in (1440, 390):
            for language in ('en', 'zh'):
                page = browser.new_page(viewport={'width': width, 'height': 960}, reduced_motion='reduce')
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda response: errors.append(f'{response.status}: {response.url}')
                        if response.status >= 400 and response.url.startswith(args.url) else None)
                page.add_init_script(f"localStorage.setItem('jev-language', '{language}')")
                page.goto(args.url.rstrip('/') + '/piccolo.html', wait_until='networkidle')
                assert page.locator('html').get_attribute('lang') == ('zh-CN' if language == 'zh' else 'en')
                assert page.locator('[data-game="othello"]').count() > 0
                assert page.locator('[data-game="snake"]').count() > 0
                for name in ('harness', 'data'):
                    host = page.locator('#' + name + 'Demo')
                    tabs = host.get_by_role('tab')
                    assert tabs.count() == 6
                    for index in range(6):
                        tabs.nth(index).click()
                        assert tabs.nth(index).get_attribute('aria-selected') == 'true'
                        assert host.locator('.wd-choice').count() >= 2
                for selector in ('#qwenpaw-showcase', '#datajev-showcase'):
                    image = page.locator(selector).locator('img').first
                    image.scroll_into_view_if_needed()
                    image.evaluate('(img) => img.decode()')
                    assert image.evaluate('(img) => img.naturalWidth') > 0
                page.locator('#harnessDemo').screenshot(path=str(args.output / f'workflows-{width}-{language}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
                checks.append({'width': width, 'language': language, 'workflow_cases': 12})
                page.close()
        context = browser.new_context()
        response = context.request.get(args.url.rstrip('/') + '/blog/assets/zenless-zone-zero.mp4', headers={'Range': 'bytes=0-63'})
        assert response.status == 206
        assert len(response.body()) == 64
        assert not errors, errors
        browser.close()
    (args.output / 'report.json').write_text(json.dumps({'checks': checks, 'errors': errors, 'video_range': True}, indent=2) + '\n')
    print('Article, 12 cases, recordings and video seeking passed in both languages at desktop and mobile sizes.')


if __name__ == '__main__':
    main()
