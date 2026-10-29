#!/usr/bin/env python3
"""Attach archived candidate probabilities to the exact existing showcase steps.

Input bundles contain only whitelisted probability receipts, never provider
configuration. Repeated decisions retain the original representative sample;
Snake retains the recorded behavior distribution (temperature and exploration).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'arena/web/showcase'


def validate(clip, receipt):
    assert receipt['replay_source_sha256'] == clip['source_sha256'], 'Replay source changed'
    assert len(receipt['steps']) == len(clip['steps']), 'Probability step count differs'
    for step, row in zip(clip['steps'], receipt['steps']):
        assert row['index'] == step['index'] and row['action'] == step['action'], 'Decision identity differs'
        probs = row['probabilities']
        if step['actor'] != 'model':
            assert probs is None, 'Non-model action must not claim model probabilities'
            continue
        assert isinstance(probs, dict) and set(probs) == set(step['candidates']), 'Candidate identity differs'
        assert all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values()), 'Invalid probability'
        assert math.isclose(sum(probs.values()), 1, abs_tol=1e-6), 'Probability sum differs'
        assert step['action'] in probs
        assert row['mode'] in ('single_request', 'representative_sample', 'behavior_policy')
    return sum(row['probabilities'] is not None for row in receipt['steps'])


def export(bundle, snake_path):
    raw = snake_path.read_bytes()
    snake = json.loads(raw)
    snake_rows = []
    for index, event in enumerate(snake['replay_events']):
        policy = event['policy']
        values, probabilities = policy['candidate_values'], policy['old_probabilities']
        assert len(values) == len(probabilities) == len(set(values))
        assert values[policy['selected_index']] == event['action']
        snake_rows.append({'index': index, 'action': event['action'],
                           'probabilities': dict(zip(values, probabilities)), 'mode': 'behavior_policy',
                           'sampling_temperature': policy['sampling_temperature'],
                           'sampling_epsilon': policy['sampling_epsilon']})
    bundle['snake'] = {'episode_id': snake['episode_id'], 'source_sha256': hashlib.sha256(raw).hexdigest(),
                       'steps': snake_rows}
    output = BASE / 'probabilities'
    output.mkdir(exist_ok=True)
    report = {}
    for item in json.loads((BASE / 'full-manifest.json').read_text())['items']:
        slug = item['id']
        clip = json.loads((BASE / item['trace']).read_text())
        receipt = {'schema': 'piccolo.showcase-probabilities.v1', 'id': slug,
                   'replay_source': clip['source'], 'replay_source_sha256': clip['source_sha256'], **bundle[slug]}
        for step, row in zip(clip['steps'], receipt['steps']):
            if step['actor'] != 'model':
                assert row['probabilities'] is None
                row['mode'] = step['actor']
        report[slug] = validate(clip, receipt)
        (output / f'{slug}.json').write_text(json.dumps(receipt, ensure_ascii=False, separators=(',', ':')) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, help='Sanitized archived probability receipts, outside Git')
    parser.add_argument('--snake-episode', type=Path, help='Original successful Snake receipt, outside Git')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        report = {p.stem: validate(json.loads((BASE / 'full' / p.name).read_text()), json.loads(p.read_text()))
                  for p in sorted((BASE / 'probabilities').glob('*.json'))}
        assert len(report) == 8
    else:
        if not args.bundle or not args.snake_episode:
            parser.error('Provide --bundle and --snake-episode, or --check')
        report = export(json.loads(args.bundle.read_text()), args.snake_episode)
    print(json.dumps(report))
