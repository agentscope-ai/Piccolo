"""Fill the original Elo ladder from settled, same-seed native episode scores.

This is an offline comparison of the frozen independent cohort, not a new
head-to-head tournament. Native score keys were validated by the episode runner;
this exporter checks their bindings and uses them without changing game scores.
"""
import argparse
from datetime import datetime, timezone
from itertools import combinations
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_arena.privacy import assert_public_document
from blink_arena.storage import write_json
from jev_demo_arena_episodes import comparison_spec, decision_policy
from jev_demo_elo import INITIAL, K, rating_tables
from scripts.publish_public_results import LABELS, ONESHOT

SCHEMA = 'jev.arena.published-elo.v1'
METHOD = 'same-seed-native-score-comparisons-v1'
METRICS = ('agreement_rate', 'unanimous_rate', 'mean_probability_variance',
           'mean_js_distance', 'probability_stability')


def checked_episode(episode, fixture, participant):
    kind, seed = fixture['kind'], fixture['seed']
    binding = episode.get('binding', {})
    spec = comparison_spec(kind)
    if (episode.get('kind') != kind or episode.get('seed') != seed
            or episode.get('model') != participant['id']
            or episode.get('episode_id') != f"{kind}-{seed}-{participant['id']}"
            or binding.get('participant') != participant or binding.get('kind') != kind
            or binding.get('seed') != seed or binding.get('comparison') != spec
            or binding.get('episode_revision') != spec['revision']
            or binding.get('engine_revision') != spec['engine_revision']
            or binding.get('decision_policy') != 'jev-game-decision-policy-v2-realtime-single'):
        raise ValueError('published_episode_binding_mismatch')
    if episode.get('status') == 'error':
        return episode
    key = episode.get('comparison_key')
    if (episode.get('status') != 'complete' or episode.get('comparison_spec') != spec
            or episode.get('episode_revision') != spec['revision']
            or episode.get('engine_revision') != spec['engine_revision']
            or episode.get('decision_policy') != decision_policy(kind)
            or episode.get('higher_is_better') is not True
            or not isinstance(key, list) or len(key) != len(spec['score_fields'])
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in key)):
        raise ValueError('published_native_score_key_invalid')
    if kind == 'mario_platformer':
        proof = episode.get('replay_validation') or {}
        if (episode.get('replay_verified') is not True or proof.get('strict_match') is not True
                or proof.get('relaxed_count') != 0):
            raise ValueError('published_mario_replay_not_strict')
    return episode


def aggregate_stability(blocks):
    """Use the original per-game decision weights; never multiply by opponents."""
    decisions = sum(b.get('decisions', 0) for b in blocks)
    probability = sum(b.get('probability_decisions', 0) for b in blocks)
    result = {'decisions': decisions, 'probability_decisions': probability,
              'probability_coverage': probability/decisions if decisions else None}
    for metric in METRICS:
        weight = 'decisions' if metric in ('agreement_rate', 'unanimous_rate') else 'probability_decisions'
        valid = [b for b in blocks if b.get(metric) is not None and b.get(weight, 0)]
        result[metric] = (sum(b[metric]*b[weight] for b in valid)/sum(b[weight] for b in valid)
                          if valid else None)
    return result


def build(summary, native_plan, episodes, replay_validation, *, oneshot_id=None):
    kinds, players = native_plan['kinds'], native_plan['participants']
    if (summary['state'] != 'complete' or native_plan.get('cohort_mode') != 'independent'
            or native_plan['seeds'] != 8 or set(kinds) != set(LABELS)
            or ONESHOT in {p['id'] for p in players}):
        raise ValueError('published_elo_cohort_invalid')
    roster = {p['id']: p for p in players}
    if oneshot_id is not None and oneshot_id not in roster:
        raise ValueError('published_oneshot_identity_missing')
    expected = {(f['kind'], f['seed'], f['a']) for f in native_plan['schedule']}
    if len(expected) != len(native_plan['schedule']) or set(episodes) != expected:
        raise ValueError('published_elo_episode_scope_mismatch')
    for fixture in native_plan['schedule']:
        checked_episode(episodes[fixture['kind'], fixture['seed'], fixture['a']], fixture, roster[fixture['a']])
    valid = sum(e['status'] == 'complete' for e in episodes.values())
    if (len(episodes), valid, len(episodes)-valid) != (summary['finished'], summary['valid'], summary['errors']):
        raise ValueError('published_elo_source_counts_mismatch')
    if summary['finished'] != summary['planned'] or len(episodes) != len(players)*len(kinds)*8:
        raise ValueError('published_elo_source_incomplete')

    schedule, receipts = [], []
    # Preserve the old canonical ordering: game, seed, registered model pair.
    for kind in kinds:
        for seed in range(native_plan['seed_base'], native_plan['seed_base']+8):
            for a, b in combinations(roster, 2):
                fixture = {'ordinal': len(schedule), 'kind': kind, 'seed': seed,
                           'a': a, 'b': b, 'leg': 0, 'a_side': 'X', 'mode': 'paired'}
                schedule.append(fixture)
                left, right = episodes[kind, seed, a], episodes[kind, seed, b]
                complete = left['status'] == right['status'] == 'complete'
                score = None
                if complete:
                    # Identical lexicographic comparison to compare_results;
                    # these are its already validated, persisted native keys.
                    x, y = tuple(left['comparison_key']), tuple(right['comparison_key'])
                    score = 1. if x > y else 0. if x < y else .5
                receipts.append({**fixture, 'status': 'complete' if complete else 'error',
                                 'score_a': score,
                                 'episode_a': left['episode_id'], 'episode_b': right['episode_id']})
    plan = {'revision': METHOD, 'participants': players, 'kinds': kinds,
            'seeds': 8, 'seed_base': native_plan['seed_base'],
            'initial_rating': INITIAL, 'k': K, 'schedule': schedule}
    overall, by_game = rating_tables(plan, receipts)
    for kind, rows in by_game.items():
        for row in rows:
            blocks = [e.get('stability', {}) for (k, _, ident), e in episodes.items()
                      if k == kind and ident == row['id']]
            row['stability'] = aggregate_stability(blocks)
    for row in overall:
        blocks = [next(r for r in rows if r['id'] == row['id'])['stability'] for rows in by_game.values()]
        # The original overall table averages available per-game metrics equally.
        stability = {k: sum(b[k] for b in blocks) for k in ('decisions', 'probability_decisions')}
        stability['probability_coverage'] = (stability['probability_decisions']/stability['decisions']
                                              if stability['decisions'] else None)
        for metric in METRICS:
            values = [b[metric] for b in blocks if b[metric] is not None]
            stability[metric] = sum(values)/len(values) if values else None
        row['stability'] = stability

    def pending():
        return {'id': ONESHOT, 'name': 'Blink', 'status': 'pending',
                'match_counts_available': False, 'overall_eligible': False,
                'coverage_complete': False, 'provisional': True,
                **dict.fromkeys(('rating', 'rank', 'coverage', 'required_games', 'played',
                                 'wins', 'draws', 'losses', 'errors', 'stability'), None)}

    if oneshot_id is None:
        overall.append(pending())
        for rows in by_game.values():
            rows.append(pending())
    else:
        for rows in [overall, *by_game.values()]:
            for row in rows:
                if row['id'] == oneshot_id:
                    row['name'] = 'Blink'
                    row['logo'] = './playground/logos/blink.svg'
    games = [{'id': kind, 'name': LABELS[kind][1], 'label_en': LABELS[kind][0],
              'label_zh': LABELS[kind][1], 'mode': 'paired', 'comparison': comparison_spec(kind)} for kind in kinds]
    public_players = [{'id': p['id'], 'name': 'Blink' if p['id'] == oneshot_id else p['name']} for p in players]
    if oneshot_id is None:
        public_players.append({'id': ONESHOT, 'name': 'Blink'})
    comparison_valid = sum(r['status'] == 'complete' for r in receipts)
    data = {'schema_version': SCHEMA, 'source': 'published_elo',
            'run_id': 'gamejev-public-20261021-independent-v4-elo',
            'state': 'complete_with_errors' if summary['errors'] else 'complete',
            'updated_at': datetime.fromtimestamp(summary['updated_at'], timezone.utc).isoformat(),
            'completed': summary['finished'], 'planned': summary['planned'], 'scored': valid,
            'errors': summary['errors'], 'managed_externally': True, 'controls_available': False,
            'replay_available': False,
            'protocol': {'run_type': METHOD, 'initial_rating': INITIAL, 'k': K,
                         'rating_rule': 'per-game Elo; overall is equal-weight mean with full game coverage',
                         'source_cohort': 'independent-fixed-opponent-v1',
                         'paired_rule': 'compare frozen native comparison_key lexicographically at identical game and seed',
                         'opponents': 'native fixed rule opponents or environment; no model head-to-head games',
                         'error_policy': 'source errors invalidate affected comparisons; never count as losses',
                         'execution_order': 'game, seed, registered participant pair',
                         'stability_rule': 'each source episode once; decision-weighted within game, equal game mean overall',
                         'decision_policy': 'jev-game-decision-policy-v2-realtime-single',
                         'kinds': kinds, 'participants': public_players,
                         'seeds': 8, 'seed_base': native_plan['seed_base'],
                         'new_model_requests': 0},
            'comparison_counts': {'planned': len(schedule), 'completed': len(receipts),
                                  'scored': comparison_valid, 'unscored': len(receipts)-comparison_valid},
            'fixed_config': {'games': games, 'baseline': public_players,
                             'seeds': 8, 'seed_base': native_plan['seed_base']},
            'baseline_progress': {'state': 'complete_with_errors' if summary['errors'] else 'complete',
                                  'completed': summary['finished'], 'planned': summary['planned'],
                                  'participants': [
                                      {'id': p['id'], 'state': 'complete_with_errors' if any(
                                          e['status'] == 'error' for (_, _, m), e in episodes.items() if m == p['id']) else 'complete',
                                       'completed': len(kinds)*8, 'planned': len(kinds)*8, 'coverage': len(kinds)}
                                      for p in players]+([{'id': ONESHOT, 'state': 'pending'}] if oneshot_id is None else [])},
            'overall': overall, 'by_game': by_game, 'matches': [],
            'replay_validation': replay_validation}
    assert_public_document(data)
    return data, plan, receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    args = parser.parse_args()
    load = lambda p: json.loads(p.read_text())
    native_plan = load(args.run/'plan.json')
    episodes = {}
    for fixture in native_plan['schedule']:
        kind, seed, model = fixture['kind'], fixture['seed'], fixture['a']
        episodes[kind, seed, model] = load(args.run/'episode_summaries'/f'{kind}-{seed}-{model}.json')
    published = load(Path(__file__).resolve().parents[1]/'leaderboard/arena-independent.json')
    data, plan, receipts = build(load(args.run/'summary.json'), native_plan, episodes, published['replay_validation'])
    write_json(args.audit_dir/'plan.json', plan)
    write_json(args.audit_dir/'comparisons.json', receipts)
    write_json(args.out, data)
    print(json.dumps({'source_games': data['completed'], 'source_errors': data['errors'],
                      'comparisons': data['comparison_counts'], 'oneshot': 'pending', 'new_requests': 0}))


if __name__ == '__main__':
    main()
