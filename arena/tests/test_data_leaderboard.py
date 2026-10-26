"""Data results use the public contract without replacing native Arena data."""
from fastapi.testclient import TestClient
from blink_arena.app import create_app
from blink_arena.leaderboards import Leaderboards
from blink_arena.schemas import AppConfig,LeaderboardDocument


def test_data_results_api_projection_source_and_arena_preservation(tmp_path):
    directory=tmp_path/'results';directory.mkdir()
    arena=b'{"untouched": "native arena fixture"}\n'
    replay=b'{"untouched": "native replay fixture"}\n'
    (directory/'arena.json').write_bytes(arena);(directory/'arena-replays.json').write_bytes(replay)
    doc=LeaderboardDocument(benchmark_id='datajevbench',title='DataJevBench',version='V0.5',metric='accuracy',rows=[
        {'model_id':'zero','model_name':'Zero','score':0,'metrics':{'accuracy':0,'brier':None,'ece':None},'axes':[{'id':'D1','label_en':'D1','label_zh':'D1','score':0}]},
        {'model_id':'pending','model_name':'Pending','score':None,'status':'pending','metrics':{'accuracy':None,'brier':None,'ece':None}},
        {'model_id':'complete','model_name':'Complete','score':.822,'metrics':{'accuracy':.822,'brier':.2429586814632819,'ece':.06370926404433189,'accuracy_n':500}}
    ])
    store=Leaderboards(directory=directory);store.put(doc)
    with TestClient(create_app(data=tmp_path/'runtime',config=AppConfig(),leaderboard_dir=directory)) as c:
        assert c.get('/api/v1/leaderboards/datajevbench').json()==doc.model_dump(mode='json')
        projection=next(b for b in c.get('/api/leaderboard').json()['benchmarks'] if b['id']=='datajevbench')
        assert [r['model_key'] for r in projection['display_rows']]==['complete','zero','pending']
        assert projection['display_rows'][1]['score']==0 and projection['display_rows'][2]['score'] is None
        row=projection['display_rows'][0]
        assert row['display_metrics']['accuracy']==.822 and row['display_metrics']['brier']==.2429586814632819
        source=c.get('/api/leaderboard/source/datajevbench-complete').json()
        assert source['result']['model_id']=='complete' and source['result']['score']==.822
    assert (directory/'arena.json').read_bytes()==arena
    assert (directory/'arena-replays.json').read_bytes()==replay
