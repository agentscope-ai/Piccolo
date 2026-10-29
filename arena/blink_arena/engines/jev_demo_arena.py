"""Fixed Piccolo Arena ladder; enrollment appends matches without resetting Elo."""
import asyncio
from pathlib import Path
import time
import traceback

from fastapi import HTTPException

from jev_demo_elo import (
    EloTournament, ENGINE, REVISION, EVALUATION_REVISION, FRONT,
    participants, game_options, make_plan, _read, _write,
)
from jev_demo_game_evaluation import KINDS, board, GAME_ENGINE_REVISIONS
from jev_demo_arena_episodes import REVISION as EPISODE_REVISION
from jev_demo_arena_direct import DIRECT_KINDS as NATIVE_DIRECT_KINDS, REVISION as DIRECT_REVISION
from jev_demo_decision_stability import POLICY_REVISION, REALTIME_GAME_KINDS, decision_policy

ARENA_REVISION = 'gamejevarena-v3-realtime-single-time'
ARENA_KINDS = tuple(KINDS)
DIRECT_KINDS = frozenset(board.GAMES) | NATIVE_DIRECT_KINDS
ARENA_SEED = 42
DECISION_POLICY = POLICY_REVISION


def _error_fields(error):
    """Keep diagnostics without provider messages, request data or credentials."""
    fields = {'error_type': type(error).__name__}
    frames = traceback.extract_tb(error.__traceback__)
    if frames:
        frame = frames[-1]
        fields['error_location'] = {'module': Path(frame.filename).name,
                                    'function': frame.name, 'line': frame.lineno}
    if isinstance(error, HTTPException):
        fields['http_status'] = error.status_code
        detail = error.detail
        if isinstance(detail, dict) and detail.get('code') == 'decision_repeat_failed':
            fields['error_code'] = detail['code']
            if type(detail.get('sample_index')) is int:
                fields['failed_sample_index'] = detail['sample_index']
    elif isinstance(error, ValueError) and error.args and error.args[0] in (
            'native_direct_nonterminal_budget_exhausted', 'paired_episode_failed',
            'nonterminal_board', 'native_episode_inference_failed'):
        # Safe internal codes distinguish exhausted game budgets from transport
        # errors without ever exporting arbitrary exception/provider text.
        fields['error_code'] = error.args[0]
    return fields


def _stability_summary(items):
    """Equal decision weight inside a game; missing probability data stays missing."""
    complete = [item for item in items if item.get('probability_complete')]
    def mean(rows, key):
        return sum(float(row[key]) for row in rows)/len(rows) if rows else None
    return {'decisions': len(items), 'probability_decisions': len(complete),
            'agreement_rate': mean(items, 'agreement_rate'),
            'unanimous_rate': mean(items, 'unanimous'),
            'mean_probability_variance': mean(complete, 'mean_probability_variance'),
            'mean_js_distance': mean(complete, 'mean_js_distance'),
            'probability_stability': mean(complete, 'probability_stability'),
            'probability_coverage': len(complete)/len(items) if items else None}


class GameArena(EloTournament):
    def __init__(self, evaluator, *, models, selected_model, root=None, ready=None, busy=None, predict=None, concurrency=12,
                 baseline_ids=None, managed_externally=False, external_manager=None, include_rule_engine=True):
        super().__init__(evaluator, root=root if root is not None else FRONT/'game_arena', ready=ready, busy=busy)
        self.models = models
        self.selected_model = selected_model
        self.registration_lock = asyncio.Lock()
        self.episode_locks = {}
        self.concurrency = concurrency
        # Explicit cohorts can bind local checkpoints and registered API models.
        # Preserve the engine entrant by default for existing archived cohorts.
        self.baseline_ids = tuple(baseline_ids) if baseline_ids is not None else None
        self.include_rule_engine = include_rule_engine
        self.managed_externally = bool(managed_externally)
        self.external_manager = external_manager
        if self.baseline_ids is not None:
            if (len(self.baseline_ids) < 2 or len(set(self.baseline_ids)) != len(self.baseline_ids)
                    or any(not isinstance(ident, str) or ident == ENGINE for ident in self.baseline_ids)):
                raise ValueError('local_arena_requires_at_least_two_distinct_models')
            for ident in self.baseline_ids:
                self._participant(ident)
        if predict is not None:
            self._original_predict = predict

    def _baseline(self):
        ids = (list(self.baseline_ids) + ([ENGINE] if self.include_rule_engine else []) if self.baseline_ids is not None
               else [p['id'] for p in participants()])
        return [self._participant(ident) for ident in ids]

    def _plan(self, roster):
        available = {p['id']: p for p in roster}
        plan = make_plan({'participants': list(available), 'kinds': list(ARENA_KINDS),
                         'seeds': 1, 'seed_base': ARENA_SEED}, available=available, direct_kinds=DIRECT_KINDS)
        plan.update(arena_revision=ARENA_REVISION, decision_policy=DECISION_POLICY,
                    game_engine_revisions=dict(GAME_ENGINE_REVISIONS),
                    episode_revision=EPISODE_REVISION, direct_revision=DIRECT_REVISION,
                    paired_rule='same game, seed, seat and fixed budget; compare native final score; cached episodes reused',
                    direct_rule='native model-versus-model games; two legs exchange sides/roles',
                    baseline_ids=[p['id'] for p in self._baseline()])
        return plan

    def ensure_baseline(self):
        """Register the fixed roster independently of adding a user's model."""
        folder, plan = self._load()
        if plan:
            # Startup is read-only for an existing cohort, including archived
            # engine versions. Never switch latest or schedule a replacement.
            return folder, plan
        plan = self._plan(self._baseline())
        plan['registrations'] = []
        plan['baseline_registered_at'] = time.time()
        folder = self.root/ARENA_REVISION
        _write(folder/'plan.json', plan)
        _write(self.root/'latest.json', {'run_id': folder.name})
        self._state(folder, 'pending')
        return folder, plan

    async def bootstrap(self):
        """Run the baseline once; resume interrupted work without replaying receipts."""
        if self.managed_externally:
            return
        async with self.registration_lock:
            folder, plan = self.ensure_baseline()
            try:
                self._validate_plan(plan)
            except HTTPException:
                return
            state = _read(folder/'status.json') or {}
            if self.active() or state.get('state') in ('paused', 'pausing', 'complete'):
                return
            if self.busy():
                return
            try:
                for player in plan['participants']:
                    await self._preflight(player)
                self._launch(folder, plan)
            except HTTPException as exc:
                self._state(folder, 'error', error_type='ParticipantNotReady', detail=exc.detail)

    async def shutdown(self):
        if self.active():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def _participant(self, ident):
        baseline = {p['id']: p for p in participants()}
        if self.baseline_ids is not None:
            if ident == ENGINE:
                return baseline[ENGINE]
            spec = self.models.get(ident, {})
            if ident not in self.baseline_ids and not (self.external_manager and self.external_manager.supports(ident)):
                raise HTTPException(422, '本轮天梯仅允许固定阵容中已登记的模型参赛')
            if spec.get('provider') == 'dashscope':
                registered = baseline.get(ident)
                if not registered or registered.get('served_model') != spec.get('served_model'):
                    raise HTTPException(422, 'DashScope 模型身份与登记不一致')
                return {**registered, 'name': spec['name'], 'policy': DECISION_POLICY}
            if spec.get('provider', 'local') != 'local' or not spec.get('path'):
                raise HTTPException(422, '本轮天梯仅支持已登记的本地或 DashScope 模型')
            return {'id': ident, 'name': spec['name'], 'provider': 'local',
                    'model_path': str(Path(spec['path']).resolve()), 'policy': DECISION_POLICY}
        if ident in baseline:
            player = baseline[ident]
            if ident != ENGINE:
                player['policy'] = DECISION_POLICY
            return player
        spec = self.models.get(ident, {})
        if spec.get('path') and spec.get('provider', 'local') == 'local':
            return {'id': ident, 'name': spec['name'], 'provider': 'local',
                    'model_path': str(Path(spec['path']).resolve()),
                    'policy': DECISION_POLICY}
        raise HTTPException(422, '天梯支持已配置的本地模型与 DashScope 模型，请在上方切换模型')

    def _validate_plan(self, plan):
        if self.external_manager:
            self.external_manager.validate(plan)
            return
        if plan.get('game_engine_revisions') != GAME_ENGINE_REVISIONS:
            raise HTTPException(409, '俄罗斯方块已升级为实时规则；当前天梯保留原规则历史成绩，不能混入新版对局，请使用单独的新协议评测')
        if (plan.get('arena_revision') != ARENA_REVISION or plan.get('revision') != REVISION
                or plan.get('engine_revision') != EVALUATION_REVISION
                or plan.get('decision_policy') != DECISION_POLICY
                or plan.get('episode_revision') != EPISODE_REVISION
                or plan.get('direct_revision') != DIRECT_REVISION
                or tuple(plan.get('kinds', [])) != ARENA_KINDS
                or plan.get('seeds') != 1 or plan.get('seed_base') != ARENA_SEED):
            raise HTTPException(409, '天梯配置版本不一致，请核对已有记录')
        for player in plan['participants']:
            if self._participant(player['id']) != player:
                raise HTTPException(409, '已登记的模型身份发生变化，请恢复原模型登记')

    async def _preflight(self, player):
        # Portable deployments never contact a model service from the engine.
        # The HTTP boundary supplies a browser registration readiness callback.
        if player['id'] != ENGINE and not self.ready(player['id']):
            raise HTTPException(503, 'Reconnect the model in the browser')

    async def _checked_predict(self, record, qid, model=None):
        _, plan = self._load()
        expected = next((p for p in (plan or {}).get('participants', []) if p['id'] == model), None)
        if expected is None or self._participant(model) != expected:
            raise ValueError('model_registration_changed')
        result = await self._original_predict(record, qid, model=model)
        if result.get('model') != model:
            raise ValueError('model_identity_mismatch')
        stability = result.get('decision_stability') or {}
        kind = (record.get('metadata') or {}).get('sub_domain') or (record.get('state') or {}).get('kind')
        kind = {'terramai_directional': 'terraria_survival'}.get(kind, kind)
        if kind in REALTIME_GAME_KINDS:
            if result.get('decision_policy') != decision_policy(kind) or result.get('decision_stability') is not None:
                raise ValueError('single_realtime_decision_required')
        elif stability.get('repeat_count') != 3 or len(stability.get('samples', [])) != 3:
            raise ValueError('three_decision_samples_required')
        if expected['provider'] == 'dashscope':
            if result.get('served_model') != expected['served_model']:
                raise ValueError('model_identity_mismatch')
            return result
        if (result.get('served_model') is not None
                and str(Path(result['served_model']).resolve()) != expected['model_path']):
            raise ValueError('model_identity_mismatch')
        # The shared local predict path checks /model_info against this exact
        # registered path on every decision. Persist that identity in the trace.
        return {**result, 'served_model': expected['model_path']}

    def status(self):
        data = super().status()
        data['managed_externally'] = self.managed_externally
        data['controls_available'] = not self.managed_externally or self.external_manager is not None
        if self.managed_externally:
            current_folder, _ = self._load()
            progress = _read(current_folder/'progress.json') if current_folder else None
            if isinstance(progress, dict):
                cost = _read(current_folder/'eta-native-work.json')
                if isinstance(cost, dict) and time.time()-cost.get('updated_at', 0) < 90:
                    progress = {**progress, 'eta_seconds': cost.get('eta_seconds'),
                                'eta_method': cost.get('method'), 'eta_work_by_game': cost.get('by_game')}
                data['progress'] = progress
                if (progress.get('state') == 'running'
                        and time.time()-progress.get('updated_at', 0) < 90):
                    data['state'] = 'running'
        _, loaded_plan = self._load()
        archived = False
        if loaded_plan:
            try:
                self._validate_plan(loaded_plan)
            except HTTPException:
                archived = True
        data['archived_protocol'] = archived
        if data.get('state') == 'complete' and data.get('scored', 0) < data.get('planned', 0):
            data['state'] = 'complete_with_errors'
        ident = self.selected_model()
        roster = (data.get('protocol') or {}).get('participants', [])
        enrolled = any(p['id'] == ident for p in roster)
        try:
            player = self._participant(ident)
            supported, reason = True, ''
        except HTTPException as exc:
            player = {'id': ident, 'name': self.models.get(ident, {}).get('name', ident)}
            supported, reason = False, exc.detail
        baseline = self._baseline()
        if archived:
            baseline_ids = {p['id'] for p in baseline}
            baseline = [p for p in loaded_plan['participants'] if p['id'] in baseline_ids]
        existing = roster or baseline
        additional = 0
        if supported and not any(p['id'] == ident for p in existing):
            additional = sum(ident in (f['a'], f['b']) for f in self._plan(existing+[player])['schedule'])
        data['current_model'] = {**player, 'enrolled': enrolled, 'supported': supported,
                                 'can_join': supported and not enrolled and not self.busy() and not archived
                                             and (not self.managed_externally or self.external_manager is not None),
                                 'reason': ('当前展示历史协议成绩；新版评测单独建档' if archived else reason
                                            or ('本轮由独立评测进程管理，尚未配置增量入口'
                                                if self.managed_externally and not self.external_manager and not enrolled else '')),
                                 'additional_matches': 0 if enrolled else additional}
        from jev_demo_arena_episodes import comparison_spec
        archived_comparisons = {}
        saved_protocol = archived or bool(self.external_manager)
        if saved_protocol:
            loaded_folder, _ = self._load()
            archived_comparisons = {row['kind']: row['comparison']
                for row in self._receipts(loaded_folder, loaded_plan) if row.get('comparison')}
        games = [{**g, 'mode': 'direct' if g['id'] in DIRECT_KINDS else 'paired',
                  'comparison': None if g['id'] in DIRECT_KINDS else
                      archived_comparisons.get(g['id']) if saved_protocol else comparison_spec(g['id'])}
                 for g in game_options() if g['id'] in ARENA_KINDS]
        data['fixed_config'] = {'revision': loaded_plan['arena_revision'] if archived else ARENA_REVISION, 'games': games,
                                'baseline': baseline, 'seed_base': ARENA_SEED,
                                'seeds': 1, 'legs': 2, 'single_player_episodes_reused': True,
                                'engine_revision': (loaded_plan or {}).get('engine_revision'),
                                'concurrency': self.external_manager.config['concurrency'] if self.external_manager else self.concurrency}
        # Only read-only fixed settings are published; enrollment takes no choices.
        data['options'] = {'participants': roster, 'games': games}
        self._add_stability(data)
        self._add_baseline_progress(data)
        folder, _ = self._load()
        repair = _read(folder/'repair_status.json') if folder else None
        if isinstance(repair, dict):
            data['repair'] = {key: repair[key] for key in (
                'state', 'source_run_id', 'target_run_id', 'total', 'completed',
                'remaining', 'attempts', 'updated_at', 'runner_pid', 'eta_seconds',
                'historical_errors_retained') if key in repair}
        for kind, rows in data['by_game'].items():
            if kind not in board.GAMES:
                data['by_game'][kind] = [r for r in rows if r['id'] != ENGINE]
        return data

    def _add_baseline_progress(self, data):
        folder, plan = self._load()
        baseline = {p['id'] for p in self._baseline()}
        fixtures = [f for f in (plan or {}).get('schedule', []) if f['a'] in baseline and f['b'] in baseline]
        expected = {f['ordinal']: f for f in fixtures}
        receipts = self._receipts(folder, plan) if plan else []
        exact = {row['ordinal']: row for row in receipts
                 if row.get('ordinal') in expected
                 and all(row.get(k) == v for k, v in expected[row['ordinal']].items())}
        errors = sum(row['status'] != 'complete' for row in exact.values())
        completed = len(exact)
        state = ('complete_with_errors' if errors else 'complete') if fixtures and completed == len(fixtures) else data['state']
        rows = []
        for player in (plan or {}).get('participants', []):
            if player['id'] not in baseline:
                continue
            own = [f for f in fixtures if player['id'] in (f['a'], f['b'])]
            done = [exact[f['ordinal']] for f in own if f['ordinal'] in exact]
            covered = {r['kind'] for r in done if r['status'] == 'complete'}
            own_errors = sum(r['status'] != 'complete' for r in done)
            rows.append({**{k: player[k] for k in ('id', 'name')},
                         'state': ('complete_with_errors' if own_errors else 'complete')
                                  if len(done) == len(own) else 'running' if done else 'pending',
                         'completed': len(done), 'planned': len(own),
                         'coverage': len(covered), 'required_games': len({r['kind'] for r in own}),
                         'errors': own_errors})
        data['baseline_progress'] = {'state': state, 'completed': completed, 'planned': len(fixtures),
                                     'errors': errors, 'participants': rows}

    def _receipts(self, folder, plan):
        rows = []
        for fixture in plan['schedule']:
            name = f"{fixture['ordinal']:05d}.json"
            row = _read(folder/'summaries'/name)
            if row is None:
                full = _read(folder/'matches'/name)
                if full is not None:
                    row = self._summary_receipt(full)
            if row is not None:
                rows.append(row)
        return rows

    def _episode_binding(self, kind, seed, model):
        from jev_demo_arena_episodes import comparison_spec
        _, plan = self._load()
        player = next(p for p in plan['participants'] if p['id'] == model)
        return {'arena_revision': ARENA_REVISION, 'episode_revision': EPISODE_REVISION,
                'engine_revision': EVALUATION_REVISION, 'decision_policy': DECISION_POLICY,
                'participant': player, 'kind': kind, 'seed': seed,
                'comparison': comparison_spec(kind)}

    @staticmethod
    def _episode_name(kind, seed, model):
        # All IDs come from the server-owned model registry, not request paths.
        if any(part in model for part in ('/', '\\', '..')):
            raise ValueError('invalid_registered_model_id')
        return f'{kind}-{seed}-{model}.json'

    @staticmethod
    def _episode_summary(row):
        summary = {k: v for k, v in row.items() if k not in (
            'trace', 'native_trace', 'initial_state', 'final_state', 'replay_events', 'execution_receipts')}
        summary['stability'] = _stability_summary([step['decision_stability'] for step in row.get('trace', [])
                                                 if step.get('decision_stability')])
        return summary

    async def _episode(self, folder, kind, seed, model, browser):
        from jev_demo_arena_episodes import run_episode
        name = self._episode_name(kind, seed, model)
        lock = self.episode_locks.setdefault((str(folder), name), asyncio.Lock())
        async with lock:
            binding = self._episode_binding(kind, seed, model)
            path, summary_path = folder/'episodes'/name, folder/'episode_summaries'/name
            previous = _read(path)
            if previous is not None:
                identity = {key: value for key, value in binding['participant'].items()
                            if key in ('id', 'provider', 'served_model', 'model_path')}
                if (previous.get('binding') != binding
                        or (previous.get('kind'), previous.get('seed'), previous.get('model')) != (kind, seed, model)
                        or previous.get('status') == 'complete' and (
                            previous.get('model_identity') != identity
                            or previous.get('episode_revision') != EPISODE_REVISION
                            or previous.get('comparison_spec') != binding['comparison'])):
                    raise ValueError('cached_episode_identity_or_protocol_changed')
                if not summary_path.exists():
                    _write(summary_path, self._episode_summary(previous))
                return {**previous, 'reused': True}
            try:
                row = await run_episode(self.evaluator, kind, seed, model, browser)
            except asyncio.CancelledError as exc:
                _write(folder/'episode_attempts'/f'{name[:-5]}-{time.time_ns()}.json',
                       {'binding': binding, 'status': 'interrupted', 'trace': getattr(exc, 'episode_trace', [])})
                raise
            except Exception as exc:
                row = {'status': 'error', 'kind': kind, 'seed': seed, 'model': model,
                       **_error_fields(exc), 'trace': getattr(exc, 'episode_trace', [])}
            row.update(binding=binding, episode_id=name[:-5], finished_at=time.time())
            _write(path, row)
            summary = self._episode_summary(row)
            _write(summary_path, summary)
            return {**row, 'reused': False}

    async def _execute(self, folder, fixture, browser):
        from jev_demo_arena_episodes import compare_results, comparison_spec
        started = time.monotonic()
        try:
            if fixture['mode'] == 'direct':
                if fixture['kind'] in board.GAMES:
                    result = await self._direct(folder, fixture)
                else:
                    from jev_demo_arena_direct import play_direct
                    result = await play_direct(self._checked_predict, fixture)
            else:
                a, b = await asyncio.gather(*(self._episode(folder, fixture['kind'], fixture['seed'],
                                                          model, browser) for model in (fixture['a'], fixture['b'])))
                if a['status'] != 'complete' or b['status'] != 'complete':
                    raise ValueError('paired_episode_failed')
                def display(row):
                    return {key: row.get(key) for key in ('score', 'outcome', 'score_label', 'higher_is_better',
                                                        'comparison_key', 'terminal', 'budget_exhausted',
                                                        'time_score', 'reused', 'episode_id')}
                spec = comparison_spec(fixture['kind'])
                result = {'score_a': compare_results(a, b), 'result_a': display(a), 'result_b': display(b),
                          'comparison': {**spec, 'label': spec['score_label']},
                          'episode_refs': {fixture['a']: a['episode_id'], fixture['b']: b['episode_id']}}
            return {**fixture, 'status': 'complete', **result,
                    'seconds': round(time.monotonic()-started, 3), 'finished_at': time.time()}
        except asyncio.CancelledError as exc:
            if getattr(exc, 'match_trace', None):
                _write(folder/'attempts'/f"{fixture['ordinal']:05d}-{time.time_ns()}.json",
                       {**fixture, 'status': 'interrupted', 'trace': exc.match_trace})
            raise
        except Exception as exc:
            return {**fixture, 'status': 'error', 'score_a': None,
                    **_error_fields(exc), 'trace': getattr(exc, 'match_trace', []),
                    'seconds': round(time.monotonic()-started, 3), 'finished_at': time.time()}

    @staticmethod
    def _summary_receipt(row):
        summaries = {}
        for player in (row['a'], row['b']):
            samples = [step['decision_stability'] for step in row.get('trace', [])
                       if player != ENGINE and step.get('player') == player and step.get('decision_stability')]
            summaries[player] = _stability_summary(samples)
        return {**{key: value for key, value in row.items()
                   if key not in ('trace', 'initial_state', 'final_state')},
                'stability': summaries}

    def _add_stability(self, data):
        folder, plan = self._load()
        if not plan:
            return
        fixtures = {fixture['ordinal']: fixture for fixture in plan['schedule']}
        # Stability and Elo must attribute a receipt to the same exact fixture.
        # Failed games can contribute completed decisions, but never another
        # model's, seed's, seat's or game's measurements.
        receipts = [row for row in self._receipts(folder, plan)
                    if (fixture := fixtures.get(row.get('ordinal'))) is not None
                    and all(row.get(key) == value for key, value in fixture.items())]
        metrics = ('agreement_rate', 'unanimous_rate', 'mean_probability_variance',
                   'mean_js_distance', 'probability_stability')
        for kind, rows in data['by_game'].items():
            for player in rows:
                blocks = [r.get('stability', {}).get(player['id'], {}) for r in receipts
                          if player['id'] != ENGINE and r['kind'] == kind and r.get('mode') == 'direct']
                if kind not in DIRECT_KINDS and player['id'] != ENGINE:
                    for seed in range(ARENA_SEED, ARENA_SEED+plan['seeds']):
                        row = _read(folder/'episode_summaries'/self._episode_name(kind, seed, player['id']))
                        binding = (row or {}).get('binding', {})
                        owner = next((p for p in plan['participants'] if p['id'] == player['id']), None)
                        # Display archived summaries under their archived plan,
                        # without requiring the newly installed engine contract.
                        matches_plan = (binding.get('participant') == owner
                            and binding.get('kind') == kind and binding.get('seed') == seed
                            and all(binding.get(key) == plan.get(key) for key in (
                                'arena_revision', 'episode_revision', 'engine_revision', 'decision_policy'))
                            and binding.get('comparison') == (row or {}).get('comparison_spec'))
                        if row and matches_plan:
                            # An episode can serve many pairings. Count its
                            # decisions once, independent of roster size.
                            blocks.append(row.get('stability', {}))
                decisions = sum(b.get('decisions', 0) for b in blocks)
                probability_decisions = sum(b.get('probability_decisions', 0) for b in blocks)
                summary = {'decisions': decisions, 'probability_decisions': probability_decisions,
                           'probability_coverage': probability_decisions/decisions if decisions else None}
                for key in metrics:
                    weight = 'decisions' if key in ('agreement_rate', 'unanimous_rate') else 'probability_decisions'
                    valid = [b for b in blocks if b.get(key) is not None and b.get(weight, 0)]
                    summary[key] = (sum(b[key]*b[weight] for b in valid)/sum(b[weight] for b in valid)) if valid else None
                player['stability'] = summary
        for player in data['overall']:
            games = [r['stability'] for rows in data['by_game'].values() for r in rows if r['id'] == player['id']]
            summary = {key: sum(g[key] for g in games) for key in ('decisions', 'probability_decisions')}
            summary['probability_coverage'] = summary['probability_decisions']/summary['decisions'] if summary['decisions'] else None
            for key in metrics:
                values = [g[key] for g in games if g[key] is not None]
                summary[key] = sum(values)/len(values) if values else None
            player['stability'] = summary

    async def join(self):
        if self.external_manager:
            async with self.registration_lock:
                ident=self.selected_model()
                folder,plan=self._load()
                self._validate_plan(plan)
                if any(p['id']==ident for p in plan['participants']):
                    return {**self.status(),'already_enrolled':True}
                await self._preflight(self._participant(ident))
                result=await self.external_manager.join(ident)
                return {**self.status(),**result}
        if self.managed_externally:
            raise HTTPException(423, '本轮天梯由独立评测进程执行，请查看实时进度')
        ident = self.selected_model()
        async with self.registration_lock:
            folder, old = self.ensure_baseline()
            self._validate_plan(old)
            if any(p['id'] == ident for p in old['participants']):
                return {**self.status(), 'already_enrolled': True}
            if self.busy():
                raise HTTPException(409, '已有游戏评测正在运行，请等待完成')
            player = self._participant(ident)
            roster = list(old['participants']) + [player]
            for entrant in roster:
                await self._preflight(entrant)
            if self.busy():
                raise HTTPException(409, '已有游戏评测正在运行，请等待完成')
            plan = self._plan(roster)
            registrations = list(old.get('registrations', []))
            registrations.append({'model': ident, 'registered_at': time.time()})
            plan['registrations'] = registrations
            added = [fixture for fixture in plan['schedule'] if ident in (fixture['a'], fixture['b'])]
            for index, fixture in enumerate(added, start=len(old['schedule'])):
                fixture['ordinal'] = index
            plan['schedule'] = old['schedule'] + added
            plan['baseline_registered_at'] = old['baseline_registered_at']
            # Registration snapshots preserve every earlier roster and schedule.
            _write(folder/'registrations'/f'{len(registrations):05d}.json', plan)
            _write(folder/'plan.json', plan)
            _write(self.root/'latest.json', {'run_id': folder.name})
            if not self.active():
                self._launch(folder, plan)
            return {**self.status(), 'already_enrolled': False}

    async def resume(self):
        if self.external_manager:
            result=await self.external_manager.resume()
            return {**self.status(),**result}
        if self.managed_externally:
            raise HTTPException(423, '本轮天梯由独立评测进程执行，请查看实时进度')
        async with self.registration_lock:
            if self.active() or self.busy():
                raise HTTPException(409, '天梯评测正在运行')
            folder, plan = self._load()
            if not plan:
                raise HTTPException(409, '请先加入当前模型评测')
            self._validate_plan(plan)
            for player in plan['participants']:
                await self._preflight(player)
            if self.busy():
                raise HTTPException(409, '已有游戏评测正在运行')
            self._launch(folder, plan)
            return self.status()

    async def pause(self):
        if self.external_manager:
            result=await self.external_manager.pause()
            return {**self.status(),**result}
        if self.managed_externally:
            raise HTTPException(423, '本轮天梯由独立评测进程执行，请由评测进程管理暂停')
        return await super().pause()

    async def _persist_fixture(self, folder, fixture, browser):
        path = folder/'matches'/f"{fixture['ordinal']:05d}.json"
        try:
            row = await asyncio.wait_for(self._execute(folder, fixture, browser), timeout=1800)
        except asyncio.TimeoutError as exc:
            row = {**fixture, 'status': 'error', 'score_a': None, 'error_type': 'MatchTimeout',
                   'trace': getattr(exc.__cause__, 'match_trace', [])}
        if row['status'] == 'error' and not row.get('trace'):
            attempts = sorted((folder/'attempts').glob(f"{fixture['ordinal']:05d}-*.json"))
            if attempts:
                partial = _read(attempts[-1]) or {}
                if all(partial.get(key) == value for key, value in fixture.items()):
                    row['trace'] = partial.get('trace', [])
        previous = []
        for archive in sorted((folder/'retry_history'/'matches').glob(f"{fixture['ordinal']:05d}-*.json")):
            attempt = _read(archive) or {}
            if all(attempt.get(key) == value for key, value in fixture.items()):
                previous.append({**{key: attempt[key] for key in (
                    'status', 'error_type', 'http_status', 'error_code', 'seconds', 'finished_at') if key in attempt},
                    'receipt': str(archive.relative_to(folder))})
        if previous:
            row['previous_attempts'] = previous
        _write(path, row)
        _write(folder/'summaries'/path.name, self._summary_receipt(row))

    def _select_pending(self, pending, plan, active_ordinals, capacity):
        return pending[:capacity]

    async def _fixtures(self, folder, plan, browser):
        running = {}
        try:
            while True:
                # Enrollment appends work; all previous ordinals/receipts stay
                # fixed. Ratings always replay ordinal order, not finish order.
                plan = _read(folder/'plan.json')
                self._validate_plan(plan)
                pending = [f for f in plan['schedule'] if f['ordinal'] not in running
                           and not (folder/'matches'/f"{f['ordinal']:05d}.json").exists()]
                if not self.pause_requested:
                    # Interleave games so short games produce results promptly
                    # while full board games continue in other slots.
                    counts, priority = {}, {}
                    # Priority is fixed by the full schedule. Recounting only
                    # pending work would reset a just-completed game's next
                    # match to priority zero and starve all later game types.
                    for fixture in plan['schedule']:
                        kind = fixture['kind']
                        priority[fixture['ordinal']] = counts.get(kind, 0)
                        counts[kind] = counts.get(kind, 0)+1
                    pending.sort(key=lambda f: (priority[f['ordinal']], f['ordinal']))
                    selected = self._select_pending(pending, plan, set(running),
                                                    max(0, self.concurrency-len(running)))
                    for fixture in selected:
                        running[fixture['ordinal']] = asyncio.create_task(self._persist_fixture(folder, fixture, browser))
                if not running:
                    self._state(folder, 'paused' if self.pause_requested and pending else 'complete')
                    return
                self._state(folder, 'pausing' if self.pause_requested else 'running',
                            active_matches=sorted(running), concurrency=self.concurrency)
                done, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
                for ordinal, task in list(running.items()):
                    if task in done:
                        del running[ordinal]
                        task.result()
        finally:
            for task in running.values():
                task.cancel()
            if running:
                await asyncio.gather(*running.values(), return_exceptions=True)

    def install(self, app, prefix):
        @app.get(prefix+'/api/elo')
        async def status():
            return self.status()

        @app.post(prefix+'/api/elo/join')
        async def join(body: dict):
            if body:
                raise HTTPException(422, '天梯配置固定，请直接加入当前模型评测')
            return await self.join()

        @app.post(prefix+'/api/elo/pause')
        async def pause():
            return await self.pause()

        @app.post(prefix+'/api/elo/resume')
        async def resume():
            return await self.resume()
