#!/usr/bin/env python3
"""Export every decision and continuous execution phase, including initial and terminal holds."""
import argparse
import functools
import hashlib
import http.server
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FPS = 12
COMPLETED = {'merge-2048', 'sokoban', 'tetris'}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def render(root=ROOT, game=None):
    manifest = json.loads((root/'arena/web/showcase/full-manifest.json').read_text())
    items = [x for x in manifest['items'] if game is None or x['id'] == game]
    if not items:
        raise ValueError('Unknown showcase: '+str(game))
    output = root/'assets/showcase'
    report_path = output/'render-manifest.json'
    report = {'schema_version':'blink.showcase-render.v2', 'fps':FPS, 'speed':2,
              'coverage':'Every archived decision and complete execution interval; no step selection or truncation.', 'items':[]}
    if game and report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get('schema_version') == report['schema_version']:
            report['items'] = [x for x in previous['items'] if x['id'] != game]
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(root/'arena/web')))
    worker = threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix='blink-full-') as temp:
            browser = pw.chromium.launch(headless=True,channel=os.environ.get('BLINK_BROWSER_CHANNEL'))
            page = browser.new_page(viewport={'width':940,'height':850},device_scale_factor=1)
            # Pin a fresh document for each game, including regenerated JS.
            page.route('**/*', lambda route: route.continue_())
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            for item in items:
                slug=item['id'];source=root/'arena/web/showcase'/item['trace'];clip=json.loads(source.read_text())
                page.goto(f'http://127.0.0.1:{server.server_port}/showcase.html?game={slug}')
                page.wait_for_function("document.documentElement.dataset.ready==='true'")
                for frame in page.frames:frame.evaluate('document.fonts.ready')
                segments=page.evaluate('BlinkShowcase.timeline');duration=page.evaluate('BlinkShowcase.duration')
                assert sorted({s['step'] for s in segments})==list(range(len(clip['steps'])))
                folder=Path(temp)/slug;folder.mkdir();target=output/('completed' if slug in COMPLETED else '')
                target.mkdir(parents=True,exist_ok=True)
                ordinal=0;coverage=[]
                def capture(t):
                    nonlocal ordinal
                    state=page.evaluate('(t)=>BlinkShowcase.sample(t)',t)
                    assert page.locator('#stage iframe').evaluate("f=>{const c=[...f.contentDocument.querySelectorAll('canvas')].find(c=>c.getBoundingClientRect().width>0);return c.getBoundingClientRect().bottom<=f.clientHeight+1}"), 'Clipped game canvas'
                    page.locator('#capture').screenshot(path=str(folder/f'{ordinal:05d}.png'),animations='disabled')
                    ordinal+=1
                    return state
                capture(0)
                initial=(folder/'00000.png').read_bytes()
                for _ in range(FPS//2-1):
                    (folder/f'{ordinal:05d}.png').write_bytes(initial);ordinal+=1
                for segment in segments:
                    first=ordinal;n=max(2,math.ceil((segment['end']-segment['start'])*FPS))
                    for i in range(n):
                        # Include the exact end before switching to the next phase.
                        t=segment['start']+(segment['end']-segment['start'])*i/(n-1)
                        if i==n-1 and t<duration:t=math.nextafter(t,segment['start'])
                        capture(t)
                    coverage.append({**segment,'first_frame':first,'last_frame':ordinal-1})
                capture(duration);terminal=(folder/f'{ordinal-1:05d}.png').read_bytes()
                assert terminal!=initial and page.locator('#error').inner_text()==''
                (target/f'{slug}.png').write_bytes(terminal)
                for _ in range(FPS*2-1):
                    (folder/f'{ordinal:05d}.png').write_bytes(terminal);ordinal+=1
                subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-i',str(folder/'%05d.png'),
                    '-filter_complex','split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
                    '-loop','0',str(target/f'{slug}.gif')],check=True)
                report['items'].append({'id':slug,'source':str(source.relative_to(root)),
                    'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'steps':len(clip['steps']),
                    'captured_indices':list(range(len(clip['steps']))),'frames':ordinal,'duration_seconds':ordinal/FPS,
                    'segments':coverage,'gif':str((target/f'{slug}.gif').relative_to(root))})
                report_path.write_text(json.dumps(report,indent=2)+'\n')
                completed_report = {**report, 'items': [x for x in report['items'] if x['id'] in COMPLETED]}
                (output/'completed/render-manifest.json').write_text(json.dumps(completed_report,indent=2)+'\n')
                print(json.dumps({'rendered':slug,'steps':len(clip['steps']),'frames':ordinal,'seconds':ordinal/FPS}),flush=True)
            browser.close()
            if errors:raise RuntimeError('; '.join(errors))
    finally:
        server.shutdown();server.server_close();worker.join()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--game')
    args=parser.parse_args();render(args.root,args.game)
