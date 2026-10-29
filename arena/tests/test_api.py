import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from blink_arena.app import create_app
from blink_arena.schemas import AppConfig, DecisionOutput


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv('JEV_LEADERBOARD_DIR', str(tmp_path / 'leaderboard'))
    app = create_app(data=tmp_path, config=AppConfig())
    calls = []
    app.state.mock_browser_calls = calls
    with TestClient(app) as client:
        client.get('/api/health')
        yield app, client, calls, tmp_path


def connect(client, ident='test-model', *, mock_browser=True, **extra):
    body = {'model_id': ident, 'name': 'Test model', 'served_model': 'actual-model',
            'adapter': 'decision', 'transport': 'browser'}
    body.update(extra)
    result = client.post('/api/v1/connections', json=body)
    assert result.status_code == 201, result.text
    if mock_browser:
        # Evaluation tests replace only the browser dispatch seam. A separate
        # test below exercises real HTTP polling and result submission.
        async def browser_result(request):
            client.app.state.mock_browser_calls.append(request.model_dump(mode='json'))
            opts = request.question.options
            probabilities = {o.id: 1/len(opts) for o in opts} if body['adapter'] == 'decision' else None
            return DecisionOutput(request_id=request.request_id, model=request.model,
                                  action=opts[0].id, probabilities=probabilities)
        client.app.state.providers.browser_relays[ident] = browser_result
    return result.json()


def decision():
    return {'model_id':'test-model','input':{'request_id':'r1','model':'actual-model',
        'observation':{'visible':True},'question':{'instructions':'Choose','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]}}}


def test_browser_connection_is_owned_strict_and_never_persists_credentials(server):
    app,c,calls,data=server
    connect(c)
    r=c.post('/api/v1/decisions',json=decision())
    assert r.status_code==200 and r.json()['probabilities']=={'a':.5,'b':.5}
    assert calls[0]['observation']=={'visible':True}
    with TestClient(app) as other:
        assert [m['id'] for m in other.get('/api/v1/models').json()['models']]==['oneshot-hosted']
        assert other.post('/api/v1/decisions',json=decision()).status_code==403
    for route in ['/api/health','/api/v1/connections','/api/openapi.json']:
        assert 'test-secret-value' not in c.get(route).text
    assert not list(data.rglob('*.json'))
    assert not any(hasattr(app.state.providers, field) for field in ('client', 'temporary_keys'))
    bad=decision();bad['input']['model']='different-model'
    assert c.post('/api/v1/decisions',json=bad).status_code==422


@pytest.mark.parametrize('forbidden', [
    {'endpoint': 'http://model.test/fixture-secret-value'},
    {'endpoint': None},
    {'api_key': 'fixture-secret-value'},
    {'api_key': None},
    {'transport': 'proxy'},
    {'api_key_env': 'FIXTURE_SECRET_ENV'},
])
def test_invalid_configuration_does_not_echo_secret(server, forbidden):
    app, client, _, _ = server
    body = {'model_id': 'invalid', 'name': 'Fixture', 'served_model': 'fixture',
            'adapter': 'decision', 'transport': 'browser', **forbidden}
    result = client.post('/api/v1/connections', json=body)
    assert result.status_code == 422
    assert 'fixture-secret-value' not in result.text and 'model.test' not in result.text
    assert not app.state.connections.entries


def test_openai_browser_result_does_not_invent_missing_probabilities(server):
    _,c,_,_=server
    connect(c,adapter='openai')
    r=c.post('/api/v1/decisions',json=decision())
    assert r.status_code==200 and r.json()['probabilities'] is None


def test_browser_queue_uses_metadata_without_keys(server):
    app,c,_,_=server
    connect(c, mock_browser=False)
    with ThreadPoolExecutor() as pool:
        future=pool.submit(c.post,'/api/v1/decisions',json=decision())
        batch=c.get('/api/v1/connections/test-model/requests').json()['requests']
        assert len(batch)==1 and batch[0]['model']=='actual-model'
        assert not hasattr(app.state.providers, 'temporary_keys')
        assert 'endpoint' not in batch[0] and 'api_key' not in batch[0]
        r=c.post('/api/v1/connections/test-model/results',json={'request_id':'r1','result':{'request_id':'r1','model':'actual-model','action':'b'}})
        assert r.json()['accepted']
        assert future.result(timeout=5).json()['action']=='b'
    app.state.connections.entries['test-model']['last_poll']=time.monotonic()-46
    assert not next(m for m in c.get('/api/v1/models').json()['models'] if m['id']=='test-model')['ready']


def test_board_revision_and_single_interactive_decision(server):
    _,c,calls,_=server
    connect(c)
    game=c.post('/api/game/new',json={'kind':'othello_6x6','seed':42}).json()
    body={'session_id':game['session_id'],'revision':0,'model':True}
    result=c.post('/api/game/move',json=body,headers={'X-Demo-Model':'test-model'})
    assert result.status_code==200,result.text
    assert len(calls)==1
    assert result.json()['result']['decision_policy']['repeat_count']==1
    assert 'decision_stability' not in result.json()['result']
    assert c.post('/api/game/move',json=body).status_code==409
    c.cookies.clear()
    assert c.post('/api/game/move',json={**body,'revision':1}).status_code==404


@pytest.mark.parametrize('kind', ['othello_6x6', 'hex_7x7', 'dots_and_boxes_3x3'])
def test_board_standard_start_and_explicit_seed_remain_distinct(server, kind):
    import jev_demo_games as board
    _, client, _, _ = server
    expected = board.visible(board.fresh(kind))
    first = client.post('/api/game/new', json={'kind': kind}).json()
    assert first['game'] == expected
    assert first['environment']['mode'] == 'standard'
    action = next(iter(first['game']['legal']))
    moved = client.post('/api/game/move', json={'session_id': first['session_id'], 'revision': 0, 'action': action})
    assert moved.status_code == 200 and moved.json()['game'] != expected
    # Numeric seeds, including zero, remain explicit reproducible curriculum
    # openings. They never leak into the following ordinary restart.
    for seed in (0, 42):
        seeded = client.post('/api/game/new', json={'kind': kind, 'seed': seed}).json()
        same = client.post('/api/game/new', json={'kind': kind, 'seed': seed}).json()
        assert seeded['game'] == same['game'] != expected
    restart = client.post('/api/game/new', json={'kind': kind}).json()
    assert restart['session_id'] != first['session_id']
    assert restart['revision'] == 0 and restart['game'] == expected


def test_leaderboard_write_requires_explicit_admin_and_checks_contract(server,monkeypatch):
    _,c,_,data=server
    doc={'benchmark_id':'jevbench','title':'JevBench','version':'test','metric':'accuracy',
         'rows':[{'model_id':'model','model_name':'Model','score':.75}]}
    url='/api/v1/leaderboards/jevbench'
    assert c.put(url,json=doc).status_code==403
    monkeypatch.setenv('JEV_ADMIN_TOKEN','test-admin')
    h={'Authorization':'Bearer test-admin'}
    assert c.put(url,json=doc,headers=h).status_code==200
    assert c.get(url).json()['rows'][0]['score']==.75
    doc['rows'][0]['score']=2
    assert c.put(url,json=doc,headers=h).status_code==422
    assert c.get(url).json()['rows'][0]['score']==.75
    assert c.get('/api/v1/leaderboards/../config').status_code==404


def test_prefix_assets_and_cross_origin_write(tmp_path):
    with TestClient(create_app(data=tmp_path,prefix='/demo')) as c:
        assert c.get('/demo/').status_code==200
        assert c.get('/demo/api/openapi.json').status_code==200
        assert c.post('/demo/api/game/new',json={'kind':'othello_6x6'},headers={'Origin':'https://other.test'}).status_code==403


def test_explicit_public_origin_behind_https_proxy(tmp_path, monkeypatch):
    origin = 'https://434426-proxy-8080.dsw-gateway-cn-beijing.data.aliyun.com'
    monkeypatch.setenv('JEV_PUBLIC_ORIGIN', origin)
    with TestClient(create_app(data=tmp_path, prefix='/demo')) as c:
        route = '/demo/api/game/new'
        body = {'kind': 'othello_6x6'}
        assert c.post(route, json=body, headers={'Origin': origin}).status_code == 200
        assert c.post(route, json=body, headers={'Origin': origin + ':443'}).status_code == 200
        assert c.post(route, json=body, headers={'Origin': 'http://testserver'}).status_code == 200
        for foreign in ['https://other.test', origin + '.other.test', origin + ':444', origin + ':0',
                        origin.replace('https:', 'http:'), 'null', origin + '/page']:
            assert c.post(route, json=body, headers={
                'Origin': foreign, 'X-Forwarded-Host': foreign,
                'X-Forwarded-Proto': 'https'}).status_code == 403
        # Deployment metadata does not grant leaderboard write permission.
        assert c.put('/demo/api/v1/leaderboards/jevbench', json={
            'benchmark_id': 'jevbench', 'title': 'JevBench', 'version': 'test',
            'metric': 'accuracy', 'rows': []}, headers={'Origin': origin}).status_code == 403


def test_complete_evaluation_replay_and_incremental_enrollment(server):
    app,c,calls,data=server
    connect(c,'a');connect(c,'b')
    result=c.post('/api/v1/evaluations',json={'model_ids':['a','b'],'games':['othello_6x6','blackjack'],'seed_base':42,'concurrency':2})
    assert result.status_code==201,result.text
    ident=result.json()['run_id']
    def wait_finished():
        until=time.monotonic()+35
        while time.monotonic()<until:
            status=c.get('/api/v1/evaluations/'+ident).json()
            if status['state'] not in ('running','pausing'): return status
            time.sleep(.03)
        pytest.fail('Mock evaluation did not finish')
    status=wait_finished()
    assert status['state']=='complete',status
    assert status['scored']==status['planned']==3
    folder=data/'evaluations'/ident
    before={p.name:p.read_bytes() for p in (folder/'matches').glob('*.json')}
    replay=c.get('/api/v1/evaluations/'+ident+'/export')
    assert replay.status_code==200,replay.text
    assert len(replay.json()['replays']['matches'])==3
    connect(c,'c')
    result=c.post('/api/v1/evaluations/'+ident+'/models/c')
    assert result.status_code==200,result.text
    status=wait_finished()
    assert status['state']=='complete',status
    assert status['scored']==status['planned']==9
    assert all((folder/'matches'/name).read_bytes()==content for name,content in before.items())
    assert 'test-secret-value' not in ''.join(p.read_text() for p in folder.rglob('*.json'))
