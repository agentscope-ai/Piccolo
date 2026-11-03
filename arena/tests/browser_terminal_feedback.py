"""Render recorded native terminal states and verify winner feedback, no model calls."""
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def run(a):
    checks=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=await b.new_page()
        await page.goto(a.url,wait_until='domcontentloaded')
        await page.wait_for_function('modelReady&&catalog&&showcaseKinds.length&&!busy&&!showcaseBusy')
        await page.evaluate("JevI18n.setLanguage('zh');tab('games')")
        await page.wait_for_function('!busy&&!showcaseBusy&&showcaseSession')
        for game,seed in [('othello_6x6',101),('hex_7x7',101),('checkers',101),('uno',101),('liars_dice',101),('xiangqi',101),('property_tycoon',202),('sudoku',202)]:
            folder=Path(a.recordings)/'runs'/(game+'-'+str(seed))
            paths=list(folder.glob('attempt-*/final-state.json')) or [folder/'final-state.json']
            g=json.loads(paths[-1].read_text())['state']
            await page.evaluate('(g)=>JevSelectPlay(g)',game)
            await page.wait_for_function('g=>selectedPlay===g&&!busy&&!showcaseBusy',arg=game)
            if await page.evaluate('JevParticipants.isDuel()'):await page.select_option('#participantOpponent','rule')
            await page.wait_for_function('!busy&&!showcaseBusy')
            if game in ['othello_6x6','hex_7x7','dots_and_boxes_3x3']:
                await page.evaluate('(g)=>{gameState.game=g;renderGame()}',g)
                selector='#gameOutcome';expected='draw' if g['winner']=='draw' else 'win' if g['winner']=='X' else 'loss'
            else:
                await page.evaluate('(g)=>{showcaseSession.world=g;renderShowcaseGame()}',g)
                selector='#showcaseOutcome';expected='draw' if g['outcome'] in ['draw','budget_exhausted'] else 'win' if g['outcome']=='win' else 'loss'
            actual=await page.locator(selector).get_attribute('class')
            assert actual==expected,(game,actual,expected)
            assert await page.locator(selector).is_visible(),(game,await page.locator(selector).evaluate('(n)=>({text:n.textContent,parent:n.parentElement.id,display:getComputedStyle(n).display})'))
            before=await page.evaluate("JevParticipants.isBoard()?gameState.session_id:showcaseSession.session_id")
            await page.click('#newGame' if game in ['othello_6x6','hex_7x7','dots_and_boxes_3x3'] else '#showcaseNew')
            await page.wait_for_function('!busy&&!showcaseBusy')
            after=await page.evaluate("JevParticipants.isBoard()?gameState.session_id:showcaseSession.session_id")
            assert after!=before,(game,'restart did not create a new session')
            assert not await page.locator(selector).is_visible(),(game,'stale outcome after restart')
            checks.append({'game':game,'expected':expected,'actual':actual,'restart':True})
        folder=Path(a.recordings)/'runs/tetris_placement-101'
        paths=list(folder.glob('attempt-*/final-state.json')) or [folder/'final-state.json']
        g=json.loads(paths[-1].read_text())['state']
        await page.evaluate("JevSelectPlay('tetris_placement')")
        await page.wait_for_function('!busy&&!showcaseBusy')
        text=await page.evaluate('''g=>{showcaseSession.world=g;renderShowcaseGame();const text=document.getElementById('sceneStats').textContent;JevTetrisUI.deactivate();return text}''',g)
        assert '已结束' in text and '下落中' not in text,text
        checks.append({'game':'tetris_placement','terminal_phase':'已结束'})
        await page.set_viewport_size({'width':390,'height':1000})
        await page.evaluate("JevSelectPlay('doudizhu')")
        await page.wait_for_function('!busy&&!showcaseBusy')
        await page.select_option('#participantFirst','human')
        await page.wait_for_function('!busy&&!showcaseBusy')
        if await page.locator('#duelReveal').is_visible():
            await page.click('#duelReveal');await page.wait_for_function('!showcaseBusy')
        canvas=page.locator('#showcaseCanvas');box=await canvas.bounding_box()
        assert box['width']<=390,box
        await canvas.click(position={'x':box['width']*.5,'y':box['height']*.87})
        assert await page.evaluate('cardSelection.length')==1,'scaled card hit test failed'
        checks.append({'game':'doudizhu','mobile_card_selection':True,'scene_width':box['width']})
        await page.evaluate("JevSelectPlay('terraria_survival')")
        await page.wait_for_function('!busy&&!showcaseBusy')
        disabled=await page.evaluate('''()=>{const g=worldBridge().snapshot(false);renderWorld({...g,wins:1,episode_terminal:true});return {step:document.getElementById('showcaseModel').disabled,auto:document.getElementById('showcaseAuto').disabled,manual:[...document.querySelectorAll('#showcaseActions button')].every(b=>b.disabled)}}''')
        assert all(disabled.values()),('terra_terminal_controls',disabled)
        await page.click('#showcaseNew');await page.wait_for_function('!showcaseBusy')
        assert await page.evaluate('!worldOutcome&&!document.getElementById("showcaseModel").disabled')
        checks.append({'game':'terraria_survival','terminal_controls_disabled':True,'restart':True})
        await b.close()
    print(json.dumps({'checks':checks,'model_calls':0},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8768/');p.add_argument('--recordings',required=True)
    asyncio.run(run(p.parse_args()))
