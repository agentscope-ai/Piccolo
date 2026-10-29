"""Decision views for small models, derived exclusively from public engine facts.

Keep goal, consequences and uncertainty close to the intent. The executor's
paths, hitbox rectangles and bookkeeping remain in native observations/replay.
"""
import copy

REVISION = 'jev.model-input.intent.v2'


def pick(value, keys):
    return {key: copy.deepcopy(value[key]) for key in keys if key in value}


def feedback(control):
    result = {
        **pick(control, ('status', 'selected_intent', 'current_goal', 'target',
                         'failure_reason', 'no_progress_count', 'failed_targets', 'remaining_frames')),
        'recent_effects': [pick(row, ('action', 'delta_x', 'delta_y', 'frames', 'event',
            'status', 'failure_reason', 'meaningful_progress', 'hp_delta', 'deaths',
            'material_gathered', 'net_terrain_changes', 'horizontal_target_reached',
            'danger_event')) for row in control.get('recent_effects', [])],
    }
    subgoal = control.get('subgoal')
    if isinstance(subgoal, dict):
        result['intent'] = subgoal.get('intent')
        if subgoal.get('target') != control.get('target'):
            result['subgoal'] = copy.deepcopy(subgoal)
    elif subgoal is not None:
        result['subgoal'] = copy.deepcopy(subgoal)
    return result


def arrival(value):
    return {**pick(value, ('rejected_count',)), 'recent_rejections': [pick(row,
        ('action', 'reason', 'observation_frame', 'arrival_frame', 'requires_new_observation'))
        for row in value.get('recent_rejections', [])]}


def mario_forecast(facts):
    names = {'predicted_player': 'landing', 'landed': 'landed', 'landing_frame': 'landing_frame',
             'blocked': 'blocked', 'predicted_stomps': 'stomps', 'can_restart_jump': 'can_jump',
             'frames': 'limit_frames', 'plant_phase_counts': 'plant_phase_counts',
             'explicit_landing_guard': 'landing_guard'}
    result = {short: copy.deepcopy(facts[key]) for key, short in names.items() if key in facts}
    risks = {'head_collision': 'head', 'plant_or_enemy_risk': 'collision', 'visible_pit_fall': 'pit',
             'unknown_terrain': 'unknown', 'landing_plant_exposure': 'flower_at_landing'}
    result['risk'] = {short: facts[key] for key, short in risks.items() if key in facts}
    for original, short in [('after_assumed_60_frame_wait', 'after_wait_1s'),
                            ('post_action_idle_60_frames', 'idle_1s')]:
        if original in facts:
            result[short] = {name: facts[original][key] for key, name in risks.items() if key in facts[original]}
    if 'latency_scenarios' in facts:
        result['delay_scenarios'] = [{short: row[key] for key, short in (
            ('assumed_wait_seconds', 'wait_s'), ('arrival_dynamic_risk_estimate', 'arrival_risk'),
            ('post_landing_idle_risk_estimate', 'idle_risk'), ('post_landing_pit', 'pit')) if key in row}
            for row in facts['latency_scenarios']]
    # Preserve timing-to-threat estimates; their uncertainty is stated once.
    if 'enemy_contact' in facts:
        result['enemy_contact'] = [{'x': row['x'], 'in_frames': row['contact_frames_estimate']}
                                   for row in facts['enemy_contact']]
    if 'continuation' in facts:
        c = facts['continuation']
        result['next_jump'] = {short: c[key] for key, short in (
            ('available', 'available'), ('headroom_pixels', 'headroom'), ('unknown_frontier', 'unknown')) if key in c}
        for key, short in (('visible_forward_landing_regions', 'forward'), ('visible_retreat_landing_regions', 'retreat')):
            if key in c:
                result['next_jump'][short] = [pick(row, ('left', 'right', 'top')) for row in c[key]]
    if 'intent' in facts:
        intent = facts['intent']
        result['target'] = {
            'obstacle': pick(intent['obstacle'], ('kind', 'left', 'right')),
            'landing_region': pick(intent['landing_region'], ('left', 'right', 'top')),
            **pick(intent, ('deadline_frames', 'max_wait_frames')),
        }
        if 'approach_frames' in intent.get('launch_window', {}):
            result['target']['approach_frames'] = intent['launch_window']['approach_frames']
    if 'complete_jump_projection' in facts:
        result['complete_jump_projection'] = mario_forecast(facts['complete_jump_projection'])
    if 'jump_now_projection' in facts:
        result['jump_now_projection'] = copy.deepcopy(facts['jump_now_projection'])
    if 'gap' in facts:
        result['gap'] = copy.deepcopy(facts['gap'])
    if facts.get('certainty') not in (
        'visible_geometry_with_plant_phase_bounds_and_enemy_velocity_estimate',
        'visible_geometry_with_observed_dynamic_estimates; target_revalidated_during_execution'):
        result.update(pick(facts, ('certainty',)))
    return result


def mario_state(old):
    o = old['observation']
    result = {
        'goal': '活着到达右侧旗杆；金币/蘑菇是额外收益，不能替代通关。',
        'rules': MARIO_RULES,
        'world': pick(o, ('player', 'map', 'enemies', 'coins', 'powerups', 'goal_x',
                         'progress', 'score', 'frame', 'outcome')),
        'plants': [pick(p, ('pipe_x', 'x', 'y', 'width', 'height', 'emerged')) for p in o.get('plants', [])],
        'recent_actions': copy.deepcopy(o.get('last_actions', [])),
        'recent_positions': copy.deepcopy(o.get('recent_player_positions', [])),
        'feedback': feedback(o.get('action_execution', {})),
        'arrival_feedback': arrival(o.get('decision_arrival', {})),
        'navigation': copy.deepcopy(old.get('navigation', {})),
        'timing': pick(o.get('timing', {}), ('clock_contract', 'inference_world_paused',
            'waiting_input', 'frames_per_second', 'action_frames_by_action', 'jump_ends_on')),
        'predictions': {action: mario_forecast(facts) for action, facts in o['candidate_effects'].items()},
        'prediction_scope': MARIO_PREDICTIONS,
    }
    # An active selected guard is decision relevant, not internal bookkeeping.
    for source in (o.get('action_execution', {}), old.get('control', {})):
        for key in ('selected_landing_guard', 'landing_guard', 'guard'):
            if key in source:
                result['feedback'][key] = copy.deepcopy(source[key])
    return result


def attack_forecast(value):
    if not isinstance(value, dict):
        return value
    return pick(value, ('geometry_exact', 'hitting_directions', 'geometrically_in_range',
                        'strict_overlap', 'uncertainty'))


def terra_state(old):
    o, nav = old['observation'], old.get('navigation', {})
    combat = []
    for row in nav.get('combat', []):
        fact = pick(row, ('enemy', 'horizontal_body_gap_tiles', 'vertical_body_gap_tiles',
            'previous_failed_attempts', 'contact_damage_under_current_buffs',
            'minimum_attacks_to_defeat_if_all_hit', 'hits_to_player_death_without_healing', 'uncertainty'))
        if 'native_attack' in row:
            fact['attack'] = attack_forecast(row['native_attack'])
        combat.append(fact)
    guardian = pick(nav.get('guardian_target', {}), ('target', 'visible', 'approach_candidate_available',
        'fight_candidate_available', 'observed_age_frames', 'at_last_seen_position_without_reacquisition', 'uncertainty'))
    if 'native_attack' in nav.get('guardian_target', {}):
        guardian['attack'] = attack_forecast(nav['guardian_target']['native_attack'])
    motion = nav.get('enemy_motion', {})
    collection = {action: pick(value, ('target', 'candidate_available', 'successful_collection_effect',
        'previous_failed_attempts', 'previous_failure_count', 'uncertainty')) for action, value in nav.get('collection', {}).items()}
    result = {
        'goal': '玩家参与击败指定守门怪→gate_unlocked=true→活着进入已见门→原生wins增加。',
        'rules': TERRA_RULES,
        'world': pick(o, ('player', 'map', 'equipment', 'objective', 'progression', 'wins', 'deaths',
            'known_goal', 'known_guardians', 'last_known_surface', 'active_buffs', 'recovery_wait_frames',
            'visible_collectibles', 'visible_equipment_drops', 'frame', 'episode_terminal')),
        'combat': combat,
        'guardian': guardian,
        'collection': collection,
        'upgrades': copy.deepcopy(nav.get('upgrade_rules', {})),
        'movement': {**pick(motion, ('target', 'completion_check_is_exact', 'retreat_boundary_x', 'pass_boundary_x', 'uncertainty')),
            **{action: pick(motion[action], ('target_id', 'already_satisfied', 'completion_margin_tiles',
                'strict_completion_predicate', 'candidate_omitted')) for action in ('retreat_left', 'pass_enemy_right') if action in motion},
            **pick(nav, ('foot_y', 'below_last_seen_surface_tiles', 'nearby_support', 'return_surface_anchor', 'approach_threat_ids'))},
        'feedback': feedback(o.get('control', {})),
        'recent_actions': copy.deepcopy(o.get('last_actions', [])),
        'recent_positions': copy.deepcopy(o.get('recent_player_tiles', [])),
        'recent_combat': copy.deepcopy(o.get('recent_combat_events', [])),
        'arrival_feedback': arrival(o.get('decision_arrival', {})),
        'timing': pick(o.get('timing', {}), ('clock_contract', 'inference_world_paused', 'waiting_input', 'frames_per_second')),
        'prediction_scope': '所有事实来自当前或历史已见状态。路径、攻击、采集须执行验证；推理时世界继续，实体可能移动。攻击次数假定全部命中，不保证伤害/安全；宝箱结果未知；历史位置可能过期；历史失败不证明当前不可达。',
    }
    # Retain exploration memory without per-cell repeated provenance sentences.
    result['known_route'] = [pick(row, ('cell', 'last_seen_frame')) for row in o.get('known_surface_route', [])]
    result['visited_tiles'] = copy.deepcopy(o.get('visited_tiles', []))
    return result


MARIO_RULES = (
    'x右y下，实体/旗杆为世界像素；地图格坐标origin+[列,行]乘tile_size=32得到像素。'
    '水平速度3.2/帧，重力0.5，起跳-10；地面完整跳约128像素、最高95像素。只有落地可起跳，不能二段跳；实心砖/管道不可穿。'
    '踩普通敌人头可消灭并弹起，侧撞/碰花无盾则死；花不能踩，掉坑始终死。顶问号砖给金币或蘑菇，碰蘑菇获一次护盾。'
    '选择一个意图后由执行器完成，不自动选择下一目标。cross_right只在当前站位等窗口并向右跳一次；指定障碍意图可走到起跳位、等窗口、跳一次。'
    '受阻/危险变化/目标失效/首次落地/到期会返回。只有cross_right_guard授权落地后最多8秒原位防御跳，不横移，新意图到达即结束。'
    '动作期限见timing和目标；实时等待模型时通常松键，重力/敌人/花继续运行。'
)
MARIO_PREDICTIONS = (
    'predictions按动作ID给出可见投影；保留落点/支撑、碰撞/落坑/未知风险与延迟情景。'
    '花相位由可见高度历史推断，plant_phase_counts是可行相位数量；敌人仅恒速外推，巡逻反向未知。'
    'risk的collision=敌人/花碰撞，pit=落坑，head=撞头，unknown=未知地形，flower_at_landing=落点仍在花口。'
    'after_wait_1s是假设API等待1秒后的风险；idle_1s是动作后松键1秒风险；'
    'delay_scenarios为等待wait_s秒的到达arrival_risk、落地后同长松键idle_risk及落坑pit。缺失值未知；都不是实际延迟、概率或安全保证。'
    'next_jump仅为落地后一次跳跃的静态前方/退路区域[left,right,top]与头顶空间，不自动执行第二跳，不保证动态安全。'
)
MARIO_PROMPT = (
    '选一个合法意图以安全向右通关。先比较落点支撑、落坑/碰撞、花口暴露、延迟及动作后等待风险，再看后续可达区。'
    '结束悬空会在等模型时坠落；过早跳落坑时应先在有支撑处调整站位。'
    '接近花口优先考虑会在到达后检查窗口的越障意图；等不到窗口、受阻或位置反复时换站位/目标，不重复无效动作。'
    '撞头不一定死亡，但会缩短跳跃；核对最终落点。金币/盾为顺路收益，通关优先。仅输出动作ID。'
)
TERRA_RULES = (
    'x右y下，实体为世界格坐标，每格16像素；geometry精确，普通x/y经圆整；地图origin+[列,行]，-1未知而非安全空地。'
    '守门怪须至少一次真实玩家命中正伤害，之后环境助杀可计参与；纯环境击杀无成长或开门。其他怪/Boss不解锁门。'
    '模型只选一个目标意图，引擎在可见地图执行移动、挖掘、搭桥、瞄准并反馈，不自动改选策略/目标。'
    '探索/采集/战斗/绕敌最多240帧；回地表/进门/接近守门怪360帧；恢复300帧。目标完成、未知、不可恢复受阻、死亡提前结束。'
    '战斗/绕敌/撤退受伤后仍执行已选意图至完成或期限。8秒未受伤后才缓慢回血；recover不防御。'
    'return_surface延续本意图有效锚点，切换意图使用当前已见局部地表，不能继承远端门高度。'
    '重生不替代击败守门怪；通关须原生wins增加。推理时松键但世界继续。'
)
TERRA_PROMPT = (
    '只选一个合法意图。围绕成长→接近已见守门怪→真实命中并持续战斗→解锁后进门。'
    '按combat的敌方血量/伤害、打败敌人所需命中数、自己可承受次数及attack射程判断是否战斗；战力不足先采集/恢复/调整位置。'
    'collection提供绑定目标和真正采得后的装备变化；upgrades给出升级成本与缺口。普通矿点主要升镐/剑，宝石可升甲；别无限采矿而不推进守门目标。'
    '门前遇威胁先选战斗/绕敌/撤退，重复进门不会解决威胁。只接近守门怪不会自动攻击；240帧到期但造成伤害仍算进展。'
    '检查feedback和arrival_feedback：净位移≥0.25格、实际资源/HP/装备收益、命中伤害、未还原地形改变或真实挖掘进度才算进展，抖动/同格挖放不算。'
    '同目标失败可换站位/目标或有依据地重试；历史位置不保证仍有目标。仅输出动作ID。'
)
