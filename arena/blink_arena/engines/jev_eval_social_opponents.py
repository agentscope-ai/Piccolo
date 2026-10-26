"""Qwen-controlled opponent turns for existing card, property and dice engines.

The ordinary frontend engines keep their tested rule opponents. This adapter
only replaces an opponent's actionable choice during an eight-game evaluation;
chance events, legal actions and terminal settlement stay in the same engines.
"""
from __future__ import annotations

import copy
import json
import random

import jev_probability_games as probability
import jev_social_games as social


def _record(kind, role, rules, observation, options, prompt):
    # Match the frontend JSON boundary for native tuples and numeric map keys.
    observation = json.loads(json.dumps(observation, ensure_ascii=False, allow_nan=False))
    record = {'schema_version': 'jev.training.v1', 'id': f'opponent-{kind}',
            'group_id': f'opponent-{kind}',
            'state': {'role': role, 'rules': rules, 'observation': observation},
            'questions': {'decision': {'type': 'choice', 'instructions': prompt,
                'criteria': options, 'option_order': list(options)}},
            'labels': {},
            'provenance': {'data_source': 'cues_live_opponent_eval', 'source_id': 'live', 'source_split': 'eval'},
            'metadata': {'domain': 'games', 'sub_domain': kind, 'scenario': 'opponent_control'}}
    from jev_game_prompt_calibration import apply as calibrate_prompt
    return calibrate_prompt(record)


async def _ask(chooser, record, ordinal):
    options = record['questions']['decision']['criteria']
    if len(options) == 1:
        return next(iter(options)), 0
    action = await chooser(record, ordinal)
    if action not in options:
        raise ValueError('Qwen opponent returned an illegal action')
    return action, 1


def _observer_before(observer, game, record, execution=None):
    if observer is None:
        return None
    # Neither an observer nor later mutable engine dictionaries can change
    # the exact input that was passed to the actor's policy.
    return {'state': copy.deepcopy(game), 'record': copy.deepcopy(record),
            'execution': copy.deepcopy(execution)}


async def _observer_after(observer, before, game, actor, ordinal, action, execution=None):
    if observer is None:
        return
    await observer({'actor': actor, 'ordinal': ordinal, 'action': action,
        'record': before['record'], 'before_state': before['state'],
        'after_state': copy.deepcopy(game),
        'execution_before': before['execution'], 'execution_after': copy.deepcopy(execution),
        'source': 'original_native_actor_execution'})


async def _doudizhu(game, action, chooser, post_execution_observer=None):
    game = copy.deepcopy(game)
    game['steps'] += 1
    social.dzplay(game, 0, action)
    calls = 0
    for substep in range(2):
        if game['outcome'] or game['turn'] == 0:
            break
        side = game['turn']
        candidates = social.dzoptions(game, side)
        options = {key: '不出／过牌' if pattern is None else social.dzname(pattern[3])
                   for key, pattern in candidates.items()}
        observation = {'hand': list(game['hands'][side]),
            'other_hand_counts': {str(i): len(game['hands'][i]) for i in range(3) if i != side},
            'last_play': game['last'], 'leader': game['leader'], 'turn': side,
            'history': game['history'][-8:]}
        record = _record('doudizhu', f'你是农民{side}，与另一名农民合作对抗地主0',
            '标准斗地主出牌、跟牌、炸弹和火箭规则；只能使用自己的手牌和公开历史。',
            observation, options,
            '尽量比地主更早出完团队手牌；根据可见组合与对手剩牌决策，不能假设隐藏手牌。只输出合法动作 ID。')
        before = _observer_before(post_execution_observer, game, record)
        chosen, used = await _ask(chooser, record, game['steps'] * 100 + substep)
        calls += used
        social.dzplay(game, side, chosen)
        await _observer_after(post_execution_observer, before, game, side,
                              game['steps'] * 100 + substep, chosen)
    if not game['outcome']:
        game['event'] = '轮到你出牌'
        game['score'] = 20 - len(game['hands'][0])
    game['history'] = game['history'][-12:]
    return game, calls


async def _texas(game, action, chooser, post_execution_observer=None):
    game = copy.deepcopy(game)
    game['steps'] += 1
    rng = random.Random(f"{game['seed']}/{game['steps']}")
    if action == 'fold':
        game['outcome'] = 'loss'
        game['stacks'][1] += game['pot']
        game['event'] = '你弃牌，对手赢下底池。'
        return game, 0
    amount = min(game['to_call'] + (40 if action == 'raise' else 0),
                 game['stacks'][0], game['stacks'][1] + game['to_call'])
    game['stacks'][0] -= amount
    game['pot'] += amount
    if action == 'raise':
        pay = min(40, game['stacks'][1])
        game['stacks'][1] -= pay
        game['pot'] += pay
    draw = 3 if not game['board'] else 1 if len(game['board']) < 5 else 0
    game['board'] += game['deck'][:draw]
    game['deck'] = game['deck'][draw:]
    game['street'] += 1
    if len(game['board']) >= 5 and game['street'] >= 4:
        social.settle(game)
        return game, 0
    options = {'check': '过牌'}
    options.update({f'bet{amount}': f'下注 {amount}' for amount in (10, 20, 40)
                    if amount <= min(game['stacks'])})
    observation = {'own_hand': list(game['hands'][1]), 'board': list(game['board']),
                   'pot': game['pot'], 'own_stack': game['stacks'][1],
                   'player_stack': game['stacks'][0], 'street': game['street'],
                   'player_last_action': action,
                   'card_encoding': '0..12=♠2..A,13..25=♥2..A,26..38=♣2..A,39..51=♦2..A'}
    observation['equity_estimate'] = social.equity({'hands': [list(game['hands'][1]), []], 'board': list(game['board'])}, draws=128)
    observation['equity_source'] = 'Monte Carlo 128次：仅自己底牌和公开公共牌；未知手牌/后续公共牌均匀抽样，有抽样误差，不读取实际隐藏牌或未来牌堆。'
    record = _record('texas_holdem', '你是德州扑克对手，持有 own_hand',
        '双人虚拟筹码，最佳五张牌定胜负；当前公共牌已公开，玩家0底牌不可见。',
        observation, options,
        '根据自己底牌、公共牌、底池和筹码决定是否下注；不能猜测玩家0底牌。只输出合法动作 ID。')
    before = _observer_before(post_execution_observer, game, record)
    chosen, used = await _ask(chooser, record, game['steps'] * 100)
    wager = 0 if chosen == 'check' else int(chosen[3:])
    game['stacks'][1] -= wager
    game['pot'] += wager
    game['to_call'] = wager
    game['opponent_last'] = '过牌' if wager == 0 else '下注 ' + str(wager)
    game['event'] = game['opponent_last'] + '，轮到你'
    if min(game['stacks']) <= 0:
        missing = 5 - len(game['board'])
        game['board'] += game['deck'][:missing]
        social.settle(game)
    game['history'] = game['history'][-12:]
    await _observer_after(post_execution_observer, before, game, 1,
                          game['steps'] * 100, chosen)
    return game, used


async def _property(game, action, chooser, post_execution_observer=None):
    game = copy.deepcopy(game)
    game['steps'] += 1
    rng = random.Random(f"{game['seed']}/{game['steps']}")
    if action == 'roll':
        game['phase'] = 'end'
        social.property_move(game, 0, rng)
        return game, 0
    index = game['positions'][0]
    price = game['prices'].get(index, 0)
    if action == 'buy':
        game['owners'][str(index)] = 0
        game['cash'][0] -= price
    if action == 'build':
        game['levels'][str(index)] = game['levels'].get(str(index), 0) + 1
        game['cash'][0] -= price / 2
    before_owners = dict(game['owners'])
    social.property_move(game, 1, rng)
    position = game['positions'][1]
    key = str(position)
    # Undo only the existing rule bot's automatic purchase. All dice/chance,
    # rent, tax and pass-start effects stay exactly as the production engine ran.
    if key not in before_owners and game['owners'].get(key) == 1:
        game['cash'][1] += game['prices'][position]
        del game['owners'][key]
    options = None
    if not game['outcome'] and position in game['prices']:
        cost = game['prices'][position]
        if key not in game['owners'] and game['cash'][1] >= cost:
            options = {'buy': '购买当前地块', 'skip': '不购买'}
        elif game['owners'].get(key) == 1 and game['levels'].get(key, 0) < 3 and game['cash'][1] >= cost/2:
            options = {'build': '升级当前地块', 'skip': '暂不升级'}
    calls = 0
    before = None
    if options:
        observation = {'position': position, 'name': game['names'][position],
                       'dice': game['dice'], 'prices': game['prices'],
                       'owners': game['owners'], 'levels': game['levels'],
                       'cash': game['cash'], 'round': game['round']}
        record = _record('property_tycoon', '你是大富翁对手玩家1',
            '经过起点加 200，买地与升级有成本，踩对手地产要交租；第 20 回合比总资产，破产即输。',
            observation, options,
            '平衡现金安全与地产收益，目标在第20回合总资产超过玩家0。只输出合法动作 ID。')
        before = _observer_before(post_execution_observer, game, record)
        chosen, calls = await _ask(chooser, record, game['steps'] * 100)
        if chosen == 'buy':
            game['owners'][key] = 1
            game['cash'][1] -= game['prices'][position]
        elif chosen == 'build':
            game['levels'][key] = game['levels'].get(key, 0) + 1
            game['cash'][1] -= game['prices'][position] / 2
    game['phase'] = 'roll'
    game['round'] += 1
    if not game['outcome'] and game['round'] >= 20:
        totals = [game['cash'][side] + sum(game['prices'][int(i)] *
                  (1 + .5 * game['levels'].get(i, 0)) for i, owner in game['owners'].items() if owner == side)
                  for side in (0, 1)]
        game['outcome'] = 'win' if totals[0] > totals[1] else 'loss' if totals[0] < totals[1] else 'draw'
        game['event'] = '20 回合结束，按现金与地产价值结算：' + str(totals)
        game['score'] = totals[0]
    game['history'] = game['history'][-12:]
    if before is not None:
        await _observer_after(post_execution_observer, before, game, 1,
                              game['steps'] * 100, chosen)
    return game, calls


async def _zha(game, action, chooser, post_execution_observer=None):
    if action in ('fold', 'peek', 'compare'):
        return probability.step(game, action), 0
    game = copy.deepcopy(game)
    game['steps'] += 1
    if action == 'raise':
        game['stake'] = min(40, game['stake'] * 2)
    probability._pay(game, 0, game['stake'] * (2 if game['seen'] else 1))
    game['round'] += 1
    game['opponent_seen'] = True
    observation = {'own_hand': list(game['hands'][1]),
        'random_hand_equity': probability.blind_equity(tuple(sorted(game['hands'][1]))),
        'equity_source': '精确枚举合法随机未知三张牌，非当前实际对手胜率；未读取对手底牌。',
        'player_seen': game['seen'], 'own_stack': game['stacks'][1],
        'player_stack': game['stacks'][0], 'pot': game['pot'],
        'stake': game['stake'], 'round': game['round'], 'history': game['history'][-8:],
        'card_encoding': '0..12=♠2..A,13..25=♥2..A,26..38=♣2..A,39..51=♦2..A'}
    record = _record('zha_jin_hua', '你是炸金花对手玩家1，只知道自己的三张牌',
        '豹子 > 顺金 > 金花 > 顺子 > 对子 > 单张，A23 最小顺子；同牌主动比牌者负。对手底牌不可见。',
        observation, {'fold': '弃牌', 'call': '跟注 ' + str(game['stake'] * 2)},
        '考虑自己的牌型、底池赔率和虚拟筹码，决定弃牌或跟注。只输出合法动作 ID。')
    before = _observer_before(post_execution_observer, game, record)
    chosen, calls = await _ask(chooser, record, game['steps'] * 100)
    if chosen == 'fold':
        probability._settle(game, 0, '对手弃牌，你赢下底池！')
    else:
        probability._pay(game, 1, game['stake'] * 2)
        game['event'] = ('你加注' if action == 'raise' else '你跟注') + '；对手看牌后跟注。'
        game['history'].append(game['event'])
        if game['round'] >= 5 or min(game['stacks']) == 0:
            winner = 0 if probability.rank3(tuple(game['hands'][0])) > probability.rank3(tuple(game['hands'][1])) else 1
            probability._settle(game, winner, '五轮结算：' + ('你赢下底池！' if winner == 0 else '对手牌更大或同牌，你输了。'))
    game['history'] = game['history'][-12:]
    await _observer_after(post_execution_observer, before, game, 1,
                          game['steps'] * 100, chosen)
    return game, calls


async def _pig(game, action, chooser, post_execution_observer=None):
    game = copy.deepcopy(game)
    game['steps'] += 1
    rng = random.Random(f"{game['seed']}/{game['steps']}")
    if action == 'roll':
        die = rng.randint(1, 6)
        game['last_roll'] = die
        game['history'].append('你掷出 ' + str(die))
        if die > 1:
            game['turn_points'] += die
            game['event'] = '掷出 ' + str(die) + '，本轮暂存 ' + str(game['turn_points']) + ' 分。'
            game['history'] = game['history'][-12:]
            return game, 0
        game['turn_points'] = 0
        game['event'] = '掷出 1，本轮分数作废；轮到对手。'
    else:
        game['scores'][0] += game['turn_points']
        game['history'].append('你收下 ' + str(game['turn_points']) + ' 分')
        game['turn_points'] = 0
        if game['scores'][0] >= 50:
            game['outcome'] = 'win'
            game['event'] = '你先达到 50 分，获胜！'
            return game, 0
        game['event'] = '已收分，轮到对手。'
    points = calls = 0
    own_last_roll = None
    terminal_execution = None
    for substep in range(16):
        options = {'roll': '继续掷骰，1/6 概率损失本轮暂存分'}
        if points:
            options['hold'] = '收下 ' + str(points) + ' 分并换手'
        record = _record('pig_dice', '你是掷骰猪的对手玩家1',
            '六面骰掷到1则本轮暂存归零，否则加2–6；收分后换手。先到50分获胜。',
            {'own_score': game['scores'][1], 'player_score': game['scores'][0],
             'turn_points': points, 'player_last_roll': game['last_roll'],
             'own_last_roll': own_last_roll,
             'candidate_roll_outcome': {'source': 'exact_fair_die_one_step_distribution',
                'probability_turn_loss': 1/6, 'expected_pending_after_one_roll': (5*points+20)/6,
                'scope': '未收分的下一掷暂存分期望，非整局胜率或已入账得分'}},
            options, '比较继续掷骰的收益与损失已累积分数的风险。只输出合法动作 ID。')
        before = _observer_before(post_execution_observer, game, record,
            {'actor': 1, 'turn_points': points, 'own_last_roll': own_last_roll,
             'remaining_turn_rolls': 16 - substep})
        ordinal = game['steps'] * 100 + substep
        chosen, used = await _ask(chooser, record, ordinal)
        calls += used
        if chosen == 'hold':
            game['scores'][1] += points
            game['history'].append('对手收下 ' + str(points) + ' 分')
            terminal_execution = (before, ordinal, chosen,
                {'actor': 1, 'turn_points': 0, 'own_last_roll': own_last_roll,
                 'banked_points': points, 'turn_complete': True, 'automatic_turn_cap': False})
            break
        die = rng.randint(1, 6)
        own_last_roll = die
        game['history'].append('对手掷出 ' + str(die))
        if die == 1:
            terminal_execution = (before, ordinal, chosen,
                {'actor': 1, 'turn_points': 0, 'own_last_roll': die,
                 'lost_points': points, 'turn_complete': True, 'automatic_turn_cap': False})
            break
        points += die
        after_execution = {'actor': 1, 'turn_points': points, 'own_last_roll': die,
                           'turn_complete': False, 'automatic_turn_cap': False}
        if substep == 15:
            terminal_execution = (before, ordinal, chosen,
                {**after_execution, 'turn_points': 0, 'banked_points': points,
                 'turn_complete': True, 'automatic_turn_cap': True})
        else:
            await _observer_after(post_execution_observer, before, game, 1,
                                  ordinal, chosen, after_execution)
    else:
        game['scores'][1] += points
        game['history'].append('对手收下 ' + str(points) + ' 分')
    if game['scores'][1] >= 50:
        game['outcome'] = 'loss'
        game['event'] = '对手先达到 50 分，你输了。'
    else:
        game['event'] += ' 现在轮到你。'
    game['score'] = game['scores'][0]
    game['history'] = game['history'][-12:]
    if terminal_execution is not None:
        before, ordinal, chosen, execution = terminal_execution
        await _observer_after(post_execution_observer, before, game, 1, ordinal, chosen, execution)
    return game, calls


async def step(game, action, chooser, *, post_execution_observer=None):
    kind = game['kind']
    options = social.choices(game) if kind in social.SCENES else probability.choices(game)
    if action not in options:
        raise ValueError('illegal player action')
    if kind == 'doudizhu':
        return await _doudizhu(game, action, chooser, post_execution_observer)
    if kind == 'texas_holdem':
        return await _texas(game, action, chooser, post_execution_observer)
    if kind == 'property_tycoon':
        return await _property(game, action, chooser, post_execution_observer)
    if kind == 'zha_jin_hua':
        return await _zha(game, action, chooser, post_execution_observer)
    if kind == 'pig_dice':
        return await _pig(game, action, chooser, post_execution_observer)
    raise ValueError('unsupported Qwen opponent game')
