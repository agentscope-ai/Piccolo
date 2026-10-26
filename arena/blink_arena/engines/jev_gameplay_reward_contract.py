"""Executed rewards shared by frontend engines and RL.

Potential differences close at every endpoint. Terra additionally has explicit
survival costs and small, capped progression rewards; these are separate from
the native terminal result and never inferred from a proposed/model action.
"""
from __future__ import annotations

import math

REVISION = 'game-executed-safe-milestones-growth-v4'
LEGACY_REVISION = 'game-executed-survival-growth-v3'
DISCOUNT = 1.0
SHAPED_GAMES = frozenset(('mario_platformer', 'terraria_survival', 'racing_sprint',
                          'snake_navigation', 'tetris_placement', 'sokoban_puzzle'))
COMPLETION_GAMES = frozenset(('mario_platformer',))
TERRA_EVENTS = {'death_cost_limit': .8, 'death_cost_scale': 4., 'ore_reward': .001, 'ore_cap': 20,
                'kill_reward': .002, 'kill_cap': 10,
                'upgrade_reward': .005, 'upgrade_cap': 12}
MARIO_EVENTS = {'safe_crossing_reward': .02, 'safe_crossing_cap': 10}
LEGACY_TERRA_EVENTS = {'death_cost': .25, 'ore_reward': .001, 'ore_cap': 20,
                       'kill_reward': .002, 'kill_cap': 10,
                       'upgrade_reward': .005, 'upgrade_cap': 12}


def _terminal_mode(kind):
    return ('completion_time' if kind in COMPLETION_GAMES else
            'completion_progress_time' if kind in ('racing_sprint', 'snake_navigation', 'tetris_placement') else 'win_draw_loss')


def default_config(games):
    return {'revision': REVISION, 'discount': DISCOUNT,
            'games': {kind: {'mode': 'potential' if kind in SHAPED_GAMES else 'terminal',
                             'weight': .2 if kind in SHAPED_GAMES else 0.,
                             'terminal': _terminal_mode(kind),
                             **({'events': dict(TERRA_EVENTS)} if kind == 'terraria_survival' else
                                {'events': dict(MARIO_EVENTS)} if kind == 'mario_platformer' else {})}
                      for kind in games}}


def validate_config(config, games):
    if (config.get('revision') not in (REVISION, LEGACY_REVISION) or type(config.get('discount')) not in (int, float)
            or config['discount'] != DISCOUNT or set(config.get('games', {})) != set(games)):
        raise ValueError('reward config must bind every game and undiscounted terminal objective')
    for kind, setting in config['games'].items():
        legacy = config['revision'] == LEGACY_REVISION
        if setting.get('events') != ((LEGACY_TERRA_EVENTS if legacy else TERRA_EVENTS)
                                     if kind == 'terraria_survival' else
                                     MARIO_EVENTS if kind == 'mario_platformer' and not legacy else None):
            raise ValueError('executed progression reward config differs: ' + kind)
        if setting.get('terminal') != _terminal_mode(kind):
            raise ValueError('terminal reward differs from the verified game objective: ' + kind)
        weight = setting.get('weight')
        if type(weight) not in (int, float) or not math.isfinite(weight):
            raise ValueError('nonfinite reward weight: ' + kind)
        if setting.get('mode') == 'terminal' and weight == 0.:
            continue
        if setting.get('mode') != 'potential' or kind not in SHAPED_GAMES or not 0 < weight <= .25:
            raise ValueError('unsupported or unbounded process reward: ' + kind)
    return config


def terminal_objective(kind, outcome, realtime_score=None):
    """World x alone is not proof of goal progress: require the native finish.

    Race distance, Snake apples and Tetris cleared lines remain meaningful
    partial objectives. Completion speed uses the same time term as Arena.
    """
    # Terra's new objective is the native guardian-gated finish. Speed must
    # not make deliberate death/respawn worth more than a safe completion.
    if kind == 'terraria_survival':
        return 1. if outcome == 'win' else -1.
    if kind in COMPLETION_GAMES and outcome != 'win':
        return -1.
    if _terminal_mode(kind) != 'win_draw_loss':
        if realtime_score is None or bool(realtime_score['completed']) != (outcome == 'win'):
            raise ValueError('missing or inconsistent measured-time terminal score')
        return _number(realtime_score['terminal_reward'])
    return {'win': 1., 'loss': -1., 'draw': 0.,
            'budget_exhausted': -1., 'no_legal_actions': -1.}[outcome]


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('missing or nonfinite executed reward state')
    return float(value)


def _unit(value):
    return max(0., min(1., _number(value)))


def _surface_progress(state, initial):
    """Visible surface navigation; ore, equipment, kills and respawns pay nothing.

    A stale surface at another column is not proof of a surface route. Use
    currently visible grass within three columns; approaching the observed gate
    also supplies a local vertical reference. Unknown geometry earns no bonus.
    """
    player = state['player']
    if player.get('respawning') or _number(player['hp']) <= 0:
        return 0.
    x, y = _number(player['x']), _number(player['y'])
    height = _number(player['height'])
    start_x = _number(initial['player']['x'])
    progress = _unit((x - start_x) / max(1., 237. - start_x))
    goal = state.get('known_goal')
    if goal is not None:
        gx, gy = map(_number, goal)
        # The gate is a spatial target, not a horizontal coordinate to overshoot.
        distance = math.hypot(x + _number(player['width']) / 2 - gx - .5,
                              y + height / 2 - gy - .5)
        return .8 * progress / (1. + abs(y + height / 2 - gy - .5)) + .2 / (1. + distance)
    world = state['map']
    ox, oy = world['origin']
    surfaces = [oy + row for row, cells in enumerate(world['tiles'])
                for col, tile in enumerate(cells) if tile == 2 and abs(ox + col - x) <= 3]
    if not surfaces:
        return 0.
    depth = min(abs(y + height - surface) for surface in surfaces)
    return progress * max(0., 1. - depth / 4.)


def unit_potential(kind, state, initial):
    """Only executed, public state; never a proposed move or hidden future seed."""
    if kind == 'mario_platformer':
        # Airborne distance is not a completed crossing. Grounding is supplied
        # by native collision physics, not by a model's statement of success.
        return _unit(_number(state['progress']) / 100.) if state['player']['on_ground'] else 0.
    if kind == 'terraria_survival':
        # Moving toward the gate cannot substitute for defeating its guardian.
        return (_unit(_surface_progress(state, initial))
                if state.get('objective', {}).get('gate_unlocked') else 0.)
    if kind == 'racing_sprint':
        # Damage and distance are already reflected in completion and time.
        # Do not pay for steering, speed, braking or merely staying alive.
        return _unit(_number(state['z']) / _number(state.get('finish_distance', 900.)))
    if kind == 'snake_navigation':
        target = _number(state['food_target'])
        if target <= 0:
            raise ValueError('invalid snake food target')
        return _unit(_number(state['score']) / target)
    if kind == 'tetris_placement':
        from jev_showcase_games import metrics
        board = state['board']
        holes, _, bump = metrics(board)
        h, w = len(board), len(board[0])
        maximum = max(h - next((y for y, row in enumerate(board) if row[x]), h) for x in range(w))
        # Clearing four lines is the actual objective. Geometry is a small
        # survival estimate, settled back even when the episode is truncated.
        health = 1. - min(1., holes / 10. + maximum / h + bump / (h * w))
        target = _number(state.get('line_target', 4.))
        if target <= 0:
            raise ValueError('invalid tetris line target')
        return .8 * _unit(_number(state['lines']) / target) + .2 * health
    if kind == 'sokoban_puzzle':
        from jev_showcase_games import sokoban_distance
        # Reuse the tiny public-board solver already used by the engine to
        # detect deadlocks. Manhattan distance rewards pushing into walls.
        distance = sokoban_distance(state)
        remaining = max(0., 80. - _number(state['steps']))
        if distance is None or distance > remaining:
            return 0.
        return 1. / (1. + distance / 10.)
    return 0.


def potential(kind, state, initial, weight=.2):
    return weight * unit_potential(kind, state, initial)


def _states(row):
    if ('credit_before_state' in row) != ('credit_after_state' in row):
        raise ValueError('incomplete executed credit interval')
    return (row.get('credit_before_state', row['before_state']),
            row.get('credit_after_state', row['after_state']))


def _terminal(kind, state, initial):
    return bool(state.get('outcome')) or (kind == 'terraria_survival' and
                                         state.get('wins', 0) > initial.get('wins', 0))


def potential_rewards(kind, initial, trace, config=None):
    config = config if config is not None else default_config([kind])
    validate_config(config, config['games'])
    setting = config['games'][kind]
    if setting['mode'] == 'terminal' or not trace:
        return [0.] * len(trace)
    before, _ = _states(trace[0])
    # The first *applied* action owns the interval. Physics while waiting for
    # the first response is unowned and must not become a synthetic reward.
    origin = potential(kind, before, initial, setting['weight'])
    previous = origin
    result = []
    for index, row in enumerate(trace):
        before, after = _states(row)
        old = potential(kind, before, initial, setting['weight'])
        if not math.isclose(old, previous, abs_tol=1e-10, rel_tol=0.):
            raise ValueError('discontinuous executed process credit')
        terminal = _terminal(kind, after, initial)
        if terminal and index != len(trace) - 1:
            raise ValueError('process credit after engine termination')
        # Every endpoint, including timeout/error/budget exhaustion, absorbs.
        # The centered absorbing potential is zero (uncentered: origin).
        newer = origin if index == len(trace) - 1 else potential(kind, after, initial, setting['weight'])
        result.append(newer - old)
        previous = newer
    if not math.isclose(math.fsum(result), 0., abs_tol=1e-10):
        raise ValueError('process rewards changed the terminal objective')
    return result


def _terra_counters(state):
    progression = state.get('progression', {})
    values = {}
    for name in ('ore_mined', 'ordinary_player_kills', 'death_count', 'respawn_count'):
        value = progression.get(name)
        if type(value) is not int or value < 0:
            raise ValueError('missing executed Terra progression: ' + name)
        values[name] = value
    if values['death_count'] != state.get('deaths'):
        raise ValueError('Terra death counter differs from native state')
    gear = state.get('equipment', {})
    for name in ('pick', 'sword', 'armor'):
        value = gear.get(name)
        if type(value) is not int or value < 0:
            raise ValueError('missing executed Terra equipment: ' + name)
        values[name] = value
    return values


def terra_death_cost(deaths):
    """Strictly increasing bounded cost; no death-count threshold is free.

    The native terminal is still +/-1. A cost below .8 and growth at most .1
    guarantee every successful episode outranks every failed episode. Deaths,
    respawns and lost equipment remain fully visible in the native ledger.
    """
    if type(deaths) is not int or deaths < 0:
        raise ValueError('invalid executed Terra death count')
    return TERRA_EVENTS['death_cost_limit'] * deaths / (deaths + TERRA_EVENTS['death_cost_scale'])


def _death_cost_increment(before, after):
    # Algebraically C(after)-C(before), avoiding subtractive cancellation at
    # large counters. Every additional native death has a positive cost.
    if type(before) is not int or type(after) is not int or not 0 <= before <= after:
        raise ValueError('invalid executed Terra death interval')
    scale = TERRA_EVENTS['death_cost_scale']
    return (TERRA_EVENTS['death_cost_limit'] * scale * (after - before)
            / ((before + scale) * (after + scale)))


def _mario_events(state):
    events = state.get('progress_events', [])
    if not isinstance(events, list):
        raise ValueError('invalid executed Mario milestone history')
    result = {}
    for event in events:
        if (not isinstance(event, dict) or
                event.get('kind') not in ('safe_obstacle_crossing', 'safe_gap_crossing') or
                not isinstance(event.get('id'), str) or not 0 < len(event['id']) <= 160 or
                event.get('landing_on_ground') is not True or
                type(event.get('frame')) is not int or event['frame'] < 0):
            raise ValueError('unproved executed Mario safe crossing')
        _number(event.get('x'))
        # Duplicate delivery is harmless, but an ID cannot change its evidence.
        proof = {key: event[key] for key in ('id', 'kind', 'frame', 'x', 'landing_on_ground')}
        if event['id'] in result and result[event['id']] != proof:
            raise ValueError('Mario milestone identity changed')
        result[event['id']] = proof
    return result


def mario_event_rewards(initial, trace, final_state=None):
    """Only native, once-only, safe landed crossings pay; old views pay zero."""
    origin = _mario_events(initial)
    previous = dict(origin)

    def advance(state):
        nonlocal previous
        current = _mario_events(state)
        if any(current.get(key) != value for key, value in previous.items()):
            raise ValueError('Mario milestone history reset or changed')
        old_count = min(MARIO_EVENTS['safe_crossing_cap'], len(previous.keys() - origin.keys()))
        new_count = min(MARIO_EVENTS['safe_crossing_cap'], len(current.keys() - origin.keys()))
        previous = current
        return {'safe_crossing': MARIO_EVENTS['safe_crossing_reward'] * (new_count - old_count)}

    first = _states(trace[0])[0] if trace else (final_state or initial)
    unowned = advance(first)
    owned = []
    for row in trace:
        before, after = _states(row)
        if _mario_events(before) != previous:
            raise ValueError('discontinuous executed Mario milestone credit')
        owned.append(advance(after))
    if final_state is not None and _mario_events(final_state) != previous:
        raise ValueError('Mario final state differs from milestone endpoint')
    return owned, unowned


def terra_event_rewards(initial, trace, final_state=None, *, legacy=False):
    """High-water growth and bounded monotone survival cost, paid by deltas.

    The initial wait has no applied model action. Account for its events in
    the episode ledger, but do not assign those costs/bonuses to a later action.
    Its growth still consumes the same episode caps, including after respawn.
    """
    origin = _terra_counters(initial)
    previous = dict(origin)
    high = dict(origin)

    def advance(state):
        nonlocal previous
        now = _terra_counters(state)
        for key in ('ore_mined', 'ordinary_player_kills', 'death_count', 'respawn_count'):
            if now[key] < previous[key]:
                raise ValueError('Terra progression counter reset during episode: ' + key)
        old = dict(high)
        for key in high:
            high[key] = max(high[key], now[key])
        def capped(name, cap, values):
            return min(cap, values[name] - origin[name])
        def levels(values):
            return min(TERRA_EVENTS['upgrade_cap'], sum(values[k] - origin[k]
                       for k in ('pick', 'sword', 'armor')))
        result = {
            'death': (-LEGACY_TERRA_EVENTS['death_cost'] * (now['death_count'] - previous['death_count'])
                      if legacy else -_death_cost_increment(previous['death_count'] - origin['death_count'],
                                                            now['death_count'] - origin['death_count'])),
            'mining': TERRA_EVENTS['ore_reward'] * (capped('ore_mined', TERRA_EVENTS['ore_cap'], high)
                                                    - capped('ore_mined', TERRA_EVENTS['ore_cap'], old)),
            'combat': TERRA_EVENTS['kill_reward'] * (capped('ordinary_player_kills', TERRA_EVENTS['kill_cap'], high)
                                                      - capped('ordinary_player_kills', TERRA_EVENTS['kill_cap'], old)),
            'upgrade': TERRA_EVENTS['upgrade_reward'] * (levels(high) - levels(old)),
        }
        previous = now
        return result

    first = _states(trace[0])[0] if trace else (final_state or initial)
    unowned = advance(first)
    owned = []
    for row in trace:
        before, after = _states(row)
        if _terra_counters(before) != previous:
            raise ValueError('discontinuous executed Terra event credit')
        owned.append(advance(after))
    if final_state is not None and _terra_counters(final_state) != previous:
        raise ValueError('Terra final state differs from executed event endpoint')
    return owned, unowned


def process_rewards(kind, initial, trace, config=None):
    config = config if config is not None else default_config([kind])
    values = potential_rewards(kind, initial, trace, config)
    if kind == 'terraria_survival':
        events, _ = terra_event_rewards(initial, trace, legacy=config['revision'] == LEGACY_REVISION)
        values = [p + math.fsum(e.values()) for p, e in zip(values, events, strict=True)]
    elif kind == 'mario_platformer' and config['revision'] == REVISION:
        events, _ = mario_event_rewards(initial, trace)
        values = [p + math.fsum(e.values()) for p, e in zip(values, events, strict=True)]
    return values


def settle_episode(kind, initial, trace, terminal_objective, config=None, *, final_state=None):
    """One contract for score, RTG and audit; no separately added final bonus."""
    terminal_objective = _number(terminal_objective)
    config = config if config is not None else default_config([kind])
    potentials = potential_rewards(kind, initial, trace, config)
    events, unowned = ([{} for _ in trace], {})
    if kind == 'terraria_survival':
        events, unowned = terra_event_rewards(initial, trace, final_state,
                                              legacy=config['revision'] == LEGACY_REVISION)
        end = final_state or (_states(trace[-1])[1] if trace else initial)
        if terminal_objective == 1. and not (
                end.get('wins', 0) > initial.get('wins', 0)
                and end.get('objective', {}).get('gate_unlocked')
                and end.get('objective', {}).get('guardian_defeated_by_player')):
            raise ValueError('Terra win requires native guardian defeat and gate entry')
    elif kind == 'mario_platformer' and config['revision'] == REVISION:
        events, unowned = mario_event_rewards(initial, trace, final_state)
    rewards = [p + math.fsum(e.values()) for p, e in zip(potentials, events, strict=True)]
    event_total = math.fsum(math.fsum(e.values()) for e in events)
    unowned_total = math.fsum(unowned.values())
    training_utility = terminal_objective + math.fsum(rewards)
    closure_error = math.fsum(rewards) - event_total
    if not math.isclose(closure_error, 0., abs_tol=1e-10):
        raise ValueError('executed reward accounting does not close')
    result = {'reward_revision': config['revision'], 'reward_discount': DISCOUNT,
            'reward_setting': dict(config['games'][kind]),
            'process_rewards': rewards, 'terminal_utility': terminal_objective,
            'terminal_margin_reward': 0., 'episode_utility': training_utility + unowned_total,
            'training_utility': training_utility,
            'unowned_process_reward': unowned_total,
            'process_reward_components': [{'potential': p, **e} for p, e in zip(potentials, events, strict=True)],
            'reward_audit': {'process_sum': math.fsum(rewards),
                             'potential_sum': math.fsum(potentials),
                             'event_sum': event_total,
                             'positive_progress_total': math.fsum(e.get(k, 0.) for e in [*events, unowned]
                                                                   for k in ('mining', 'combat', 'upgrade', 'safe_crossing')),
                             'one_time_safe_crossings_count': (round(math.fsum(
                                 e.get('safe_crossing', 0.) for e in [*events, unowned]) /
                                 MARIO_EVENTS['safe_crossing_reward']) if kind == 'mario_platformer' else 0),
                             'death_cost_total': -math.fsum(e.get('death', 0.) for e in [*events, unowned]),
                             'native_deaths_total': (final_state.get('progression', {}).get('death_count', 0)
                                 - initial.get('progression', {}).get('death_count', 0)
                                 if kind == 'terraria_survival' and final_state is not None else None),
                             'unowned_events': unowned,
                             'max_abs_process_reward': max(map(abs, rewards), default=0.),
                             'terminal_objective': terminal_objective,
                             'closure_error': closure_error,
                             'absorbing_endpoint': True}}
    if config['revision'] == LEGACY_REVISION:
        # Archived receipts used this exact audit schema. New callers always
        # get v4 unless they explicitly load an unchanged v3 plan/config.
        result['reward_audit'].pop('one_time_safe_crossings_count')
        result['reward_audit'].pop('native_deaths_total')
    return result


def validate_episode(episode, config):
    """Recompute from verified states before group filtering or dataset export."""
    from jev_realtime_scoring import REALTIME_KINDS, score_episode
    if episode['kind'] in REALTIME_KINDS:
        score = score_episode(episode['kind'], episode['final_state'], episode['outcome'],
                              elapsed_seconds=episode.get('real_time_seconds'))
        if episode.get('realtime_score') != score:
            raise ValueError('realtime objective differs from executed final state')
        objective = terminal_objective(episode['kind'], episode['outcome'], score)
    else:
        objective = terminal_objective(episode['kind'], episode['outcome'])
    expected = settle_episode(episode['kind'], episode['initial_state'], episode['trace'],
                              objective, config, final_state=episode['final_state'])
    for field, value in expected.items():
        if episode.get(field) != value:
            raise ValueError('episode reward contract changed: ' + field)
