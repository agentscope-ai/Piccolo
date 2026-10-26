"""Shared episode execution for standalone backends and the legacy RL sampler.

The existing board/native/browser loops and exact replay methods live here once.
Policy inference is an injected callback on the runner; this module does not
load tokenizers, credentials, dataset audits, providers, or training frameworks.
"""
from __future__ import annotations

import asyncio
import copy
import importlib
import inspect
import json
import math
from pathlib import Path
import random
import time

import jev_agent_games as agent
import jev_eval_social_opponents as social_opponents
import jev_probability_games as probability
import jev_social_games as social
import jev_board_algorithm_opponent as board_bot
from jev_engine_registry import get_engine
from jev_gameplay_reward_contract import (
    settle_episode, terminal_objective, validate_episode as validate_reward_episode,
)
from jev_realtime_scoring import REALTIME_KINDS, SCORING_REVISION, score_episode


class _DecisionLimits(dict):
    """Diagnostic overrides with the shared registry as the default source."""
    def __missing__(self, kind):
        return get_engine(kind).limit


LIMITS = _DecisionLimits()


def fresh(kind, seed, opponent='human'):
    engine = get_engine(kind)
    return engine.reset(seed, {'opponent': opponent} if engine.family == 'agent' else None)

def choices(state):
    return get_engine(state['kind'], state).legal_actions(state)

def as_record(state):
    return get_engine(state['kind'], state).observe(state)

def step(state, action, **kwargs):
    return get_engine(state['kind'], state).step(state, action, **kwargs)

def _runner(reference):
    module, separator, attribute = reference.partition(':')
    if not separator or not module or not attribute:
        raise ValueError('engine rollout hook must be module:attribute')
    function = getattr(importlib.import_module(module), attribute)
    if not callable(function):
        raise ValueError('engine rollout hook is not callable')
    return function

def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False,
                               default=_json_default) + '\n')
    temp.replace(path)

def read(path):
    return json.loads(Path(path).read_text())

def _json_default(value):
    if isinstance(value, random.Random):
        return {'__python_random_state__': value.getstate()}
    raise TypeError(f'unserializable engine value: {type(value).__name__}')

def same_engine_state(left, right):
    return json.dumps(left, sort_keys=True, default=_json_default, ensure_ascii=False) == json.dumps(
        right, sort_keys=True, default=_json_default, ensure_ascii=False)

def terminal_utility(outcome):
    return {'win': 1.0, 'loss': -1.0, 'draw': 0.0,
            'budget_exhausted': -1.0, 'no_legal_actions': -1.0}.get(outcome)


async def _cpu_complete(function, *args):
    """Keep CPU/file work off the loop and drain it before cancellation exits."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Repeated cancellation must not leave a file write running after the
        # episode releases its durable ownership.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()  # Retrieve a worker failure; cancellation wins.
        raise


def _settled_episode_row(job, initial, final, trace, outcome, extra,
                         reward_config, model_url, started):
    """Pure terminal accounting; no physics, inference, replay or shared state."""
    utility = terminal_utility(outcome)
    if utility is None:
        raise ValueError(f'unknown outcome {outcome!r}')
    realtime_score = None
    if job['kind'] in REALTIME_KINDS:
        realtime_score = score_episode(job['kind'], final, outcome,
                                       elapsed_seconds=extra.get('real_time_seconds'))
    utility = terminal_objective(job['kind'], outcome, realtime_score)
    reward = settle_episode(job['kind'], initial, trace, utility, reward_config,
                            final_state=final)
    if not math.isfinite(utility):
        raise ValueError('nonfinite utility')
    row = {**job, **extra, 'status': 'complete' if extra.get('status','complete')=='complete' else 'error', 'initial_state': initial,
           'final_state': final, 'trace': trace, 'outcome': outcome,
           **reward,
           'decisions': len(trace),
           'trainable_decisions': sum(not t['policy']['forced'] for t in trace),
           'forced_actions': sum(t['policy']['forced'] for t in trace)
                             + int(extra.get('deterministic_student_actions', 0)),
           'policy_origin':'student' if model_url else 'teacher',
           'on_policy':bool(model_url) and extra.get('status','complete')=='complete' and all(t['policy'].get('forced') or t['policy'].get('origin')=='student_model' for t in trace),
           'rule_takeover_count':int(extra.get('rule_takeover_count',0))+sum(bool(t['policy'].get('C_takeover')) or t['policy'].get('origin')=='C' for t in trace),
           'replay_verified': True, 'seconds': round(time.monotonic() - started, 3)}
    if realtime_score is not None:
        row.update(realtime_score=realtime_score, scoring_revision=SCORING_REVISION,
                   terminal_score=utility)
    return row


def _read_complete_episode(path, kind, reward_config):
    previous = read(path)
    if previous.get('status') == 'complete':
        validate_reward_episode(previous, reward_config)
        if kind in REALTIME_KINDS and previous.get('scoring_revision') != SCORING_REVISION:
            raise ValueError('realtime scoring protocol changed; use a new rollout directory')
    return previous


class EngineEpisodeRunner:
    """Reuse these methods with policy_action, qwen and journal callbacks."""

    async def board_episode(self, job):
        kind, seed, side, mode = (job[k] for k in ('kind', 'seed', 'side', 'mode'))
        engine = get_engine(kind)
        game = engine.reset(seed)
        opening_actions = game['_initialization']['actions']
        initial = copy.deepcopy(game)
        trace, all_actions = [], []
        rule_exploration = 0.
        for ordinal in range(LIMITS[kind]):
            if engine.outcome(game, side) or not engine.legal_actions(game):
                break
            record = engine.observe(game)
            options = list(record['questions']['decision']['criteria'])
            if game['turn'] == side:
                action, details = await self.policy_action(record, job['episode_id'], ordinal)
                self.journal(job, 'decision', {'ordinal':ordinal, 'record':record,
                                               'action':action, 'policy':details})
                trace.append({'ordinal': ordinal, 'record': record, 'action': action,
                              'before_state': copy.deepcopy(game), 'policy': details})
            elif mode == 'qwen3.8-max':
                action, _ = await self.qwen(kind, seed, ordinal, record)
            else:
                trial_rng = random.Random(f'rl-rule-curriculum/{kind}/{seed}/{ordinal}')
                action = (trial_rng.choice(options) if trial_rng.random() < rule_exploration
                          else board_bot.choose(game, options, seed, ordinal))
            if action not in options:
                raise ValueError('illegal board action')
            all_actions.append(action)
            game = engine.step(game, action)
            if trace and trace[-1]['ordinal'] == ordinal:
                trace[-1]['after_state'] = copy.deepcopy(game)
                self.journal(job, 'executed', trace[-1])
        outcome = engine.outcome(game, side) or 'budget_exhausted'
        return initial, game, trace, outcome, {'opening_plies': len(opening_actions),
            'opening_actions': opening_actions, 'all_turn_actions': all_actions,
            'opponent': mode, 'rule_random_fraction': rule_exploration if mode == 'rule_engine' else 0.}

    async def python_episode(self, job):
        kind, seed, mode, side = (job[k] for k in ('kind', 'seed', 'mode', 'side'))
        engine = get_engine(kind)
        if engine.rl_runner:
            return await _runner(engine.rl_runner)(self, job)
        if kind in social.SCENES or kind in probability.SCENES:
            import sys
            import jev_game_seat_control as seat_control
            return await seat_control.play(self, sys.modules[__name__], job,
                transitions=bool(getattr(self.args, 'model_url', None)))
        use_agent = kind in agent.SCENES
        game = fresh(kind, seed, 'human' if use_agent else 'rule')
        initial = copy.deepcopy(game)
        trace, events = [], []
        qwen_calls = 0
        deterministic_student_actions = deterministic_opponent_actions = 0
        for ordinal in range(engine.limit):
            if use_agent and game.get('handoff'):
                game = agent.reveal(game)
                events.append({'type': 'reveal', 'after_state': copy.deepcopy(game)})
            visible = engine.public(game)
            if engine.outcome(game):
                break
            opts = choices(game)
            if not opts:
                break
            is_opponent = use_agent and agent.actor(game) != side
            if len(opts) == 1:
                # A sole legal continuation is mechanical execution (B), not a
                # model Choice or rule-policy takeover. Some native record
                # builders intentionally reject fewer than two candidates.
                action = next(iter(opts))
                actor = agent.actor(game) if use_agent else 0
                game = await asyncio.to_thread(step, game, action) if use_agent else step(game, action)
                events.append({'type': 'deterministic', 'action': action,
                               'actor': actor, 'execution_origin': 'B',
                               'after_state': copy.deepcopy(game)})
                deterministic_student_actions += not is_opponent
                deterministic_opponent_actions += is_opponent
                self.journal(job, 'deterministic_execution', events[-1])
                continue
            record = as_record(game)
            if is_opponent:
                if mode=='qwen3.8-max':
                    action, meta = await self.qwen(kind, seed, ordinal, record)
                    qwen_calls += not meta.get('forced', False)
                else:
                    action=agent.rule_action(game,agent.actor(game))
                game = await asyncio.to_thread(step, game, action)
                events.append({'type': 'opponent', 'action': action, 'record': record,
                               'after_state': copy.deepcopy(game)})
                continue
            action, details = await self.policy_action(record, job['episode_id'], ordinal)
            self.journal(job, 'decision', {'ordinal':ordinal, 'record':record,
                                           'action':action, 'policy':details})
            before = copy.deepcopy(game)
            responses = []
            if not use_agent and mode == 'qwen3.8-max' and (kind in social.SCENES or kind in probability.SCENES):
                async def choose_opponent(opponent_record, substep):
                    # Some opponent observations reference mutable engine
                    # dictionaries (for example, property owners and cash).
                    # Capture the exact public context before the engine
                    # applies the opponent's choice.
                    observed = copy.deepcopy(opponent_record)
                    chosen, _ = await self.qwen(kind, seed, substep, opponent_record)
                    responses.append({'record': observed, 'ordinal': substep, 'action': chosen})
                    return chosen
                game, used = await social_opponents.step(game, action, choose_opponent)
                qwen_calls += used
            else:
                game = await asyncio.to_thread(step, game, action) if use_agent else step(game, action)
            trace.append({'ordinal': ordinal, 'record': record, 'action': action,
                          'before_state': before, 'after_state': copy.deepcopy(game), 'policy': details})
            self.journal(job, 'executed', trace[-1])
            events.append({'type': 'policy', 'action': action, 'record': record,
                           'opponent_responses': responses,
                           'used_social_opponent': bool(not use_agent and mode == 'qwen3.8-max' and
                                                        (kind in social.SCENES or kind in probability.SCENES)),
                           'after_state': copy.deepcopy(game)})
        visible = engine.public(game)
        outcome = engine.outcome(game) or 'budget_exhausted'
        if use_agent and side == 1:
            outcome = {'win': 'loss', 'loss': 'win'}.get(outcome, outcome)
        return initial, game, trace, outcome, {'qwen_calls': qwen_calls,
            'events': events, 'opponent': mode,
            'deterministic_student_actions': deterministic_student_actions,
            'deterministic_opponent_actions': deterministic_opponent_actions}

    async def verify_python_replay(self, job, initial, final, extra, trace=None):
        engine = get_engine(job['kind'], initial)
        if engine.rl_verify:
            verifier = _runner(engine.rl_verify)
            kwargs = {'trace': trace} if 'trace' in inspect.signature(verifier).parameters else {}
            result = verifier(job, initial, final, extra, **kwargs)
            return await result if inspect.isawaitable(result) else result
        if extra.get('native_social_actor_control'):
            import sys
            import jev_game_seat_control as seat_control
            return await seat_control.replay(sys.modules[__name__], job, initial, final, extra)
        game = fresh(job['kind'], job['seed'], 'human' if job['kind'] in agent.SCENES else 'rule')
        if not same_engine_state(game, initial):
            raise ValueError('python engine initial state did not replay')
        for event in extra['events']:
            if event['type'] == 'reveal':
                game = agent.reveal(game)
            elif event['type'] == 'deterministic':
                options = choices(game)
                actor = agent.actor(game) if job['kind'] in agent.SCENES else 0
                if (len(options) != 1 or event['action'] != next(iter(options))
                        or event.get('actor') != actor or event.get('execution_origin') != 'B'):
                    raise ValueError('deterministic execution is not the sole legal action')
                game = await asyncio.to_thread(step, game, event['action']) if job['kind'] in agent.SCENES else step(game, event['action'])
            elif event['type'] == 'opponent':
                if as_record(game) != event['record']:
                    raise ValueError('opponent public record did not replay')
                game = await asyncio.to_thread(step, game, event['action'])
            elif event['type'] == 'policy':
                if as_record(game) != event['record']:
                    raise ValueError('policy public record did not replay')
                responses = iter(event['opponent_responses'])
                if event['used_social_opponent']:
                    async def choose(record, ordinal):
                        saved = next(responses)
                        if saved['record'] != record or saved['ordinal'] != ordinal:
                            raise ValueError('opponent decision context changed on replay')
                        return saved['action']
                    game, _ = await social_opponents.step(game, event['action'], choose)
                    if next(responses, None) is not None:
                        raise ValueError('unused Qwen opponent decision')
                else:
                    game = await asyncio.to_thread(step, game, event['action']) if job['kind'] in agent.SCENES else step(game, event['action'])
            else:
                raise ValueError('unknown replay event')
            if not same_engine_state(game, event['after_state']):
                raise ValueError('python engine state diverged on exact replay')
        if not same_engine_state(game, final):
            raise ValueError('python final state diverged on exact replay')

    def verify_board_replay(self, job, initial, final, extra, trace):
        engine = get_engine(job['kind'], initial)
        game = engine.reset(job['seed'])
        if game['_initialization']['actions'] != extra['opening_actions']:
            raise ValueError('board initialization actions changed on replay')
        if not same_engine_state(game, initial):
            raise ValueError('board opening did not replay')
        cursor = 0
        for ordinal, action in enumerate(extra['all_turn_actions']):
            if cursor < len(trace) and trace[cursor]['ordinal'] == ordinal:
                if not same_engine_state(game, trace[cursor]['before_state']) or engine.observe(game) != trace[cursor]['record']:
                    raise ValueError('board policy observation changed on replay')
            game = engine.step(game, action)
            if cursor < len(trace) and trace[cursor]['ordinal'] == ordinal:
                if not same_engine_state(game, trace[cursor]['after_state']):
                    raise ValueError('board policy action changed on replay')
                cursor += 1
        if cursor != len(trace) or not same_engine_state(game, final):
            raise ValueError('board final state diverged on exact replay')

    async def verify_world_replay(self, job, initial, final, trace, extra):
        engine = get_engine(job['kind'], initial)
        if not engine.rl_verify:
            raise ValueError('browser engine must provide an exact replay verifier')
        await _runner(engine.rl_verify)(self, job, initial, final, extra, trace)

    async def world_episode(self, job):
        engine = get_engine(job['kind'])
        if not engine.rl_runner:
            raise ValueError('browser engine must provide a realtime rollout runner')
        return await _runner(engine.rl_runner)(self, job)

    async def episode(self, job):
        path = Path(self.args.out) / 'episodes' / f"{job['episode_id']}.json"
        if path.exists():
            previous = await _cpu_complete(_read_complete_episode, path, job['kind'], self.args.reward_config)
            if previous.get('status') == 'complete':
                return previous
            attempt = Path(self.args.out) / 'attempts' / f"{job['episode_id']}-{int(time.time() * 1000)}.json"
            await _cpu_complete(write, attempt, previous)
        started = time.monotonic()
        self.journal(job, 'attempt_started', {'job':job})
        try:
            engine = get_engine(job['kind'])
            initial, final, trace, outcome, extra = await (
                self.board_episode(job) if engine.family == 'board' else
                self.world_episode(job) if engine.backend == 'browser' else
                self.python_episode(job))
            if engine.family == 'board':
                self.verify_board_replay(job, initial, final, extra, trace)
            elif engine.backend == 'browser':
                await self.verify_world_replay(job, initial, final, trace, extra)
            else:
                if engine.family == 'world' and engine.backend == 'worker':
                    from jev_world_realtime_rl import rebuild_credit
                    rebuilt, credit = rebuild_credit(job['kind'], initial, trace, final, extra['replay_events'])
                    if rebuilt != trace or any(extra.get(k) != value for k, value in credit.items()):
                        raise ValueError('world_executed_credit_did_not_replay')
                await self.verify_python_replay(job, initial, final, extra, trace)
            row = await _cpu_complete(_settled_episode_row, job, initial, final,
                trace, outcome, extra, self.args.reward_config, self.args.model_url, started)
        except Exception as exc:
            row = {**job, 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'[:500],
                   'seconds': round(time.monotonic() - started, 3)}
        await _cpu_complete(write, path, row)
        self.journal(job, 'attempt_finished', {k:row.get(k) for k in ('status','outcome','error','seconds')})
        return row
