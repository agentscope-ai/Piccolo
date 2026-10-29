"""Run against tests/hosted_fixture.py on loopback; uses no real provider keys."""
import argparse
import asyncio
import json
import uuid
from pathlib import Path

from playwright.async_api import async_playwright
from browser_connections import mock_model, FIXTURE_KEY, SERVED_MODEL


async def run(args):
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    results=[];errors=[];requests=[]
    user_id='duel-user-'+uuid.uuid4().hex[:12]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1360,'height':1000})
        page.set_default_timeout(20000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append({'path':r.url.split('/api/')[-1], 'model':r.headers.get('x-demo-model')}) if '/api/' in r.url and r.method=='POST' else None)
        await page.goto(args.url,wait_until='domcontentloaded')
        await page.wait_for_function('modelReady&&catalog&&showcaseKinds.length')
        await page.evaluate("JevI18n.setLanguage('zh');tab('games')")
        await page.wait_for_function('!busy&&!showcaseBusy&&showcaseSession')
        games=[]
        for group in await page.evaluate('JevGameCategories.groups.map(g=>g.id)'):
            await page.select_option('#playGameCategory',group)
            games+=await page.locator('#playQuickGame option').evaluate_all('(ns)=>ns.map(n=>n.value).filter(Boolean)')

        async def choose(kind):
            await page.evaluate('JevParticipants.stop()')
            await page.wait_for_function('!busy&&!showcaseBusy')
            await page.evaluate('(kind)=>JevSelectPlay(kind)',kind)
            await page.wait_for_function('kind=>selectedPlay===kind&&!busy&&!showcaseBusy',arg=kind)

        for kind in games:
            if kind=='mbti_text':continue
            try:
                await choose(kind)
                duel=await page.evaluate('JevParticipants.isDuel()')
                if duel:await page.select_option('#participantOpponent','oneshot-hosted')
                button='#modelMove' if await page.evaluate('JevParticipants.isBoard()') else '#showcaseModel'
                await page.click(button)
                await page.wait_for_function('!busy&&!showcaseBusy')
                assert not await page.locator('#globalError').is_visible(), await page.locator('#globalError').text_content()
                if duel:
                    await page.click('#participantStart')
                    await page.wait_for_function("(JevParticipants.isBoard()?gameState.revision:showcaseSession.revision)>=4 || !!(JevParticipants.isBoard()?gameState.game.winner:showcaseSession.world.outcome)",timeout=30000)
                    await page.evaluate('JevParticipants.stop()')
                    await page.wait_for_function('!busy&&!showcaseBusy')
                    assert not await page.locator('#globalError').is_visible(), await page.locator('#globalError').text_content()
                await page.screenshot(path=str(output/(kind+'.png')),full_page=True)
                row={'game':kind,'status':'ok','duel':duel}
            except Exception as exc:
                row={'game':kind,'status':'error','error':str(exc)[:700]}
            results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
            (output/'browser-progress.json').write_text(json.dumps({'games':results,'page_errors':errors},ensure_ascii=False,indent=2))

        await choose('othello_6x6')
        await page.evaluate('''() => {
          const originalLabel=JevParticipants.label;
          JevParticipants.label=()=>'<img src=x onerror=window.badModelName=true>';
          gameState.game.winner='X';renderGame();JevParticipants.label=originalLabel;
        }''')
        assert await page.locator('#gameOutcome img').count()==0
        assert await page.evaluate('window.badModelName !== true')

        with mock_model(args.url) as (endpoint,seen):
            await page.evaluate('JevParticipants.stop()');await page.wait_for_function('!busy&&!showcaseBusy')
            await page.click('#connectionSettings')
            for field,value in [('connectionModelId',user_id),('connectionName','User model'),('connectionServedModel',SERVED_MODEL),('connectionEndpoint',endpoint+'/decide'),('connectionApiKey',FIXTURE_KEY)]:
                await page.fill('#'+field,value)
            await page.select_option('#connectionAdapter','decision');await page.click('#connectSave')
            await page.wait_for_function('(id)=>modelName===id&&modelReady',arg=user_id);await page.click('#connectCancel')
            await page.select_option('#modelSelect','oneshot-hosted');await page.wait_for_function("modelName==='oneshot-hosted'&&modelReady")
            for kind in [r['game'] for r in results if r.get('duel')]:
                await choose(kind);await page.select_option('#participantOpponent',user_id)
                before=len(seen)
                await page.click('#participantStart')
                for _ in range(120):
                    if len(seen)>before:break
                    await page.wait_for_timeout(200)
                await page.evaluate('JevParticipants.stop()');await page.wait_for_function('!busy&&!showcaseBusy')
                assert len(seen)>before, (kind,'opponent model never called')
                assert not await page.locator('#globalError').is_visible(), (kind,await page.locator('#globalError').text_content())
                print(json.dumps({'game':kind,'other_model':'ok'}),flush=True)
            assert all(r['authorized'] and r['cookies_absent'] for r in seen)
            # A solo game can also use the visitor's model.
            await choose('merge_2048');await page.select_option('#modelSelect',user_id)
            await page.wait_for_function('(id)=>modelName===id&&modelReady',arg=user_id)
            before=len(seen);await page.click('#showcaseModel');await page.wait_for_function('!showcaseBusy')
            assert len(seen)>before
            await page.select_option('#modelSelect','oneshot-hosted');await page.wait_for_function("modelName==='oneshot-hosted'&&modelReady")
            # Human handoff: start the match, then take one legal move as seat B.
            for kind in ['othello_6x6','hex_7x7','dots_and_boxes_3x3','chess','checkers','xiangqi','uno','liars_dice','doudizhu','texas_holdem','property_tycoon','zha_jin_hua']:
                await choose(kind);await page.select_option('#participantOpponent','human');await page.click('#participantStart')
                await page.wait_for_function("JevParticipants.controller()==='human'&&!busy&&!showcaseBusy",timeout=30000)
                if await page.evaluate('!!showcaseSession?.world.handoff&&!JevParticipants.isBoard()'):
                    await page.evaluate('JevParticipants.reveal()')
                moved=await page.evaluate("async()=>{const options=JevParticipants.isBoard()?gameState.game.legal:Object.keys(showcaseSession.choices);return JevParticipants.isBoard()?play(options[0],false):showcaseStep(options[0],false)}")
                assert moved,(kind,'manual action did not execute')
                if await page.evaluate("JevParticipants.controller()!=='human' && !(JevParticipants.isBoard()?gameState.game.winner:showcaseSession.world.outcome)"):
                    revision=await page.evaluate('JevParticipants.isBoard()?gameState.revision:showcaseSession.revision')
                    await page.wait_for_function('(rev)=>(JevParticipants.isBoard()?gameState.revision:showcaseSession.revision)>rev',arg=revision)
                await page.evaluate('JevParticipants.stop()');await page.wait_for_function('!busy&&!showcaseBusy')
                print(json.dumps({'game':kind,'human':'ok'}),flush=True)
            await choose('othello_6x6')
            for width in [1360,390,320]:
                await page.set_viewport_size({'width':width,'height':900})
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                await page.screenshot(path=str(output/f'participants-{width}.png'),full_page=True)
            await page.click('#connectionSettings')
            assert await page.locator('.connected-model').filter(has_text='Piccolo').locator('.connection-remove').count()==0
            await page.request.delete(args.url+'api/v1/connections/'+user_id)
        summary={'games':results,'page_errors':errors,'user_model_calls':len(seen),'request_models':sorted(set(r['model'] for r in requests if r['model']))}
        (output/'browser-qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        await browser.close()
        assert not errors and all(r['status']=='ok' for r in results),summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8893/');parser.add_argument('--output',required=True)
    asyncio.run(run(parser.parse_args()))
