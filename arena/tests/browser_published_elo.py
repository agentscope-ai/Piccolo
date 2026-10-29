"""Read-only acceptance of the original seven-column Elo ladder."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    base = args.url.rstrip('/')
    data = json.load(urlopen(base+'/api/elo', timeout=30))
    assert data['schema_version'] == 'jev.arena.published-elo.v1'
    headings = {'en': ['#', 'Participant', 'Elo', 'Coverage / W–D–L', 'Agreement', 'Probability stability', 'Variance'],
                'zh': ['#', '参赛者', 'Elo', '覆盖 / 胜–平–负', '三次一致率', '概率稳定度', '方差']}
    findings = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size, viewport in [('desktop', {'width': 1440, 'height': 1000}),
                               ('mobile', {'width': 390, 'height': 844})]:
            page = browser.new_page(viewport=viewport); errors = []; archives = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: archives.append(r.url) if 'visible-control.js' in r.url else None)
            page.goto(base, wait_until='domcontentloaded')
            page.locator('[data-tab="leaderboard"]').click()
            page.locator('[data-benchmark="gamejevbench"]').click()
            page.wait_for_selector('#eloRows [data-result-model]')
            page.wait_for_function('document.querySelectorAll(".lb-radar-axis").length===22')
            for language in ('en', 'zh'):
                page.locator(f'[data-language="{language}"]').click()
                page.locator('#eloScope').select_option('overall')
                titles = page.locator('#gameEloPanel .elo-table thead th').evaluate_all('(cells)=>cells.map(c=>c.querySelector(".lb-sort-label")?.firstChild?.textContent||c.textContent)')
                assert titles == headings[language], titles
                assert page.locator('#eloTitle').inner_text() == ('Ladder' if language == 'en' else '天梯榜')
                assert page.locator('#eloRows [data-result-model]').count() == 10
                assert page.locator('.lb-radar-axis').count() == 22
                page.locator('#lbRadarDimension').select_option('-1')
                assert 'Elo' in page.locator('.lb-bar-metric').inner_text()
                for row in data['overall']:
                    bar = page.locator(f'[data-bar-model="{row["id"]}"]')
                    score = bar.get_attribute('data-bar-score')
                    assert (score == '') if row.get('status') == 'pending' else abs(float(score)-row['rating']) < 1e-6
                for scope, table in [('overall', data['overall']), *data['by_game'].items()]:
                    page.locator('#eloScope').select_option(scope)
                    assert page.locator('#eloRows [data-result-model]').count() == 10
                    for row in table:
                        cells = page.locator(f'#eloRows [data-result-model="{row["id"]}"] td')
                        assert cells.count() == 7
                        if row.get('status') == 'pending':
                            assert [cells.nth(i).inner_text() for i in (0, 2, 3, 4, 5, 6)] == ['—']*6
                        else:
                            assert cells.nth(2).inner_text() == f'{row["rating"]:.1f}'
                            if scope in ('mario_platformer', 'terraria_survival', 'snake_navigation', 'tetris_placement'):
                                assert [cells.nth(i).inner_text() for i in (4, 5, 6)] == ['—']*3
                page.locator('#eloScope').select_option('overall')
                # Frozen Elo refreshes must preserve a selected game.
                page.locator('#eloScope').select_option('chess')
                page.locator('#eloRefresh').click()
                page.wait_for_function('!document.getElementById("eloRefresh").disabled')
                assert page.locator('#eloScope').input_value() == 'chess'
                page.locator('#eloScope').select_option('overall')
                # This cohort has no published replay bundle; never load a
                # historical tournament's large archive into the new ladder.
                page.locator('#eloMatchHistory').evaluate('(node)=>{node.open=true}')
                assert not archives, archives
                dims = page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                assert dims['scroll'] <= dims['client']+1, dims
                assert not errors, errors
                page.evaluate('document.fonts.ready')
                page.screenshot(path=str(args.out/f'{size}-{language}.png'), full_page=True)
                findings.append({'size': size, 'language': language, 'columns': headings[language],
                                 'game_views': 23, 'model_rows': 10,
                                 'oneshot_blank': any(r.get('status') == 'pending' for r in data['overall'] if r['name'] == 'Piccolo'),
                                 'page_errors': 0, 'overflow': False, 'stale_replay_requests': 0})
            page.close()
        browser.close()
    (args.out/'validation.json').write_text(json.dumps({'url': base, 'checks': findings}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': len(findings), 'views': len(findings)*23, 'columns': 7,
                      'oneshot_blank': findings[0]['oneshot_blank']}))


if __name__ == '__main__':
    main()
