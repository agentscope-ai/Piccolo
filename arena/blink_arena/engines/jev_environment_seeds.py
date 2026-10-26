"""Reproducible initial conditions; seed provenance stays outside model input."""
import random

REVISION = 'jev-environment-seed-v1'
SNAKE_REVISION = 'jev-snake-initial-condition-v2'
MAX_SEED = 2**32 - 1


def validate_seed(seed):
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError('种子必须是 0 到 4294967295 的整数')
    return seed


def board_opening(kind, seed, plies=None):
    """Replay legal moves, never fabricate stones or choose a winning solution.

    This is environment initialization, not a model trajectory or model win.
    A standard start remains available through board.fresh(kind) without seed.
    """
    import jev_demo_games as board
    validate_seed(seed)
    if plies is None:
        plies = (10 if kind == 'dots_and_boxes_3x3' else 6) + 2 * (seed % 3)
    if type(plies) is not int or not 0 <= plies <= 20:
        raise ValueError('开局走子数必须是 0 到 20 的整数')
    for attempt in range(64):
        game = board.fresh(kind)
        rng = random.Random(f'{REVISION}/{kind}/{seed}/{attempt}')
        actions = []
        for _ in range(plies):
            options = board.legal(game)
            if game['winner'] or not options:
                break
            action = rng.choice(options)
            actions.append(action)
            game = board.move(game, action)
        if len(actions) == plies and not game['winner']:
            # Historical effects are initialization, not student decisions.
            game.pop('control', None)
            game['_initialization'] = {
                'revision': REVISION, 'seed': seed, 'mode': 'legal_opening',
                'actions': actions, 'plies': len(actions),
                'controller': 'environment_initialization',
                'model_decisions': 0,
            }
            return game
    raise ValueError('不能生成指定步数的合法未结束开局')


def condition_info(kind, seed, *, initialization=None, replay=False):
    """UI/episode provenance only: exposing a hidden deck seed to a model leaks it."""
    if replay:
        return {'revision': REVISION, 'mode': 'dataset_replay', 'seed': None,
                'description': '数据样例回放；初始状态来自原样例'}
    if seed is None:
        return {'revision': REVISION, 'mode': 'standard', 'seed': None,
                'description': '标准开局'}
    validate_seed(seed)
    if initialization is not None:
        return {**initialization, 'description': f"合法开局 · 预走 {initialization['plies']} 手；不计模型决策"}
    notes = {
        'checkers': '标准西洋跳棋开局；种子用于规则对手与对局复现，不随机改摆棋子',
        'go': '标准9×9空盘、白方贴目7.5；种子用于规则对手与复现',
        'xiangqi': '标准中国象棋开局；种子用于规则对手与对局复现，不随机改摆棋子',
        'guess_the_number': '种子控制隐藏目标整数；模型只看到猜测和提示',
        'minesweeper': '首击安全；种子与首次点击共同决定原生布雷，不向模型公开雷图',
        'sudoku': '种子控制原生唯一解数独盘面；候选不读取隐藏答案',
        'uno': '种子控制洗牌和初始顶牌；仅公开己方手牌及对方张数',
        'sokoban_puzzle': '种子控制墙、箱子、目标和玩家位置',
        'snake_navigation': '种子控制蛇头、身体、朝向、障碍和当前及后续食物；开局保留三个安全方向',
        'merge_2048': '种子控制初始数字位置和后续生成',
        'jump_jump': '种子控制平台和落点条件',
        'tetris_placement': '标准空棋盘；种子控制当前方块和后续随机序列',
        'pig_dice': '标准零分开局；种子控制后续骰子序列',
        'zha_jin_hua': '种子控制发牌；未看牌前公开状态可能相同',
        'goofspiel': '种子控制奖分牌顺序；同首张奖分可能重复',
        'liars_dice': '种子控制双方骰子；对手暗骰仍不可见',
        'blackjack': '种子控制发牌和后续抽牌',
        'doudizhu': '种子控制发牌和对手随机选择',
        'texas_holdem': '种子控制洗牌和对手随机选择',
        'property_tycoon': '固定初始棋盘；种子控制后续骰子和机会事件',
    }
    return {'revision': SNAKE_REVISION if kind == 'snake_navigation' else REVISION, 'mode': 'seeded', 'seed': seed,
            'description': notes.get(kind, '种子控制初始条件和随机序列')}
