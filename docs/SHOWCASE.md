# Showcase Sources and Reproduction

The README and blog showcase nine games: Mario, Snake, 2048, Sokoban, Tetris, Jump Jump, Hex, Dots and Boxes, and Othello. Othello uses the original archived 6×6 winning replay. Game videos retain their on-screen names; the records below come from historical experiments.

Exported animations remove `COMPLETED GAME`, numbered arrows, and the game-switching bar, while retaining the current game, state, action, and right-hand candidate panel. The web player retains interactive navigation. The blog no longer introduces each game individually; source details are collected here.

## Current animations: Complete timelines and candidate actions

### 2026-10-29: Restore original candidate probabilities

Probability bars, percentages, and final-choice highlighting were added to the right-hand panels of eight games. Candidate probabilities for all **195 model judgments** were recovered from original records and aligned by action ID. No model probabilities are fabricated for the additional 14 automatic Tetris executions or 1 sole legal action in Dots and Boxes. During automatic execution, the previous judgment remains visible, clearly marked as having no new request.

When there are many candidates, the six highest-probability options are shown by default, with the final choice always visible. The remaining probability mass is labeled separately; all candidates can be expanded on the website. The animations have no additional game legends and retain all 210 transitions and original animations.

- [Public probability receipts](../arena/web/showcase/probabilities/) contain only candidate probabilities, selection methods, and source digests; they exclude model-service URLs, credentials, and private runtime paths.
- Mario and Tetris use the distributions returned by their original requests, checking each request's state and action. Mario first reuses the original lossless input compaction, then checks the state.
- 2048, Sokoban, Jump Jump, Hex, and Dots and Boxes retain the `representative_sample_index` saved by the original evaluation pipeline. They show the actual judgment distribution supporting the final action, with its position among the three judgments labeled on the page. The three distributions are not averaged and presented as one output.
- Snake uses `policy.old_probabilities` from the original successful rollout, aligned by `candidate_values`. This is a behavior-policy distribution incorporating temperature and exploration. Sampling parameters are saved in the receipt, and the selected action is the actual sampled result.
- `scripts/export_showcase_probabilities.py --check` checks each step's action, candidate set, probability sum, source digest, and coverage. For a new export, supply `--bundle` and `--snake-episode` inputs located outside the repository.

### Complete playback

All eight animations use the [unified player](../arena/web/showcase.html): game visuals on the left, candidate actions, the selected option, and execution feedback on the right. All **210 transitions** play in recorded order, without selective skipping or truncation. Opening states, waits, action execution, and final states are preserved. Playback runs at 2× with short reading pauses; GIFs are 12 fps and do not represent actual model inference speed.

The [complete timeline](../arena/web/showcase/full/) records three phases for each step and continuous execution frames. Mario reconstructs physics frames 0–2083 individually and strictly checks every original observation, arrival, and execution boundary. Snake retains all 49 body movements; Sokoban retains 14 actual walking and box-pushing movements; Tetris expands every clock-driven execution frame. Board games and Jump Jump retain each original decision and complete action transition. Historical board-game initial states already contain pieces; playback begins at the archived initial state.

The [render manifest](../assets/showcase/render-manifest.json) lists GIF frame indices for each phase, complete consecutive step indices, source digests, and durations. The initial state pauses for 0.5 seconds and the final state for 2 seconds. Main documents retain a four-row, two-column layout without additional captions.

```bash
python scripts/export_mario_showcase.py --check
python scripts/export_snake_showcase.py --check
python scripts/export_full_showcase.py
BLINK_BROWSER_CHANNEL=chrome python scripts/render_showcase.py
```

Use options such as `--game snake` to rebuild a single game; without `--game`, all eight are rebuilt. Output targets include `assets/showcase/` and `assets/showcase/completed/`, preserving the README's image paths.

## Complete game sources (2026-10-27)

The player, styles, and public archive were imported from JevArena's committed homepage Showcase, at source commit `5cc08eb` (complete replay data was introduced in `926adff`). The import leaves the original workspace untouched. Data files are preserved byte for byte; the exporter is adapted to this repository's Python package paths, and rendering support for Tetris clock versions v1–v4 is also imported. The historical `oneshot.home-decision.v3` schema and original model IDs are preserved.

| Game | Historical checkpoint | seed | Recorded transitions / model calls | Verified outcome |
| --- | --- | ---: | ---: | --- |
| 2048 (target 128) | SFT v9-a17 | 44 | 65 / 65 | Reached 128, score 760 |
| Sokoban | RL R9 / iter_0000031 | 43 | 4 / 4 | Both boxes placed, 14 environment moves |
| 6×6 Othello | RL R6 / iter_0000019 | 47 | 22 / 9 | Model won as O |
| Tetris | GRPO N3 / iter_0000006 | 46 | 25 / 11 | Cleared 4 lines |

There are 116 transitions and 89 model calls in total. Opponent turns, sole legal actions, and execution intervals without model requests are labeled separately. These are selected successful games from four different versions; they cannot be used to compare versions or estimate overall success rates.

- The [complete archive](../arena/web/playground/data/home-decision.json) preserves initial states, candidates and actions at every step, successor states, model identities, clocks, and outcomes.
- The [standalone player](../arena/web/completed-showcase.html) and Arena's Blog tab reuse `home-demo.js`, supporting Chinese/English, progress seeking, playback speed, final states, and keyboard switching. Tetris uses the existing read-only renderer.
- Current GIFs use the unified timeline export above; the old fixed-state sampling has been replaced. The original standalone player and source archive remain available.
- `assets/showcase/completed/render-manifest.json` records source digests, all steps, phases, and frame positions for the three active assets from the complete render manifest. PNGs retain each game's final state.

Offline verification requires no model, training directory, or key:

```bash
cd arena
python3.12 scripts/export_home_decision.py --check
python3.12 -m unittest tests.test_home_decision -v
```

Verification uses the shared engines to check candidates, actions, successor states, natural wins, and budget status, and to validate Tetris clocks and execution frames. Tests also deliberately tamper with actions, blocks, and budget status to confirm that fabricated results are rejected.

To generate new showcase assets, run from the repository root:

```bash
python -m pip install playwright
python -m playwright install chromium
# ffmpeg must already be installed on the system.
python scripts/render_completed_showcase.py
```

If desktop Chrome is installed, set `BLINK_BROWSER_CHANNEL=chrome` for new showcase rendering and browser checks.

Browser acceptance checks can target a locally running Arena:

```bash
python arena/tests/browser_home_replays.py --url http://127.0.0.1:8080 --out var/completed-replay-check
```

For a static preview server, add `--standalone` to the same command. Both entry points check desktop/mobile, Chinese/English, all four final states, actual slider positions, reset, gravity animation, keyboard switching, swiping, and reduced-motion preferences.

When replacing replays, the exporter supports a private selection file outside the repository; see `arena/scripts/export_home_decision.py --help`. Original evaluation data, private paths, and selection files must not be committed.

## Archived showcases (2026-10-26, expanded 2026-10-27)

The showcase uses selected trajectories already extracted into `arena/web/showcase/traces/`, with their source receipts. It does not rerun policies, make additional model calls, or rescore results. The optional extraction tool requires an explicitly supplied archive outside the repository.

Seven trajectories with complete visual states were selected. All original recording types are `reconstructed_verified`: archived states were reconstructed and verified by the original exporter. This release directly renders those saved states and does not describe them as original screen recordings.

| Showcase | Archive location | Recorded steps | Original result |
| --- | --- | ---: | --- |
| 6×6 Othello | `replays["00000"].streams[0]` | 28 | White O won |
| 2048 | `episodes["merge_2048-42-oneshot27b-game-rl-native-iter17"]` | 91 | Score 916; the archived task targeted a 128 tile |
| Jump Jump | `episodes["jump_jump-42-oneshot27b-game-rl-native-iter17"]` | 8 | Reached 8 platforms |
| Tetris | `episodes["tetris_placement-42-oneshot27b-game-rl-native-iter17"]` | 14 | Top-out failure, 0 lines cleared; steps include environment frames, not 14 model judgments |
| 19×19 Gomoku | `replays["00004"].streams[0]` | 7 | X won |
| 7×7 Hex | `replays["00006"].streams[0]` | 31 | X won |
| 3×3 Dots and Boxes | `replays["00008"].streams[0]` | 14 | O won |

All examples use seed 42, totaling 193 recorded steps. The table above retains the model IDs and original record locations of each showcased trajectory.

## Complete Mario replay (added 2026-10-27)

The [public Mario trajectory](../arena/web/showcase/traces/mario.json) comes from `mario_platformer-44-oneshot-sft-v9a17-presence-positive-retention` in `oneshot-sft-v9a17-20261022`. It retains the original model ID, seed 44, the easy map from `mario-map-v2-curriculum`, and real-time waiting rules.

This game contains 12 model calls and execution events: 11 actions were executed and 1 response was rejected because an enemy changed direction. Final progress was 100%, with natural completion before budget exhaustion. The rejected action retains its original marker and an action-rejection label in the player. This selected historical example cannot be used to compare models or estimate overall success rates.

During export, the current repository's shared engine replays the initial state, observations, action arrivals, and final state. All 38 strict state comparisons passed without relaxed floating-point tolerances. The original episode's SHA-256 is `655f4cf910b9b36f9b3e204b3f905a4a14456c0992c509cf7627aaf483c76088`. The public file retains only game states, candidates, actions, execution results, and clock fields needed for reproduction. Model-service configuration, private paths, and raw responses are excluded.

Verify offline from the repository root (Python 3.12, Node.js, and Arena dependencies required):

```bash
python scripts/export_mario_showcase.py --check
```

To update this example, run `python scripts/export_mario_showcase.py --episode /path/to/private-episode.json --source-run public-run-id`, then run the general export and rendering commands below. Original inputs stay outside the repository. The public trajectory includes the events needed for offline verification, requiring neither original-input access nor model calls.

## Successful Snake replay (2026-10-27)

The [public Snake trajectory](../arena/web/showcase/traces/snake.json) comes from our own historical run `jev-game-rl-online-20261016-v1`, with policy ID `formal-sft310-20261016-v5/policy-0` and seed `1194410000`. The original record is `jev.rollout.receipt.v1`, with `policy_origin=student`, `on_policy=true`, and `rule_takeover_count=0`. This is an actual historical rollout, not an external baseline, and is not reported as an independent evaluation-set result.

The game **wins naturally after 51 decisions, 49 body movements, and all 6 apples collected**, with an in-game clock of 51.1 seconds. It replaces the previously misselected failed SFT v9-a17 / seed 43 trajectory. The exporter uses the current shared engine to verify the initial state, every observation/arrival/post-execution state, and the final state: **all 155 public states match exactly**. Early archives stored only public projections; missing inter-request durations are recovered precisely from adjacent records' game clocks. No model was called again and no original action was changed.

The public file retains the original episode's SHA-256, candidates, actions, and clocks. Service configuration, private paths, and raw model responses are excluded. The exporter requires a win, the target food count, and natural termination, preventing failed examples from being generated through this entry point.

```bash
python scripts/export_snake_showcase.py --check
python scripts/export_full_showcase.py --game snake
python scripts/render_showcase.py --game snake
```

To replace the source, first export a verified public trajectory with `--episode /path/to/private-episode.json --source-run public-run-id`. Do not commit original inputs.

## Data and visuals

- The [trajectory manifest](../arena/web/showcase/manifest.json) records source runs, source fields, participants, recording types, and results. Mario and Snake use the sources and original-file digests identified separately in their entries.
- `arena/web/showcase/traces/` contains seven complete streams copied field for field from the old archive (checked for JSON round-trip equality), plus public states and verification events for Mario and Snake. The nine archived trajectories total 256 recorded transitions; only some assets appear in the main documents.
- The [render manifest](../assets/showcase/render-manifest.json) records original state locations, cover locations, and frame durations for each animation.
- The current eight GIFs traverse every decision and execution interval; exact coverage is listed in the v2 render manifest. Remaining older assets are historical archives and do not appear in the main gallery.
- Visuals reuse the read-only replay entry point in `arena/web/playground/renderers.js`. They do not call models or reselect actions. Continuous visuals come from saved execution frames or are reconstructed by the same engine using original actions and clocks. Boundary states must match the original records.

## Reproduction

Run from the repository root:

```bash
python -m pip install playwright
python -m playwright install chromium
# ffmpeg must already be installed on the system.
python scripts/export_showcase.py
python scripts/export_full_showcase.py
python scripts/render_showcase.py
```

The scripts output `assets/showcase/*.gif` and `*.png`, then shut down the temporary local asset server. Fonts use the bundled Inter. Browser environments may affect antialiasing, but state and action sources remain unchanged.
