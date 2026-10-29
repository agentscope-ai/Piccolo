"""The published ladder keeps the original Elo and stability semantics."""
import copy
import json
import math

from fastapi.testclient import TestClient
import pytest

from blink_arena.app import create_app
from blink_arena.paths import REPO
from blink_arena.privacy import assert_public_document
from blink_arena.schemas import AppConfig
from jev_demo_elo import rating_tables
from scripts.publish_public_elo import aggregate_stability, checked_episode, ONESHOT
from jev_demo_arena_episodes import comparison_spec, decision_policy


def published():
    return json.loads((REPO/'leaderboard/arena-elo.json').read_text())


def test_original_elo_formula_and_equal_game_average_ignore_failed_comparisons():
    plan = {'participants': [{'id': x, 'name': x} for x in ('a', 'b')],
            'kinds': ['hex_7x7', 'chess'], 'schedule': [
                {'ordinal': 0, 'kind': 'hex_7x7', 'a': 'a', 'b': 'b'},
                {'ordinal': 1, 'kind': 'hex_7x7', 'a': 'a', 'b': 'b'},
                {'ordinal': 2, 'kind': 'chess', 'a': 'a', 'b': 'b'}]}
    receipts = [{**f, 'status': 'error' if f['ordinal'] == 1 else 'complete',
                 'score_a': None if f['ordinal'] == 1 else 1 if f['ordinal'] == 0 else .5}
                for f in plan['schedule']]
    overall, games = rating_tables(plan, list(reversed(receipts)))
    assert games['hex_7x7'][0]['rating'] == 1516
    assert games['chess'][0]['rating'] == 1500
    assert overall[0]['rating'] == 1508
    assert (overall[0]['played'], overall[0]['wins'], overall[0]['draws'], overall[0]['errors']) == (2, 1, 1, 1)


def test_published_elo_has_full_game_coverage_with_exact_rl_checkpoint():
    data = published()
    assert_public_document(data)
    assert (data['planned'], data['completed'], data['scored'], data['errors']) == (1760, 1760, 1754, 6)
    assert data['comparison_counts'] == dict(planned=7920, completed=7920, scored=7866, unscored=54)
    assert data['source_episode_counts'] == dict(reused_baseline=1584, new_checkpoint=176)
    release = data['oneshot_release']
    assert release == dict(id='oneshot-rl-r6-iter0000019', variant='RL R6', iteration=19,
                           source_episodes=176, valid_episodes=176, episode_errors=0)
    assert ONESHOT not in {r['id'] for r in data['overall']}
    oneshot = next(r for r in data['overall'] if r['id'] == release['id'])
    assert oneshot['name'] == 'Blink' and oneshot['rating'] is not None
    assert data['protocol']['new_model_requests'] == 0
    assert len(data['by_game']) == 22
    for row in data['overall']:
        games = [next(r for r in rows if r['id'] == row['id']) for rows in data['by_game'].values()]
        assert row['rating'] == sum(g['rating'] for g in games)/22
        assert row['coverage'] == row['required_games'] == 22
        for key in ('played', 'wins', 'draws', 'losses', 'errors'):
            assert row[key] == sum(g[key] for g in games)
        for metric in ('agreement_rate', 'probability_stability', 'mean_probability_variance'):
            values = [g['stability'][metric] for g in games if g['stability'][metric] is not None]
            assert row['stability'][metric] == sum(values)/len(values)
    for rows in [data['overall'], *data['by_game'].values()]:
        active = [r for r in rows if r.get('status') != 'pending']
        assert len(active) == len(rows) == 10
        assert all(r['played'] == r['wins']+r['draws']+r['losses'] for r in active)
        assert math.isclose(sum(r['rating'] for r in active), 1500*10)
        assert sum(r['wins'] for r in active) == sum(r['losses'] for r in active)
    for kind in ('mario_platformer', 'snake_navigation', 'tetris_placement', 'terraria_survival'):
        assert all(r['stability']['agreement_rate'] is None for r in data['by_game'][kind] if r['id'] != ONESHOT)
    assert data['replay_validation']['mario']['strict_passed'] == 80


def test_original_stability_weights_decisions_within_each_game():
    blocks = [{'decisions': 1, 'probability_decisions': 0, 'agreement_rate': .5},
              {'decisions': 3, 'probability_decisions': 2, 'agreement_rate': 1,
               'probability_stability': .8, 'mean_probability_variance': .02}]
    result = aggregate_stability(blocks)
    assert result['decisions'] == 4 and result['probability_decisions'] == 2
    assert result['agreement_rate'] == .875
    assert result['probability_stability'] == .8
    assert result['mean_probability_variance'] == .02


@pytest.mark.parametrize('kind', ['hex_7x7', 'mario_platformer'])
def test_native_score_summary_must_match_model_seed_and_scoring_contract(kind):
    participant = {'id': 'a', 'name': 'a'}
    fixture = {'kind': kind, 'seed': 42}
    spec = comparison_spec(kind)
    episode = {'status': 'complete', 'kind': kind, 'seed': 42, 'model': 'a',
               'episode_id': f'{kind}-42-a',
               'comparison_spec': spec, 'episode_revision': spec['revision'],
               'engine_revision': spec['engine_revision'], 'higher_is_better': True,
               'decision_policy': decision_policy(kind), 'comparison_key': [1.]*len(spec['score_fields']),
               'replay_verified': True, 'replay_validation': {'strict_match': True, 'relaxed_count': 0},
               'binding': {'participant': participant, 'kind': kind, 'seed': 42,
                           'comparison': spec, 'episode_revision': spec['revision'],
                           'engine_revision': spec['engine_revision'],
                           'decision_policy': 'jev-game-decision-policy-v2-realtime-single'}}
    assert checked_episode(episode, fixture, participant) is episode
    for field, value in [('seed', 43), ('model', 'b'), ('comparison_key', [float('nan')]),
                         ('comparison_spec', {}), ('decision_policy', {})]:
        changed = copy.deepcopy(episode); changed[field] = value
        with pytest.raises(ValueError):
            checked_episode(changed, fixture, participant)
    if kind == 'mario_platformer':
        for field, value in [('replay_verified', False), ('replay_validation', {}),
                             ('replay_validation', {'strict_match': True, 'relaxed_count': 1})]:
            changed = copy.deepcopy(episode); changed[field] = value
            with pytest.raises(ValueError, match='published_mario_replay_not_strict'):
                checked_episode(changed, fixture, participant)


def test_frontend_prefers_published_elo_over_success_view_and_old_runtime(tmp_path):
    import shutil
    directory = tmp_path/'published'; directory.mkdir()
    for name in ('arena-elo.json', 'arena-independent.json', 'arena.json'):
        shutil.copy2(REPO/'leaderboard'/name, directory/name)
    runtime = tmp_path/'runtime'
    (runtime/'evaluations').mkdir(parents=True)
    (runtime/'evaluations/latest.json').write_text(json.dumps({'run_id': 'old-runtime-pointer'}))
    with TestClient(create_app(data=runtime, config=AppConfig(), leaderboard_dir=directory)) as client:
        assert client.get('/api/elo').json() == published()
        arena = next(b for b in client.get('/api/leaderboard').json()['benchmarks'] if b['id'] == 'gamejevbench')
        assert arena['source_file'] == 'arena-elo.json'
