"""Render real native retry feedback in both languages and viewport sizes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from blink_arena.engine import get_engine


def run():
    e = get_engine('minesweeper'); state = e.reset(2026102194)
    for action in ('[3 3]', '[0 4]', '[1 4]'):
        state = e.step(state, action)
    root = Path(__file__).resolve().parents[1]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        for width in (390, 1440):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_content('<canvas id="showcaseCanvas"></canvas><div id="showcaseActions"></div><div id="keyboardHint"></div>')
            page.evaluate("window.$=id=>document.getElementById(id);window.JevI18n={lang:'zh'};window.showcaseBusy=false")
            page.add_script_tag(path=str(root/'web/playground/selected-games.js'))
            page.add_style_tag(path=str(root/'web/playground/selected-games.css'))
            for language in ('zh', 'en'):
                page.evaluate('(lang)=>window.JevI18n.lang=lang', language)
                page.evaluate('([world,choices])=>JevSelectedGames.render(world,choices,action=>window.clicked=action)', [e.public(state),e.legal_actions(state)])
                text = page.locator('.selected-feedback').inner_text()
                assert ('已踩到雷：2行 5列' if language=='zh' else 'You hit a mine at (1, 4).') in text
                assert ('剩余重试：0' if language=='zh' else 'retries remaining: 0') in text
                assert page.locator('.selected-feedback').get_attribute('role') == 'status'
                assert page.locator('.selected-feedback').evaluate('(n)=>n.getBoundingClientRect().right<=innerWidth')
                results.append({'width': width, 'language': language, 'feedback': True})
            page.locator('[data-row="1"][data-col="4"]').click()
            assert page.evaluate('window.clicked') == '[1 4]'
            assert not errors, errors
            page.close()
        browser.close()
    print(json.dumps(results))

if __name__=='__main__':run()
