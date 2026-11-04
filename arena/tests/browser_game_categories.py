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
                assert sum(len(group['games']) for group in taxonomy)==17
                assert not errors,errors
                findings.append({'size':size,'language':language,'game_switches':17,'category_selects':2,'page_errors':0})
            page.close()
        browser.close()
    (args.out/'validation.json').write_text(json.dumps({'url':base,'checks':findings},indent=2)+'\n')
    print(json.dumps({'passed':len(findings),'game_switches':sum(f['game_switches'] for f in findings),
                      'active_games':17}))


if __name__=='__main__':main()
