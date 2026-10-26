"""Whole content sand: real game canvases/DOM/iframe, stable controls, fixed English brand labels."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    errors=[];checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        for width in (1440,390):
            page=browser.new_page(viewport={'width':width,'height':1200})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(args.url,wait_until='networkidle');page.evaluate('document.fonts.ready')
            page.locator('[data-language="zh"]').click()
            assert page.locator('.brand .eyebrow').text_content().strip()=='Decision Intelligence'
            assert page.locator('[data-tab="leaderboard"]').inner_text()=='Leaderboard'
            assert page.locator('.lb-heading h2').inner_text()=='Leaderboard'
            page.locator('[data-tab="games"]').click()
            page.wait_for_function('!busy&&!showcaseBusy&&catalog&&showcaseKinds.length>0')
            for kind,surface in [('snake_navigation','#showcaseCanvas'),('xiangqi','.selected-grid.xiangqi'),('mario_platformer','#marioFrame')]:
                page.locator('#playSearch').fill(kind)
                page.locator(f'#gamePicker [data-kind="{kind}"]').click()
                page.wait_for_function('k=>selectedPlay===k&&!busy&&!showcaseBusy',arg=kind)
                page.locator(surface).wait_for(state='visible')
                page.wait_for_timeout(1200)
                # Start the same page entry effect by switching away and back.
                page.locator('[data-tab="blog"]').click();page.wait_for_timeout(1000)
                page.locator('[data-tab="games"]').click();page.wait_for_timeout(300)
                state=page.evaluate('''s=>{
                  const root=$('sitePageContent'),nav=document.querySelector('.tabs'),scene=document.querySelector(s),r=scene.getBoundingClientRect(),canvas=$('fsSandCanvas'),scale=canvas.width/innerWidth,ctx=canvas.getContext('2d');
                  const x=Math.max(0,r.x),y=Math.max(nav.getBoundingClientRect().bottom,r.y),w=Math.min(innerWidth-x,r.width),h=Math.min(innerHeight-y,r.height);
                  let pixels=0;if(w>0&&h>0){const d=ctx.getImageData(Math.floor(x*scale),Math.floor(y*scale),Math.floor(w*scale),Math.floor(h*scale)).data;for(let i=3;i<d.length;i+=4)if(d[i])pixels++;}
                  const top=ctx.getImageData(0,0,canvas.width,Math.floor(nav.getBoundingClientRect().bottom*scale)).data;
                  return{groupOpacity:Number(getComputedStyle(root).opacity),surfaceInside:root.contains(scene),footerInside:root.contains(document.querySelector('.foot')),navInside:root.contains(nav),brandInside:root.contains(document.querySelector('.brand')),gamePixels:pixels,navPixels:top.filter((v,i)=>i%4===3&&v>0).length,pointer:getComputedStyle(canvas).pointerEvents,steps:typeof showcaseSession!=='undefined'?showcaseSession?.world.steps:null};
                }''',surface)
                assert state['groupOpacity']<1 and state['surfaceInside'] and state['footerInside'],(kind,state)
                assert not state['navInside'] and not state['brandInside'],state
                assert state['gamePixels']>20 and state['navPixels']==0 and state['pointer']=='none',(kind,state)
                page.screenshot(path=str(args.output/f'{kind}-{width}-sand.png'))
                page.wait_for_timeout(1050)
                assert page.locator('#sitePageContent').evaluate('n=>n.style.opacity===""')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if kind=='xiangqi':
                    assert page.locator('.xiangqi-piece').count()==32
                    page.locator('.xiangqi .selectable').first.click()
                    page.locator('.xiangqi .destination').first.click()
                    page.wait_for_function('showcaseSession.world.steps===1&&!showcaseBusy')
                checks.append({'kind':kind,'width':width,**state,'clicks_after_reveal':True})
            page.emulate_media(reduced_motion='reduce');page.locator('[data-tab="blog"]').click();page.wait_for_timeout(100)
            assert page.locator('#sitePageContent').evaluate('n=>n.style.opacity===""')
            page.close()
        browser.close()
    assert not errors,errors
    (args.output/'report.json').write_text(json.dumps({'checks':checks,'errors':errors,'model_calls':0},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'errors':errors}))

if __name__=='__main__':main()
