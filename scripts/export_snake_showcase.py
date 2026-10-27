#!/usr/bin/env python3
"""Export saved Snake states and clock events, or replay the public artifact offline."""
import argparse
import copy
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


def reconstruct_public(stream):
    """Replay older public-only receipts; verify all 3 boundaries per decision exactly."""
    native = game.fresh(stream['seed'])
    assert game.public(native) == stream['initial_state']
    events = []
    for saved in stream['replay']['replay_events']:
        event = copy.deepcopy(saved)
        pre = max(0., saved['before_state']['elapsed'] - native['elapsed'])
        event['pre_decision_seconds'] = pre
        native = game.advance_idle(native, pre)
        assert game.public(native) == saved['before_state']
        event['before_state'] = copy.deepcopy(native)
        candidates = saved.get('record', {}).get('questions', {}).get('decision', {}).get('criteria', {})
        assert saved['action'] in candidates and saved['action'] in game.choices(native)
        native = game.advance_idle(native, saved['waiting_seconds'])
        assert game.public(native) == saved['arrival_state']
        event['arrival_state'] = copy.deepcopy(native)
        applied = not native['outcome'] and saved['action'] in game.choices(native)
        assert applied == saved['action_applied']
        if applied:
            native = game.step(native, saved['action'])
        native = game.advance_idle(native, saved['post_action_seconds'])
        assert game.public(native) == saved['after_state']
        event['after_state'] = copy.deepcopy(native)
        events.append(event)
    assert game.public(native) == stream['final_state']
    return events


def verify(stream):
    native = stream['replay']
    events = native['replay_events']
    assert stream['kind'] == 'snake_navigation' and not stream['missing_frames']
    assert game.public(native['initial_state']) == stream['initial_state']
    assert game.public(events[-1]['after_state']) == stream['final_state']
    assert stream['steps'] == steps(events, stream['participant'])
    assert stream['result']['outcome'] == stream['final_state']['outcome'] == 'win'
    assert stream['final_state']['score'] >= stream['final_state']['food_target']
    assert stream['result']['terminal'] and not stream['result']['budget_exhausted']
    if stream['replay'].get('state_projection') == 'public':
        reconstruct_public(stream)
        return {'verified': True, 'events': len(events), 'public_final_exact': True,
                'exact_public_boundaries': 2 + 3 * len(events)}
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
    public_receipt = row.get('schema_version') == 'jev.rollout.receipt.v1'
    participant = row.get('model') or row['episode_id'].split('-policy-')[0] + '/' + row['policy_version']
    if public_receipt:
        assert row['on_policy'] and row['rule_takeover_count'] == 0
        assert row['policy_origin'] == 'student', row['policy_origin']
    events = [{key: event[key] for key in EVENT_FIELDS if key in event}
              for event in row['replay_events']]
    stream = {
        'id': row['episode_id'], 'kind': row['kind'], 'seed': row['seed'],
        'participant': participant, 'participants': [participant],
        'recording': 'recorded_states_verified', 'missing_frames': False,
        'source': {'run_id': source_run, 'episode_id': row['episode_id'],
                   'episode_sha256': hashlib.sha256(raw).hexdigest()},
        'initial_state': game.public(row['initial_state']), 'final_state': row['final_state'],
        'result': {'status': row['status'], 'outcome': row['outcome'],
                   'terminal': bool(row['final_state']['outcome']),
                   'budget_exhausted': row.get('budget_exhausted', False),
                   'model_calls': row.get('model_calls', row.get('decision_requests')),
                   'steps': len(events), 'score': row['final_state']['score'],
                   'failure_reason': row.get('failure_reason')},
        'steps': steps(events, participant),
        'replay': {'clock_contract': row['clock_contract'],
                   'initial_state': row['initial_state'], 'replay_events': events,
                   **({'state_projection': 'public', 'policy_version': row['policy_version'],
                       'policy_origin': row['policy_origin'], 'on_policy': True, 'rule_takeover_count': 0} if public_receipt else {})},
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
