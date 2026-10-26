"""Actual current UI + native backend + explicit fixture predictions; no deployment."""
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlparse
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from blink_arena.app import create_app
from blink_arena.schemas import AppConfig,DecisionOutput
from jev_selected_games import GAMES

OUT=Path(os.environ.get('JEV_SELECTED_TEST_OUT', str(Path(tempfile.gettempdir())/'jev-selected-games-browser')))
MODEL='selected-games-fixture'

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assets=Path(__file__).resolve().parents[1]/'web'
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(assets)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    results=[];calls=[]
    try:
        with tempfile.TemporaryDirectory() as folder,TestClient(create_app(data=folder,config=AppConfig())) as client,sync_playwright() as pw:
            reply=client.post('/api/v1/connections',json={'model_id':MODEL,'name':'接口验证 Fixture','served_model':MODEL,'adapter':'decision','transport':'browser'})
            assert reply.status_code==201,reply.text
            async def fixture(request):
                calls.append(request.game)
                options=request.question.options
                return DecisionOutput(request_id=request.request_id,model=request.model,action=options[0].id,
                                      probabilities={o.id:1/len(options) for o in options})
            client.app.state.providers.browser_relays[MODEL]=fixture
            client.app.state.connections.entries[MODEL]['last_poll']=time.monotonic()
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1150},device_scale_factor=2)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def route(route):
                req=route.request;u=urlparse(req.url)
                headers={'content-type':'application/json','X-Demo-Model':MODEL}
                response=client.request(req.method,u.path+('?' + u.query if u.query else ''),content=req.post_data,headers=headers)
                route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
            page.route('**/api/**',route)
            page.goto(f'http://127.0.0.1:{server.server_port}/?model={MODEL}')
            page.wait_for_function('modelReady&&typeof showcaseKinds!=="undefined"&&showcaseKinds.length>0&&!busy')
            page.locator('.tab[data-tab="games"]').click()
            page.locator('#playFilters [data-filter="board"]').click()
            for kind in ('checkers','go','xiangqi'):
                assert page.locator(f'#gamePicker [data-kind="{kind}"]').is_visible()
            page.locator('#playFilters [data-filter="new"]').click()
            assert page.locator('#gamePicker [data-kind="iterated_rps"]').count()==0
            assert page.locator('#gamePicker [data-kind]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.kind)') == [
                'snake_navigation','sokoban_puzzle','blackjack','chess','tetris_placement','uno']
            for kind in GAMES:
                page.locator('#playSearch').fill(kind)
                page.locator(f'#gamePicker [data-kind="{kind}"]').click()
                page.wait_for_function('k=>showcaseSession?.world.kind===k&&!showcaseBusy',arg=kind)
                # A typed draft seed no longer changes a standard opening.
                # Use the actual opt-in reset control for reproducible fixtures.
                page.locator('#playSeed').fill('42')
                page.locator('#playSeedApply').click()
                page.wait_for_function('!showcaseBusy&&showcaseSession.world.steps===0')
                assert page.locator('#selectedGameBoard').is_visible()
                page.locator('[data-language="en"]').click()
                assert not re.search(r'[\u3400-\u9fff]',page.locator('#selectedGameBoard .selected-heading').inner_text())
                assert not re.search(r'[\u3400-\u9fff]',page.locator('#showcaseGoal').inner_text())
                page.locator('[data-language="zh"]').click()
                if kind=='uno':
                    assert page.locator('.selected-hand .uno-card').count()==len(page.evaluate('showcaseSession.world.hand'))
                    assert page.locator('.uno-opponent .uno-back').count()>0
                    assert page.locator('#showcaseActions .uno-wild').count()==4
                    labels=page.locator('#showcaseActions .uno-action').all_text_contents()
                    assert all(any(color in label for label in labels) for color in ('红色','绿色','蓝色','黄色'))
                if kind=='xiangqi':
                    assert page.locator('.xiangqi-piece').count()==32
                    assert page.locator('.red-piece .xiangqi-piece').count()==16
                    assert page.locator('.xiangqi-lines .xiangqi-palace').count()==4
                    assert '楚 河' in page.locator('.xiangqi-lines').text_content()
                    assert '漢 界' in page.locator('.xiangqi-lines').text_content()
                    page.locator('#selectedGameBoard').screenshot(path=str(OUT/'xiangqi-desktop-initial.png'))
                    action,label=page.evaluate('Object.entries(showcaseSession.choices)[0]')
                    coords=re.search(r'\((\d+),(\d+)\)-\((\d+),(\d+)\)',label)
                    r,c,rr,cc=map(int,coords.groups())
                    origin=page.locator(f'.xiangqi [data-row="{r}"][data-col="{c}"]')
                    token=origin.locator('.xiangqi-piece').bounding_box();cell=origin.bounding_box()
                    assert abs(token['x']+token['width']/2-cell['x']-cell['width']/2)<1
                    assert abs(token['y']+token['height']/2-cell['y']-cell['height']/2)<1
                    origin.click()
                    destination=page.locator(f'.xiangqi [data-row="{rr}"][data-col="{cc}"]')
                    assert 'origin' in origin.get_attribute('class')
                    assert 'destination' in destination.get_attribute('class')
                    destination.click()
                    page.wait_for_function('a=>showcaseSession.action===a&&!showcaseBusy',arg=action)
                    assert page.locator(f'.xiangqi [data-row="{rr}"][data-col="{cc}"] .xiangqi-piece').count()==1
                    assert origin.locator('.xiangqi-piece').count()==0
                elif kind=='checkers':
                    page.locator('#showcaseActions details').evaluate('n=>n.open=true')
                    page.locator('#showcaseActions [data-action]').first.click()
                elif kind in ('go','minesweeper','sudoku'):
                    page.locator('#selectedGameBoard [data-action]').first.click()
                elif kind=='uno':
                    blue=page.evaluate('Object.keys(showcaseSession.choices).find(k=>showcaseSession.choices[k]==="b-wild")')
                    page.locator(f'#showcaseActions [data-action="{blue}"]').click()
                else:page.locator('#showcaseActions [data-action]').first.click()
                page.wait_for_function('showcaseSession?.world.steps===1&&!showcaseBusy')
                if kind=='uno':
                    page.locator('.selected-reveal').click();page.wait_for_function('!showcaseBusy&&!showcaseSession.world.handoff')
                    assert page.evaluate('showcaseSession.world.target')=='b-wild'
                    assert '蓝色' in page.locator('.uno-active-color').inner_text()
                if kind=='go':
                    geometry=page.locator('.go-stone').evaluate('''s=>{const b=s.parentElement,a=s.getBoundingClientRect(),p=b.getBoundingClientRect(),line=getComputedStyle(b,'::before');return {dx:Math.abs(a.x+a.width/2-p.x-p.width/2),dy:Math.abs(a.y+a.height/2-p.y-p.height/2),line:parseFloat(line.top),half:p.height/2,label:b.getAttribute('aria-label')}}''')
                    assert geometry['dx']<1 and geometry['dy']<1 and abs(geometry['line']-geometry['half'])<1,geometry
                    assert geometry['label'].startswith('A9'),geometry
                if page.evaluate('showcaseSession.world.handoff'):
                    assert page.locator('#selectedGameBoard .selected-reveal').is_visible()
                    page.locator('.selected-reveal').click();page.wait_for_function('!showcaseBusy&&!showcaseSession.world.handoff')
                old=page.evaluate('showcaseSession.world.steps')
                page.locator('#showcaseModel').click()
                page.wait_for_function('n=>!showcaseBusy&&showcaseSession.world.steps>n',arg=old)
                if page.evaluate('showcaseSession.world.handoff'):
                    page.locator('.selected-reveal').click();page.wait_for_function('!showcaseBusy&&!showcaseSession.world.handoff')
                assert not errors,errors
                assert page.locator('#globalError').evaluate('n=>n.classList.contains("hidden")'),page.locator('#globalError').inner_text()
                page.screenshot(path=str(OUT/(kind+'.png')))
                results.append({'kind':kind,'native_manual_action':True,'fixture_model_action':True,'custom_renderer':True,'seat_handoff':kind == 'uno','page_errors':0})
                print(kind,'browser PASS',flush=True)
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#playSearch').fill('xiangqi')
            page.locator('#gamePicker [data-kind="xiangqi"]').click()
            page.wait_for_function('showcaseSession?.world.kind==="xiangqi"&&!showcaseBusy')
            assert page.locator('.xiangqi-piece').count()==32
            geometry=page.locator('.xiangqi-piece').first.evaluate('''n=>{const p=n.getBoundingClientRect(),c=n.parentElement.getBoundingClientRect(),b=n.closest('.xiangqi').getBoundingClientRect();return{width:p.width,cell:c.width,dx:Math.abs(p.x+p.width/2-c.x-c.width/2),dy:Math.abs(p.y+p.height/2-c.y-c.height/2),font:parseFloat(getComputedStyle(n).fontSize),board:b.width,viewport:innerWidth}}''')
            assert 20<=geometry['width']<geometry['cell'] and geometry['font']>=16,geometry
            assert geometry['dx']<1 and geometry['dy']<1 and geometry['board']<=geometry['viewport'],geometry
            page.locator('#selectedGameBoard').screenshot(path=str(OUT/'xiangqi-mobile-initial.png'))
            page.locator('.xiangqi .selectable').first.click()
            assert page.locator('.xiangqi .origin').count()==1
            assert page.locator('.xiangqi .destination').count()>0
            page.locator('#selectedGameBoard').screenshot(path=str(OUT/'xiangqi-mobile-selected.png'))
            page.locator('.xiangqi .destination').first.click()
            page.wait_for_function('showcaseSession.world.steps===1&&!showcaseBusy')
            page.locator('#selectedGameBoard').screenshot(path=str(OUT/'xiangqi-mobile-moved.png'))
            print('xiangqi-mobile pieces and moves PASS',flush=True)
            # The social renderers use the same logical 900×540 hit positions at
            # every display density. Check readability and real card selection.
            social=[]
            page.locator('#playFilters [data-filter="all"]').click()
            for viewport in ({'width':1440,'height':1150},{'width':390,'height':844}):
                page.set_viewport_size(viewport)
                for kind in ('property_tycoon','texas_holdem','doudizhu'):
                    page.locator('#playSearch').fill(kind)
                    page.locator(f'#gamePicker [data-kind="{kind}"]').click()
                    page.wait_for_function('k=>showcaseSession?.world.kind===k&&!showcaseBusy',arg=kind)
                    page.evaluate('document.fonts.ready');page.wait_for_timeout(100)
                    quality=page.locator('#showcaseCanvas').evaluate('''c=>({width:c.width,height:c.height,css:c.getBoundingClientRect().width,dpr:devicePixelRatio,rendering:getComputedStyle(c).imageRendering})''')
                    assert quality['width']>=quality['css']*quality['dpr']-1 and quality['rendering']=='auto',quality
                    if kind=='doudizhu':
                        # At mobile width the stage scrolls. Select an actually
                        # visible middle card using logical coordinates.
                        point=page.evaluate('''()=>{const c=$('showcaseCanvas'),b=c.getBoundingClientRect(),n=showcaseSession.world.hand.length,w=54,step=Math.min(37,(900-144-w)/Math.max(1,n-1)),left=(900-step*(n-1)-w)/2,i=Math.floor(n/2);return{x:b.x+(left+i*step+step/2)*b.width/900,y:b.y+455*b.height/540,i}}''')
                        page.locator('#showcaseCanvas').scroll_into_view_if_needed()
                        # Vertical scroll can move the canvas; recompute y.
                        rect=page.locator('#showcaseCanvas').bounding_box();point['y']=rect['y']+455*rect['height']/540
                        page.mouse.click(point['x'],point['y'])
                        assert page.evaluate('cardSelection')==[point['i']]
                    if kind=='property_tycoon' and viewport['width']==1440:
                        before=page.evaluate('structuredClone(showcaseSession.world)')
                        page.locator('#showcaseActions [data-action="roll"]').click()
                        page.wait_for_function('showcaseSession.world.steps>0&&!showcaseBusy')
                        replay=page.evaluate('''async before=>{
                          const host=document.createElement('div');host.style.width='900px';document.body.append(host);
                          const renderer=await JevReplayRenderer.mount(host,{kind:'property_tycoon'});
                          const canvas=renderer.frame.contentDocument.querySelector('canvas'),ctx=canvas.getContext('2d'),draw=ctx.drawImage,overlays=[];
                          ctx.drawImage=function(...args){overlays.push({scale:this.getTransform().a,width:args[3],height:args[4]});return draw.apply(this,args)};
                          await renderer.update({previousState:before,state:showcaseSession.world,animate:true,durationMs:180});
                          const result={width:canvas.width,height:canvas.height,overlays};renderer.destroy();host.remove();return result;
                        }''',before)
                        assert replay['overlays'] and all(x['scale']==1 and x['width']==replay['width'] and x['height']==replay['height'] for x in replay['overlays']),replay
                    await_before=page.evaluate('showcaseSession.world.steps')
                    if kind=='texas_holdem':
                        page.locator('#showcaseActions [data-action="check"],#showcaseActions [data-action="call"]').first.click()
                        page.wait_for_function('n=>showcaseSession.world.steps>n&&!showcaseBusy',arg=await_before)
                    name=kind+('-mobile' if viewport['width']==390 else '-desktop')
                    page.locator('.canvas-shell').screenshot(path=str(OUT/(name+'.png')))
                    social.append({'kind':kind,'viewport':viewport,**quality,'card_hit_test':kind=='doudizhu'})
                    print(name,'clarity PASS',flush=True)
            assert not errors,errors
            browser.close()
        (OUT/'browser.json').write_text(json.dumps({'games':results,'social':social,'fixture_prediction_calls':len(calls),'real_model_calls':0,'public_deployment':False},ensure_ascii=False,indent=2)+'\n')
    finally:
        server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()
