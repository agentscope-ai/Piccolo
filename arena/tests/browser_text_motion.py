#!/usr/bin/env python3
"""Check text-dust lifecycle and path-prefixed logos without model requests."""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


PIXELS = """() => {
 const c=document.getElementById('fsSandCanvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
 let count=0;for(let i=3;i<d.length;i+=4)if(d[i])count++;
 return {pixels:count,active:Number(c.dataset.active),pointer:getComputedStyle(c).pointerEvents};
}"""
RESTORED = """() => !document.querySelector('.fs-type-scramble,.fs-type-running') && [...document.querySelectorAll('#sitePageContent,#blogTitle,.blog-heading p,.playground-heading h2,#playCount,.lb-heading h2,#leaderboardStatus,.fs-type-text,.fs-intro-text,.tabs .tab>span,#blogView,#leaderboardView,#gamesView,.blog-reports,.blog-signal,.playground-connections,.play-library-tools,#gamePicker,#leaderboardRefresh,#leaderboardTabs,#leaderboardDetail,#gameEloPanel')].every(n=>n.style.opacity===''&&n.style.color==='')"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8080/')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    report=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(args.output/'video'),record_video_size={'width':1440,'height':1000})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url,wait_until='domcontentloaded');page.wait_for_timeout(200)
        initial=page.evaluate(PIXELS);assert initial['active']>0 and initial['pixels']>100,initial
        assert initial['pointer']=='none'
        brand=page.locator('.brand strong')
        assert brand.inner_text()=='Blink'
        page.locator('[data-language="zh"]').click()
        assert page.locator('.brand .eyebrow').text_content().strip()=='Decision Intelligence'
        assert page.locator('[data-tab="leaderboard"]').inner_text()=='Leaderboard'
        assert page.locator('.lb-heading h2').inner_text()=='Leaderboard'
        page.locator('[data-language="en"]').click()
        assert brand.locator('.fs-type-scramble').count()==0
        assert brand.evaluate('n=>getComputedStyle(n).opacity==="1"&&getComputedStyle(n).color!=="rgba(0, 0, 0, 0)"&&!n.getAnimations().length')
        page.screenshot(path=str(args.output/'intro-gather.png'))
        page.wait_for_function(RESTORED,timeout=15000)
        assert page.locator('.brand strong').inner_text()=='Blink'
        assert page.locator('.blog-kicker').count()==0
        assert page.evaluate("getComputedStyle(document.body).getPropertyValue('--fs-accent').trim().toLowerCase()")=='#b96e50'
        report.append({'intro':initial,'text_restored':True})
        page.locator('[data-tab="leaderboard"]').click();page.wait_for_timeout(160)
        dust=page.evaluate(PIXELS);assert dust['active']==1 and dust['pixels']>100,dust
        assert page.locator('.nav-wind-light').evaluate('(n)=>n.getAnimations().length')==1
        assert page.locator('.tabs .tab>span').evaluate_all('(ns)=>ns.every(n=>getComputedStyle(n).opacity==="1" && !n.getAnimations().length)'), 'Navigation labels must stay intact'
        assert page.evaluate("""() => {const c=document.getElementById('fsSandCanvas'),ratio=c.width/innerWidth,d=c.getContext('2d').getImageData(0,Math.floor(400*ratio),c.width,Math.floor(250*ratio)).data;return d.some((v,i)=>i%4===3&&v>0)}"""), 'Article content must participate, beyond the page title'
        assert page.locator('#lbPixelEffects i').count()>0
        page.screenshot(path=str(args.output/'nav-dissolve.png'))
        page.wait_for_function(RESTORED,timeout=15000)
        assert page.evaluate(PIXELS)['pixels']==0
        page.locator('[data-tab="blog"]').click();page.wait_for_function(RESTORED,timeout=15000)
        page.locator('.blog-report>summary').first.click()
        page.locator('[data-tab="leaderboard"]').click();page.wait_for_timeout(150)
        assert page.evaluate("""() => {const c=document.getElementById('fsSandCanvas'),ratio=c.width/innerWidth,d=c.getContext('2d').getImageData(0,Math.floor(670*ratio),c.width,Math.floor(250*ratio)).data;return d.some((v,i)=>i%4===3&&v>0)}"""), 'Expanded article body must participate'
        page.screenshot(path=str(args.output/'expanded-article-dissolve.png'))
        page.wait_for_function(RESTORED,timeout=15000)
        # Titles and smaller subtitles gather with the body. No character
        # substitution or typing overlay is allowed in the final design.
        for language in ['en','zh']:
            page.locator(f'[data-language="{language}"]').click()
            for view,title,subtitle in [
                ('games','.playground-heading h2','#playCount'),
                ('leaderboard','.lb-heading h2','#leaderboardStatus'),
                ('blog','#blogTitle','.blog-heading p')]:
                page.locator(f'[data-tab="{view}"]').click();page.wait_for_timeout(150)
                sample=page.evaluate('''([title,subtitle])=>[title,subtitle].map(s=>{
                  const n=document.querySelector(s),r=n.getBoundingClientRect();
                  return{text:n.textContent,opacity:parseFloat(getComputedStyle(document.getElementById('sitePageContent')).opacity),rect:[r.x,r.y,r.width,r.height]};
                })''',[title,subtitle])
                assert all(x['text'] and x['opacity']<1 for x in sample),(view,sample)
                assert page.locator('.fs-type-scramble,.fs-type-running').count()==0
                assert page.evaluate(PIXELS)['active']==1
                assert page.evaluate('''([title,subtitle])=>{
                  const c=document.getElementById('fsSandCanvas'),ctx=c.getContext('2d'),scale=c.width/innerWidth;
                  return [title,subtitle].every(s=>{const r=document.querySelector(s).getBoundingClientRect(),x=Math.max(0,r.x-140),y=Math.max(0,r.y-65),w=Math.min(innerWidth-x,r.width+200),h=Math.min(innerHeight-y,r.height+130);if(w<=0||h<=0)return false;const pixels=ctx.getImageData(Math.floor(x*scale),Math.floor(y*scale),Math.floor(w*scale),Math.floor(h*scale)).data;return pixels.some((v,i)=>i%4===3&&v>0);});
                }''',[title,subtitle]),(view,'heading/subtitle sand missing')
                page.screenshot(path=str(args.output/f'{view}-{language}-sand.png'))
                page.wait_for_function(RESTORED,timeout=15000)
                final=page.locator(title).bounding_box();old=sample[0]['rect']
                assert all(abs(final[k]-v)<.6 for k,v in zip(['x','y','width','height'],old)),(view,old,final)
                assert page.locator(title).inner_text()==sample[0]['text']
                page.screenshot(path=str(args.output/f'{view}-{language}-resolved.png'))
                report.append({'view':view,'language':language,'heading_sand':True,'subtitle_sand':True,'no_typing':True,'synchronized_sand':True,'no_layout_shift':True})
        # Interruptions restore original inline style, including live preference changes.
        page.evaluate("""async()=>{for(let i=0;i<7;i++){
          document.querySelector('[data-tab="'+(i%2?'leaderboard':'blog')+'"]').click();
          await new Promise(r=>setTimeout(r,55));}}""")
        page.wait_for_function(RESTORED,timeout=15000)
        page.locator('[data-tab="leaderboard"]').click();page.wait_for_timeout(100)
        page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(60)
        assert page.evaluate(RESTORED) and page.evaluate(PIXELS)['active']==0
        page.locator('[data-tab="blog"]').click();page.wait_for_timeout(80)
        assert page.evaluate(PIXELS)['pixels']==0
        page.emulate_media(reduced_motion='no-preference')
        page.locator('[data-tab="leaderboard"]').click();page.wait_for_timeout(100)
        page.evaluate('window.scrollTo(0,200)');page.wait_for_timeout(60)
        assert page.evaluate(RESTORED) and page.evaluate(PIXELS)['active']==0
        page.evaluate('window.scrollTo(0,0)')
        page.locator('[data-tab="blog"]').click();page.wait_for_timeout(100)
        page.set_viewport_size({'width':1280,'height':900});page.wait_for_timeout(60)
        assert page.evaluate(RESTORED) and page.evaluate(PIXELS)['active']==0
        report.append({'navigation':dust,'rapid_switch':True,'reduced_motion':True,'scroll_resize_cleanup':True,'glass_light_and_wind_preserved':True})
        context.close()
        # Mimic a reverse proxy that strips its mount prefix. Asset URLs must retain it.
        prefix='dsw-434426/ide/proxy/8080/'
        page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        page.on('pageerror',lambda e:errors.append(str(e)))
        def proxy(route):
            path=route.request.url.split('/'+prefix,1)[1]
            route.fulfill(response=route.fetch(url=urljoin(args.url,path)))
        page.route('**/'+prefix+'**',proxy)
        page.goto(urljoin(args.url,prefix),wait_until='networkidle')
        page.locator('[data-tab="leaderboard"]').click()
        for benchmark in ['jevbench','decisionindex','harnessjevbench','gamejevbench']:
            page.locator(f'[data-benchmark="{benchmark}"]').click();page.wait_for_selector('.lb-radar-svg');page.wait_for_timeout(200)
            logos=page.locator('.lb-model-logo').evaluate_all("""ns=>ns.filter(n=>n.getClientRects().length).map(n=>({url:n.src,loaded:n.complete&&n.naturalWidth>0}))""")
            assert logos and all(l['loaded'] and prefix in l['url'] for l in logos),(benchmark,logos)
            report.append({'benchmark':benchmark,'prefixed_logos_loaded':len(logos)})
        for model in ['Qwen3.8 Max','Qwen3.6']:
            rows=page.locator('.elo-table tbody tr').filter(has_text=model)
            assert rows.count()>0,model
            for row in rows.all():
                logo=row.locator('.lb-model-logo');assert logo.count()>0,model
                assert logo.first.get_attribute('src').endswith('/qwen.png'),model
        page.close();browser.close()
    assert not errors,errors
    (args.output/'motion-report.json').write_text(json.dumps({'checks':report,'errors':errors},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(report),'errors':errors}))


if __name__=='__main__':
    main()
