"""Shared student-visible goals for the repaired training and live games.

The observations and legal candidates come from the production engine. Teacher
search scores, hidden deals and sampled futures never enter this contract.
"""
import copy

REVISION = 'gameplay-visible-intents-20261016-v6-world-contract'
TASKS = {
    'tetris_placement': (
        '棋盘0为空、1为占用，行从上到下、列从左到右。形状坐标[x,y]从左上开始；只能从顶部选择旋转和列后垂直直落，不能横移钻洞。满行立即消除，上方格下落。每次随后独立随机出现七种方块之一，未来方块尚不可见。目标是在40次落块内累计消除4行，并避免顶部堵塞导致无合法落点。考虑空洞、堆积高度、后续可放置空间和消行机会；不要假定未来方块已知。',
        '为存活并最终累计消除4行，当前方块应落在哪个合法位置？'),
    'snake_navigation': (
        '坐标[x,y]，原点左上，x向右、y向下。每步移动一格，不能直接反向；撞墙、障碍或自身则失败。不吃食物时尾部同时前移，因此可以进入当步腾出的旧尾格；吃到食物时身体增长且不移尾。每次吃到食物后在空格随机生成下一份，位置事先未知。foods_eaten是引擎记录的已吃食物数，food_target是本局目标3，steps是已走步数，max_steps是上限80。目标是在步数用尽前达到food_target。兼顾到达当前食物和进食后仍能安全脱身，避免封闭区域和反复循环。',
        '为了安全吃到3份食物，结合身体移动、障碍和剩余步数，下一步往哪走？'),
    'merge_2048': (
        '4×4棋盘，0为空。滑动时所有方块向选定方向压紧，相同相邻方块每次移动最多合并一次。只有棋盘发生变化的方向可选。随后在随机空格生成2（90%）或4（10%）；未来落点不可见。目标是在120步内合成128，棋盘无合法移动则失败。兼顾后续合并、空位、较大方块的排列和避免锁死，不要假定随机落点。',
        '为最终合成128并避免棋盘锁死，现在应向哪个方向滑动？'),
    'doudizhu': (
        '三人斗地主规则仿真，玩家0为地主，两名农民合作；地主先出完则地主胜，任一农民先出完则农民胜。支持单张、对子、三张及带牌、顺子、连对、飞机带翅膀、四带二、炸弹、火箭；2与王不能进顺子。跟牌须同型同张数且主点数更大，炸弹压普通牌，火箭最大。连续两家过牌后最后出牌者重新领出。候选都是合法出法；复杂手牌最多列254种出法和过牌。只知道自己的手牌、公开出牌历史、当前待压牌和对手剩余张数，不知道农民手牌。目标是赢下整局，结合出牌权、剩余牌型和对手威胁选择，必要时可以过牌。',
        '你是地主。根据公开局面和自己的剩余手牌，选择最有利于赢下整局的合法出牌或过牌。不要假设知道农民的隐藏手牌。'),
    'texas_holdem': (
        '双人德扑固定下注档位仿真，只使用虚拟筹码。自己的2张手牌加最多5张公共牌取最佳5张比大小，A2345为最小顺子。候选为弃牌、过牌/跟注、加注。加注支付当前跟注额再额外加40，选项中的金额是本次总支付额，例如跟注10时加注选项显示50。底池和双方剩余筹码见观测。跟注后依次发出翻牌、转牌、河牌，最终摊牌；对手后续下注金额随机取0/10/20/40，不超筹码。加注后对手再跟入最多40。牌不重复，对手手牌和未来公共牌不可见。equity_estimate仅为128次公开信息蒙特卡洛估计，有抽样误差。目标是最大化这手牌最终虚拟筹码的期望收益；结合底池赔率、牌力、未来投入和加注价值，不能据此断言隐藏手牌。',
        '只依据公开信息、手牌和底池，选择期望筹码收益更好的合法操作。'),
    'property_tycoon': (
        '16格地产棋盘，双方起始现金1200；每次前进是两枚独立公平六面骰点数之和。经过起点+200；税务格4/12扣100；机会格2/10等概率得到−80/40/80/120。空地产可以买，自有地产可升至3级，升级费用为地价一半。租金=15+地价×0.15+25×等级。踏上对方地产交租，任一方现金为负立即破产。20回合结束后按现金+各地产价格×(1+0.5×等级)比较资产。目标是获胜，综合剩余回合、租金机会、现金流和破产风险决定买地或升级。cash_reserve仅是旧界面的参考值，不是必须遵守的策略阈值。',
        '为了在避免破产的同时赢得最终资产比较，当前阶段应选择哪一个合法操作？'),
}


def adapt_record(record, *, calibrate=True):
    r = copy.deepcopy(record)
    family = r.get('metadata', {}).get('sub_domain')
    if not family and isinstance(r.get('state'), dict):
        family = r['state'].get('kind') or r['state'].get('observation', {}).get('kind')
    if family == 'terramai_directional':
        from jev_terraria_contract import COMPACT_RECORD_FORMAT, expand_record
        if r.get('state', {}).get('record_format') == COMPACT_RECORD_FORMAT:
            # Re-adaptation must not rebuild the de-duplicated control fields.
            expand_record(r)  # Validate references/version without changing input.
            return r
    if family in TASKS:
        r['state']['rules'], r['questions']['decision']['instructions'] = TASKS[family]
        for key in ('decision_policy', 'planning_assumption', 'planning_task', 'local_task'):
            r['state'].pop(key, None)
        if family == 'property_tycoon':
            r['state']['observation'].pop('cash_reserve', None)
            r['state']['rules'] = r['state']['rules'].split('cash_reserve')[0]
    if family in ('mario_platformer', 'terramai_directional'):
        if family == 'mario_platformer':
            from jev_mario_contract import RULES as world_rules
        else:
            from jev_terraria_contract import RULES as world_rules
        # The world contract selects rules from the observed control interface.
        # Replacing them with the legacy module constant falsely advertises
        # unavailable intents or the wrong action duration to the live model.
        r['state'].setdefault('rules', world_rules)
        observation = r['state']['observation']
        timing = observation.setdefault('timing', {})
        # Older frozen records have no explicit clock contract. Keep their
        # legacy default, but never rewrite an observed realtime/stepped clock.
        if timing.get('clock_contract') not in ('realtime-v1', 'stepped-v1'):
            timing.update(mode='model_step', fps=60,
                          action_frames=timing.get('action_frames', 12 if family == 'mario_platformer' else 36),
                          note='观察和推理时冻结物理；选定意图按期限执行，落地、受阻或危险变化触发重新决策。')
    if family == 'mancala':
        container = r['state'] if 'rules' in r['state'] else r['state']['observation']
        if '玩家索引current_player使用0/1' not in container['rules']:
            container['rules'] += ' 玩家索引current_player使用0/1，分别对应界面玩家一/二。坑编号0是玩家二得分仓，1–6是玩家一小坑，7是玩家一得分仓，8–13是玩家二小坑；播种可以绕圈，单坑种子数可超过初始4颗。'
    if family == 'robot_pick_cola':
        from jev_demo_robot_pick import RULES as robot_rules
        r['state']['rules'] = robot_rules
    if family == 'sokoban_puzzle':
        from jev_showcase_games import SOKOBAN_RULES
        r['state']['rules'] = SOKOBAN_RULES+' push:x:y:direction:goal_x:goal_y 联合选择箱子、最终目标格和推动方向；引擎只执行到站位的可达步行和一次推动，箱子ID与目标子计划持续记录，全部实际移动计入80步预算。'
    if family:
        from jev_game_control import control_view
        r['state']['control'] = control_view(r['state'], family)
    if family == 'terramai_directional':
        from jev_terraria_contract import compact_record, COMPACT_PROMPT_REVISION
        if r['state'].get('prompt_revision') == COMPACT_PROMPT_REVISION:
            r = compact_record(r)
    if calibrate:
        from jev_game_prompt_calibration import apply as calibrate_prompt
        return calibrate_prompt(r)
    return r
