"""Independent CPU rules/replay checks for the shared orthodox-chess module."""
import copy
import json

import chess
import pytest

from blink_arena.engines import jev_chess as game


def play(actions, state=None, controller='model'):
    state = game.fresh() if state is None else state
    for action in actions.split():
        state = game.step(state, action, controller=controller)
    return state


def test_standard_start_full_catalog_and_single_choice():
    state = game.fresh(0)
    options = game.choices(state)
    assert set(options) == {move.uci() for move in chess.Board().legal_moves}
    assert len(options) == 20 and game.actor(state) == 0
    record = game.as_record(state)
    assert record == json.loads(json.dumps(record))
    assert set(record['questions']) == {'decision'}
    assert record['questions']['decision']['criteria'] == options
    assert record['questions']['decision']['option_order'] == sorted(options)
    assert record['labels'] == {}
    assert all(f['certainty'] == 'deterministic_public_one_ply_rules'
               for f in record['state']['observation']['candidate_facts'].values())
    assert game.outcome(state) is None


def test_seed_openings_are_reproducible_diverse_public_and_not_model_moves():
    fingerprints = set()
    for seed in range(65):
        state = game.fresh(seed)
        assert state == game.fresh(seed)
        assert state['steps'] == 0 and state['history'] == []
        assert state['initialization']['opening_is_policy_trajectory'] is False
        assert game.public(state)['moves_uci'] == state['moves_uci']
        assert game.actor(state) == 0
        assert game.outcome(state) is None
        fingerprints.add(state['fen'])
    assert len(fingerprints) == 65


def test_illegal_action_cannot_mutate_or_trigger_fallback():
    state = game.fresh()
    frozen = copy.deepcopy(state)
    for action in ['e2e5', 'e7e5', '0000', 'claim_draw:threefold', 'bad']:
        with pytest.raises(ValueError):
            game.step(state, action)
        assert state == frozen
    with pytest.raises(ValueError):
        game.step(state, 'e2e4', controller='deterministic_execution')


def test_checkmate_is_real_and_seat_relative_even_on_budget_boundary():
    state = play('f2f3 e7e5 g2g4', game.fresh(max_plies=4))
    record = game.as_record(state)
    assert record['state']['observation']['candidate_facts']['d8h4']['checkmate'] is True
    state = game.step(state, 'd8h4')
    assert state['result'] == '0-1' and state['termination'] == 'checkmate'
    assert game.outcome(state, 0) == 'loss' and game.outcome(state, 1) == 'win'
    assert game.choices(state) == {}
    with pytest.raises(ValueError): game.step(state, 'a2a3')


@pytest.mark.parametrize('fen,reason', [
    ('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1', 'stalemate'),
    ('7k/8/8/8/8/8/8/4K3 w - - 0 1', 'insufficient_material'),
])
def test_automatic_draws(fen, reason):
    state = game.fresh(fen=fen)
    assert game.outcome(state) == 'draw'
    assert state['termination'] == reason


def test_castling_and_json_history_preserve_rights():
    state = game.fresh(fen='r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    assert {'e1g1', 'e1c1'} <= set(game.choices(state))
    state = game.step(state, 'e1g1')
    assert game.public(state)['board'][7][6] == 'K'
    assert game.public(state)['board'][7][5] == 'R'
    restored = json.loads(json.dumps(state))
    assert game.public(state) == game.public(restored)
    assert game.choices(state) == game.choices(restored)
    assert game.public(state)['castling_rights'] == 'kq'


def test_en_passant_capture_and_expiry_are_native_rules():
    state = play('e2e4 a7a6 e4e5 d7d5')
    assert game.public(state)['en_passant_square'] == 'd6'
    facts = game.as_record(state)['state']['observation']['candidate_facts']['e5d6']
    assert facts['en_passant'] and facts['captured_piece'] == 'pawn'
    after = game.step(state, 'e5d6')
    assert game.public(after)['pieces'].get('d5') is None
    assert game.public(after)['pieces']['d6'] == 'P'
    ignored = play('g1f3 a6a5', state)
    assert 'e5d6' not in game.choices(ignored)


def test_all_four_promotions_are_choices_and_execute_distinctly():
    state = game.fresh(fen='7k/P7/8/8/8/8/8/7K w - - 0 1')
    for suffix, symbol in [('q', 'Q'), ('r', 'R'), ('b', 'B'), ('n', 'N')]:
        action = 'a7a8' + suffix
        assert action in game.choices(state)
        assert game.public(game.step(state, action))['pieces']['a8'] == symbol
    with pytest.raises(ValueError): game.step(state, 'a7a8')


def test_threefold_requires_explicit_claim_and_preserves_complete_history():
    state = play('g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1')
    claim = 'claim_draw:threefold'
    assert claim in game.choices(state) and game.outcome(state) is None
    with pytest.raises(ValueError): game.step(state, 'claim_draw:threefold:f6g8')
    claimed = game.step(json.loads(json.dumps(state)), claim)
    assert claimed['moves_uci'] == state['moves_uci']
    assert claimed['claim']['intended_uci'] == 'f6g8'
    assert game.outcome(claimed) == 'draw' and claimed['termination'] == 'claimed_threefold'
    now = game.step(state, 'f6g8')
    assert game.outcome(now) is None and 'claim_draw:threefold' in game.choices(now)
    assert game.choices(now) == game.choices(json.loads(json.dumps(now)))
    assert game.outcome(game.step(now, 'claim_draw:threefold')) == 'draw'


def test_fivefold_is_automatic_and_seventyfive_has_priority_over_budget():
    state = play(' '.join(['g1f3 g8f6 f3g1 f6g8'] * 4))
    assert state['termination'] == 'fivefold_repetition' and game.outcome(state) == 'draw'
    state = game.fresh(max_plies=1, fen='7k/8/8/8/8/8/8/R3K3 w - - 149 75')
    state = game.step(state, 'a1a2')
    assert state['termination'] == 'seventyfive_moves' and game.outcome(state) == 'draw'


def test_fifty_moves_current_and_announced_claims_do_not_auto_end():
    state = game.fresh(fen='7k/8/8/8/8/8/8/R3K3 w - - 99 50')
    claim = 'claim_draw:fifty_moves'
    assert claim in game.choices(state) and game.outcome(state) is None
    assert game.outcome(game.step(state, claim)) == 'draw'
    after = game.step(state, 'a1a2')
    assert game.outcome(after) is None and 'claim_draw:fifty_moves' in game.choices(after)
    assert game.outcome(game.step(after, 'claim_draw:fifty_moves')) == 'draw'


def test_budget_is_not_adjudicated_as_win_draw_or_loss():
    state = game.step(game.fresh(max_plies=1), 'e2e4')
    assert game.outcome(state, 0) == game.outcome(state, 1) == 'budget_exhausted'
    assert state['result'] == '*' and state['termination'] == 'ply_budget'


def test_rule_opponent_is_explicit_bounded_and_no_model_takeover():
    state = game.fresh()
    action = game.rule_action(state)
    assert action in game.choices(state) and action == game.rule_action(state)
    after = game.step(state, action, controller='rule_engine')
    assert after['history'][-1]['strategy_origin'] == 'rule_opponent'
    assert after['history'][-1]['policy_decision_class'] == 'C'
    counts = game.public(after)['controller_counts']
    assert counts['rule_opponent_moves'] == 1 and counts['model_decisions'] == 0
    assert counts['rule_takeover_count'] == 0
    assert state['steps'] == 0


def test_unique_legal_move_can_execute_as_b_without_a_model_decision():
    state = game.fresh(fen='7k/8/6K1/8/8/8/8/7R b - - 0 1')
    assert list(game.choices(state)) == ['h8g8']
    after = game.step(state, 'h8g8', controller='deterministic_execution')
    assert after['history'][-1]['policy_decision_class'] == 'B'
    assert game.public(after)['controller_counts']['model_decisions'] == 0
    assert game.public(after)['controller_counts']['forced_legal_executions'] == 1


def test_reference_prefers_demonstrable_mate_to_a_claimable_draw():
    state = game.fresh(fen='7k/5Q2/6K1/8/8/8/8/8 w - - 100 51')
    assert 'claim_draw:fifty_moves' in game.choices(state)
    action = game.rule_action(state)
    assert not action.startswith('claim_draw:')
    assert game.step(state, action)['termination'] == 'checkmate'


def test_environment_adapter_custom_fen_requires_explicit_opt_in():
    env = game.ChessEnvironment()
    fen = '7k/8/8/8/8/8/8/4K3 w - - 0 1'
    with pytest.raises(ValueError): env.reset(0, {'fen': fen})
    assert env.reset(0, {'fen': fen, 'allow_custom_fen': True})['initialization']['source'] == 'explicit_fen'
    state = env.reset(0)
    assert env.reference_action(state) == game.rule_action(state)
    after = env.step(state, 'e2e4', controller='qwen3.8-max')
    assert after['history'][-1]['strategy_origin'] == 'opponent_model'
    assert env.observe(state) == game.as_record(state)


def test_derived_fen_and_journal_cannot_silently_drift():
    state = play('e2e4 e7e5')
    changed = copy.deepcopy(state)
    changed['fen'] = chess.STARTING_FEN
    with pytest.raises(ValueError): game.public(changed)
    changed = copy.deepcopy(state)
    changed['history'][0]['uci'] = 'd2d4'
    with pytest.raises(ValueError): game.as_record(changed)


def test_model_history_keeps_all_moves_without_repeated_full_boards():
    state = play('e2e4 e7e5 g1f3 b8c6')
    obs = game.as_record(state)['state']['observation']
    assert [row['uci'] for row in obs['history']] == state['moves_uci']
    assert all('fen_before' not in row and 'fen_after' not in row for row in obs['history'])
    assert all('fen_before' in row and 'fen_after' in row for row in state['history'])


def test_draw_witnesses_are_facts_for_one_intent_and_preserve_every_legal_move():
    fen = '6rk/6pp/6QQ/3Q4/5Q2/3Q3Q/1Q6/KQQ5 w - - 99 50'
    state = game.fresh(fen=fen)
    board = chess.Board(fen)
    options = game.choices(state)
    ordinary = {action for action in options if not action.startswith('claim_draw:')}
    assert ordinary == {move.uci() for move in board.legal_moves}
    assert len(ordinary) == 137 and len(options) == 138
    action = 'claim_draw:fifty_moves'
    facts = game.as_record(state)['state']['observation']['candidate_facts'][action]
    assert len(facts['announced_witnesses']) == 131 and not facts['available_now']
    assert facts['witness_selection'] == 'lexicographic_uci_first'
    assert facts['intended_uci'] == facts['announced_witnesses'][0]['uci']
    assert facts['intended_uci'] == min(proof['uci'] for proof in facts['announced_witnesses'])
    for proof in facts['announced_witnesses']:
        move = chess.Move.from_uci(proof['uci'])
        assert move in board.legal_moves and proof['san'] == board.san(move)
        board.push(move)
        assert board.is_fifty_moves()
        board.pop()
    claimed = game.step(state, action)
    assert claimed['moves_uci'] == state['moves_uci'] and claimed['fen'] == state['fen']
    assert claimed['current_player'] == state['current_player']
    assert game.outcome(claimed) == 'draw'
    assert '预告 ' + facts['intended_san'] + ' 后申领' in options[action]


def test_old_draw_aliases_and_changed_witness_cannot_bypass_choice_admission():
    state = game.fresh(fen='7k/8/8/8/8/8/8/R3K3 w - - 99 50')
    for alias in ['claim_draw:fifty_moves:a1a2', 'claim_draw:fifty_moves:e1d1']:
        assert alias not in game.choices(state)
        with pytest.raises(ValueError): game.step(state, alias)
    claimed = game.step(state, 'claim_draw:fifty_moves')
    bad = copy.deepcopy(claimed)
    bad['claim']['intended_uci'] = next(proof['uci'] for proof in bad['claim']['announced_witnesses']
                                      if proof['uci'] != bad['claim']['intended_uci'])
    with pytest.raises(ValueError): game.public(bad)
    bad = copy.deepcopy(claimed)
    bad['claim']['announced_witnesses'].pop()
    with pytest.raises(ValueError): game.outcome(bad)
