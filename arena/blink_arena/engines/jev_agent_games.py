"""CPU-only, locally playable board games with observation-safe Jev decisions.

OpenSpiel owns the five game rule engines; python-chess owns chess legality.
Serialized states, sealed bids and random generators stay on the server.
"""
import copy
import math
import random
import re
import sys
from functools import lru_cache
from pathlib import Path

import chess

import pyspiel

SPECS = {
    'breakthrough': 'breakthrough(rows=6,columns=6)',
    'mancala': 'mancala',
    'liars_dice': 'liars_dice(numdice=3)',
    'goofspiel': 'goofspiel(num_cards=7,imp_info=false)',
    'blackjack': 'blackjack',
}
HIDDEN = frozenset({'liars_dice', 'goofspiel'})
RULES = {
    'chess': '国际象棋标准规则，白方先行。支持王车易位、吃过路兵、升变。将死获胜；无子可走且未被将军、子力不足、可申领的三次重复或五十回合规则自动和棋。',
    'breakthrough': '6×6 棋盘，黑方先行并向下走，白方向上走。兵每次向正前或斜前走一格；正前只能走到空格，斜前可走空格或吃敌兵。任一兵抵达对侧底线或吃光敌兵即胜。',
    'mancala': '每方六个小坑，每坑四颗种子。选己方非空坑，按递增编号逆时针播种，跳过对方得分仓。最后一颗落入己仓可再走；落入己方空坑且对坑有种子，则一并收走。任一侧清空即结算，各方余种计入自己的得分，分多者胜。',
    'liars_dice': '双方各三枚六面骰，只能看己方骰子。每次叫「至少 N 枚点数 F」，数量增加或同数量点数增加。6 是万能点，计入任意非 6 点数的叫数；叫 6 时只数 6。可质疑上次叫数：实际不足则叫数者输，否则质疑者输。一轮定胜负。',
    'goofspiel': '双方各有 1–7 的七张牌。每轮翻出一张随机奖分牌，双方密封选择一张未用手牌，同时揭示。出牌较大者获得奖分；相同则该奖分作废。手牌各用一次，最后只剩一张时自动出牌。七轮后总分高者胜。对手剩余手牌公开，当轮密封出牌不可见。',
    'blackjack': '单人对庄家。A 算 1 或 11，J/Q/K 算 10；爆 21 即输。选择要牌或停牌，庄家 16 点及以下要牌、17 点及以上停牌（含软 17）。不分牌、不加倍；最终更接近 21 者胜，同点和局。仅虚拟得分。',
}
GOALS = {'chess': '将死对方的王', 'breakthrough': '让一枚兵突破对方底线',
         'mancala': '收集比对手更多的种子', 'liars_dice': '识破虚报，或让对手质疑失败',
         'goofspiel': '用七张手牌赢得更多奖分', 'blackjack': '不超过 21 点，并胜过庄家'}
STRATEGY = {
    'chess': '先查将军、将杀、己方被将军和对方下一手威胁；再比较候选着的失子风险与子力发展。棋盘第一行是第 8 横线，白方大写、黑方小写；动作 ID 是 UCI。不要只连续推动同一兵而忽视王的安全。',
    'breakthrough': '先检查本步是否可到对侧底线，以及对手下一步能否突破；优先挡住直接威胁或吃掉突破兵，再推进有掩护的兵。向前竞速时避免把唯一防线送给对手。',
    'mancala': 'observation.candidate_preview 列出每个合法播种动作的公开确定结果。先看额外回合、直接得分与捕获，再比较播种后对手可得分数和终局清盘风险；不要只看坑内现有种子数量。',
    'liars_dice': '用自己的三枚骰和上次叫数估算可信度；未知的三枚对手骰须按概率而不是当作已知。仅在上次叫数明显不可信时质疑；否则选择自己骰支持、不过分抬高数量的最小合法叫数。',
    'goofspiel': 'option 的动作 ID 从 0 开始，实际出牌数字是动作 ID+1。看 observation.rounds 中已揭示的对手出牌，把对手对奖分的出牌倾向当作预测而非确定信息。若对手常出与当前奖分同值且手中仍有此牌，同值出牌只会平局；高奖分 5/6 可考虑高一档争胜，奖分 7 无法用更高牌压制时可暂用低牌节省资源。始终考虑双方剩余手牌和累计奖分。当前密封出牌不可见。',
    'blackjack': '先按 A 可作 1 或 11 算出不爆点数，再看庄家明牌。总点数 17 以上通常停牌；11 以下通常要牌；12–16 对庄家高明牌时权衡爆牌风险与庄家成牌概率。停牌后庄家按规则行动，不能看到暗牌。',
}
SCENES = {k: {'name': name, 'mode': 'game', 'note': note,
               'supports_opponent': k != 'blackjack', 'source_label': source,
               'url': url} for k, name, note, source, url in [
    ('chess', '国际象棋', '从开局到将杀，在完整规则下对弈。', '规则引擎 · python-chess', 'https://python-chess.readthedocs.io/'),
    ('breakthrough', '兵卒突围', '没有后退的兵，六行棋盘里的攻防竞速。', '规则引擎 · OpenSpiel', 'https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/breakthrough/breakthrough.cc'),
    ('mancala', '播棋 · Mancala', '一把种子，连走与捕获的巧妙布局。', '规则引擎 · OpenSpiel', 'https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/mancala/mancala.cc'),
    ('liars_dice', '吹牛骰子', '三枚暗骰，概率判断与胆量的较量。', '规则引擎 · OpenSpiel', 'https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/liars_dice/liars_dice.cc'),
    ('goofspiel', '竞价夺牌', '同时亮牌，把最好的筹码留给值得的奖分。', '规则引擎 · OpenSpiel', 'https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/goofspiel/goofspiel.cc'),
    ('blackjack', '21 点', '继续要牌，还是见好就收？', '规则引擎 · OpenSpiel', 'https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/blackjack/blackjack.cc'),
]}


@lru_cache(maxsize=8)
def engine(kind):
    return pyspiel.load_game(SPECS[kind])


def restore(g):
    if g['kind'] == 'chess':
        b = chess.Board()
        for uci in g['_moves']:
            b.push_uci(uci)
        return b
    return engine(g['kind']).deserialize_state(g['_state'])


def settle(g, state):
    while state.is_chance_node():
        actions, weights = zip(*state.chance_outcomes())
        state.apply_action(g['_rng'].choices(actions, weights=weights)[0])
    g['_state'] = state.serialize()


def actor(g, state=None):
    if g['kind'] == 'goofspiel':
        return 1 if g['_pending'] is not None else 0
    state = state if state is not None else restore(g)
    return (0 if state.turn else 1) if g['kind'] == 'chess' else max(0, state.current_player())


def names(g):
    if g['kind'] == 'chess':
        return ['白方', '黑方' if g['opponent'] == 'human' else '黑方 · 规则对手']
    if g['kind'] == 'breakthrough':
        return ['黑方', '白方' if g['opponent'] == 'human' else '白方 · 规则对手']
    if g['kind'] == 'blackjack':
        return ['你', '庄家']
    return ['玩家一', '玩家二' if g['opponent'] == 'human' else '规则对手']


def finished(g, state=None):
    state = state if state is not None else restore(g)
    return state.outcome(claim_draw=True) is not None if g['kind'] == 'chess' else state.is_terminal()


def options(g):
    s = restore(g)
    if finished(g, s):
        return {}
    if g['kind'] == 'chess':
        return {m.uci(): s.san(m) for m in s.legal_moves}
    p = actor(g, s)
    legal = s.legal_actions(p)
    if g['kind'] == 'breakthrough':
        return {str(a): s.action_to_string(p, a) for a in legal}
    if g['kind'] == 'mancala':
        return {str(a): f'播种 · {a} 号坑' for a in legal}
    if g['kind'] == 'liars_dice':
        return {str(a): '质疑上家' if a == 36 else f'至少 {a // 6 + 1} 枚「{a % 6 + 1}」' for a in legal}
    if g['kind'] == 'goofspiel':
        return {str(a): f'密封出牌 · {a + 1}' for a in legal}
    return {str(a): ('要牌' if a == 0 else '停牌') for a in legal}


def choices(g):
    return {} if g['handoff'] else options(g)


def fresh(kind, seed, opponent='human'):
    if kind not in SCENES or opponent not in ('human', 'rule'):
        raise ValueError('unknown game or opponent')
    g = {'kind': kind, 'opponent': opponent, 'steps': 0, 'history': [],
         'handoff': kind in HIDDEN and opponent == 'human', '_rng': random.Random(seed),
         '_pending': None, '_moves': [], 'last_move': None, 'rounds': [], 'event': '新的一局，开始吧'}
    if kind != 'chess':
        settle(g, engine(kind).new_initial_state())
    return g


def goof_info(s):
    obs = s.observation_string(0)
    def vals(label):
        match = re.search(r'^' + re.escape(label) + r':([^\n]*)', obs, re.M)
        return [int(x) for x in re.findall(r'\d+', match.group(1))] if match else []
    remaining = re.search(r'Remaining Point Cards: ([^\n]*)', obs)
    return {'hands': [vals('P0 hand'), vals('P1 hand')], 'points': vals('Points'),
            'prize': next(iter(vals('Current point card')), None),
            'remaining': [int(x) for x in remaining.group(1) if x.isdigit()] if remaining else []}


def apply_one(g, action):
    s = restore(g)
    p = actor(g, s)
    label = options(g)[action]
    kind = g['kind']
    if kind == 'chess':
        s.push_uci(action)
        g['_moves'].append(action)
        g['last_move'] = action
    elif kind == 'goofspiel':
        if g['_pending'] is None:
            if g['opponent'] == 'human':
                g['_pending'] = int(action)
                g['event'] = '玩家一已密封出牌，请玩家二接手'
                g['steps'] += 1
                return
            # The policy sees only the uncommitted public position.
            bids = [int(action), int(rule_action(g, player=1))]
        else:
            bids = [g['_pending'], int(action)]
        before = goof_info(s)
        s.apply_actions(bids)
        settle(g, s)
        g['_pending'] = None
        round_info = {'prize': before['prize'], 'bids': [a + 1 for a in bids]}
        g['rounds'].append(round_info)
        g['event'] = f"奖分 {before['prize']} · 出牌 {bids[0]+1} : {bids[1]+1}"
        if s.is_terminal() and len(before['hands'][0]) == 2:
            final_bids = [next(v for v in before['hands'][p] if v != bids[p] + 1) for p in (0, 1)]
            final_prize = next(v for v in before['remaining'] if v != before['prize'])
            g['rounds'].append({'prize': final_prize, 'bids': final_bids, 'automatic': True})
            g['event'] += '；最后一轮自动亮牌'
        g['steps'] += 1
        g['history'].append(g['event'])
        return
    else:
        if kind == 'breakthrough':
            g['last_move'] = s.action_to_string(p, int(action))
        s.apply_action(int(action))
        settle(g, s)
    g['steps'] += 1
    g['event'] = f'{names(g)[p]} · {label}'
    g['history'].append(g['event'])
    g['history'] = g['history'][-30:]


def step(g, action):
    if action not in choices(g):
        raise ValueError('illegal action')
    g = copy.deepcopy(g)
    apply_one(g, action)
    if g['opponent'] == 'rule' and g['kind'] not in ('blackjack', 'goofspiel'):
        for _ in range(100):
            if finished(g) or actor(g) == 0:
                break
            apply_one(g, rule_action(g))
        else:
            raise ValueError('opponent turn limit')
    g['handoff'] = g['kind'] in HIDDEN and g['opponent'] == 'human' and not finished(g)
    return g


def reveal(g):
    if not g['handoff']:
        raise ValueError('no handoff pending')
    g = copy.deepcopy(g)
    g['handoff'] = False
    return g


def chess_score(board, color):
    end = board.outcome(claim_draw=True)
    if end:
        return 0 if end.winner is None else (100000 if end.winner == color else -100000)
    value = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
             chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
    return sum((1 if piece.color == color else -1) * (value[piece.piece_type] +
               (3.5 - abs(3.5-chess.square_file(sq))) * 3) for sq, piece in board.piece_map().items())


def rule_action(g, player=None):
    s = restore(g)
    p = actor(g, s) if player is None else player
    kind = g['kind']
    if kind == 'chess':
        color = s.turn
        def rank(m):
            b = s.copy()
            b.push(m)
            if b.outcome(claim_draw=True):
                return chess_score(b, color)
            return min(chess_score_after(b, reply, color) for reply in b.legal_moves)
        return max(s.legal_moves, key=rank).uci()
    legal = s.legal_actions(p)
    if kind == 'goofspiel':
        info = goof_info(s)
        rank = sorted(info['remaining'] + [info['prize']]).index(info['prize'])
        return str(sorted(legal)[min(rank, len(legal)-1)])
    if kind == 'liars_dice':
        info = s.information_state_string(p).split()
        dice = [int(x) for x in info[0]]
        def probability(a):
            qty, face = a // 6 + 1, a % 6 + 1
            need = qty - sum(x == face or (face != 6 and x == 6) for x in dice)
            prob = 1 / 6 if face == 6 else 1 / 3
            return sum(math.comb(3, n) * prob**n * (1-prob)**(3-n) for n in range(max(0, need), 4))
        if 36 in legal:
            qty, face = map(int, info[-1].split('-'))
            if probability((qty-1)*6+face-1) < .45:
                return '36'
        bids = [a for a in legal if a != 36]
        if not bids:
            return '36'
        return str(max(bids, key=lambda a: probability(a) - a * .007))
    def rank(a):
        b = s.clone()
        b.apply_action(a)
        if b.is_terminal():
            return b.returns()[p] * 10000
        if kind == 'mancala':
            v = list(b.observation_tensor(0))[:14]
            return (v[7]-v[0]) * (1 if p == 0 else -1) + (3 if b.current_player() == p else 0)
        rows = breakthrough_board(b)
        own, enemy = ('b', 'w') if p == 0 else ('w', 'b')
        return sum((8+(r if p == 0 else 5-r)) if v == own else -8 if v == enemy else 0
                   for r, row in enumerate(rows) for v in row)
    return str(max(legal, key=rank))


def chess_score_after(board, move, color):
    b = board.copy()
    b.push(move)
    return chess_score(b, color)


def breakthrough_board(s):
    return [list(line[1:7]) for line in s.observation_string(0).splitlines() if re.match(r'^[1-6][bw.]{6}$', line)]


def card_name(ident):
    return 'CDHS'[ident // 13] + 'A23456789TJQK'[ident % 13]


def public(g):
    s = restore(g)
    p = actor(g, s)
    end = finished(g, s)
    out = {k: copy.deepcopy(g[k]) for k in ('kind', 'opponent', 'steps', 'handoff', 'event', 'history', 'last_move', 'rounds')}
    out.update(current_player=p, players=names(g), rules=RULES[g['kind']], outcome=None,
               stats=[[g['steps'], '行动次数'], ['本地双人' if g['opponent'] == 'human' else '规则对手', '对局方式']])
    if end:
        if g['kind'] == 'chess':
            winner = s.outcome(claim_draw=True).winner
            result = 0 if winner is None else 1 if winner else -1
        else:
            result = s.returns()[0]
        out['outcome'] = 'draw' if result == 0 else 'win' if result > 0 else 'loss'
        out['outcome_label'] = '和局' if result == 0 else names(g)[0 if result > 0 else 1] + '获胜'
    kind = g['kind']
    if kind == 'chess':
        out.update(board=[[s.piece_at(chess.square(c, r)).symbol() if s.piece_at(chess.square(c, r)) else '.' for c in range(8)] for r in range(7, -1, -1)], check=s.is_check(), fen=s.fen())
    elif kind == 'breakthrough':
        out['board'] = breakthrough_board(s)
        out['moves'] = {a: v for a, v in options(g).items()}
    elif kind == 'mancala':
        pits = [int(n) for n in s.observation_tensor(0)[:14]]
        out['pits'] = pits
        scores = [pits[7], pits[0]]
        if end:
            scores = [pits[7]+sum(pits[1:7]), pits[0]+sum(pits[8:14])]
        out['stats'] = [[scores[0], '玩家一得分'], [scores[1], '玩家二得分']]
    elif kind == 'liars_dice':
        own = s.information_state_string(p).split()
        out['bids'] = own[1:]
        if not g['handoff'] or end:
            out['dice'] = [int(x) for x in own[0]]
        if end:
            out['all_dice'] = [[int(x) for x in s.information_state_string(i).split()[0]] for i in (0, 1)]
    elif kind == 'goofspiel':
        out.update(goof_info(s))
        out['stats'] = [[out['points'][0], '玩家一奖分'], [out['points'][1], '玩家二奖分']]
    else:
        out['cards'] = [card_name(c) for c in s.cards(0)]
        out['dealer'] = [card_name(c) for c in s.cards(1)] if end else ['??', card_name(s.dealers_visible_card())]
        out['stats'] = [[g['steps'], '决策次数'], ['固定庄家', '对局方式']]
    return out


def as_record(g):
    opts = choices(g)
    if len(opts) < 2:
        raise ValueError('decision needs two options')
    obs = public(g)
    # Move/bid history is public information.  Keep it in the model state so
    # sequential decisions can account for earlier moves and revealed bids.
    for key in ('stats', 'event', 'handoff', 'opponent'):
        obs.pop(key, None)
    if g['kind'] == 'mancala':
        # Mancala is fully observable.  Show the deterministic result of each
        # legal sowing so the model can compare turns and captures correctly.
        current = restore(g)
        before = [int(n) for n in current.observation_tensor(0)[:14]]
        obs['pit_layout'] = 'pits[1..6]=本方坑，pits[7]=本方得分仓；pits[8..13]=对手坑，pits[0]=对手得分仓。'
        obs['candidate_preview'] = {}
        for action in opts:
            after = current.clone()
            after.apply_action(int(action))
            pits = [int(n) for n in after.observation_tensor(0)[:14]]
            obs['candidate_preview'][action] = {
                'pits_after': pits,
                'own_store_gain': pits[7] - before[7],
                'extra_turn': not after.is_terminal() and after.current_player() == 0,
            }
    ident = f"interactive-{g['kind']}-{g['steps']}"
    return {'schema_version': 'jev.training.v1', 'id': ident, 'group_id': ident,
            'state': {'role': f"你正在替{names(g)[actor(g)]}行动。只能依据本方可见观测，选择一个合法动作。", 'observation': obs},
            'questions': {'decision': {'type': 'choice', 'instructions': '整局目标：' + GOALS[g['kind']] + '。' + STRATEGY[g['kind']] + '只输出当前合法动作 ID。', 'criteria': opts, 'option_order': list(opts)}},
            'labels': {}, 'provenance': {'data_source': 'jev_live_agent_games', 'source_id': ident, 'source_split': 'demo', 'source_revision': '20261009-v1'},
            'metadata': {'domain': 'game', 'sub_domain': g['kind'], 'scenario': SCENES[g['kind']]['name'], 'task_category': 'bounded_decision', 'difficulty': 'L1'}}
