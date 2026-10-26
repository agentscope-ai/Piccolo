#!/usr/bin/env python3
"""Capture original game renderers from exported trajectories into README assets."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
from pathlib import Path
import subprocess
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def render(root: Path) -> dict:
    manifest = json.loads((root / 'arena/web/showcase/manifest.json').read_text())
    output = root / 'assets/showcase'
    output.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(QuietHandler, directory=str(root / 'arena/web'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    result = {'schema_version': 'blink.showcase-render.v1', 'items': []}
    try:
        with sync_playwright() as playwright, tempfile.TemporaryDirectory(prefix='blink-showcase-') as work:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 940, 'height': 940}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for item in manifest['items']:
                slug = item['id']
                page.goto(f'http://127.0.0.1:{server.server_port}/showcase.html?game={slug}')
                page.wait_for_function("document.documentElement.dataset.ready === 'true'")
                count = page.evaluate('window.BlinkShowcase.count')
                indices = sorted({round(i * (count - 1) / (min(count, 24) - 1)) for i in range(min(count, 24))})
                folder = Path(work) / slug
                folder.mkdir()
                for ordinal, index in enumerate(indices):
                    page.evaluate('(index)=>window.BlinkShowcase.seek(index)', index)
                    for frame in page.frames:
                        frame.evaluate('document.fonts.ready')
                    page.locator('#capture').screenshot(path=str(folder / f'{ordinal:03d}.png'))
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
    render(parser.parse_args().root)
