"""Stale public game rankings and replay mounts must never reappear."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from blink_arena.app import create_app
from blink_arena.schemas import AppConfig
from blink_arena.leaderboards import Leaderboards, PUBLIC_BENCHMARKS
from blink_arena.public_surface import REMOVED_FILES
from scripts.preview_leaderboard import create_preview_app
from scripts.build_release import excluded

@pytest.mark.parametrize('prefix', ['', '/piccolo'])
@pytest.mark.parametrize('preview', [False, True])
def test_stale_mounts_and_runtime_cannot_publish_scores_or_replays(tmp_path, prefix, preview):
    if preview and prefix:
        return
    web=tmp_path/'web'; web.mkdir()
    (web/'playground').mkdir(); (web/'leaderboard').mkdir()
    published=tmp_path/'published'; published.mkdir()
    marker='stale-private-game-result'
    for name in REMOVED_FILES:
        (web/'playground'/name).write_text(marker)
        (web/'leaderboard'/name).write_text(marker)
        (published/name).write_text(marker)
    (web/'index.html').write_text('fixture')
    runtime=tmp_path/'runtime'
    (runtime/'evaluations').mkdir(parents=True)
    (runtime/'evaluations/latest.json').write_text(json.dumps({'run_id':marker}))
    app=(create_preview_app(web=web,leaderboard_dir=published) if preview else
         create_app(data=runtime,web=web,config=AppConfig(),leaderboard_dir=published,prefix=prefix))
    with TestClient(app) as client:
        for route in ['/api/elo','/api/elo/join','/api/v1/leaderboards/arena',
                      '/api/v1/evaluations','/api/v1/evaluations/old/export']:
            for method in ('get','post','put'):
                response=getattr(client,method)(prefix+route)
                assert response.status_code==404,(route,method,response.text)
                assert marker not in response.text
        for name in REMOVED_FILES:
            for folder in ('playground','leaderboard'):
                assert client.get(f'{prefix}/{folder}/{name}').status_code==404
        projection=client.get(prefix+'/api/leaderboard').json()
        assert tuple(b['id'] for b in projection['benchmarks'])==PUBLIC_BENCHMARKS
        assert marker not in json.dumps(projection)
        # A mounted old index or bundled leaderboard script cannot restore even
        # the old navigation while known score/replay assets remain blocked.
        for name in ('index.html', 'playground/leaderboard.js', 'piccolo.html'):
            (web/name).write_text('GameJevArena gameEloPanel gamejevbench')
            assert client.get(prefix+'/'+name).status_code==404
        assert client.get(prefix+'/').status_code==404
    store=Leaderboards(directory=published)
    with pytest.raises(ValueError):store.get('arena')
    for name in REMOVED_FILES:assert excluded('leaderboard/'+name)

def test_no_public_game_snapshots_or_players_in_current_tree():
    root=Path(__file__).resolve().parents[1]
    for folder in ('leaderboard','web/playground'):
        for name in REMOVED_FILES:
            assert not (root/folder/name).exists()
