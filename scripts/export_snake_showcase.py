#!/usr/bin/env python3
"""Export saved Snake states and clock events, or replay the public artifact offline."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'arena/web/showcase/traces/snake.json'
sys.path.insert(0, str(ROOT / 'arena'))
import blink_arena  # Registers the shipped engines.
import jev_snake_realtime as game
import jev_snake_rl as replay

EVENT_FIELDS = ('ordinal', 'record', 'action', 'pre_decision_seconds', 'before_state',
                'waiting_seconds', 'arrival_state', 'action_applied', 'post_action_seconds',
                'reason', 'after_state', 'clock_contract', 'error_type', 'status', 'no_request')


def steps(events, participant):
    return [{'index': index, 'player': participant, 'action': event.get('action'),
             'action_applied': event.get('action_applied', False),
             'state': game.public(event['after_state'])}
            for index, event in enumerate(events)]


def verify(stream):
    native = stream['replay']
    events = native['replay_events']
    assert stream['kind'] == 'snake_navigation' and not stream['missing_frames']
    assert game.public(native['initial_state']) == stream['initial_state']
    assert game.public(events[-1]['after_state']) == stream['final_state']
    assert stream['steps'] == steps(events, stream['participant'])
    assert stream['result']['outcome'] == stream['final_state']['outcome']
    # The evaluator's final_state is a public projection; the verifier takes the
    # full engine state retained in the last event. Check both representations.
    assert replay.verify({'kind': stream['kind'], 'seed': stream['seed']},
                         native['initial_state'], events[-1]['after_state'], native)
    return {'verified': True, 'events': len(events), 'public_final_exact': True}


def export(path, source_run):
    raw = path.read_bytes()
    row = json.loads(raw)
    assert row['status'] == 'complete' and row['replay_verified']
    assert source_run and all(c.isalnum() or c in '-_' for c in source_run)
    events = [{key: event[key] for key in EVENT_FIELDS if key in event}
              for event in row['replay_events']]
    stream = {
        'id': row['episode_id'], 'kind': row['kind'], 'seed': row['seed'],
        'participant': row['model'], 'participants': [row['model']],
        'recording': 'recorded_states_verified', 'missing_frames': False,
        'source': {'run_id': source_run, 'episode_id': row['episode_id'],
                   'episode_sha256': hashlib.sha256(raw).hexdigest()},
        'initial_state': game.public(row['initial_state']), 'final_state': row['final_state'],
        'result': {key: row[key] for key in ('status', 'outcome', 'terminal',
                   'budget_exhausted', 'model_calls', 'steps', 'score', 'failure_reason')},
        'steps': steps(events, row['model']),
        'replay': {'clock_contract': row['clock_contract'],
                   'initial_state': row['initial_state'], 'replay_events': events},
    }
    stream['verification'] = verify(stream)
    TARGET.write_text(json.dumps(stream, ensure_ascii=False, separators=(',', ':')) + '\n')
    return stream


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, help='External original episode; do not commit')
    parser.add_argument('--source-run', help='Public run identifier')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        stream = json.loads(TARGET.read_text())
        assert verify(stream) == stream['verification']
    else:
        if not args.episode or not args.source_run:
            parser.error('Provide --episode and --source-run, or use --check')
        stream = export(args.episode, args.source_run)
    print(json.dumps({'episode': stream['id'], **stream['verification']}))
