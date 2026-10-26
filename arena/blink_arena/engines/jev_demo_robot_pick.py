"""Discrete task-space can picking demo. Synthetic, no hardware or dataset claim."""
import copy,random
from collections import deque
ACTIONS={'forward':'向前','backward':'向后','left':'向左','right':'向右','up':'抬升','down':'下降','grasp':'夹取可乐','open':'打开夹爪'}
DELTA={'forward':(0,1,0),'backward':(0,-1,0),'left':(-1,0,0),'right':(1,0,0),'up':(0,0,1),'down':(0,0,-1)}
RULES='桌面取物仿真；每格为一个移动步长。tool=[x,y,z]，x向右、y向前、z向上。水平范围0..6，高度0..3；物体抓取高度为0，障碍高度为1。目标是拿到红色可乐并抬到z>=2。夹取可乐时，夹爪必须与可乐的x、y坐标对齐且z=0；安全移动可先下降再横向移动，也可先横向移动再下降，不要求固定顺序。夹取后继续抬升到z>=2。前后左右每次移动一格；仅列出不会撞障碍和越界的动作。打开夹爪只能在未抓物时；夹取只有对齐物体时可选。不要拿水瓶。'

def fresh(seed=0):
 r=random.Random(seed);target=[r.randint(3,5),r.randint(3,5),0];obstacles=[[2,2],[3,2],[2,3]]
 return {'kind':'robot_pick_cola','seed':seed,'steps':0,'score':0,'outcome':None,'tool':[1,1,2],'target':target,'water':[5,1,0],'obstacles':obstacles,'holding':False,'gripper_open':True,'event':'请帮我拿起桌上的可乐。','trail':[[1,1,2]],'last_actions':[]}

def choices(g):
 if g.get('outcome'):return {}
 opts={}
 for k,d in DELTA.items():
  p=[a+b for a,b in zip(g['tool'],d)]
  if not(0<=p[0]<=6 and 0<=p[1]<=6 and 0<=p[2]<=3):continue
  if p[:2] in g['obstacles'] and p[2]<=1:continue
  if not g['holding'] and p[:2] in [g['target'][:2],g['water'][:2]] and p[2]<0:continue
  opts[k]=ACTIONS[k]
 if not g['holding'] and g['gripper_open'] and g['tool'] in [g['target'],g['water']]:opts['grasp']='合拢夹爪，抓住正下方物体'
 if not g['holding'] and not g['gripper_open']:opts['open']=ACTIONS['open']
 return opts

def step(g,action):
 if action not in choices(g):raise ValueError('非法动作或本局已结束')
 s=copy.deepcopy(g);s['steps']+=1;s['event']=ACTIONS[action];s['last_actions']=(s['last_actions']+[action])[-6:]
 if action in DELTA:s['tool']=[a+b for a,b in zip(s['tool'],DELTA[action])]
 elif action=='grasp':
  s['gripper_open']=False
  if s['tool']==s['water']:s['outcome']='loss';s['event']='拿到了水瓶，目标是可乐。'
  else:s['holding']=True;s['score']=1;s['event']='已夹住可乐，继续抬升。'
 elif action=='open':s['gripper_open']=True
 s['trail'].append(list(s['tool']));s['trail']=s['trail'][-45:]
 if s['holding'] and s['tool'][2]>=2:s['outcome']='win';s['score']=2;s['event']='已拿到可乐！'
 if s['steps']>=40 and not s['outcome']:s['outcome']='loss';s['event']='步数用尽，尚未完成抓取。'
 return s

def best(g):
 # Reference controller is separate from Jev inference and explicitly labeled in UI.
 if g['holding']:return 'up'
 if not g['gripper_open']:return 'open'
 if g['tool']==g['target']:return 'grasp'
 target=tuple(g['target']);start=tuple(g['tool']);queue=deque([(start,[])]);seen={start}
 for_node=lambda p:{**g,'tool':list(p)}
 while queue:
  p,path=queue.popleft()
  if p==target:return path[0]
  for k in choices(for_node(p)):
   if k not in DELTA:continue
   q=tuple(a+b for a,b in zip(p,DELTA[k]))
   if q not in seen:seen.add(q);queue.append((q,path+[k]))
 raise ValueError('No path')

def as_record(g):
 opts=choices(g)
 observation={k:copy.deepcopy(g[k]) for k in ['tool','water','obstacles','holding','gripper_open','last_actions']}
 observation['recent_tool_positions']=copy.deepcopy(g['trail'][-8:])
 # Once held, the object follows the tool; its original table position is no
 # longer a target. Expose this physical state without injecting an oracle move.
 observation.update(cola_position=list(g['tool'] if g['holding'] else g['target']),
     task_status='可乐已夹住，尚未抬到安全高度' if g['holding'] else '尚未夹住可乐',
     success_condition='夹住可乐且夹爪高度 z >= 2',
     safe_lift_height=2)
 return {'schema_version':'jev.training.v1','id':'live-robot-pick','group_id':'live-robot-pick','state':{'role':'控制桌面机械臂取物','rules':RULES,**observation},'questions':{'decision':{'type':'choice','instructions':'用户要可乐。根据当前抓取状态，为完成拿起并抬升可乐的任务，下一步应选择哪个动作？','criteria':opts,'option_order':list(opts)}},'labels':{},'provenance':{'data_source':'cues_robot_task_space_simulator_v1','source_id':'live','source_split':'demo'},'metadata':{'domain':'embodied_robotics','sub_domain':'robot_pick_cola','scenario':'pick_cola','difficulty':'L2'}}
