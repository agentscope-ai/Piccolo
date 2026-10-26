"""Observation and action contract for the browser platform game."""
import math

VISIBLE_INTENT_PREFIX = 'cross_visible_right:'
VISIBLE_INTENT_REVISION = 'mario-visible-target-choice-v1'


def _visible_intent_option(facts):
    """Describe a single bound target, using only the captured public facts."""
    intent = facts['intent']
    obstacle = intent['obstacle']
    landing = intent['landing_region']
    window = intent['launch_window']
    verb = ('登上选定可见' if obstacle['kind'] == 'pipe'
            and landing['support_row'] < obstacle.get('support_row', landing['support_row'])
            else '越过选定可见')
    return (
        verb + {'gap': '坑', 'pipe': '管道'}.get(obstacle['kind'], obstacle['kind'])
        + f"[{obstacle['left']},{obstacle['right']}]，落在指定区域"
        + f"x=[{landing['left']},{landing['right']}]、支撑面y={landing['top']}"
        + f"；几何起跳站位x=[{window['minimum_x']},{window['maximum_x']}]"
        + f"，执行站位x={window['selected_x']}、预计走近{window['approach_frames']}帧"
        + f"；最多{intent['deadline_frames']}帧、其中等窗口最多{intent['max_wait_frames']}帧"
        + '；当前投影落点=' + str(facts.get('predicted_player'))
        + '，落地=' + str(facts.get('landed'))
        + '，可见落坑=' + str(facts.get('visible_pit_fall'))
        + '，动态碰撞风险估计=' + str(facts.get('plant_or_enemy_risk'))
        + '，头顶碰撞=' + str(facts.get('head_collision'))
        + '，未知地形=' + str(facts.get('unknown_terrain'))
    )


def _continuation_description(facts):
    continuation = facts.get('continuation')
    if not continuation:
        return ''
    def regions(key):
        return [[r['left'], r['right'], r['top']]
                for r in continuation.get(key, [])]
    return ('；落地后单跳几何可达区[x左,x右,支撑y]：向前='
            + str(regions('visible_forward_landing_regions'))
            + '、退路=' + str(regions('visible_retreat_landing_regions'))
            + '；头顶净空像素=' + str(continuation.get('headroom_pixels'))
            + '；后续投影触及未知边界=' + str(continuation.get('unknown_frontier'))
            + '；这些仅为已见静态几何，不含敌人/花的安全保证，不自动执行后续跳跃')

OPTIONS = {
    'right': '向右跑',
    'jump_right': '向右跳',
    'left': '向左跑',
    'jump_left': '向左跳',
    'jump': '原地跳跃',
    'wait': '松开方向，等待落地',
    'cross_right': '持续向右越过当前可见障碍：等可见安全窗口后起跳，落地或受阻重新决策',
    'wait_safe': '等待可见花缩回或落地事件；最多180帧，到期反馈',
    'cross_gap_right': '持续跨过当前可见坑：走到几何起跳窗口，再跳向对岸；落地或受阻重新决策',
}
RULES = (
    '横向卷轴平台闯关，x 向右、y 向下。player、enemies、coins 的位置及 goal_x 以世界像素计，角色和敌人的宽高也以像素计。'
    'map.origin=[x,y] 是局部地图左上角的世界格坐标，不是像素坐标；每格 map.tile_size=32 像素。'
    'map.tiles[row][col] 的左上角世界像素为 ((map.origin[0]+col)*map.tile_size,(map.origin[1]+row)*map.tile_size)，row 向下、col 向右。'
    '跑动最多12帧，跳跃最多40帧，持续过障碍/等待窗口最多180帧；落地、受阻可提前返回。水平速度3.2像素/帧，重力0.5，起跳速度-10。'
    '跳跃只在动作开始且 on_ground=true 时生效；空中可以改变左右方向，不能二段跳。'
    '地面、砖块和管道均不可穿过；从下方顶问号砖会弹出金币或蘑菇，金币立即计分，碰到蘑菇后得到一次护盾。'
    '管道里的食人花会按周期升降，plants 给出当前可见管道花的位置和伸出高度；不能踩退食人花，须避开或等其缩回。'
    '从上方下落踩中普通敌人可消灭敌人并弹起；侧面碰撞会失败，除非还有蘑菇护盾。掉入坑底始终失败。'
    '优先安全抵达右侧旗杆，金币和蘑菇为额外收益。观测只包含当前镜头可见地形、敌人和奖励，'
    '不要把可见范围外当作安全地面；结合速度、脚下平台及最近动作判断起跳时机。'
    '食人花周期180帧，相位只依据亲眼观察的高度历史推断；相位区间及敌人恒速外推均有不确定性。'
    '直接动作若可见预测将碰撞会安全中止并返回失败现场，不代替你选择下一策略。持续过坑会计算并执行起跳窗口，不能在空中重新起跳。'
)

ATOMIC_RULES = (
    '横向卷轴平台闯关，x向右、y向下。角色、敌人、金币、管道花与旗杆坐标均为世界像素。'
    'map.origin为可见地图左上角的世界格坐标，每格32像素；tiles[row][col]的像素坐标为(origin+[col,row])*32。'
    '水平速度3.2像素/帧，重力0.5，起跳速度-10，水平地面完整跳跃约40帧、前进128像素、最高抬升95像素。'
    '只有起跳时on_ground=true才能跳，空中不能二段跳。实心地面、砖和管道均不可穿过。'
    '从上方下落踩中普通敌人可消灭它并弹起；侧撞会失败。食人花不能踩退，它在管道口周期升降，伸出时触碰会失败。'
    '顶问号砖会给金币或弹出蘑菇；碰到蘑菇得到一次护盾，能挡一次敌人或食人花伤害。掉坑始终失败。'
    '唯一胜利条件是活着抵达右侧旗杆；收集、攻击、探索均应服务于这条路线。当前只提供六个原子方向动作，没有自动选路、避险或规则接管。'
    '敌人和花只观察当前镜头，不知道隐藏相位、未见地形或未来随机数；可见花的高度也不能保证模型答复时仍然安全。'
)

ATOMIC_INSTRUCTIONS = (
    '活着抵达右侧旗杆。先核对脚下平台、右侧管道/坑、普通敌人及最近动作的实际效果，再选择六个合法动作之一。'
    '探索时向右推进；平地用right接近目标，不能长时间在敌人巡逻路径或花口上等模型。'
    '防御优先：地面跳跃最高只抬升95像素，64像素高管道上的48像素食人花不能从地面直接跳过完全伸出的花。'
    '可以先落到管道不接触花的边缘，再从较高平台跳过；仅有当前缩回不等于整个推理等待和通过过程安全。'
    '遇到坑，先在有支撑的坑边起跳，完整向右跳约125像素，过早跳会落入96像素宽的坑。'
    '普通敌人可用落下踩头攻击，切勿侧面硬撞；有盾可承受一次接触但不能防坠落。'
    '顺路跳跃可以收集金币，安全时顶问号砖取蘑菇护盾；不要为了金币在危险区徘徊。'
    '若上一步受阻或位置重复，换可行的跳跃/后退站位；不要重复无效right。'
    '先比较候选投影：visible_pit_fall=true不可选；普通right若结束on_ground=false会在下一次推理时原地坠落，应在仍有支撑时改选能落地的jump_right。'
    '动态风险是保守估计，不应反复等待或退回整个关卡；若跳跃当前风险与假设等待1秒风险都高，先改变安全站位再观察窗口。'
    '实时推理期间方向松开但物理继续，优先让本次动作结束在安全、有支撑的位置。只输出合法动作ID。'
)

WINDOW_INSTRUCTIONS = (
    '目标是活着抵达右侧旗杆，探索、踩敌和收集都服务于这条路线。先比较候选的可见落点、地面支撑、碰撞风险与最近实际效果。'
    'cross_right是你选择的“在当前站位等安全窗口然后跳向右侧可见落点”，执行层只执行这个子目标，不会替你规划整关；若踩敌弹起，到达这次投影落点的横坐标后松方向收住，落地或到期返回。'
    '接近管道花时优先选cross_right，让执行层在API答复到达之后检查窗口；当前花缩回并不表示延迟之后仍安全，别在这种情况下冒险直接jump_right。'
    'cross_right不调整站位：如果完整跳跃会落坑或无法落地，先用right/left调整到可安全起跳的位置，不能一直重复等不存在的窗口。撞头本身不是死亡：从下方顶砖可以打碎砖或触发问号奖励，但会缩短本次跳跃，需看最终落点和实际反馈。'
    '落在花口即使此刻花缩回也不安全：landing_plant_exposure=true时cross_right会拒绝执行，先右走到管道旁的最后地面站位，使跳跃最终落点越过花的水平范围，再选cross_right。'
    '必须考虑下一轮模型推理的空档：候选“动作结束后松键1秒”若会落坑或碰撞，说明动作结束位置不能安全等待；选择能继续前进并安全落地的跳跃，不要用wait或后退把自己停在巡逻敌人前。'
    '坑前使用投影选择站位：若jump_right的visible_pit_fall为true，通常是过早起跳，需要在仍有支撑的位置再靠近坑边；若right结束on_ground=false，则会在下一次推理等待时原地落坑，不能再右走。'
    '普通敌人从上方下落踩头才可攻击，侧撞会死；可比较predicted_stomps，食人花永远不能踩退。'
    '顺路跳跃收金币，安全时顶问号砖取得蘑菇并接触它获得一次护盾；不为额外收益离开通关方向。'
    '避免在花口或敌人巡逻路径等模型，选择能落在安全平台的动作；受阻、到期或无进展时改变站位再判断。只输出合法动作ID。'
)


def as_record(observation):
    player = observation['player']
    terrain = observation['map']
    tile_size = terrain['tile_size']
    origin_x, origin_y = terrain['origin']
    tiles = terrain['tiles']
    def tile_at(x, y):
        col, row = x-origin_x, y-origin_y
        return tiles[row][col] if 0 <= row < len(tiles) and 0 <= col < len(tiles[row]) else None
    front_x = math.floor((player['x']+player['width']+1)/tile_size)
    top_y = math.floor(player['y']/tile_size)
    bottom_y = math.floor((player['y']+player['height']-0.01)/tile_size)
    blockers = [tile_at(front_x, y) for y in range(top_y, bottom_y+1)]
    recent = observation.get('recent_player_positions', [])
    stalled = len(recent) >= 2 and all(abs(float(pos[0])-player['x']) < 1 for pos in recent[-2:])
    enemies_ahead = [enemy['x']-(player['x']+player['width'])
                     for enemy in observation.get('enemies', [])
                     if enemy['x']+enemy['width'] >= player['x']+player['width']]
    plants_ahead = [plant['x']-(player['x']+player['width'])
                    for plant in observation.get('plants', [])
                    if plant['x']+plant['width'] >= player['x']+player['width'] and plant['emerged']]
    navigation = {
        'right_adjacent_tile_x': front_x,
        'right_adjacent_solid': any(t is not None and t > 0 for t in blockers),
        'right_adjacent_unknown': any(t is None for t in blockers),
        'right_adjacent_ground': tile_at(front_x, bottom_y+1),
        'stalled_on_recent_actions': stalled,
        'nearest_enemy_ahead_pixels': round(min(enemies_ahead), 1) if enemies_ahead else None,
        'nearest_emerged_plant_ahead_pixels': round(min(plants_ahead), 1) if plants_ahead else None,
        'has_mushroom_shield': bool(player.get('shield')),
    }
    effects=observation.get('candidate_effects', {})
    visible_intents = {key: facts for key, facts in effects.items()
                       if key.startswith(VISIBLE_INTENT_PREFIX)}
    enhanced=bool(visible_intents) or any(k in effects for k in ('cross_right', 'cross_gap_right', 'wait_safe'))
    native_execution=bool(observation.get('action_execution'))
    timing=observation.get('timing', {})
    action_frames=timing.get('action_frames_by_action', {})
    jump_frames=action_frames.get('jump_right', timing.get('action_frames', 12))
    rules=RULES if enhanced and not native_execution else ATOMIC_RULES.replace(
        '当前只提供六个原子方向动作，没有自动选路、避险或规则接管。',
        '原有六个方向动作之外，cross_right是明确由模型选定的持续向右跳跃意图；没有自动选路或规则接管。' if enhanced else
        '当前只提供六个原子方向动作，没有自动选路、避险或规则接管。')+(
        f'跑动和等待最多{action_frames.get("right", 12)}帧；跳跃最多{jump_frames}帧。'
        + ('选定跳跃将持所选方向到首次落地、地面受阻或期限到达；执行层不改变方向、不另选路线。' if jump_frames > 12 else
           '短跳只持方向12帧，前进38.4像素；动作结束仍在空中，后续等待会原地落下，不能当作125像素完整跳跃。')
        + ('推理等待时世界继续运行、按键松开，模型看到的是请求发起时的观测。' if timing.get('clock_contract') == 'realtime-v1' else '')
    )
    if effects and (not enhanced or native_execution):
        rules += '候选事实使用同一可见地图进行几何投影；花只用已观察高度历史推断相位集合，敌人仅恒速估计且可能巡逻反向。after_assumed_60_frame_wait是假设等待1秒的动态风险估计，不是实际延迟或确定结果。'
    if enhanced and native_execution:
        rules += 'cross_right最多180帧，在当前有支撑的站位等待可见完整跳跃风险降低，然后向右侧本次可见落点起跳；踩敌弹起后到达目标横坐标可松方向收住，首次落地、地面受阻、终局或期限到达返回。窗口不一定出现，不提前移动站位、不自动规划整关。'
    options={k:v for k,v in OPTIONS.items() if k in effects or k not in ('cross_right','wait_safe','cross_gap_right')}
    if visible_intents:
        rules += ('cross_visible_right:开头的每个ID是一个完整Choice，绑定候选中那一个可见障碍和落地区域。'
                  '模型选择目标；执行层只在有支撑的已见路线走到起跳站位，等待可见安全窗口，起跳一次并在落地时返回。'
                  '受阻、危险变化、目标失效或到期会反馈，不替你选择另一个目标。等待模型时物理继续。'
                  '走近和起跳属于所选意图的B执行，只采样这一个Choice的概率，不把机械帧算成额外策略决策。'
                  'continuation只描述可见静态几何中的后续单跳可达区、头顶和退路；不是未来动态安全保证，也不执行第二跳。')
        options.update({key: '' for key in visible_intents})
    if 'cross_right_guard' in effects:
        rules += 'cross_right_guard是额外的显式持续意图：先执行cross_right，落地立即重新请求模型，同时在原位最多8秒按可见碰撞窗口进行安全原地跳防御；只在模型选择该项后执行，不横移、不自动选择下个障碍；新意图、到期、终局或无安全防御窗口时中止。普通动作结束后仍松开按键，不会自动获得防御。latency_scenarios的4/8秒只在当前观察到的起跳姿态估计动态危险，角色到达时跳跃阶段另行校验；不是实际服务保证或概率，敌人巡逻反向未知。'
        options['cross_right_guard']='选定向右越障一次，并授权落地后最多8秒原位防御等待'
    if 'cross_gap_right' in options and not effects.get('cross_gap_right',{}).get('gap'):
        options.pop('cross_gap_right')
    for action,facts in effects.items():
        if action not in options:
            continue
        if action.startswith(VISIBLE_INTENT_PREFIX):
            options[action] = _visible_intent_option(facts)
        elif action in ('cross_right','cross_right_guard') and native_execution:
            options[action]='在当前站位等可见安全窗口后跳向右侧本次可见落点；若踩敌弹起，达到目标横坐标后松方向收住；最多180帧，首次落地/受阻/到期返回；不自动规划整关、不承诺窗口出现。现在立即起跳的可见落点='+str(facts.get('predicted_player'))+'，落地='+str(facts.get('landed'))+'，可见落坑='+str(facts.get('visible_pit_fall'))+'，当前动态风险='+str(facts.get('plant_or_enemy_risk'))+'，头顶碰撞='+str(facts.get('head_collision'))+'；当前风险不等于等待后风险'
        elif action.startswith('cross'):
            options[action]+='；这是有期限的持续意图，会等可见窗口并调整起跳站位，最多180帧；以下风险仅指【现在立即起跳】，不是等待后的结果：当前起跳落点='+str(facts.get('jump_now_projection'))+'，当前动态碰撞风险='+str(facts['plant_or_enemy_risk'])+'；可见坑='+str(facts.get('gap'))+'。窗口可能不出现，落地/受阻/到期返回，不承诺固定落点。'
        elif action.startswith('jump'):
            full=facts.get('complete_jump_projection',facts)
            options[action]+='；完整跳跃投影落点='+str(full.get('predicted_player'))+'，落地='+str(full.get('landed'))+'，可见落坑='+str(full.get('visible_pit_fall'))+'，动态碰撞风险='+str(full.get('plant_or_enemy_risk'))+'，头顶碰撞='+str(full.get('head_collision'))+'，未知地形='+str(full.get('unknown_terrain'))
        elif action=='wait_safe':
            options[action]+='；等完整跳跃投影支持安全通过的窗口（单纯当前花缩回不代表足够时间通过），最多180帧；不自动移动，不自动选下一策略'
        else:
            options[action]+='；预测落点='+str(facts.get('predicted_player'))+'，动态碰撞风险='+str(facts.get('plant_or_enemy_risk'))+'，可见落坑='+str(facts.get('visible_pit_fall'))+'，未知地形='+str(facts.get('unknown_terrain'))
        options[action]+='；'+facts['certainty']
        if native_execution:
            options[action]+='；落点仍在可见花口范围='+str(facts.get('landing_plant_exposure'))
            idle=facts.get('post_action_idle_60_frames')
            if idle:
                options[action]+='；动作结束后松键1秒：可见落坑='+str(idle.get('visible_pit_fall'))+'，动态碰撞风险估计='+str(idle.get('plant_or_enemy_risk'))
        if (not enhanced or native_execution) and facts.get('after_assumed_60_frame_wait'):
            later=facts['after_assumed_60_frame_wait']
            options[action]+='；假设API等待1秒后的动态碰撞风险估计='+str(later.get('plant_or_enemy_risk'))+'；该估计不保证实际到达时安全'
        if facts.get('latency_scenarios'):
            options[action]+='；等待情景（秒/到达动态风险/落地后同长松键风险）='+str([
                [s['assumed_wait_seconds'],s['arrival_dynamic_risk_estimate'],s['post_landing_idle_risk_estimate']]
                for s in facts['latency_scenarios']])+'；敌人可能巡逻反向，均是可见恒速估计而非概率'
        if action=='cross_right_guard':
            options[action]+='；落地立即返回模型重决策，但这次显式选定的B防御继续：原地松方向，可见碰撞临近且原地跳投影安全时才原地跳，不横移、不选下一障碍；新模型意图、8秒到期或无法处理的危险结束，不能保证安全'
        options[action] += _continuation_description(facts)
    intent_instructions = (
        '若有cross_visible_right:候选，可以直接选择其中一个具体障碍和落地区域，执行层会完成该目标内的走位、等窗口和一次跳跃。'
        '比较落地后头顶、前进区、退路和未知边界；这些几何事实不代表动态安全，也不会自动执行下一跳。'
        if visible_intents else '')
    return {
        'schema_version': 'jev.training.v1', 'id': 'live-mario', 'group_id': 'live-mario',
        'state': {'role': '马里奥像素闯关玩家', 'rules': rules, 'observation': observation,
                  'navigation': navigation,
                  **({'prompt_revision': VISIBLE_INTENT_REVISION} if visible_intents else {})},
        'questions': {'decision': {'type': 'choice',
            'instructions': ('目标是活着抵达右侧旗杆。优先比较候选真实可见后果；若同一动作已安全中止或无进展，避免重复；比较 jump_left/left 的实际安全撤离后果。坑前若完整跳跃预测落坑，应选择 cross_gap_right 让执行层走到起跳窗口再跳；不要过早 jump_right 或在空中要求二段跳。先看 state.navigation 和最近位置：若连续向右但 x 不变、右前方有实心砖或管道且人在地面，改为 jump_right 越过障碍，不能继续重复 right。观察 nearest_enemy_ahead_pixels：地面上距离普通敌人约 40–90 像素时应提前 jump_right；食人花不能踩退；cross_right 会持续等可见安全窗口并越过实心障碍，优先使用该意图来过管道；wait_safe 只等窗口不会推进，窗口就绪后别继续重复等待。空中不能二段跳，应观察落点；坑前也须提前起跳。可从下方顶问号方块获取奖励，但金币和蘑菇不是通关条件。只输出合法动作 ID。' if enhanced and not native_execution else WINDOW_INSTRUCTIONS if enhanced else ATOMIC_INSTRUCTIONS) + ('若预计落地后仍需在敌人附近等模型，可明确选择cross_right_guard授权一次越障后的有期限原地防御；该项也不保证安全，不能借此自动续跑整关。' if 'cross_right_guard' in effects else '') + intent_instructions,
            'criteria': options, 'option_order': list(options)}},
        'labels': {},
        'provenance': {'data_source': 'cues_mario_browser_v1', 'source_id': 'live', 'source_split': 'demo'},
        'metadata': {'domain': 'games', 'sub_domain': 'mario_platformer', 'scenario': 'interactive_control'},
    }
