<p align="center"><img src="arena/web/playground/logos/blink.svg" width="72" alt="Piccolo"></p>

<h1 align="center">Piccolo</h1>
<p align="center"><strong>Decisions, in motion.</strong></p>
<p align="center"><a href="https://decisionplayground.agentscope.io/">Decision · Website</a> · English / <a href="README_zh.md">简体中文</a> · <a href="docs/piccolo-blog.md">Blog 中文</a> · <a href="arena/README.md">Arena docs</a></p>

Piccolo connects **observation, action, and feedback** in an inspectable decision loop. Its Arena brings together interactive games, shared environment rules, model evaluation, and replayable trajectories. Explore the [Decision website](https://decisionplayground.agentscope.io/), or run the included Arena locally.

**Release status:** Piccolo-4B, Piccolo-9B, and Piccolo-27B are published as complete checkpoints, Q8_0 GGUFs, and Q4_K_M GGUFs. See [published models and QwenPaw setup](docs/MODELS.md). Training recipes and formal task benchmarks remain **coming soon**. Historical Arena checkpoint names identify the recorded experiments and do not establish results for this model release.

## See decisions unfold

Eight complete historical replays in one gallery, with recorded candidate probabilities on the right. The interactive players support pausing, seeking, and inspecting every decision.

<table>
  <tr>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/mario.json"><img src="assets/showcase/mario.gif" width="100%" alt="Mario"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/snake.json"><img src="assets/showcase/snake.gif" width="100%" alt="Snake"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/merge-2048.gif" width="100%" alt="2048 · target 128"></a></td>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/sokoban.gif" width="100%" alt="Sokoban"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/playground/data/home-decision.json"><img src="assets/showcase/completed/tetris.gif" width="100%" alt="Tetris"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/jump-jump.json"><img src="assets/showcase/jump-jump.gif" width="100%" alt="Jump Jump"></a></td>
  </tr>
  <tr>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/hex.json"><img src="assets/showcase/hex.gif" width="100%" alt="Hex"></a></td>
    <td width="50%" align="center"><a href="arena/web/showcase/traces/dots-and-boxes.json"><img src="assets/showcase/dots-and-boxes.gif" width="100%" alt="Dots &amp; Boxes"></a></td>
  </tr>
</table>

These are **historical examples**, not an aggregate success rate or a comparison between models. The examples preserve recorded actions, states, and outcomes from existing archives. GIFs sample saved states at a fixed pace, so their speed is not inference latency. See [provenance and reproduction](docs/SHOWCASE.md) for original identities and outcomes. [Earlier trajectories](arena/web/showcase/manifest.json), including a failed Tetris run, remain available.

## Try it

### Preview the showcase

Python 3 is sufficient for this static, read-only preview:

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory arena/web
```

Open **http://127.0.0.1:8080/completed-showcase.html** for the four completed replays, or **http://127.0.0.1:8080/showcase.html** for the other archived examples. No model, API key, or backend service is needed. Stop this server before starting Arena on the same port.

### Run Piccolo Arena

Use Python 3.12 and Node.js 22:

```bash
cd arena
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
bash scripts/run.sh
```

Open **http://127.0.0.1:8080/** to play manually, browse imported benchmark results, and inspect replays. A model service is optional. To connect one, use the model connection form and the [API contract](arena/docs/API.md); the service must allow the browser origin through CORS. See [Arena setup](arena/README.md), [shared engines](arena/docs/ENGINE.md), and [rollout API](arena/docs/ROLLOUT.md) for integration details.

## What's included

| Component | Available now | Next release |
| --- | --- | --- |
| Arena | Frontend, HTTP API, shared game engines, archived results and replays | See [Arena docs](arena/README.md) for supported behavior |
| Model | Historical identities remain attached to their replays | [Model card, weights and terms](models/README.md) |
| Inference | Arena can connect to an existing compatible service | [Piccolo model serving recipe](inference/README.md) |
| Training and data | Shared environment and rollout interfaces | [Training recipe](training/README.md), [data release](data/README.md) |
| Evaluation | Existing Arena evaluation code and historical result files | [Release-specific settings and results](evaluation/README.md) |
| Examples | Manual play, replay inspection, safety review scaffold | [End-to-end Piccolo model examples](examples/README.md) |

A placeholder directory documents planned work; it does not contain an executable implementation.

## Action safety review

The [blink-safety-review skill](skills/blink-safety-review/SKILL.md) includes a release download helper, decision client, and optional QwenPaw ToolGuard adapter for `allow`, `ask_user`, or `deny` advice on a proposed tool action.

The [release descriptor](skills/blink-safety-review/assets/release.json) is deliberately unconfigured. No model is downloaded or activated by default, and model-backed action review has not been validated by the game showcase. Follow the [QwenPaw integration guide](skills/blink-safety-review/references/qwenpaw.md) once the model release and serving adapter are available.

## Repository map

```text
arena/                      Standalone Arena application, engines and archives
assets/showcase/             Reproducible GIFs, posters and frame manifests
docs/                       Blog, provenance, release scope and verification
scripts/                    Showcase rendering and frontend verification
skills/blink-safety-review/  Action review integration scaffold
models/                     Coming soon: model card, weights and release terms
inference/                  Coming soon: Piccolo inference and serving
training/                   Coming soon: training recipes and configuration
data/                       Coming soon: dataset documentation and release
evaluation/                 Coming soon: release evaluation and results
examples/                   Coming soon: Piccolo model integration examples
```

## Reproduce and contribute

The complete replay archive can be checked offline using Python 3.12, without a model:

```bash
cd arena
python3.12 scripts/export_home_decision.py --check
python3.12 -m unittest tests.test_home_decision -v
```

To rebuild images, install Playwright, its Chromium browser, and `ffmpeg`, then run `python scripts/render_completed_showcase.py` from the repository root. Run `python scripts/export_showcase.py` and `python scripts/render_showcase.py` for the other archived examples. [Showcase notes](docs/SHOWCASE.md) also cover the earlier asset set.

For a useful issue or contribution, include the game, seed, steps to reproduce, and an anonymized replay when available. Keep original participant IDs and outcomes intact. See [verification](docs/VERIFICATION.md) for tested scope and known limitations, and [repository notes](docs/REPOSITORY.md) for remaining release work.

## Attribution and licensing

Arena and the completed showcase were adapted from JevArena. Historical `jev.*` protocols, `JEV_*` environment variables, and checkpoint IDs remain compatible. Component origins, game libraries, fonts, and existing licenses are listed in [third-party notes](arena/docs/THIRD_PARTY.md). A project-wide code license and model-weight terms are still pending; this repository does not yet grant a new project-wide license.
