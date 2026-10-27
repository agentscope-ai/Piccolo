#!/usr/bin/env python3
"""Extract exact archived streams and record their provenance; never run a policy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = (
    ('othello', 'Othello', 'replays', '00000'),
    ('merge-2048', '2048', 'episodes', 'merge_2048-42-oneshot27b-game-rl-native-iter17'),
    ('jump-jump', 'Jump Jump', 'episodes', 'jump_jump-42-oneshot27b-game-rl-native-iter17'),
    ('tetris', 'Tetris', 'episodes', 'tetris_placement-42-oneshot27b-game-rl-native-iter17'),
    ('gomoku', 'Gomoku', 'replays', '00004'),
    ('hex', 'Hex', 'replays', '00006'),
    ('dots-and-boxes', 'Dots & Boxes', 'replays', '00008'),
)


def export(root: Path) -> dict:
    archive_path = root / 'arena/leaderboard/arena-replays.json'
    archive = json.loads(archive_path.read_text())
    target = root / 'arena/web/showcase'
    (target / 'traces').mkdir(parents=True, exist_ok=True)
    items = []
    for slug, title, collection, key in SELECTION:
        original = archive[collection][key]
        stream = original['streams'][0] if collection == 'replays' else original
        if stream.get('episode_id'):
            raise ValueError('Selection must point directly to its original episode')
        if stream.get('missing_frames') or stream.get('initial_state') is None:
            raise ValueError('Selected trajectory lacks complete visual states: ' + key)
        if any(step.get('state', step.get('after_state')) is None for step in stream['steps']):
            raise ValueError('A selected trajectory step has no saved state: ' + key)
        trace = 'traces/' + slug + '.json'
        (target / trace).write_text(json.dumps(stream, ensure_ascii=False, separators=(',', ':')) + '\n')
        # Round-trip equality ensures export changes neither actions nor outcomes.
        if json.loads((target / trace).read_text()) != stream:
            raise ValueError('Trajectory export differs from source')
        items.append({
            'id': slug, 'title': title, 'kind': stream['kind'], 'trace': trace,
            'source_collection': collection, 'source_key': key,
            'source_stream_index': 0 if collection == 'replays' else None,
            'seed': original.get('seed', stream['initial_state'].get('seed', 42)),
            'participants': stream['participants'], 'recording': stream['recording'],
            'missing_frames': stream['missing_frames'], 'steps': len(stream['steps']),
            'result': stream.get('result'),
        })
    manifest = {
        'schema_version': 'blink.showcase.v1',
        'source': 'arena/leaderboard/arena-replays.json',
        'source_run_id': archive['run_id'], 'source_revision': archive['revision'],
        'source_updated_at': archive['updated_at'],
        'scope': 'Historical experiments, not results of the upcoming Blink model.',
        'selection': 'Fixed representative games with complete saved states; not a success-rate sample.',
        'playback': 'Original renderers, saved decision states, fixed playback pace; not wall-clock video.',
        'items': items,
    }
    mario_path = target / 'traces/mario.json'
    mario = json.loads(mario_path.read_text())
    if mario['missing_frames'] or not mario['verification']['strict_match']:
        raise ValueError('Mario requires a complete verified public replay')
    items.append({
        'id': 'mario', 'title': 'Mario', 'kind': mario['kind'], 'trace': 'traces/mario.json',
        'source': 'arena/web/showcase/traces/mario.json',
        'source_run_id': mario['source']['run_id'],
        'source_collection': 'public_episode', 'source_key': mario['id'],
        'source_episode_sha256': mario['source']['episode_sha256'],
        'seed': mario['seed'], 'participants': mario['participants'],
        'recording': mario['recording'], 'missing_frames': False,
        'steps': len(mario['steps']), 'result': mario['result'],
    })
    snake = json.loads((target / 'traces/snake.json').read_text())
    if snake['missing_frames'] or not snake['verification']['verified']:
        raise ValueError('Snake requires a complete verified public replay')
    items.append({
        'id': 'snake', 'title': 'Snake', 'kind': snake['kind'], 'trace': 'traces/snake.json',
        'source': 'arena/web/showcase/traces/snake.json',
        'source_run_id': snake['source']['run_id'], 'source_collection': 'public_episode',
        'source_key': snake['id'], 'source_episode_sha256': snake['source']['episode_sha256'],
        'seed': snake['seed'], 'participants': snake['participants'],
        'recording': snake['recording'], 'missing_frames': False,
        'steps': len(snake['steps']), 'result': snake['result'],
    })
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return {'trajectories': len(items), 'steps': sum(item['steps'] for item in items)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    print(json.dumps(export(parser.parse_args().root)))
