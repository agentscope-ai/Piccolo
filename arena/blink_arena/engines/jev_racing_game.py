"""Shared real-time racing physics with free steering and real pedal inputs.

No target lane or target speed controller. One joint Choice controls steering
and throttle/coast/brake. The same fixed ticks run during model inference.
"""
from __future__ import annotations
import copy
import math
import random

KIND = 'racing_sprint'
REVISION = 'rally-sprint-v5-throttle-start-swept-contact'
TRACK_REVISION = 'rally-sprint-v2-realtime'  # Preserve existing seed -> road exactly.
SFT_EXPORT_PROHIBITED = True
CANDIDATE_REVISION = 'visible-contact-latency-envelope-v4-throttle-start'
LATENCY_SCENARIO_SECONDS = 1.25
LATENCY_EXECUTION_SECONDS = 1.5
GOAL = '首次踩油门后300秒内自主驾驶900米抵达终点，车辆耐久大于0；允许停车和低速恢复'
SCENE = {'name':'赛车 · Rally Sprint', 'mode':'game',
         'note':'首次踩油门才发车计时；发车后等待模型时物理继续。可停车后重新起步，300秒内跑完900米。',
         'url':'https://github.com/jakesgordon/javascript-racer',
         'source_label':'CuES 共享实时赛车引擎 · 绘制参考 JavaScript Racer (MIT)'}
LIMIT = 320
LENGTH = 900.
TIME_LIMIT = 300.
DT = .05
DURATION = 2.
VISIBILITY = 70.
CAR_WIDTH = 1.25
CAR_LENGTH = 2.
OBSTACLE_LENGTH = 1.
CONTACT_HALF_LENGTH = (CAR_LENGTH+OBSTACLE_LENGTH)/2
ROAD_CENTER_LIMIT = 4.05
ROAD_HALF_WIDTH = ROAD_CENTER_LIMIT+CAR_WIDTH/2
MAX_SPEED = 23.
STEERING = {'hard_left':-1., 'left':-.4, 'straight':0., 'right':.4, 'hard_right':1., 'pulse_left':-1., 'pulse_right':1.}
PULSE_SECONDS = .35
DELAY_SCENARIOS = (.5,.75,1.25,2.)
PEDALS = ('throttle','coast','brake')
STEERING_LABELS = {'hard_left':'大幅左转','left':'轻微左转','straight':'方向回正','right':'轻微右转','hard_right':'大幅右转','pulse_left':'大左0.35秒脉冲后回正','pulse_right':'大右0.35秒脉冲后回正'}
PEDAL_LABELS = {'throttle':'踩油门','coast':'松油门滑行','brake':'踩刹车'}
LANES = {'left':-2.7,'center':0.,'right':2.7}  # Obstacle placement only, never steering targets.
RULES = ('自由实时驾驶：900米，耐久100。首次提交有效throttle油门输入才发车，并开始300秒墙钟赛时；发车前等待、转向、滑行或刹车均不耗赛时。发车后松油门、停车和等模型仍正常计时，重开才重新待发。到终点、耐久>0、赛时<=300秒才赢。'
 '动作是5档持续方向盘加左右0.35秒脉冲×3种踏板，共21个单一联合选择，不是车道目标或巡航速度。'
 '方向盘hard_left/left/straight/right/hard_right对应-1/-0.4/0/0.4/1，负数向左；方向回正不会把车拉回道路中央。pulse_left/pulse_right以-1/+1打方向0.35秒后机械回正，踏板保持；这是模型选定的执行期限B，不是C代驾。'
 '车辆横向位置x和横向速度lateral_velocity连续变化；打方向后有转向响应惯性，回正后横向速度逐渐衰减。车停住时不能横移瞬移。'
 'throttle踩油门提供4.5米/秒²驱动力；coast松油门没有驱动力，依滚阻和风阻慢慢减速；brake刹车提供8米/秒²减速度，可停到0。'
 '阻力为0.2+0.015×车速，最高车速23米/秒；没有最低车速或自动巡航，允许停车观察、缓行、再次踩油门起步。'
 '弯道高于公布grip_speed会向外滑移。相对道路中心|x|>4.05米为出界，每秒扣28耐久；路肩阻力为min(10,2×车速)米/秒²，保留低速起步能力。车体宽1.25米、长2米，障碍纵深1米；道路半宽4.675米。每tick沿实际运动线段检查纵横向同时重叠，纵向接触带为障碍z±1.5米，横向中心间距须小于(障碍宽+1.25)/2才碰撞，扣35耐久、速度乘0.45；每个障碍最多扣一次。'
 '每个输入有效4秒，等待模型时仍执行上一输入；到期后方向回正并制动，计C安全中止，不自动选路。'
 '仅前方70米可见，未来道路和障碍不可见。候选给出立即执行2秒与假设等待0.5/0.75/1.25/2秒的条件投影，最长总投影3秒且最远69米；不同延迟结果可能非单调，汇总这几个情景最坏损伤，不保证未模拟延迟安全。只用请求时公开信息。'
 '固定每0.05秒物理tick；最多320次模型决策。人工按键与模型分开计数。错误、超时、耗尽留在验收分母。')
PROMPT_REVISION = 'racing-prompt-v6-arrival-time-20261015'
PROMPT = (
    '目标是先安全完成，同等完成度下用时越短得分越高；300秒允许先以约5–10米/秒缓行，转向稳定后再按剩余时间提速。这是策略建议，不是强制限速。观察到的speed是请求开始时的快照。race_start'
    'ed=true且旧pedal为throttle时，即使speed仍接近0也已在等待期间加速，不要把它当作尚未起步而反复加油。参考control_facts.old_input_after_assume'
    'd_wait的条件速度与位置，并核对候选的各延迟情景。连续踩油门会不断加速，松油门会缓慢降速；可在起步后用油门/滑行脉冲控制速度。刹车在当前输入仍会继续一段时间的情况下要提前。不要仅因即时投影无伤就继'
    '续油门；必须比较0.5/0.75/1.25/2秒延迟情景最坏损伤，短延迟未必比长延迟安全。查看障碍接触带的可通行横向区间，提前把车移到选定空隙；可用0.35秒转向脉冲微调后自动回正，避免等待期间持续打'
    '方向。这是你选定动作的机械执行，不会自动选路。选择接下来保持的方向盘和踏板联合输入。你能自行决定快慢、松油门滑行或刹停再起步；不要把straight理解成自动回到中间车道。先依据x、横向速度、车速、前'
    '方障碍/弯道以及即时与延迟条件投影避免碰撞或出界，再考虑实际推进。目前预算允许慢速恢复，剩余距离/剩余时间显示最低平均速度需求。转向会持续改变位置，接近合适位置时需回正；等待模型期间仍执行旧输入。选项'
    '位置可能变化，按动作ID及描述判断，再遵循当前回答格式返回该动作对应的选项标签，不解释。'
)


def fresh(seed=0):
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError('seed must be uint32')
    rng = random.Random(f'{TRACK_REVISION}/{seed}')
    sections, obstacles, center = [], [], 0.
    for i in range(30):
        curve = 0. if i == 0 else rng.choice([-.014,-.009,-.004,0.,.004,.009,.014])
        grip = 23. if abs(curve)<.005 else 19. if abs(curve)<.012 else 15.
        sections.append({'start':i*30.,'end':(i+1)*30.,'curve':curve,'grip_speed':grip,'center':center})
        center += curve*900./2
        if 2 <= i < 29 and rng.random()<.66:
            lanes = rng.sample(list(LANES),rng.choices([1,2],[.8,.2])[0])
            for lane in lanes:
                obstacles.append({'id':f'obstacle-{i}-{lane}','z':i*30.+rng.uniform(9,21),
                                  'x':LANES[lane],'width':1.25})
    return {'kind':KIND,'_seed':seed,'_track':sections,'_obstacles':obstacles,
            'z':0.,'x':0.,'speed':0.,'lateral_velocity':0.,'steering_input':0.,'pedal':'coast',
            'steering_pulse_deadline':None,'steering_pulse_completed':False,
            'elapsed':0.,'race_started':False,'health':100.,'steps':0,'score':0.,'outcome':None,
            'event':'静止发车：踩油门起步，可松油门滑行或刹停恢复','contacts':[],
            'last_action':None,'execution_status':'waiting_start','collision_count':0,'offroad_seconds':0.,
            'model_decisions':0,'human_inputs':0,'input_events':0,'deterministic_execution_ticks':0,
            'rule_takeover_count':0,'active_action':'straight:coast','active_controller':'initial_idle',
            'intent_expires_at':4.,'_clock_remainder':0.,'expired_intent':False}


def _section(track,z):
    return next((s for s in track if s['start']<=z<s['end']),track[-1])


def public(g,include_trace=False):
    state={k:copy.deepcopy(v) for k,v in g.items() if not k.startswith('_') and k!='execution_trace'}
    state['visible_track']=[copy.deepcopy(s) for s in g['_track'] if s['end']>=g['z']-6 and s['start']<=g['z']+VISIBILITY]
    state['visible_obstacles']=[copy.deepcopy(o) for o in g['_obstacles'] if g['z']-4<=o['z']<=g['z']+VISIBILITY]
    state.update(finish_distance=LENGTH,time_limit=TIME_LIMIT,max_model_decisions=LIMIT,
                 remaining_distance=round(max(0,LENGTH-g['z']),2),remaining_time=round(max(0,TIME_LIMIT-g['elapsed']),2),
                 visible_distance=VISIBILITY,clock='realtime_wall_clock',engine_revision=REVISION,
                 track_revision=TRACK_REVISION,control_mode='steering_and_pedals',max_speed=MAX_SPEED,
                 control_labels={'steering':STEERING_LABELS,'pedals':PEDAL_LABELS},
                 steering_pulse_duration=PULSE_SECONDS,
                 collision_geometry={'car_width':CAR_WIDTH,'car_length':CAR_LENGTH,'obstacle_length':OBSTACLE_LENGTH,
                                     'contact_half_length':CONTACT_HALF_LENGTH,'road_center_limit':ROAD_CENTER_LIMIT,'road_half_width':ROAD_HALF_WIDTH},
                 race_clock_start='first_throttle_input',
                 steering_pulse_remaining=max(0.,g['steering_pulse_deadline']-g['elapsed']) if g.get('steering_pulse_deadline') is not None else None)
    if include_trace and 'execution_trace' in g:state['execution_trace']=copy.deepcopy(g['execution_trace'])
    return state


def _actions(g):
    return [] if g.get('outcome') else [f'{steer}:{pedal}' for steer in STEERING for pedal in PEDALS]


def _frame(g):
    return {k:copy.deepcopy(g[k]) for k in ('z','x','speed','lateral_velocity','steering_input','pedal','elapsed','health','outcome','event')}


def _contact_segment(x0,z0,x1,z1,obstacle):
    """Clip one physical tick to the longitudinal band before testing x.

    Both axes must overlap at the same instant. Testing the final x against the
    whole z sweep charged cars which had already cleared a barrier, and missed
    cars which steered clear during the end of the tick.
    """
    lo,hi=0.,1.
    dz=z1-z0
    lower,upper=obstacle['z']-CONTACT_HALF_LENGTH,obstacle['z']+CONTACT_HALF_LENGTH
    if abs(dz)<1e-12:
        if not lower-1e-9<=z0<=upper+1e-9:return None
    else:
        a,b=(lower-z0)/dz,(upper-z0)/dz
        lo,hi=max(lo,min(a,b)),min(hi,max(a,b))
        if lo>hi+1e-9:return None
        lo,hi=max(0.,lo),min(1.,hi)
    xa=x0+(x1-x0)*lo;xb=x0+(x1-x0)*hi
    distance=0. if (xa-obstacle['x'])*(xb-obstacle['x'])<=0 else min(abs(xa-obstacle['x']),abs(xb-obstacle['x']))
    return {'entry_fraction':lo,'exit_fraction':hi,'entry_x':xa,
            'minimum_lateral_clearance_m':distance-(obstacle['width']+CAR_WIDTH)/2}


def _tick(s):
    steer_name,pedal=s.get('active_action','straight:coast').split(':')
    steering=STEERING[steer_name]
    events=[]
    if steer_name.startswith('pulse_') and s.get('steering_pulse_deadline') is not None and s['elapsed']+1e-9>=s['steering_pulse_deadline']:
        steering=0.
        if not s.get('steering_pulse_completed',False):
            s['steering_pulse_completed']=True;events.append('steering_pulse_completed')
    if s['elapsed']>=s['intent_expires_at']:
        steering,pedal=0.,'brake'
        if not s['expired_intent']:
            s['expired_intent']=True;s['rule_takeover_count']+=1;events.append('intent_expired_safety_brake')
    s['steering_input'],s['pedal']=steering,pedal
    prior_z,prior_x=s['z'],s['x'];sec=_section(s['_track'],prior_z)
    drag=.2+.015*s['speed']
    acceleration=(4.5 if pedal=='throttle' else -8. if pedal=='brake' else 0.)-drag
    s['speed']=max(0.,min(MAX_SPEED,s['speed']+acceleration*DT))
    # Tire response carries lateral inertia. Neutral steering damps lateral
    # velocity but never selects a road coordinate/lane or drives toward x=0.
    target_lateral=steering*min(3.6,.22*s['speed'])
    s['lateral_velocity']+=(target_lateral-s['lateral_velocity'])*min(1.,4.*DT)
    if s['speed']<=1e-9:s['lateral_velocity']=0.
    drift=-math.copysign(max(0.,s['speed']-sec['grip_speed'])*.65,sec['curve']) if sec['curve'] else 0.
    s['x']+=(s['lateral_velocity']+drift)*DT
    s['z']+=s['speed']*DT;s['elapsed']+=DT;s['deterministic_execution_ticks']+=1
    if steer_name.startswith('pulse_') and not s.get('steering_pulse_completed') and s['elapsed']+1e-9>=s['steering_pulse_deadline']:
        s['steering_input']=0.;s['steering_pulse_completed']=True;events.append('steering_pulse_completed')
    if abs(s['x'])>ROAD_CENTER_LIMIT:
        s['health']-=28.*DT;s['speed']=max(0.,s['speed']-min(10.,2.*s['speed'])*DT)
        s['offroad_seconds']+=DT;events.append('offroad')
    for obstacle in s['_obstacles']:
        if obstacle['id'] in s['contacts']:continue
        contact=_contact_segment(prior_x,prior_z,s['x'],s['z'],obstacle)
        if contact is not None and contact['minimum_lateral_clearance_m']<-1e-9:
            s['contacts'].append(obstacle['id']);s['health']-=35.;s['speed']*=.45
            s['collision_count']+=1;events.append('collision')
    s['health']=max(0.,s['health']);s['score']=round(min(s['z'],LENGTH),3)
    if s['health']<=0:s.update(outcome='loss',event='车辆损毁',failure_reason='vehicle_destroyed')
    elif s['elapsed']>TIME_LIMIT+1e-7:s.update(outcome='loss',event=f'超过{TIME_LIMIT:g}秒赛时',failure_reason='race_time_exhausted')
    elif s['z']>=LENGTH:s.update(outcome='win',event='自主驾驶抵达900米终点')
    elif 'collision' in events:s['event']='碰撞：车辆继续运行，可刹车恢复'
    elif 'offroad' in events:s['event']='车辆偏出赛道，请转向或制动恢复'
    elif s['expired_intent']:s['event']='输入超过4秒期限，回正制动（C）'
    elif 'steering_pulse_completed' in events:s['event']='0.35秒转向脉冲完成，机械回正；踏板继续保持（B）'
    elif s['speed']<=1e-9:s['event']='车辆已停止；可观察后踩油门起步'
    else:s['event']='按方向盘与踏板输入持续行驶'
    s['execution_status']='terminal' if s['outcome'] else 'safety_braking' if s['expired_intent'] else 'stopped' if s['speed']<=1e-9 else 'executing'
    return events


def advance_idle(g,seconds):
    if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0:
        raise ValueError('elapsed time must be finite and nonnegative')
    s=copy.deepcopy(g);s.pop('execution_trace',None)
    frames=[_frame(s)];events=[];start=s['elapsed']
    # Positive motion/elapsed also recognizes archived or explicitly constructed
    # mid-race states; a fresh stationary car only starts in step(throttle).
    if not s.get('race_started') and (s['speed']>0 or s['elapsed']>0 or s['z']>0):s['race_started']=True
    if not s.get('race_started'):
        s['_clock_remainder']=0.
        s['execution_status']='waiting_start'
        s['event']='待发车：首次踩油门才开始计时'
        s['execution_trace']={'version':1,'dt':DT,'duration':0.,'frames':frames,
            'strategy_action':s.get('active_action'),'intent_controller':s.get('active_controller'),
            'controller':'B_deterministic_execution','events':[],
            'requested_wall_seconds':seconds,'rule_takeover_count':0}
        return s
    credit=s.get('_clock_remainder',0.)+seconds;ticks=int((credit+1e-9)/DT)
    s['_clock_remainder']=max(0.,credit-ticks*DT)
    for _ in range(ticks):
        if s['outcome']:break
        events.extend(_tick(s));frames.append(_frame(s))
    s['execution_trace']={'version':1,'dt':DT,'duration':round(s['elapsed']-start,6),'frames':frames,
        'strategy_action':s.get('active_action'),'intent_controller':s.get('active_controller'),
        'controller':'B_deterministic_execution','events':list(dict.fromkeys(events)),
        'requested_wall_seconds':seconds,'rule_takeover_count':s['rule_takeover_count']-g['rule_takeover_count']}
    return s


def step(g,action,*,controller='model'):
    if controller not in ('model','human'):raise ValueError('unknown racing input controller')
    if action not in _actions(g):raise ValueError('illegal action or finished race')
    s=copy.deepcopy(g);s.pop('execution_trace',None)
    if controller=='model' and s['model_decisions']>=LIMIT:
        s.update(outcome='loss',failure_reason='decision_budget_exhausted',event=f'{LIMIT}次模型决策预算耗尽')
        return s
    steer,pedal=action.split(':')
    if pedal=='throttle':s['race_started']=True
    s.update(last_action=action,active_action=action,active_controller=controller,
             steering_input=STEERING[steer],pedal=pedal,intent_expires_at=s['elapsed']+4.,
             steering_pulse_deadline=s['elapsed']+PULSE_SECONDS if steer.startswith('pulse_') else None,steering_pulse_completed=False,
             expired_intent=False,execution_status='executing' if s.get('race_started') else 'waiting_start',
             event='方向盘与踏板输入已提交' if s.get('race_started') else '待发车：首次踩油门才开始计时')
    s['input_events']+=1
    if controller=='model':s['steps']+=1;s['model_decisions']+=1
    else:s['human_inputs']+=1
    return s


def _visible_copy(g):
    s={k:v for k,v in g.items() if k!='execution_trace'}
    s['_track']=[v for v in g['_track'] if v['end']>=g['z']-6 and v['start']<=g['z']+VISIBILITY]
    s['_obstacles']=[v for v in g['_obstacles'] if g['z']-4<=v['z']<=g['z']+VISIBILITY]
    s=copy.deepcopy(s)
    return s


def _execute(g,action,projection=False):
    s=_visible_copy(g) if projection else copy.deepcopy(g)
    return advance_idle(step(s,action),DURATION)


def _delayed_projection(g,action):
    s=advance_idle(_visible_copy(g),LATENCY_SCENARIO_SECONDS)
    if not s['outcome']:s=advance_idle(step(s,action),LATENCY_EXECUTION_SECONDS)
    return s


def _delay_projection(g,action,delay):
    visible=_visible_copy(g);held=advance_idle(visible,delay)
    frames=held['execution_trace']['frames']
    if held['outcome']:return held,frames
    final=advance_idle(step(held,action),min(1.5,3.-delay))
    return final,frames[:-1]+final['execution_trace']['frames']


def _contact_facts(g,frames,delay=0.):
    """Summarize visible contact bands along an exact projected physics path."""
    visible=_visible_copy(g)
    obstacles=sorted((o for o in visible['_obstacles'] if o['id'] not in g['contacts'] and o['z']+CONTACT_HALF_LENGTH>=g['z']),key=lambda o:o['z'])
    first_damage=next((f for f in frames if f['health']<g['health']-1e-8),None)
    contact=None
    for obstacle in obstacles:
        overlap=[]
        for before,after in zip(frames,frames[1:]):
            clipped=_contact_segment(before['x'],before['z'],after['x'],after['z'],obstacle)
            if clipped is not None:overlap.append((before,after,clipped))
        if overlap:
            before,after,first=overlap[0]
            seconds=before['elapsed']-g['elapsed']+(after['elapsed']-before['elapsed'])*first['entry_fraction']
            contact={'obstacle_id':obstacle['id'],'seconds':round(seconds,2),
                     'x':round(first['entry_x'],2),'minimum_lateral_clearance_m':round(min(part['minimum_lateral_clearance_m'] for _,_,part in overlap),2)}
            break
    return {'first_damage_seconds':round(first_damage['elapsed']-g['elapsed'],2) if first_damage else None,
            'first_damage_phase':'waiting_old_input' if first_damage and first_damage['elapsed']-g['elapsed']<=delay else 'selected_input' if first_damage else None,
            'nearest_contact_band':contact}


def choices(g):
    result={}
    for action in _actions(g):
        immediate=_execute(g,action,projection=True)
        scenarios=[(0.,immediate,_contact_facts(g,immediate['execution_trace']['frames']))]
        for delay in DELAY_SCENARIOS:
            state,frames=_delay_projection(g,action,delay)
            scenarios.append((delay,state,_contact_facts(g,frames,delay)))
        damages=[round(g['health']-state['health'],1) for _,state,_ in scenarios]
        risk=min((facts['first_damage_seconds'],delay,facts) for delay,_,facts in scenarios if facts['first_damage_seconds'] is not None) if any(facts['first_damage_seconds'] is not None for _,_,facts in scenarios) else None
        contacts=[(delay,facts['nearest_contact_band']) for delay,_,facts in scenarios if facts['nearest_contact_band'] is not None]
        contact=min(contacts,key=lambda item:item[1]['minimum_lateral_clearance_m']) if contacts else None
        steer,pedal=action.split(':')
        risk_text=f"最早掉血t={risk[0]:.2f}s({risk[2]['first_damage_phase']})" if risk else '这些情景均未掉血'
        contact_text=(f"近障带最差情景delay={contact[0]:g}s：进入t={contact[1]['seconds']:.2f}s时x={contact[1]['x']:.2f}，带内最小横向净距{contact[1]['minimum_lateral_clearance_m']:.2f}m（负值未清空）" if contact else '投影内尚未到可见障碍接触带')
        result[action]=(f'{STEERING_LABELS[steer]} / {PEDAL_LABELS[pedal]}；'
            f'立即/延迟0.5/0.75/1.25/2秒的损伤={damages}，最坏{max(damages):.1f}；{risk_text}；{contact_text}；'
            f"立即2秒末x={immediate['x']:.2f}、横速{immediate['lateral_velocity']:.2f}、车速{immediate['speed']:.1f}、前进{immediate['z']-g['z']:.1f}m。仅列举可见条件情景，非所有延迟保证。")
    return result


def visible_control_facts(g):
    visible=_visible_copy(g)
    current=_section(visible['_track'],g['z'])
    brake=advance_idle(step(visible,'straight:brake'),3.)
    stopped=next((f for f in brake['execution_trace']['frames'] if f['speed']<=1e-9),None)
    held=advance_idle(visible,LATENCY_SCENARIO_SECONDS)
    return {
        'current_grip_speed_mps':current['grip_speed'],
        'visible_minimum_grip_speed_mps':min(s['grip_speed'] for s in visible['_track']),
        'road_edge_margin_m':{'left':round(g['x']+ROAD_CENTER_LIMIT,3),'right':round(ROAD_CENTER_LIMIT-g['x'],3)},
        'brake_now_visible_projection':{'stops':stopped is not None,
            'stop_seconds':round(stopped['elapsed']-g['elapsed'],3) if stopped else None,
            'distance_m':round((stopped or brake)['z']-g['z'],3),
            'health_lost':round(g['health']-brake['health'],3),
            'note':'当前可见信息下立即回正并刹车的确定性物理投影；碰撞也会减速，实际响应有延迟'},
        'old_input_after_assumed_wait':{'assumed_seconds':LATENCY_SCENARIO_SECONDS,
            'z':round(held['z'],3),'x':round(held['x'],3),'speed':round(held['speed'],3),
            'health':round(held['health'],3),'note':'保持旧输入的可见条件投影，非未来观测或实际延迟保证'},
        'approaching_sections':[{'distance_m':round(max(0,s['start']-g['z']),3),
            'at_current_speed_seconds':round(max(0,s['start']-g['z'])/g['speed'],3) if g['speed']>0 else None,
            'curve':s['curve'],'grip_speed':s['grip_speed']} for s in visible['_track'] if s['end']>g['z']],
        'approaching_obstacles':[{'id':o['id'],'x':o['x'],'distance_m':round(o['z']-g['z'],3),
            'at_current_speed_seconds':round((o['z']-g['z'])/g['speed'],3) if g['speed']>0 else None}
            for o in visible['_obstacles'] if o['z']>=g['z'] and o['id'] not in g['contacts']],
        'contact_time_note':'上面时间假设保持当前纵向速度；实际加速、转向、碰撞会改变结果，不是预测答案'}


def as_record(g):
    from jev_gameplay_contract import adapt_record
    from jev_racing_visible_geometry import visible_obstacle_geometry
    opts=choices(g);state=public(g);state['rules']=RULES;state['candidate_revision']=CANDIDATE_REVISION
    state['minimum_average_speed']=round((LENGTH-g['z'])/max(.001,TIME_LIMIT-g['elapsed']),2)
    state['current_goal']='安全完成优先，不追求最快；首次踩油门开始计时，在300秒内抵达900米终点'
    state['control_facts']=visible_control_facts(g)
    state['obstacle_geometry']=visible_obstacle_geometry(public(g))
    state['active_subgoal']=g.get('last_action')
    ident=f'rally-observation-{g["steps"]}'
    record=adapt_record({'schema_version':'jev.training.v1','id':ident,'group_id':ident,'state':state,
      'questions':{'decision':{'type':'choice','instructions':PROMPT,'criteria':opts,'option_order':list(opts)}},
      'labels':{},'provenance':{'data_source':'cues_live_rally_engine','source_id':ident,'source_split':'online','source_revision':REVISION},
      'metadata':{'domain':'game','sub_domain':KIND,'scenario':'Rally Sprint','task_category':'joint_steering_pedals','difficulty':'L2'}})
    record['state']['control'].update(goal=state['current_goal'],subgoal=g.get('active_action'),
        status=g['execution_status'],deadline=g['intent_expires_at'],deadline_unit='absolute_elapsed_seconds',
        remaining_seconds=max(0.,g['intent_expires_at']-g['elapsed']),
        steering_pulse_deadline=g.get('steering_pulse_deadline'),steering_pulse_duration=PULSE_SECONDS,
        steering_pulse_completed=g.get('steering_pulse_completed',False),
        events=list(g.get('execution_trace',{}).get('events',[])),
        fallback_actions=g['rule_takeover_count'],strategy_origin='human' if g['active_controller']=='human' else 'A',
        execution_origin='C' if g['expired_intent'] else 'B',
        abort_on=['new_input','intent_expired','terminal'])
    return record


def process_rewards(initial,trace):
    def potential(s):return .2*min(LENGTH,max(0,s['z']))/LENGTH-.15*(100-s['health'])/100
    prior=potential(initial);result=[]
    for t in trace:
        if 'credit_before_state' in t and 'credit_after_state' in t:
            result.append(potential(t['credit_after_state'])-potential(t['credit_before_state']))
        else:
            value=potential(t['after_state']);result.append(value-prior);prior=value
    return result
