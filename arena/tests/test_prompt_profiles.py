"""Prompt candidates preserve observable evidence and exact legal choices."""
from copy import deepcopy
import json

import pytest

from blink_arena.engine import get_engine
from blink_arena.paths import REPO
import jev_game_prompt_calibration as calibration

GAMES = ('doudizhu', 'texas_holdem', 'zha_jin_hua', 'minesweeper',
         'uno', 'checkers', 'xiangqi')


@pytest.mark.parametrize('kind', GAMES)
def test_candidate_changes_guidance_but_not_evidence_or_legal_choices(kind, monkeypatch, tmp_path):
    candidate = REPO / 'config/game-prompts.candidate.json'
    baseline = tmp_path / 'unmodified.json'
    baseline.write_text(json.dumps({'schema':'jev.live-prompt-calibration.v1',
                                    'revision':'test-unmodified','games':{}}))
    monkeypatch.setenv('JEV_GAME_PROMPTS_PATH', str(baseline))
    engine = get_engine(kind)
    state = engine.reset(42)
    old = engine.observe(state)
    saved = deepcopy(old)
    monkeypatch.setenv('JEV_GAME_PROMPTS_PATH', str(candidate))
    new = engine.observe(state)
    assert old == saved
    assert old['state'] == new['state']
    a, b = old['questions']['decision'], new['questions']['decision']
    assert a['criteria'] == b['criteria']
    assert a['option_order'] == b['option_order']
    assert b['instructions'] == json.loads(candidate.read_text())['games'][kind]['instructions']
    assert b['instructions'] != a['instructions']
    # Switching back must refresh the cache even within this same process.
    monkeypatch.setenv('JEV_GAME_PROMPTS_PATH', str(baseline))
    assert engine.observe(state) == old


def test_effective_prompt_path_is_available_to_rl_source_binding(monkeypatch, tmp_path):
    target=tmp_path/'frozen.json'
    monkeypatch.setenv('JEV_GAME_PROMPTS_PATH', str(target))
    assert calibration.config_path() == target
