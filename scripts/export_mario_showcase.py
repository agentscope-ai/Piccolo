#!/usr/bin/env python3
"""Export a verified Mario episode's public states, or check the saved replay offline."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'arena/web/showcase/traces/mario.json'
EVENT_FIELDS = ('ordinal', 'record', 'action', 'before_state', 'arrival_state',
                'after_state', 'action_applied', 'arrival_check', 'discard_reason', 'clock_contract')
REPLAY_FIELDS = ('clock_contract', 'environment_generation', 'engine_viewport')


def verify(stream):
    sys.path.insert(0, str(ROOT / 'arena'))
    import blink_arena  # Registers the shipped engines.
    from jev_world_core_rl import verify as verify_world
    from unittest.mock import patch

    assert stream['kind'] == 'mario_platformer' and not stream['missing_frames']
    events = stream['replay']['replay_events']
    assert stream['steps'] == steps(events, stream['participant'])
    assert stream['initial_state'] == events[0]['before_state']
    assert stream['final_state'] == events[-1]['after_state']
    assert stream['result']['outcome'] == stream['final_state']['outcome'] == 'win'
    assert stream['result']['terminal'] and not stream['result']['budget_exhausted']
    with patch.dict('os.environ', {'JEV_WORLD_REPLAY_MODE': 'strict'}):
        proof = asyncio.run(verify_world(
            {'kind': stream['kind'], 'seed': stream['seed']},
            stream['initial_state'], stream['final_state'], dict(stream['replay'])))
    assert proof['strict_match'] and proof['relaxed_count'] == 0
    return proof


def steps(events, participant):
    return [{'index': index, 'player': participant, 'action': event['action'],
             'action_applied': event['action_applied'],
             'discard_reason': event.get('discard_reason'), 'state': event['after_state']}
            for index, event in enumerate(events)]


def export(episode: Path, source_run: str):
    raw = episode.read_bytes()
    row = json.loads(raw)
    assert row['status'] == 'complete' and row['replay_verified']
    assert source_run and all(c.isalnum() or c in '-_/' for c in source_run)
    assert not source_run.startswith('/') and '..' not in source_run
    # Explicit allowlists exclude provider configuration, private paths and replies.
    events = [{key: event[key] for key in EVENT_FIELDS if key in event}
              for event in row['replay_events']]
    stream = {
        'id': row['episode_id'], 'kind': row['kind'], 'seed': row['seed'],
        'participant': row['model'], 'participants': [row['model']],
        'recording': 'recorded_states_verified', 'missing_frames': False,
        'source': {'run_id': source_run, 'episode_id': row['episode_id'],
                   'episode_sha256': hashlib.sha256(raw).hexdigest(),
                   'finished_at': row['finished_at']},
        'initial_state': row['initial_state'], 'final_state': row['final_state'],
        'result': {key: row[key] for key in
                   ('status', 'outcome', 'terminal', 'budget_exhausted', 'model_calls', 'steps', 'score')},
        'steps': steps(events, row['model']),
        'replay': {**{key: row[key] for key in REPLAY_FIELDS}, 'replay_events': events},
    }
    stream['verification'] = verify(stream)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(stream, ensure_ascii=False, separators=(',', ':')) + '\n')
    return stream


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, help='External original episode; never commit this input')
    parser.add_argument('--source-run', help='Public run identifier, without an absolute path')
    parser.add_argument('--check', action='store_true', help='Verify the committed public replay offline')
    args = parser.parse_args()
    if args.check:
        stream = json.loads(TARGET.read_text())
        assert verify(stream) == stream['verification']
    else:
        if not args.episode or not args.source_run:
            parser.error('Export requires --episode and --source-run; use --check for offline verification')
        stream = export(args.episode, args.source_run)
    print(json.dumps({'episode': stream['id'], 'events': len(stream['steps']),
                      'outcome': stream['result']['outcome'], 'verified': True}))
