#!/usr/bin/env python3
"""Exercise shared navigation, motion, overlays and responsive layout locally.

Creates only manual game sessions. Never connects a model or starts evaluation.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

RECTS = """() => [...document.querySelectorAll('.tabs .tab')].map(n=>{
 const r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];})"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:37535/')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    checks=[];failures=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        for width in [320,390,768,1440,1920]:
            for language in ['en','zh']:
                label=f'{width}-{language}';errors=[]
                page=browser.new_page(viewport={'width':width,'height':1000})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(args.url,wait_until='networkidle')
                page.locator(f'[data-language="{language}"]').click()
                page.evaluate('document.fonts.ready')
                page.evaluate('window.scrollTo(0,0)')
                baseline=page.evaluate(RECTS)
                case={'width':width,'language':language,'views':[]}
                for tab in ['blog','leaderboard','games']:
                    page.locator(f'[data-tab="{tab}"]').click()
                    # Measure hit targets at animation start, mid-flight and end.
                    for delay in [0,80,400]:
                        page.wait_for_timeout(delay)
                        actual=page.evaluate(RECTS)
                        assert all(abs(x-y)<.6 for a,b in zip(baseline,actual) for x,y in zip(a,b)),(label,tab,'navigation moved',baseline,actual)
                    layout=page.evaluate('({viewport:document.documentElement.clientWidth,content:document.documentElement.scrollWidth})')
                    if layout['content']>layout['viewport']+1:failures.append([label,tab,'page overflow',layout])
                    case['views'].append(tab)
                # Interrupt several transitions; geometry and selection must settle correctly.
                page.evaluate("""async()=>{for(const id of ['blog','games','leaderboard','blog','leaderboard']){
                    document.querySelector('[data-tab="'+id+'"]').click();await new Promise(r=>setTimeout(r,35));}}""")
                page.wait_for_timeout(450)
                assert page.locator('#leaderboardView').is_visible()
                alignment=page.evaluate("""()=>{const a=document.querySelector('.tabs .active').getBoundingClientRect(),b=document.querySelector('.nav-glass').getBoundingClientRect();return ['x','y','width','height'].map(k=>Math.abs(a[k]-b[k]));}""")
                assert max(alignment)<.6,(label,'indicator failed to settle',alignment)
                assert page.locator('.tabs [role="tab"][tabindex="0"]').count()==1
                page.locator('.tabs .active').focus();page.keyboard.press('End');page.wait_for_timeout(60)
                assert page.locator('#gamesView').is_visible()
                page.keyboard.press('Home');page.wait_for_timeout(60)
                assert page.locator('#blogView').is_visible()
                page.locator('[data-tab="leaderboard"]').click()
                page.locator('[data-benchmark="jevbench"]').click()
                page.wait_for_selector('.lb-comparison-grid');page.wait_for_timeout(100)
                chart=page.locator('.lb-comparison-grid').bounding_box()
                picker=page.locator('.lb-model-picker')
                picker.locator('summary').click()
                box=page.locator('.lb-model-picker-body').bounding_box()
                assert box['x']>=0 and box['x']+box['width']<=width,(label,'chooser clipped',box)
                after=page.locator('.lb-comparison-grid').bounding_box()
                assert all(abs(chart[k]-after[k])<.6 for k in chart),(label,'chooser shifted chart')
                page.keyboard.press('Escape')
                assert not picker.evaluate('(n)=>n.open')
                assert picker.locator('summary').evaluate('(n)=>n===document.activeElement')
                picker.locator('summary').click();page.locator('.lb-heading h2').click()
                assert not picker.evaluate('(n)=>n.open')
                if width<=390:
                    row=page.locator('.lb-metrics-table tbody tr').first
                    primary=row.locator('td').nth(2).bounding_box()
                    assert primary['x']+primary['width']<=width,(label,'primary score initially hidden',primary)
                page.locator('[data-tab="games"]').click()
                before=page.evaluate(RECTS);page.locator('#connectionSettings').click()
                after=page.evaluate(RECTS)
                assert all(abs(x-y)<.6 for a,b in zip(before,after) for x,y in zip(a,b)),(label,'modal moved header')
                page.keyboard.press('Escape');assert not page.locator('.connection-dialog').is_visible()
                # CSS and WAAPI both honor live changes to reduced-motion preference.
                page.emulate_media(reduced_motion='reduce')
                page.locator('[data-tab="blog"]').click();page.wait_for_timeout(60)
                assert page.locator('#blogView').evaluate('(n)=>n.getAnimations().length')==0
                assert page.locator('.nav-glass').evaluate('(n)=>getComputedStyle(n).transitionDuration')=='0s'
                assert page.locator('#lbPixelAtmosphere i').first.evaluate('(n)=>getComputedStyle(n).animationName')=='none'
                assert page.locator('.brand').evaluate('(n)=>getComputedStyle(n).fontFamily').startswith('Inter')
                assert page.evaluate('document.fonts.check("14px Inter")')
                if errors:failures.extend([[label,e] for e in errors])
                page.screenshot(path=str(args.output/f'chrome-{label}.png'),full_page=True)
                checks.append(case);page.close()
        browser.close()
    (args.output/'site-chrome-report.json').write_text(json.dumps({'checks':checks,'failures':failures},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'failures':failures},ensure_ascii=False))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
