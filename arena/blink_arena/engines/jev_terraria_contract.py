"""Shared Terramai intent Choices, with legacy directional-control compatibility.

Candidate facts use only the supplied public observation. Physics and selected
intent execution live in the real frontend engine; no private map or RNG is read
here. One Choice represents the entire action, including deterministic execution.
"""
DIRECTIONS={'left':'左','right':'右','up':'上','down':'下'}
TOOLS={'move':'移动／瞄准','mine':'挖矿','attack':'攻击','place':'放置方块'}
OPTIONS={('jump_' if jump else '')+tool+'_'+direction:('跳跃并' if jump else '')+'朝'+name+label for jump in [False,True] for direction,name in DIRECTIONS.items() for tool,label in TOOLS.items()}
OPTIONS['wait']='原地等待'
INTENTS={
 'explore_right':'沿已见地表向右探索一个局部路段；底层按可见地形走、起跳、挖通、搭桥，遇到前方威胁返回模型选择策略',
 'explore_left':'沿当前可见地形向左返回一个局部路段；无需有敌人，底层清障、起跳、搭桥，遇左侧威胁或未知边界返回，不自动战斗',
 'approach_guardian':'接近指定守门 Boss；绑定当前可见守卫或此前亲眼见到的位置，在可见地形内向左/右接近、挖掘下行或搭柱上行；进入真实剑框范围即返回，不自动攻击，不保证旧位置仍有守卫',
 'fight_guardian':'只攻击当前可见的指定守门 Boss，不被更近的小怪替代；底层接近并调整高度、按原生剑框瞄准挥剑，目标离开视野/死亡/受阻即返回，不自动换目标',
 'return_surface':'返回已见地表高度；底层清理头顶、按可见材料采集和搭柱，真正落地后结束',
 'cross_gap_right':'跨过当前可见坑；底层起跳/搭桥并保持方向，首次落地完成',
 'clear_right':'挖通右侧当前可见障碍并前进一个局部路段',
 'fight_nearest':'只对当前最近可见敌人战斗；底层接近、瞄准、在射程内攻击，目标消失结束，不自动换敌',
 'pass_enemy_right':'绕过当前最近可见敌人向右脱离；底层在可见地形起跳、保持方向并清障，到该敌人右侧八格结束，为模型推理等待保留距离，不自动攻击或改追另一敌人',
 'retreat_left':'向左撤离当前最近可见威胁；底层起跳/避碰和处理可见障碍，拉开七格后结束，不自动转战斗',
 'collect_visible':'收集一个当前可见目标：优先食物、装备掉落、宝箱、矿物，各类内选最近；底层按公开地图规划、移动或挖掘，目标消失后检查实际收益，不自动改采下一个',
 'collect_visible_gem':'收集当前可见的一块宝石矿(8)；仅在宝石矿中选最近，复用可见路径与原生挖掘，不采其他矿或替你决定成长路线',
 'recover':'松开按键恢复或等待重生；敌人和时间继续，受伤立即返回；不会自动格挡',
 'reach_known_goal':'前往已亲眼见到的胜利之门；仅玩家参与击败指定守门 Boss 后可进入通关；底层走到门的实际坐标/高度，遇前方已见威胁先返回模型选择战斗、绕敌或撤退，不自动切换策略；必须原生 wins 增加才胜利'}

RULES='Terramai 像素沙盒，x 向右、y 向下，有重力与碰撞。观测中的 player.x/y 和 enemies.x/y 已换算为世界格坐标（每格16像素），表示实体左上角，保留1位小数；player.tile 是角色中心所在格的整数坐标。map.origin=[x,y] 是局部地图左上角的世界格坐标；map.tiles[row][col] 对应世界格 (map.origin[0]+col,map.origin[1]+row)，row 向下、col 向右。动作由四方向、移动/挖矿/攻击/放置及可选跳跃组成，原子动作推进36个物理帧（60帧/秒下0.6秒）；仅当候选中提供持续意图时，该意图最多执行96帧并在落地、受阻、危险或死亡事件提前返回。左右方向同时水平移动；上下方向改变瞄准，不会飞行，跳跃只能从地面起跳。挖矿、攻击与放置均朝所选方向；放置消耗方块且不能把自己埋住。矿石自动升级装备。仅观察已探索局部地图，-1 为未知。胜利条件是玩家参与击败指定守门 Boss 后，活着进入地图右侧地表的胜利之门；普通怪或其他 Boss 不会解锁。仅已有真实玩家命中且伤害大于0的环境助杀可计玩家参与；纯环境死亡不算玩家击杀、不授予击杀经验且不解锁。采矿、击败适合的小怪和真实装备升级有助于准备守门战斗，不能替代通关；known_goal 只在探索到门后给出坐标。last_known_surface 是此前亲眼看见的最近草地格，不保证是当前列地表；recent_player_tiles 是最近动作结束时的实际位置。'

LEGACY_PROMPT_REVISION = 'terramai-visible-hierarchy-v18-targeted-navigation'
PROMPT_REVISION = 'terramai-visible-hierarchy-v19-compact-public-facts'
ATOMIC_INSTRUCTIONS = '你在持续探索沙盒世界，最终目标是先通过采矿、小怪战斗和装备成长做好准备，玩家参与击败守门 Boss 后活着进入右侧地表胜利之门。每次只能选择本次 option 中存在的一个原子动作；左右动作同时横移，上下动作只瞄准，不会自动寻路或爬升。每个动作最多36帧，等待模型回复时按键松开而世界、敌人和重力继续运行。\n持续计划分为：沿地表探索并接近门；处理当前可见障碍；必要时采集沿途资源、攻击威胁或撤离恢复，然后继续原目标。先读最近动作实际效果、位置变化与当前候选靶格，不要连续重复无效果动作。\n探索：地形平缓时向右；遇台阶/坑且头顶有空间，用 jump_move_right；地面或空中向右均无进展时，检查候选所示前方实心格，改用 mine_right 或 jump_mine_right 挖通阻挡。低顶阻止起跳时用 mine_up/jump_mine_up 清头顶，再移动；不要只重复跳跃撞墙。\n回地表：player 脚底 y 明显大于已见草地高度时，优先寻找可见台阶或跳跃路线；竖井可用 jump_place_down 在腾空后脚下垫方块，每次检查实际升高和库存，头顶实心先挖开。建材不足时采集侧面可见泥土/石块，不要不断挖脚底使自己更深；同一动作无效果要换靶格。\n战斗与防御：attack_方向 才会挥剑，move不会攻击；左右攻击同时横移，jump_attack_方向 可结合跳跃避险。只打当前范围可达的敌人；指定守门 Boss 是通关前置，先读当前装备和 navigation.combat 判断战力；弱小普通怪可积累真实击杀经验，强敌前先采矿升级、恢复和选择安全战斗位置，绕过守门 Boss 不会解锁门。没有格挡键，防御靠保持距离、跳跃与掩体；低血量先离开威胁，再在安全处等待恢复，原地受击时等待不能救命。\n收集：宝箱(13)、可见食物/掉落物靠近自动拾取；可见矿物(4–8)要朝正确靶格挖掘，带来真实装备提升。优先顺路或恢复所需资源，不能用地下无限采矿代替完成任务。\nknown_goal 有坐标后，比较角色与门的横向和高度差；选择实际移动/跳跃/挖掘抵达门，接近后别继续冲过。objective.gate_unlocked 为真后，进入门并以原生 wins 增加才算成功；未解锁时先处理守门 Boss。未知格(-1)不当成安全空地；敌人和落点会在推理等待期间变化，候选描述只代表观察时事实。只输出合法动作 ID。'


def atomic_facts(observation):
 """Describe only the captured public map; never query the engine or its RNG."""
 import math
 player=observation['player']; terrain=observation['map']; x,y=player.get('geometry',player)['x'],player.get('geometry',player)['y']
 width,height=player.get('width',.625),player.get('height',1.25)
 solid={1,2,3,4,5,6,7,8,9,11}; hardness={1:10,2:10,3:24,4:28,5:34,6:40,7:55,8:45,9:16,10:4}
 def tile(tx,ty):
  row,col=ty-terrain['origin'][1],tx-terrain['origin'][0]
  return terrain['tiles'][row][col] if 0<=row<len(terrain['tiles']) and 0<=col<len(terrain['tiles'][row]) else -1
 targets=observation.get('tool_targets')
 if targets is None:
  targets={};mx=math.floor(x+width/2);hy=math.floor(y+3/16);fy=math.floor(y+height-3/16)
  for direction in DIRECTIONS:
   tx=math.floor(x-2/16) if direction=='left' else math.floor(x+width+2/16) if direction=='right' else mx
   ty=math.floor(y)-1 if direction=='up' else math.floor(y+height+2/16) if direction=='down' else hy if tile(tx,hy) in solid else fy
   value=tile(tx,ty);targets[direction]={'tile':[tx,ty],'value':value,'solid':value in solid,'mineable':value in hardness,'hardness':hardness.get(value,0)}
 surface=[]
 for row,line in enumerate(terrain['tiles']):
  for col,value in enumerate(line):
   if value==2:surface.append([terrain['origin'][0]+col,terrain['origin'][1]+row])
 effects=observation.get('last_effects',[])
 anchor=observation.get('last_known_surface')
 foot_y=round(y+height,2);ground_row=math.floor(foot_y+.05);support={}
 for direction,sign in [('left',-1),('right',1)]:
  columns=[]
  for offset in range(1,5):
   tx=math.floor(x+width/2)+sign*offset
   cells=[tile(tx,ground_row+depth) for depth in range(6)]
   ground=next((ground_row+i for i,value in enumerate(cells) if value in solid),None)
   columns.append({'x':tx,'first_visible_support_y':ground,'has_unknown_below':-1 in cells,'visible_hazard':any(t in (14,15) for t in cells)})
  support[direction]=columns
 return {'target_basis':'engine_visible_exact' if observation.get('tool_targets') else 'rounded_public_position_estimate_may_differ_one_tile_at_boundaries',
         'tool_targets':targets,'visible_grass_cells':surface,
         'foot_y':foot_y,'last_seen_surface':anchor,'below_last_seen_surface_tiles':round(foot_y-anchor[1],2) if anchor else None,'nearby_support':support,'recent_actual_effects':effects,
         'no_displacement_actions':sum(abs(e.get('delta_x',0))<.1 and abs(e.get('delta_y',0))<.1 for e in effects[-3:]),
         'uncertainty':'当前可见格和实际历史；未预测未来随机事件，推理等待会改变位置/敌人，跳跃落点与可达性须执行验证。'}


def atomic_options(observation,facts):
 options={};labels=observation['map'].get('legend',{})
 for action,label in OPTIONS.items():
  if action=='wait':
   options[action]='松开按键等待36帧；重力/敌人持续运行；8秒未战斗后才缓慢回血，附近危险时会继续受伤';continue
  direction=action.rsplit('_',1)[-1];tool=action.removeprefix('jump_').split('_',1)[0]
  target=facts['tool_targets'][direction];value=target['value']
  described=labels.get(str(value),labels.get(value,str(value)))
  detail='；当前瞄准格'+str(target['tile'])+'='+str(described)
  if tool=='mine':detail+='；'+('可开采，命中后才有收益' if target['mineable'] else '此刻无可开采方块，移动/跳跃后靶格可能改变')
  if tool=='place':detail+='；库存'+str(observation.get('equipment',{}).get('dirt',0))+'；仅空格且不重叠玩家才可放'
  if tool=='move' and direction in ('left','right') and target['solid']:detail+='；当前前方实心阻挡，纯走不能穿过'
  if direction in ('up','down'):detail+='；无横向移动，不会因朝上而升高'
  depth=facts.get('below_last_seen_surface_tiles')
  if direction in ('left','right'):
   nearby=facts['nearby_support'][direction]
   unsupported=[c['x'] for c in nearby if c['first_visible_support_y'] is None]
   hazards=[c['x'] for c in nearby if c['visible_hazard']]
   if unsupported:detail+='；前方列'+str(unsupported)+'当前脚下6格未见支撑（含未知时不能断言安全）'
   if hazards:detail+='；前方列'+str(hazards)+'脚下可见熔岩/毒雾'
   if depth is not None and depth>3:detail+='；当前低于已见地表'+str(depth)+'格，纯横移/横挖不会上升'
  if action=='jump_place_down':detail+='；腾空后尝试在脚下搭柱抬高站位，可用于回地表，实际效果看落地高度和建材变化'
  if action in ('mine_up','jump_mine_up'):detail+='；清理头顶实心格，为向上跳/搭柱腾空间'
  if tool=='attack':detail+='；挥剑有26帧冷却，近身命中才伤害；'+('同时横移' if direction in ('left','right') else '原地瞄准')
  if action.startswith('jump_'):
   above=facts['tool_targets']['up'];above_label=labels.get(str(above['value']),str(above['value']))
   detail+='；仅接触地面时起跳；当前头顶'+str(above['tile'])+'='+above_label
   if above['solid']:detail+='，会碰顶，未挖开前无法完整上升'
  recent=observation.get('last_actions',[])
  if len(recent)>=3 and all(a==action for a in recent[-3:]):
   positions=observation.get('recent_player_tiles',[])[-4:]
   if positions and max(p[0] for p in positions)-min(p[0] for p in positions)<=1 and max(p[1] for p in positions)-min(p[1] for p in positions)<=1:
    detail+='；警告：此动作连续重复且实际位置未明显变化，检查靶格/头顶/库存并换动作'
  options[action]=label+detail
 return options

def native_attack_facts(observation,enemy):
 """Original native attackRectangle / strict AABB overlap in public geometry."""
 player=observation['player'];p={**player,**player.get('geometry',{})};e={**enemy,**enemy.get('geometry',{})}
 exact=all(k in player.get('geometry',{}) for k in ('x','y')) and all(k in enemy.get('geometry',{}) for k in ('x','y','width','height'))
 x,y,w,h=p['x']*16,p['y']*16,p.get('width',.625)*16,p.get('height',1.25)*16
 ex,ey,ew,eh=e['x']*16,e['y']*16,e.get('width',1)*16,e.get('height',1)*16
 rectangles={};hits=[]
 for aim in ('left','right','up','down'):
  dx=-1 if aim=='left' else 1 if aim=='right' else 0;dy=-1 if aim=='up' else 1 if aim=='down' else 0
  rx=x+w if dx>0 else x-28 if dx<0 else x-6;ry=y-28 if dy<0 else y+h if dy>0 else y-6
  rw=28 if dx else w+12;rh=28 if dy else h+12
  intersects=ex+ew>rx and ex<rx+rw and ey+eh>ry and ey<ry+rh
  rectangles[aim]={'x':rx/16,'y':ry/16,'width':rw/16,'height':rh/16,'intersects_enemy':intersects}
  if intersects:hits.append(aim)
 return {'geometry_exact':exact,'geometry_basis':'current_visible_exact_native_geometry' if exact else 'legacy_rounded_geometry_estimate',
         'rectangles_tiles':rectangles,'hitting_directions':hits,'geometrically_in_range':bool(hits),
         'strict_overlap':True,'uncertainty':'仅当前几何；旧记录缺精确geometry时为估计。攻击冷却、推理等待及实体移动可能改变实际命中，不保证未来伤害或安全。'}


def combat_facts(observation):
 import math
 player=observation['player'];p={**player,**player.get('geometry',{})};gear=observation.get('equipment',{});buffs=observation.get('active_buffs',{});facts=[]
 attack=((5+gear.get('sword',1)*4)*gear.get('swordMul',1)+gear.get('potAtk',0))*(2 if buffs.get('power',0)>0 else 1)
 for enemy in observation.get('enemies',[]):
  e={**enemy,**enemy.get('geometry',{})};width,height=e.get('width',1),e.get('height',1)
  gap_x=max(0,abs(e['x']+width/2-p['x']-p.get('width',.625)/2)-(width+p.get('width',.625))/2)
  gap_y=max(0,abs(e['y']+height/2-p['y']-p.get('height',1.25)/2)-(height+p.get('height',1.25))/2)
  base={'slime':8,'zombie':13,'bat':6}.get(enemy.get('kind'));damage=None
  if base is not None:
   damage=max(2,math.floor(base*(1+.55*(enemy.get('level',1)-1))+observation.get('wins',0)-gear.get('armor',0)*2*gear.get('armorMul',1)-gear.get('potArm',0)*2+.5))
   if enemy.get('boss'):damage=math.floor(damage*.8+.5)
   if buffs.get('shield',0)>0:damage=0
  facts.append({'enemy':enemy,'horizontal_body_gap_tiles':round(gap_x,2),'vertical_body_gap_tiles':round(gap_y,2),
   'native_attack':native_attack_facts(observation,enemy),
   'previous_failed_attempts':[f for f in observation.get('control',{}).get('failed_targets',[]) if f.get('intent')=='fight_nearest' and f.get('target',{}).get('id')==enemy.get('id')],
   'contact_damage_under_current_buffs':damage,'minimum_attacks_to_defeat_if_all_hit':math.ceil(enemy['hp']/attack),
   'hits_to_player_death_without_healing':math.ceil(p['hp']/damage) if damage else None,
   'uncertainty':'当前可见位置，可能在推理期间接近；攻击数假定全部命中，不保证安全/成功。'})
 return facts



ORE_POINTS={4:1,5:2,6:3,7:5}


def _next_pts_upgrade(gear,cap):
 if gear['pick']<=gear['sword'] and gear['pick']<cap:return 'pick'
 if gear['sword']<cap:return 'sword'
 if gear['armor']<cap:return 'armor'
 return None


def _apply_points(gear,points,cap):
 gear['pts']+=points
 while True:
  target=_next_pts_upgrade(gear,cap)
  if target is None or gear['pts']<3+gear[target]:break
  gear['pts']-=3+gear[target];gear[target]+=1


def _apply_gem_armor(gear,cap):
 while gear['armor']<cap and gear['gems']>=(gear['armor']+1)*2:gear['armor']+=1


def progression_facts(observation):
 """Original public upgrade rules; no hidden resource or RNG lookup."""
 gear=observation.get('equipment',{});g={k:gear.get(k,1 if k in ('pick','sword') else 0) for k in ('pick','sword','armor','pts','gems')}
 cap=2*(10+observation.get('wins',0));target=_next_pts_upgrade(g,cap)
 threshold=(g['armor']+1)*2 if g['armor']<cap else None
 return {'equipment':g,'equipment_level_cap':cap,
  'next_pts_upgrade':{'target':target,'cost':3+g[target] if target else None,'points_short':max(0,3+g[target]-g['pts']) if target else 0},
  'next_gem_armor_upgrade':{'threshold_total_gems':threshold,'gems_short':max(0,threshold-g['gems']) if threshold is not None else 0,'consumes_gems':False},
  'ore_points_by_tile':{str(k):v for k,v in ORE_POINTS.items()},'gem_tile':8,'gem_gain_per_mined_tile':1,
  'rules':'矿点优先镐/剑：镐不高于剑且未到上限时先升镐，否则升未满剑，二者满后才用点数升甲；每次成本3+该装备当前等级。宝石是累计数量，不扣除；挖到宝石或击败lv>=3敌人时按每2颗一级触发护甲升级。',
  'player_participating_kill':'真实玩家参与击败敌人才给该敌人level点数；level>=3另+1宝石并触发升甲；Boss之后另+5宝石，该额外5颗不会当场再次触发升甲。纯环境击杀无这些成长收益。',
  'uncertainty':'这是公开规则与当前装备；采集/击杀需要真实执行成功，宝箱未来结果随机未知。'}


def resource_equipment_effect(observation,target):
 from copy import deepcopy
 facts=progression_facts(observation);before=facts['equipment'];after=deepcopy(before);tile=target.get('tile') if target else None
 if tile in ORE_POINTS:_apply_points(after,ORE_POINTS[tile],facts['equipment_level_cap'])
 elif tile==8:after['gems']+=1;_apply_gem_armor(after,facts['equipment_level_cap'])
 else:return {'deterministic':False,'equipment_after':None,'reason':'宝箱未来随机结果未知；其他拾取收益未在此预测' if target else '无当前可见目标'}
 return {'deterministic':True,'condition':'当前装备不变且真正成功采得该矿；不保证路径可达或等待后目标仍存在',
         'equipment_after':after,'equipment_delta':{k:after[k]-before[k] for k in before},'points_gained':ORE_POINTS.get(tile,0),'gems_gained':int(tile==8)}


def collection_facts(observation,gem_only=False):
 """Same public priority/distance/x/y ordering as jevIntentKeys."""
 import math
 player=observation['player'];p={**player,**player.get('geometry',{})};terrain=observation['map'];targets=[]
 if not gem_only:
  for priority,key in [(0,'visible_collectibles'),(1,'visible_equipment_drops')]:
   targets.extend({'kind':'pickup','id':c['id'],'x':c['x'],'y':c['y'],'priority':priority} for c in observation.get(key,[]))
 for row,line in enumerate(terrain['tiles']):
  for col,tile in enumerate(line):
   if (tile==8 if gem_only else tile==13 or 4<=tile<=8):
    targets.append({'kind':'chest' if tile==13 else 'ore','tile':tile,'x':terrain['origin'][0]+col,'y':terrain['origin'][1]+row,'priority':2 if tile==13 else 3})
 target=min(targets,key=lambda t:(t['priority'],math.hypot(t['x']-p['x'],t['y']-p['y']),t['x'],t['y']),default=None)
 failures=[f for f in observation.get('control',{}).get('failed_targets',[]) if target is not None and
           all(f.get('target',{}).get(k)==target.get(k) for k in ('kind','id','tile','x','y'))]
 return {'target':target,'candidate_available':target is not None,'scope':'currently_visible_gem8_only' if gem_only else 'current_visible_food_equipment_chest_then_nearest_ore',
         'target_basis':'current_public_exact_player_geometry' if player.get('geometry') else 'rounded_public_player_estimate',
         'successful_collection_effect':resource_equipment_effect(observation,target),
         'previous_failed_attempts':failures,'previous_failure_count':sum(f.get('failures',0) for f in failures),
         'failure_history_scope':'已执行的同一公开资源目标；历史失败不证明当前不可达，位置/地形/装备变化后可由模型决定重试',
         'uncertainty':'当前可见目标；推理期间物理继续，实际执行重新绑定最近合法目标，不保证到达或采得。'}


def nearest_visible_enemy(observation):
 """Mirror jevIntentKeys target binding using only the public observation."""
 import math
 player=observation['player'];p={**player,**player.get('geometry',{})}
 return min(observation.get('enemies',[]),
            key=lambda e:(math.hypot(e['x']-p['x'],e['y']-p['y']),e.get('id',0)),default=None)


def guardian_target_facts(observation):
 """Bind exactly like JS, to current sight or an explicitly stale sighting."""
 import math
 player=observation['player'];p={**player,**player.get('geometry',{})}
 guardians=[e for e in observation.get('enemies',[]) if e.get('gate_guardian')]
 enemy=min(guardians,key=lambda e:(math.hypot(e['x']-p['x'],e['y']-p['y']),e['id']),default=None)
 target=None
 if enemy is not None:
  e={**enemy,**enemy.get('geometry',{})}
  target={'kind':'guardian','id':enemy['id'],'x':e['x'],'y':e['y'],'width':e['width'],'height':e['height'],
          'last_seen_frame':observation['frame'],'visible':True}
 elif observation.get('known_guardians'):
  old=max(observation['known_guardians'],key=lambda e:(e['last_seen_frame'],-e['id']))
  target={**old,'kind':'guardian','visible':False}
 defeated=observation.get('objective',{}).get('guardian_defeated_by_player',False)
 attack=native_attack_facts(observation,enemy) if enemy is not None else None
 in_range=bool(attack and attack['hitting_directions'])
 at_old_position=bool(target and enemy is None and math.hypot(
   target['x']+target['width']/2-p['x']-p['width']/2,
   target['y']+target['height']/2-p['y']-p['height']/2)<1.5)
 return {'target':target,'visible':enemy is not None,'native_attack':attack,
         'approach_candidate_available':bool(target and not defeated and not in_range and not at_old_position),
         'fight_candidate_available':bool(enemy is not None and not defeated),
         'observed_age_frames':max(0,observation['frame']-target['last_seen_frame']) if target else None,
         'at_last_seen_position_without_reacquisition':at_old_position,
         'uncertainty':'仅当前可见或此前实际观察的守卫；历史位置可能过期，不提供未见位置、未来血量或隐藏寻路。接近不自动攻击，战斗不自动换成小怪。'}


def enemy_motion_facts(observation):
 """Exact current completion predicates; no forecast of arrival-time safety."""
 player=observation['player'];p={**player,**player.get('geometry',{})}
 enemy=nearest_visible_enemy(observation)
 exact=all(k in player.get('geometry',{}) for k in ('x','y'))
 facts={'target':enemy,'target_basis':'public_exact_player_geometry_distance_then_enemy_id' if exact else 'rounded_public_player_estimate',
        'completion_check_is_exact':exact,
        'uncertainty':'仅当前观察时刻。推理期间世界继续、敌人可能移动或目标重绑；零位移指状态不变时意图已完成，不保证未来安全。'}
 if enemy is None:return facts
 # Keep the original JS arithmetic and strict inequalities at the boundary.
 right=p['x']+p['width'];retreat_limit=enemy['x']-7;pass_limit=enemy['x']+enemy['width']+8
 for action,complete,margin,predicate in (
     ('retreat_left',right<retreat_limit,retreat_limit-right,'player.x + player.width < enemy.x - 7'),
     ('pass_enemy_right',p['x']>pass_limit,p['x']-pass_limit,'player.x > enemy.x + enemy.width + 8')):
  facts[action]={'target_id':enemy['id'],'already_satisfied':complete,
      'completion_margin_tiles':margin,'strict_completion_predicate':predicate,
      'candidate_omitted':bool(exact and complete),
      'controlled_horizontal_displacement_if_state_unchanged':0 if exact and complete else None,
      'omission_reason':'current_selected_target_already_completed' if exact and complete else None}
 facts['player_left']=p['x'];facts['player_right']=right
 facts['retreat_boundary_x']=retreat_limit;facts['pass_boundary_x']=pass_limit
 return facts


def visible_approach_threats(observation):
 """Mirror the existing public explore/reach-goal trigger, not a safety oracle."""
 player=observation['player'];p={**player,**player.get('geometry',{})}
 return [e for e in observation.get('enemies',[]) if e['x']+e['width']>p['x']-1
         and e['x']-p['x']<7 and abs(e['y']-p['y'])<5]


def return_surface_anchor(observation):
 """Choose the same public target that JS will bind for this selected intent."""
 control=observation.get('control') or {};anchor=control.get('target_surface');terrain=observation['map']
 def valid_support(cell):
  if not isinstance(cell,(list,tuple)) or len(cell)!=2:return False
  x,y=cell[0]-terrain['origin'][0],cell[1]-terrain['origin'][1]
  if 0<=y<len(terrain['tiles']) and 0<=x<len(terrain['tiles'][y]):
   return terrain['tiles'][y][x] in (-1,1,2,3,4,5,6,7,8,9,11)
  return True  # A previously observed out-of-view anchor is uncertain memory.
 retain=(control.get('target_surface_owner')=='return_surface' and control.get('status')!='completed' and valid_support(anchor)
         and not observation.get('player',{}).get('respawning')
         and not set(control.get('events',())).intersection(('goal_reached','goal_door_entered','death_or_respawn','respawned')))
 if retain:return list(anchor)
 local=observation.get('last_known_surface')
 return local if valid_support(local) else None


def _as_record_v18(observation):
 if not isinstance(observation.get('player'),dict) or not isinstance(observation.get('map'),dict):
  if observation.get('control'):raise ValueError('semantic_control_requires_public_player_and_map')
  return {'schema_version':'jev.training.v1','id':'live-terramai','group_id':'live-terramai','state':{'role':'Terramai 玩家','prompt_revision':LEGACY_PROMPT_REVISION,'rules':RULES,'action_layout':'directional-combos-v2','observation':observation,'navigation':{'status':'unavailable','reason':'legacy_observation_missing_player_or_map'}},'questions':{'decision':{'type':'choice','instructions':ATOMIC_INSTRUCTIONS,'criteria':dict(OPTIONS),'option_order':list(OPTIONS)}},'labels':{},'provenance':{'data_source':'Xinji-Mai/Terramai','source_id':'live','source_split':'demo'},'metadata':{'domain':'games','sub_domain':'terramai_directional','scenario':'interactive_control'}}
 facts=atomic_facts(observation);facts['combat']=combat_facts(observation)
 facts['objective']=dict(observation.get('objective') or {});facts['progression']=dict(observation.get('progression') or {});facts['upgrade_rules']=progression_facts(observation)
 control=observation.get('control')
 options=dict(INTENTS) if control else atomic_options(observation,facts)
 if control:
  player=observation['player'];anchor=return_surface_anchor(observation);facts['return_surface_anchor']=anchor
  targeted=control.get('executor_revision')=='visible-hierarchy-v18-targeted-navigation'
  if targeted:
   guardian=guardian_target_facts(observation);facts['guardian_target']=guardian
   for action,available in [('approach_guardian',guardian['approach_candidate_available']),('fight_guardian',guardian['fight_candidate_available'])]:
    if not available:options.pop(action,None)
    else:options[action]+='；当前公开绑定目标='+str(guardian['target'])+'；旧观察距今帧数='+str(guardian['observed_age_frames'])
  else:
   for action in ('explore_left','approach_guardian','fight_guardian'):options.pop(action,None)
  threats=visible_approach_threats(observation);facts['approach_threat_ids']=[e.get('id') for e in threats]
  if not anchor or player.get('on_ground') and facts['foot_y']<=anchor[1]+.2:options.pop('return_surface',None)
  if not observation.get('known_goal'):options.pop('reach_known_goal',None)
  else:options['reach_known_goal']+='；已见门='+str(observation['known_goal'])+'；当前门已解锁='+str(observation.get('objective',{}).get('gate_unlocked','未知'))+'；未解锁到门前会受阻，必须玩家参与击败守门 Boss，不会自动战斗'
  for action in ('explore_right','reach_known_goal'):
   if action in options:
    options[action]+='；当前触发重决策的可见敌人ID='+str(facts['approach_threat_ids'])+'；执行中逐帧复查，发现威胁即停止并返回模型；等待回复时世界继续，不保证回复前安全'
  motion=enemy_motion_facts(observation);facts['enemy_motion']=motion
  enemies=observation.get('enemies',[])
  if not enemies:
   for action in ('fight_nearest','pass_enemy_right','retreat_left'):options.pop(action,None)
  else:
   enemy=motion['target']
   for action in ('fight_nearest','pass_enemy_right','retreat_left'):
    options[action]+='；当前绑定目标='+str(enemy)+'；推理期间目标移动，执行时以当时最近可见目标重新绑定并记录，不预测保证安全'
   selected_combat=next(c for c in facts['combat'] if c['enemy']['id']==enemy['id']);hit=selected_combat['native_attack']
   options['fight_nearest']+='；当前原生剑框命中方向='+str(hit['hitting_directions'])+'，精确几何='+str(hit['geometry_exact'])+'；没有相交时底层先对齐/接近/可见头顶允许时起跳，不把近似距离当作已能命中；90帧无接近或有效命中会返回受阻'
   if selected_combat['previous_failed_attempts']:options['fight_nearest']+='；该敌此前执行失败='+str(selected_combat['previous_failed_attempts'])
   for action in ('retreat_left','pass_enemy_right'):
    result=motion[action]
    if result['candidate_omitted']:
     options.pop(action)
    else:
     options[action]+='；当前完成条件='+result['strict_completion_predicate']+'，完成边界余量='+str(round(result['completion_margin_tiles'],4))+'格（严格大于0才完成）；当前已满足='+str(result['already_satisfied'])+'；只描述当前公开几何，不预测等待后的敌人位置'
  if 'return_surface' in options:options['return_surface']+='；已见锚点='+str(anchor)+'，脚底='+str(facts['foot_y'])+'，库存方块='+str(observation.get('equipment',{}).get('dirt',0))
  facts['collection']={}
  for action in ('collect_visible','collect_visible_gem'):
   collection=collection_facts(observation,gem_only=action=='collect_visible_gem');facts['collection'][action]=collection
   if not collection['candidate_available']:options.pop(action,None)
   else:
    options[action]+='；当前绑定目标='+str(collection['target'])+'；真正采得后的当前装备规则后果='+str(collection['successful_collection_effect'])+'；矿物需要原生工具耗时，路径和等待后的实际目标须执行验证'
    if collection['previous_failed_attempts']:options[action]+='；该目标此前实际失败='+str(collection['previous_failed_attempts'])+'；未证明当前不可达，是否改变位置/子目标或重试由你决定'
  for action in options:
   budget=360 if action in ('return_surface','reach_known_goal','approach_guardian') else 300 if action=='recover' else 240
   options[action]+='；动作期限 '+str(budget)+' 帧，目标完成/未知/不可恢复受阻/死亡提前结束'
 rules=RULES
 if control:
  rules=RULES.split('动作由四方向')[0]+'仅观察已探索局部地图，-1为未知。胜利要求玩家参与击败指定守门 Boss，令 objective.gate_unlocked 为真，再活着进入右侧地表门并使原生 wins 增加；其他 Boss/小怪不解锁；至少一次真实玩家命中并造成正伤害后的环境助杀计玩家参与，纯环境死亡不算玩家击杀或击杀经验。采矿与小怪战斗可提升装备，为守门战斗做准备。模型只从语义意图选择一个，原子键盘动作由底层机械执行。复用原生 Dijkstra 代价算法，但路径只读取本次可见地图；路径仅候选路线，身体碰撞、支撑、工具射程与库存须逐帧验证。探索/采集/绕敌最多240帧，回地表/进门360帧，恢复300帧。中途落地属于执行反馈，不要求重新选择相同机械动作；绕敌/撤离/选定战斗在受伤后仍完成已选动作或期限，不会自动换策略。未通关时等待模型仍松键且物理继续；原生通关后本模型局终止，显式重置才开始新局。'
 instructions=ATOMIC_INSTRUCTIONS if not control else (
  '你只决定意图，底层会在已见地图内执行寻路、碰撞避让、起跳、挖通、搭桥和瞄准。所有意图是同一个 decision Choice 的互斥动作，单选概率就是完整动作概率。'
  'return_surface 只延续该意图自己的有效地表锚点；从其他意图切换时使用当前已见局部地表，不继承胜利门的远端高度。'
  'navigation.upgrade_rules 给出下一矿点升级目标/成本/缺口和宝石护甲门槛；普通矿点主要升镐/剑，护甲可通过宝石成长。collect_visible_gem 由你明确选择当前可见宝石，不代替你决策；collect_visible 保留原优先级。宝箱未来结果未知，不能据随机奖励规划必胜。'
  '持续总目标是成长、击败守门 Boss、再进入胜利门。先用 collect_visible 采集当前可见矿物/宝箱/食物，用 fight_nearest 处理战力适合的普通怪，核对 progression 与 equipment 的真实升级；按需要 explore_right 与 return_surface 探索和回地表。守门 Boss 只在当前可见 enemies 中以 gate_guardian=true 标识，不会提供未探索位置；击败后 objective.gate_unlocked 才为真，已见门后再 reach_known_goal。矿物、小怪、升级都不能替代原生 wins。'
  '探索和前往已见门遇前方可见威胁都会停下让你选战斗、绕敌或撤退；此时继续重复进门会再次停止，应先选择你认可的威胁处理意图。读取 navigation.combat 比较敌人血量/自身生存；守门 Boss 是必须击败的目标；战力不足时可以暂避、采集升级和恢复后再来。非守门 Boss 不是通关前置，可选择绕行继续成长/探索，不必反复靠近和退避。pass_enemy_right 只改变位置，不会绕过守门前置；retreat_left 用于拉开距离。navigation.enemy_motion 给出与执行器一致的当前完成条件；已完成的绕行/撤离意味着当前状态不变时机械横移为0，所以不列为本次候选；这不保证之后安全，需要等待恢复可选择 recover。'
  '当前可见实体的 geometry 是精确格坐标，供原生四向剑框相交计算；旧记录缺该字段时 native_attack 只提供四舍五入位置估计，不能保证边界命中。近身弱敌可以 fight_nearest，底层只打已绑定的最近可见敌人，不会自动换敌或决定升级路线。collect_visible 与 collect_visible_gem 各自绑定当前真实可见目标；查看矿物点数带来的镐/剑/护甲提升，避免无限采矿却不准备守门战斗。普通怪/其他 Boss 被击败并不解锁门。'
  'recover 只有安全时才适合，8秒未受伤后才能缓慢恢复；站在敌人旁等待不会防御。死亡和重生次数在 progression 累计，重生不会替你击败守门 Boss或解锁门；核对真实 HP/装备和恢复成本，不以送死代替战术撤离。'
  '读取 control.target/subgoal、recent_effects、failed_targets、失败原因和 no_progress_count；有效进度以至少0.25格净位移、实际资源/生命/装备收益、真实玩家命中伤害、未被还原的地形改变或同一靶格的原生挖掘进度判断，轻微抖动和同格挖放循环不算进度。采集按当前可见路径下行，不把下行路线反复搭桥封住；失败目标会记录原因与次数并在候选展示，未证明不可达时由你决定是否重试。不能口头宣布成功。未知格不是安全空地；当前候选事实来自观察，推理期间敌人/位置会变化，底层执行中验证。只输出合法意图ID。')
 if control and targeted:
  instructions+=' 新执行接口：explore_left 可以在没有敌人时向左返回；approach_guardian 只接近当前/历史已见守卫并处理高低差，不自动挥剑；fight_guardian 绑定当前可见守卫，不被更近的小怪替代。known_guardians 是此前观察的历史位置，不保证守卫还在那里。准备可战后保持“接近守卫→实际命中并持续战斗→门解锁后进门”的子目标；接触伤害不等于每次挥剑必受伤，240帧到期但已造成伤害不表示无进展。根据真实 HP 与几何判断是否继续，必要时恢复。'
 return {'schema_version':'jev.training.v1','id':'live-terramai','group_id':'live-terramai','state':{'role':'Terramai 玩家','prompt_revision':LEGACY_PROMPT_REVISION if control and targeted else 'terramai-visible-hierarchy-v17-native-attack-geometry','rules':rules,'action_layout':'visible-semantic-intents-v18-targeted-navigation' if control and targeted else 'visible-semantic-intents-v15-native-attack-geometry' if control else 'directional-combos-v2','observation':observation,'navigation':facts},'questions':{'decision':{'type':'choice','instructions':instructions,'criteria':options,'option_order':list(options)}},'labels':{},'provenance':{'data_source':'Xinji-Mai/Terramai','source_id':'live','source_split':'demo'},'metadata':{'domain':'games','sub_domain':'terramai_directional','scenario':'interactive_control'}}


# Record representation only: the public physics snapshot, choices, action
# execution, uncertainty and rewards do not change. Old inputs keep v17/v18.
COMPACT_PROMPT_REVISION = PROMPT_REVISION
COMPACT_RECORD_FORMAT = 'jev.terramai.compact-public.v1'
_COMPACT_INSTRUCTIONS = ('\n\n紧凑公开表示v1：$ref是从State根开始的同值引用；'
 'known_surface_route的rows按columns解读，certainty全表共享；'
 '候选期限仍为物理帧，共同提前结束条件见shared_facts.candidate_execution。'
 '这些引用只去重已有公开事实，不表示额外信息或安全保证。')
_COMMON_END = '目标完成/未知/不可恢复受阻/死亡提前结束'
_PUBLIC_ALIASES = (
 (('control','recent_effects'),('observation','control','recent_effects')),
 (('navigation','recent_actual_effects'),('observation','last_effects')),
 (('navigation','progression'),('observation','progression')),
 (('navigation','tool_targets'),('observation','tool_targets')),
 (('navigation','objective'),('observation','objective')),
)


def _public_pointer(root, path):
 value=root
 for key in path:
  if not isinstance(value,dict) or key not in value:return None,False
  value=value[key]
 return value,True


def as_record(observation, *, format_revision=None):
 """Build current records; explicit legacy revisions remain byte-replayable."""
 record=_as_record_v18(observation)
 observed_revision=record['state']['prompt_revision']
 if format_revision is not None and format_revision not in (
    COMPACT_PROMPT_REVISION,observed_revision):
  raise ValueError('Terra record revision does not match the observed executor')
 if (format_revision in (None,COMPACT_PROMPT_REVISION)
     and (observation.get('control') or {}).get('executor_revision')=='visible-hierarchy-v18-targeted-navigation'):
  record['state']['prompt_revision']=COMPACT_PROMPT_REVISION
 return record


def compact_record(record):
 """Lossless v19 wire projection, applied after the shared control adapter.

 Only captured public fields are read. No engine, seed, future or policy lookup
 occurs here. Every altered field has an exact inverse in expand_record().
 """
 import copy,json,re
 result=copy.deepcopy(record);state=result.get('state',{})
 if state.get('prompt_revision') not in (LEGACY_PROMPT_REVISION,COMPACT_PROMPT_REVISION):return result
 if state.get('record_format')==COMPACT_RECORD_FORMAT:return result
 state['prompt_revision']=COMPACT_PROMPT_REVISION
 if 'record_format' in state or 'shared_facts' in state:
  raise ValueError('Terra compact record namespace already occupied')
 for source,target in _PUBLIC_ALIASES:
  value,exists=_public_pointer(state,source);other,found=_public_pointer(state,target)
  reference={'$ref':'/'+('/'.join(target))}
  if (exists and found and value==other
      and len(json.dumps(value,ensure_ascii=False,separators=(',',':')))
          >len(json.dumps(reference,ensure_ascii=False,separators=(',',':')))):
   state[source[0]][source[1]]=reference
 route=state.get('observation',{}).get('known_surface_route')
 if (isinstance(route,list) and route
     and all(isinstance(row,dict) and set(row)=={'cell','last_seen_frame','certainty'}
             and isinstance(row['cell'],list) and len(row['cell'])==2 for row in route)
     and all(row['certainty']==route[0]['certainty'] for row in route)):
  state['observation']['known_surface_route']={
   'columns':['x','y','last_seen_frame'],'certainty':route[0]['certainty'],
   'rows':[[*row['cell'],row['last_seen_frame']] for row in route]}
 shared={};attacks=state.get('navigation',{}).get('combat',[])
 equal={}
 for index,item in enumerate(attacks):
  attack=item.get('native_attack')
  if isinstance(attack,dict):
   text=json.dumps(attack,sort_keys=True,ensure_ascii=False,separators=(',',':'))
   equal.setdefault(text,[]).append(index)
 for indices in equal.values():
  if len(indices)<2:continue
  values=shared.setdefault('native_attacks',[]);slot=len(values)
  values.append(copy.deepcopy(attacks[indices[0]]['native_attack']))
  for index in indices:attacks[index]['native_attack']={'$ref':'/shared_facts/native_attacks/'+str(slot)}
 criteria=result['questions']['decision']['criteria'];changed=0
 for action,description in list(criteria.items()):
  match=re.search(r'；动作期限 (\d+) 帧，'+re.escape(_COMMON_END)+r'$',description)
  if match:
   criteria[action]=description[:match.start()]+'；期限'+match.group(1)+'帧';changed+=1
 if changed:shared['candidate_execution']={'end_on':['目标完成','未知','不可恢复受阻','死亡']}
 if shared:state['shared_facts']=shared
 state['record_format']=COMPACT_RECORD_FORMAT
 result['questions']['decision']['instructions']+=_COMPACT_INSTRUCTIONS
 return result


def expand_record(record):
 """Recover the exact previous public TrainingRecord, never policy inputs.

 This is for semantic checks and evaluation-isolation identity. Replay chooses
 its original revision and still compares the entire record strictly.
 """
 import copy,re
 result=copy.deepcopy(record);state=result.get('state',{})
 if state.get('record_format')!=COMPACT_RECORD_FORMAT:
  if state.get('prompt_revision')==COMPACT_PROMPT_REVISION:
   raise ValueError('Terra compact revision missing its record format')
  return result
 if state.get('prompt_revision')!=COMPACT_PROMPT_REVISION:
  raise ValueError('Terra compact format has an inconsistent prompt revision')
 shared=state.get('shared_facts',{})
 allowed={'/'+('/'.join(path)) for _,path in _PUBLIC_ALIASES}
 def resolve(value,chain=()):
  if isinstance(value,dict) and set(value)=={'$ref'}:
   pointer=value['$ref']
   if not isinstance(pointer,str) or pointer in chain:
    raise ValueError('invalid or cyclic Terra public reference')
   if pointer not in allowed and not re.fullmatch(r'/shared_facts/native_attacks/\d+',pointer):
    raise ValueError('unknown Terra public reference')
   target=state
   try:
    for part in pointer[1:].split('/'):
     target=target[int(part)] if isinstance(target,list) else target[part]
   except (KeyError,IndexError,TypeError,ValueError):
    raise ValueError('unresolved Terra public reference') from None
   return resolve(copy.deepcopy(target),chain+(pointer,))
  if isinstance(value,dict):return {key:resolve(item,chain) for key,item in value.items()}
  if isinstance(value,list):return [resolve(item,chain) for item in value]
  return value
 state=resolve(state);result['state']=state
 route=state.get('observation',{}).get('known_surface_route')
 if isinstance(route,dict):
  if set(route)!={'columns','certainty','rows'} or route['columns']!=['x','y','last_seen_frame']:
   raise ValueError('unknown Terra route table encoding')
  if not isinstance(route['rows'],list) or any(not isinstance(row,list) or len(row)!=3 for row in route['rows']):
   raise ValueError('invalid Terra route table row')
  state['observation']['known_surface_route']=[{'cell':row[:2],'last_seen_frame':row[2],
   'certainty':copy.deepcopy(route['certainty'])} for row in route['rows']]
 if 'candidate_execution' in shared:
  if shared['candidate_execution']!={'end_on':['目标完成','未知','不可恢复受阻','死亡']}:
   raise ValueError('unknown Terra candidate execution encoding')
  criteria=result['questions']['decision']['criteria']
  for action,description in list(criteria.items()):
   match=re.search(r'；期限(\d+)帧$',description)
   if match:criteria[action]=description[:match.start()]+'；动作期限 '+match.group(1)+' 帧，'+_COMMON_END
 instructions=result['questions']['decision']['instructions']
 clock_suffix=''
 if state.get('sampling_clock') is not None:
  if state['sampling_clock'].get('revision')=='simulated-wait-2-4s-v1':
   from jev_inference_clock import simulated_marker,SIMULATED_NOTICE
   expected_clock=simulated_marker();clock_suffix=SIMULATED_NOTICE
  else:
   expected_clock={'mode':'inference_paused','revision':'inference-paused-v1',
    'waiting_advances_world':False,'execution_advances_world':True}
   clock_suffix=('\n本局时钟约定：构造观察和等待模型回复期间世界暂停；动作执行期间物理正常推进。'
    '上文及候选中的推理延迟风险仅为实时模式的反事实预测，本局等待延迟取0；'
    '仍须考虑动作执行中的碰撞、重力、敌人和资源变化。')
  if state['sampling_clock']!=expected_clock or not instructions.endswith(clock_suffix):
   raise ValueError('Terra sampling clock marker or instructions mismatch')
  instructions=instructions[:-len(clock_suffix)]
 if not instructions.endswith(_COMPACT_INSTRUCTIONS):
  raise ValueError('Terra compact instructions suffix is missing or changed')
 result['questions']['decision']['instructions']=instructions[:-len(_COMPACT_INSTRUCTIONS)]+clock_suffix
 state.pop('shared_facts',None);state.pop('record_format')
 state['prompt_revision']=LEGACY_PROMPT_REVISION
 return result


def record_for_revision(observation, revision):
 """Strict input reconstruction for the version recorded at decision time."""
 from jev_gameplay_contract import adapt_record
 if revision is None:return adapt_record(_as_record_v18(observation))
 return adapt_record(as_record(observation,format_revision=revision))
