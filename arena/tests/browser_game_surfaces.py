"""Check Canvas, DOM and iframe games survive page navigation without model calls."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


PAINTED = """canvas => canvas.width>0 && canvas.height>0 &&
    canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data.some(
      (value,index)=>index%4===3 && value>0)"""


def settle(page, tab):
    panel={'blog':'blogView','games':'gamesView'}[tab]
    page.locator('#'+panel).wait_for(state='visible')
    page.wait_for_function("""() => !busy && !showcaseBusy &&
      !document.querySelector('#sitePageContent').getAnimations().some(a=>a.playState==='running')""")
    assert page.locator('#sitePageContent').evaluate('(n)=>getComputedStyle(n).opacity')=='1'
    assert page.locator('#globalError').evaluate('(n)=>n.classList.contains("hidden")')


def move_xiangqi(page, expected_steps):
    page.locator('.xiangqi .selectable').first.click()
    page.locator('.xiangqi .destination').first.click()
    page.wait_for_function('steps=>showcaseSession.world.steps===steps&&!showcaseBusy',arg=expected_steps)


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
                page.locator('#playQuickGame').select_option(kind)
                page.wait_for_function('k=>selectedPlay===k&&!busy&&!showcaseBusy',arg=kind)
                page.locator(surface).wait_for(state='visible')
                settle(page,'games')
                scene=page.locator(surface).element_handle()
                world=None
                bridge=None
                if kind=='mario_platformer':
                    world=scene.content_frame()
                    assert world is not None
                    world.wait_for_function('!!window.JevMario?.snapshot')
                    world.locator('#game').wait_for(state='visible')
                    assert world.locator('#game').evaluate(PAINTED),(kind,'iframe canvas is blank')
                    bridge=page.evaluate_handle('worldBridge("mario_platformer")')
                    before=world.evaluate('window.JevMario.snapshot()')
                    condition=world.evaluate('window.JevMario.condition()')
                    assert before['player'] and before['map']['tiles'],(kind,'world snapshot missing')
                else:
                    if kind=='snake_navigation':
                        assert page.locator(surface).evaluate(PAINTED),(kind,'canvas is blank')
                    else:
                        assert page.locator('.xiangqi-piece').count()==32
                        move_xiangqi(page,1)
                    before=page.evaluate('({session:showcaseSession.session_id,world:showcaseSession.world})')
                    assert before['session'],(kind,'manual session missing')
                # Returning to Playground must retain the selected game and its state.
                page.locator('[data-tab="blog"]').click()
                settle(page,'blog')
                assert not page.locator(surface).is_visible()
                page.locator('[data-tab="games"]').click()
                settle(page,'games')
                page.locator(surface).wait_for(state='visible')
                assert page.evaluate('selectedPlay')==kind
                assert page.locator('#playQuickGame').input_value()==kind
                assert scene.evaluate('(node,selector)=>node===document.querySelector(selector)',surface),(kind,'surface was replaced')
                state=page.evaluate('''s=>{
                  const root=document.getElementById('sitePageContent'),nav=document.querySelector('.tabs'),scene=document.querySelector(s),r=scene.getBoundingClientRect();
                  return{surfaceInside:root.contains(scene),footerInside:root.contains(document.querySelector('.foot')),navInside:root.contains(nav),brandInside:root.contains(document.querySelector('.brand')),width:r.width,height:r.height,pointer:getComputedStyle(scene).pointerEvents};
                }''',surface)
                assert state['surfaceInside'] and state['footerInside'],(kind,state)
                assert not state['navInside'] and not state['brandInside'],(kind,state)
                assert state['width']>0 and state['height']>0 and state['pointer']!='none',(kind,state)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if kind=='mario_platformer':
                    assert bridge.evaluate('(value)=>value===worldBridge("mario_platformer")'),(kind,'world bridge was replaced')
                    after=world.evaluate('window.JevMario.snapshot()')
                    assert world.evaluate('window.JevMario.condition()')==condition,(kind,'world seed changed')
                    assert after['frame']>=before['frame'] and after['decisions']==before['decisions'],(kind,'world was reset')
                    assert world.locator('#game').evaluate(PAINTED),(kind,'iframe canvas blank after return')
                    bridge.dispose()
                else:
                    after=page.evaluate('({session:showcaseSession.session_id,world:showcaseSession.world})')
                    assert after['session']==before['session'],(kind,'manual session was replaced')
                    if kind=='xiangqi':
                        assert after['world']==before['world'],(kind,'board state changed during navigation')
                        move_xiangqi(page,2)
                    else:
                        # Realtime game clocks may advance; returning must not restart them.
                        assert after['world']['steps']>=before['world']['steps'],(kind,'game progress reset')
                        assert page.locator(surface).evaluate(PAINTED),(kind,'canvas blank after return')
                page.locator(surface).scroll_into_view_if_needed()
                page.screenshot(path=str(args.output/f'{kind}-{width}-surface.png'))
                checks.append({'kind':kind,'viewport':width,**state,'state_preserved':True,'manual_move_after_return':kind=='xiangqi'})
                scene.dispose()
            page.emulate_media(reduced_motion='reduce')
            page.locator('[data-tab="blog"]').click()
            settle(page,'blog')
            page.locator('[data-tab="games"]').click()
            settle(page,'games')
            assert page.locator('#marioFrame').is_visible()
            assert page.locator('#sitePageContent').evaluate('(n)=>!n.getAnimations().length')
            page.close()
        browser.close()
    assert not errors,errors
    (args.output/'report.json').write_text(json.dumps({'checks':checks,'errors':errors,'model_calls':0},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'errors':errors}))

if __name__=='__main__':main()
