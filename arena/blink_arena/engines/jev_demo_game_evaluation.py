from __future__ import annotations

from blink_arena.paths import REPO as BASE, WEB as FRONT, DATA
OUT = DATA / "game_evaluations"

import asyncio

import copy

import importlib

import inspect

import json

import random

import re

import time

from pathlib import Path


from fastapi import HTTPException

from playwright.async_api import async_playwright

import jev_agent_games as agent

import jev_demo_games as board

import jev_probability_games as probability

import jev_racing_game as racing

import jev_snake_realtime as snake

import jev_tetris_realtime as tetris

import jev_social_games as social

import jev_eval_social_opponents as social_opponents

import jev_board_algorithm_opponent as board_opponent

from jev_demo_showcases import as_record, choices, fresh, step

from blink_arena.game_constants import WORLD, LIMITS

from jev_engine_registry import get_engine, list_engines

from jev_control_scope import active_games

from jev_gameplay_contract import adapt_record

from jev_showcase_common import SCENES

HIDDEN = {'breakthrough', 'mancala', 'robot_pick_cola', 'jump_jump'}

KINDS = tuple(active_games(engine.kind for engine in list_engines(include_internal=False) if engine.kind not in HIDDEN))

_INITIAL_KINDS = KINDS

EVALUATION_REVISION = 'frontend-full-game-eight-v11-retired6'
from jev_control_scope import policy as _scope_policy
GAME_SCOPE_REVISION = _scope_policy()['revision']

GAME_ENGINE_REVISIONS = {tetris.KIND: tetris.REVISION,
    'chess': 'jev.chess.visible-one-ply.v1',
    'mario_platformer': 'shared-core-v1+mario-map-v2-curriculum',
    'terraria_survival': 'shared-core-v1+terramai-gate-guardian-v1'}

SEED_BASE = 8300000

def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)

def _read(path):
    return json.loads(path.read_text()) if path.exists() else None

def _modes(kind, episodes_per_game=8):
    if type(episodes_per_game) is not int or episodes_per_game <= 0 or episodes_per_game % 4:
        raise ValueError('episodes_per_game must be a positive multiple of four for opponent/seat balance')
    modes = get_engine(kind).opponent_modes
    if not modes or episodes_per_game % len(modes):
        raise ValueError('episode count must balance registered opponent modes')
    return list(modes) * (episodes_per_game // len(modes))

def _seat(kind, seed, mode):
    engine = get_engine(kind)
    if engine.family == 'board':
        return 'X' if (seed // 2) % 2 == 0 else 'O'
    if engine.seat_count > 1:
        return (seed // 2 + (mode == 'rule_engine')) % engine.seat_count
    if kind in agent.SCENES:
        return 0
    return None

class GameEvaluator:
    def __init__(self, predict, selected_model, model_spec, frontend, *, out=None,
                 seed_base=None, episodes_per_game=8, episode_concurrency=4, busy=None):
        self.predict = predict
        self.selected_model = selected_model
        self.model_spec = model_spec
        self.frontend = frontend
        self.busy = busy or (lambda: False)
        # Explicit legacy subsets remain supported; otherwise discover plugins
        # at evaluator creation and freeze that roster for the whole run.
        self.kinds = (tuple(KINDS) if KINDS != _INITIAL_KINDS else
                      tuple(active_games(e.kind for e in list_engines(include_internal=False))))
        _modes(self.kinds[0], episodes_per_game)
        if type(episode_concurrency) is not int or episode_concurrency < 1:
            raise ValueError('episode_concurrency must be positive')
        self.out = Path(out) if out is not None else OUT
        self.seed_base = SEED_BASE if seed_base is None else seed_base
        self.episodes_per_game = episodes_per_game
        self.episode_concurrency = episode_concurrency
        if type(self.seed_base) is not int or not 0 <= self.seed_base <= 4294967295:
            raise ValueError('seed_base must be uint32')
        if self.seed_base + len(self.kinds)*episodes_per_game > 4294967296:
            raise ValueError('held-out seed range exceeds uint32')
        self.task = None
        self.run_id = None

    async def _current(self, record, model):
        options = record['questions']['decision']['criteria']
        if len(options) == 1:
            return next(iter(options)), False
        result = await self.predict(record, 'decision', model=model)
        action = str(result['value'])
        if action not in options:
            raise ValueError('本地模型输出非法动作')
        return action, True

    def _capture_final(self, result, final_state, initial_state=None, terminal_returns=None):
        """Opt-in absolute-score evidence for Arena; archived projections stay unchanged."""
        if not getattr(self, 'capture_final_state', False):
            return result
        return {**result, 'capture_revision': 'jev-arena-final-state-v1',
                'final_state': copy.deepcopy(final_state),
                'initial_state': copy.deepcopy(initial_state),
                'terminal_returns': copy.deepcopy(terminal_returns)}

    async def _board(self, pool, kind, seed, mode, model):
        engine = get_engine(kind)
        game = engine.reset(seed)
        initial_state = copy.deepcopy(engine.public(game)) if getattr(self, 'capture_final_state', False) else None
        model_side = _seat(kind, seed, mode)
        opening = game['_initialization']['plies']
        calls = 0
        for turn in range(LIMITS[kind]):
            if engine.outcome(game, model_side) or not engine.legal_actions(game):
                break
            record = engine.observe(game)
            options = list(record['questions']['decision']['criteria'])
            if game['turn'] == model_side:
                action, used = await self._current(record, model)
                calls += used
            else:
                action = (await self._qwen(pool, kind, seed, turn, record)
                          if mode == 'qwen3.8-max' else
                          board_opponent.choose(game, options, seed, turn))
            if action not in options:
                raise ValueError('动作不在公开候选中')
            game = engine.step(game, action)
        result = {'outcome': engine.outcome(game, model_side) or 'budget_exhausted',
                'model_calls': calls, 'opening_plies': opening, 'model_side': model_side,
                'final_turn': game['turn']}
        if getattr(self, 'capture_final_state', False):
            result['model_player'] = 0 if model_side == 'X' else 1
        return self._capture_final(result, engine.public(game), initial_state)

    async def _python(self, pool, kind, seed, mode, model):
        engine = get_engine(kind)
        if engine.rl_runner:
            module, attribute = engine.rl_runner.split(':', 1)
            runner_module = importlib.import_module(module)
            evaluation_play = getattr(runner_module, attribute + '_evaluation', None)
            play = evaluation_play or getattr(runner_module, attribute)
            if not engine.rl_verify:
                raise ValueError('registered realtime engine requires an exact replay verifier')
            module, attribute = engine.rl_verify.split(':', 1)
            verify_module = importlib.import_module(module)
            evaluation_verify = getattr(verify_module, attribute + '_evaluation', None)
            if bool(evaluation_play) != bool(evaluation_verify):
                raise ValueError('evaluation runner and verifier must be paired')
            verify = evaluation_verify or getattr(verify_module, attribute)
            evaluator=self
            class RacingPolicy:
                def __init__(self):self.model_calls=0;self.model_requests=0
                def journal(self,*args):pass
                async def policy_action(self,record,episode_id,ordinal):
                    self.model_requests+=1
                    if kind == tetris.KIND:
                        options=record['questions']['decision']['criteria']
                        if len(options)==1:return next(iter(options)),{'forced':True,'origin':'forced'}
                        result=await evaluator.predict(record,'decision',model=model)
                        # A late timeout can occur after natural terminal. Count
                        # the returned predictions separately from requests, so
                        # Arena's prediction trace still closes exactly.
                        self.model_calls+=1
                        action=str(result['value'])
                        if action not in options:raise ValueError('本地模型输出非法动作')
                        return action,{'forced':False,'origin':'model'}
                    self.model_calls+=1
                    action,used=await evaluator._current(record,model)
                    return action,{'forced':not used,'origin':'evaluation_model' if evaluation_play else 'model'}
            policy=RacingPolicy()
            if engine.seat_count > 1:
                async def opponent(*args):
                    return await evaluator._qwen(pool, *args), {'origin':'opponent_model','forced':False}
                policy.qwen=opponent
                policy.journal=lambda *args: None
            job={'kind':kind,'seed':seed,'side':(_seat(kind,seed,mode) or 0) if engine.seat_count>1 else 0,
                 'mode':mode if engine.seat_count>1 else 'environment',
                 'episode_id':f'frontend-eval-{kind}-{seed}'}
            initial,final,trace,outcome,extra=await play(policy,job)
            verify_args={'trace':trace} if 'trace' in inspect.signature(verify).parameters else {}
            verified = verify(job,initial,final,extra,**verify_args)
            if inspect.isawaitable(verified):
                await verified
            return {'outcome':outcome,'status':'complete' if extra.get('status','complete')=='complete' else 'error',
                'error_type':extra.get('error_type'),'model_calls':policy.model_calls,
                **({'model_requests':policy.model_requests} if kind==tetris.KIND else {}),
                **({'model_player':job['side']} if engine.seat_count>1 else {}),
                'steps':len(trace),'forced_B':extra.get('deterministic_student_actions',0),'rule_takeover_C':extra.get('rule_takeover_count',0),
                'clock_contract':extra.get('clock_contract',engine.clock),'final_state':engine.public(final),
                'failure_reason':final.get('failure_reason'),'replay_verified':True,
                'initial_state':initial,'trace':trace,'replay_events':extra.get('replay_events',[]),
                **({'evaluation_job':job,'evaluation_extra':extra,'final_engine_state':final,
                    'evaluation_only':True,'on_policy':False} if evaluation_play else {}),
                'real_time_seconds':extra.get('real_time_seconds'),'inference_world_paused':engine.clock != 'realtime',
                **({'decision_limit':extra['decision_limit']} if 'decision_limit' in extra else {}),
                'capture_revision':'jev-arena-final-state-v1',
                'inference_waiting_seconds':extra.get('inference_waiting_seconds'),
                'reward_export_prohibited':True}
        # Keep the exact production engines; only assign each existing actor's
        # legal public choice to the selected model/Qwen/rule opponent.
        if kind in social.SCENES or kind in probability.SCENES:
            from types import SimpleNamespace
            from jev_game_seat_control import play
            evaluator = self
            model_player = _seat(kind, seed, mode)
            native = SimpleNamespace(fresh=fresh, choices=choices, as_record=as_record,
                step=step, social=social, probability=probability,
                social_opponents=social_opponents, LIMITS=LIMITS)
            class ActorPolicy:
                def __init__(self):
                    self.model_calls = 0
                async def policy_action(self, record, episode_id, ordinal):
                    action, used = await evaluator._current(record, model)
                    self.model_calls += used
                    return action, {'forced': not used, 'origin': 'model'}
                async def qwen(self, _kind, _seed, ordinal, record):
                    action = await evaluator._qwen(pool, _kind, _seed, ordinal, record)
                    return action, {'forced': False, 'origin': 'qwen_opponent'}
                def journal(self, *args):
                    pass
            policy = ActorPolicy()
            job = {'kind': kind, 'seed': seed, 'side': model_player, 'mode': mode,
                   'episode_id': f'frontend-eval-{kind}-{seed}'}
            initial, game, trace, outcome, extra = await play(policy, native, job)
            result = {'outcome': outcome, 'model_player': model_player,
                'model_calls': policy.model_calls, 'qwen_calls': extra['qwen_calls'],
                'steps': game['steps'], 'native_actor_control': True,
                'role_asymmetry': extra['role_asymmetry'],
                'engine_actor0_policy': extra['engine_actor0_policy'],
                'forced_B': sum(bool(t['policy'].get('forced')) for t in trace),
                'rule_takeover_C': 0, 'reward_export_prohibited': True}
            public = probability.public if kind in probability.SCENES else social.public
            return self._capture_final(result, public(game), public(initial))
        use_agent = kind in agent.SCENES
        # Human actor control already exists in the frontend. It prevents the
        # built-in auto opponent from silently owning a model assigned seat 1.
        model_player = _seat(kind, seed, mode) if use_agent else 0
        game = fresh(kind, seed, 'human' if use_agent else 'rule')
        initial_state = (copy.deepcopy(engine.public(game))
                         if getattr(self, 'capture_final_state', False) else None)
        calls = qwen_calls = forced_B = 0
        for ordinal in range(LIMITS[kind]):
            if use_agent and game.get('handoff'):
                game = agent.reveal(game)
            outcome = engine.outcome(game)
            if outcome:
                break
            options = choices(game)
            if not options:
                break
            record = as_record(game) if len(options) >= 2 else None
            actor = agent.actor(game) if use_agent else 0
            if record is None:
                action = next(iter(options))
                forced_B += actor == model_player
            elif use_agent and actor != model_player:
                if mode == 'qwen3.8-max':
                    action = await self._qwen(pool, kind, seed, ordinal, record)
                    qwen_calls += 1
                else:
                    action = agent.rule_action(game, actor)
            else:
                action, used = await self._current(record, model)
                calls += used
            game = await asyncio.to_thread(step, game, action) if use_agent else step(game, action)
        visible = engine.public(game)
        outcome = engine.outcome(game) or 'budget_exhausted'
        if use_agent and model_player == 1:
            outcome = {'win': 'loss', 'loss': 'win'}.get(outcome, outcome)
        result = {'outcome': outcome, 'model_player': model_player,
                'model_calls': calls, 'qwen_calls': qwen_calls, 'steps': visible.get('steps'),
                'forced_B': forced_B, 'rule_takeover_C': 0}
        terminal_returns = None
        if getattr(self, 'capture_final_state', False) and use_agent and agent.finished(game):
            terminal_returns = list(agent.restore(game).returns())
        return self._capture_final(result, visible, initial_state, terminal_returns)

    async def _world(self, browser, kind, seed, model):
        engine = get_engine(kind)
        if engine.rl_runner != 'jev_world_realtime_rl:play':
            return await self._registered_browser(browser, engine, seed, model)
        from jev_world_episode_clock import install_episode_clock
        filename, bridge, record_fn = WORLD[kind]
        page = await browser.new_page(viewport={'width': 920, 'height': 700})
        calls = executed = discarded = 0
        receipts = []
        try:
            await install_episode_clock(page, kind)
            await page.goto(self.frontend.rstrip('/') + '/playground/' + filename + '.html')
            await page.wait_for_function('!!window.' + bridge + '?.snapshot')
            initial = await page.evaluate('([b,seed])=>{window[b].reset(seed);window[b].activate(true);const state=window[b].prepare({clock:"realtime"});window.__JevEpisodeClock.start();return state}', [bridge,seed])
            state = initial
            for ordinal in range(LIMITS[kind]):
                observation = await page.evaluate('b=>window[b].prepare({clock:"realtime"})', bridge)
                state = observation
                if state.get('outcome') or kind == 'terraria_survival' and state.get('wins', 0) > initial.get('wins', 0):
                    break
                record = record_fn(observation)
                # Keep the complete public clock, including provider-independent
                # extensions, identical in live evaluation and training input.
                record['state']['observation']['timing'] = copy.deepcopy(observation['timing'])
                started = time.monotonic()
                action, used = await self._current(record, model)
                calls += used
                inference_seconds = time.monotonic()-started
                execution = await page.evaluate('''async ([b,a,observation])=>{
                  const api=window[b],arrival=api.snapshot();
                  const reason=arrival.outcome?'terminal':
                    (arrival.wins||0)!==(observation.wins||0)?'world_changed':
                    (arrival.deaths||0)!==(observation.deaths||0)||
                    arrival.player?.respawning||observation.player?.respawning?'death_or_respawn':null;
                  // Snapshot, validity check and action start share one task;
                  // replay never has to guess a start from the action duration.
                  const after=reason?arrival:await api.act(a);
                  return {arrival,after,reason,action_start_frame:reason?null:arrival.frame};
                }''', [bridge, action, observation])
                state, reason = execution['after'], execution['reason']
                arrival = execution['arrival']
                receipt = {'ordinal':ordinal, 'action':action, 'observation_frame':observation['frame'],
                           'execution_frame':arrival['frame'], 'inference_frames':arrival['frame']-observation['frame'],
                           'action_start_frame':execution['action_start_frame'],
                           'after_frame':state['frame'],
                           'latency_seconds':inference_seconds,
                           'status':'discarded' if reason else 'executed', 'reason':reason}
                receipts.append(receipt)
                if reason:
                    discarded += 1
                    if reason in ('terminal', 'world_changed'):
                        break
                    continue
                executed += 1
            outcome = 'win' if kind == 'terraria_survival' and state.get('wins', 0) > initial.get('wins', 0) else state.get('outcome') or 'budget_exhausted'
            terminal_clock = await page.evaluate('window.__JevEpisodeClock.finish()')
            result = {'outcome': outcome, 'model_calls': calls, 'steps': executed,
                    'progress': state.get('progress'), 'wins': state.get('wins'),
                    'deaths':state.get('deaths',0), 'discarded_replies':discarded,
                    'clock_contract':'realtime-v1', 'inference_world_paused':False,
                    'real_time_seconds':terminal_clock['elapsed_seconds'],
                    'terminal_clock':terminal_clock,
                    'execution_receipts':receipts}
            return self._capture_final(result, state, initial)
        finally:
            await page.close()

    async def _registered_browser(self, browser, engine, seed, model):
        """A browser plugin owns its real clock and exact replay implementation."""
        from types import SimpleNamespace
        evaluator = self

        class BrowserPolicy:
            def __init__(self):
                self.browser = browser
                self.args = SimpleNamespace(frontend=evaluator.frontend)
                self.model_calls = 0

            async def policy_action(self, record, episode_id, ordinal):
                action, used = await evaluator._current(record, model)
                self.model_calls += used
                return action, {'forced': not used, 'origin': 'model'}

        if not engine.rl_runner or not engine.rl_verify:
            raise ValueError('browser engine requires rollout and exact replay hooks')
        module, attribute = engine.rl_runner.split(':', 1)
        play = getattr(importlib.import_module(module), attribute)
        module, attribute = engine.rl_verify.split(':', 1)
        verify = getattr(importlib.import_module(module), attribute)
        policy = BrowserPolicy()
        job = {'kind': engine.kind, 'seed': seed, 'side': 0, 'mode': 'environment',
               'episode_id': f'frontend-eval-{engine.kind}-{seed}'}
        initial, final, trace, outcome, extra = await play(policy, job)
        if engine.backend == 'worker' and engine.family == 'world':
            from jev_world_core_rl import verify_with_trace
            checked = verify_with_trace(policy, job, initial, final, trace, extra)
        else:
            checked = verify(policy, job, initial, final, extra, trace)
        if inspect.isawaitable(checked):
            await checked
        result = {**extra, 'outcome': outcome, 'model_calls': policy.model_calls,
                'steps': len(trace), 'trace': trace, 'initial_state': initial,
                'final_state': engine.public(final), 'replay_verified': True,
                'reward_export_prohibited': True}
        return self._capture_final(result, engine.public(final), initial)

    async def _qwen(self, *args, **kwargs):
        raise RuntimeError("Register the opponent as an explicit model connection")
