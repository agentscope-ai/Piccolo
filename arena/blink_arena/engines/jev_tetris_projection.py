"""Visible-only Tetris intent consequences from the production fixed-step engine.

Predictions stop after this piece locks and its lines resolve, before _spawn.
No seed, bag sequence, opponent information or model/teacher answer is available.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from functools import lru_cache
import json
import math

REVISION='tetris-visible-intent-consequences-v2-latency'
DELAY_SECONDS=1.5
LEGACY_NOTE=('候选后果由当前可见状态沿同一物理规则计算，只到本块锁定及消行，'
    '不替你选择目标或硬降。即时情景假定响应现在到达且之后不改意图；'
    '延迟1.5秒是另一确定性情景，不是概率、蒙特卡洛估计或置信区间，其他网络时延可能有不同结果。'
    '顶部连通空格只表示空间，不保证下一块可任意放置；预告仅检查其标准出生位置是否被堵。')
# Rounded measured median/tail from policy18 (3.114/6.696s). These are explicit
# calibration scenarios, not a claim about the latency of a future response.
LATENCY_SCENARIOS=(3.2,7.)
PREDICTION_NOTE=(LEGACY_NOTE+'另列3.2秒/7秒情景，取自20261019已测服务延迟中位/尾部的向上取整，'
    '不是实时测速或保证。timing.control_window给出无新输入时本块剩余寿命；'
    '它不是可达性保证或允许跨块的TTL。回复前若已锁块，只能丢弃并重新观察；不得将旧落点用于新块。')

_PHYSICS_FIELDS=('kind','engine_revision','width','height','board','lines','line_target','steps',
    'max_steps','score','decisions','max_model_decisions','started','elapsed','time_limit',
    'simulation_clock','simulation_ticks','outcome','failure_reason','piece','active','phase',
    'gravity_clock','lock_clock','clear_clock','clearing_rows','pending_intent','input_clock','event')


def visible_physics(state):
    """Discard presentation fields; reject private data at this public boundary."""
    if not isinstance(state,dict) or any(key.startswith('_') for key in state):
        raise ValueError('projection_requires_only_public_state')
    import jev_tetris_realtime as game
    if not game.is_realtime(state) or state.get('outcome') or not state.get('active'):
        raise ValueError('projection_requires_an_active_visible_piece')
    result={key:deepcopy(state[key]) for key in _PHYSICS_FIELDS}
    result['active']={key:state['active'][key] for key in ('piece','piece_id','x','y','rotation')}
    if not game._fits(result,result['active']):raise ValueError('invalid_visible_piece_geometry')
    if state.get('next_piece') in game.PIECES:result['next_piece']=state['next_piece']
    return result


def board_facts(board):
    from jev_showcase_games import metrics
    height,width=len(board),len(board[0]);holes,_,bump=metrics(board)
    heights=[height-next((y for y,row in enumerate(board) if row[x]),height) for x in range(width)]
    hole_cells={(x,y) for x in range(width) for y in range(height-heights[x],height) if not board[y][x]}
    wells=[max(0,min(heights[x-1] if x else height,heights[x+1] if x+1<width else height)-heights[x]) for x in range(width)]
    reachable={(x,0) for x in range(width) if not board[0][x]};queue=deque(reachable)
    while queue:
        x,y=queue.popleft()
        for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0<=nx<width and 0<=ny<height and not board[ny][nx] and (nx,ny) not in reachable:
                reachable.add((nx,ny));queue.append((nx,ny))
    return {'holes':holes,'hole_cells':hole_cells,'maximum_height':max(heights),
        'surface_bumpiness':bump,'deepest_well':max(wells),'top_connected_empty_cells':len(reachable)}


def _project(visible,action,delay,*,prepared=None,before=None):
    import jev_tetris_realtime as game
    before=board_facts(visible['board']) if before is None else before
    initial_id=visible['active']['piece_id'];start=visible['elapsed'];initial_lines=visible['lines']
    if prepared is None:
        s=deepcopy(visible);s['_projection_stop_after_piece']=True
        game._advance_in_place(s,delay)
    else:
        # All candidates share exactly the same no-input prefix. Clone the
        # completed prefix, never simulate future pieces or reuse mutable tails.
        s=deepcopy(prepared)
    applied=bool(s.get('active') and s['active']['piece_id']==initial_id and not s['outcome'] and not s.get('_projection_complete'))
    if applied:
        s=game.step(s,action)
        game._advance_in_place(s,game.TIME_LIMIT-s['elapsed'])
    elif s.get('phase') == 'clearing':
        # A late answer can arrive during the line animation. Finish the same
        # already-locked piece, still stopping before any future spawn.
        game._advance_in_place(s,game.TIME_LIMIT-s['elapsed'])
    after=board_facts(s['board']);landing=s.get('_projection_landing')
    removed=s.get('_projection_cleared_rows',[])
    surviving_holes={(x,y+sum(row>y for row in removed))
        for x,y in before['hole_cells'] if y not in removed}
    rotation,column=map(int,action.split(':'))
    target=bool(landing and landing['rotation']==rotation and landing['x']==column)
    preview=visible.get('next_piece');clearance=None
    if preview and landing:
        shape=game.rotations(preview)[0];spawn_x=(game.WIDTH-1-max(x for x,y in shape))//2
        clearance=all(not s['board'][y][spawn_x+x] for x,y in shape)
    return {'response_delay_seconds':delay,'prediction_type':'deterministic_visible_physics_scenario',
        'action_applied':applied,'locked':landing is not None,'target_reached':target if applied else False,
        'intent_blocked':bool(s.get('_projection_intent_blocked')),'landing':landing,
        'lines_cleared':s['lines']-initial_lines,'holes_before':before['holes'],'holes_after':after['holes'],
        'holes_added':len(after['hole_cells']-surviving_holes),
        'holes_relieved':before['holes']-len(after['hole_cells']&surviving_holes),
        **{key:after[key] for key in ('maximum_height','surface_bumpiness','deepest_well','top_connected_empty_cells')},
        'visible_next_piece_spawn_clear':clearance,'seconds_until_resolved':round(s['elapsed']-start,3),
        'terminal_outcome':s['outcome'],'after_board':s['board'],
        'scope':'current_piece_only_no_future_spawn_no_probability'}


def project_candidate(public_state,action,*,response_delay=0.):
    if type(response_delay) not in (int,float) or not math.isfinite(response_delay) or response_delay<0:
        raise ValueError('invalid_response_delay')
    visible=visible_physics(public_state)
    import jev_tetris_realtime as game
    if action not in game.placement_choices(visible):raise ValueError('unknown_visible_intent')
    return _project(visible,action,float(response_delay))


@lru_cache(maxsize=64)
def _cached_predictions(encoded):
    import jev_tetris_realtime as game
    visible=json.loads(encoded)
    before=board_facts(visible['board'])
    delays=(0.,DELAY_SECONDS,*LATENCY_SCENARIOS) if visible['started'] else (0.,)
    prefixes={}
    for delay in delays:
        prefix=deepcopy(visible);prefix['_projection_stop_after_piece']=True
        game._advance_in_place(prefix,delay)
        prefixes[delay]=prefix
    def project(action,delay):
        return _project(visible,action,delay,prepared=prefixes[delay],before=before)
    result={}
    for action in game.placement_choices(visible):
        immediate=project(action,0.)
        # Before the first actual input the existing engine clock is stopped.
        delayed=(project(action,DELAY_SECONDS) if visible['started'] else
            dict(immediate,response_delay_seconds=DELAY_SECONDS))
        result[action]={'immediate':immediate,'delayed':delayed}
        if visible['engine_revision']==game.REVISION:
            result[action]['latency_scenarios']=[
                project(action,delay) if visible['started'] else dict(immediate,response_delay_seconds=delay)
                for delay in LATENCY_SCENARIOS]
    return result


def candidate_predictions(public_state):
    visible=visible_physics(public_state)
    return deepcopy(_cached_predictions(json.dumps(visible,ensure_ascii=False,sort_keys=True,separators=(',',':'))))


@lru_cache(maxsize=128)
def _cached_control_window(encoded):
    import jev_tetris_realtime as game
    visible=json.loads(encoded)
    result={'piece_id':visible['active']['piece_id'],'binding':'current_piece_only',
            'prediction_type':'deterministic_visible_physics_without_new_input',
            'new_piece_control_authorized':False,'latency_scenarios_seconds':list(LATENCY_SCENARIOS),
            'uncertainty':'new input may change landing; service delay unknown; no future piece simulated'}
    if not visible['started']:
        return dict(result,seconds_to_lock_without_new_input=None,clock_starts_on_first_applied_input=True)
    s=deepcopy(visible);s['_projection_stop_after_piece']=True
    # No selected target or future spawn. The existing intent, if any, is the
    # only input carried into this deterministic remaining-window projection.
    start=s['elapsed']
    while not s['outcome'] and not s.get('_projection_landing') and not s.get('_projection_complete'):
        game._advance_in_place(s,game.TICK)
    return dict(result,seconds_to_lock_without_new_input=round(s['elapsed']-start,3),
                clock_starts_on_first_applied_input=False,
                ends_by='terminal' if s['outcome'] and not s.get('_projection_landing') else 'piece_lock')


def control_window(public_state):
    return deepcopy(_cached_control_window(json.dumps(visible_physics(public_state),sort_keys=True,separators=(',',':'))))


def choice_descriptions(public_state):
    facts=candidate_predictions(public_state);result={}
    for action,scenarios in facts.items():
        rot,col=map(int,action.split(':'));a,b=scenarios['immediate'],scenarios['delayed']
        target=('已达' if a['target_reached'] else '受阻' if a['intent_blocked'] else '未达')
        preview='未知' if a['visible_next_piece_spawn_clear'] is None else '通畅' if a['visible_next_piece_spawn_clear'] else '被堵'
        delayed=('过期或终止，未施加' if not b['action_applied'] else
            f"消行{b['lines_cleared']}/孔洞{b['holes_after']}/目标{'已达' if b['target_reached'] else '未达'}")
        result[action]=(f'旋转 {rot}，左侧第 {col+1} 列｜即时情景：'
            f"消行{a['lines_cleared']}；孔洞{a['holes_before']}→{a['holes_after']}（新增{a['holes_added']}/解除{a['holes_relieved']}）；"
            f"最高列{a['maximum_height']}；起伏{a['surface_bumpiness']}；深井{a['deepest_well']}；顶部连通空格{a['top_connected_empty_cells']}；"
            f"预告出生{preview}；目标{target}；本块{'已锁定' if a['locked'] else '未锁定'}；结算约{a['seconds_until_resolved']:g}秒｜"
            f'延迟1.5秒情景：{delayed}；非概率')
        for scenario in scenarios.get('latency_scenarios',[]):
            consequence=('过期/终止，不施加' if not scenario['action_applied'] else
                f"消{scenario['lines_cleared']}/孔{scenario['holes_after']}/目标{'到达' if scenario['target_reached'] else '未达'}")
            result[action]+=f"｜延迟{scenario['response_delay_seconds']:g}秒：{consequence}"
    return result
