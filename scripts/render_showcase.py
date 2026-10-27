#!/usr/bin/env python3
"""Capture original game renderers from exported trajectories into README assets."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def render(root: Path, game: str | None = None) -> dict:
    manifest = json.loads((root / 'arena/web/showcase/manifest.json').read_text())
    output = root / 'assets/showcase'
    output.mkdir(parents=True, exist_ok=True)
    selected = [item for item in manifest['items'] if game is None or item['id'] == game]
    if not selected:
        raise ValueError('Unknown showcase: ' + str(game))
    handler = functools.partial(QuietHandler, directory=str(root / 'arena/web'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    result = {'schema_version': 'blink.showcase-render.v1',
              'presentation': 'Game title and recorded states; no generic showcase banner or badge.', 'items': []}
    if game and (output / 'render-manifest.json').exists():
        previous = json.loads((output / 'render-manifest.json').read_text())
        result['items'] = [item for item in previous['items'] if item['id'] != game]
    try:
        with sync_playwright() as playwright, tempfile.TemporaryDirectory(prefix='blink-showcase-') as work:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'],
                                                 channel=os.environ.get('BLINK_BROWSER_CHANNEL'))
            page = browser.new_page(viewport={'width': 940, 'height': 940}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for item in selected:
                slug = item['id']
                page.goto(f'http://127.0.0.1:{server.server_port}/showcase.html?game={slug}')
                page.wait_for_function("document.documentElement.dataset.ready === 'true'")
                page.add_style_tag(content='.card-head .eyebrow,.card-head .badge{display:none!important}.card-head h2{margin:0}')
                count = page.evaluate('window.BlinkShowcase.count')
                indices = sorted({round(i * (count - 1) / (min(count, 24) - 1)) for i in range(min(count, 24))})
                folder = Path(work) / slug
                folder.mkdir()
                first_frame = None
                for ordinal, index in enumerate(indices):
                    page.evaluate('(index)=>window.BlinkShowcase.seek(index)', index)
                    for frame in page.frames:
                        frame.evaluate('document.fonts.ready')
                    frame = page.locator('#capture').screenshot(path=str(folder / f'{ordinal:03d}.png'))
                    if ordinal == 0:
                        first_frame = frame
                assert first_frame != frame, (slug, 'unchanged initial and final frames')
                assert page.locator('#error').inner_text() == ''
                # Keep the original final result in the trace; the poster is only a middle frame.
                poster = indices[len(indices) // 2]
                page.evaluate('(index)=>window.BlinkShowcase.seek(index)', poster)
                page.locator('#capture').screenshot(path=str(output / f'{slug}.png'))
                subprocess.run([
                    'ffmpeg', '-v', 'error', '-y', '-framerate', '2', '-i', str(folder / '%03d.png'),
                    '-filter_complex', 'split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
                    '-loop', '0', str(output / f'{slug}.gif'),
                ], check=True)
                result['items'].append({'id': slug, 'saved_states': count, 'captured_indices': indices,
                                        'poster_index': poster, 'frame_duration_ms': 500,
                                        'gif': f'assets/showcase/{slug}.gif'})
                print(json.dumps({'rendered': slug, 'frames': len(indices)}), flush=True)
            browser.close()
            if errors:
                raise RuntimeError('Browser errors: ' + '; '.join(errors))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    (output / 'render-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--game', help='Render only this game and retain other frame manifests')
    args = parser.parse_args()
    render(args.root, args.game)
