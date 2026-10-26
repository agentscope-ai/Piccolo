"""Small deterministic worlds and explicitly bounded decision objectives.

All rules are original implementations. These are synthetic decision exercises,
not Terraria recordings or claims of globally optimal game play.
"""
import copy, random
from functools import lru_cache
from collections import deque
from jev_showcase_common import record
import jev_showcase_robot as robot

SHAPES = {'I':[(0,0),(1,0),(2,0),(3,0)], 'O':[(0,0),(1,0),(0,1),(1,1)],
    'T':[(0,0),(1,0),(2,0),(1,1)], 'S':[(1,0),(2,0),(0,1),(1,1)],
    'Z':[(0,0),(1,0),(1,1),(2,1)], 'J':[(0,0),(0,1),(1,1),(2,1)],
    'L':[(2,0),(0,1),(1,1),(2,1)]}
DIRS={'up':(0,-1),'right':(1,0),'down':(0,1),'left':(-1,0)}
MOVE_ORDER=('up','left','right','down')
MOVE_LABELS={'up':'↑ 上移','left':'← 左移','right':'右移 →','down':'↓ 下移'}
SOKOBAN_RULES='坐标 [x,y]，原点左上，x 向右、y 向下。# 为墙；玩家每步上下左右移动一格，可以推一只箱子一格，但不能拉，也不能同时推动两只。所有箱子到达目标格即成功；无解死局或 80 步未完成即失败。grid 的 P=玩家、+=玩家在目标上、B=箱子、G=目标、*=箱子在目标上、#=墙。先规划箱子如何被推到目标，再安排玩家站到箱子背后；推动前检查目标格和后续推动空间。只依据可见地图，不读取隐藏解答。'
SOKOBAN_MAP=(
    '########',
    '#......#',
    '#.##...#',
    '#..B.G.#',
    '#..B.#.#',
    '#..P.G.#',
    '#......#',
    '########',
)
TERRA_ACTIONS={'attack':'挥剑攻击', 'heal':'饮用治疗药水', 'wood':'采集 4 木材',
    'stone':'开采 3 石块', 'torch':'制作火把', 'shelter':'搭建庇护所', 'retreat':'暂时撤退'}
TERRA_RULES = ('这是自建的泰拉瑞亚主题简化模拟，数值以本规则为准。每步先执行动作，'
    '再由仍存活的敌人造成 damage 点伤害；有庇护所时伤害向下取半。'
    'attack 减少 enemy_hp，减少量为 attack；heal 消耗一瓶药水恢复 35 HP，上限 100；'
    'wood 增加 4 木材；stone 增加 3 石块，黑暗且无火把时额外损失 4 HP；'
    'torch 消耗 1 木材和 1 凝胶；shelter 消耗 10 木材；retreat 本步不受伤。'
    '本次决策先避免死亡，再最大化动作后效用：4*HP + 3*木材 + 2*石块 + '
    '30*是否有火把 + 100*是否有庇护所 - 2*敌人HP - 10*是否撤退。'
    '并列时按 attack,heal,wood,stone,torch,shelter,retreat 顺序。只评本步，不预测敌人刷新。')

def rotations(name):
    result=[];shape=SHAPES[name]
    for _ in range(4):
        xmin=min(x for x,y in shape);ymin=min(y for x,y in shape)
        shape=sorted((x-xmin,y-ymin) for x,y in shape)
        if shape not in result:result.append(shape)
        shape=[(-y,x) for x,y in shape]
    return result

def landing(g, action):
    rot,col=map(int,action.split(':'));shape=rotations(g['piece'])[rot];h=len(g['board']);w=len(g['board'][0])
    if not all(0<=x+col<w for x,dy in shape):raise ValueError('blocked placement')
    def fits(y):return all(dy+y<h and (dy+y<0 or not g['board'][dy+y][x+col]) for x,dy in shape)
    # Enter from above the board, rather than creating the complete bounding
    # box at row0. An overhanging piece's lower cell must not be spawned below
    # an occupied top cell and thereby appear inside an inaccessible hole.
    y=-max(dy for x,dy in shape)-1
    while fits(y+1):y+=1
    if y<0:raise ValueError('blocked entry from above the board')
    b=copy.deepcopy(g['board'])
    for x,dy in shape:b[y+dy][x+col]=1
    remaining=[row for row in b if not all(row)];cleared=h-len(remaining)
    b=[[0]*w for _ in range(cleared)]+remaining
    return b,cleared,[(col+x,y+dy) for x,dy in shape]

def metrics(board):
    heights=[];holes=0
    for x in range(len(board[0])):
        first=next((y for y,row in enumerate(board) if row[x]),len(board))
        heights.append(len(board)-first);holes+=sum(not board[y][x] for y in range(first,len(board)))
    return holes,sum(heights),sum(abs(a-b) for a,b in zip(heights,heights[1:]))

def snake_next(g,action):
    dx,dy=DIRS[action];head=[g['body'][0][0]+dx,g['body'][0][1]+dy]
    eating=head==g['food'];body=[head]+g['body'][:len(g['body']) if eating else -1]
    collision=not (0<=head[0]<g['n'] and 0<=head[1]<g['n']) or head in body[1:] or head in g['obstacles']
    return head,body,eating,collision

def snake_facts(g,action):
    head,body,eating,collision=snake_next(g,action)
    if collision:return (-1,-10000,-10000)
    blocked={tuple(p) for p in body[1:]+g['obstacles']};queue=deque([(tuple(head),0)]);visited={tuple(head)};dist=None
    while queue:
        pos,d=queue.popleft()
        if list(pos)==g['food']:dist=d
        for dx,dy in DIRS.values():
            q=(pos[0]+dx,pos[1]+dy)
            if 0<=q[0]<g['n'] and 0<=q[1]<g['n'] and q not in blocked and q not in visited:
                visited.add(q);queue.append((q,d+1))
    return (1,-(dist if dist is not None else 10000),len(visited))

def slide_2048(board,action):
    """Return the board after one slide and the points from merges, before spawning."""
    out=copy.deepcopy(board);gain=0;n=len(board)
    for fixed in range(n):
        cells=([(x,fixed) for x in range(n)] if action=='left' else
               [(x,fixed) for x in range(n-1,-1,-1)] if action=='right' else
               [(fixed,y) for y in range(n)] if action=='up' else
               [(fixed,y) for y in range(n-1,-1,-1)])
        values=[board[y][x] for x,y in cells if board[y][x]];merged=[];i=0
        while i<len(values):
            if i+1<len(values) and values[i]==values[i+1]:
                merged.append(values[i]*2);gain+=values[i]*2;i+=2
            else:merged.append(values[i]);i+=1
        for (x,y),value in zip(cells,merged+[0]*(n-len(merged))):out[y][x]=value
    return out,gain

def sokoban_move(g,action):
    dx,dy=DIRS[action];x,y=g['player'];next_cell=(x+dx,y+dy)
    walls={tuple(p) for p in g['walls']};boxes={tuple(p) for p in g['boxes']}
    if next_cell in walls or not (0<=next_cell[0]<g['width'] and 0<=next_cell[1]<g['height']):return None
    if next_cell in boxes:
        beyond=(next_cell[0]+dx,next_cell[1]+dy)
        if beyond in walls or beyond in boxes or not (0<=beyond[0]<g['width'] and 0<=beyond[1]<g['height']):return None
        boxes.remove(next_cell);boxes.add(beyond)
    return next_cell,tuple(sorted(boxes))

def sokoban_distance(g):
    """Shortest remaining player moves on the tiny visible puzzle; None means deadlock."""
    return _sokoban_distance(tuple(g['player']),tuple(sorted(map(tuple,g['boxes']))),
        tuple(sorted(map(tuple,g['walls']))),tuple(sorted(map(tuple,g['targets']))),g['width'],g['height'])

@lru_cache(maxsize=4096)
def _sokoban_distance(player,boxes,walls,goals,width,height):
    goals=set(goals);start=(player,boxes)
    walls=set(walls);queue=deque([(start,0)]);seen={start}
    while queue:
        (player,boxes),distance=queue.popleft()
        if set(boxes)==goals:return distance
        occupied=set(boxes)
        for dx,dy in DIRS.values():
            next_cell=(player[0]+dx,player[1]+dy)
            if next_cell in walls or not (0<=next_cell[0]<width and 0<=next_cell[1]<height):continue
            next_boxes=occupied
            if next_cell in occupied:
                beyond=(next_cell[0]+dx,next_cell[1]+dy)
                if beyond in walls or beyond in occupied or not (0<=beyond[0]<width and 0<=beyond[1]<height):continue
                next_boxes=(occupied-{next_cell})|{beyond}
            state=(next_cell,tuple(sorted(next_boxes)))
            if state not in seen:seen.add(state);queue.append((state,distance+1))
    return None

def terra_next(g,action):
    s=copy.deepcopy(g)
    if action=='attack':s['enemy_hp']=max(0,s['enemy_hp']-s['attack'])
    elif action=='heal':s['hp']=min(100,s['hp']+35);s['potions']-=1
    elif action=='wood':s['wood']+=4
    elif action=='stone':s['stone']+=3;s['hp']-=4 if s['dark'] and not s['torch'] else 0
    elif action=='torch':s['wood']-=1;s['gel']-=1;s['torch']=True
    elif action=='shelter':s['wood']-=10;s['shelter']=True
    if action!='retreat' and s['enemy_hp']>0:s['hp']-=s['damage']//2 if s['shelter'] else s['damage']
    s['hp']=max(0,s['hp'])
    return s

def choices(g):
    if g.get('outcome'):return {}
    kind=g['kind']
    if kind=='robot_grasp':return robot.choices(g)
    if kind=='terraria_survival':
        return {k:v for k,v in TERRA_ACTIONS.items() if not (
            k=='heal' and (not g['potions'] or g['hp']==100) or
            k=='attack' and not g['enemy_hp'] or
            k=='torch' and (g['torch'] or g['wood']<1 or g['gel']<1) or
            k=='shelter' and (g['shelter'] or g['wood']<10))}
    if kind=='jump_jump':return {str(t):f'按住 {t} 毫秒后松开' for t in g['holds']}
    if kind=='snake_navigation':
        reverse={'up':'down','down':'up','left':'right','right':'left'}[g['direction']]
        return {a:{'up':'上','right':'右','down':'下','left':'左'}[a] for a in DIRS if a!=reverse}
    if kind=='merge_2048':return {a:MOVE_LABELS[a] for a in MOVE_ORDER if slide_2048(g['board'],a)[0]!=g['board']}
    if kind=='sokoban_puzzle':
        from jev_game_control import push_intents
        return {**{a:MOVE_LABELS[a] for a in MOVE_ORDER if sokoban_move(g,a) is not None},
                **{a:f['description'] for a,f in push_intents(g).items()}}
    opts={}
    for rot,shape in enumerate(rotations(g['piece'])):
        for x in range(len(g['board'][0])-max(x for x,y in shape)):
            action=f'{rot}:{x}'
            try:landing(g,action)
            except ValueError:continue
            from jev_game_control import tetris_description
            opts[action]=tetris_description(g,action)
    return opts

def rank(g,action):
    kind=g['kind']
    if kind=='terraria_survival':
        s=terra_next(g,action);utility=4*s['hp']+3*s['wood']+2*s['stone']+30*s['torch']+100*s['shelter']-2*s['enemy_hp']-10*(action=='retreat')
        return (s['hp']>0,utility,-list(TERRA_ACTIONS).index(action))
    if kind=='jump_jump':
        distance=abs(g['position']+int(action)*g['gain']-g['target']);return (distance<=g['width']/2,-distance,-int(action))
    if kind=='snake_navigation':return (*snake_facts(g,action),-list(DIRS).index(action))
    if kind=='merge_2048':
        board,gain=slide_2048(g['board'],action)
        return (gain,sum(not v for row in board for v in row),max(map(max,board)),-MOVE_ORDER.index(action))
    if kind=='sokoban_puzzle':
        if action.startswith('push:'):
            from jev_game_control import execute_push
            after=execute_push(g,action);distance=sokoban_distance(after)
            return (distance is not None,-distance if distance is not None else -10000,0)
        player,boxes=sokoban_move(g,action);after={**g,'player':list(player),'boxes':[list(p) for p in boxes]};distance=sokoban_distance(after)
        return (distance is not None,-distance if distance is not None else -10000,-MOVE_ORDER.index(action))
    board,lines,_=landing(g,action);holes,height,bump=metrics(board);rot,col=map(int,action.split(':'))
    return (lines,-holes,-height,-bump,-rot,-col)

def best(g):return robot.best(g) if g['kind']=='robot_grasp' else max(choices(g),key=lambda a:rank(g,a))

def next_platform(g,rng):
    g['target']=round(g['position']+rng.randint(100,240),2);g['width']=rng.randint(24,60);g['gain']=rng.choice([.35,.4,.5,.6])
    ideal=round((g['target']-g['position'])/g['gain']/20)*20
    g['holds']=list(range(max(20,ideal-120),ideal+121,20))

def snake_initial_state(seed):
    """Seed all visible start conditions without executing a policy or changing rules.

    Keep the original 10x10 board, length-three snake and five obstacles. Geometry
    validation guarantees a connected map, three safe initial choices, two free
    forward cells and an apple reachable without crossing the initial body.
    """
    from jev_environment_seeds import SNAKE_REVISION, validate_seed
    validate_seed(seed)
    rng=random.Random(f'{SNAKE_REVISION}/{seed}')
    n=10;cells=[(x,y) for y in range(n) for x in range(n)]
    def reachable(start,blocked):
        distances={start:0};queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for dx,dy in DIRS.values():
                cell=x+dx,y+dy
                if 0<=cell[0]<n and 0<=cell[1]<n and cell not in blocked and cell not in distances:
                    distances[cell]=distances[(x,y)]+1;queue.append(cell)
        return distances
    direction=rng.choice(list(DIRS));dx,dy=DIRS[direction]
    starts=[(x,y) for x,y in cells if 1<=x<n-1 and 1<=y<n-1
            and 0<=x-2*dx<n and 0<=y-2*dy<n and 0<=x+2*dx<n and 0<=y+2*dy<n]
    for _ in range(128):
        x,y=rng.choice(starts);body=[(x-i*dx,y-i*dy) for i in range(3)]
        protected=set(body)|{(x+ax,y+ay) for ax,ay in DIRS.values()}|{(x+2*dx,y+2*dy)}
        obstacles=set(rng.sample([cell for cell in cells if cell not in protected],5))
        if len(reachable((x,y),obstacles)) != n*n-len(obstacles):continue
        distances=reachable((x,y),obstacles|set(body[1:]))
        food_cells=[cell for cell in cells if cell in distances and distances[cell]>=3]
        if not food_cells:continue
        return {'n':n,'body':[list(p) for p in body],'direction':direction,
                'food':list(rng.choice(food_cells)),'obstacles':[list(p) for p in sorted(obstacles)]}
    raise ValueError('无法生成安全且食物可达的贪吃蛇初始条件')

def fresh(kind,seed=0):
    if kind=='robot_grasp':return robot.fresh(seed)
    rng=random.Random(seed);g={'kind':kind,'seed':seed,'steps':0,'score':0,'outcome':None}
    if kind=='terraria_survival':g.update(hp=rng.randint(55,90),wood=rng.randint(1,9),stone=0,gel=2,potions=2,torch=False,shelter=False,enemy_hp=rng.choice([0,15,25]),attack=18,damage=7,dark=True)
    elif kind=='jump_jump':g['position']=0;next_platform(g,rng)
    elif kind=='snake_navigation':
        g.update(snake_initial_state(seed))
    elif kind=='merge_2048':
        g['board']=[[0]*4 for _ in range(4)]
        for _ in range(2):
            x,y=rng.choice([(x,y) for y in range(4) for x in range(4) if not g['board'][y][x]])
            g['board'][y][x]=2
    elif kind=='sokoban_puzzle':
        from jev_game_control import sokoban_condition
        g.update(sokoban_condition(seed))
        g['box_ids']={f'{p[0]},{p[1]}':f'box-{i}' for i,p in enumerate(sorted(g['boxes']))}
    elif kind=='tetris_placement':g.update(board=[[0]*10 for _ in range(12)],piece=rng.choice(list(SHAPES)),lines=0)
    else:raise ValueError('unknown game')
    return g

def step(g,action):
    if g['kind']=='robot_grasp':return robot.step(g,action)
    if action not in choices(g):raise ValueError('非法动作或本局已结束')
    s=copy.deepcopy(g);s['steps']+=1;rng=random.Random(g['seed']*1009+s['steps']);kind=s['kind']
    if kind=='jump_jump':
        x=round(g['position']+int(action)*g['gain'],2);s['last_landing']=x
        if abs(x-g['target'])>g['width']/2:s['outcome']='loss'
        else:
            s['position']=x;s['score']+=1
            if s['score']>=8:s['outcome']='win'
            else:next_platform(s,rng)
    elif kind=='terraria_survival':
        s.update(terra_next(g,action));s['steps']=g['steps']+1;s['score']=int(s['torch'])+int(s['shelter'])
        if s['hp']<=0:s['outcome']='loss'
        elif s['torch'] and s['shelter']:s['outcome']='win'
        elif s['steps']>=20:s['outcome']='loss'
        elif s['steps']%4==0 and not s['enemy_hp']:s['enemy_hp']=rng.choice([12,18,24])
    elif kind=='snake_navigation':
        head,body,eating,collision=snake_next(g,action);s['body']=body;s['direction']=action
        if collision:s['outcome']='loss'
        elif eating:
            s['score']+=1;free=[[x,y] for x in range(s['n']) for y in range(s['n']) if [x,y] not in body+s['obstacles']]
            if not free or s['score']>=3:s['outcome']='win'
            else:s['food']=rng.choice(free)
        if s['steps']>=80 and not s['outcome']:s['outcome']='loss'
    elif kind=='merge_2048':
        board,gain=slide_2048(g['board'],action);s['board']=board;s['score']+=gain
        if max(map(max,board))>=128:s['outcome']='win'
        else:
            x,y=rng.choice([(x,y) for y in range(4) for x in range(4) if not board[y][x]])
            board[y][x]=4 if rng.random()<.1 else 2
            if s['steps']>=120 or not choices(s):s['outcome']='loss'
    elif kind=='sokoban_puzzle':
        if action.startswith('push:'):
            from jev_game_control import execute_push
            s=execute_push(g,action)
        else:
            player,boxes=sokoban_move(g,action);s['player']=list(player);s['boxes']=[list(p) for p in boxes]
            removed=set(map(tuple,g['boxes']))-set(boxes);added=set(boxes)-set(map(tuple,g['boxes']))
            if removed and added:
                source=next(iter(removed));dest=next(iter(added));mapping=s.setdefault('box_ids',{})
                mapping[f'{dest[0]},{dest[1]}']=mapping.pop(f'{source[0]},{source[1]}',f'box@{source[0]},{source[1]}')
            from jev_game_control import sokoban_motion_frame
            s['execution_trace']={'version':1,'frames':[sokoban_motion_frame(g),
                {**sokoban_motion_frame(s),'action':action}]}
            s['execution']={'origin':'B','strategy_origin':'A','intent':action,
                'mechanical_moves':1,'deadline_moves':1,'status':'completed',
                'event':'push_complete' if removed else 'move_complete','fallback_actions':0}
        s['recent_positions']=(g.get('recent_positions', [g['player']])+
            [frame['player'] for frame in s['execution_trace']['frames'][1:]])[-8:]
        s['score']=len({tuple(p) for p in s['boxes']} & {tuple(p) for p in s['targets']})
        if s['score']==len(s['targets']):s['outcome']='win'
        elif s['steps']>=80 or sokoban_distance(s) is None:s['outcome']='loss'
    else:
        board,lines,cells=landing(g,action);s.update(board=board,lines=g['lines']+lines,score=g['score']+lines,piece=rng.choice(list(SHAPES)))
        if s['lines']>=4:s['outcome']='win'
        elif not choices(s) or s['steps']>=40:s['outcome']='loss'
    return s

def as_record(g,index=0,include_reference=True):
    state={k:copy.deepcopy(v) for k,v in g.items() if k not in ['seed','outcome','score','last_landing','execution_trace']}
    kind=g['kind']
    if kind=='robot_grasp':state['rules']=robot.RULES;prompt='为安全抓取并放置物体，机械臂下一步应执行哪个动作？'
    elif kind=='terraria_survival':state['rules']=TERRA_RULES;prompt='在本步生存与效用规则下，选择哪个动作？'
    elif kind=='jump_jump':
        state['candidate_landings']={hold:{'landing_x':round(g['position']+int(hold)*g['gain'],2),
            'inside_platform':abs(g['position']+int(hold)*g['gain']-g['target'])<=g['width']/2,
            'distance_to_center':round(abs(g['position']+int(hold)*g['gain']-g['target']),2)}
            for hold in choices(g)}
        state['rules']='落点 = position + 按住毫秒数 * gain。目标平台闭区间为 [target-width/2,target+width/2]。优先落在平台，再离中心最近；相同距离选按住时间更短者。'
        prompt='目标是连续安全落到 8 个平台。candidate_landings 是用当前公开位置、速度系数和按压时长计算的每个候选落点；只能选 inside_platform=true 的动作，优先 distance_to_center 最小者。不要靠猜按压时长。只输出对应的动作 ID。'
    elif kind=='snake_navigation':
        # Progress is public engine state. Body length is not a safe substitute
        # for score in custom fixtures or reconstructed training positions.
        state.update(foods_eaten=int(g['score']),food_target=3,max_steps=80)
        grid=[['.']*g['n'] for _ in range(g['n'])]
        for x,y in g['obstacles']:grid[y][x]='#'
        for x,y in g['body'][1:]:grid[y][x]='S'
        fx,fy=g['food'];grid[fy][fx]='F'
        hx,hy=g['body'][0];grid[hy][hx]='H'
        state['grid']=[''.join(row) for row in grid]
        state['candidate_next_cells']={action:{'head':head,'collision':collision,'eats_food':eating}
            for action in choices(g)
            for head,body,eating,collision in [snake_next(g,action)]}
        state['rules']='坐标 [x,y]，原点左上，x 向右、y 向下；grid 的 H=蛇头、S=身体、F=食物、#=障碍、.=空格。不能直接反向；头每步移动一格，撞边界、障碍或身体立即失败。没有吃到食物时尾巴同一步前移，因此可以进入旧尾格；吃到食物时尾巴不动，身体增长。80 步内吃到 3 个食物才算成功。食物吃掉后在空格随机出现；不要假设未来位置。存活优先，同时避免钻进没有退路的狭窄区域。'
        prompt='目标是在 80 步内安全吃到 3 个食物。先对每个候选方向算下一格头坐标，排除越界、障碍和自身碰撞；即使食物在同一方向也不能撞墙。再从安全动作中选通往食物的可达短路，并保留足够空间给不断变长的蛇。不要重复走向已知死路。只输出动作 ID。'
    elif kind=='merge_2048':
        state['rules']='4×4 棋盘，0 是空格。滑动时所有方块向选定方向压紧，相同相邻数值每次移动最多合并一次；只有棋盘变化的方向可选。动作后随机生成一个 2 或 4，本题只比较生成前的局面。先最大化本步合并所得分数，再最大化空格数，再最大化当前最大方块；仍并列时按 up,left,right,down 顺序。短局在合成 128 时成功，120 步或无合法移动时结束。'
        prompt='只根据当前棋盘，按本步合并收益、空位数和并列顺序选择滑动方向。不要预测随机新方块。'
    elif kind=='sokoban_puzzle':
        state.setdefault('recent_positions', [copy.deepcopy(g['player'])])
        grid=[['.']*g['width'] for _ in range(g['height'])]
        for x,y in g['walls']:grid[y][x]='#'
        for x,y in g['targets']:grid[y][x]='G'
        for x,y in g['boxes']:grid[y][x]='*' if grid[y][x]=='G' else 'B'
        px,py=g['player'];grid[py][px]='+' if grid[py][px]=='G' else 'P'
        state['grid']=[''.join(row) for row in grid]
        state['candidate_effects']={action:{'player':list(player),'boxes':[list(p) for p in boxes],
            'pushes_box':boxes!=tuple(sorted(map(tuple,g['boxes']))),
            'returns_to_recent_position':list(player) in g.get('recent_positions',[]),
            'deadlock':any(tuple(p) not in set(map(tuple,g['targets'])) and
                any((p[0]+dx,p[1]) in set(map(tuple,g['walls'])) and (p[0],p[1]+dy) in set(map(tuple,g['walls']))
                    for dx in (-1,1) for dy in (-1,1)) for p in boxes),
            'deadlock_check':'static_corner_only; other configurations may still be unsolvable'}
            for action in choices(g) if action in DIRS
            for player,boxes in [sokoban_move(g,action)]}
        state['rules']=SOKOBAN_RULES
        from jev_game_control import push_intents
        state['push_intents']={a:{k:v for k,v in f.items() if k!='description'} for a,f in push_intents(g).items()}
        state['rules']+=' push:x:y:direction:goal_x:goal_y 由你联合选择箱子、最终目标格和本次推动方向；引擎只走到站位再推一格，不规划后续箱子路线。箱子ID与目标子计划持续记录；全部移动计入80步预算。'
        prompt='目标是两只箱子都到达目标格，而不是玩家走到目标。先找箱子要走的推动路线及玩家必须站到的箱子后方格；candidate_effects 给出每个合法动作后的玩家和箱子位置，可直接核对。排除 deadlock=true 的推法；若箱子不动，优先走向推动所需的站位，避免 returns_to_recent_position=true 的无进展往返。确需绕行站位时允许回头。只输出动作 ID。'
    else:
        state['rotations']={str(i):[list(point) for point in shape] for i,shape in enumerate(rotations(g['piece']))}
        from jev_game_control import tetris_facts
        state['candidate_landings']={action:tetris_facts(g,action) for action in choices(g)}
        state['rules']='棋盘 0 为空、1 为占用，行从上到下，列从左到右。形状坐标 [x,y] 从左上开始；仅允许从顶部垂直直落，无横移钻洞。填满的行立刻消除，累计消除 4 行即胜，40 块内未完成或顶部无法落块即败。空洞指本列最上方占用格下的空格；空洞会让未来消行更难。落块后会随机给出下一形状，不能预知。优先留平坦且可用的顶部空间，避免制造深井和被盖住的空洞，在安全时制造并完成整行。'
        prompt='目标是在 40 块内累计消除 4 行。candidate_landings 是按当前公开棋盘算出的每个合法落点结果，尚未生成下一块；优先消行，并在相近选择中减少空洞、控制最高列，保留可用顶部空间。不要惯性地反复堆同一列。只输出 option 中的旋转:列动作 ID。'
    options=choices(g)
    if kind=='sokoban_puzzle' and not include_reference:
        from jev_game_control import push_intents
        pushes=push_intents(g)
        if pushes:options={a:f['description'] for a,f in pushes.items()}
    r=record(kind,state,prompt,options,best(g) if include_reference else next(iter(options),''),index)
    if not include_reference:r['labels']={}
    return r
