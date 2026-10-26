"""Shared orthodox-chess rules, public one-ply facts and JSON replay state.

python-chess supplies legality, never a teacher/search answer. Every legal move
remains an option. Claimable draws require a separate explicit action; a budget
limit is not a chess result. No model failure invokes the rule opponent.
"""
from __future__ import annotations

import copy
import random
from typing import Any, Mapping

import chess

KIND = 'chess'
REVISION = 'jev.chess.visible-one-ply.v1'
DEFAULT_MAX_PLIES = 256
RULE_CANDIDATE_BUDGET = 256
RULE_POLICY = 'public-one-ply-material-development-v1'
CONTROLLERS = frozenset({'model', 'human', 'rule', 'rule_engine', 'qwen3.8-max',
                         'deterministic_execution'})
PIECE_NAMES = {chess.PAWN: '兵', chess.KNIGHT: '马', chess.BISHOP: '象',
               chess.ROOK: '车', chess.QUEEN: '后', chess.KING: '王'}
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
          chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
RULES = ('标准国际象棋，0 为白方、1 为黑方，白方先走。支持王车易位、吃过路兵和四种升变。'
         '将死获胜；逼和、子力不足、五次重复、七十五回合规则自动和棋。'
         '三次重复和五十回合规则需要明确选择申和；可预告一手合法走法后申和。'
         '预算耗尽记未完成，不按子力或引擎估分裁胜。候选为全部合法走法，'
         'UCI 是稳定动作 ID，SAN 是人类记谱，候选只附当前公开棋盘的一步规则事实。')


def _validate_seed(seed: int | None) -> int:
    seed = 0 if seed is None else seed
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError('seed must be uint32 or None')
    return seed


def _board(state: Mapping[str, Any]) -> chess.Board:
    if state.get('kind') != KIND or state.get('engine_revision') != REVISION:
        raise ValueError('Unsupported chess state')
    board = chess.Board(state['initial_fen'])
    if not board.is_valid():
        raise ValueError('Invalid initial chess position')
    moves = state.get('moves_uci')
    history = state.get('history')
    if (not isinstance(moves, list) or not isinstance(history, list)
            or type(state.get('steps')) is not int or state['steps'] != len(history)
            or type(state.get('opening_plies')) is not int
            or not 0 <= state['opening_plies'] <= len(moves)
            or type(state.get('max_plies')) is not int or state['max_plies'] < 1):
        raise ValueError('Invalid chess action journal')
    recorded = [row.get('uci') for row in history if row.get('uci')]
    if moves[state['opening_plies']:] != recorded:
        raise ValueError('Chess move history and action journal disagree')
    for uci in moves:
        if board.is_game_over(claim_draw=False):
            raise ValueError('Move history continues after a chess terminal')
        board.push_uci(uci)  # Validates legality, including castling/EP/promotion.
    if state.get('fen') is not None and state['fen'] != board.fen(en_passant='fen'):
        raise ValueError('Chess FEN does not match the complete move history')
    return board


def actor(state: Mapping[str, Any]) -> int:
    return 0 if _board(state).turn == chess.WHITE else 1


def _claims(board: chess.Board) -> dict[str, dict[str, Any]]:
    result = {}
    if board.is_game_over(claim_draw=False):
        return result
    now_three = board.is_repetition(3)
    now_fifty = board.is_fifty_moves()
    witnesses = {'threefold': [], 'fifty_moves': []}
    for reason, valid in [('threefold', now_three), ('fifty_moves', now_fifty)]:
        if valid:
            result['claim_draw:' + reason] = {'reason': reason, 'intended_uci': None,
                'available_now': True, 'announced_witnesses': [], 'witness_selection': 'not_required'}
    # An announced move is verified but not played: the player claims before
    # making it, and the game ends without transferring the turn. All witnesses
    # for one reason certify the same semantic claim; they are facts, not extra
    # policy choices. Ordinary legal UCI moves remain separate and complete.
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        san = board.san(move)
        board.push(move)
        checks = [('threefold', not now_three and board.is_repetition(3)),
                  ('fifty_moves', not now_fifty and board.is_fifty_moves())]
        board.pop()
        for reason, valid in checks:
            if valid:
                witnesses[reason].append({'uci': move.uci(), 'san': san})
    for reason, proofs in witnesses.items():
        if proofs:
            selected = proofs[0]  # Iteration order is lexicographic UCI.
            result['claim_draw:' + reason] = {'reason': reason,
                'intended_uci': selected['uci'], 'intended_san': selected['san'],
                'available_now': False, 'announced_witnesses': proofs,
                'witness_selection': 'lexicographic_uci_first'}
    return result


def _terminal(state: Mapping[str, Any], board: chess.Board) -> tuple[str | None, str | None, str]:
    native = board.outcome(claim_draw=False)
    if native is not None:
        value = 'draw' if native.winner is None else 'win' if native.winner else 'loss'
        return value, native.termination.name.lower(), native.result()
    claim = state.get('claim')
    if claim:
        action = claim.get('action')
        valid = _claims(board).get(action)
        if (valid is None or claim != {'action': action, **valid, 'actor': 0 if board.turn else 1}
                or not state['history'] or state['history'][-1]['action'] != action):
            raise ValueError('Invalid recorded draw claim')
        return 'draw', 'claimed_' + valid['reason'], '1/2-1/2'
    if state['steps'] >= state['max_plies']:
        return 'budget_exhausted', 'ply_budget', '*'
    return None, None, '*'


def outcome(state: Mapping[str, Any], side: int | None = 0) -> str | None:
    side = 0 if side is None else side
    if type(side) is not int or side not in (0, 1):
        raise ValueError('Chess seat must be 0 (white) or 1 (black)')
    result = _terminal(state, _board(state))[0]
    if side == 1 and result in ('win', 'loss'):
        return 'loss' if result == 'win' else 'win'
    return result


def finished(state: Mapping[str, Any]) -> bool:
    return outcome(state) is not None


def _sync(state: dict, board: chess.Board) -> dict:
    state.update(fen=board.fen(en_passant='fen'), current_player=0 if board.turn else 1)
    state['outcome'], state['termination'], state['result'] = _terminal(state, board)
    return state


def fresh(seed: int | None = 0, *, opponent: str = 'human', max_plies: int = DEFAULT_MAX_PLIES,
          fen: str | None = None) -> dict[str, Any]:
    seed = _validate_seed(seed)
    if opponent not in ('human', 'rule', 'rule_engine', 'qwen3.8-max'):
        raise ValueError('Unknown chess opponent')
    if type(max_plies) is not int or not 1 <= max_plies <= 4096:
        raise ValueError('max_plies must be an integer in [1,4096]')
    if fen is not None and seed != 0:
        raise ValueError('An explicit FEN cannot also claim a seeded random opening')
    board = chess.Board(fen) if fen is not None else chess.Board()
    if not board.is_valid():
        raise ValueError('Explicit FEN is not a valid orthodox chess position')
    initial_fen = board.fen(en_passant='fen')
    opening = []
    if seed and fen is None:
        rng = random.Random(seed)
        for _ in range(4 + 2 * (seed % 5)):
            # No book/teacher score. Only legal moves that do not already end
            # the game may belong to the public randomized opening prefix.
            candidates = []
            for move in sorted(board.legal_moves, key=lambda item: item.uci()):
                board.push(move)
                terminal = board.is_game_over(claim_draw=False)
                board.pop()
                if not terminal:
                    candidates.append(move)
            if not candidates:
                break
            selected = rng.choice(candidates)
            opening.append(selected.uci())
            board.push(selected)
        # Both model seats are covered by the runner; reset itself always has
        # white to move, even if an exceptional opening cannot be extended.
        if len(opening) % 2:
            opening.pop()
            board.pop()
    state = {'kind': KIND, 'engine_revision': REVISION, 'seed': seed,
             'initial_fen': initial_fen, 'moves_uci': opening, 'opening_plies': len(opening),
             'initialization': {'source': 'explicit_fen' if fen is not None else
                                'standard_start' if seed == 0 else 'seeded_legal_opening',
                                'generator_revision': 'legal-uniform-prefix-v1',
                                'opening_uci': list(opening), 'opening_is_policy_trajectory': False},
             'opponent': opponent, 'steps': 0, 'max_plies': max_plies,
             'history': [], 'last_move': None, 'claim': None, 'handoff': False,
             'event': '标准初始局面' if seed == 0 and fen is None else '公开起始局面已加载'}
    return _sync(state, board)


def _move_facts(board: chess.Board, move: chess.Move) -> dict[str, Any]:
    piece = board.piece_at(move.from_square)
    en_passant = board.is_en_passant(move)
    captured = chess.PAWN if en_passant else (
        board.piece_at(move.to_square).piece_type if board.piece_at(move.to_square) else None)
    facts = {'uci': move.uci(), 'san': board.san(move),
             'from_square': chess.square_name(move.from_square),
             'to_square': chess.square_name(move.to_square),
             'piece': piece.symbol(), 'captured_piece': chess.piece_name(captured) if captured else None,
             'captured_value': VALUES.get(captured, 0),
             'castling': board.is_castling(move), 'en_passant': en_passant,
             'promotion': chess.piece_name(move.promotion) if move.promotion else None,
             'certainty': 'deterministic_public_one_ply_rules'}
    board.push(move)
    end = board.outcome(claim_draw=False)
    facts.update(gives_check=board.is_check(), checkmate=board.is_checkmate(),
                 resulting_piece_attacked=board.is_attacked_by(board.turn, move.to_square),
                 attack_fact_note='Geometric attack; pinned attackers need not have a legal capture.',
                 automatic_termination=end.termination.name.lower() if end else None,
                 automatic_result=end.result() if end else None)
    board.pop()
    return facts


def _catalog(state: Mapping[str, Any], board: chess.Board) -> tuple[dict[str, str], dict[str, dict]]:
    if _terminal(state, board)[0] is not None:
        return {}, {}
    options, facts = {}, {}
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        item = _move_facts(board, move)
        parts = [item['san'], f"{item['from_square']}→{item['to_square']}"]
        if item['captured_piece']:
            parts.append('吃' + PIECE_NAMES[chess.PIECE_NAMES.index(item['captured_piece'])])
        if item['castling']: parts.append('王车易位')
        if item['en_passant']: parts.append('吃过路兵')
        if move.promotion: parts.append('升变为' + PIECE_NAMES[move.promotion])
        if item['checkmate']: parts.append('执行后将死')
        elif item['gives_check']: parts.append('执行后将军')
        if item['automatic_termination'] and not item['checkmate']:
            parts.append('执行后规则和棋:' + item['automatic_termination'])
        parts.append('落点受对方几何攻击' if item['resulting_piece_attacked'] else '落点未受对方几何攻击')
        options[move.uci()] = '；'.join(parts)
        facts[move.uci()] = item
    for action, item in _claims(board).items():
        reason = '三次重复' if item['reason'] == 'threefold' else '五十回合规则'
        options[action] = ('预告 ' + item['intended_san'] + ' 后申领' if item['intended_uci'] else '立即申领') + reason + '和棋'
        facts[action] = {**item, 'draw_claim': True, 'move_is_announced_not_executed': bool(item['intended_uci']),
                         'certainty': 'deterministic_public_rules_and_complete_history'}
    return options, facts


def choices(state: Mapping[str, Any]) -> dict[str, str]:
    return _catalog(state, _board(state))[0]


def step(state: Mapping[str, Any], action: str, *, controller: str = 'model') -> dict[str, Any]:
    if controller not in CONTROLLERS:
        raise ValueError('Unsupported chess action controller')
    board = _board(state)
    if _terminal(state, board)[0] is not None:
        raise ValueError('Cannot act after a chess terminal or budget limit')
    if not isinstance(action, str):
        raise ValueError('Chess actions must be UCI or explicit draw claims')
    if controller == 'deterministic_execution' and len(_catalog(state, board)[0]) != 1:
        raise ValueError('Only a unique legal action is deterministic forced execution')
    before = board.fen(en_passant='fen')
    seat = 0 if board.turn else 1
    claims = _claims(board) if action.startswith('claim_draw:') else {}
    claim = claims.get(action)
    if action.startswith('claim_draw:'):
        if claim is None:
            raise ValueError('Draw claim is not legal in this position/history')
        move, san = None, None
    else:
        try:
            move = chess.Move.from_uci(action)
        except ValueError as error:
            raise ValueError('Invalid UCI action') from error
        if move not in board.legal_moves:
            raise ValueError('Illegal chess move; no fallback was executed')
        san = board.san(move)
        board.push(move)
    result = copy.deepcopy(dict(state))
    origin = ('rule_opponent' if controller in ('rule', 'rule_engine') else
              'opponent_model' if controller == 'qwen3.8-max' else
              'forced_legal_execution' if controller == 'deterministic_execution' else controller)
    row = {'action': action, 'actor': seat, 'controller': controller, 'strategy_origin': origin,
           'policy_decision_class': 'C' if origin == 'rule_opponent' else
                                    'B' if origin == 'forced_legal_execution' else 'A',
           'execution_class': 'B', 'rule_takeover': False,
           'uci': move.uci() if move else None, 'san': san, 'fen_before': before,
           'fen_after': board.fen(en_passant='fen')}
    result['history'].append(row)
    result['steps'] += 1
    result['last_move'] = action
    if move:
        result['moves_uci'].append(move.uci())
        result['event'] = ('白方' if seat == 0 else '黑方') + '走 ' + san
    else:
        result['claim'] = {'action': action, **claim, 'actor': seat}
        result['event'] = '合法申和：' + claim['reason']
    return _sync(result, board)


def rule_action(state: Mapping[str, Any], ordinal: int = 0) -> str:
    """Explicit opponent: bounded one-ply heuristic, never a model fallback."""
    board = _board(state)
    if _terminal(state, board)[0] is not None:
        raise ValueError('No rule action after terminal')
    moves = sorted(board.legal_moves, key=lambda item: item.uci())
    if len(moves) > RULE_CANDIDATE_BUDGET:
        raise ValueError('Rule-opponent fixed candidate budget exceeded')
    ranked, mates = [], []
    for move in moves:
        facts = _move_facts(board, move)
        if facts['checkmate']:
            mates.append(move.uci())
        piece = board.piece_type_at(move.from_square)
        value = VALUES[move.promotion or piece]
        score = (10000 if facts['checkmate'] else 0) + 12 * facts['captured_value']
        score += 10 * (VALUES[move.promotion] - 1) if move.promotion else 0
        score -= 10 * value if facts['resulting_piece_attacked'] else 0
        score += 2 * facts['gives_check'] + 3 * facts['castling']
        rank, file = chess.square_rank(move.to_square), chess.square_file(move.to_square)
        score += (3.5 - abs(file - 3.5) + 3.5 - abs(rank - 3.5)) / 10
        ranked.append((score, move.uci()))
    if mates:
        return sorted(mates)[int(ordinal) % len(mates)]
    claims = _claims(board)
    if claims:
        # A legal immediate mate remains preferable; otherwise this basic
        # opponent accepts a demonstrable draw, without a hidden evaluation.
        return sorted(claims)[0]
    if not ranked:
        raise ValueError('No legal rule-opponent move')
    best = max(score for score, _ in ranked)
    tied = sorted(action for score, action in ranked if score == best)
    return tied[int(ordinal) % len(tied)]


def public(state: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    if kwargs:
        raise TypeError('Unsupported chess public arguments')
    board = _board(state)
    value, termination, result = _terminal(state, board)
    claims = _claims(board) if value is None else {}
    history = copy.deepcopy(state['history'])
    return {'kind': KIND, 'engine_revision': REVISION, 'rules': RULES,
            'board': [[board.piece_at(chess.square(file, rank)).symbol() if
                       board.piece_at(chess.square(file, rank)) else '.'
                       for file in range(8)] for rank in range(7, -1, -1)],
            'board_coordinates': 'Rows are ranks 8→1; columns files a→h; uppercase white, lowercase black.',
            'fen': board.fen(en_passant='fen'), 'initial_fen': state['initial_fen'],
            'moves_uci': list(state['moves_uci']), 'opening_plies': state['opening_plies'],
            'initialization': copy.deepcopy(state['initialization']), 'seed': state['seed'],
            'current_player': 0 if board.turn else 1, 'players': ['白方', '黑方'],
            'check': board.is_check(), 'castling_rights': board.castling_xfen(),
            'en_passant_square': chess.square_name(board.ep_square) if board.ep_square is not None else None,
            'halfmove_clock': board.halfmove_clock, 'fullmove_number': board.fullmove_number,
            'pieces': {chess.square_name(square): piece.symbol() for square, piece in sorted(board.piece_map().items())},
            'claimable_draw_actions': claims, 'claim': copy.deepcopy(state['claim']),
            'outcome': value, 'termination': termination, 'result': result,
            'steps': state['steps'], 'max_plies': state['max_plies'], 'history': history,
            'last_move': state['last_move'], 'event': state['event'], 'handoff': False,
            'opponent': state['opponent'], 'stats': [[state['steps'], '行动次数'], [len(state['moves_uci']), '总半回合']],
            'controller_counts': {'model_decisions': sum(row['controller'] == 'model' for row in history),
                                  'rule_opponent_moves': sum(row['strategy_origin'] == 'rule_opponent' for row in history),
                                  'forced_legal_executions': sum(row['controller'] == 'deterministic_execution' for row in history),
                                  'rule_takeover_count': 0},
            'rule_opponent': {'policy': RULE_POLICY, 'candidate_budget': RULE_CANDIDATE_BUDGET,
                              'lookahead_plies': 1, 'automatic_takeover': False}}


def as_record(state: Mapping[str, Any]) -> dict[str, Any]:
    board = _board(state)
    options, facts = _catalog(state, board)
    if not options:
        raise ValueError('No chess decision at terminal or budget limit')
    obs = public(state)
    # Complete move order and controller attribution remain visible, but every
    # previous before/after FEN would duplicate the same boards quadratically
    # across an episode. Full replay receipts stay in the engine state/public.
    obs['history'] = [{key: row[key] for key in
                       ('action', 'actor', 'controller', 'strategy_origin', 'uci', 'san')}
                      for row in state['history']]
    obs['candidate_facts'] = facts
    ident = f'chess:{state["seed"]}:{state["steps"]}'
    return {'schema_version': 'jev.training.v1', 'id': ident, 'group_id': ident,
            'state': {'role': '你正在替' + ('白方' if board.turn else '黑方') + '行动。',
                      'observation': obs},
            'questions': {'decision': {'type': 'choice', 'instructions':
                '目标是将死对方的王。依据完整公开棋盘、历史和一步确定规则事实选择一个动作 ID。'
                '所有合法走法都在候选中；落点受攻击不等同于必然失子。申和需明确选择对应动作。',
                'criteria': options, 'option_order': list(options)}},
            'labels': {}, 'provenance': {'data_source': 'jev_shared_chess_python_chess',
                'source_id': ident, 'source_revision': REVISION,
                'python_chess_version': chess.__version__,
                'initialization_source': state['initialization']['source']},
            'metadata': {'domain': 'games', 'sub_domain': KIND, 'scenario': 'orthodox_chess',
                         'task_category': 'bounded_decision', 'choice_semantics': 'one_action'}}


class ChessEnvironment:
    """Standard shared environment adapter; custom FEN requires explicit opt-in."""
    kind = KIND

    def reset(self, seed: int | None, options: Mapping[str, Any] | None = None) -> dict:
        settings = dict(options or {})
        if set(settings) - {'opponent', 'max_plies', 'fen', 'allow_custom_fen'}:
            raise ValueError('Unsupported chess reset options')
        custom = settings.pop('allow_custom_fen', False)
        if settings.get('fen') is not None and custom is not True:
            raise ValueError('Explicit FEN requires allow_custom_fen=True; not a seeded RL reset')
        return fresh(seed, **settings)

    def legal_actions(self, state): return choices(state)
    def observe(self, state): return as_record(state)
    as_record = observe
    def step(self, state, action, **kwargs): return step(state, action, **kwargs)
    raw_step = step
    def public(self, state, **kwargs): return public(state, **kwargs)
    def outcome(self, state, side=None): return outcome(state, side)
    def reference_action(self, state): return rule_action(state)


def reference_action(state):
    return rule_action(state)
