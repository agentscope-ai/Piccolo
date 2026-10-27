#!/usr/bin/env python3
"""Render sampled archive states with the actual completed-replay UI, without a model."""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SLUGS = {"merge_2048": "merge-2048", "sokoban_puzzle": "sokoban",
         "othello_6x6": "othello", "tetris_placement": "tetris"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def render(root: Path) -> dict:
    source = root / "arena/web/playground/data/home-decision.json"
    archive = json.loads(source.read_bytes())
    output = root / "assets/showcase/completed"
    output.mkdir(parents=True, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
        QuietHandler, directory=str(root / "arena/web")))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    report = {"schema": "blink.completed-showcase-render.v1",
              "source": str(source.relative_to(root)),
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "presentation": "Content-only cards: no completed-game banner, pager or game tabs.",
              "sampling": "State 0 is the initial state; state n is after transition n-1. Fixed 500 ms per frame; final state held for 2 seconds.",
              "items": []}
    try:
        with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix="blink-completed-") as temp:
            browser = pw.chromium.launch(headless=True, channel=os.environ.get("BLINK_BROWSER_CHANNEL"))
            page = browser.new_page(viewport={"width": 1000, "height": 1200}, device_scale_factor=1)
            page.emulate_media(reduced_motion="reduce")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/completed-showcase.html")
            page.wait_for_selector(".home-demo-timeline")
            # Export clean cards; the interactive page keeps its navigation.
            page.add_style_tag(content=".home-demo-top,.home-demo-game-tabs{display:none!important}")
            assert not page.locator('.home-demo-top').is_visible()
            assert not page.locator('.home-demo-game-tabs').is_visible()
            capture = page.locator("#homeDecisionDemo")

            def seek(position):
                if position == 0:
                    page.locator(".home-demo-reset").click()
                else:
                    page.locator(".home-demo-timeline").fill(str(position - 1))
                page.evaluate("document.fonts.ready")
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

            for game_index, clip in enumerate(archive["clips"]):
                slug = SLUGS[clip["game"]]
                page.locator(".home-demo-game-tabs button").nth(game_index).evaluate("node => node.click()")
                if clip["game"] == "tetris_placement":
                    page.wait_for_function("document.querySelector('.jev-native-replay')?.contentDocument?.querySelector('canvas')?.width > 0")
                count = len(clip["steps"]) + 1
                indices = sorted({round(i * (count - 1) / (min(count, 24) - 1)) for i in range(min(count, 24))})
                # Fix the capture height across this game, including long terminal copy.
                capture.evaluate("node => node.style.minHeight = ''")
                heights = []
                for index in indices:
                    seek(index)
                    heights.append(capture.bounding_box()["height"])
                capture.evaluate("(node, height) => node.style.minHeight = `${Math.ceil(height)}px`", max(heights))
                folder = Path(temp) / slug
                folder.mkdir()
                frames = indices + [indices[-1]] * 3
                for ordinal, index in enumerate(frames):
                    seek(index)
                    capture.screenshot(path=str(folder / f"{ordinal:03d}.png"))
                assert page.locator(".home-demo-next").is_disabled()
                assert "victory" in page.locator(".home-demo-stage-copy").last.inner_text()
                capture.screenshot(path=str(output / f"{slug}.png"))
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "2",
                                "-i", str(folder / "%03d.png"), "-filter_complex",
                                "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                                "-loop", "0", str(output / f"{slug}.gif")], check=True)
                report["items"].append({"game": clip["game"], "model": clip["models"][0],
                                        "episode_id": clip["episode_id"], "seed": clip["seed"],
                                        "states": count, "captured_state_indices": frames,
                                        "poster_state_index": count - 1, "frame_duration_ms": 500,
                                        "gif": f"assets/showcase/completed/{slug}.gif",
                                        "poster": f"assets/showcase/completed/{slug}.png"})
                print(json.dumps({"rendered": slug, "frames": len(frames)}), flush=True)
            browser.close()
            if errors:
                raise RuntimeError("Browser errors: " + "; ".join(errors))
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    (output / "render-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    render(parser.parse_args().root)
