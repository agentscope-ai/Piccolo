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
