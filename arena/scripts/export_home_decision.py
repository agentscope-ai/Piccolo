#!/usr/bin/env python3
"""Export completed Home replays, or verify the committed display archive offline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "oneshot27b-game-rl-native-iter17"
EXCERPT_START = 43
STATE_FIELDS = {
    "merge_2048": ("kind", "seed", "steps", "score", "outcome", "board"),
    "sokoban_puzzle": ("kind", "steps", "score", "outcome", "width", "height", "walls", "boxes", "targets", "player"),
    "snake_navigation": ("kind", "engine_revision", "n", "body", "direction", "pending_direction", "food", "obstacles", "steps", "decisions", "score", "outcome", "elapsed", "collision_cell"),
    "othello_6x6": ("kind", "game", "n", "board", "turn", "winner", "passes"),
}
SCHEMA = "oneshot.home-decision.v3"
LABELS = {"merge_2048": ("2048 · target 128", "2048 · 目标 128"),
          "sokoban_puzzle": ("Sokoban", "推箱子"),
          "othello_6x6": ("Othello · 6×6", "黑白棋 · 6×6"),
          "tetris_placement": ("Tetris", "俄罗斯方块")}
CLOCK_FIELDS = ("ordinal", "pre_decision_seconds", "waiting_seconds", "post_action_seconds",
                "action_applied", "reason", "error_type", "status", "no_request", "idle_seconds",
                "idle_segments", "coalesced_wait_count", "no_request_reason", "policy_request",
                "strategy_origin", "execution_origin", "clock_contract")


def state_view(game: str, state: dict) -> dict:
    """Only the actual public fields needed by the small homepage renderer."""
    if game == "tetris_placement":
        import jev_tetris_realtime as tetris
        return tetris.public(state)
    return {key: state[key] for key in STATE_FIELDS[game] if key in state}


def shared_engines():
    sys.path.insert(0, str(ROOT))
    import blink_arena  # Registers the shipped engine module search path.
    from jev_engine_registry import get_engine
    return get_engine


def board_episode(row):
    """Replay the same fixed opponent, including forced moves on both sides."""
    import jev_board_algorithm_opponent as opponent
    engine = shared_engines()(row["kind"])
    world = engine.reset(row["seed"])
    assert engine.public(world) == row["initial_state"], "Board initial state changed"
    traces, used, frames = row["trace"], 0, []
    for turn in range(engine.limit):
        if engine.outcome(world, row["model_side"]) or not engine.legal_actions(world):
            break
        before = engine.public(world)
        candidates = list(engine.observe(world)["questions"]["decision"]["criteria"])
        controlled = world["turn"] == row["model_side"]
        if controlled and len(candidates) > 1:
            item = traces[used]
            assert item["player"] == row["model"]
            used += 1
            action = item["action"]
        else:
            action = candidates[0] if controlled else opponent.choose(world, candidates, row["seed"], turn)
            item = {}
        assert action in candidates
        world = engine.step(world, action)
        frames.append({**item, "action": action, "actor": before["turn"],
                       "model_call": controlled and len(candidates) > 1,
                       "origin": "model" if controlled and len(candidates) > 1 else "forced" if controlled else "opponent",
                       "before_state": before, "after_state": engine.public(world)})
    assert used == len(traces), "Unused board predictions"
    assert engine.public(world) == row["final_state"], "Board final state changed"
    assert engine.outcome(world, row["model_side"]) == "win"
    return frames


def replay_tetris(clip):
    """Rebuild full clock receipts from public states, with no model requests."""
    import jev_tetris_realtime as game
    from jev_demo_arena_replay_native import tetris_frames
    from jev_tetris_runtime import CLOCK_CONTRACT
    events = []
    for step in clip["steps"]:
        event = {**step["execution"], "action": step["action"],
                 "before_state": step["before"], "after_state": step["after"]}
        if not event.get("no_request"):
            event.update(arrival_state=step["arrival"],
                         record=game.as_record({**step["before"], "_seed": clip["seed"]}))
        events.append(event)
    return tetris_frames({"seed": clip["seed"], "initial_state": clip["initial_state"],
                          "final_state": clip["final_state"], "clock_contract": CLOCK_CONTRACT,
                          "replay_events": events})


def tetris_animation(frames, before):
    """Successive deltas retain every frame without repeating the whole board."""
    result = []
    previous = state_view("tetris_placement", before)
    for frame in frames:
        visible = state_view("tetris_placement", frame)
        if visible != previous:
            result.append({key: value for key, value in visible.items() if previous.get(key) != value})
            previous = visible
    return result


def verify_completed(archive):
    get_engine = shared_engines()
    assert archive["schema"] == SCHEMA and len(archive["clips"]) == 4
    assert {c["game"] for c in archive["clips"]} == set(LABELS)
    assert len({c["models"][0]["id"] for c in archive["clips"]}) == 4, "Showcase must cover all four checkpoints"
    transitions = 0
    for clip in archive["clips"]:
        kind, steps = clip["game"], clip["steps"]
        result = clip["result"]
        assert result["status"] == "complete" and result["outcome"] == "win"
        assert result["terminal"] is True and result["budget_exhausted"] is False
        assert steps and clip["initial_state"] == steps[0]["before"]
        assert clip["final_state"] == steps[-1]["after"]
        if kind == "tetris_placement":
            recovered = replay_tetris(clip)
            assert len(recovered) == len(steps)
            for step, frame in zip(steps, recovered):
                assert step["before"] == state_view(kind, frame["before_state"])
                assert step["after"] == state_view(kind, frame["after_state"])
                assert step["execution_frames"] == tetris_animation(frame["execution_frames"], frame["before_state"])
                options = [] if step["execution"].get("no_request") else list(
                    get_engine(kind).observe({**frame["before_state"], "_seed": clip["seed"]})["questions"]["decision"]["criteria"])
                assert step["candidates"] == options
            assert clip["final_state"]["outcome"] == "win" and clip["final_state"]["lines"] >= 4
        else:
            engine = get_engine(kind)
            world = engine.reset(clip["seed"])
            for step in steps:
                assert state_view(kind, engine.public(world)) == step["before"]
                assert list(engine.observe(world)["questions"]["decision"]["criteria"]) == step["candidates"]
                assert step["action"] in step["candidates"]
                world = engine.step(world, step["action"])
                assert state_view(kind, engine.public(world)) == step["after"]
            assert engine.outcome(world, clip.get("model_side")) == "win"
        transitions += len(steps)
    from blink_arena.privacy import assert_public_document
    assert_public_document(archive)
    return transitions


def extract_selected(selection):
    get_engine = shared_engines()
    from jev_demo_arena_replay_native import native_frames
    clips = []
    for spec in selection["clips"]:
        source = Path(spec["episode"])
        row = json.loads(source.read_text())
        summary = json.loads((source.parent.parent / "summary.json").read_text())
        assert summary["state"] == "complete" and summary["finished"] == summary["planned"] == 176
        assert row["status"] == "complete" and row["outcome"] == "win" and row["terminal"] is True
        assert row["budget_exhausted"] is False and not row.get("error_type")
        assert row["model"] == spec["model_id"] == row["model_identity"]["id"]
        kind = row["kind"]
        frames = board_episode(row) if kind == "othello_6x6" else native_frames(row)
        assert frames
        steps = []
        for index, frame in enumerate(frames):
            before, after = frame["before_state"], frame["after_state"]
            auto = kind == "tetris_placement" and frame.get("no_request", False)
            model_call = frame.get("model_call", not auto and len(get_engine(kind).legal_actions(before)) > 1)
            stability = frame.get("decision_stability") or {}
            execution = {"status": "verified_against_shared_engine", "action_applied": True}
            if kind == "tetris_placement":
                execution = {key: frame[key] for key in CLOCK_FIELDS if key in frame}
            elif kind in ("sokoban_puzzle", "merge_2048"):
                execution.update(score_delta=after["score"]-before["score"], physical_moves=after["steps"]-before["steps"])
            else:
                import jev_demo_games as board
                execution["flipped_discs"] = 0 if frame["action"] == "pass" else len(board.flips(before, *board.coord(before, frame["action"])))
            step = {"index": index, "model_id": row["model"] if model_call else None,
                    "model_call": model_call, "actor": frame.get("actor"), "origin": frame.get("origin", "automatic" if auto else "model" if model_call else "forced"),
                    "candidates": [] if auto else list(get_engine(kind).observe(before)["questions"]["decision"]["criteria"]),
                    "action": frame.get("action"), "before": state_view(kind, before), "after": state_view(kind, after),
                    "latency_seconds": frame.get("latency_seconds", frame.get("waiting_seconds")) if not auto else None,
                    "repeat_count": stability.get("repeat_count", row["decision_policy"]["repeat_count"]) if model_call else None,
                    "execution": execution}
            if kind == "tetris_placement":
                if not auto:
                    step["arrival"] = state_view(kind, frame["arrival_state"])
                step["execution_frames"] = tetris_animation(frame["execution_frames"], before)
            steps.append(step)
        clips.append({"game": kind, "name_en": LABELS[kind][0], "name_zh": LABELS[kind][1],
                      "episode_id": row["episode_id"], "recording": "reconstructed_verified",
                      "models": [{"id": row["model"], "name": spec["name"], "checkpoint": spec["checkpoint"]}],
                      "seed": row["seed"], "model_side": row.get("model_side"), "episode_steps": len(steps),
                      "model_calls": row["model_calls"], "result": {k: row[k] for k in ("status", "outcome", "terminal", "budget_exhausted", "score")},
                      "initial_state": steps[0]["before"], "final_state": steps[-1]["after"],
                      "source_run": spec.get("source_run", source.parent.parent.parent.name), "steps": steps})
    archive = {"schema": SCHEMA, "run_id": selection["run_id"],
               "source": {"selection": "Curated successful episodes from four checkpoints; these examples are not aggregate evaluation results.",
                          "verification": "Complete action logs and final states replayed through the shipped engines; Tetris includes the original advancing clock."},
               "clips": clips}
    verify_completed(archive)
    return archive


def assert_recorded_fields(generated: dict, recorded: dict, *, ignore=()) -> None:
    # Current rules may append execution metadata that older archives omitted.
    # Every field present in the archive must still match.
    for key, value in recorded.items():
        if key not in ignore:
            assert generated.get(key) == value, f"Archived {key} differs from the shared engine"


def extract() -> dict:
    source = ROOT / "leaderboard" / "arena-replays.json"
    source_bytes = source.read_bytes()
    archive = json.loads(source_bytes)
    arena = json.loads((ROOT / "leaderboard" / "arena.json").read_text())
    assert archive["run_id"] == arena["run_id"], "Arena and replay runs differ"
    model_names = {row["id"]: row["name"] for row in arena["overall"]}
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "blink_arena" / "engines"))
    import jev_showcase_games as puzzles
    import jev_snake_realtime as snake
    import jev_demo_games as boards

    clips = []
    specs = [
        ("merge_2048", f"merge_2048-42-{MODEL_ID}", EXCERPT_START, "2048", "2048"),
        ("sokoban_puzzle", f"sokoban_puzzle-42-{MODEL_ID}", 0, "Sokoban", "推箱子"),
        ("snake_navigation", f"snake_navigation-42-{MODEL_ID}", 0, "Snake", "贪吃蛇"),
        ("othello_6x6", "match-00001", 8, "Othello", "黑白棋"),
    ]
    for game, episode_id, start, name_en, name_zh in specs:
        if game == "othello_6x6":
            replay = archive["replays"]["00001"]
            episode = replay["streams"][0]
            seed = replay["seed"]
        else:
            episode = archive["episodes"][episode_id]
            seed = episode["initial_state"].get("seed", 42)
            assert episode["participant"] == MODEL_ID
        assert episode["id"] == episode_id and not episode["missing_frames"]
        source_steps = episode["steps"][start:start + 4]
        assert len(source_steps) == 4
        steps = []
        previous_after = None
        for item in source_steps:
            before, after, action = item["before_state"], item["state"], item["action"]
            execution = {"status": "verified_against_shared_engine", "action_applied": True}
            if game in ("merge_2048", "sokoban_puzzle"):
                candidates = puzzles.choices(before)
                assert action in candidates
                assert_recorded_fields(puzzles.step(before, action), after)
                if previous_after is not None:
                    assert before == previous_after, "Puzzle excerpt is not consecutive"
                execution["score_delta"] = after["score"] - before["score"]
                execution["physical_moves"] = after["steps"] - before["steps"]
            elif game == "snake_navigation":
                # before_state is the captured input. The archive's observation
                # field is the later arrival snapshot, not the model input.
                candidates = snake.choices(before)
                assert action in candidates
                timing = item["execution"]
                if previous_after is not None:
                    advanced = snake.advance_idle(previous_after, timing["pre_decision_seconds"])
                    assert_recorded_fields(advanced, before, ignore=("execution_trace",))
                arrival = snake.advance_idle(before, timing["waiting_seconds"])
                assert_recorded_fields(arrival, item["observation"], ignore=("execution_trace",))
                generated = snake.step(arrival, action) if timing["action_applied"] else arrival
                generated = snake.advance_idle(generated, timing["post_action_seconds"])
                assert_recorded_fields(generated, after, ignore=("execution_trace",))
                if not timing["action_applied"]:
                    assert arrival["outcome"] and timing["reason"] == "game_finished_while_waiting"
                execution.update(timing)
            else:
                candidates = boards.legal(before)
                assert action in candidates
                assert_recorded_fields(boards.move(before, action), after)
                if previous_after is not None:
                    assert before == previous_after, "Board excerpt is not consecutive"
                execution["flipped_discs"] = len(boards.flips(before, *boards.coord(before, action)))
            previous_after = after
            assert item["player"] in model_names
            steps.append({
                "index": item["index"], "model_id": item["player"], "actor": item.get("actor"),
                "candidates": list(candidates), "action": action,
                "before": state_view(game, before), "after": state_view(game, after),
                "latency_seconds": item.get("latency_seconds"),
                "repeat_count": item.get("stability", {}).get("repeat_count"), "execution": execution,
            })
        ids = list(dict.fromkeys(step["model_id"] for step in steps))
        clips.append({
            "game": game, "name_en": name_en, "name_zh": name_zh,
            "episode_id": episode_id, "recording": episode["recording"],
            "models": [{"id": ident, "name": model_names[ident]} for ident in ids],
            "seed": seed, "episode_steps": len(episode["steps"]),
            "verification": "Shared game rules; captured-state candidates and every recorded next state verified. Snake additionally replays the original waiting and post-action times.",
            "steps": steps,
        })
    return {
        "schema": "oneshot.home-decision.v2", "run_id": archive["run_id"],
        "source": {
            "file": "leaderboard/arena-replays.json",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "candidate_provenance": "Reconstructed from archived captured before_state with the shipped shared engine.",
            "probabilities": "Not included in the replay archive; not inferred.",
        },
        "homepage_benchmark_model_id": "oneshot-w22m05r02-v5best-avg50", "clips": clips,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--selection", type=Path, help="Private JSON listing four completed source episodes and public model labels")
    parser.add_argument("--output", type=Path, default=ROOT / "web" / "playground" / "data" / "home-decision.json")
    args = parser.parse_args()
    target = args.output
    if not args.selection and target.exists() and json.loads(target.read_text()).get("schema") == SCHEMA:
        transitions = verify_completed(json.loads(target.read_text()))
        print(f"Verified: four completed winning episodes, four checkpoints, {transitions} transitions, exact final states and clock receipts.")
        return
    archive = extract_selected(json.loads(args.selection.read_text())) if args.selection else extract()
    expected = json.dumps(archive, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    if args.check:
        assert target.read_text() == expected, "Homepage clips differ from their source"
        print("Verified: four games, 16 archived transitions, captured candidates, model identities, realtime execution and source hash.")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected)
        print(f"Wrote {target.name} ({len(expected.encode())} bytes)")


if __name__ == "__main__":
    main()
