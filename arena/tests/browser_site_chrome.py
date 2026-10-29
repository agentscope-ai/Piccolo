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
PANELS = {'blog': 'blogView', 'leaderboard': 'leaderboardView', 'games': 'gamesView'}
RETIRED_DECORATIONS = (
    '.nav-glass,.nav-wind-light,.nav-underline,'
    '#lbPixelAtmosphere,#lbPixelEffects,#fsSandCanvas,.fs-type-scramble,.fs-type-running'
)


def assert_selected_view(page, tab, label, *, focused=False):
    """Selection, visible content and keyboard focus must agree after a reveal."""
    page.wait_for_function("""tab => {
      const selected=document.querySelector('.tabs [aria-selected="true"]');
      return selected?.dataset.tab===tab &&
        !document.querySelector('#sitePageContent').getAnimations().some(a=>a.playState==='running');
    }""", arg=tab, timeout=1000)
    assert page.locator('.tabs').get_attribute('role')=='tablist'
    assert page.locator('.tabs [role="tab"][aria-selected="true"]').count()==1
    assert page.locator('.tabs [role="tab"][tabindex="0"]').count()==1
    for key, panel in PANELS.items():
        button=page.locator(f'.tabs [data-tab="{key}"]')
        assert button.get_attribute('role')=='tab'
        assert button.get_attribute('aria-controls')==panel
        assert button.get_attribute('aria-selected')==str(key==tab).lower()
        assert button.get_attribute('tabindex')==('0' if key==tab else '-1')
        assert page.locator('#'+panel).is_visible()==(key==tab),(label,tab,panel)
    assert page.locator('#sitePageContent').evaluate('(n)=>getComputedStyle(n).opacity')=='1'
    assert page.locator(RETIRED_DECORATIONS).count()==0,(label,'retired decoration returned')
    if focused:
        assert page.locator(f'.tabs [data-tab="{tab}"]').evaluate('(n)=>n===document.activeElement')


def assert_mast_layout(page, width, label):
    """Desktop navigation shares the brand row; narrow screens give it a full row."""
    assert page.locator('.mast > .tabs').count()==1
    boxes=page.locator('.mast,.mast .brand,.mast .tabs,.mast .mast-controls').evaluate_all("""nodes=>
      Object.fromEntries(nodes.map(n=>{
        const r=n.getBoundingClientRect();
        return [n.classList.contains('mast')?'mast':n.classList.contains('brand')?'brand':
          n.classList.contains('tabs')?'tabs':'controls',
          {left:r.left,right:r.right,top:r.top,bottom:r.bottom,center:(r.top+r.bottom)/2}];
      }))""")
    mast,brand,nav,controls=(boxes[key] for key in ['mast','brand','tabs','controls'])
    for child in [brand,nav,controls]:
        assert child['left']>=mast['left']-.6 and child['right']<=mast['right']+.6,(label,boxes)
        assert child['top']>=mast['top']-.6 and child['bottom']<=mast['bottom']+.6,(label,boxes)
    if width<=760:
        assert nav['top']>=max(brand['bottom'],controls['bottom'])-.6,(label,'navigation row overlaps brand',boxes)
        assert brand['right']<=controls['left']+.6,(label,'language controls overlap brand',boxes)
    else:
        assert brand['right']<=nav['left']+.6 and nav['right']<=controls['left']+.6,(label,'mast columns overlap',boxes)
        assert max(c['center'] for c in [brand,nav,controls])-min(c['center'] for c in [brand,nav,controls])<1,(label,boxes)
    rects=page.evaluate(RECTS)
    assert max(r[1] for r in rects)-min(r[1] for r in rects)<.6,(label,'tabs wrapped',rects)


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
                assert_mast_layout(page,width,label)
                baseline=page.evaluate(RECTS)
                case={'width':width,'language':language,'views':[]}
                for tab in ['blog','leaderboard','games']:
                    page.locator(f'[data-tab="{tab}"]').click()
                    # Check stable hit targets through the 180 ms reveal, plus one frame.
                    for delay in [0,80,120]:
                        page.wait_for_timeout(delay)
                        actual=page.evaluate(RECTS)
                        assert all(abs(x-y)<.6 for a,b in zip(baseline,actual) for x,y in zip(a,b)),(label,tab,'navigation moved',baseline,actual)
                    assert_selected_view(page,tab,label)
                    layout=page.evaluate('({viewport:document.documentElement.clientWidth,content:document.documentElement.scrollWidth})')
                    if layout['content']>layout['viewport']+1:failures.append([label,tab,'page overflow',layout])
                    case['views'].append(tab)
                # Interrupt several transitions; geometry and selection must settle correctly.
                page.evaluate("""async()=>{for(const id of ['blog','games','leaderboard','blog','leaderboard']){
                    document.querySelector('[data-tab="'+id+'"]').click();await new Promise(r=>setTimeout(r,35));}}""")
                page.wait_for_timeout(200)
                assert_selected_view(page,'leaderboard',label)
                actual=page.evaluate(RECTS)
                assert all(abs(x-y)<.6 for a,b in zip(baseline,actual) for x,y in zip(a,b)),(label,'rapid switches moved navigation')
                page.locator('.tabs .active').focus()
                scroll=page.evaluate('window.scrollY')
                for key,tab in [('End','games'),('Home','blog'),('ArrowLeft','games'),('ArrowRight','blog'),('ArrowRight','leaderboard')]:
                    page.keyboard.press(key)
                    assert_selected_view(page,tab,label,focused=True)
                    assert abs(page.evaluate('window.scrollY')-scroll)<1,(label,key,'keyboard navigation scrolled the page')
                page.locator('#leaderboardTabs [data-benchmark="jevbench"]').click()
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
                assert_selected_view(page,'blog',label)
                assert page.locator('#sitePageContent,#leaderboardDetail').evaluate_all('(nodes)=>nodes.every(n=>!n.getAnimations().length)')
                assert page.locator('.tabs .active').evaluate('(n)=>getComputedStyle(n,"::after").transitionDuration')=='0s'
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
