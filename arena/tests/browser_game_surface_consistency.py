"""Exercise surface ownership, phone input, native autoplay and waiting gravity.

The waiting-gravity check holds the browser request before dispatch: it tests
the UI clock/cancellation contract and contributes no model performance result.
"""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Error as PlaywrightError
from browser_five_seed_playthrough import write


async def run(a):
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-background-timer-throttling'])
        page=await browser.new_page(viewport={'width':390,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(a.url,wait_until='domcontentloaded')
        await page.wait_for_function('modelReady&&catalog&&showcaseKinds.length&&!busy&&!showcaseBusy')
        await page.evaluate("JevI18n.setLanguage('zh');tab('games')")
        await page.wait_for_function('!busy&&!showcaseBusy&&showcaseSession')
        async def choose(game):
            await page.evaluate('(g)=>JevSelectPlay(g)',game)
            await page.wait_for_function('g=>selectedPlay===g&&!busy&&!showcaseBusy',arg=game)

        # A selected DOM board must never survive a canvas/iframe/board switch.
        for game in ['sudoku','snake_navigation','sudoku','tetris_placement','sudoku','merge_2048','sudoku','terraria_survival','sudoku','hex_7x7','chess','uno','doudizhu']:
            await choose(game)
            surfaces=await page.evaluate("()=>[...document.querySelectorAll('#board,#showcaseCanvas,#selectedGameBoard,#chessStage,#agentGameStage,#marioFrame,#terrariaFrame')].filter(n=>n.getBoundingClientRect().width&&n.getBoundingClientRect().height).map(n=>n.id)")
            assert len(surfaces)==1,(game,surfaces)
        checks.append({'check':'surface_switches','transitions':13,'visible_surfaces':1})

        # The first frame must exist before a new episode releases its controls.
        for game in ['tetris_placement','snake_navigation']:
            await choose(game)
            for _ in range(5):
                painted=await page.evaluate('''async()=>{await newShowcase();const c=document.getElementById('showcaseCanvas');return c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0)}''')
                assert painted,(game,'reset released controls before painting the scene')
            checks.append({'check':'synchronous_initial_frame','game':game,'resets':5})

        # Phone controls must remain legible and large enough after theme overrides.
        for game in ['uno','liars_dice','tetris_placement','snake_navigation','sokoban_puzzle','terraria_survival','guess_the_number']:
            await choose(game)
            controls=await page.evaluate("()=>[...document.querySelectorAll('#modelMove,#showcaseModel,#newGame,#showcaseNew,#showcaseActions>button,#showcaseActions .dpad button,#showcaseActions .tetris-live-controls button')].filter(n=>n.getBoundingClientRect().height).map(n=>({id:n.id||n.textContent.trim(),height:n.getBoundingClientRect().height,font:parseFloat(getComputedStyle(n).fontSize)}))")
            assert all(c['height']>=43.5 and c['font']>=12 for c in controls),(game,controls)
        checks.append({'check':'phone_controls','games':7,'minimum_height':44})

        # Reflow is reversible and card indices still select the intended hand.
        await choose('doudizhu')
        await page.select_option('#participantFirst','human')
        await page.wait_for_function('!busy&&!showcaseBusy')
        for width,layout in [(390,'compact'),(1440,'wide'),(320,'compact')]:
            await page.set_viewport_size({'width':width,'height':900})
            await page.wait_for_timeout(100)
            assert await page.locator('#showcaseCanvas').get_attribute('data-layout')==layout
            point=await page.evaluate('''()=>{const c=document.getElementById('showcaseCanvas'),b=c.getBoundingClientRect();cardSelection=[];drawShowcase();const compact=c.dataset.layout==='compact';const g=showcaseSession.world.table;const hand=g.hand;const step=Math.min(37,(900-144-54)/Math.max(1,hand.length-1)),left=(900-step*(hand.length-1)-54)/2;return {x:(compact?34:left+5)*b.width/(compact?400:900),y:(compact?390:450)*b.height/(compact?555:540)}}''')
            await page.locator('#showcaseCanvas').click(position=point)
            assert await page.evaluate('JSON.stringify(cardSelection)')=='[0]',(width,'wrong selected card')
        checks.append({'check':'card_selection_after_resize','widths':[390,1440,320],'selected_index':0})

        # Native rule participants exercise the actual autoplay scheduler end to end.
        await page.set_viewport_size({'width':1024,'height':900})
        await choose('hex_7x7')
        await page.select_option('#participantFirst','rule')
        await page.select_option('#participantOpponent','rule')
        await page.wait_for_function('!busy&&!showcaseBusy')
        await page.click('#participantStart')
        await page.wait_for_function('!!gameState.game.winner',timeout=30000)
        await page.wait_for_function("document.getElementById('participantStart').textContent==='开始'")
        assert await page.locator('#gameOutcome').is_visible()
        await page.screenshot(path=str(out/'native-autoplay-terminal.png'),full_page=True)
        await page.click('#newGame');await page.wait_for_function('!busy&&!showcaseBusy')
        assert not await page.locator('#gameOutcome').is_visible()
        checks.append({'check':'native_autoplay_terminal_restart','game':'hex_7x7'})

        # The falling world must keep changing while the UI awaits a model reply.
        await choose('tetris_placement')
        await page.click('[data-tetris-action=rotate_cw]')
        await page.wait_for_function('showcaseSession.world.started')
        entered=asyncio.Event();release=asyncio.Event();handled=asyncio.Event()
        async def hold(route):
            if route.request.post_data_json.get('model'):
                entered.set();await release.wait()
                try:await route.abort('aborted')
                except PlaywrightError as error:
                    # Restart already aborted the fetch through AbortController.
                    if 'already handled' not in str(error):raise
                finally:handled.set()
            else:await route.continue_()
        await page.route('**/api/showcases/step',hold)
        await page.click('#showcaseAuto')
        await asyncio.wait_for(entered.wait(),10)
        before=await page.evaluate('({id:showcaseSession.session_id,world:showcaseSession.world})')
        await page.screenshot(path=str(out/'tetris-wait-before.png'),full_page=True)
        await page.wait_for_timeout(2600)
        after=await page.evaluate('showcaseSession.world')
        assert after['elapsed']>before['world']['elapsed']+1.5,(before['world']['elapsed'],after['elapsed'])
        assert after['active']!=before['world']['active'] or after['steps']>before['world']['steps'],'falling piece did not advance'
        await page.screenshot(path=str(out/'tetris-wait-during.png'),full_page=True)
        await page.click('#showcaseNew')
        await page.wait_for_function('old=>showcaseSession.session_id!==old&&!showcaseBusy',arg=before['id'])
        release.set();await asyncio.wait_for(handled.wait(),5)
        await page.unroute('**/api/showcases/step',hold)
        await page.wait_for_timeout(200)
        assert not await page.locator('#globalError').is_visible()
        checks.append({'check':'gravity_while_waiting_and_restart','elapsed_delta':round(after['elapsed']-before['world']['elapsed'],2),'model_calls':0})

        assert not errors,errors
        await browser.close()
    write(out/'checks.json',{'checks':checks,'page_errors':errors,'model_calls':0})
    print(json.dumps({'checks':checks,'page_errors':errors,'model_calls':0},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8768/');p.add_argument('--output',required=True)
    asyncio.run(run(p.parse_args()))
