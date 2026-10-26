<p align="center"><img src="arena/web/playground/logos/blink.svg" width="72" alt="Blink"></p>

<h1 align="center">Blink</h1>
<p align="center"><strong>Decisions, in motion.</strong></p>
<p align="center">[English] · <a href="README_zh.md">简体中文</a> · <a href="arena/README.md">Blink Arena</a> · <a href="docs/SHOWCASE.md">Trajectory provenance</a> · <a href="skills/blink-safety-review/SKILL.md">Safety review skill</a></p>

Blink brings together an interactive playground, shared game engines, and inspectable decision trajectories. **The model release is in preparation.** Model selection, weights, inference, and training will be added once finalized; `inference/` and `training/` are intentionally empty.

## Showcase

These previews are rendered from trajectories already included in the Arena, using its original game renderers. They show **historical experiments**, not the performance of an upcoming Blink model. Playback samples saved decision states at a fixed pace, not original wall-clock timing.

<table>
  <tr>
    <td width="50%"><a href="arena/web/showcase/traces/othello.json"><img src="assets/showcase/othello.gif" alt="Archived Othello trajectory"></a><br><strong>Othello</strong> · turn-by-turn board decisions</td>
    <td width="50%"><a href="arena/web/showcase/traces/merge-2048.json"><img src="assets/showcase/merge-2048.gif" alt="Archived 2048 trajectory"></a><br><strong>2048</strong> · merge, make space, reach the target</td>
  </tr>
  <tr>
    <td width="50%"><a href="arena/web/showcase/traces/jump-jump.json"><img src="assets/showcase/jump-jump.gif" alt="Archived Jump Jump trajectory"></a><br><strong>Jump Jump</strong> · choose the next landing</td>
    <td width="50%"><a href="arena/web/showcase/traces/tetris.json"><img src="assets/showcase/tetris.gif" alt="Archived Tetris trajectory"></a><br><strong>Tetris</strong> · recorded placement decisions, including failure</td>
  </tr>
</table>

Click a preview to inspect its trajectory JSON. The [source manifest](arena/web/showcase/manifest.json) retains original participant IDs, recording types, and outcomes. [Showcase notes](docs/SHOWCASE.md) explain frame selection and reproduction.

## Run Blink Arena

Requires Python 3.12 and Node.js 22. No model is needed to browse historical results, replay trajectories, or play manually.

```bash
cd arena
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
bash scripts/run.sh
```

Open **http://127.0.0.1:8080/** for the playground and **http://127.0.0.1:8080/showcase.html** for the trajectory player. To connect an existing model service, use the page's model connection form; see the [Arena API](arena/docs/API.md).

The Arena includes the frontend, HTTP API, shared engines, imported benchmark results, and archived replays. Historical participant IDs and wire formats are retained for traceability; interface branding is Blink / Blink Arena. Third-party benchmark names retain their original names.

## Safety review skill

[blink-safety-review](skills/blink-safety-review/SKILL.md) prepares Blink for action safety review in QwenPaw: download a configured model release, submit a proposed tool action to a local decision service, and obtain `allow`, `ask_user`, or `deny` advice. It includes an optional ToolGuard adapter and QwenPaw import instructions.

The model release descriptor is deliberately unconfigured. **No model is downloaded or activated by default.** Enabling a skill does not itself install a host-level approval hook; model-backed activation follows the [integration instructions](skills/blink-safety-review/references/qwenpaw.md) once the model and serving adapter are available.

## Repository

```text
arena/                      Blink Arena frontend, API, shared engines and replays
assets/showcase/             Trajectory GIFs, posters and frame manifest
docs/                       Provenance, repository notes and verification
scripts/                    Reproduce showcase data and images
skills/blink-safety-review/  QwenPaw-ready action review skill and integration adapter
inference/                  Reserved; no implementation yet
training/                   Reserved; no implementation yet
```

## Reproduce the showcase

Install Playwright and its Chromium browser, and make `ffmpeg` available. Then, from the repository root:

```bash
python scripts/export_showcase.py
python scripts/render_showcase.py
```

The exporter copies exact archived streams. The renderer starts a temporary loopback-only asset server, captures the existing frontend renderers, and stops the server when complete. It makes no model calls.

## Development and attribution

Arena setup and checks: [arena/README.md](arena/README.md). Current verification: [docs/VERIFICATION.md](docs/VERIFICATION.md). Component sources, game libraries, fonts, and their licenses: [third-party notes](arena/docs/THIRD_PARTY.md). A project-wide code license and model-weight terms have not yet been selected; existing third-party notices remain in place.
