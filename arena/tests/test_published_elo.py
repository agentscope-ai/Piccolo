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
