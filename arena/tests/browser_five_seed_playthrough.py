"""Play the real Playground to native terminal states using its hosted model.

No fake model, engine shortcuts, altered physics, or hidden-state decisions.
Outputs live receipts and screenshots; interrupted batches can be resumed.
"""
import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import time

from playwright.async_api import async_playwright

STATE = r'''() => {
 const board=JevParticipants.isBoard(),world=showcaseKind?.mode==='world'&&showcaseKind.kind===selectedPlay;
 const g=board?gameState?.game:world?worldBridge()?.snapshot(false):showcaseSession?.world;
 const outcome=board?g?.winner:g?.outcome||(g?.episode_terminal?(g.wins>0?'win':'loss'):null);
 const visible=n=>!!n&&n.getBoundingClientRect().width>0&&n.getBoundingClientRect().height>0&&getComputedStyle(n).visibility!=='hidden';
 const canvases=[...document.querySelectorAll('#gamesView canvas')].filter(visible).map(n=>({id:n.id,width:n.width,height:n.height,painted:n.getContext('2d').getImageData(0,0,n.width,n.height).data.some((v,i)=>i%4===3&&v>0)}));
 const view=world?worldFrame():board?document.getElementById('board'):[...document.querySelectorAll('#chessStage,#selectedGameBoard,.selected-game,#showcaseCanvas,#agentGameStage')].find(visible);
 const box=view?.getBoundingClientRect();
 return {game:selectedPlay,board,world,terminal:!!outcome,outcome:outcome||null,state:g,engine_limit:showcaseKind?.engine?.limit,
  revision:board?gameState?.revision:world?g?.decisions:showcaseSession?.revision,
  actor:JevParticipants.isDuel()?JevParticipants.actor():0,controller:JevParticipants.controller(),
  error:!document.getElementById('globalError').classList.contains('hidden')?document.getElementById('globalError').textContent:null,
  busy:busy||showcaseBusy,canvases,overflow:document.documentElement.scrollWidth>innerWidth+1,
  surface:box?{width:box.width,height:box.height}:null,
  seed:world?worldBridge().condition().seed:board?gameState?.environment?.seed:showcaseSession?.environment?.seed,
  outcome_visible:visible(document.getElementById(board?'gameOutcome':'showcaseOutcome')),
  buttons:{step_disabled:document.getElementById(board?'modelMove':'showcaseModel').disabled,
   restart_disabled:document.getElementById(board?'newGame':'showcaseNew').disabled}};
}'''


def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


async def run(args):
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    summary_path=output/'summary.json'
    expected=json.loads(Path(args.expected_rules).read_text()) if args.expected_rules else {}
    saved=json.loads(summary_path.read_text()) if summary_path.exists() else {'runs':[]}
    completed={(r['game'],r['seed']) for r in saved['runs'] if (r.get('terminal') or r.get('status')=='budget_exhausted') and not r.get('errors')}
    active={};started=time.time()
    def save():
        write(summary_path,{'started_at':saved.get('started_at',started),'updated_at':time.time(),
          'backend':'https://decisionplayground.agentscope.io/api/v1/decisions',
          'games':args.games,'seeds':args.seeds,'expected_rules':expected,'opponent':'native_rule','concurrency':args.concurrency,
          'runs':saved['runs'],'active':list(active.values())})
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows'])
        queue=asyncio.Queue()
        # The first pass covers every game before repeating seeds.
        for seed in args.seeds:
            for game in args.games:
                if (game,seed) not in completed:queue.put_nowait((game,seed))
        async def worker(index):
            while not queue.empty():
                try:game,seed=queue.get_nowait()
                except asyncio.QueueEmpty:return
                key=f'{game}-{seed}';previous=next((r for r in saved['runs'] if (r['game'],r['seed'])==(game,seed)),None)
                attempts=[int(p.name.split('-')[-1]) for p in (output/'runs'/key).glob('attempt-*') if p.is_dir() and p.name.split('-')[-1].isdigit()]
                attempt=max(attempts+[previous.get('attempt',1) if previous else 0])+1
                folder=output/'runs'/key/f'attempt-{attempt}';folder.mkdir(parents=True,exist_ok=True)
                row={'game':game,'seed':seed,'status':'running','started_at':time.time(),'worker':index,'attempt':attempt,'artifacts':str(folder),'steps':0,'errors':[],'display_issues':[],'model_calls':0,'model_seconds':[]}
                active[index]=row;save()
                page=await browser.new_page(viewport={'width':1440,'height':1050})
                page.set_default_timeout(20000)
                page.on('pageerror',lambda e,row=row:row['errors'].append({'type':'pageerror','message':str(e)[:500]}))
                tasks=set()
                async def response(resp):
                    if resp.request.method!='POST' or '/api/' not in resp.url:return
                    path=resp.url.split('/api/')[-1]
                    if path not in ['game/move','showcases/step','showcases/world'] and not path.endswith('/steps'):return
                    try:
                        data=await resp.json()
                        result=data.get('result') or data.get('model_decision')
                        if result:
                            row['model_calls']+=1
                            if isinstance(result.get('latency_seconds'),(int,float)):row['model_seconds'].append(result['latency_seconds'])
                        receipt={'at':time.time(),'path':path,'status':resp.status,'data':data}
                        with (folder/'responses.jsonl').open('a') as f:f.write(json.dumps(receipt,ensure_ascii=False)+'\n')
                        if resp.status>=400:row['errors'].append({'type':'http','path':path,'status':resp.status,'code':data.get('detail',{}).get('code') if isinstance(data.get('detail'),dict) else None})
                    except Exception as e:row['errors'].append({'type':'receipt','error_type':type(e).__name__})
                def capture(resp):
                    task=asyncio.create_task(response(resp));tasks.add(task);task.add_done_callback(tasks.discard)
                page.on('response',capture)
                last=None
                async def check_visual(state,tag):
                    findings=[]
                    if state['overflow']:findings.append('horizontal_overflow')
                    if any(not c['painted'] for c in state['canvases']):findings.append('blank_canvas')
                    if not state['surface'] or state['surface']['width']<10 or state['surface']['height']<10:findings.append('missing_game_surface')
                    if state['terminal'] and not state['outcome_visible']:findings.append('terminal_banner_missing')
                    for finding in findings:
                        if finding not in row['display_issues']:row['display_issues'].append(finding)
                    if findings or tag in ['initial','terminal','middle']:
                        await page.screenshot(path=str(folder/(tag+'.png')),full_page=True)
                try:
                    await page.goto(args.url,wait_until='domcontentloaded')
                    await page.wait_for_function('modelReady&&catalog&&showcaseKinds.length&&!busy&&!showcaseBusy')
                    await page.evaluate("JevI18n.setLanguage('zh');tab('games')")
                    await page.wait_for_function('!busy&&!showcaseBusy&&showcaseSession')
                    await page.evaluate('(kind)=>JevSelectPlay(kind)',game)
                    await page.wait_for_function('kind=>selectedPlay===kind&&!busy&&!showcaseBusy',arg=game)
                    duel=await page.evaluate('JevParticipants.isDuel()')
                    if duel:
                        await page.select_option('#participantFirst','oneshot-hosted')
                        await page.select_option('#participantOpponent','rule')
                        if game=='doudizhu':await page.select_option('#participantThird','rule')
                    await page.wait_for_function('!busy&&!showcaseBusy')
                    await page.locator('.workspace-environment > summary').click()
                    await page.fill('#playSeed',str(seed));await page.click('#playSeedApply')
                    await page.locator('.workspace-environment > summary').click()
                    await page.wait_for_function('!busy&&!showcaseBusy')
                    last=await page.evaluate(STATE)
                    assert last['seed']==seed,('seed_not_applied',last['seed'])
                    for key,value in expected.get(game,{}).items():
                        actual=last.get(key) if key=='engine_limit' else last['state'].get(key)
                        assert actual==value,('unexpected_game_rule',game,key,actual,value)
                    if game in expected:row['rules']=expected[game]
                    write(folder/'initial-state.json',last);await check_visual(last,'initial')
                    budget=await page.evaluate('showcaseKind?.engine?.limit || 300')
                    stalled=0
                    while not last['terminal']:
                        if last['world'] and (last['state'].get('decisions') or 0)>=budget:
                            row.update(status='budget_exhausted',outcome='budget_exhausted',decision_budget=budget);break
                        if time.time()-row['started_at']>args.max_minutes*60:
                            row['status']='audit_time_limit';break
                        if row['steps']>=args.max_steps:
                            row['status']='audit_step_limit';break
                        # These are the same public step handlers used by the buttons.
                        # Calling the handler avoids Playwright's scroll delay affecting real-time survival.
                        ok=await page.evaluate("async()=>JevParticipants.isBoard()?await play(null,true):await showcaseStep(null,true)")
                        await page.wait_for_function('!busy&&!showcaseBusy',timeout=120000)
                        row['steps']+=1
                        new=await page.evaluate(STATE)
                        if new['error']:
                            row['errors'].append({'type':'visible_error','message':new['error'][:500],'step':row['steps']})
                        stalled=stalled+1 if not ok and not new['terminal'] else 0
                        if row['steps']==5:await check_visual(new,'middle')
                        with (folder/'states.jsonl').open('a') as f:f.write(json.dumps({'step':row['steps'],'recorded_at':time.time(),**new},ensure_ascii=False)+'\n')
                        last=new;active[index]={**row,'frame':last['state'].get('frame'),'outcome':last['outcome']};save()
                        if stalled>=3:
                            row['status']='stalled';break
                        await asyncio.sleep(.05)
                    if last['terminal']:row.update(status='complete',terminal=True,outcome=last['outcome'])
                    else:row.update(terminal=False,outcome=row.get('outcome') or last['outcome'])
                    write(folder/'final-state.json',last);await check_visual(last,'terminal' if last['terminal'] else 'stalled')
                    # Terminal controls should allow an immediate new episode.
                    if last['terminal'] and last['buttons']['restart_disabled']:row['display_issues'].append('restart_disabled_after_terminal')
                except Exception as e:
                    row.update(status='audit_error',terminal=False,error_type=type(e).__name__,error=str(e)[:700])
                    row['errors'].append({'type':'script','error_type':type(e).__name__})
                    try:await page.screenshot(path=str(folder/'audit-error.png'),full_page=True)
                    except Exception:pass
                finally:
                    try:await page.evaluate('stopAuto()')
                    except Exception:pass
                    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
                    row['seconds']=round(time.time()-row['started_at'],3)
                    row['mean_response_seconds']=round(sum(row['model_seconds'])/len(row['model_seconds']),3) if row['model_seconds'] else None
                    row.pop('model_seconds',None)
                    write(folder/'result.json',row)
                    saved['runs']=[r for r in saved['runs'] if (r['game'],r['seed'])!=(game,seed)]+[row]
                    active.pop(index,None);save()
                    print(json.dumps(row,ensure_ascii=False),flush=True)
                    await page.close();queue.task_done()
        try:await asyncio.gather(*(worker(i) for i in range(args.concurrency)))
        finally:await browser.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='http://127.0.0.1:8768/');p.add_argument('--output',required=True)
    p.add_argument('--games',nargs='+',required=True);p.add_argument('--seeds',nargs='+',type=int,default=[101,202,303,404,505])
    p.add_argument('--concurrency',type=int,default=2);p.add_argument('--max-minutes',type=float,default=35)
    p.add_argument('--max-steps',type=int,default=1100)
    p.add_argument('--expected-rules',help='JSON file of required initial-state fields, checked before any model call')
    asyncio.run(run(p.parse_args()))
