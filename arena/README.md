# Piccolo Arena

Piccolo Arena brings together interactive games, model connections, leaderboards and the bilingual Piccolo website. Visit [Decision Playground](https://decisionplayground.agentscope.io/) or run the source locally.

- [Website source, Method figures and recorded showcases](docs/WEBSITE.md)
- [12 workflow examples](../examples/workflows/README.md)
- [Models](../docs/MODELS.md) and [benchmark results](../evaluation/README.md)
- [API](docs/API.md), [shared engines](docs/ENGINE.md) and [rollouts](docs/ROLLOUT.md)

## Run locally

Requirements: Python 3.12 and Node.js 22. Run `git lfs pull` after cloning to download the complete article video. From this directory:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
bash scripts/run.sh
```

Open <http://127.0.0.1:8080/>. The game engines run without Chromium. Browser tests additionally require `.venv/bin/python -m playwright install --with-deps chromium`.

For a website-only preview with the bundled leaderboards and media:

```bash
.venv/bin/python scripts/preview_leaderboard.py --port 8080
```

Docker is also supported:

```bash
docker compose up --build -d
```

See [deployment](docs/DEPLOYMENT.md) for domains, path prefixes and persistent storage. Install from the complete source tree so the service can locate its static assets.

## Games and recorded showcases

The active playground follows `config/game-scope.json` and exposes 17 games through `/api/v1/games`. It includes 6×6 Othello. Dots and Boxes, Blackjack, Texas Hold'em, Zha Jin Hua and Mario are excluded from the current playground. Archived recordings remain available in the [release article](web/piccolo.html) and [completed showcase](web/completed-showcase.html).

Games share the same rules, legal actions, observations, seeds and outcome scoring across the web UI, Arena and RL. The `blink_arena` Python package, `jev.*` protocols and `JEV_*` environment variables retain their established names for compatibility.

## Connect a model

Use the model connection dialog to enter a display name, the model identity returned by the service, a full request URL and an optional API key.

| Interface | Response |
| --- | --- |
| Structured decision API | A legal option ID, optionally with its full probability distribution |
| OpenAI-compatible Chat Completions | `{"action":"option ID"}` in `choices[0].message.content` |

The browser calls the model service directly. The service must allow the website origin through CORS; an HTTPS website requires an HTTPS model endpoint. Endpoint settings and keys stay in browser memory, and connections must be entered again after a refresh. The returned model identity must match `served_model`. See the [API contract](docs/API.md).

## Source layout

```text
web/                  Homepage, games, leaderboards, article and recorded media
blink_arena/          HTTP API, sessions, decision queue and shared game engines
config/               Active games, prompts and service settings
leaderboard/          Published scores and bundled replays
data/seed/            Public catalog metadata
var/                  Local runtime outputs (ignored by Git)
```

Clients use `/api/v1/*`; the machine-readable contract is `/api/openapi.json`. Rollout clients can use `/api/v1/rollouts` or call `blink_arena.engine` directly. Browser adapters draw the game state; Node.js runs the same DOM-free world cores on the server.

## Leaderboards

JevBench, Decision Index, HarnessJevBench and DataJevBench each have a `jev.leaderboard.v1` JSON file. The files include metric names, scales, model identities and bilingual chart labels. The Arena also accepts aggregate and per-game Elo snapshots.

```bash
.venv/bin/python scripts/import_leaderboard.py results.json
```

Set `JEV_LEADERBOARD_DIR` to use another directory. Imported results are displayed immediately; new evaluation jobs are started explicitly. See the [leaderboard data guide](docs/LEADERBOARD_DATA.md).

## Development

```bash
.venv/bin/python -m pytest
node --test tests/*.test.cjs tests/test_connections_transport.cjs
node scripts/render_blog.mjs --check
node scripts/build_blog_profiles.mjs --check
node scripts/export_workflow_cases.mjs --check
python scripts/build_release.py --check-only
```

[GitHub CI](../.github/workflows/ci.yml) runs the tests, link checks, browser smoke checks and source packaging. Third-party code, assets and fonts retain their [licenses and attribution](docs/THIRD_PARTY.md).
