"""Durable native game evaluations with exact protocol and model bindings."""
import asyncio
import json
import time
import uuid
from pathlib import Path
from fastapi import HTTPException
from .schemas import EvaluationCreate
from jev_demo_arena import GameArena, ARENA_REVISION, DIRECT_KINDS, DECISION_POLICY
from jev_demo_elo import make_plan, _read, _write, game_options
from jev_demo_game_evaluation import GameEvaluator, KINDS, EVALUATION_REVISION, GAME_ENGINE_REVISIONS
from jev_demo_arena_episodes import REVISION as EPISODE_REVISION
from jev_demo_arena_direct import REVISION as DIRECT_REVISION
from jev_demo_decision_stability import REALTIME_GAME_KINDS, decision_policy

def identity(spec):
    return {'id': spec.id, 'name': spec.name, 'provider': spec.adapter,
            'served_model': spec.served_model, 'policy': DECISION_POLICY}

class PortableArena(GameArena):
    def __init__(self, *, folder, request, providers, predict, frontend, selected_model, participants=None):
        self.folder = Path(folder)
        self.request = request
        self.providers = providers
        self.registered = {p['id']: p for p in (participants or [identity(providers.models[i]) for i in request.model_ids])}
        specs = {i: {**p, 'provider': p['provider']} for i, p in self.registered.items()}
        evaluator = GameEvaluator(predict, selected_model, lambda i: (i, specs[i]), frontend)
        super().__init__(evaluator, models=specs, selected_model=selected_model, root=self.folder.parent,
                         predict=predict, baseline_ids=list(self.registered), include_rule_engine=False,
                         concurrency=request.concurrency)

    def _load(self): return self.folder, _read(self.folder/'plan.json')

    def _participant(self, ident):
        if ident in self.registered: return dict(self.registered[ident])
        if ident in self.providers.models: return identity(self.providers.models[ident])
        raise HTTPException(422, 'Connect the model first')

    def _plan(self, roster):
        available = {p['id']: p for p in roster}
        plan = make_plan({'participants': list(available), 'kinds': self.request.games or list(KINDS),
                          'seeds': self.request.seeds, 'seed_base': self.request.seed_base},
                         available=available, direct_kinds=DIRECT_KINDS)
        plan.update(arena_revision=ARENA_REVISION, decision_policy=DECISION_POLICY,
                    game_engine_revisions=dict(GAME_ENGINE_REVISIONS), episode_revision=EPISODE_REVISION,
                    direct_revision=DIRECT_REVISION, baseline_ids=list(available),
                    portable_revision='jev.evaluation.v1', registrations=[])
        return plan

    def _validate_plan(self, plan):
        expected = self._plan(self._baseline())
        # Incremental enrollment appends fixtures; old ordinals stay immutable.
        if not plan or any(plan.get(k) != expected[k] for k in expected if k not in ('schedule','registrations')):
            raise HTTPException(409, 'Saved evaluation protocol differs; start a new evaluation')
        normalized = lambda rows: sorted(json.dumps({k:v for k,v in row.items() if k!='ordinal'},sort_keys=True) for row in rows)
        if (normalized(plan['schedule']) != normalized(expected['schedule']) or
                [r['ordinal'] for r in plan['schedule']] != list(range(len(plan['schedule'])))):
            raise HTTPException(409, 'Saved fixture schedule differs')

    async def _preflight(self, player):
        spec = self.providers.models.get(player['id'])
        if not spec or not self.providers.configured(spec.id): raise HTTPException(503, 'Reconnect the evaluation models first')
        if identity(spec) != player: raise HTTPException(409, 'Connected model identity differs from the saved evaluation')

    async def _checked_predict(self, record, qid, model=None):
        expected = self._participant(model)
        await self._preflight(expected)
        result = await self._original_predict(record, qid, model=model)
        if result.get('model') != model or result.get('served_model') != expected['served_model']:
            raise ValueError('model_identity_mismatch')
        kind = record.get('metadata', {}).get('sub_domain') or record.get('state', {}).get('kind')
        kind = {'terramai_directional': 'terraria_survival'}.get(kind, kind)
        if kind in REALTIME_GAME_KINDS:
            if result.get('decision_policy') != decision_policy(kind) or result.get('decision_stability') is not None:
                raise ValueError('single_realtime_decision_required')
        elif (result.get('decision_stability') or {}).get('repeat_count') != 3:
            raise ValueError('three_decision_samples_required')
        return result

    def status(self):
        data = super().status()
        data['schema_version'] = 'jev.evaluation.v1'
        data['fixed_config'].update(seeds=self.request.seeds, seed_base=self.request.seed_base,
                                   games=[g for g in data['fixed_config']['games'] if not self.request.games or g['id'] in self.request.games])
        return data

class Evaluations:
    def __init__(self, data, seed, providers, predict, frontend, selected_model, *, leaderboard_dir=None):
        self.root = Path(data)/'evaluations'
        self.seed = Path(seed)
        from .paths import leaderboard_directory
        self.leaderboard_dir = leaderboard_directory(leaderboard_dir)
        self.providers, self.predict = providers, predict
        self.frontend, self.selected_model = frontend, selected_model
        self.runners = {}

    def load(self, ident):
        if ident in self.runners: return self.runners[ident]
        folder = self.root/ident
        saved = _read(folder/'request.json')
        plan = _read(folder/'plan.json')
        if not saved or not plan: raise HTTPException(404, 'Evaluation not found')
        runner = PortableArena(folder=folder, request=EvaluationCreate.model_validate(saved), providers=self.providers,
                               predict=self.predict, frontend=self.frontend, selected_model=self.selected_model,
                               participants=plan['participants'])
        self.runners[ident] = runner
        return runner

    async def create(self, body):
        if self.active(): raise HTTPException(409, 'An evaluation is already running; pause it first')
        if any(g not in KINDS for g in (body.games or [])): raise HTTPException(422, 'Unknown game')
        if any(i not in self.providers.models for i in body.model_ids): raise HTTPException(422, 'Connect every selected model first')
        ident = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())+'-'+uuid.uuid4().hex[:8]
        runner = PortableArena(folder=self.root/ident, request=body, providers=self.providers, predict=self.predict,
                               frontend=self.frontend, selected_model=self.selected_model)
        for player in runner._baseline(): await runner._preflight(player)
        plan = runner._plan(runner._baseline())
        _write(runner.folder/'request.json', body.model_dump(mode='json'))
        _write(runner.folder/'plan.json', plan)
        _write(self.root/'latest.json', {'run_id': ident})
        self.runners[ident] = runner
        runner._launch(runner.folder, plan)
        return runner.status()

    async def join(self, runner, ident):
        async with runner.registration_lock:
            old = _read(runner.folder/'plan.json')
            runner._validate_plan(old)
            if ident in runner.registered: return {**runner.status(), 'already_enrolled': True}
            if self.active(): raise HTTPException(409, 'Wait for the active evaluation before adding a model')
            player = runner._participant(ident)
            for entrant in list(runner.registered.values())+[player]: await runner._preflight(entrant)
            runner.registered[ident] = player
            runner.models[ident] = player
            runner.baseline_ids = tuple(runner.registered)
            runner.request = runner.request.model_copy(update={'model_ids':list(runner.registered)})
            plan = runner._plan(runner._baseline())
            added = [row for row in plan['schedule'] if ident in (row['a'],row['b'])]
            for ordinal,row in enumerate(added,start=len(old['schedule'])): row['ordinal']=ordinal
            plan['schedule'] = old['schedule']+added
            plan['registrations'] = old.get('registrations',[])+[{'model':ident,'registered_at':time.time()}]
            _write(runner.folder/'registrations'/f'{len(plan["registrations"]):05d}.json',old)
            _write(runner.folder/'request.json',runner.request.model_dump(mode='json'))
            _write(runner.folder/'plan.json',plan)
            runner._launch(runner.folder,plan)
            return {**runner.status(),'already_enrolled':False}

    def active(self): return any(r.active() for r in self.runners.values())

    def latest(self):
        row = _read(self.root/'latest.json')
        return self.load(row['run_id']) if row else None

    def status(self):
        from .game_scope import project_arena
        return project_arena(self._status())

    def _status(self):
        runner = self.latest()
        if runner: return runner.status()
        from .leaderboards import Leaderboards
        imported = Leaderboards(directory=self.leaderboard_dir).get('arena')
        if imported:
            def row(item, value):
                return {'id':item.model_id,'name':item.model_name,'rating':value,'rank':None,
                        **({'logo':item.logo} if item.logo else {}),
                        'coverage':sum(axis.score is not None for axis in item.axes),'required_games':len(imported_games),
                        'provisional':True,'errors':item.errors,'played':item.samples,
                        'wins':item.metrics.get('wins',0),'draws':item.metrics.get('draws',0),'losses':item.metrics.get('losses',0)}
            imported_games = list(dict.fromkeys(a.id for item in imported.rows for a in item.axes))
            from jev_demo_elo import _rank
            overall = _rank([row(item,item.score) for item in imported.rows])
            by_game = {kind:_rank([row(item,next((a.score for a in item.axes if a.id==kind),None))
                                  for item in imported.rows]) for kind in imported_games}
            ident=self.selected_model();spec=self.providers.models.get(ident)
            return {'schema_version':'jev.evaluation.v1','state':'archived','run_id':None,
                    'source':'imported_ratings','overall':overall,'by_game':by_game,'matches':[],
                    'completed':0,'planned':0,'scored':0,'archived_protocol':True,'controls_available':False,
                    'current_model':{'id':ident,'name':spec.name if spec else ident,'supported':bool(spec),
                                     'enrolled':False,'can_join':len(self.providers.models)>=2},
                    'fixed_config':{'games':[g for g in game_options() if g['id'] in imported_games],
                                    'baseline':[],'seed_base':42,'seeds':1}}
        saved = _read(self.leaderboard_dir/'arena.json')
        if saved:
            ident = self.selected_model()
            spec = self.providers.models.get(ident)
            return {**saved, 'state': 'archived', 'managed_externally': True, 'controls_available': False,
                    'archived_protocol': True, 'current_model': {'id': ident, 'name': spec.name if spec else ident,
                        'supported': bool(spec), 'enrolled': False, 'can_join': len(self.providers.models)>=2,
                        'reason': 'Connect at least two models to start a new evaluation.'}}
        return {'state': 'idle', 'overall': [], 'by_game': {}, 'matches': [], 'planned': 0, 'completed': 0,
                'current_model': {'id': self.selected_model(), 'supported': True, 'can_join': len(self.providers.models)>=2},
                'fixed_config': {'games': game_options(), 'baseline': [], 'seed_base': 42, 'seeds': 1}}

    async def close(self):
        await asyncio.gather(*(r.shutdown() for r in self.runners.values()))
