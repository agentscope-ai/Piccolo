"""All published results share one portable, explicitly configurable folder."""
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from blink_arena.app import create_app
from blink_arena.leaderboards import Leaderboards
from blink_arena.paths import REPO, leaderboard_directory
from blink_arena.schemas import AppConfig, LeaderboardDocument


def copied_results(tmp_path):
    target = tmp_path / 'published'
    shutil.copytree(REPO / 'leaderboard', target, ignore=shutil.ignore_patterns('history'))
    return target


def test_one_directory_serves_benchmarks_arena_and_replays(tmp_path):
    directory = copied_results(tmp_path)
    app = create_app(data=tmp_path / 'runtime', config=AppConfig(), leaderboard_dir=directory)
    with TestClient(app) as client:
        for benchmark in ('jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench'):
            expected = json.loads((directory / f'{benchmark}.json').read_text())
            response = client.get(f'/api/v1/leaderboards/{benchmark}')
            assert response.status_code == 200
            assert response.json() == expected
        original = json.loads((directory / 'arena.json').read_text())
        arena = client.get('/api/elo').json()
        assert arena['run_id'] == original['run_id']
        assert arena['overall'] == original['overall']
        assert arena['by_game'] == original['by_game']
        replay = client.get('/playground/visible-control.js')
        assert replay.status_code == 200
        archive = json.loads(replay.text.removeprefix('window.BlinkArenaReplayArchive=').removesuffix(';'))
        assert archive == json.loads((directory / 'arena-replays.json').read_text())


def test_directory_environment_and_external_updates(tmp_path, monkeypatch):
    directory = copied_results(tmp_path)
    monkeypatch.setenv('JEV_LEADERBOARD_DIR', str(directory))
    monkeypatch.setenv('JEV_DATA_DIR', str(tmp_path / 'unrelated-runtime'))
    store = Leaderboards()
    assert leaderboard_directory() == directory
    assert store.path('jevbench') == directory / 'jevbench.json'
    document = json.loads(store.path('jevbench').read_text())
    document['version'] = 'external-update-fixture'
    store.path('jevbench').write_text(json.dumps(document))
    assert store.get('jevbench').version == 'external-update-fixture'
    app = create_app(data=tmp_path / 'runtime', config=AppConfig())
    with TestClient(app) as client:
        assert client.get('/api/v1/leaderboards/jevbench').json()['version'] == 'external-update-fixture'
        assert client.get('/api/elo').json()['run_id'] == json.loads((directory / 'arena.json').read_text())['run_id']


def test_arena_rating_import_preserves_native_snapshot_and_replay(tmp_path):
    directory = copied_results(tmp_path)
    originals = {name: (directory / name).read_bytes() for name in ('arena.json', 'arena-replays.json')}
    store = Leaderboards(directory=directory)
    assert store.get('arena') is None
    doc = LeaderboardDocument.model_validate({
        'benchmark_id': 'arena', 'title': 'Arena ratings', 'version': 'fixture-v1',
        'metric': 'elo', 'score_scale': [0, 3000], 'axis_scale': [0, 3000],
        'rows': [{'model_id': 'fixture-model', 'model_name': 'Fixture', 'score': 1500,
                  'axes': [{'id': 'blackjack', 'label_en': 'Blackjack', 'label_zh': '二十一点', 'score': 1500}]}],
    })
    store.put(doc)
    assert store.path('arena').name == 'arena-ratings.json'
    assert store.get('arena') == doc
    for name, value in originals.items():
        assert (directory / name).read_bytes() == value
    app = create_app(data=tmp_path / 'runtime', config=AppConfig(), leaderboard_dir=directory)
    with TestClient(app) as client:
        response = client.get('/api/elo')
        assert response.status_code == 200
        assert response.json()['source'] == 'imported_ratings'
        assert response.json()['overall'][0]['rating'] == 1500


def test_no_hidden_fallback_to_old_runtime_or_seed_paths(tmp_path):
    old_data = tmp_path / 'runtime' / 'leaderboards'
    old_data.mkdir(parents=True)
    (old_data / 'jevbench.json').write_text('not a supported result')
    directory = tmp_path / 'empty-public-directory'
    store = Leaderboards(tmp_path / 'runtime', REPO / 'data/seed', directory=directory)
    assert store.get('jevbench') is None
    app = create_app(data=tmp_path / 'runtime', config=AppConfig(), leaderboard_dir=directory)
    with TestClient(app) as client:
        assert client.get('/api/v1/leaderboards/jevbench').status_code == 404
        assert client.get('/api/elo').json()['state'] == 'idle'


def test_projection_timestamps_follow_each_source_file(tmp_path):
    import os
    from datetime import datetime, timezone
    directory = copied_results(tmp_path)
    expected = {}
    for index, (ident, filename) in enumerate((('jevbench', 'jevbench.json'), ('decisionindex', 'decisionindex.json'),
                                              ('harnessjevbench', 'harnessjevbench.json'), ('datajevbench', 'datajevbench.json'), ('gamejevbench', 'arena.json'))):
        stamp = 1_700_000_000 + index * 3600
        os.utime(directory / filename, (stamp, stamp))
        expected[ident] = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
    store = Leaderboards(directory=directory)
    first = store.projection()
    assert {row['id']: row['updated_at'] for row in first['benchmarks']} == expected
    assert store.projection() == first  # Refreshing cannot make unchanged data look new.
    stamp = 1_800_000_000
    os.utime(directory / 'decisionindex.json', (stamp, stamp))
    next_rows = {row['id']: row for row in store.projection()['benchmarks']}
    assert next_rows['decisionindex']['updated_at'] == datetime.fromtimestamp(stamp, timezone.utc).isoformat()
    for ident in ('jevbench', 'harnessjevbench', 'datajevbench', 'gamejevbench'):
        assert next_rows[ident]['updated_at'] == expected[ident]


def test_missing_results_have_no_fabricated_update_time(tmp_path):
    projection = Leaderboards(directory=tmp_path).projection()
    assert projection['updated_at'] is None
    assert all(row.get('updated_at') is None for row in projection['benchmarks'])
