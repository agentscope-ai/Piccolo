"""Read-only checks of the October 28 results, Piccolo display and public release."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18087/')
    parser.add_argument('--browser-executable')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks, errors, model_requests = [], [], []
    with sync_playwright() as p:
        launch = {'headless': True, 'args': ['--no-sandbox']}
        if args.browser_executable:
            launch['executable_path'] = args.browser_executable
        browser = p.chromium.launch(**launch)
        for size, width, height in [('desktop', 1440, 1050), ('mobile', 390, 844)]:
            for language in ['en', 'zh']:
                page = browser.new_page(viewport={'width': width, 'height': height}, reduced_motion='reduce')
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                page.on('request', lambda r: model_requests.append(r.url)
                        if r.method == 'POST' and any(s in r.url for s in ['/decision', '/predict', '/systemone', '/chat/completions']) else None)
                page.goto(args.url, wait_until='networkidle')
                page.locator(f'[data-language="{language}"]').click()
                page.wait_for_function("document.querySelector('#homeResults')?.innerText.includes('92.21')")
                home_card = page.locator('.home-usecase').filter(has=page.locator('[data-home-benchmark="harnessjevbench"]'))
                assert 'Coming Soon' not in home_card.inner_text()
                assert home_card.locator('a[href="https://github.com/agentscope-ai/HarnessJevBench"]').count() == 1
                if size == 'desktop':
                    page.screenshot(path=str(args.output / f'{size}-{language}-home.png'), full_page=True)
                expected = {}
                for benchmark in ['jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench']:
                    response = page.request.get(args.url.rstrip('/') + '/api/v1/leaderboards/' + benchmark)
                    assert response.ok
                    expected[benchmark] = response.json()['rows']
                page.locator('[data-tab="leaderboard"]').click()
                page.wait_for_selector('.lb-metrics-table tbody tr')
                for benchmark, source in expected.items():
                    page.locator(f'#leaderboardTabs [data-benchmark="{benchmark}"]').click()
                    table = page.locator('.lb-metrics-table')
                    rows = table.locator('tbody tr[data-result-model]')
                    assert rows.count() == 11
                    assert rows.first.get_attribute('data-result-model') == 'blink-27b-1028'
                    assert table.get_attribute('data-sort-key') == 'featured'
                    assert page.locator('.lb-featured-note').is_visible()
                    assert table.locator('.lb-rank:visible').count() == 11
                    assert 'Blink' not in table.inner_text() and 'StartLux' not in table.inner_text()
                    assert {r['model_id'] for r in source} == set(rows.evaluate_all('(rs)=>rs.map(r=>r.dataset.resultModel)'))
                    for r in source:
                        row = table.locator(f'tr[data-result-model="{r["model_id"]}"]')
                        actual = row.locator('td[data-metric]').first
                        if r['score'] is None:
                            assert actual.inner_text() == '—'
                            assert row.locator('.lb-rank').inner_text() == '—'
                        else:
                            assert abs(float(actual.get_attribute('data-sort-value')) - r['score']) < 1e-12
                            rank = 1 + sum(x['score'] is not None and x['score'] > r['score'] for x in source)
                            assert row.locator('.lb-rank').inner_text() == str(rank)
                    if benchmark == 'harnessjevbench':
                        assert rows.first.locator('.lb-rank').inner_text() == '2'
                        assert page.locator('.lb-benchmark-link[href="https://github.com/agentscope-ai/HarnessJevBench"]').count() >= 1
                        assert 'Coming Soon' not in page.locator('#leaderboardDetail').inner_text()
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                    page.locator('.lb-group').screenshot(path=str(args.output / f'{size}-{language}-{benchmark}-results.png'))
                    if benchmark == 'harnessjevbench':
                        page.screenshot(path=str(args.output / f'{size}-{language}-harnessjevbench.png'), full_page=True)
                    # Explicit sorting releases the featured presentation, retaining real ranks.
                    table.locator('thead th').nth(2).locator('button').click()
                    assert table.get_attribute('data-sort-key') in ['accuracy', 'native']
                    assert not page.locator('.lb-featured-note').is_visible()
                    scores = rows.locator('td[data-metric]').evaluate_all('(ns)=>ns.filter(n=>n.dataset.metric==="accuracy"||n.dataset.metric==="native").map(n=>n.dataset.sortValue)')
                    present = [float(v) for v in scores if v != '']
                    assert present == sorted(present, reverse=True)
                    if benchmark == 'harnessjevbench':
                        assert rows.first.get_attribute('data-result-model') == 'access-vllm-sr--d3'
                    own_filter = page.locator('#leaderboardDetail [data-table-own]')
                    own_filter.click()
                    assert table.locator('tbody tr:visible').count() == 3
                    own_filter.click()
                    checks.append({'size': size, 'language': language, 'benchmark': benchmark, 'models': 11})
                page.close()
        browser.close()
    report = {'checks': checks, 'page_and_console_errors': errors, 'model_requests': model_requests}
    (args.output / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    assert not errors, errors
    assert not model_requests, model_requests
    print(f'{len(checks)} bilingual desktop/mobile views passed; no model requests or console errors.')


if __name__ == '__main__':
    main()
