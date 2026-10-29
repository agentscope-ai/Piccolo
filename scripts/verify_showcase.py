#!/usr/bin/env python3
"""Check all complete replays, candidate selection, actual canvas bounds, seeking and restart."""
import functools
import http.server
import json
import os
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from render_showcase import QuietHandler, ROOT

out=ROOT/'var/full-showcase-check';out.mkdir(parents=True,exist_ok=True)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'arena/web')))
worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start();base=f'http://127.0.0.1:{server.server_port}'
report={'replays':[],'errors':[],'external_requests':[]}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,channel=os.environ.get('BLINK_BROWSER_CHANNEL'))
  for width in (1440,390):
   page=browser.new_page(viewport={'width':width,'height':1000})
   page.on('pageerror',lambda e:report['errors'].append(str(e)))
   def route(r):
    if r.request.url.startswith(base):r.continue_()
    else:report['external_requests'].append(r.request.url);r.abort()
   page.route('**/*',route)
   for item in json.loads((ROOT/'arena/web/showcase/full-manifest.json').read_text())['items']:
    slug=item['id'];clip=json.loads((ROOT/'arena/web/showcase'/item['trace']).read_text())
    page.goto(base+'/showcase.html?game='+slug);page.wait_for_function("document.documentElement.dataset.ready==='true'")

    for frame in page.frames:frame.evaluate('document.fonts.ready')
    page.evaluate('PiccoloShowcase.sample(0)')
    initial=page.locator('#stage').screenshot();timeline=page.evaluate('PiccoloShowcase.timeline');duration=page.evaluate('PiccoloShowcase.duration')
    assert sorted({x['step'] for x in timeline})==list(range(len(clip['steps'])))
    for segment in timeline:
     if segment['phase']!='execute':continue
     step=clip['steps'][segment['step']];page.evaluate('(t)=>PiccoloShowcase.sample(t)',(segment['start']+segment['end'])/2)
     assert page.locator('#candidates .candidate').all_text_contents()==step['candidates']
     if step['action'] is not None:
      assert page.locator('#candidates .selected').inner_text()==str(step['action'])
    # A canvas must fit inside its iframe: tall boards must never be cropped.
    assert page.locator('#stage iframe').evaluate('''f=>{const c=[...f.contentDocument.querySelectorAll('canvas')].find(c=>c.getBoundingClientRect().width>0);const r=c.getBoundingClientRect();return r.bottom<=f.clientHeight+1&&r.right<=f.clientWidth+1}'''),(slug,width,'clipped canvas')
    page.locator('#seek').focus();page.locator('#seek').press('End');assert 'Replay complete' in page.locator('#feedback').inner_text(),(slug,width,'slider end')
    assert initial!=page.locator('#stage').screenshot()
    assert not page.locator('.card-head').is_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#capture').screenshot(path=str(out/f'{slug}-final-{width}.png'))
    page.locator('#restart').click();assert page.locator('#seek').input_value()=='0'
    reset=page.locator('#stage').screenshot()
    if reset!=initial:
     (out/f'{slug}-initial-{width}.png').write_bytes(initial);(out/f'{slug}-reset-{width}.png').write_bytes(reset)
    assert reset==initial,(slug,width,'reset pixels')
    page.locator('#play').click();page.wait_for_timeout(150);assert float(page.locator('#seek').input_value())>0;page.locator('#play').click()
    assert page.locator('#error').inner_text()==''
    report['replays'].append({'game':slug,'width':width,'steps':len(clip['steps']),'all_selected_options':True,'canvas_fits':True,'seek_restart_play':True})
   page.evaluate("async()=>{await Promise.all(['hex','tetris','snake'].map(id=>PiccoloShowcase.load(id)))}")
   assert page.evaluate('PiccoloShowcase.id')=='snake'
   assert page.locator('#game-title').inner_text()=='Snake'
   page.close()
  browser.close()
 assert not report['errors'] and not report['external_requests'],report
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'cases':len(report['replays']),'errors':report['errors'],'external_requests':report['external_requests']}))
finally:server.shutdown();server.server_close();worker.join()
