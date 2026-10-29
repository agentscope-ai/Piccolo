#!/usr/bin/env python3
"""Read-only browser checks for imported tables and bilingual radar charts.

Run against a local PiccoloArena service. This does not connect a model or start an
evaluation. Screenshots are written to the ignored var/browser directory.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

BENCHMARKS = {'gamejevbench': 21, 'jevbench': 18, 'decisionindex': 5, 'harnessjevbench': 31, 'datajevbench': 6}
HAN = re.compile(r'[\u3400-\u9fff]')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8092/')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'var' / 'browser')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = []
    failures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        for size, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            page.goto(args.url, wait_until='domcontentloaded')
            assert page.locator('.brand strong').inner_text() == 'Piccolo'
            assert page.locator('.tabs .tab').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.tab)') == ['blog','leaderboard','games']
            assert page.locator('#blogView').is_visible()
            assert page.locator('[data-tab="games"]').inner_text() == 'Playground'
            projection = page.request.get(urljoin(args.url.rstrip('/')+'/', 'api/leaderboard')).json()
            timestamps = {row['id']:row.get('updated_at', '') for row in projection['benchmarks']}
            expected_rows = {}
            for benchmark in BENCHMARKS:
                if benchmark == 'gamejevbench': continue
                response = page.request.get(urljoin(args.url.rstrip('/')+'/', 'api/v1/leaderboards/'+benchmark))
                assert response.ok, benchmark
                expected_rows[benchmark] = {row['model_id']: row for row in response.json()['rows']}
            page.locator('[data-tab="leaderboard"]').click()
            page.wait_for_selector('.lb-radar-svg .lb-radar-axis')
            chart_sizes = {}
            model_colors = {}
            for language in ['en', 'zh']:
                page.locator(f'[data-language="{language}"]').click()
                for benchmark, dimension_count in BENCHMARKS.items():
                    if benchmark != 'gamejevbench':
                        dimension_count = len({axis['id'] for row in expected_rows[benchmark].values() for axis in row.get('axes', [])})
                    page.locator(f'[data-benchmark="{benchmark}"]').click()
                    page.wait_for_function('expected => document.querySelectorAll(".lb-radar-axis").length === expected', arg=dimension_count if dimension_count >= 3 else 0)
                    page.evaluate('document.fonts.ready')
                    assert page.locator('#leaderboardStatus').get_attribute('data-updated-at') == timestamps[benchmark]
                    labels = page.locator('.lb-radar-axis').evaluate_all('(nodes) => nodes.map(n => [...n.querySelectorAll("tspan")].map(t => t.textContent).join(" "))')
                    dense = dimension_count > 24
                    semantic_labels = labels
                    assert len(labels) == dimension_count and all(label.strip() for label in labels)
                    if dense:
                        assert page.locator('.lb-axis-key').count() == 0, 'Names must be on the radar itself'
                        axis = page.locator('.lb-radar-axis').nth(dimension_count - 1)
                        axis.click()
                        assert page.locator('#lbRadarDimension').input_value() == str(dimension_count - 1)
                    if language == 'zh' and benchmark!='datajevbench' and not all(HAN.search(label) or label == '2048' for label in semantic_labels):
                        failures.append(f'{size}/{language}/{benchmark}: missing Chinese radar label')
                    if language == 'en' and any(HAN.search(label) for label in semantic_labels):
                        failures.append(f'{size}/{language}/{benchmark}: Chinese text remains in English radar')
                    if any(re.fullmatch(r'\s*\d+\s*', label) and label != '2048' for label in labels):
                        failures.append(f'{size}/{language}/{benchmark}: numeric placeholder axis')
                    dimensions = page.evaluate('({client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})')
                    if dimensions['scroll'] > dimensions['client'] + 1:
                        failures.append(f'{size}/{language}/{benchmark}: page overflow {dimensions}')
                    headers=page.locator('#leaderboardView .lb-table:visible thead th').all_text_contents()
                    assert not any(h.strip() in {'Errors','Record','Failures','错误','记录','失败数','失败'} for h in headers),headers
                    assert 'QwenJev' not in page.locator('#leaderboardView').inner_text()
                    if benchmark != 'gamejevbench':
                        rows = page.locator('.lb-metrics-table tbody tr[data-result-model]')
                        expected = expected_rows[benchmark]
                        rendered_ids = rows.evaluate_all('(nodes) => nodes.map(n => n.dataset.resultModel)')
                        if len(rendered_ids) != len(expected) or set(rendered_ids) != set(expected):
                            failures.append(f'{size}/{language}/{benchmark}: imported model rows differ from the current data')
                        for index, ident in enumerate(rendered_ids):
                            if ident not in expected: continue
                            metrics = expected[ident]['metrics']
                            for metric in ['accuracy', 'brier', 'ece']:
                                value = metrics.get(metric, metrics.get('acc') if metric == 'accuracy' else None)
                                if benchmark=='harnessjevbench' and metric=='accuracy':value=metrics.get('strict_task_accuracy',value)
                                cell = rows.nth(index).locator(f'[data-metric="{metric}"]')
                                if cell.count() != 1 or (cell.text_content().strip() == '—') != (value is None):
                                    failures.append(f'{size}/{language}/{benchmark}: {ident} {metric} missing-value display differs from data')
                                elif value is not None:
                                    expected_text=f'{100*value:.2f}%' if metric=='accuracy' else f'{value:.4f}'
                                    if cell.text_content().strip()!=expected_text:
                                        failures.append(f'{size}/{language}/{benchmark}: {ident} {metric} value differs from data')
                        if size == 'mobile':
                            scroll = page.locator('.lb-table-scroll').last
                            reachable = scroll.evaluate('node => { node.scrollLeft = node.scrollWidth; const max=node.scrollWidth-node.clientWidth; const ok=Math.abs(node.scrollLeft-max)<2; node.scrollLeft=0; return ok; }')
                            if not reachable:
                                failures.append(f'{size}/{language}/{benchmark}: metric columns cannot be scrolled into view')
                    chart = page.locator('.lb-radar-svg')
                    if dimension_count >= 3:
                        if chart.count() != 1 or chart.get_attribute('viewBox') != '0 0 820 780':
                            failures.append(f'{size}/{language}/{benchmark}: inconsistent radar geometry')
                    elif chart.count() or not page.locator('#leaderboardRadar .lb-radar-empty').first.is_visible():
                        failures.append(f'{size}/{language}/{benchmark}: missing dimensions must display an explicit empty state')
                    if dimension_count >= 3:
                        assert page.locator('.lb-comparison-grid > .lb-chart-card').count() == 2
                        boxes = page.locator('.lb-comparison-grid > .lb-chart-card').evaluate_all('(nodes)=>nodes.map(n=>({x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y}))')
                        assert (abs(boxes[0]['y']-boxes[1]['y']) < 2) if size == 'desktop' else (boxes[1]['y'] > boxes[0]['y'])
                        page.locator('.lb-model-picker').evaluate('(node)=>node.open=true')
                        # Exercise the actual picker and chart instead of screenshot-only validation.
                        assert page.locator('[data-radar-zoom]').count() == 0
                        initial_ids = page.locator('[data-radar-model]:checked').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.radarModel)')
                        all_ids = page.locator('[data-radar-model]:not(:disabled)').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.radarModel)')
                        assert set(initial_ids) == set(all_ids), 'Every model is selected by default'
                        if benchmark != 'gamejevbench': assert set(initial_ids) == set(expected_rows[benchmark])
                        assert page.locator('.lb-radar-count').count() == 0
                        geometry = page.locator('.lb-radar-chart,#lbBarChart').evaluate_all('(nodes)=>nodes.map(n=>({width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height}))')
                        if not chart_sizes: chart_sizes = geometry
                        for current, reference in zip(geometry, chart_sizes):
                            assert abs(current['height']-reference['height']) < 1 and abs(current['width']-reference['width']) < 1, (benchmark, geometry, chart_sizes)
                        assert abs(geometry[0]['height']-geometry[1]['height']) < 1
                        if size == 'desktop': assert abs(geometry[0]['width']-geometry[1]['width']) < 1
                        colors = page.locator('.lb-radar-legend-row').evaluate_all('(nodes)=>nodes.map(n=>({id:n.querySelector("input").dataset.radarModel,color:getComputedStyle(n.querySelector(".lb-radar-swatch")).backgroundColor}))')
                        for item in colors:
                            if item['id'] in model_colors: assert model_colors[item['id']] == item['color'], 'Model accents must stay consistent across benchmarks'
                            model_colors[item['id']] = item['color']
                        last = page.locator('[data-radar-model]').last
                        last.uncheck()
                        assert page.locator('[data-radar-model]:checked').count() == len(all_ids)-1
                        page.locator('[data-radar-model]').last.check()
                        assert page.locator('[data-radar-model]:checked').count() == len(all_ids)
                        search = page.locator('#lbRadarSearch')
                        search.fill('__not_a_model__')
                        assert page.locator('.lb-radar-legend-row:visible').count() == 0
                        assert page.locator('.lb-legend-no-match').is_visible()
                        search.fill('')
                        page.locator('[data-radar-selection="all"]').click()
                        assert page.locator('[data-radar-model]:checked').count() == len(all_ids)
                        assert page.locator('.lb-radar-legend').evaluate('(node)=>node.clientHeight') <= 260
                        assert page.locator('.lb-radar-inspect').evaluate('(node)=>node.clientHeight') <= 320
                        if len(all_ids) > 6: assert page.locator('.lb-radar-many').count() == 1
                        assert page.locator('[data-radar-model]:disabled').count() == 0
                        page.locator('[data-radar-selection="none"]').click()
                        assert page.locator('[data-radar-model]:checked').count() == 0
                        assert page.locator('.lb-radar-empty').is_visible()
                        page.locator('[data-radar-only]').first.click()
                        assert page.locator('[data-radar-model]:checked').count() == 1
                        assert page.evaluate('document.activeElement.hasAttribute("data-radar-only")')
                        page.locator('[data-radar-selection="default"]').click()
                        assert set(page.locator('[data-radar-model]:checked').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.radarModel)')) == set(initial_ids)
                        page.locator('#lbRadarDimension').select_option('-1')
                        assert page.locator('.lb-bar-row').count() == len(initial_ids)
                        if benchmark != 'gamejevbench':
                            for row in page.locator('.lb-bar-row').all():
                                expected_score = expected_rows[benchmark][row.get_attribute('data-bar-model')]['score']
                                actual = row.get_attribute('data-bar-score')
                                if expected_score is None:
                                    assert actual == '' and row.locator('.lb-bar-track > span').count() == 0
                                else:
                                    assert abs(float(actual) - expected_score * (1 if benchmark == 'decisionindex' else 100)) < 1e-8
                        assert page.locator('.lb-bar-rank').count() == 0
                        assert page.locator('.lb-bar-track').first.evaluate('(node)=>node.offsetHeight') <= 30
                        assert page.locator('.lb-selected-models').count() == 0, 'Bars replace the duplicate legend'
                        if benchmark != 'gamejevbench':
                            for bar in page.locator('.lb-bar-row').all():
                                source = expected_rows[benchmark][bar.get_attribute('data-bar-model')]
                                if source.get('logo') and source['score'] and source['score'] > 0:
                                    icon = bar.locator('.lb-bar-fill .lb-model-logo')
                                    assert icon.count() == 1
                                    assert icon.evaluate('(node)=>node.complete && node.naturalWidth > 0'), 'Configured logo must actually load inside the bar'
                                    assert bar.locator('.lb-bar-fill .lb-bar-name').inner_text().strip()
                        page.keyboard.press('Escape')
                        assert not page.locator('.lb-model-picker').evaluate('(node)=>node.open')
                        if page.locator('.lb-radar-series').count():
                            bar = page.locator('.lb-bar-track').first
                            ident = bar.locator('..').get_attribute('data-bar-model')
                            axis_before = page.locator('#lbRadarDimension').input_value()
                            bar.hover()
                            assert page.locator('#leaderboardRadar').evaluate('(node)=>node.classList.contains("has-highlight")')
                            assert page.locator('#lbRadarDimension').input_value() == axis_before
                            bar.focus(); page.keyboard.press('Enter')
                            assert bar.get_attribute('aria-pressed') == 'true'
                            page.locator('#lbRadarDimension').select_option('0')
                            assert page.locator('.lb-bar-track[aria-pressed="true"]').count() == 1
                            assert page.locator('.lb-bar-row.is-highlighted').count() == 1
                            page.locator('.lb-bar-track[aria-pressed="true"]').focus(); page.keyboard.press('Escape')
                            page.mouse.move(1,1)
                            page.locator('#lbRadarDimension').focus()
                            page.locator('#lbRadarDimension').select_option('-1')
                            assert not page.locator('#leaderboardRadar').evaluate('(node)=>node.classList.contains("has-highlight")')
                        page.locator('.lb-model-picker').evaluate('(node)=>node.open=false')
                    if benchmark != 'gamejevbench':
                        tools = page.locator('#leaderboardDetail .lb-table-tools')
                        tools.locator('input').fill('__not_a_model__')
                        assert page.locator('.lb-metrics-table tbody tr:visible').count() == 0
                        tools.locator('input').fill('')
                        tools.locator('[data-table-own]').click()
                        assert page.locator('.lb-metrics-table tbody tr:visible').count() == len([key for key in expected if key in {'oneshot27b-control-reviewed-sft-iter310', 'oneshot27b-gameplay-terminal-rl4', 'oneshot27b-game-rl-native-iter17'}])
                        tools.locator('[data-table-own]').click()
                        page.locator('.lb-metrics-table thead th[data-metric-help]').first.hover()
                        assert page.locator('#lbMetricTooltip').is_visible()
                        assert page.locator('#lbMetricTooltip').inner_text().strip()
                        page.keyboard.press('Escape')
                        assert not page.locator('#lbMetricTooltip').is_visible()
                    assert page.locator('.lb-metrics-table .lb-rank:visible').count() == 0
                    if benchmark == 'jevbench':
                        model = page.locator('[data-result-model="access-openai--gpt-6-luna-decisions"] .lb-model-name')
                        if model.count(): assert model.inner_text().strip() == expected_rows[benchmark]['access-openai--gpt-6-luna-decisions']['model_name']
                    page.screenshot(animations='disabled', path=str(args.output / f'leaderboard-{size}-{language}-{benchmark}.png'), full_page=True)
                    report.append({'viewport': size, 'language': language, 'benchmark': benchmark,
                                   'axes': len(labels), 'labels': labels, 'page_width': dimensions})
            failures.extend(f'{size}: {error}' for error in errors)
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('#lbPixelAtmosphere i').first.evaluate('(node)=>getComputedStyle(node).animationName') == 'none'
            page.locator('[data-tab="blog"]').click()
            assert page.locator('#blogView').is_visible()
            assert not page.locator('#leaderboardView').is_visible()
            page.screenshot(path=str(args.output / f'blog-{size}.png'), full_page=True)
            page.locator('[data-tab="games"]').click()
            assert page.locator('#gamesView').is_visible() and not page.locator('#blogView').is_visible()
            page.close()
        browser.close()
    (args.output / 'leaderboards-report.json').write_text(json.dumps({'checks': report, 'failures': failures}, ensure_ascii=False, indent=2) + '\n')
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)
    print(f'{len(report)} leaderboard views passed: 5 benchmark panels, radar dimensions/empty states, 4 result tables, EN/ZH, desktop/mobile; no console errors or page overflow.')


if __name__ == '__main__':
    main()
