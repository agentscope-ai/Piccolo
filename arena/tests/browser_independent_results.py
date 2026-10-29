"""Read-only browser acceptance for published eight-seed results."""
import argparse
import csv
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
    assert data['schema_version']=='jev.arena.independent-results.v1'
    assert (data['completed'],data['scored'],data['errors'])==(1584,1578,6)
    findings=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for size,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
            page=browser.new_page(viewport=viewport);errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base,wait_until='domcontentloaded')
            page.locator('[data-tab="leaderboard"]').click()
            page.locator('[data-benchmark="gamejevbench"]').click()
            page.wait_for_selector('#arenaIndependent [data-independent-model]')
            # Charts and the results table fetch the same published snapshot
            # independently; the public network can settle them in either order.
            page.wait_for_function('document.querySelectorAll(".lb-radar-axis").length===22')
            for language in ('en','zh'):
                page.locator(f'[data-language="{language}"]').click()
                page.locator('#independentScope').select_option('overall')
                rows=page.locator('#arenaIndependent [data-independent-model]')
                assert rows.count()==10
                oneshot=rows.filter(has_text='Piccolo')
                assert oneshot.locator('[data-independent-score]').get_attribute('data-independent-score')==''
                assert '0.00%' not in oneshot.inner_text()
                assert page.locator('.lb-radar-axis').count()==22
                page.locator('#lbRadarDimension').select_option('-1')
                assert 'Elo' not in page.locator('.lb-bar-metric').inner_text()
                assert page.locator('[data-bar-model="oneshot-w22m05r02-v5best-avg50"]').get_attribute('data-bar-score')==''
                for game in data['fixed_config']['games']:
                    page.locator('#independentScope').select_option(game['id'])
                    assert page.locator('#arenaIndependent [data-independent-model]').count()==10
                    missing=page.locator('[data-independent-model="oneshot-w22m05r02-v5best-avg50"]')
                    assert missing.locator('[data-independent-score]').inner_text()=='—'
                page.locator('#independentScope').select_option('mario_platformer')
                start=page.locator('[data-independent-model="access-StartLux-Decision-v1.1-27B-Instant"]')
                assert start.locator('td').nth(7).inner_text()=='—'
                page.locator('#independentLatency').select_option('all')
                assert start.locator('td').nth(7).inner_text()=='10.76'
                page.locator('#independentScope').select_option('overall')
                assert page.locator('#independentLatency').input_value()=='current'
                with page.expect_download() as download:
                    page.locator('#independentDownload').click()
                target=args.out/f'{size}-{language}.csv';download.value.save_as(target)
                with target.open(encoding='utf-8-sig',newline='') as stream: exported=list(csv.DictReader(stream))
                assert len(exported)==220
                assert all(all(v=='' for k,v in r.items() if k not in ('model','game')) for r in exported if r['model']=='Piccolo')
                dims=page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                assert dims['scroll']<=dims['client']+1,dims
                assert not errors,errors
                page.screenshot(path=str(args.out/f'{size}-{language}.png'),full_page=True)
                findings.append({'size':size,'language':language,'games':22,'model_rows':10,'oneshot_blank':True,
                                 'csv_rows':220,'page_errors':len(errors),'overflow':False})
            page.close()
        browser.close()
    (args.out/'validation.json').write_text(json.dumps({'url':base,'checks':findings},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':len(findings),'game_views':len(findings)*22,'oneshot':'blank'}))


if __name__=='__main__':main()
