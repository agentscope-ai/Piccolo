#!/usr/bin/env python3
"""Check publication typography, stable page reveals and prefixed model logos.

Only opens public pages and manual game sessions; never requests model decisions.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


RETIRED_DECORATIONS = (
    '#fsSandCanvas,#lbPixelAtmosphere,#lbPixelEffects,'
    '.nav-glass,.nav-wind-light,.nav-underline,.fs-type-scramble,.fs-type-running'
)
SETTLED = """() => ['sitePageContent','leaderboardDetail'].every(id=>{
 const n=document.getElementById(id);if(!n)return true;
 return !n.getAnimations().some(a=>a.playState==='running') &&
   getComputedStyle(n).opacity==='1' && n.style.opacity==='' && n.style.color==='';
})"""
HEADINGS = [
    ('games', '.playground-heading h2', '#playCount'),
    ('leaderboard', '.lb-heading h2', '#leaderboardStatus'),
    ('blog', '#blogTitle', '.home-description'),
]


def rgb(value):
    return tuple(int(channel) for channel in re.findall(r'\d+', value)[:3])


def assert_theme(page):
    theme = page.evaluate("""() => {
      const body=getComputedStyle(document.body),nav=getComputedStyle(document.querySelector('.tabs'));
      return {background:body.backgroundColor,image:body.backgroundImage,text:body.color,
        bodyFont:body.fontFamily,accent:getComputedStyle(document.querySelector('.tabs .active'),'::after').backgroundColor,
        navShadow:nav.boxShadow,navBlur:nav.backdropFilter,
        headings:[...document.querySelectorAll('#blogTitle,#blogTitle span,.lb-heading h2,.playground-heading h2')].map(n=>getComputedStyle(n).fontFamily),
        prose:getComputedStyle(document.querySelector('.home-description')).fontFamily};
    }""")
    r, g, b = rgb(theme['background'])
    assert 235 <= r <= 255 and 230 <= g <= r and 220 <= b < g, theme
    assert theme['image'] == 'none', theme
    assert max(rgb(theme['text'])) < 80, theme
    r, g, b = rgb(theme['accent'])
    assert 120 <= r <= 200 and r > g + 30 and g > b + 10, theme
    assert theme['navShadow'] == 'none' and theme['navBlur'] == 'none', theme
    assert theme['bodyFont'].startswith('Inter') and theme['prose'].startswith('Inter'), theme
    assert all(any(face in font for face in ['Georgia', 'Iowan Old Style', 'Songti SC'])
               and not font.startswith('Inter') for font in theme['headings']), theme
    assert page.locator(RETIRED_DECORATIONS).count() == 0
    assert page.locator('script[src*="leaderboard-effects.js"]').count() == 0
    return theme


def assert_brand(page, language):
    assert page.locator('.brand strong').inner_text() == 'Piccolo'
    assert page.locator('.brand .eyebrow').text_content().strip() == 'Decision Intelligence'
    assert page.locator('[data-tab="blog"]').inner_text() == ('首页' if language == 'zh' else 'Home')
    assert page.locator('[data-tab="leaderboard"]').inner_text() == 'Leaderboard'
    assert page.locator('[data-tab="games"]').inner_text() == 'Playground'
    assert page.locator('.brand strong').evaluate("""n=>getComputedStyle(n).opacity==='1' &&
      getComputedStyle(n).color!=='rgba(0, 0, 0, 0)' && !n.getAnimations().length""")
    assert page.locator('.tabs .tab>span').evaluate_all("""nodes=>nodes.every(n=>
      getComputedStyle(n).opacity==='1' && !n.getAnimations().length)""")


def heading_snapshot(page, title, subtitle):
    return page.evaluate("""selectors=>selectors.map(selector=>{
      const n=document.querySelector(selector),r=n.getBoundingClientRect(),style=getComputedStyle(n);
      return {text:n.textContent.trim(),rect:[r.x,r.y,r.width,r.height],color:style.color};
    })""", [title, subtitle])


def assert_no_heading_shift(before, after, label):
    for first, last in zip(before, after):
        assert first['text'] and first['text'] == last['text'], (label, before, after)
        assert all(abs(a-b) < .6 for a, b in zip(first['rect'], last['rect'])), (label, before, after)
        assert first['rect'][2] > 0 and first['rect'][3] > 0, (label, before)
        assert last['color'] != 'rgba(0, 0, 0, 0)', (label, after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080/')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width':1440, 'height':1000})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        page.wait_for_function(SETTLED, timeout=2000)
        theme = assert_theme(page)
        page.screenshot(path=str(args.output/'publication-home.png'))
        report.append({'publication_theme':theme, 'retired_decorations_absent':True})
        for language in ['en', 'zh']:
            page.locator(f'[data-language="{language}"]').click()
            assert_brand(page, language)
            for view, title, subtitle in HEADINGS:
                page.locator(f'[data-tab="{view}"]').click()
                page.locator(title).wait_for(state='visible')
                if view == 'leaderboard':
                    # The first entry fetches the snapshot; do not confuse its real
                    # timestamp update with a layout change caused by the reveal.
                    page.wait_for_selector('.lb-radar-heading')
                page.wait_for_function("""selector=>!!document.querySelector(selector)?.textContent.trim()""", arg=subtitle)
                before = heading_snapshot(page, title, subtitle)
                animation = page.evaluate("""() => ['sitePageContent','leaderboardDetail'].flatMap(id=>
                  (document.getElementById(id)?.getAnimations()||[]).map(a=>({
                    duration:a.effect.getTiming().duration,frames:a.effect.getKeyframes()
                  })))""")
                for reveal in animation:
                    assert reveal['duration'] <= 220, reveal
                    assert all('opacity' in frame and 'transform' not in frame
                               for frame in reveal['frames']), reveal
                page.wait_for_function(SETTLED, timeout=2000)
                assert_no_heading_shift(before, heading_snapshot(page, title, subtitle), (view, language))
                assert_brand(page, language)
                assert page.locator(RETIRED_DECORATIONS).count() == 0
                page.screenshot(path=str(args.output/f'{view}-{language}-publication.png'))
                report.append({'view':view, 'language':language, 'serif_heading':True,
                               'no_layout_shift':True, 'brand_stable':True, 'opacity_only_reveal':True})
        # Unpublished research notes stay off the public Home page.
        assert page.locator('.home-research,.blog-report').count() == 0
        assert page.locator('.brand .logo img').evaluate('n=>n.complete&&n.naturalWidth>0')
        assert page.locator('.brand strong').evaluate('n=>getComputedStyle(n).fontFamily').startswith('Inter')
        # Rapid switches must settle on the final page without leaving hidden text.
        page.evaluate("""async()=>{for(const view of ['leaderboard','blog','games','blog','leaderboard']){
          document.querySelector('[data-tab="'+view+'"]').click();
          await new Promise(resolve=>setTimeout(resolve,35));}}""")
        page.wait_for_function(SETTLED, timeout=2000)
        assert page.locator('.tabs [aria-selected="true"]').get_attribute('data-tab') == 'leaderboard'
        assert page.locator('#leaderboardView').is_visible()
        assert not page.locator('#blogView').is_visible()
        # A live accessibility-preference change cancels a reveal and suppresses the next one.
        page.locator('[data-tab="blog"]').click()
        page.emulate_media(reduced_motion='reduce')
        page.wait_for_function(SETTLED, timeout=1000)
        page.locator('[data-tab="leaderboard"]').click()
        page.wait_for_timeout(60)
        assert page.evaluate(SETTLED)
        assert page.locator('#sitePageContent,#leaderboardDetail').evaluate_all('(nodes)=>nodes.every(n=>!n.getAnimations().length)')
        assert page.locator('.tabs .active').evaluate('(n)=>getComputedStyle(n,"::after").transitionDuration') == '0s'
        page.emulate_media(reduced_motion='no-preference')
        page.locator('[data-tab="blog"]').click()
        page.set_viewport_size({'width':1280, 'height':900})
        page.wait_for_function(SETTLED, timeout=1000)
        assert page.locator(RETIRED_DECORATIONS).count() == 0
        report.append({'unpublished_notes_removed':True, 'rapid_switch':True,
                       'reduced_motion':True, 'resize_cleanup':True})
        context.close()

        # Mimic a reverse proxy stripping its mount prefix: asset URLs must retain it.
        prefix = 'dsw-434426/ide/proxy/8080/'
        page = browser.new_page(viewport={'width':1440, 'height':1000}, reduced_motion='reduce')
        page.on('pageerror', lambda error: errors.append(str(error)))

        def proxy(route):
            path = route.request.url.split('/'+prefix, 1)[1]
            route.fulfill(response=route.fetch(url=urljoin(args.url, path)))

        page.route('**/'+prefix+'**', proxy)
        page.goto(urljoin(args.url, prefix), wait_until='networkidle')
        page.locator('[data-tab="leaderboard"]').click()
        for benchmark in ['jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench', 'gamejevbench']:
            page.locator(f'#leaderboardTabs [data-benchmark="{benchmark}"]').click()
            page.wait_for_selector('.lb-radar-svg')
            page.wait_for_function("""() => {
              const logos=[...document.querySelectorAll('.lb-model-logo')].filter(n=>n.getClientRects().length);
              return logos.length>0 && logos.every(n=>n.complete && n.naturalWidth>0);
            }""", timeout=10000)
            logos = page.locator('.lb-model-logo').evaluate_all("""nodes=>nodes.filter(n=>n.getClientRects().length)
              .map(n=>({url:n.src,loaded:n.complete&&n.naturalWidth>0}))""")
            assert logos and all(logo['loaded'] and prefix in logo['url'] for logo in logos), (benchmark, logos)
            report.append({'benchmark':benchmark, 'prefixed_logos_loaded':len(logos)})
        for model in ['Qwen3.8 Max', 'Qwen3.6']:
            rows = page.locator('.elo-table tbody tr').filter(has_text=model)
            assert rows.count() > 0, model
            for row in rows.all():
                logo = row.locator('.lb-model-logo')
                assert logo.count() > 0, model
                assert logo.first.get_attribute('src').endswith('/qwen.png'), model
        page.close()
        browser.close()
    assert not errors, errors
    (args.output/'publication-theme-report.json').write_text(
        json.dumps({'checks':report, 'errors':errors}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'checks':len(report), 'errors':errors}))


if __name__ == '__main__':
    main()
