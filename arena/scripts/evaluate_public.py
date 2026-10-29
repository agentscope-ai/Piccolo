"""One command prepares, probes and resumes the JevBench Public Piccolo Arena cohort."""
import argparse
import asyncio
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from contextlib import asynccontextmanager
import csv
import fcntl
import json
import os
from pathlib import Path
import random
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blink_arena.public_models import PublicClients, participant
from blink_arena.model_inputs import project_record, SELECTED_REVISION
from blink_arena.engine import get_engine
from jev_demo_arena import (GameArena, DIRECT_KINDS, ARENA_REVISION,
                            EPISODE_REVISION, DIRECT_REVISION, DECISION_POLICY)
from jev_demo_elo import make_plan, rating_tables, _read, _write
from jev_demo_game_evaluation import GameEvaluator, KINDS, EVALUATION_REVISION, GAME_ENGINE_REVISIONS
from jev_demo_decision_stability import repeated_predict, REALTIME_GAME_KINDS
from scripts import public_independent as independent

CONTEXT = ContextVar('public_fixture', default=None)
REVISION = 'gamejevarena-public-cohort-v4-independent-eight'
_REQUEST_CACHE = {}


def schedule(players, games, seeds, seed_base, mode='tournament'):
    if mode == independent.MODE:
        return independent.schedule(players, games, seeds, seed_base, REVISION)
    if not 1 <= seeds <= 8:
        raise ValueError('seeds_must_be_1_to_8')
    available = {p['id']: p for p in players}
    chunks = [make_plan({'participants': list(available), 'kinds': games,
                         'seeds': 1, 'seed_base': seed_base + i},
                        available=available, direct_kinds=DIRECT_KINDS) for i in range(seeds)]
    plan = chunks[0]
    fixtures = [dict(f) for chunk in chunks for f in chunk['schedule']]
    for ordinal, fixture in enumerate(fixtures):
        fixture['ordinal'] = ordinal
    plan.update(schedule=fixtures, seeds=seeds, public_revision=REVISION,
                arena_revision=ARENA_REVISION, decision_policy=DECISION_POLICY,
                game_engine_revisions=dict(GAME_ENGINE_REVISIONS),
                episode_revision=EPISODE_REVISION, direct_revision=DIRECT_REVISION,
                paired_rule='same seed, seat and budget; native score comparison; episode reused',
                direct_rule='native model versus model; two legs exchange seats',
                model_input_revision=SELECTED_REVISION, baseline_ids=list(available))
    return plan


def engine_sources():
    paths = list((ROOT/'blink_arena/engines').glob('*.py')) + [
        ROOT/'blink_arena/model_inputs.py', ROOT/'blink_arena/public_models.py', Path(__file__),
        ROOT/'scripts/public_independent.py'] + list((ROOT/'web/playground').glob('*.js')) + [
        ROOT/'web/playground/world-core-worker.cjs']
    return {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
            for p in sorted(paths)}


def prepare(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    roster = json.loads(Path(args.roster).read_text())
    ids = [i for i, row in roster['models'].items()
           if row.get('enabled') and row.get('role') != 'awaiting_rl_checkpoint']
    games = args.games or list(KINDS)
    if len(games) != len(set(games)) or set(games) - set(KINDS):
        raise ValueError('invalid_games')
    prompt = json.loads((ROOT/'config/game-prompts.json').read_text())
    scope = json.loads((ROOT/'config/game-scope.json').read_text())
    contract = {'schema': REVISION, 'roster': roster, 'games': games,
                'cohort_mode': args.cohort_mode,
                'seeds': args.seeds, 'seed_base': args.seed_base, 'concurrency': args.max_games,
                'max_games': args.max_games, 'per_model_concurrency': args.model_concurrency,
                'game_execution_timeout_seconds': args.game_timeout,
                'prompt': prompt, 'scope': scope, 'engine_sources': engine_sources(),
                'transport': {'timeout_seconds': 900, 'max_attempts': 4,
                              'global_request_concurrency': args.max_games,
                              'per_model_concurrency': args.model_concurrency},
                'input_format': 'selected-v1', 'world_wait_policy': 'frontend_clock_continues',
                'state_serialization': 'canonical-object-keys-preserve-values-and-array-order',
                'probability_policy': 'public-compatible-0.02-audited',
                'choice_policy': 'native-probability-argmax-lexicographic-original-choice-audited',
                'queue_time_in_execution_timeout': False}
    contract['inherit_from'] = str(Path(args.inherit).resolve()) if args.inherit else None
    old = _read(out/'contract.json')
    if old is not None and old != contract:
        raise ValueError('resume_contract_changed_use_original_code_and_config')
    if old is None:
        _write(out/'contract.json', contract)
        _write(out/'prompt-config.json', prompt)
        _write(out/'game-scope.json', scope)
        _write(out/'plan.json', schedule([participant(roster['models'][i]) for i in ids],
                                       games, args.seeds, args.seed_base, args.cohort_mode))
    if args.inherit and not (out/'inheritance.json').exists():
        if args.cohort_mode == independent.MODE:
            independent.inherit(out, Path(args.inherit), contract)
        else:
            inherit_completed(out, Path(args.inherit), contract)
    return contract


def inherit_completed(out, source, contract):
    """Reuse valid turn-based evidence; rerun realtime games and failed work."""
    previous, old_plan, plan = _read(source/'contract.json'), _read(source/'plan.json'), _read(out/'plan.json')
    if any(previous.get(k) != contract.get(k) for k in ('games', 'seeds', 'seed_base', 'prompt', 'scope')):
        raise ValueError('inheritance_evidence_contract_changed')
    if old_plan['participants'] != plan['participants'] or old_plan['schedule'] != plan['schedule']:
        raise ValueError('inheritance_schedule_or_model_identity_changed')
    for name, info in previous.get('engine_sources', {}).items():
        if (name.startswith('blink_arena/engines/') or name == 'blink_arena/model_inputs.py') and name != 'blink_arena/engines/jev_demo_arena.py':
            if contract['engine_sources'].get(name) != info:
                raise ValueError('inheritance_game_engine_or_prompt_projection_changed')
    status = _read(source/'status.json') or {}
    if status.get('state') not in ('paused', 'complete', 'complete_with_errors'):
        raise ValueError('inheritance_source_must_be_stopped')
    origin = {'source': str(source.resolve()), 'kind': 'validated_turn_based_reuse',
              'original_concurrency': previous['concurrency']}
    matches, episodes = set(), set()
    for fixture in plan['schedule']:
        if fixture['kind'] in REALTIME_GAME_KINDS:
            continue
        name = f"{fixture['ordinal']:05d}.json"
        row = _read(source/'matches'/name)
        if not row or row.get('status') != 'complete':
            continue
        if any(row.get(k) != v for k, v in fixture.items()):
            raise ValueError('inheritance_fixture_receipt_mismatch')
        _write(out/'matches'/name, {**row, 'provenance': origin})
        summary = _read(source/'summaries'/name) or GameArena._summary_receipt(row)
        _write(out/'summaries'/name, {**summary, 'provenance': origin})
        matches.add(fixture['ordinal'])
    participants = {p['id']: p for p in plan['participants']}
    for path in (source/'episode_summaries').glob('*.json'):
        summary = _read(path)
        if summary.get('kind') in REALTIME_GAME_KINDS or summary.get('status') != 'complete':
            continue
        binding = summary.get('binding', {})
        if (binding.get('participant') != participants.get(summary['model'])
                or summary.get('comparison_spec') != binding.get('comparison')):
            raise ValueError('inheritance_episode_binding_changed')
        row = _read(source/'episodes'/path.name)
        if not row or row.get('binding') != binding or row.get('status') != 'complete':
            raise ValueError('inheritance_episode_receipt_changed')
        _write(out/'episodes'/path.name, {**row, 'provenance': origin})
        _write(out/'episode_summaries'/path.name, {**summary, 'provenance': origin})
        episodes.add((summary['kind'], summary['seed'], summary['model']))
    requests = 0
    for path in (source/'requests').glob('*.jsonl'):
        if not path.stem.isdigit():
            continue
        fixture = old_plan['schedule'][int(path.stem)]
        if fixture['kind'] in REALTIME_GAME_KINDS:
            continue
        target = out/'requests'/path.name
        target.parent.mkdir(exist_ok=True)
        with path.open() as old, target.open('w') as new:
            for line in old:
                if not line.endswith('\n'):
                    break
                row = json.loads(line)
                if fixture['ordinal'] in matches or (fixture['kind'], fixture['seed'], row['model']) in episodes:
                    new.write(json.dumps({**row, 'runtime_generation': 'v2-inherited'}, ensure_ascii=False)+'\n')
                    requests += 1
    receipt = {'source': str(source.resolve()), 'matches': len(matches), 'episodes': len(episodes),
               'requests': requests, 'realtime_games': 'rerun_under_new_concurrency',
               'failed_work': 'retained_in_source_and_requeued', 'finished_at': time.time()}
    _write(out/'inheritance.json', receipt)
    return receipt


def request_log(out, event, context=None):
    context = (CONTEXT.get() or {}) if context is None else context
    ordinal = context.get('ordinal', 'probe')
    folder = out/'requests'
    folder.mkdir(exist_ok=True)
    with (folder/f'{ordinal}.jsonl').open('a') as stream:
        stream.write(json.dumps({**event, 'fixture_ordinal': ordinal,
                                'game': context.get('kind', 'probe'),
                                'runtime_generation': REVISION}, ensure_ascii=False) + '\n')


class RequestJournal:
    """Keep shared-disk writes off the realtime simulation's event loop."""
    def __init__(self, out):
        self.out = out
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='request-journal')
        self.pending = deque()

    def __call__(self, event):
        while self.pending and self.pending[0].done():
            self.pending.popleft().result()
        if len(self.pending) >= 128:
            raise RuntimeError('request_journal_backlog_full')
        current = CONTEXT.get() or {}
        context = {k: current[k] for k in ('ordinal', 'kind') if k in current}
        self.pending.append(self.pool.submit(request_log, self.out, event, context))

    async def close(self):
        try:
            for future in self.pending:
                await asyncio.wrap_future(future)
        finally:
            await asyncio.to_thread(self.pool.shutdown, wait=True)


def effective_contract(out, contract):
    result = json.loads(json.dumps(contract))
    for row in (_read(out/'enrollments.json') or {}).get('models', []):
        if row['id'] in result['roster']['models']:
            raise ValueError('enrollment_cannot_replace_existing_identity')
        result['roster']['models'][row['id']] = row
    return result


def append_enrollment(out, contract, row):
    old = _read(out/'plan.json')
    history = _read(out/'enrollments.json') or {'models': []}
    if row['id'] in contract['roster']['models'] or any(r['id'] == row['id'] for r in history['models']):
        raise ValueError('model_id_already_registered')
    new = schedule(old['participants']+[participant(row)], contract['games'],
                   contract['seeds'], contract['seed_base'], contract.get('cohort_mode', 'tournament'))
    added = [f for f in new['schedule'] if row['id'] in (f['a'], f['b'])]
    for ordinal, fixture in enumerate(added, len(old['schedule'])):
        fixture['ordinal'] = ordinal
    new['schedule'] = old['schedule']+added
    _write(out/'registration-history'/f'{time.time_ns()}.json', {'plan': old, 'enrollments': history})
    # Write a transaction intent first: interrupted two-file updates fail closed.
    _write(out/'enrollment-transaction.json', {'plan': new, 'enrollments': {'models': history['models']+[row]}})
    _write(out/'enrollments.json', {'models': history['models']+[row]})
    _write(out/'plan.json', new)
    _write(out/'enrollment-transaction.json', {'committed': True, 'plan': new,
        'enrollments': {'models': history['models']+[row]}})
    return len(added)


async def probe(out, contract, clients, only=None):
    """Use the same model-visible fixtures as the game engine, including long state."""
    fixture_path = out/'probe-inputs.jsonl'
    fixtures = [json.loads(line) for line in fixture_path.read_text().splitlines() if line.strip()]
    result = dict((_read(out/'availability.json') or {}).get('models', {}))
    gate = asyncio.Semaphore(2)
    async def check(ident, row):
        health = await clients.health(ident)
        status = {'id': ident, 'name': row['name'], 'health': health, 'cases': [], 'ready': False}
        result[ident] = status
        if not health['ready']:
            return
        for fixture in fixtures:
            record = fixture['record']
            qid = next(iter(record['questions']))
            if len(record['questions'][qid]['criteria']) < 2:
                continue
            async with gate:
                token = CONTEXT.set({'kind': fixture['game']})
                start = time.monotonic()
                try:
                    answer = await clients.predict(record, qid, model=ident)
                    case = {'game': fixture['game'], 'status': 'ok',
                            'served_model': answer['served_model'], 'usage': answer['usage']}
                except Exception as exc:
                    case = {'game': fixture['game'], 'status': 'error',
                            'error': getattr(exc, 'code', type(exc).__name__)}
                finally:
                    CONTEXT.reset(token)
                case['seconds'] = time.monotonic() - start
                status['cases'].append(case)
                if case['status'] != 'ok':
                    break
        status['ready'] = bool(status['cases']) and all(c['status'] == 'ok' for c in status['cases'])
    await asyncio.gather(*(check(i, r) for i, r in contract['roster']['models'].items()
                           if only is None or i in only))
    receipt = {'checked_at': time.time(), 'models': result}
    _write(out/'availability.json', receipt)
    _write(out/'availability-history'/f'{time.time_ns()}.json', receipt)
    return {i for i, r in result.items() if r['ready']}


class GameAdmission:
    """Atomically reserve a live game and all of its participating models."""
    def __init__(self, maximum, limits):
        self.maximum, self.limits = maximum, limits
        self.condition = asyncio.Condition()
        self.active = self.peak = 0
        self.by_model, self.model_peak = Counter(), Counter()

    @asynccontextmanager
    async def slot(self, models):
        models = set(models)
        async with self.condition:
            await self.condition.wait_for(lambda: self.active < self.maximum and all(
                self.by_model[m] < self.limits[m] for m in models))
            self.active += 1
            self.peak = max(self.peak, self.active)
            for m in models:
                self.by_model[m] += 1
                self.model_peak[m] = max(self.model_peak[m], self.by_model[m])
        try:
            yield
        finally:
            async with self.condition:
                self.active -= 1
                for m in models:
                    self.by_model[m] -= 1
                self.condition.notify_all()

    def snapshot(self):
        return {'active_games': self.active, 'peak_games': self.peak,
                'games_by_model': dict(self.by_model), 'game_peak_by_model': dict(self.model_peak)}


class PublicArena(GameArena):
    @staticmethod
    def _comparison_evidence(row):
        # Native comparison revalidates scores against these terminal states.
        # Only replay/decision histories are unnecessary in the in-memory cache.
        return {k: v for k, v in row.items() if k not in (
            'trace', 'native_trace', 'replay_events', 'execution_receipts',
            'evaluation_extra', 'evaluation_job', 'final_engine_state')}

    def __init__(self, out, contract, clients, ready):
        self.folder, self.contract, self.clients, self.ready_ids = out, contract, clients, ready
        plan = self.plan = _read(out/'plan.json')
        self.registered = {p['id']: p for p in plan['participants']}
        limits = {i: min(contract['per_model_concurrency'],
                        contract['roster']['models'][i]['config'].get('game_concurrency', 5))
                  for i in self.registered}
        self.games = GameAdmission(contract['max_games'], limits)
        self.episode_tasks = {}
        self.existing_episodes = {p.name for p in (out/'episodes').glob('*.json')}
        self.match_timeout_seconds = None
        first = next(iter(self.registered))
        evaluator = GameEvaluator(self.predict_public, lambda: first,
            lambda i: (i, self.registered[i]), 'http://127.0.0.1:0', out=out)
        evaluator.capture_final_state = True
        super().__init__(evaluator, models=self.registered, selected_model=lambda: first,
                         root=out, baseline_ids=list(self.registered) if len(self.registered)>1 else None, include_rule_engine=False,
                         predict=self.predict_public, concurrency=contract['max_games'])

    def _load(self):
        return self.folder, self.plan

    def _participant(self, ident):
        return dict(self.registered[ident])

    def _validate_plan(self, plan):
        expected = schedule(list(self.registered.values()), self.contract['games'],
                            self.contract['seeds'], self.contract['seed_base'],
                            self.contract.get('cohort_mode', 'tournament'))
        # Incremental enrollment appends new fixtures, preserving old ordinals.
        normalize = lambda fixtures: sorted(json.dumps({k:v for k,v in f.items() if k != 'ordinal'}, sort_keys=True) for f in fixtures)
        if (any(plan.get(k) != v for k, v in expected.items() if k != 'schedule')
                or normalize(plan['schedule']) != normalize(expected['schedule'])
                or [f['ordinal'] for f in plan['schedule']] != list(range(len(plan['schedule'])))):
            raise ValueError('saved_schedule_changed')

    async def _checked_predict(self, record, qid, model=None):
        result = await self.predict_public(record, qid, model=model)
        if result['served_model'] != self.registered[model]['served_model']:
            raise ValueError('model_identity_mismatch')
        return result

    async def predict_public(self, record, qid, model=None):
        context = CONTEXT.get()
        rng = context['rng'].setdefault(model, random.Random(
            f"{context['kind']}/{context['seed']}/{model}/{context['leg'] if context['mode']=='direct' else 0}"))
        return await repeated_predict(self.clients.predict, project_record(record, 'selected-v1'),
                                      qid, model=model, rng=rng)

    async def _persist_fixture(self, folder, fixture, browser):
        token = CONTEXT.set({**fixture, 'rng': {}})
        try:
            await super()._persist_fixture(folder, fixture, browser)
            row = _read(folder/'summaries'/f"{fixture['ordinal']:05d}.json")
            print(json.dumps({'event': 'fixture_finished', 'ordinal': fixture['ordinal'],
                              'game': fixture['kind'], 'status': row['status'],
                              'score_a': row.get('score_a'), 'seconds': row.get('seconds')}), flush=True)
        finally:
            CONTEXT.reset(token)

    async def _episode(self, folder, kind, seed, model, browser):
        key = (kind, seed, model)
        if key not in self.episode_tasks:
            async def execute():
                parent = super(PublicArena, self)
                name = self._episode_name(kind, seed, model)
                if name in self.existing_episodes:
                    row = await parent._episode(folder, kind, seed, model, browser)
                    return self._comparison_evidence(row)
                async with self.games.slot([model]):
                    try:
                        row = await asyncio.wait_for(parent._episode(folder, kind, seed, model, browser),
                            timeout=self.contract['game_execution_timeout_seconds'])
                        return self._comparison_evidence(row)
                    except asyncio.TimeoutError:
                        row = {'status': 'error', 'kind': kind, 'seed': seed, 'model': model,
                               'error_type': 'EpisodeExecutionTimeout', 'binding': self._episode_binding(kind, seed, model),
                               'finished_at': time.time()}
                        await asyncio.to_thread(_write, folder/'episodes'/name, row)
                        await asyncio.to_thread(_write, folder/'episode_summaries'/name, self._episode_summary(row))
                        return row
            self.episode_tasks[key] = asyncio.create_task(execute())
        return await asyncio.shield(self.episode_tasks[key])

    async def _execute(self, folder, fixture, browser):
        if fixture['mode'] == independent.MODE:
            row = await self._episode(folder, fixture['kind'], fixture['seed'], fixture['a'], browser)
            return independent.match_receipt(fixture, row)
        if fixture['mode'] == 'direct':
            async with self.games.slot([fixture['a'], fixture['b']]):
                async with asyncio.timeout(self.contract['game_execution_timeout_seconds']):
                    return await super()._execute(folder, fixture, browser)
        return await super()._execute(folder, fixture, browser)

    async def _fixtures(self, folder, plan, browser):
        running = {}
        completed = {int(p.stem) for p in (folder/'matches').glob('*.json') if p.stem.isdigit()}
        last_admission = time.monotonic()
        # Finite short games first, then interleave all games. Scoring still
        # replays immutable ordinal order, never completion order.
        fast = ['blackjack', 'guess_the_number', 'liars_dice', 'minesweeper', 'uno']
        ordering = fast + [g for g in plan['kinds'] if g not in fast]
        priority = {g: i for i, g in enumerate(ordering)}
        counts, slots = {}, {}
        for f in plan['schedule']:
            slots[f['ordinal']] = counts.get(f['kind'], 0)
            counts[f['kind']] = slots[f['ordinal']] + 1
        try:
            while True:
                self.ready_ids -= set(self.clients.blocked)
                if time.monotonic()-last_admission >= 60:
                    candidates = set(self.registered)-self.ready_ids
                    if candidates:
                        self.ready_ids |= await probe(folder, self.contract, self.clients, only=candidates)
                    last_admission = time.monotonic()
                pending = [f for f in plan['schedule'] if f['ordinal'] not in running
                           and f['ordinal'] not in completed]
                eligible = [f for f in pending if set(independent.fixture_models(f)) <= self.ready_ids]
                if not self.pause_requested:
                    load = Counter(m for ordinal in running for m in
                                   independent.fixture_models(plan['schedule'][ordinal]))
                    for _ in range(max(0, self.concurrency-len(running))):
                        # Independent episodes occupy a real game slot. Avoid
                        # filling workers with tasks waiting for one native replica.
                        if plan.get('cohort_mode') == independent.MODE:
                            eligible = [f for f in eligible if all(load[m] < self.games.limits[m]
                                        for m in independent.fixture_models(f))]
                        if not eligible:
                            break
                        f = min(eligible, key=lambda f: (max(load[m] for m in independent.fixture_models(f)),
                            sum(load[m] for m in independent.fixture_models(f)),
                            slots[f['ordinal']], priority[f['kind']], f['ordinal']))
                        eligible.remove(f)
                        running[f['ordinal']] = asyncio.create_task(self._persist_fixture(folder, f, browser))
                        load.update(independent.fixture_models(f))
                if not running:
                    state = ('paused' if self.pause_requested else 'waiting_for_models') if pending else 'complete'
                    await asyncio.to_thread(self._state, folder, state, pending=len(pending), http_peak=self.clients.peak,
                        model_http_peak=getattr(self.clients, 'model_peak', {}), **self.games.snapshot())
                    return
                await asyncio.to_thread(self._state, folder, 'pausing' if self.pause_requested else 'running',
                                        active_matches=list(running), ready_models=sorted(self.ready_ids),
                                        http_peak=self.clients.peak, model_http_peak=getattr(self.clients, 'model_peak', {}),
                                        **self.games.snapshot())
                done, _ = await asyncio.wait(running.values(), timeout=20,
                                            return_when=asyncio.FIRST_COMPLETED)
                for ordinal, task in list(running.items()):
                    if task in done:
                        del running[ordinal]
                        task.result()
                        completed.add(ordinal)
                await asyncio.to_thread(report, folder)
        finally:
            for task in running.values():
                task.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)
            for task in self.episode_tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.episode_tasks.values(), return_exceptions=True)


def stats(values):
    values = sorted(values)
    def percentile(q):
        if not values:
            return None
        p = (len(values)-1)*q
        i = int(p)
        return values[i]+(values[min(i+1, len(values)-1)]-values[i])*(p-i)
    return {'mean': sum(values)/len(values) if values else None,
            'p50': percentile(.5), 'p95': percentile(.95)}


def report(out):
    with (out/'report.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _report(out)


def _report(out):
    plan = _read(out/'plan.json')
    if not plan:
        return {}
    receipts = []
    for f in plan['schedule']:
        row = _read(out/'summaries'/f"{f['ordinal']:05d}.json")
        if row:
            if any(row.get(k) != v for k, v in f.items()):
                raise ValueError('receipt_fixture_mismatch')
            receipts.append(row)
    requests = []
    for path in (out/'requests').glob('*.jsonl'):
        if path.stem == 'probe':
            continue
        cached = _REQUEST_CACHE.setdefault(str(path), {'offset': 0, 'rows': []})
        if path.stat().st_size < cached['offset']:
            raise ValueError('request_journal_was_truncated')
        with path.open() as stream:
            stream.seek(cached['offset'])
            while line := stream.readline():
                if not line.endswith('\n'):
                    break
                value = json.loads(line)
                cached['rows'].append({k: value[k] for k in
                    ('model', 'game', 'status', 'seconds', 'usage', 'error', 'runtime_generation') if k in value})
                cached['offset'] = stream.tell()
        requests.extend(cached['rows'])
    if plan.get('cohort_mode') == independent.MODE:
        return independent.report(out, plan, receipts, requests, stats)
    overall, tables = rating_tables(plan, receipts)
    rows = []
    for kind in plan['kinds']:
        for p in plan['participants']:
            model = p['id']
            fixtures = [f for f in plan['schedule'] if f['kind'] == kind and model in (f['a'], f['b'])]
            done = [r for r in receipts if r['kind'] == kind and model in (r['a'], r['b'])]
            valid = [r for r in done if r['status'] == 'complete']
            wins = sum((r['score_a'] if r['a'] == model else 1-r['score_a']) == 1 for r in valid)
            draws = sum(r['score_a'] == .5 for r in valid)
            calls = [r for r in requests if r['model'] == model and r['game'] == kind]
            latency = stats([r['seconds'] for r in calls if r['status'] == 'ok'])
            current = [r for r in calls if r.get('runtime_generation') != 'v2-inherited']
            current_latency = stats([r['seconds'] for r in current if r['status'] == 'ok'])
            episodes = [_read(out/'episode_summaries'/GameArena._episode_name(kind, seed, model))
                        for seed in range(plan['seed_base'], plan['seed_base']+plan['seeds'])]
            episodes = [e for e in episodes if e]
            environment_wins = sum(e.get('outcome') == 'win' for e in episodes)
            environment_valid = sum(e.get('status') == 'complete' for e in episodes)
            rows.append({'game': kind, 'model': model, 'name': p['name'],
                         'mode': 'direct' if kind in DIRECT_KINDS else 'paired',
                         'planned_matches': len(fixtures), 'finished_matches': len(done),
                         'wins': wins, 'draws': draws, 'losses': len(valid)-wins-draws,
                         'errors': len(done)-len(valid), 'pending': len(fixtures)-len(done),
                         'arena_win_rate_lower_bound': wins/len(fixtures),
                         'arena_win_rate_completed': wins/len(valid) if valid else None,
                         'environment_episodes': len(episodes),
                         'environment_wins': environment_wins,
                         'environment_errors': len(episodes)-environment_valid,
                         'environment_pending': plan['seeds']-len(episodes) if kind not in DIRECT_KINDS else None,
                         'environment_success_rate_completed': environment_wins/environment_valid if environment_valid else None,
                         'environment_success_rate_lower_bound': environment_wins/plan['seeds'] if kind not in DIRECT_KINDS else None,
                         'environment_budget_exhausted': sum(bool(e.get('budget_exhausted')) for e in episodes),
                         'http_requests': len(calls), 'http_errors': sum(c['status'] == 'error' for c in calls),
                         'http_cancelled': sum(c['status'] == 'cancelled' for c in calls),
                         'http_current_requests': len(current), 'http_inherited_requests': len(calls)-len(current),
                         'http_current_mean_seconds': current_latency['mean'],
                         'http_current_p50_seconds': current_latency['p50'],
                         'http_current_p95_seconds': current_latency['p95'],
                         'error_counts': dict(Counter(c.get('error', 'unknown') for c in calls if c['status'] == 'error')),
                         'http_mean_seconds': latency['mean'], 'http_p50_seconds': latency['p50'],
                         'http_p95_seconds': latency['p95'],
                         'reported_cost_usd': sum((c.get('usage') or {}).get('cost', 0) or 0 for c in calls)})
    status = _read(out/'status.json') or {'state': 'prepared'}
    summary = {**status, 'updated_at': time.time(), 'planned': len(plan['schedule']),
               'finished': len(receipts), 'errors': sum(r['status'] != 'complete' for r in receipts),
               'overall': overall, 'by_game': tables, 'metrics': rows,
               'reported_cost_usd': sum(r['reported_cost_usd'] for r in rows)}
    summary['inheritance'] = _read(out/'inheritance.json')
    _write(out/'summary.json', summary)
    with (out/'game_metrics.csv.tmp').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({**r, 'error_counts': json.dumps(r['error_counts'])} for r in rows)
    (out/'game_metrics.csv.tmp').replace(out/'game_metrics.csv')
    lines = ['# Piccolo Arena · JevBench Public 模型', '',
             f"状态：{summary['state']}；已结束 {len(receipts)}/{len(plan['schedule'])} 场；错误 {summary['errors']}。",
             f"{len(plan['kinds'])} 款游戏；每款 {plan['seeds']} 个固定种子；每个模型最多 5 个请求、最多 20 局实际游戏。Blink 等 RL checkpoint 就绪后加入。", '',
             '直接对战交换座位；其余游戏复用同种子原生终局。回合制每步三次顺序探测，实时游戏一次且时钟持续。',
             '未完成的胜率为计划分母下界；Elo 为暂定值。环境通关与模型间对战胜负分别记录，不混算。', '',
             '| 模型 | 已赛 | 胜 | 平 | 负 | 错误 | 游戏覆盖 | 暂定 Elo |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in overall:
        rating = f"{row['rating']:.1f}" if row['rating'] is not None else '—'
        lines.append(f"| {row['name']} | {row['played']} | {row['wins']} | {row['draws']} | {row['losses']} | {row['errors']} | {row['coverage']}/{row['required_games']} | {rating} |")
    lines += ['', '逐游戏成功率、错误和耗时见 [game_metrics.csv](game_metrics.csv)。',
              'HTTP 耗时含服务端排队，不等于纯 GPU 时间；请求包含全部重试，原始输入和响应保存在 requests/。',
              '不可用模型仍留在赛程中，等待服务就绪后续跑；已经结束的失败不自动重打。', '']
    if summary['inheritance']:
        lines += [f"继承 {summary['inheritance']['matches']} 场有效回合制结果；实时游戏按新并发重跑。旧轮错误保留在原目录。",
                  '耗时字段 http_current_* 仅统计本轮；http_inherited_requests 单列复用的旧请求。', '']
    (out/'report.md').write_text('\n'.join(lines))
    return summary


async def main(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.command == 'report':
        result = report(out)
        print(json.dumps({k: result.get(k) for k in ('state', 'finished', 'planned', 'errors')}))
        return
    with (out/'runner.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        contract = prepare(args)
        transaction = _read(out/'enrollment-transaction.json')
        if transaction and not transaction.get('committed'):
            _write(out/'enrollments.json', transaction['enrollments'])
            _write(out/'plan.json', transaction['plan'])
            _write(out/'enrollment-transaction.json', {**transaction, 'committed': True})
        os.environ['JEV_GAME_PROMPTS_PATH'] = str(out/'prompt-config.json')
        if args.command == 'prepare':
            print(json.dumps({'state': 'prepared', 'planned': len(_read(out/'plan.json')['schedule'])}))
            report(out)
            return
        if args.command == 'enroll':
            if not all((args.model_id, args.endpoint, args.checkpoint, args.served_model)):
                raise ValueError('enroll_requires_model_id_endpoint_checkpoint_served_model')
            if any(s in args.model_id for s in ('/', '\\', '..')):
                raise ValueError('invalid_registered_model_id')
            row = {'id': args.model_id, 'name': args.model_name or 'Blink (RL)',
                   'access_id': args.served_model, 'role': 'rl', 'enabled': True,
                   'config': {'adapter': 'systemone_http', 'endpoint': args.endpoint,
                              'checkpoint': str(Path(args.checkpoint).resolve()),
                              'model_id': args.served_model,
                              'expected_returned_models': [args.served_model]}}
            client = PublicClients({'models': {row['id']: row}})
            try:
                health = await client.health(row['id'])
                if not health['ready']:
                    raise ValueError('enrollment_health_failed:' + health['reason'])
            finally:
                await client.close()
            print(json.dumps({'added_fixtures': append_enrollment(out, contract, row)}))
            return
        contract = effective_contract(out, contract)
        journal = RequestJournal(out)
        clients = PublicClients(contract['roster'], concurrency=args.max_games,
                                per_model_concurrency=args.model_concurrency, on_request=journal)
        try:
            ready = await probe(out, contract, clients)
            print(json.dumps({'event': 'probed', 'ready': sorted(ready)}), flush=True)
            if args.command == 'probe':
                return
            arena = PublicArena(out, contract, clients, ready)
            arena._validate_plan(_read(out/'plan.json'))
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: setattr(arena, 'pause_requested', True))
            await arena._fixtures(out, _read(out/'plan.json'), None)
        finally:
            await clients.close()
            await journal.close()
            await asyncio.to_thread(report, out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('prepare', 'probe', 'run', 'report', 'enroll'))
    p.add_argument('--roster', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--games', nargs='+')
    p.add_argument('--seeds', type=int, default=8)
    p.add_argument('--seed-base', type=int, default=42)
    p.add_argument('--model-concurrency', type=int, choices=range(1, 6), default=5)
    p.add_argument('--max-games', type=int, choices=range(1, 21), default=20)
    p.add_argument('--game-timeout', type=int, default=7200)
    p.add_argument('--inherit', help='Stopped prior run; reuse valid turn-based evidence only')
    p.add_argument('--cohort-mode', choices=('independent', 'tournament'), default='independent')
    p.add_argument('--model-id')
    p.add_argument('--model-name')
    p.add_argument('--endpoint')
    p.add_argument('--checkpoint')
    p.add_argument('--served-model')
    asyncio.run(main(p.parse_args()))
