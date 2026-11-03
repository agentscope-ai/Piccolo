"""The read-only website preview exposes the same published Arena as production."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from blink_arena.elo_ranking import rank_rows
from blink_arena.game_scope import project_arena
from blink_arena.paths import REPO
from jev_control_scope import active_games
from scripts.preview_leaderboard import create_preview_app


class PreviewLeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_preview_preserves_published_models_games_ratings_and_rankings(self):
        path = REPO / 'leaderboard/arena-elo.json'
        original = path.read_bytes()
        saved = json.loads(original)
        with TestClient(create_preview_app()) as client:
            response = client.get('/api/elo')
            assert response.status_code == 200
            result = response.json()
            assert result == project_arena(saved)
            assert result['controls_available'] is False
            assert client.post('/api/elo/join').status_code == 405
        assert path.read_bytes() == original
        assert {row['id'] for row in result['overall']} == {row['id'] for row in saved['overall']}
        expected_games = active_games(saved['by_game'])
        assert set(result['by_game']) == set(expected_games)
        assert {game['id'] for game in result['fixed_config']['games']} == set(expected_games)
        for game in expected_games:
            assert result['by_game'][game] == saved['by_game'][game]
        for row in result['overall']:
            games = [next(item for item in saved['by_game'][game] if item['id'] == row['id'])
                     for game in expected_games]
            assert row['rating'] == sum(game['rating'] for game in games) / len(games)
            assert row['coverage'] == len(games)
        scores = [row['rating'] for row in result['overall']]
        assert scores == sorted(scores, reverse=True)
        assert [row['rank'] for row in result['overall']] == list(range(1, len(scores) + 1))


    def test_preview_prefers_current_published_elo_and_never_fabricates_missing_results(self):
        tmp_path = self.directory
        source = REPO / 'leaderboard'
        for name in ('arena-elo.json', 'arena-independent.json'):
            (tmp_path / name).write_bytes((source / name).read_bytes())
        with TestClient(create_preview_app(leaderboard_dir=tmp_path)) as client:
            assert client.get('/api/elo').json()['schema_version'] == 'jev.arena.published-elo.v1'
            (tmp_path / 'arena-elo.json').unlink()
            assert client.get('/api/elo').json()['schema_version'] == 'jev.arena.independent-results.v1'
            (tmp_path / 'arena-independent.json').unlink()
            result = client.get('/api/elo').json()
            assert result['state'] == 'idle'
            assert result['overall'] == [] and result['by_game'] == {} and result['matches'] == []
            assert result['controls_available'] is False


    def test_preview_rejects_invalid_or_private_snapshots(self):
        tmp_path = self.directory
        saved = json.loads((REPO / 'leaderboard/arena-elo.json').read_text())
        target = tmp_path / 'arena-elo.json'
        with TestClient(create_preview_app(leaderboard_dir=tmp_path)) as client:
            for changed in ([], {**saved, 'schema_version': 'unknown'},
                            {**saved, 'endpoint': 'private-serving-location'}):
                target.write_text(json.dumps(changed))
                response = client.get('/api/elo')
                assert response.status_code == 503
                assert 'private-serving-location' not in response.text
            target.write_text('{broken JSON')
            assert client.get('/api/elo').status_code == 503


    def test_preview_source_links_return_the_registered_record(self):
        source = json.loads((REPO / 'leaderboard/harnessjevbench.json').read_text())
        row = next(item for item in source['rows'] if item['model_id'] == 'blink-27b-1028')
        with TestClient(create_preview_app()) as client:
            response = client.get('/api/leaderboard/source/harnessjevbench-blink-27b-1028')
            assert response.status_code == 200
            assert response.json() == {'benchmark': 'harnessjevbench', 'version': source['version'], 'result': row}
            assert client.get('/api/leaderboard/source/harnessjevbench-unknown').status_code == 404


    def test_shared_ranking_preserves_ties_and_missing_scores(self):
        rows = [dict(id='missing', rating=None), dict(id='b', rating=1500),
                dict(id='winner', rating=1600), dict(id='a', rating=1500)]
        ranked = rank_rows(copy.deepcopy(rows))
        assert [(row['id'], row['rank']) for row in ranked] == [('winner', 1), ('a', 2), ('b', 2), ('missing', None)]
        assert all('_rating' not in row for row in ranked)
        assert [row['id'] for row in rows] == ['missing', 'b', 'winner', 'a']
