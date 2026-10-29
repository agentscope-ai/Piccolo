"""Check the two native selectors and four uncluttered radar quadrants."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    base=args.url.rstrip('/')
    data=json.load(urlopen(base+'/api/elo',timeout=30))
    findings=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for size,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
            page=browser.new_page(viewport=viewport);errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base,wait_until='domcontentloaded')
            page.locator('[data-tab="games"]').click()
            page.wait_for_function('document.querySelectorAll("#playQuickGame option").length>1')
            for language in ('en','zh'):
                page.locator(f'[data-language="{language}"]').click()
                taxonomy=page.evaluate('window.JevGameCategories.groups')
                assert page.locator('#playGameCategory option').count()==4
                assert page.locator('#playGameCategories button').count()==0
                model=page.locator('#modelSelect').input_value()
                for group in taxonomy:
                    before=page.evaluate('selectedPlay')
                    page.locator('#playGameCategory').select_option(group['id'])
                    assert page.evaluate('selectedPlay')==before
                    options=page.locator('#playQuickGame option:not([value=""])').evaluate_all('nodes=>nodes.map(n=>n.value)')
                    assert set(options)==set(group['games']),(group['id'],options)
                    for kind in options:
                        page.locator('#playQuickGame').select_option(kind)
                        page.wait_for_function('kind=>selectedPlay===kind&&!busy&&!showcaseBusy',arg=kind)
                        assert page.locator('#playGameCategory').input_value()==group['id']
                        assert page.locator('#modelSelect').input_value()==model
                page.locator('#playGameCategory').select_option('realtime')
                page.locator('#playQuickGame').select_option('snake_navigation')
                page.wait_for_function('selectedPlay==="snake_navigation"&&!busy&&!showcaseBusy')
                page.evaluate('document.fonts.ready')
                assert page.evaluate('document.fonts.check("16px NotoGameEmoji", "🐍")')
                positions=page.locator('#playGameCategory,#playQuickGame').evaluate_all('nodes=>nodes.map(n=>({y:n.getBoundingClientRect().y,x:n.getBoundingClientRect().x,w:n.getBoundingClientRect().width}))')
                assert abs(positions[0]['y']-positions[1]['y'])<2 and positions[0]['x']+positions[0]['w']<=positions[1]['x']
                page.screenshot(path=str(args.out/f'{size}-{language}-playground.png'),full_page=True)
                page.locator('[data-tab="leaderboard"]').click()
                page.locator('[data-benchmark="gamejevbench"]').click()
                page.wait_for_function('document.querySelectorAll("[data-radar-group]").length===4')
                assert page.locator('.lb-radar-group-arc').count()==0
                assert page.locator('.lb-radar-axis').count()==22
                overlaps=page.locator('.lb-radar-axis,.lb-radar-group-label').evaluate_all('nodes=>{const a=nodes.map(n=>({text:n.textContent,r:n.getBoundingClientRect()})),out=[];for(let i=0;i<a.length;i++)for(let j=i+1;j<a.length;j++){const x=a[i].r,y=a[j].r;if(Math.min(x.right,y.right)-Math.max(x.left,y.left)>2&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>2)out.push([a[i].text,a[j].text]);}return out;}')
                assert not overlaps,overlaps
                page.locator('#lbRadarDimension').select_option('-1')
                assert 'Elo' in page.locator('.lb-bar-metric').inner_text()
                assert page.locator('#gameEloPanel .elo-table thead th').count()==7
                dims=page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                assert dims['scroll']<=dims['client']+1,dims
                assert not errors,errors
                page.screenshot(path=str(args.out/f'{size}-{language}-radar.png'),full_page=True)
                findings.append({'size':size,'language':language,'game_switches':22,'category_selects':2,
                                 'radar_groups':4,'overlapping_labels':0,'columns':7,'page_errors':0})
                page.locator('[data-tab="games"]').click()
            page.close()
        browser.close()
    (args.out/'validation.json').write_text(json.dumps({'url':base,'checks':findings},indent=2)+'\n')
    print(json.dumps({'passed':len(findings),'game_switches':sum(f['game_switches'] for f in findings),
                      'radar_groups':4,'overlapping_labels':0}))


if __name__=='__main__':main()
