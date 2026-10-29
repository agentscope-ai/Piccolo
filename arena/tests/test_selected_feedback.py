from copy import deepcopy
import json
from blink_arena.engine import get_engine
import jev_selected_games as games


def test_mine_retry_feedback_is_public_persistent_and_replayable(monkeypatch):
    engine = get_engine('minesweeper')
    state = engine.reset(2026102194)
    for action in ('[3 3]', '[0 4]', '[1 4]'):
        state = engine.step(state, action)
    view = engine.public(state)
    assert not view['outcome'] and view['invalid_retry_remaining'] == 0
    assert view['action_feedback'] == [{'action': '[1 4]', 'reason': 'You hit a mine at (1, 4).'}]
    assert view['board'][1][4] is None
    assert '[1 4]' in engine.legal_actions(state)  # native candidates remain exact
    assert engine.observe(state)['state']['observation'] == view
    with games._LOCK:
        games._CACHE.clear()
    assert engine.public(json.loads(json.dumps(state))) == view
    native, selected, rng = games._load(state)
    fake = deepcopy(native)
    for r in range(fake.rows):
        for c in range(fake.cols):
            if not fake.revealed[r][c]:
                fake.grid[r][c] = 7
    with monkeypatch.context() as patch:
        patch.setattr(games, '_runtime', lambda *args: (fake, selected, rng))
        assert engine.public(state) == view
    terminal = engine.step(state, '[1 4]')
    assert engine.outcome(terminal) == 'loss'
    assert engine.public(terminal)['action_feedback'] == view['action_feedback']
    assert engine.public(terminal)['invalid_retry_remaining'] == 0


def test_valid_move_resets_retry_but_does_not_erase_known_mine():
    engine = get_engine('minesweeper'); state = engine.reset(2026102194)
    for action in ('[3 3]', '[0 4]', '[1 4]'):
        state = engine.step(state, action)
    native, _, _ = games._load(state)
    safe = next(f'[{r} {c}]' for r in range(native.rows) for c in range(native.cols)
                if not native.revealed[r][c] and native.grid[r][c] != -1)
    state = engine.step(state, safe)
    view = engine.public(state)
    assert view['invalid_retry_remaining'] == 1
    assert view['action_feedback'][0]['action'] == '[1 4]'


def test_sudoku_wrong_answer_feedback_survives_cell_selection():
    engine = get_engine('sudoku'); state = engine.reset(42)
    for cell in engine.legal_actions(state):
        chosen = engine.step(state, cell)
        native, (r, c), _ = games._load(chosen)
        wrong = next((a for a in engine.legal_actions(chosen)
                      if a.startswith('fill:') and int(a[5:]) != native.full_grid[r][c]), None)
        if wrong:
            break
    assert wrong
    rejected = engine.step(chosen, wrong)
    view = engine.public(rejected)
    assert view['action_feedback'] and view['invalid_retry_remaining'] == 0
    assert view['board'][r][c] == 0
    assert view['action_feedback'][0]['action'] == f'[{r+1} {c+1} {int(wrong[5:])}]'
    selected = engine.step(rejected, cell)
    assert engine.public(selected)['action_feedback'] == view['action_feedback']
    assert engine.public(selected)['invalid_retry_remaining'] == 0
    assert engine.outcome(engine.step(selected, wrong)) == 'loss'
