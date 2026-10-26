"""Task-space pick/place simulator, centimetres and Newtons, no hardware interface."""
import copy,math,random

ACTIONS={'open':'打开夹爪','raise':'抬升到安全高度','object':'移到物体正上方','grasp_height':'降到抓取高度',
    'gentle':'轻夹 · 5 N','firm':'稳固夹取 · 12 N','bin':'移到放置区正上方','place_height':'降到放置高度'}
RULES=('桌面机械臂简化仿真。坐标单位 cm，夹持力单位 N；工具位置用 [x,y,z]。工作空间 40×30×25。'
    '移动按直线执行，水平移动前必须先到 clearance 安全高度；否则路径可能碰撞障碍。'
    '空夹爪闭合时先打开。未持物时顺序为：升到安全高度→移到物体正上方→降到 grasp_z→夹取；'
    '已持物时顺序为：升到安全高度→移到 bin 正上方→降到 place_z→打开。'
    '已经到达目标位置或高度的步骤跳过。抓取力度必须位于物体允许的 [min_force,max_force]，'
    '只有夹爪在物体位置、grasp_z 高度且打开时才能抓取。两种力度都满足时取较小值。'
    '只在放置区和放置高度释放，其他位置释放会掉落。以不碰撞、不压坏、不滑落完成搬运为目标。')

def fresh(seed):
    rng=random.Random(seed)
    obj=[rng.randint(6,15),rng.randint(7,23)];target=[rng.randint(27,35),rng.randint(7,23)]
    boxes=[{'x1':18,'x2':22,'y1':rng.randint(2,8),'y2':rng.randint(20,28),'height':rng.randint(7,15)}]
    fragile=rng.choice([True,False])
    return {'kind':'robot_grasp','seed':seed,'steps':0,'score':0,'outcome':None,'tool':[3,3,20],
        'object':obj,'bin':target,'obstacles':boxes,'clearance':max(b['height'] for b in boxes)+4,
        'grasp_z':3,'place_z':3,'gripper_open':rng.choice([True,False]),'holding':False,
        'min_force':3 if fragile else 9,'max_force':8 if fragile else 20,'placed':False}

def close(a,b):return all(abs(x-y)<1e-6 for x,y in zip(a,b))

def choices(g):
    if g.get('outcome'):return {}
    return {k:v for k,v in ACTIONS.items() if not (
        k=='open' and g['gripper_open'] or k in ['gentle','firm'] and (not g['gripper_open'] or g['holding']) or
        k=='raise' and g['tool'][2]==g['clearance'] or k=='object' and close(g['tool'][:2],g['object']) or
        k=='bin' and close(g['tool'][:2],g['bin']) or k=='grasp_height' and g['tool'][2]==g['grasp_z'] or
        k=='place_height' and g['tool'][2]==g['place_z'])}

def best(g):
    pos=g['tool'];destination=g['bin'] if g['holding'] else g['object'];height=g['place_z'] if g['holding'] else g['grasp_z']
    if not g['holding'] and not g['gripper_open']:return 'open'
    if close(pos[:2],destination):
        if pos[2]!=height:return 'place_height' if g['holding'] else 'grasp_height'
        if g['holding']:return 'open'
        return 'gentle' if g['min_force']<=5<=g['max_force'] else 'firm'
    if pos[2]!=g['clearance']:return 'raise'
    return 'bin' if g['holding'] else 'object'

def collision(start,end,obstacles):
    # Exact segment vs expanded axis-aligned boxes (gripper/object footprint radius 1 cm).
    for b in obstacles:
        lower=[b['x1']-1,b['y1']-1,0];upper=[b['x2']+1,b['y2']+1,b['height']+1];lo,hi=0.,1.
        for i in range(3):
            delta=end[i]-start[i]
            if abs(delta)<1e-12:
                if not lower[i]<=start[i]<=upper[i]:lo,hi=1.,0.;break
            else:
                x=(lower[i]-start[i])/delta;y=(upper[i]-start[i])/delta
                lo=max(lo,min(x,y));hi=min(hi,max(x,y))
        if lo<=hi:return True
    return False

def step(g,action):
    if action not in choices(g):raise ValueError('非法动作')
    s=copy.deepcopy(g);s['steps']+=1;s['event']=''
    if action=='open':
        if s['holding']:
            if close(s['tool'][:2],s['bin']) and s['tool'][2]==s['place_z']:
                s['placed']=True;s['score']=2;s['outcome']='win';s['event']='物体已平稳放入目标区'
            else:s['outcome']='loss';s['event']='物体在目标区外或过高处掉落'
        s['holding']=False;s['gripper_open']=True
    elif action in ['gentle','firm']:
        force=5 if action=='gentle' else 12;s['gripper_open']=False
        if close(s['tool'][:2],s['object']) and s['tool'][2]==s['grasp_z']:
            if force>s['max_force']:s['outcome']='loss';s['event']='夹持力过大，物体受损'
            elif force<s['min_force']:s['outcome']='loss';s['event']='夹持力不足，物体滑落'
            else:s['holding']=True;s['score']=1;s['event']='已抓住物体'
        else:s['event']='夹爪闭合，但没有抓住物体'
    else:
        target=list(s['tool'])
        if action=='raise':target[2]=s['clearance']
        elif action=='object':target[:2]=s['object']
        elif action=='bin':target[:2]=s['bin']
        elif action=='grasp_height':target[2]=s['grasp_z']
        elif action=='place_height':target[2]=s['place_z']
        if collision(s['tool'],target,s['obstacles']):s['outcome']='loss';s['event']='移动路径碰撞障碍物'
        s['tool']=target
    if s['steps']>=20 and not s['outcome']:s['outcome']='loss';s['event']='步数用尽，尚未完成放置'
    return s
