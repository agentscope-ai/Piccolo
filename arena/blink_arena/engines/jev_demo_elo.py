"""Persisted, balanced tournaments using the Playground's actual game engines.

Ratings are reconstructed in schedule order, never completion order. Archived
win-rate runs have different opponent policies and are deliberately not imported.
"""
from __future__ import annotations

from jev_engine_registry import get_engine

import asyncio
import copy
from itertools import combinations
import math
from pathlib import Path
import time
import uuid

from fastapi import HTTPException
from playwright.async_api import async_playwright

from jev_demo_dashscope import MODEL_SPECS
from jev_demo_game_evaluation import (
    FRONT, KINDS, EVALUATION_REVISION, WORLD, SCENES, board, board_opponent,
    social, agent, probability, _write, _read,
)

REVISION = 'jev-elo-v1-balanced-seats-paired-terminal'
ENGINE = 'rule-engine-v1'
INITIAL = 1500.0
K = 32.0
ENGINE_SPEC = {'id': ENGINE, 'name': '规则引擎 · 棋盘算法', 'provider': 'rule_engine',
               'policy': 'jev_board_algorithm_opponent-v1'}


def participants():
    return [{'id': ident, 'name': spec['name'], 'provider': 'dashscope',
             'served_model': spec['served_model'], 'policy': 'typed-token-logprobs-v1'}
            for ident, spec in MODEL_SPECS.items()] + [dict(ENGINE_SPEC)]


def game_options():
    result = []
    extras = {'mario_platformer': '马里奥 · 闯关', 'racing_sprint': '赛车 · 自由驾驶'}
    for kind in KINDS:
        spec = next((registry[kind] for registry in (SCENES, social.SCENES, agent.SCENES, probability.SCENES)
                     if kind in registry), {})
        name = board.GAMES[kind][0] if kind in board.GAMES else spec.get('name', extras.get(kind, kind))
        result.append({'id': kind, 'name': name,
                       'mode': 'direct' if kind in board.GAMES else 'paired',
                       'engine_supported': kind in board.GAMES})
    return result


def make_plan(body, *, available=None, direct_kinds=None):
    available = available if available is not None else {row['id']: row for row in participants()}
    direct_kinds = set(board.GAMES) if direct_kinds is None else set(direct_kinds)
    ids, kinds = body.get('participants'), body.get('kinds')
    if (not isinstance(ids, list) or not 2 <= len(ids) <= len(available)
            or len(set(str(x) for x in ids)) != len(ids)
            or any(not isinstance(x, str) or x not in available for x in ids)):
        raise HTTPException(422, '请选择至少两个已登记的不同参赛者')
    if (not isinstance(kinds, list) or not kinds or len(kinds) > len(KINDS)
            or len(set(str(x) for x in kinds)) != len(kinds)
            or any(not isinstance(x, str) or x not in KINDS for x in kinds)):
        raise HTTPException(422, '请选择当前前端开放的游戏')
    seeds, seed_base = body.get('seeds', 1), body.get('seed_base', 8500000)
    if type(seeds) is not int or seeds not in (1, 2, 3):
        raise HTTPException(422, '每游戏种子数量须为 1 至 3')
    if type(seed_base) is not int or not 0 <= seed_base <= 2147483644:
        raise HTTPException(422, '起始种子须为 0 至 2147483644 的整数')
    # Canonical order makes both the schedule and ratings independent of UI order.
    ids = [ident for ident in available if ident in ids]
    kinds = [kind for kind in KINDS if kind in kinds]
    schedule = []
    for kind in kinds:
        eligible = [ident for ident in ids if ident != ENGINE or kind in board.GAMES]
        if len(eligible) < 2:
            raise HTTPException(422, '所选游戏需要至少两个支持该游戏的模型；规则引擎仅支持棋盘对战')
        for offset in range(seeds):
            for a, b in combinations(eligible, 2):
                for leg in range(2 if kind in direct_kinds else 1):
                    schedule.append({'ordinal': len(schedule), 'kind': kind,
                                     'seed': seed_base + offset, 'a': a, 'b': b,
                                     'leg': leg, 'a_side': 'X' if leg == 0 else 'O',
                                     'mode': 'direct' if kind in direct_kinds else 'paired'})
    return {'revision': REVISION, 'engine_revision': EVALUATION_REVISION,
            'participants': [available[ident] for ident in ids], 'kinds': kinds,
            'seeds': seeds, 'seed_base': seed_base, 'initial_rating': INITIAL, 'k': K,
            'rating_rule': 'per-game Elo; overall is equal-weight mean with full game coverage',
            'paired_rule': 'same seed and fixed rule opponents; win=1,draw=0.5,loss/budget=0; compare terminal points',
            'board_rule': 'same seeded opening, two legs with swapped seats; actual terminal winner',
            'execution_order': 'canonical schedule ordinal', 'schedule': schedule}


def elo_delta(a, b, score):
    return K * (score - 1 / (1 + 10 ** ((b - a) / 400)))


def rating_tables(plan, receipts):
    roster = plan['participants']
    tables = {}
    # A receipt must match its immutable schedule entry before it can affect Elo.
    rows = {row['ordinal']: row for row in receipts if type(row.get('ordinal')) is int}
    for kind in plan['kinds']:
        entries = {p['id']: {**{key: p[key] for key in ('id', 'name')},
                             'rating': INITIAL, 'played': 0, 'wins': 0, 'draws': 0,
                             'losses': 0, 'errors': 0} for p in roster}
        for fixture in plan['schedule']:
            if fixture['kind'] != kind:
                continue
            row = rows.get(fixture['ordinal'])
            if row is None:
                continue
            a, b = entries[fixture['a']], entries[fixture['b']]
            exact = all(row.get(key) == value for key, value in fixture.items())
            score = row.get('score_a')
            if (not exact or row.get('status') != 'complete' or type(score) not in (float, int)
                    or score not in (0, .5, 1)):
                a['errors'] += 1
                b['errors'] += 1
                continue
            delta = elo_delta(a['rating'], b['rating'], score)
            a['rating'] += delta
            b['rating'] -= delta
            for item, value in ((a, score), (b, 1-score)):
                item['played'] += 1
                item['wins' if value == 1 else 'losses' if value == 0 else 'draws'] += 1
        for row in entries.values():
            row.update(coverage=int(row['played'] > 0), required_games=1,
                       provisional=row['played'] < 30 or row['errors'] > 0)
            if not row['played']:
                row['rating'] = None
        tables[kind] = _rank(list(entries.values()))
    overall = []
    for player in roster:
        applicable = [kind for kind in plan['kinds']
                      if player['id'] != ENGINE or kind in board.GAMES]
        games = [next(r for r in tables[kind] if r['id'] == player['id']) for kind in applicable]
        scored = [r for r in games if r['rating'] is not None]
        full = bool(games) and len(scored) == len(games)
        overall_eligible = player['id'] != ENGINE
        overall.append({'id': player['id'], 'name': player['name'],
                        'rating': sum(r['rating'] for r in scored)/len(scored) if full and overall_eligible else None,
                        'coverage': len(scored), 'required_games': len(games),
                        'coverage_complete': full, 'overall_eligible': overall_eligible,
                        **{key: sum(r[key] for r in games) for key in ('played', 'wins', 'draws', 'losses', 'errors')},
                        'provisional': not full or any(r['provisional'] for r in games)})
    return _rank(overall), tables


def _rank(rows):
    rows.sort(key=lambda row: (-(row['rating'] if row['rating'] is not None else -math.inf), row['id']))
    previous = None
    for index, row in enumerate(rows):
        # Equal ratings share the same rank; no arbitrary tie-breaking by name.
        rounded = round(row['rating'], 8) if row['rating'] is not None else None
        row['rank'] = (previous['rank'] if previous and rounded == previous['_rating'] else index+1) if rounded is not None else None
        row['_rating'] = rounded
        previous = row
    for row in rows:
        row.pop('_rating')
    return rows


class EloTournament:
    def __init__(self, evaluator, *, root=None, ready=None, busy=None):
        self.evaluator = copy.copy(evaluator)
        self._original_predict = evaluator.predict
        self.evaluator.predict = self._checked_predict
        self.root = Path(root) if root is not None else FRONT/'elo_tournaments'
        self.ready = ready or (lambda ident: True)
        self.busy = busy or (lambda: False)
        self.task = None
        self.pause_requested = False

    async def _checked_predict(self, record, qid, model=None):
        result = await self._original_predict(record, qid, model=model)
        if (model not in MODEL_SPECS or result.get('model') != model
                or result.get('served_model') != MODEL_SPECS[model]['served_model']):
            raise ValueError('model_identity_mismatch')
        return result

    def active(self):
        return self.task is not None and not self.task.done()

    def _load(self):
        latest = _read(self.root/'latest.json')
        if not latest:
            return None, None
        folder = self.root/latest['run_id']
        return folder, _read(folder/'plan.json')

    def status(self):
        folder, plan = self._load()
        options = {'participants': participants(), 'games': game_options()}
        if not plan:
            return {'state': 'idle', 'run_id': None, 'completed': 0, 'planned': 0,
                    'protocol': None, 'overall': [], 'by_game': {}, 'matches': [], 'options': options}
        receipts = self._receipts(folder, plan)
        state = _read(folder/'status.json') or {'state': 'interrupted'}
        if state['state'] in ('running', 'pausing') and not self.active():
            state = {**state, 'state': 'interrupted'}
        overall, by_game = rating_tables(plan, receipts)
        return {**state, 'run_id': folder.name, 'protocol': plan, 'options': options,
                'completed': len(receipts), 'planned': len(plan['schedule']),
                'scored': sum(r.get('status') == 'complete' for r in receipts),
                'overall': overall, 'by_game': by_game,
                'matches': [{key: value for key, value in row.items()
                             if key not in ('trace', 'initial_state', 'final_state')}
                            for row in receipts[-80:]]}

    def _receipts(self, folder, plan):
        return [row for fixture in plan['schedule']
                if (row := _read(folder/'matches'/f"{fixture['ordinal']:05d}.json")) is not None]

    def _state(self, folder, state, **extra):
        _write(folder/'status.json', {'state': state, 'updated_at': time.time(), **extra})

    async def start(self, body):
        if self.active() or self.busy():
            raise HTTPException(409, '已有游戏评测正在运行，请先暂停或等待完成')
        plan = make_plan(body)
        for player in plan['participants']:
            if player['id'] != ENGINE and not self.ready(player['id']):
                raise HTTPException(503, player['name']+' 尚未就绪')
        run_id = time.strftime('%Y%m%d-%H%M%S', time.gmtime())+'-'+uuid.uuid4().hex[:8]
        folder = self.root/run_id
        _write(folder/'plan.json', plan)
        _write(self.root/'latest.json', {'run_id': run_id})
        self._launch(folder, plan)
        return self.status()

    def _launch(self, folder, plan):
        self.pause_requested = False
        self._state(folder, 'running')
        self.task = asyncio.create_task(self._run(folder, plan))

    async def pause(self):
        if self.active():
            self.pause_requested = True
            folder, _ = self._load()
            self._state(folder, 'pausing')
        return self.status()

    async def resume(self):
        if self.active() or self.busy():
            raise HTTPException(409, '已有游戏评测正在运行')
        folder, plan = self._load()
        if not plan or plan.get('revision') != REVISION or plan.get('engine_revision') != EVALUATION_REVISION:
            raise HTTPException(409, '没有当前协议可续跑的对局')
        expected = {p['id']: p for p in participants()}
        if any(expected.get(p['id']) != p for p in plan['participants']):
            raise HTTPException(409, '模型登记已变化，请创建新一轮评测')
        for player in plan['participants']:
            if player['id'] != ENGINE and not self.ready(player['id']):
                raise HTTPException(503, player['name']+' 尚未就绪')
        self._launch(folder, plan)
        return self.status()

    async def _action(self, game, player, seed, ordinal):
        record, options = board.as_record(game)
        if player == ENGINE:
            action = await asyncio.to_thread(board_opponent.choose, game, options, seed, ordinal)
            return action, {'origin': 'rule_engine'}
        if len(options) == 1:
            return next(iter(options)), {'origin': 'forced_legal', 'model_call': False}
        began = time.monotonic()
        result = await self.evaluator.predict(record, 'decision', model=player)
        # _checked_predict verifies the registered provider/checkpoint identity.
        action = str(result['value'])
        if action not in options:
            raise ValueError('illegal_action')
        return action, {'origin': 'model', 'model_call': True,
                        'model': player, 'served_model': result['served_model'],
                        'latency_seconds': round(time.monotonic()-began, 3),
                        'decision_stability': result.get('decision_stability')}

    async def _direct(self, folder, fixture):
        game = board.fresh(fixture['kind'], fixture['seed'])
        initial = game
        trace = []
        seats = {fixture['a_side']: fixture['a'], 'O' if fixture['a_side'] == 'X' else 'X': fixture['b']}
        # Full native board termination, including Othello passes; not a short rollout.
        limit = 2*game['n']*game['n']+4
        try:
            for ordinal in range(limit):
                if game['winner']:
                    break
                player = seats[game['turn']]
                action, receipt = await self._action(game, player, fixture['seed'], ordinal)
                trace.append({'ordinal': ordinal, 'side': game['turn'], 'player': player,
                              'action': action, **receipt})
                game = board.move(game, action)
            if game['winner'] not in ('X', 'O', 'draw'):
                raise ValueError('nonterminal_board')
            return {'score_a': .5 if game['winner'] == 'draw' else float(game['winner'] == fixture['a_side']),
                    'winner': game['winner'], 'steps': len(trace), 'seats': seats,
                    'initial_state': initial, 'final_state': game, 'trace': trace}
        except BaseException:
            # Preserve paid partial work without turning an incomplete game into a draw.
            _write(folder/'attempts'/f"{fixture['ordinal']:05d}-{time.time_ns()}.json",
                   {**fixture, 'status': 'interrupted', 'initial_state': initial,
                    'final_state': game, 'trace': trace})
            raise

    async def _episode(self, folder, kind, seed, model, browser):
        path = folder/'episodes'/f'{kind}-{seed}-{model}.json'
        previous = _read(path)
        if previous:
            return previous
        began = time.monotonic()
        try:
            result = (await self.evaluator._world(browser, kind, seed, model) if kind in WORLD else
                      await self.evaluator._python(None, kind, seed, 'rule_engine', model))
            outcome = result.get('outcome')
            if result.get('status') == 'error' or outcome not in ('win', 'draw', 'loss', 'budget_exhausted'):
                raise ValueError('invalid_episode_result')
            row = {'status': 'complete', 'model': model, 'kind': kind, 'seed': seed,
                   'served_model': MODEL_SPECS[model]['served_model'],
                   'points': {'win': 1, 'draw': .5, 'loss': 0, 'budget_exhausted': 0}[outcome],
                   'result': result, 'seconds': round(time.monotonic()-began, 3)}
        except Exception as exc:
            row = {'status': 'error', 'model': model, 'kind': kind, 'seed': seed,
                   'error_type': type(exc).__name__}
        _write(path, row)
        return row

    async def _execute(self, folder, fixture, browser):
        began = time.monotonic()
        try:
            if fixture['mode'] == 'direct':
                result = await self._direct(folder, fixture)
            else:
                a = await self._episode(folder, fixture['kind'], fixture['seed'], fixture['a'], browser)
                b = await self._episode(folder, fixture['kind'], fixture['seed'], fixture['b'], browser)
                if a['status'] != 'complete' or b['status'] != 'complete':
                    raise ValueError('paired_episode_failed')
                result = {'score_a': 1. if a['points'] > b['points'] else 0. if a['points'] < b['points'] else .5,
                          'points_a': a['points'], 'points_b': b['points'],
                          'outcome_a': a['result']['outcome'], 'outcome_b': b['result']['outcome']}
            return {**fixture, 'status': 'complete', **result,
                    'seconds': round(time.monotonic()-began, 3), 'finished_at': time.time()}
        except Exception as exc:
            return {**fixture, 'status': 'error', 'score_a': None,
                    'error_type': type(exc).__name__, 'seconds': round(time.monotonic()-began, 3),
                    'finished_at': time.time()}

    async def _run(self, folder, plan):
        try:
            if any(get_engine(kind).backend == 'browser' for kind in plan['kinds']):
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
                    try:
                        await self._fixtures(folder, plan, browser)
                    finally:
                        await browser.close()
            else:
                await self._fixtures(folder, plan, None)
        except asyncio.CancelledError:
            self._state(folder, 'interrupted')
            raise
        except Exception as exc:
            self._state(folder, 'error', error_type=type(exc).__name__)

    async def _fixtures(self, folder, plan, browser):
        for fixture in plan['schedule']:
            path = folder/'matches'/f"{fixture['ordinal']:05d}.json"
            if path.exists():
                continue
            if self.pause_requested:
                self._state(folder, 'paused')
                return
            self._state(folder, 'running', current=fixture)
            try:
                row = await asyncio.wait_for(self._execute(folder, fixture, browser), timeout=1800)
            except asyncio.TimeoutError:
                row = {**fixture, 'status': 'error', 'score_a': None, 'error_type': 'MatchTimeout'}
            _write(path, row)
            self._state(folder, 'pausing' if self.pause_requested else 'running')
        self._state(folder, 'complete')

    def install(self, app, prefix):
        @app.get(prefix+'/api/elo')
        async def status():
            return self.status()

        @app.post(prefix+'/api/elo/start')
        async def start(body: dict):
            return await self.start(body)

        @app.post(prefix+'/api/elo/pause')
        async def pause():
            return await self.pause()

        @app.post(prefix+'/api/elo/resume')
        async def resume():
            return await self.resume()
