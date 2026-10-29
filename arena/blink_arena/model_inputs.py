"""Public model input projections; native observations and replay stay intact.

Only captured public records are read. Intent views retain decision consequences
and uncertainty; the lossless view additionally preserves all structured fields.
Candidate IDs/order stay unchanged in both views.
"""
from collections import Counter
import copy
import json

LOSSLESS_REVISION = 'jev.model-input.compact.v1'
SELECTED_REVISION = 'jev.model-input.selected.v1'
from .intent_inputs import REVISION
# Preserve the original representation where the paired pilot regressed. This
# selects a presentation only; it never selects an action or edits an outcome.
SELECTED_FORMATS = {'othello_6x6': 'original', 'hex_7x7': 'original',
                    'mario_platformer': 'lossless-v1'}
GAMES = frozenset(('gomoku_19x19', 'mario_platformer', 'terraria_survival'))
OPTIMIZED_GAMES = GAMES | frozenset(('othello_6x6', 'othello_8x8', 'hex_7x7',
    'dots_and_boxes_3x3', 'merge_2048', 'sokoban_puzzle', 'property_tycoon', 'chess', 'pig_dice'))
BOARD_FACT_GAMES = frozenset(('gomoku_19x19', 'othello_6x6', 'othello_8x8', 'hex_7x7', 'dots_and_boxes_3x3'))
KEYED_FACTS = frozenset(('candidate_consequences', 'candidate_effects', 'candidate_box_effects',
                         'candidate_facts', 'push_intents'))
TABLE_RULE = ('紧凑表：columns为列名，rows按列排列；点分列名表示嵌套字段。'
              'defaults是每行共有字段，行内值覆盖它；未提供字段仍为未知。'
              'groups内各表以action ID关联候选；field_aliases指向重复字段的同值路径。'
              '所有坐标、帧数与布尔值保持原义。')


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def _flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        path = prefix + key
        if isinstance(item, dict) and item and '$ref' not in item:
            result.update(_flatten(item, path + '.'))
        else:
            result[path] = item
    return result


def _table(items, *, keyed=False):
    """Factor only fields present in every row; null never means missing."""
    rows = [_flatten(item) for item in items.values()] if keyed else [_flatten(item) for item in items]
    if not rows:
        return items
    # Heterogeneous schemas remain objects: absence is not an observed null.
    if any(set(row) != set(rows[0]) for row in rows):
        if keyed:
            groups = {}
            for key, item in items.items():
                groups.setdefault(tuple(sorted(_flatten(item))), {})[key] = item
            grouped = {'groups': [_table(group, keyed=True) for group in groups.values()]}
            if _size(grouped) < _size(items):
                return grouped
        return {key: _pack(value) for key, value in items.items()} if keyed else [_pack(item) for item in items]
    common = {}
    for key in rows[0]:
        counts = Counter(json.dumps(row[key], ensure_ascii=False, sort_keys=True) for row in rows)
        encoded, count = counts.most_common(1)[0]
        if count == len(rows):
            common[key] = rows[0][key]
    columns = [key for key in rows[0] if key not in common]
    result = {'columns': (['action'] if keyed else []) + columns,
              'rows': [[*([key] if keyed else []), *[_pack(row[col]) for col in columns]]
                       for key, row in zip(items if keyed else range(len(rows)), rows)]}
    if keyed:
        result['key'] = 'action'
    if common:
        result['defaults'] = {key: _pack(value) for key, value in common.items()}
    return result if _size(result) < _size(items) else (
        {key: _pack(value) for key, value in items.items()} if keyed else [_pack(item) for item in items])


def _pack(value):
    if isinstance(value, list):
        if len(value) >= 2 and all(isinstance(row, dict) and row for row in value):
            return _table(value)
        return [_pack(item) for item in value]
    if isinstance(value, dict):
        return {key: (_table(item, keyed=True)
                      if key in KEYED_FACTS and isinstance(item, dict) and item
                      and all(isinstance(row, dict) and row for row in item.values())
                      and 'columns' not in item and 'groups' not in item else _pack(item))
                for key, item in value.items()}
    return value


def game_kind(record):
    state = record.get('state', {})
    kind = (record.get('metadata', {}).get('sub_domain') or state.get('game') or state.get('kind'))
    return 'terraria_survival' if kind == 'terramai_directional' else kind


def _drop_equal(root, source, target):
    """Keep the canonical copy; preserve differing feedback rather than merge."""
    def parent(path):
        obj = root
        for key in path[:-1]:
            obj = obj.get(key, {})
        return obj
    a, b = parent(source), parent(target)
    if source[-1] in a and target[-1] in b and a[source[-1]] == b[target[-1]]:
        a.pop(source[-1])
        root.setdefault('field_aliases', {})['.'.join(source)] = '.'.join(target)


def lossless_record(record):
    """Project a request, never mutate its native observation or replay receipt."""
    kind = game_kind(record)
    if kind not in OPTIMIZED_GAMES or record.get('questions', {}).get('decision', {}).get('type') != 'choice':
        return record
    if record.get('state', {}).get('model_input_revision') in (LOSSLESS_REVISION, REVISION):
        return record
    result = copy.deepcopy(record)
    if kind == 'terraria_survival':
        from jev_terraria_contract import COMPACT_RECORD_FORMAT, expand_record
        if result['state'].get('record_format') == COMPACT_RECORD_FORMAT:
            result = expand_record(result)
    state, question = result['state'], result['questions']['decision']
    criteria = question['criteria']
    if kind in BOARD_FACT_GAMES and set(criteria) <= set(state.get('candidate_consequences', {})):
        facts = state.get('candidate_consequences', {})
        state['candidate_consequences'] = _table(facts, keyed=True)
        question['criteria'] = {action: action for action in criteria}
        question['instructions'] = question['instructions'].replace(
            'option 已列当前公开局面的实际后果', 'candidate_consequences已列当前公开局面的实际后果')
    elif kind == 'mario_platformer' and state.get('observation', {}).get('candidate_effects'):
        observation = state['observation']
        effects = observation.get('candidate_effects', {})
        observation['candidate_effects'] = _table(effects, keyed=True)
        _drop_equal(state, ('control', 'recent_effects'), ('observation', 'action_execution', 'recent_effects'))
        question['criteria'] = {action: mario_label(action, effects.get(action, {}), label)
                                for action, label in criteria.items()}
    elif kind == 'terraria_survival' and state.get('observation', {}).get('control'):
        observation = state['observation']
        for source, target in (
            (('control', 'recent_effects'), ('observation', 'control', 'recent_effects')),
            (('navigation', 'recent_actual_effects'), ('observation', 'last_effects')),
            (('navigation', 'progression'), ('observation', 'progression')),
            (('navigation', 'tool_targets'), ('observation', 'tool_targets')),
            (('navigation', 'objective'), ('observation', 'objective')),
        ):
            _drop_equal(state, source, target)
        # Only execution semantics are shortened. Bound targets, upgrade effects,
        # deadlines and uncertainty are already in the structured public facts.
        question['criteria'] = {action: TERRA_LABELS.get(action, label)
                                for action, label in criteria.items()}
    state = _pack(state)
    state['model_input_revision'] = LOSSLESS_REVISION
    state['encoding'] = TABLE_RULE
    result['state'] = state
    if kind not in GAMES and _size(result) > .9 * _size(record):
        return record
    return result


def compact_record(record):
    """Current intent-oriented input; the native record stays replayable."""
    kind = game_kind(record)
    if kind not in OPTIMIZED_GAMES or record.get('questions', {}).get('decision', {}).get('type') != 'choice':
        return record
    if record.get('state', {}).get('model_input_revision') in (LOSSLESS_REVISION, REVISION):
        return record
    from .intent_inputs import mario_state, terra_state, MARIO_PROMPT, TERRA_PROMPT
    if kind not in GAMES:
        return lossless_record(record)
    result = copy.deepcopy(record)
    state, question = result['state'], result['questions']['decision']
    if kind == 'gomoku_19x19' and 'candidate_consequences' in state:
        state['candidate_consequences'] = {action: {
            'win': fact['wins_now'], 'opponent_wins': fact['opponent_immediate_winning_replies'],
            'line': fact['max_own_contiguous_line_after']}
            for action, fact in state['candidate_consequences'].items()}
        state['prediction_fields'] = '每个候选：win=本步获胜；opponent_wins=本步后对手下一手可直接获胜的坐标；line=本方最长连续子数。坐标与棋盘一致，均为确定公开规则事实，不是整局胜率。'
        question['criteria'] = {action: '落子' + action for action in question['criteria']}
        question['instructions'] = question['instructions'].replace(
            'option 已列当前公开局面的实际后果', 'candidate_consequences已列当前公开局面的实际后果')
    elif kind == 'mario_platformer' and state.get('observation', {}).get('candidate_effects'):
        effects = state['observation']['candidate_effects']
        result['state'] = mario_state(state)
        question['instructions'] = MARIO_PROMPT
        question['criteria'] = {action: mario_label(action, effects.get(action, {}), label)
                                for action, label in question['criteria'].items()}
    elif kind == 'terraria_survival' and state.get('observation', {}).get('control'):
        from jev_terraria_contract import COMPACT_RECORD_FORMAT, expand_record
        if state.get('record_format') == COMPACT_RECORD_FORMAT:
            result = expand_record(result)
            state, question = result['state'], result['questions']['decision']
        result['state'] = terra_state(state)
        question['instructions'] = TERRA_PROMPT
        question['criteria'] = {action: TERRA_LABELS.get(action, label)
                                for action, label in question['criteria'].items()}
    else:
        return lossless_record(record)
    result['state']['model_input_revision'] = REVISION
    return result


def project_record(record, input_format='selected-v1'):
    if input_format == 'selected-v1':
        input_format = SELECTED_FORMATS.get(game_kind(record), 'intent-v2')
    if input_format == 'original':
        return record
    if input_format in ('compact-v1', 'lossless-v1'):
        return lossless_record(record)
    if input_format == 'intent-v2':
        return compact_record(record)
    raise ValueError('unknown_model_input_format')


def mario_label(action, facts, original):
    if action.startswith('cross_visible_right:') and 'intent' in facts:
        intent = facts['intent']
        target, landing = intent['obstacle'], intent['landing_region']
        return (f"越过指定{target['kind']}[{target['left']},{target['right']}]，"
                f"落地区x=[{landing['left']},{landing['right']}]、y={landing['top']}；"
                f"走到起跳位、等窗口、跳一次；期限{intent['deadline_frames']}帧")
    return MARIO_LABELS.get(action, original)


MARIO_LABELS = {
    'right': '向右跑', 'left': '向左跑',
    'jump_right': '向右跳', 'jump_left': '向左跳', 'jump': '原地跳',
    'wait': '松方向，等待落地',
    'cross_right': '当前站位等安全窗口，向右跳一次，最多180帧',
    'cross_right_guard': '向右越障一次；落地后授权最多8秒原位跳防御，直到新意图到达',
    'cross_gap_right': '走到可见坑的起跳窗口，向右跨坑一次，最多180帧',
    'wait_safe': '原地等可见安全窗口，最多180帧，不自动前进',
}

TERRA_LABELS = {
    'explore_right': '向右探索当前可见路段；前方威胁时返回',
    'explore_left': '向左返回当前可见路段；威胁或未知边界时返回',
    'approach_guardian': '接近已见守门怪至剑框射程，不攻击',
    'fight_guardian': '攻击绑定的当前可见守门怪，不改打小怪',
    'fight_nearest': '攻击绑定的最近可见敌人，不换敌',
    'return_surface': '返回本意图的有效已见地表锚点，落地结束',
    'cross_gap_right': '向右跨过当前可见坑，首次落地结束',
    'clear_right': '挖通右侧可见障碍并前进一个路段',
    'pass_enemy_right': '绕过绑定敌人至其右侧8格，不攻击',
    'retreat_left': '向左撤离最近可见威胁7格，不战斗',
    'collect_visible': '采集绑定的一个可见目标；食物→装备→宝箱→矿物，同类最近',
    'collect_visible_gem': '采集绑定的最近可见宝石矿(8)，不采其他矿',
    'recover': '松键等恢复或重生，受伤返回，不格挡',
    'reach_known_goal': '进入已见门；须先解锁，遇威胁返回',
}
