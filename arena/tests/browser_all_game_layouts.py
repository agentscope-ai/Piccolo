"""Inspect each shipped game's desktop/mobile initial rendering without model calls."""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from browser_five_seed_playthrough import STATE, write


async def run(a):
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);rows=[];errors=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True,args=['--no-sandbox'], **({'executable_path': a.browser_executable} if a.browser_executable else {}))
        page=await b.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(a.url,wait_until='domcontentloaded')
        await page.wait_for_function('catalog&&showcaseKinds.length&&!busy&&!showcaseBusy')
        await page.evaluate("lang=>{JevI18n.setLanguage(lang);tab('games')}",a.lang)
        await page.wait_for_function('!busy&&!showcaseBusy&&showcaseSession')
        games=await page.evaluate('JevGameCategories.groups.flatMap(g=>g.games)')
        for width in a.widths:
            await page.set_viewport_size({'width':width,'height':1050})
            for game in games:
                try:
                    await page.evaluate('(g)=>JevSelectPlay(g)',game)
                    await page.wait_for_function('g=>selectedPlay===g&&!busy&&!showcaseBusy',arg=game)
                    await page.wait_for_timeout(150)
                    s=await page.evaluate(STATE)
                    row={k:v for k,v in s.items() if k not in ['state','seed','revision']};row['width']=width
                    row['scene_fits']=bool(s['surface'] and 0<s['surface']['width']<=width)
                    row['visible_surfaces']=await page.evaluate('''()=>[...document.querySelectorAll('#board,#showcaseCanvas,#selectedGameBoard,#chessStage,#agentGameStage,#marioFrame,#terrariaFrame')].filter(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(n).visibility!=='hidden'}).map(n=>n.id)''')
                    row['overlapping_actions']=await page.evaluate('''()=>{const buttons=[...document.querySelectorAll('#showcaseActions button')].filter(n=>n.getBoundingClientRect().height).map(n=>({text:n.textContent,r:n.getBoundingClientRect()})),out=[];for(let i=0;i<buttons.length;i++)for(let j=i+1;j<buttons.length;j++){const a=buttons[i].r,b=buttons[j].r;if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)out.push([buttons[i].text,buttons[j].text]);}return out;}''')
                    # Iframe worlds paint inside their own document.
                    if s['world']:
                        paint=await page.evaluate('''()=>{const c=worldFrame().contentDocument.querySelector('canvas');return !!c&&c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0)}''')
                        row['iframe_painted']=paint
                    await page.screenshot(path=str(out/f'{game}-{width}.png'),full_page=True)
                except Exception as e:row={'game':game,'width':width,'error_type':type(e).__name__,'error':str(e)[:400]}
                rows.append(row);write(out/'layouts.json',{'checks':rows,'page_errors':errors,'model_calls':0})
                print(json.dumps({k:v for k,v in row.items() if k in ['game','width','error','overflow','surface','iframe_painted','canvases']},ensure_ascii=False),flush=True)
        await b.close()
        assert not errors,errors
        assert all(not r.get('error') and r.get('scene_fits') and len(r.get('visible_surfaces',[]))==1 and not r.get('overlapping_actions') and not r.get('overflow') and r.get('iframe_painted',True) and all(c['painted'] for c in r.get('canvases',[])) for r in rows),rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8768/');p.add_argument('--output',required=True)
    p.add_argument('--widths',type=int,nargs='+',default=[1440,1024,768,390,320])
    p.add_argument('--lang',choices=['en','zh'],default='zh')
    p.add_argument('--browser-executable')
    asyncio.run(run(p.parse_args()))
