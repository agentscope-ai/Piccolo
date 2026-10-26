"""Eight selected GitHub games, using their original OpenSpiel/TextArena/RLCard rules.

Only JSON action journals are persisted. A bounded cache retains read-only native
states; transitions clone before execution. TextArena's global RNG is isolated
under a lock and restored after each call. No native private state is serialized
into public(), observe(), candidate filtering or browser payloads.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from collections import OrderedDict
import importlib.metadata
import random
from threading import RLock

REVISION = 'selected-games-v1'
# id, display name, upstream, upstream id, decision limit, seats
GAMES = {
    'checkers': ('西洋跳棋', 'openspiel', 'checkers', 300, 2),
    'xiangqi': ('中国象棋', 'openspiel', 'xiangqi', 400, 2),
    'guess_the_number': ('猜数字', 'textarena', 'GuessTheNumber-v0', 10, 1),
    'minesweeper': ('扫雷', 'textarena', 'Minesweeper-v0', 100, 1),
    'sudoku': ('数独', 'textarena', 'Sudoku-v0', 240, 1),
    'uno': ('UNO纸牌', 'rlcard', 'uno', 300, 2),
}
PRIVATE = frozenset(('uno',))
RULES = {
    'checkers': '8×8西洋跳棋，玩家0为白方o、玩家1为黑方+，8和*分别表示白王和黑王。按OpenSpiel原生规则移动、强制吃子和升王。双方轮流操作，不能走时判负；重复及和棋按原生规则。目标是获胜。',
    'go': '9×9围棋，玩家0执黑、玩家1执白。按OpenSpiel原生提子、劫、禁入点和计分规则。可停着，双方连续停着后原生计分。白方贴目见komi。目标是赢得终局。',
    'xiangqi': '9×10中国象棋，玩家0为红方大写字母、玩家1为黑方小写字母，候选坐标为从上往下的0起始行列。按OpenSpiel原生将军、将死、蹩马腿、塞象眼、炮架和将帅不能照面规则。只可选择合法着法。目标是获胜。',
    'guess_the_number': '目标为1到20的整数，最多10次猜测，不可重复。只公开每次猜测后更大或更小的提示；目标值不可见。猜中获胜。',
    'minesweeper': '按TextArena原生规则揭开格子：首击后布雷并保证首击邻域安全，0格连锁展开，数字为周围雷数。候选包含全部未揭开格子，不据隐藏雷图筛选。揭开所有安全格才算获胜。原生引擎允许一次无效动作重试，连续无效或用尽预算失败；已反馈的雷格应避开。',
    'sudoku': '9×9数独。每行、列、3×3宫包含1到9各一次。先选择空格，再选择数字；候选数字仅按公开盘面排除冲突，不查询标准答案。可返回重选空格。原生引擎检查填数正确性，填满正确盘面才胜；原生引擎允许一次错误重试，连续错误或预算耗尽失败。',
    'uno': 'RLCard双人UNO原生规则：按颜色或牌面跟牌，支持反转、跳过、加二、变色和加四；原生draw和变色动作保留。只公开自己的手牌、顶牌、公开出牌及对手张数，其他手牌和牌堆顺序不可见。先出完手牌获胜。',
}
_LOCK = RLock()


@contextmanager
def _rng(state=None):
    with _LOCK:
        previous = random.getstate()
        if state is not None:
            random.setstate(state)
        try:
            yield
        finally:
            random.setstate(previous)


_CACHE = OrderedDict()


def _native_done(kind, native):
    source = GAMES[kind][1]
    return (native.is_terminal() if source == 'openspiel' else
            native.is_over() if source == 'rlcard' else native.state.done)


def _runtime(kind, seed, history):
    """Reconstruct iteratively from a cached prefix; native states stay read-only."""
    with _rng():
        key = (kind, seed, history)
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        source, upstream = GAMES[kind][1:3]
        prefix = None
        for length in range(len(history)-1, -1, -1):
            parent = _CACHE.get((kind, seed, history[:length]))
            if parent is not None:
                prefix = length
                native, selected, rng_state = parent
                native = deepcopy(native)
                random.setstate(rng_state)
                break
        if prefix is None:
            prefix, selected = 0, None
            if source == 'openspiel':
                import pyspiel
                native = pyspiel.load_game(upstream).new_initial_state()
            elif source == 'rlcard':
                import rlcard
                native = rlcard.make(upstream, config={'seed': seed})
                native.reset()
            else:
                import textarena as ta
                native = ta.make(upstream + '-raw')
                native.reset(num_players=GAMES[kind][4], seed=seed)
        for action in history[prefix:]:
            if _native_done(kind, native) or action not in _native_choices(kind, native, selected):
                raise ValueError('Invalid native action journal')
            if source == 'openspiel':
                native.apply_action(int(action))
            elif source == 'rlcard':
                native.step(int(action))
            elif kind == 'sudoku':
                if action.startswith('cell:'):
                    _, r, c = action.split(':'); selected = (int(r), int(c))
                elif action == 'back':
                    selected = None
                else:
                    native.step(f'[{selected[0]+1} {selected[1]+1} {int(action.split(":")[1])}]')
                    selected = None
            else:
                native.step(action)
        value = (native, selected, random.getstate())
        _CACHE[key] = value
        while len(_CACHE) > 128:
            _CACHE.popitem(last=False)
        return value


def _load(state):
    if state.get('engine_revision') != REVISION or state.get('kind') not in GAMES:
        raise ValueError('Unsupported selected-game state')
    if type(state.get('steps')) is not int or state['steps'] != len(state.get('_history', ())):
        raise ValueError('Invalid action journal')
    if (not 0 <= state['steps'] <= GAMES[state['kind']][3]
            or type(state.get('_seed')) is not int or not 0 <= state['_seed'] <= 4294967295
            or any(not isinstance(a,str) or len(a)>256 for a in state['_history'])):
        raise ValueError('Invalid seed or journal bounds')
    return _runtime(state['kind'], state['_seed'], tuple(state['_history']))


def actor(state):
    native, _, _ = _load(state)
    source = GAMES[state['kind']][1]
    if source == 'openspiel':
        return max(0, native.current_player())
    if source == 'rlcard':
        return native.get_player_id()
    return native.state.current_player_id


def _terminal(state):
    native, _, _ = _load(state)
    return _native_done(state['kind'], native)


def outcome(state, side=None):
    native, _, _ = _load(state)
    kind = state['kind']; side = 0 if side is None else side
    if type(side) is not int or not 0 <= side < GAMES[kind][4]:
        raise ValueError('Invalid controlled seat')
    if not _terminal(state):
        return 'budget_exhausted' if state['steps'] >= GAMES[kind][3] else None
    source = GAMES[kind][1]
    if source == 'openspiel':
        reward = native.returns()[side]
    elif source == 'rlcard':
        reward = native.get_payoffs()[side]
    else:
        won = (native.game_number in native.guessed_numbers if kind == 'guess_the_number' else
               native._is_solved() if kind == 'minesweeper' else
               native.state.game_state['completed'])
        return 'win' if won else 'loss'
    return 'win' if reward > 0 else 'loss' if reward < 0 else 'draw'


def fresh(kind, seed, options=None):
    from jev_engine_environment import validate_seed
    validate_seed(seed)
    if seed is None or kind not in GAMES:
        raise ValueError('Explicit seed and known selected game required')
    options = dict(options or {})
    if set(options) - {'opponent'} or options.get('opponent', 'human') not in ('human', 'rule'):
        raise ValueError('Unsupported reset options')
    state = {'kind': kind, 'engine_revision': REVISION, '_seed': seed, '_history': [],
             '_opponent': options.get('opponent', 'human'), 'steps': 0, 'handoff': False, 'outcome': None}
    _load(state)
    if state['_opponent']=='rule' and GAMES[kind][4]>1 and actor(state)!=0:
        return step(state, rule_action(state))
    return state


def choices(state):
    native, selected, _ = _load(state)
    if state.get('handoff') or outcome(state):
        return {}
    return _native_choices(state['kind'], native, selected)


def _native_choices(kind, native, selected):
    source = GAMES[kind][1]
    if source == 'openspiel':
        return {str(a): native.action_to_string(native.current_player(), a) for a in native.legal_actions()}
    if source == 'rlcard':
        player = native.get_state(native.get_player_id())
        from rlcard.games.uno.utils import ACTION_LIST
        return {str(a): ACTION_LIST[a] for a in player['legal_actions']}
    if kind == 'guess_the_number':
        return {f'[{n}]': str(n) for n in range(native.min_number, native.max_number+1)
                if n not in native.guessed_numbers}
    if kind == 'minesweeper':
        return {f'[{r} {c}]': f'揭开 {r+1}行 {c+1}列' for r in range(native.rows)
                for c in range(native.cols) if not native.revealed[r][c]}
    board = native.state.game_state['board']
    if selected is None:
        return {f'cell:{r}:{c}': f'选择 {r+1}行 {c+1}列' for r in range(9) for c in range(9)
                if board[r][c] == 0}
    r, c = selected
    return {**{f'fill:{n}': f'填入 {n}' for n in range(1, 10) if native.is_safe(board, r, c, n)},
            'back': '返回选择空格'}


def reveal(state):
    if not state.get('handoff') or state['kind'] not in PRIVATE:
        raise ValueError('No pending seat handoff')
    return {**state, 'handoff': False}


def sealed(state):
    return False


def rule_action(state, ordinal=0):
    options = list(choices(state))
    if not options:
        raise ValueError('No legal action')
    # This baseline never inspects the opponent's hand, pending simultaneous
    # move, puzzle solution or mine map. Its identity is exposed in metadata.
    return random.Random(f'selected-legal-random-v1/{state["_seed"]}/{state["steps"]}/{ordinal}').choice(options)


def step(state, action, **kwargs):
    kwargs = dict(kwargs)
    if kwargs.pop('card_ids', None) is not None or kwargs.pop('controller', 'model') not in ('human', 'model') or kwargs:
        raise ValueError('Unsupported action arguments')
    if not isinstance(action, str) or action not in choices(state):
        raise ValueError('Illegal action')
    before_actor = actor(state)
    result = {**state, '_history': [*state['_history'], action], 'steps': state['steps']+1}
    result['outcome'] = outcome(result)
    if state['_opponent'] == 'rule' and GAMES[state['kind']][4] > 1:
        while not result['outcome'] and actor(result) != 0:
            automatic = rule_action(result)
            result = {**result, '_history': [*result['_history'], automatic], 'steps': result['steps']+1}
            result['outcome'] = outcome(result)
    result['handoff'] = (state['kind'] in PRIVATE and not result['outcome']
                         and actor(result) != before_actor and state['_opponent'] == 'human')
    return result


def _public_feedback(native):
    """Keep only errors already delivered to this player; never inspect solutions."""
    from textarena import ObservationType
    action = None
    feedback = {}
    for sender, message, category in native.state.observations.get(native.state.current_player_id, []):
        if category == ObservationType.PLAYER_ACTION:
            action = message
        elif category == ObservationType.GAME_ADMIN and action and 'Reason: ' in message:
            reason = message.split('Reason: ', 1)[1].split(' Please resubmit', 1)[0]
            feedback[action] = {'action': action, 'reason': reason}
    terminal = native.state.game_info.get(native.state.current_player_id, {})
    if terminal.get('invalid_move') and action and terminal.get('reason', '').startswith('Invalid Move: '):
        feedback[action] = {'action': action, 'reason': terminal['reason'].removeprefix('Invalid Move: ')}
    if not feedback:
        return {}
    return {'action_feedback': list(feedback.values()),
            'invalid_retry_remaining': 0 if native.state.done else max(0, native.state.error_allowance-native.state.error_count)}


def public(state, **kwargs):
    if set(kwargs) - {'include_trace'}:
        raise TypeError('Unsupported public options')
    native, selected, _ = _load(state)
    kind = state['kind']
    view = {'kind': kind, 'name': GAMES[kind][0], 'steps': state['steps'],
            'player': actor(state), 'seat_count': GAMES[kind][4], 'outcome': outcome(state),
            'handoff': bool(state.get('handoff')), 'rules': RULES[kind]}
    names={'checkers':('白方','黑方'),'go':('黑方','白方'),'xiangqi':('红方','黑方')}.get(kind,('玩家1','玩家2'))
    view['player_name']=names[view['player']]
    if view['outcome']:
        view['outcome_label'] = ('达到决策预算，未完成对局' if view['outcome']=='budget_exhausted' else
            '平局' if view['outcome']=='draw' else
            (names[0]+'获胜' if view['outcome']=='win' else names[1]+'获胜') if GAMES[kind][4]>1 else
            '挑战完成' if view['outcome']=='win' else '挑战失败')
    if view['handoff']:
        return view
    source = GAMES[kind][1]
    if source == 'openspiel':
        view['board_text'] = native.observation_string(max(0, native.current_player()))
        if kind == 'go':
            view.update(size=9, komi=native.get_game().get_parameters().get('komi', 7.5))
    elif kind == 'guess_the_number':
        view.update(history=[list(item) for item in native.state.game_state['guess_history']], minimum=native.min_number,
                    maximum=native.max_number, remaining=max(0, native.max_turns-state['steps']))
    elif kind == 'minesweeper':
        view.update(rows=native.rows, cols=native.cols, mine_count=native.num_mines,
                    board=[[native.grid[r][c] if native.revealed[r][c] else None
                            for c in range(native.cols)] for r in range(native.rows)])
    elif kind == 'sudoku':
        view.update(board=deepcopy(native.state.game_state['board']), selected=list(selected) if selected is not None else None,
                    phase='select_number' if selected is not None else 'select_cell')
    else:
        player = native.get_state(native.get_player_id())['raw_obs']
        # RLCard mutates a wild card's color after it is played, but its cached
        # `.str` (raw_obs['target']) retains the old color. Read the public top
        # card dynamically so the displayed color agrees with legal actions.
        view.update(hand=list(player['hand']), target=native.game.round.target.get_str(),
                    hand_counts=[len(p.hand) for p in native.game.players],
                    played_cards=list(player['played_cards']))
    if source == 'textarena':
        view.update(_public_feedback(native))
    return view


def as_record(state):
    options = choices(state)
    if not options:
        raise ValueError('No decision at handoff or terminal state')
    if len(options) > 254:
        raise ValueError('Choice exceeds the single-token candidate budget')
    ident = f'selected:{state["kind"]}:{state["_seed"]}:{state["steps"]}'
    source = GAMES[state['kind']][1]
    package = {'openspiel': 'open-spiel', 'textarena': 'textarena', 'rlcard': 'rlcard'}[source]
    record = {'schema_version': 'jev.training.v1', 'id': ident, 'group_id': ident,
            'state': {'rules': RULES[state['kind']], 'observation': public(state)},
            'questions': {'decision': {'type': 'choice', 'instructions': '依据当前玩家可见信息，选择一个合法动作。',
                         'criteria': options, 'option_order': list(options)}}, 'labels': {},
            'provenance': {'data_source': source, 'source_id': ident,
                           'source_revision': package + ':' + importlib.metadata.version(package),
                           'engine_revision': REVISION, 'public_view_revision': 'selected-feedback-v2'},
            'metadata': {'domain': 'games', 'sub_domain': state['kind'],
                         'scenario': GAMES[state['kind']][0], 'task_category': 'bounded_decision'}}

    from jev_game_prompt_calibration import apply
    return apply(record)


class SelectedEnvironment:
    def __init__(self, kind): self.kind = kind
    def _check(self, state):
        if state.get('kind') != self.kind: raise ValueError('Engine/state kind mismatch')
    def reset(self, seed, options=None): return fresh(self.kind, seed, options)
    def legal_actions(self, state): self._check(state); return choices(state)
    def observe(self, state): self._check(state); return as_record(state)
    def step(self, state, action, **kwargs): self._check(state); return step(state, action, **kwargs)
    def public(self, state, **kwargs): self._check(state); return public(state, **kwargs)
    def outcome(self, state, side=None): self._check(state); return outcome(state, side)
    def reveal(self, state): self._check(state); return reveal(state)
    def sealed(self, state): self._check(state); return sealed(state)


def register_games(register, spec_class):
    repos = {'openspiel': 'google-deepmind/open_spiel', 'textarena': 'TextArena/TextArena', 'rlcard': 'datamllab/rlcard'}
    for kind, (name, source, upstream, limit, seats) in GAMES.items():
        register(spec_class(kind, name, SelectedEnvironment(kind), family='selected', limit=limit,
            goal=RULES[kind], seat_count=seats, renderer='selected',
            opponent_modes=('rule_engine', 'qwen3.8-max') if seats > 1 else ('environment',),
            rl_runner='jev_selected_games_rl:play', rl_verify='jev_selected_games_rl:verify',
            source_modules=('jev_selected_games', 'jev_selected_games_rl'),
            capabilities=('seeded_reset', 'choice', 'public_observation', 'exact_replay') +
                         (('private_turns',) if kind in PRIVATE else ()),
            scene={'name': name, 'mode': 'game', 'note': RULES[kind], 'featured': True,
                   'play_category': 'board' if source=='openspiel' else 'table' if seats>1 else 'arcade',
                   'supports_opponent': seats > 1, 'source_label': source + ' · original rules',
                   'url': 'https://github.com/' + repos[source]}))
