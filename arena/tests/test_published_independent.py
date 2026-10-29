import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from blink_arena.app import create_app
from blink_arena.paths import REPO
from blink_arena.privacy import assert_public_document
from blink_arena.schemas import AppConfig


def test_published_results_keep_evidence_denominators_and_pending_oneshot():
    data = json.loads((REPO/'leaderboard/arena-independent.json').read_text())
    assert_public_document(data)
    rows = [r for r in data['overall'] if r['status'] != 'pending']
    assert (len(rows),len(data['by_game']),data['completed'],data['scored'],data['errors']) == (9,22,1584,1578,6)
    assert sum(r['valid'] for r in rows) == 1578
    assert sum(r['errors'] for r in rows) == 6
    assert sum(r['planned'] for r in rows) == 1584
    for row in rows:
        per_game = [next(g for g in table if g['id']==row['id']) for table in data['by_game'].values()]
        assert all(g['planned']==8 and g['valid']+g['errors']==8 for g in per_game)
        assert row['score'] == sum(g['wins'] for g in per_game)/176
        assert row['errors'] == sum(g['errors'] for g in per_game)
        assert all(g['score']==g['wins']/8 for g in per_game)
    for table in [data['overall'],*data['by_game'].values()]:
        missing = [r for r in table if r['status']=='pending']
        assert len(missing)==1 and missing[0]['name']=='Blink'
        assert all(missing[0][k] is None for k in ('score','success_rate','success_rate_valid','wins','valid','errors','latency_current','latency_all'))
    assert data['replay_validation']['mario']['strict_passed']==72
    luna = next(r for r in rows if 'gpt-6-luna' in r['id'])
    assert luna['success_rate']==49/176 and luna['success_rate_valid']==49/170


def test_frontend_prefers_published_cohort_over_stale_runtime_and_legacy_elo(tmp_path):
    results = tmp_path/'results'
    results.mkdir()
    for name in ('arena-independent.json','arena.json'):
        shutil.copy2(REPO/'leaderboard'/name, results/name)
    runtime = tmp_path/'runtime'
    (runtime/'evaluations').mkdir(parents=True)
    (runtime/'evaluations/latest.json').write_text(json.dumps({'run_id':'old-runtime-pointer'}))
    app = create_app(data=runtime, config=AppConfig(), leaderboard_dir=results)
    with TestClient(app) as client:
        payload = client.get('/api/elo')
        assert payload.status_code==200
        assert payload.json()==json.loads((results/'arena-independent.json').read_text())
        projection=client.get('/api/leaderboard').json()
        arena=next(b for b in projection['benchmarks'] if b['id']=='gamejevbench')
        assert arena['source_file']=='arena-independent.json'
