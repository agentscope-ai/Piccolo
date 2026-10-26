"""Offline playback of archived actions through unchanged frontend engines.

No predictor, server, evaluator or network client is imported. Every generated
frame is discarded unless the initial state, consumed observations/actions and
complete final state agree with the archive at the JSON boundary.
"""
import asyncio
import copy
import json
import math
from pathlib import Path
import sys

ARCADE = {'jump_jump', 'tetris_placement', 'snake_navigation', 'merge_2048', 'sokoban_puzzle'}
AGENT = {'liars_dice', 'goofspiel', 'blackjack'}
SOCIAL = {'doudizhu', 'texas_holdem', 'property_tycoon', 'zha_jin_hua', 'pig_dice'}
KINDS = ARCADE | AGENT | SOCIAL | {'chess'}


def wire(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def engines():
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import jev_demo_showcases as native
    import jev_agent_games as agent
    import jev_social_games as social
    import jev_probability_games as probability
    import jev_eval_social_opponents as opponents
    import jev_game_seat_control as seats
    return native, agent, social, probability, opponents, seats


class Actions:
    def __init__(self, row):
        self.row, self.index = row, 0

    def take(self, options, actor, record=None):
        if len(options) == 1:
            return {'action': next(iter(options)), 'actor': actor,
                    'origin': 'forced_legal', 'model_call': False}
        if self.index >= len(self.row.get('trace', [])):
            raise ValueError('archived_actions_exhausted')
        item = self.row['trace'][self.index]
        if item.get('action') not in options or item.get('actor', actor) != actor:
            raise ValueError('archived_action_mismatch')
        if record is not None and item.get('input'):
            observed = item['input'].get('state', {}).get('observation')
            if wire(record['state']['observation']) != observed:
                raise ValueError('archived_observation_mismatch')
        self.index += 1
        return copy.deepcopy(item)

    def finish(self, final):
        if self.index != len(self.row.get('trace', [])):
            raise ValueError('unconsumed_archived_actions')
        if wire(final) != self.row['final_state']:
            raise ValueError('archived_final_state_mismatch')


async def reconstruct(row):
    native, agent, social, probability, opponents, seats = engines()
    kind = row['kind']
    if kind in ('snake_navigation', 'tetris_placement'):
        # Historical archives used one movement per decision. Never pass those
        # actions through the newer live real-time factory or rewrite archives.
        if row['initial_state'].get('engine_revision'):
            raise ValueError('realtime_game_requires_clock_receipts')
        import jev_showcase_games as legacy
        from types import SimpleNamespace
        native = SimpleNamespace(fresh=lambda kind, seed, mode: legacy.fresh(kind, seed),
                                 choices=legacy.choices, step=legacy.step)
    actions, frames = Actions(row), []
    game = native.fresh(kind, row['seed'], 'human' if kind in AGENT else 'rule')

    def public(value):
        return (agent.public(value) if kind in AGENT else social.public(value) if kind in social.SCENES
                else probability.public(value) if kind in probability.SCENES else copy.deepcopy(value))

    if wire(public(game)) != row['initial_state']:
        raise ValueError('archived_initial_state_mismatch')

    if kind in ARCADE | AGENT:
        target_steps = row['final_state'].get('steps', row.get('steps'))
        if type(target_steps) is not int or not 0 <= target_steps <= 2000:
            raise ValueError('invalid_archived_step_count')
        while game['steps'] < target_steps:
            if kind in AGENT and game.get('handoff'):
                game = agent.reveal(game)
            actor = agent.actor(game) if kind in AGENT else 0
            item = actions.take(native.choices(game), actor,
                                native.as_record(game) if kind in AGENT else None)
            before = public(game)
            game = agent.step(game, item['action']) if kind in {'liars_dice', 'goofspiel'} else native.step(game, item['action'])
            frames.append({**item, 'before_state': before, 'after_state': public(game)})
    elif kind == 'doudizhu':
        adapter = type('Native', (), {'as_record': staticmethod(native.as_record),
                                     'social': social, 'social_opponents': opponents})
        for _ in range(1000):
            if game.get('outcome'):
                break
            actor = game['turn']
            record = seats.doudizhu_record(adapter, game, actor)
            item = actions.take(record['questions']['decision']['criteria'], actor, record)
            before = public(game)
            if actor == 0:
                game['steps'] += 1
            social.dzplay(game, actor, item['action'])
            if not game['outcome']:
                game['event'] = '轮到玩家'+str(game['turn'])+'出牌'
                game['score'] = 20-len(game['hands'][0])
            game['history'] = game['history'][-12:]
            frames.append({**item, 'before_state': before, 'after_state': public(game)})
    else:
        for _ in range(1000):
            if game.get('outcome'):
                break
            record = native.as_record(game)
            item = actions.take(native.choices(game), 0, record)
            outer = {**item, 'before_state': public(game)}
            frames.append(outer)
            pending = []

            async def choose(record, ordinal):
                selected = actions.take(record['questions']['decision']['criteria'], 1, record)
                pending.append(selected)
                return selected['action']

            async def observe(event):
                # The callback's pre-state is the actual state after actor 0's
                # move, before the opponent acts. It is not a predicted frame.
                if 'after_state' not in outer:
                    outer['after_state'] = public(event['before_state'])
                options = event['record']['questions']['decision']['criteria']
                selected = (actions.take(options, 1, event['record']) if len(options) == 1 else pending.pop(0))
                if selected['action'] != event['action']:
                    raise ValueError('native_callback_mismatch')
                frames.append({**selected, 'before_state': public(event['before_state']),
                               'after_state': public(event['after_state'])})

            game, _ = await opponents.step(game, item['action'], choose, post_execution_observer=observe)
            if pending:
                raise ValueError('native_callback_not_executed')
            if 'after_state' not in outer:
                outer['after_state'] = public(game)
            else:
                # Include deterministic settlement/history updates after the
                # final callback in the last frame of this original outer step.
                frames[-1]['after_state'] = public(game)
    actions.finish(public(game))
    return frames


def native_frames(row):
    if row.get('kind') not in KINDS or not row.get('initial_state') or not row.get('final_state'):
        return None
    if row['kind'] == 'chess':
        return chess_frames(row)
    if row['kind'] == 'tetris_placement' and row['initial_state'].get('engine_revision'):
        return tetris_frames(row)
    if row['kind'] == 'snake_navigation' and row['initial_state'].get('engine_revision'):
        raise ValueError('realtime_game_requires_clock_receipts')
    return asyncio.run(reconstruct(row))


def chess_frames(row):
    """Verify the full shared-core journal, including the opponent's moves."""
    from jev_chess_rl import verify_evaluation
    from jev_engine_registry import get_engine
    engine = get_engine('chess')
    job, extra, final = (row.get(key) for key in ('evaluation_job', 'evaluation_extra', 'final_engine_state'))
    if not isinstance(job, dict) or not isinstance(extra, dict) or not isinstance(final, dict):
        raise ValueError('chess_evaluation_replay_receipts_missing')
    if job.get('kind') != 'chess' or job.get('seed') != row.get('seed') or job.get('side') != row.get('model_player'):
        raise ValueError('chess_evaluation_replay_identity_mismatch')
    native_trace = row.get('native_trace', row.get('trace'))
    verify_evaluation(job, row['initial_state'], final, extra, trace=native_trace)
    if wire(engine.public(final)) != wire(row['final_state']) or extra.get('verified_outcome') != row.get('outcome'):
        raise ValueError('chess_evaluation_final_projection_mismatch')
    predictions = row.get('trace', []) if 'native_trace' in row else native_trace
    frames, index = [], 0
    for event in extra['events']:
        model_call = event['controlled'] and event['type'] == 'policy'
        detail = {}
        if model_call:
            if index >= len(predictions) or predictions[index]['action'] != event['action']:
                raise ValueError('chess_evaluation_model_action_mismatch')
            detail = {key: copy.deepcopy(predictions[index][key]) for key in
                      ('player', 'model', 'served_model', 'decision_stability', 'latency_seconds') if key in predictions[index]}
            index += 1
        frames.append({**detail, 'action': event['action'], 'actor': event['actor'],
            'origin': 'forced_legal' if event['type'] == 'deterministic' else 'model' if model_call else 'opponent',
            'model_call': model_call, 'controller': event['controller'],
            'before_state': engine.public(event['before_state']), 'after_state': engine.public(event['after_state'])})
    if index != len(predictions):
        raise ValueError('chess_evaluation_unconsumed_model_actions')
    return frames


def tetris_frames(row):
    """Rebuild every falling/lock/clear frame from verified clock receipts.

    The live trace ring is bounded. Replaying small clock intervals restores
    frames beyond that ring without predicting actions or rewriting archives.
    Only the trace ring itself is excluded from state equality checks.
    """
    import jev_tetris_realtime as game
    from jev_tetris_runtime import CLOCK_CONTRACT, discard_reason
    from jev_tetris_rl import _force_failure, idle_segments

    if not game.is_realtime(row['initial_state']) or row.get('clock_contract') != CLOCK_CONTRACT:
        raise ValueError('unsupported_tetris_clock_archive')
    events = row.get('replay_events')
    if not isinstance(events, list) or not events:
        raise ValueError('tetris_clock_receipts_missing')
    world = game.fresh(row['seed'], revision=row['initial_state'].get('engine_revision'))

    def equal(actual, saved):
        if wire(game.public(actual)) != wire(game.public(saved)):
            raise ValueError('tetris_archive_state_mismatch')

    equal(world, row['initial_state'])
    frames, requests = [], 0
    for event in events:
        snapshots = []

        def advance(seconds):
            nonlocal world
            if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                    or seconds < 0 or seconds > game.TIME_LIMIT + 60):
                raise ValueError('invalid_tetris_archived_interval')
            remaining = seconds
            while remaining > 1e-9:
                delta = min(.1, remaining)
                before = world['elapsed']
                world = game.advance_idle(world, delta)
                for saved in world['execution_trace']['frames']:
                    if saved['elapsed'] >= before:
                        frame = {**game.public(world), **copy.deepcopy(saved)}
                        if not snapshots or frame != snapshots[-1]:
                            snapshots.append(frame)
                remaining = round(remaining - delta, 9)
                if world['outcome'] or not world['started']:
                    break

        advance(event.get('pre_decision_seconds', 0.))
        equal(world, event['before_state'])
        before = copy.deepcopy(world)
        if event.get('no_request'):
            if event.get('action_applied') or any(event.get(k) is not None for k in ('action','record','policy')):
                raise ValueError('tetris_archived_action_ownership_mismatch')
            if event['ordinal'] != requests:
                raise ValueError('tetris_archived_nondecision_ordinal_mismatch')
            for index, (pre_seconds, wait_seconds) in enumerate(idle_segments(event)):
                if index:
                    advance(pre_seconds)
                if game.needs_decision(world):
                    raise ValueError('tetris_missing_archived_request')
                if game.persistent(world) and event.get('no_request_reason') != game.decision_reason(world):
                    raise ValueError('tetris_archived_nondecision_event_mismatch')
                advance(wait_seconds)
        else:
            if not game.needs_decision(world) or event['ordinal'] != requests or wire(game.as_record(world)) != wire(event['record']):
                raise ValueError('tetris_archived_observation_mismatch')
            requests += 1
            advance(event['waiting_seconds'])
            equal(world, event['arrival_state'])
            reason = discard_reason(before, world, event['action'])
            applied = not event.get('error_type') and reason is None
            if event['action_applied'] != applied or event.get('reason') != reason:
                raise ValueError('tetris_archived_action_ownership_mismatch')
            terminal_at_arrival = bool(world['outcome'])
            if applied:
                world = game.step(world, event['action'])
                # Include same-clock hard-drop, lock and spawn transitions.
                for saved in world['execution_trace']['frames']:
                    if saved['elapsed'] == world['elapsed']:
                        snapshots.append({**game.public(world), **copy.deepcopy(saved)})
            advance(event['post_action_seconds'])
            if event.get('error_type') and not terminal_at_arrival:
                world = _force_failure(world, 'model_timeout' if event['status'] == 'timeout' else 'model_error')
        equal(world, event['after_state'])
        frames.append({**event, 'before_state': before, 'after_state': copy.deepcopy(world),
                       'execution_frames': snapshots, 'execution': event})
    if not world['outcome'] and requests >= row.get('decision_limit', game.LIMIT):
        world.update(outcome='loss', event='策略预算耗尽', failure_reason='decision_budget_exhausted')
    equal(world, row['final_state'])
    if frames:
        frames[-1]['after_state'] = copy.deepcopy(world)
    return frames


def partial_doudizhu(row):
    """Recover only a prefix witnessed by the next saved actor observation.

    The final saved prediction has no execution receipt. Its pre-state may be
    shown, but no action effect or terminal state is invented for that decision.
    """
    if (row.get('kind') != 'doudizhu' or row.get('status') != 'error'
            or not row.get('trace') or row.get('final_state')):
        return None
    native, _, social, _, opponents, seats = engines()
    game = native.fresh('doudizhu', row['seed'], 'rule')
    initial = social.public(game)
    actions, frames = Actions(row), []
    adapter = type('Native', (), {'as_record': staticmethod(native.as_record),
                                 'social': social, 'social_opponents': opponents})
    for _ in range(1000):
        actor = game['turn']
        record = seats.doudizhu_record(adapter, game, actor)
        item = actions.take(record['questions']['decision']['criteria'], actor, record)
        frame = {**item, 'before_state': social.public(game)}
        frames.append(frame)
        if actions.index == len(row['trace']):
            return {'initial_state': initial, 'steps': frames}
        if actor == 0:
            game['steps'] += 1
        social.dzplay(game, actor, item['action'])
        if not game['outcome']:
            game['event'] = '轮到玩家'+str(game['turn'])+'出牌'
            game['score'] = 20-len(game['hands'][0])
        game['history'] = game['history'][-12:]
        frame['after_state'] = social.public(game)
        if game.get('outcome'):
            raise ValueError('partial_archive_has_unrecorded_terminal')
    raise ValueError('partial_replay_step_limit')
