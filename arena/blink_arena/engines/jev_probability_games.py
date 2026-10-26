"""Two bounded, server-authoritative games with public Jev decisions."""
from __future__ import annotations

import copy
import itertools
import random
from collections import Counter
from functools import lru_cache

SCENES = {
    'zha_jin_hua': {
        'name': '炸金花',
        'mode': 'game',
        'note': '双人三张牌：闷牌、看牌、跟注、加注和比牌；只使用虚拟筹码。',
        'source_label': '交互规则仿真 · CuES 自建',
    },
    'pig_dice': {
        'name': '掷骰猪',
        'mode': 'game',
        'note': '掷骰累分或及时收手；掷到 1 本轮得分归零，先到 50 分获胜。',
        'source_label': '交互规则仿真 · CuES 自建',
        'url': 'https://github.com/google-deepmind/open_spiel/blob/master/docs/games.md',
    },
}
GOALS = {'zha_jin_hua': '赢下这手三张牌的底池', 'pig_dice': '先于对手达到 50 分'}
SUITS = ('♠', '♥', '♣', '♦')
RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')


def card_name(card):
    return SUITS[card // 13] + RANKS[card % 13]


@lru_cache(maxsize=25000)
def rank3(cards):
    """House ranking: trips > straight flush > flush > straight > pair > high card.

    A-2-3 is the lowest straight. Suits never break a tie; the player who asks
    to compare loses an exact tie.
    """
    values = sorted((card % 13 + 2 for card in cards), reverse=True)
    counts = Counter(values)
    flush = len({card // 13 for card in cards}) == 1
    unique = sorted(counts)
    straight = 3 if unique == [2, 3, 14] else unique[-1] if len(unique) == 3 and unique[-1] - unique[0] == 2 else 0
    if len(counts) == 1:
        return (5, values[0])
    if flush and straight:
        return (4, straight)
    if flush:
        return (3, *values)
    if straight:
        return (2, straight)
    if 2 in counts.values():
        pair = next(value for value, count in counts.items() if count == 2)
        kicker = next(value for value, count in counts.items() if count == 1)
        return (1, pair, kicker)
    return (0, *values)


def fresh(kind, seed=0):
    if kind not in SCENES:
        raise ValueError('未知游戏')
    rng = random.Random(seed)
    if kind == 'zha_jin_hua':
        deck = list(range(52))
        rng.shuffle(deck)
        return {'kind': kind, 'seed': seed, 'steps': 0, 'hands': [deck[:3], deck[3:6]],
                'stacks': [190, 190], 'pot': 20, 'stake': 10, 'round': 0,
                'seen': False, 'opponent_seen': False, 'showdown': False,
                'outcome': None, 'score': 0, 'event': '双方各投入 10 筹码；可以闷牌或先看牌。',
                'history': []}
    return {'kind': kind, 'seed': seed, 'steps': 0, 'scores': [0, 0], 'turn_points': 0,
            'last_roll': None, 'outcome': None, 'score': 0, 'event': '你先手，选择掷骰或收分。',
            'history': []}


def choices(game):
    if game['outcome']:
        return {}
    if game['kind'] == 'pig_dice':
        options = {'roll': '继续掷骰（1/6 概率损失本轮分数）'}
        if game['turn_points']:
            options['hold'] = '收下本轮 ' + str(game['turn_points']) + ' 分并换手'
        return options
    result = {'fold': '弃牌'}
    if not game['seen']:
        result['peek'] = '看自己的三张牌（此后下注额翻倍）'
    cost = game['stake'] * (2 if game['seen'] else 1)
    if game['stacks'][0] >= cost:
        result['call'] = '跟注 ' + str(cost)
    if game['stake'] < 40 and game['stacks'][0] >= min(40, game['stake'] * 2) * (2 if game['seen'] else 1):
        result['raise'] = '加注至 ' + str(min(40, game['stake'] * 2))
    if game['round'] >= 1 and game['stacks'][0] >= cost:
        result['compare'] = '付 ' + str(cost) + ' 筹码比牌（同牌由发起者负）'
    return result


@lru_cache(maxsize=256)
def blind_equity(cards):
    """Exact random-hand showdown probability, without reading opponent cards."""
    own = rank3(cards)
    deck = [card for card in range(52) if card not in cards]
    total = 0
    wins = 0
    ties = 0
    for other in itertools.combinations(deck, 3):
        score = rank3(other)
        total += 1
        wins += own > score
        ties += own == score
    return round((wins + 0.5 * ties) / total, 4)


def _pay(game, side, amount):
    amount = min(amount, game['stacks'][side])
    game['stacks'][side] -= amount
    game['pot'] += amount


def _settle(game, winner, event):
    game['showdown'] = True
    game['stacks'][winner] += game['pot']
    game['score'] = game['stacks'][0] - 200
    game['outcome'] = 'win' if winner == 0 else 'loss'
    game['event'] = event
    game['history'].append(event)


def _step_zha(game, action, rng):
    if action == 'fold':
        _settle(game, 1, '你弃牌，对手赢得底池。')
        return
    if action == 'peek':
        game['seen'] = True
        game['event'] = '你看了底牌；以后每次下注需要双倍筹码。'
        game['history'].append(game['event'])
        return
    if action == 'raise':
        game['stake'] = min(40, game['stake'] * 2)
    cost = game['stake'] * (2 if game['seen'] else 1)
    _pay(game, 0, cost)
    if action == 'compare':
        winner = 0 if rank3(tuple(game['hands'][0])) > rank3(tuple(game['hands'][1])) else 1
        _settle(game, winner, '比牌：' + ('你赢下底池！' if winner == 0 else '对手牌更大或同牌，你输了。'))
        return
    game['round'] += 1
    game['opponent_seen'] = True
    opponent_rank = rank3(tuple(game['hands'][1]))
    # The opponent uses only its own hidden hand, public bets and a seeded bluff.
    weak = opponent_rank[0] == 0 and opponent_rank[1] <= 10
    if game['round'] >= 2 and weak and rng.random() < 0.28:
        _settle(game, 0, '对手弃牌，你赢下底池！')
        return
    _pay(game, 1, game['stake'] * 2)
    game['event'] = ('你加注' if action == 'raise' else '你跟注') + '；对手看牌后跟注。'
    game['history'].append(game['event'])
    if game['round'] >= 5 or min(game['stacks']) == 0:
        own, other = rank3(tuple(game['hands'][0])), rank3(tuple(game['hands'][1]))
        winner = 0 if own > other else 1
        _settle(game, winner, '五轮结算：' + ('你赢下底池！' if winner == 0 else '对手牌更大或同牌，你输了。'))


def _pig_opponent(game, rng):
    points = 0
    for _ in range(16):
        target = 14 if game['scores'][1] >= game['scores'][0] else 18
        if points >= target or game['scores'][1] + points >= 50:
            game['scores'][1] += points
            game['history'].append('对手收下 ' + str(points) + ' 分')
            break
        die = rng.randint(1, 6)
        game['history'].append('对手掷出 ' + str(die))
        if die == 1:
            break
        points += die
    else:
        game['scores'][1] += points
        game['history'].append('对手收下 ' + str(points) + ' 分')
    if game['scores'][1] >= 50:
        game['outcome'] = 'loss'
        game['event'] = '对手先达到 50 分，你输了。'


def _step_pig(game, action, rng):
    if action == 'roll':
        die = rng.randint(1, 6)
        game['last_roll'] = die
        game['history'].append('你掷出 ' + str(die))
        if die > 1:
            game['turn_points'] += die
            game['event'] = '掷出 ' + str(die) + '，本轮暂存 ' + str(game['turn_points']) + ' 分。'
            return
        game['turn_points'] = 0
        game['event'] = '掷出 1，本轮分数作废；轮到对手。'
    else:
        game['scores'][0] += game['turn_points']
        game['history'].append('你收下 ' + str(game['turn_points']) + ' 分')
        game['turn_points'] = 0
        if game['scores'][0] >= 50:
            game['outcome'] = 'win'
            game['event'] = '你先达到 50 分，获胜！'
            return
        game['event'] = '已收分，轮到对手。'
    _pig_opponent(game, rng)
    if not game['outcome']:
        game['event'] += ' 现在轮到你。'
    game['score'] = game['scores'][0]


def step(game, action):
    if action not in choices(game):
        raise ValueError('非法动作')
    next_game = copy.deepcopy(game)
    next_game['steps'] += 1
    rng = random.Random(f"{next_game['seed']}/{next_game['steps']}")
    if next_game['kind'] == 'zha_jin_hua':
        _step_zha(next_game, action, rng)
    else:
        _step_pig(next_game, action, rng)
    next_game['history'] = next_game['history'][-12:]
    return next_game


def public(game):
    result = {key: copy.deepcopy(value) for key, value in game.items() if key not in ('seed', 'hands')}
    if game['kind'] == 'zha_jin_hua':
        result['hand'] = list(game['hands'][0]) if game['seen'] or game['showdown'] else None
        result['opponent_hand'] = list(game['hands'][1]) if game['showdown'] else None
        result['card_encoding'] = '0..12=♠2..A,13..25=♥2..A,26..38=♣2..A,39..51=♦2..A'
    return result


def as_record(game):
    observation = public(game)
    if game['kind'] == 'zha_jin_hua':
        if game['seen']:
            observation['random_hand_equity'] = blind_equity(tuple(sorted(game['hands'][0])))
        rules = ('双人三张牌、虚拟筹码各 200，双方先各付 10。自建固定规则：豹子 > 顺金 > 金花 > 顺子 > 对子 > 单张；'
                 'A23 是最小顺子。同牌由主动比牌者负。闷牌下注额为当前档位，看牌后为两倍；可跟注或加注至最多 40。'
                 '至少跟注一轮后可付费比牌，第五轮或筹码耗尽时自动摊牌。对手底牌在摊牌前不可见；'
                 'random_hand_equity 仅是对随机三张牌的精确胜率，不代表对该对手的胜率。')
        prompt = ('目标是赢得本手底池。根据手牌信息、底池赔率、已投入筹码和剩余轮数选择；'
                  '闷牌时不得假设自己或对手的隐藏牌。看牌后可使用随机手牌胜率作参考，并留意看牌后的双倍下注成本。'
                  '只输出合法动作 ID。')
    else:
        rules = ('双人掷骰猪，先到 50 分获胜。每次掷六面骰，2–6 加入本轮暂存分，掷到 1 则本轮暂存清零并换手；'
                 '选择收分可把暂存分加入总分并换手。骰子公平，每次掷出 1 的概率为 1/6；没有真实下注。')
        prompt = ('比较当前暂存分、双方总分与到 50 分的差距。继续掷骰可能获益，也有 1/6 概率损失本轮暂存分；'
                  '达到 50 分时及时收分。只输出合法动作 ID。')
    return {
        'schema_version': 'jev.training.v1', 'id': 'live-' + game['kind'], 'group_id': 'live-' + game['kind'],
        'state': {'role': '玩家0', 'rules': rules, 'observation': observation},
        'questions': {'decision': {'type': 'choice', 'instructions': prompt, 'criteria': choices(game),
                                   'option_order': list(choices(game))}},
        'labels': {},
        'provenance': {'data_source': 'cues_probability_games_v1', 'source_id': 'live', 'source_split': 'demo'},
        'metadata': {'domain': 'games', 'sub_domain': game['kind'], 'scenario': 'interactive_control',
                     'task_category': 'control'},
    }
