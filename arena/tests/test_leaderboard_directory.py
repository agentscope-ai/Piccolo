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
    # Legacy import and archive tests deliberately exclude the newer published cohort.
    shutil.copytree(REPO / 'leaderboard', target, ignore=shutil.ignore_patterns('history','arena-independent.json','arena-elo.json'))
    return target


def test_one_directory_serves_benchmarks_arena_and_replays(tmp_path):
    directory = copied_results(tmp_path)
    app = create_app(data=tmp_path / 'runtime', config=AppConfig(), leaderboard_dir=directory)
    with TestClient(app) as client:
        for benchmark in ('jevbench', 'decisionindex', 'decisionindex-vision', 'harnessjevbench', 'datajevbench'):
            expected = json.loads((directory / f'{benchmark}.json').read_text())
            response = client.get(f'/api/v1/leaderboards/{benchmark}')
            assert response.status_code == 200
            assert response.json() == expected
        assert client.get('/api/elo').status_code == 404


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
        assert client.get('/api/elo').status_code == 404




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
        assert client.get('/api/elo').status_code == 404


def test_projection_timestamps_follow_each_source_file(tmp_path):
    import os
    from datetime import datetime, timezone
    directory = copied_results(tmp_path)
    expected = {}
    for index, (ident, filename) in enumerate((('jevbench', 'jevbench.json'), ('decisionindex', 'decisionindex.json'), ('decisionindex-vision', 'decisionindex-vision.json'),
                                              ('harnessjevbench', 'harnessjevbench.json'), ('datajevbench', 'datajevbench.json'))):
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
    for ident in ('jevbench', 'harnessjevbench', 'datajevbench'):
        assert next_rows[ident]['updated_at'] == expected[ident]


def test_missing_results_have_no_fabricated_update_time(tmp_path):
    projection = Leaderboards(directory=tmp_path).projection()
    assert projection['updated_at'] is None
    assert all(row.get('updated_at') is None for row in projection['benchmarks'])
