"""Standalone HTTP boundary for browser play, model connections and evaluation."""
import asyncio
import contextvars
import hmac
import gzip
import json
import os
import re
import secrets
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import ValidationError

from .paths import CONFIG, DATA, SEED, WEB
from .schemas import (AppConfig, ConnectionCreate, RelayResult, DecisionCall,
                      EvaluationCreate, SessionCreate, SessionStep, LeaderboardDocument)
from .providers import Providers
from .connections import Connections
from .sessions import Sessions
from .evaluations import Evaluations
from .leaderboards import Leaderboards
import jev_demo_games as board
import jev_demo_showcases as showcases
import jev_demo_mbti as mbti
from jev_demo_decision_stability import repeated_predict
from jev_demo_game_evaluation import KINDS
from jev_environment_seeds import condition_info
from jev_engine_registry import get_engine, list_engines
from jev_control_scope import active_games

owner_context = contextvars.ContextVar('jev_owner', default='')
model_context = contextvars.ContextVar('jev_model', default='')
SAFE_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$')


def _http_origin(value):
    """Compare browser origins without trusting arbitrary forwarded headers."""
    if not value or any(c.isspace() for c in value):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme not in ('http', 'https') or not url.hostname
                or url.username is not None or url.password is not None
                or url.path not in ('', '/') or url.query or url.fragment):
            return None
        port = url.port
        return url.scheme, url.hostname.lower(), port if port is not None else (443 if url.scheme == 'https' else 80)
    except ValueError:
        return None


def create_app(*, data=DATA, seed=SEED, web=WEB, config=None, prefix='', frontend=None, leaderboard_dir=None,
               rollout_options=None, rollout_opponent=None):
    prefix = prefix.rstrip('/')
    if prefix and (not prefix.startswith('/') or '..' in prefix or not re.fullmatch(r'/[A-Za-z0-9_/-]+', prefix)):
        raise ValueError('Invalid URL prefix')
    public_origin_value = os.environ.get('JEV_PUBLIC_ORIGIN')
    public_origin = _http_origin(public_origin_value)
    if public_origin_value is not None and public_origin is None:
        raise ValueError('JEV_PUBLIC_ORIGIN must be an HTTP(S) origin without a path')
    config = config or AppConfig.model_validate_json(CONFIG.read_text())
    providers = Providers(config)
    from .hosted_model import HostedModel
    hosted = HostedModel()
    providers.models[hosted.spec.id] = hosted.spec
    providers.server_relays[hosted.spec.id] = hosted.decide
    providers.slots[hosted.spec.id] = asyncio.Semaphore(hosted.spec.concurrency)
    providers.availability[hosted.spec.id] = lambda: hosted.ready
    connections = Connections(providers)
    legacy_owners = {}
    board_sessions = {}
    frontend = frontend or 'http://127.0.0.1:8080'+prefix

    def selected_model(): return model_context.get()

    async def predict(record, qid, model=None):
        from .model_inputs import project_record
        record = project_record(record)
        ident = model or selected_model()
        connections.require(ident, owner_context.get())
        result = await providers.predict(record, qid, model=ident)
        return {**result, 'decision_policy': {'revision': 'jev.interactive-single.v1',
                'repeat_count': 1, 'option_order': 'original', 'reason': 'interactive_play'}}

    async def evaluation_predict(record, qid, model=None):
        from .model_inputs import project_record
        record = project_record(record)
        ident = model or selected_model()
        connections.require(ident, owner_context.get())
        return await repeated_predict(providers.predict, record, qid, model=ident)

    sessions = Sessions(predict, frontend)
    evaluations = Evaluations(data, seed, providers, evaluation_predict, frontend, selected_model, leaderboard_dir=leaderboard_dir)
    leaderboards = Leaderboards(data, seed, directory=leaderboard_dir)
    from .rollouts import Rollouts
    from jev_engine_rollout_backend import install as install_rollouts
    rollout_settings = {
        'decision_timeout': float(os.environ.get('JEV_ROLLOUT_DECISION_TIMEOUT', '90')),
        'max_active': int(os.environ.get('JEV_ROLLOUT_MAX_ACTIVE', '16')),
        'completed_cache_size': int(os.environ.get('JEV_ROLLOUT_CACHE_SIZE', '32')),
        'completed_cache_bytes': int(os.environ.get('JEV_ROLLOUT_CACHE_BYTES', str(64*1024*1024))),
    }
    rollout_settings.update(rollout_options or {})
    rollouts = Rollouts(Path(data)/'rollouts', frontend, opponent=rollout_opponent, **rollout_settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await rollouts.close()
        await evaluations.close()
        await sessions.close()
        await providers.close()
        await hosted.close()

    app = FastAPI(title='PiccoloArena API', version='1.0.0', lifespan=lifespan,
                  openapi_url=prefix+'/api/openapi.json', docs_url=None, redoc_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.state.providers, app.state.connections = providers, connections
    app.state.sessions, app.state.evaluations, app.state.leaderboards = sessions, evaluations, leaderboards
    app.state.rollouts = rollouts
    app.state.hosted_model = hosted
    install_rollouts(app, prefix, rollouts, owner_resolver=lambda request: owner_context.get())

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        # Pydantic input/context may contain user keys. Never return them.
        return JSONResponse({'detail': 'Invalid request', 'errors': [
            {'location': list(e['loc']), 'type': e['type']} for e in exc.errors()]}, status_code=422)

    @app.middleware('http')
    async def context(request, call_next):
        owner = request.cookies.get('jev_session', '')
        fresh = not re.fullmatch(r'[a-f0-9]{64}', owner)
        if fresh: owner = secrets.token_hex(32)
        ot = owner_context.set(owner)
        mt = model_context.set(request.headers.get('X-Demo-Model', ''))
        try:
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                # Same-site browser writes only. Explicit non-browser clients use cookies.
                origin = request.headers.get('origin')
                if origin is not None:
                    browser_origin = _http_origin(origin)
                    if browser_origin is None or browser_origin not in (
                            _http_origin(str(request.base_url)), public_origin):
                        return JSONResponse({'detail': 'Cross-origin writes are disabled'}, status_code=403)
                length = request.headers.get('content-length', '0')
                if not length.isdecimal() or int(length) > 4*1024*1024:
                    return JSONResponse({'detail': 'Request too large'}, status_code=413)
                raw = await request.body()
                if len(raw) > 4*1024*1024: return JSONResponse({'detail': 'Request too large'}, status_code=413)
                if request.url.path.startswith((prefix+'/api/showcases/',prefix+'/api/engines/')) and raw:
                    try: body = json.loads(raw)
                    except ValueError: body = {}
                    ident = body.get('session_id') if isinstance(body, dict) else None
                    if ident and legacy_owners.get(ident) != owner:
                        return JSONResponse({'detail': 'Session not found'}, status_code=404)
            response = await call_next(request)
            if request.url.path == prefix+'/api/showcases/new' and response.status_code == 200:
                raw = b''.join([chunk async for chunk in response.body_iterator])
                result = json.loads(gzip.decompress(raw) if response.headers.get('content-encoding')=='gzip' else raw)
                legacy_owners[result['session_id']] = owner
                response = Response(raw, status_code=response.status_code, headers=dict(response.headers), media_type='application/json')
            if fresh:
                response.set_cookie('jev_session', owner, httponly=True, samesite='strict',
                                    secure=request.url.scheme=='https', path=prefix or '/')
            if '/api/' in request.url.path: response.headers['Cache-Control'] = 'no-store'
            else: response.headers['Cache-Control'] = 'no-cache'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response
        finally:
            owner_context.reset(ot); model_context.reset(mt)

    def check_admin(request):
        expected = os.environ.get('JEV_ADMIN_TOKEN')
        if not expected: raise HTTPException(403, 'Set JEV_ADMIN_TOKEN to enable leaderboard writes')
        token = request.headers.get('x-jev-admin-token')
        authorization = request.headers.get('authorization','')
        presented = token if token is not None else authorization[7:] if authorization.startswith('Bearer ') else ''
        if not hmac.compare_digest(presented.encode('utf-8'), expected.encode('utf-8')):
            raise HTTPException(403, 'Administrator token required')

    def checked_id(ident):
        if not SAFE_ID.fullmatch(ident) or '..' in ident: raise HTTPException(404, 'Not found')
        return ident

    def own_runner(ident):
        runner = evaluations.load(checked_id(ident))
        for model in runner.registered: connections.require(model, owner_context.get())
        return runner

    def public_evaluation(value):
        # Exact serving identities remain in private resumable receipts. Public
        # standings need participant IDs/display names, not service paths.
        private = {'served_model','model_path','tokenizer_path','endpoint','url','api_key','credential',
                   'runner_pid','run_root','frontend','weight_receipt'}
        if isinstance(value,dict):return {k:public_evaluation(v) for k,v in value.items() if k not in private}
        if isinstance(value,list):return [public_evaluation(v) for v in value]
        return value

    @app.get(prefix+'/api/v1/models')
    @app.get(prefix+'/api/v1/connections')
    async def models(): return {'models': connections.visible(owner_context.get())}

    @app.post(prefix+'/api/v1/connections', status_code=201)
    async def connect(body: ConnectionCreate): return connections.add(body, owner_context.get())

    @app.delete(prefix+'/api/v1/connections/{ident}')
    async def disconnect(ident: str):
        if any(r.active() and ident in r.registered for r in evaluations.runners.values()):
            raise HTTPException(409, 'Pause the active evaluation before disconnecting')
        connections.remove(ident, owner_context.get())
        return {'disconnected': True}

    @app.get(prefix+'/api/v1/connections/{ident}/requests')
    async def relay_requests(ident: str): return await connections.poll(ident, owner_context.get())

    @app.post(prefix+'/api/v1/connections/{ident}/results')
    async def relay_results(ident: str, body: RelayResult): return connections.complete(ident, owner_context.get(), body)

    @app.post(prefix+'/api/v1/decisions')
    async def decide(body: DecisionCall):
        connections.require(body.model_id, owner_context.get())
        return await providers.decide(body.model_id, body.input)

    @app.get(prefix+'/api/v1/games')
    async def games():
        return {'schema_version': 'jev.engine-registry.v1',
                'games': [e.descriptor() for e in list_engines(include_internal=False) if active_games([e.kind])]}

    @app.post(prefix+'/api/v1/sessions', status_code=201)
    async def create_session(body: SessionCreate): return await sessions.create(body.game, body.seed, owner_context.get())

    @app.get(prefix+'/api/v1/sessions/{ident}')
    async def get_session(ident: str): return await sessions.view(ident, owner_context.get())

    @app.post(prefix+'/api/v1/sessions/{ident}/steps')
    async def step_session(ident: str, body: SessionStep):
        if body.model_id: connections.require(body.model_id, owner_context.get())
        return await sessions.step(ident, owner_context.get(), body)

    @app.get(prefix+'/api/v1/sessions/{ident}/replay')
    async def session_replay(ident: str):
        return sessions.replay(ident, owner_context.get())

    @app.delete(prefix+'/api/v1/sessions/{ident}')
    async def delete_session(ident: str):
        await sessions.remove(ident, owner_context.get()); return {'deleted': True}

    @app.get(prefix+'/api/v1/evaluations')
    async def evaluation_list():
        return {'evaluations': [public_evaluation(evaluations.load(p.parent.name).status()) for p in sorted(evaluations.root.glob('*/request.json'))]}

    @app.post(prefix+'/api/v1/evaluations', status_code=201)
    async def create_evaluation(body: EvaluationCreate):
        for ident in body.model_ids: connections.require(ident, owner_context.get())
        return public_evaluation(await evaluations.create(body))

    @app.get(prefix+'/api/v1/evaluations/{ident}')
    async def evaluation_status(ident: str): return public_evaluation(evaluations.load(checked_id(ident)).status())

    @app.post(prefix+'/api/v1/evaluations/{ident}/pause')
    async def pause_evaluation(ident: str): return public_evaluation(await own_runner(ident).pause())

    @app.post(prefix+'/api/v1/evaluations/{ident}/resume')
    async def resume_evaluation(ident: str): return public_evaluation(await own_runner(ident).resume())

    @app.post(prefix+'/api/v1/evaluations/{ident}/models/{model}')
    async def join_evaluation(ident: str, model: str):
        connections.require(model, owner_context.get())
        runner = own_runner(ident)
        return public_evaluation(await evaluations.join(runner, model))

    @app.get(prefix+'/api/v1/evaluations/{ident}/export')
    async def export_evaluation(ident: str):
        runner = evaluations.load(checked_id(ident))
        from jev_demo_arena_replay import Exporter
        exporter = Exporter(evaluations.root, Path(data)/'replay.js')
        archive = await asyncio.to_thread(exporter.export, run_id=ident, data_only=True)
        return {'schema_version': 'jev.evaluation-export.v1', 'evaluation': public_evaluation(runner.status()), 'replays': archive}

    @app.get(prefix+'/api/v1/leaderboards/{ident}')
    async def get_leaderboard(ident: str):
        if ident not in ('jevbench','decisionindex','harnessjevbench','datajevbench','arena'): raise HTTPException(404, 'Unknown benchmark')
        doc = leaderboards.get(ident)
        if not doc: raise HTTPException(404, 'No imported results')
        return doc

    @app.put(prefix+'/api/v1/leaderboards/{ident}')
    async def put_leaderboard(ident: str, body: LeaderboardDocument, request: Request):
        check_admin(request)
        if body.benchmark_id != ident: raise HTTPException(422, 'Benchmark ID differs from URL')
        leaderboards.put(body)
        return {'imported': len(body.rows), 'benchmark_id': ident}

    @app.get(prefix+'/api/health')
    async def health():
        rows = connections.visible(owner_context.get())
        model = next((m for m in rows if m['id']==selected_model()), {})
        return {'status': 'ok', 'schema_version':'jev.health.v1', 'ready': bool(model.get('ready')),
                'models': rows, 'model': model.get('id',''), 'provider': model.get('provider',''),
                'endpoint': model.get('served_model',''), 'default_model': rows[0]['id'] if rows else ''}

    @app.get(prefix+'/api/catalog')
    async def catalog():
        return {'categories': [], 'games':[{'id':k,'name':v[0]} for k,v in board.GAMES.items() if active_games([k])], 'total':0}

    @app.get(prefix+'/api/evaluations')
    async def legacy_evaluations(): return []

    @app.get(prefix+'/api/leaderboard')
    async def leaderboard(): return leaderboards.projection(prefix)

    @app.get(prefix+'/api/leaderboard/source/{ident}')
    async def leaderboard_source(ident: str):
        for benchmark in ('jevbench','decisionindex','harnessjevbench','datajevbench'):
            if ident.startswith(benchmark+'-'):
                doc = leaderboards.get(benchmark)
                if doc:
                    for row in doc.rows:
                        if row.model_id == ident[len(benchmark)+1:]: return {'benchmark':benchmark,'version':doc.version,'result':row}
        raise HTTPException(404, 'Result not found')

    @app.get(prefix+'/api/elo')
    async def elo(): return public_evaluation(evaluations.status())

    @app.post(prefix+'/api/elo/join')
    async def elo_join():
        ident = selected_model()
        connections.require(ident, owner_context.get())
        runner = evaluations.latest()
        if runner:
            own_runner(runner.folder.name)
            return public_evaluation(await evaluations.join(runner, ident))
        ids = [m['id'] for m in connections.visible(owner_context.get()) if m['ready']]
        if len(ids)<2: raise HTTPException(409, 'Connect at least two models before starting Arena')
        return public_evaluation(await evaluations.create(EvaluationCreate(model_ids=ids, concurrency=config.concurrency)))

    @app.post(prefix+'/api/elo/pause')
    async def elo_pause():
        runner = evaluations.latest()
        if not runner: raise HTTPException(409, 'No active evaluation')
        return public_evaluation(await own_runner(runner.folder.name).pause())

    @app.post(prefix+'/api/elo/resume')
    async def elo_resume():
        runner = evaluations.latest()
        if not runner: raise HTTPException(409, 'No resumable evaluation')
        return public_evaluation(await own_runner(runner.folder.name).resume())

    @app.get(prefix+'/playground/visible-control.js')
    async def replay_archive():
        from jev_demo_arena_replay import Exporter
        archive = None
        if (evaluations.root/'latest.json').is_file():
            archive = await asyncio.to_thread(Exporter(evaluations.root, Path(data)/'replay.js').export, data_only=True)
        if not archive and (evaluations.leaderboard_dir/'arena-replays.json').exists(): archive = json.loads((evaluations.leaderboard_dir/'arena-replays.json').read_text())
        return Response('window.JevArenaReplayArchive='+json.dumps(archive or {},ensure_ascii=False)+';', media_type='application/javascript')

    def board_payload(ident):
        item = board_sessions.get(ident)
        if not item or item['owner'] != owner_context.get(): raise HTTPException(404, 'Session not found')
        state = item['world']; engine=get_engine(state['game'],state)
        record = engine.model_input(state) if not engine.outcome(state) and len(engine.legal_actions(state))>=2 else None
        return {'session_id':ident,'revision':item['revision'],'game':engine.public(state),'environment':item['environment'],
                'input':None if record is None else {'state':record['state'],'prompt':record['questions']['decision']['instructions'], 'option':record['questions']['decision']['criteria']}}

    @app.post(prefix+'/api/game/new')
    async def board_new(body: showcases.New):
        if body.kind not in board.GAMES or not active_games([body.kind]): raise HTTPException(422,'Unknown board game')
        if body.seq is not None: raise HTTPException(422,'Training examples are not included')
        if len(board_sessions)>=1000: raise HTTPException(429,'Session limit reached')
        # Omitted seed means a standard opening. Seeded curriculum positions
        # remain opt-in; substituting a random seed silently preplays moves.
        seed_value = body.seed
        ident = secrets.token_hex(16)
        board_sessions[ident] = {'world':get_engine(body.kind).reset(seed_value),'revision':0,'owner':owner_context.get(),
                                'busy':False,'environment':condition_info(body.kind,seed_value)}
        return board_payload(ident)

    @app.post(prefix+'/api/game/move')
    async def board_move(body: showcases.Move):
        if body.reference and body.model: raise HTTPException(422,'Choose rule engine or model')
        board_payload(body.session_id)
        item = board_sessions[body.session_id]
        if body.revision != item['revision'] or item['busy']: raise HTTPException(409,'Game changed or action in progress')
        item['busy'] = True
        try:
            engine=get_engine(item['world']['game'],item['world'])
            legal = engine.legal_actions(item['world']); forced = len(legal)==1
            result = None; action = body.action; previous_input = None
            if body.reference:
                from jev_board_algorithm_opponent import choose
                if not legal: raise HTTPException(422,'Game is over')
                action = await asyncio.to_thread(choose,item['world'],legal,item['environment'].get('seed'),item['revision'])
            elif body.model:
                if forced: action=next(iter(legal))
                elif legal:
                    record = engine.model_input(item['world'])
                    question = record['questions']['decision']
                    previous_input = {'state':record['state'], 'prompt':question['instructions'], 'option':question['criteria']}
                    result = await predict(record,'decision'); action=result['value']
            if action not in legal: raise HTTPException(422,'Illegal game action')
            item['world'] = engine.step(item['world'],action); item['revision'] += 1
            return {**board_payload(body.session_id),'action':action,'result':result,'forced':forced,'previous_input':previous_input,
                    'controller':'rule_engine' if body.reference else 'model' if body.model else 'human'}
        finally: item['busy'] = False

    def no_case(seq): raise HTTPException(404,'Training examples are not included')
    @contextmanager
    def no_db(): yield None
    showcases.install(app,prefix,no_case,predict,no_db)
    mbti.install(app,prefix,predict,lambda *a,**k: [])
    if prefix:
        @app.get('/')
        async def root_redirect(): return RedirectResponse(prefix+'/')
    app.mount(prefix or '/', StaticFiles(directory=web, html=True), name='frontend')
    return app
