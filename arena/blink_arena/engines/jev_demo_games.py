"""Small deterministic rule engines for the seven games present in Jev HF data."""
import copy,re

GAMES={'tic_tac_toe':('井字棋',3),'connect_four':('四子棋',7),'othello_6x6':('黑白棋 · 6×6',6),'othello_8x8':('黑白棋 · 8×8',8),'gomoku_19x19':('五子棋 · 19×19',19),'hex_7x7':('Hex · 7×7',7),'dots_and_boxes_3x3':('点格棋 · 3×3',3)}
DIRECTIONS=[(a,b) for a in [-1,0,1] for b in [-1,0,1] if a or b]
RULES={
'tic_tac_toe':'Alternate marks on a 3×3 grid. Three in a row wins; a full board without a line is a draw. Indices are row-major 0 through 8.',
'connect_four':'Connect Four. Drop a disc into a non-full column C1 through C7. It falls to the lowest empty cell. Four in a row horizontally, vertically, or diagonally wins.',
'gomoku_19x19':'Gomoku on a 19x19 board. Five or more stones in a row wins. There are no captures, forbidden moves, swap rules, or pass moves. Coordinates are 1-based x,y.',
'hex_7x7':'Hex on a 7x7 board. X connects west to east; O connects north to south. No captures or draws. Moves use labels like d4. Hex cells in descending-number rows are progressively indented to the right.',
'dots_and_boxes_3x3':'Dots and Boxes on a 3x3 box grid. Draw one undrawn edge. Completing a box claims it and gives the same player another move. Most boxes wins. Hrow,col: horizontal edges, rows 1..4 and cols 1..3. Vrow,col: vertical edges, rows 1..3 and cols 1..4.',
}

def fresh(kind, seed=None, opening_plies=None):
    if kind not in GAMES:raise ValueError('未知游戏')
    if seed is not None:
        from jev_environment_seeds import board_opening
        return board_opening(kind, seed, opening_plies)
    if opening_plies is not None:raise ValueError('指定开局步数时必须提供种子')
    n=GAMES[kind][1];h=6 if kind=='connect_four' else n
    g={'game':kind,'n':n,'board':[['.' for _ in range(n)] for _ in range(h)],'turn':'X','winner':None,'edges':{},'boxes':{},'passes':0}
    if kind.startswith('othello'):
        a=n//2-1;b=n//2;g['board'][a][a]=g['board'][b][b]='O';g['board'][a][b]=g['board'][b][a]='X'
    return g

def key(g,r,c):
    kind=g['game'];n=g['n']
    if kind=='tic_tac_toe':return str(r*3+c)
    if kind=='connect_four':return 'C'+str(c+1)
    if kind=='gomoku_19x19':return f'{c+1},{n-r}'
    return chr(97+c)+str(n-r)

def coord(g,action):
    kind=g['game'];n=g['n']
    if kind=='tic_tac_toe':return divmod(int(action),3)
    if kind=='gomoku_19x19':x,y=map(int,action.split(','));return n-y,x-1
    if kind=='connect_four':
        c=int(action[1:])-1
        return next((r for r in range(5,-1,-1) if g['board'][r][c]=='.'),-1),c
    return n-int(action[1:]),ord(action[0])-97

def flips(g,r,c):
    b=g['board'];n=g['n'];side=g['turn'];other='O' if side=='X' else 'X';out=[]
    if b[r][c]!='.':return []
    for dr,dc in DIRECTIONS:
        rr,cc=r+dr,c+dc;run=[]
        while 0<=rr<n and 0<=cc<n and b[rr][cc]==other:run.append((rr,cc));rr+=dr;cc+=dc
        if run and 0<=rr<n and 0<=cc<n and b[rr][cc]==side:out.extend(run)
    return out

def box_edges(r,c):return [f'H{r},{c}',f'H{r+1},{c}',f'V{r},{c}',f'V{r},{c+1}']

def legal(g):
    if g.get('winner'):return []
    kind=g['game'];b=g['board'];n=g['n']
    if kind=='dots_and_boxes_3x3':return [f'{t}{r},{c}' for t,rs,cs in [('H',4,3),('V',3,4)] for r in range(1,rs+1) for c in range(1,cs+1) if f'{t}{r},{c}' not in g['edges']]
    if kind=='connect_four':return ['C'+str(c+1) for c in range(n) if b[0][c]=='.']
    out=[key(g,r,c) for r in range(n) for c in range(n) if b[r][c]=='.' and (not kind.startswith('othello') or flips(g,r,c))]
    return out or (['pass'] if kind.startswith('othello') else [])

def terminal(g):
    kind=g['game'];n=g['n'];b=g['board']
    if kind=='dots_and_boxes_3x3':
        if len(g['boxes'])<9:return None
        x=sum(v=='X' for v in g['boxes'].values());return 'X' if x>4 else 'O'
    if kind.startswith('othello'):
        if g['passes']<2 and any('.' in row for row in b):return None
        x=sum(row.count('X') for row in b);o=sum(row.count('O') for row in b);return 'X' if x>o else 'O' if o>x else 'draw'
    if kind=='hex_7x7':
        for side in ['X','O']:
            stack=[(r,c) for r in range(n) for c in range(n) if b[r][c]==side and (c==0 if side=='X' else r==0)];seen=set(stack)
            while stack:
                r,c=stack.pop()
                if (c==n-1 if side=='X' else r==n-1):return side
                for dr,dc in [(0,1),(0,-1),(1,0),(-1,0),(1,-1),(-1,1)]:
                    rr,cc=r+dr,c+dc
                    if 0<=rr<n and 0<=cc<n and (rr,cc) not in seen and b[rr][cc]==side:seen.add((rr,cc));stack.append((rr,cc))
        return None
    needed=3 if kind=='tic_tac_toe' else 4 if kind=='connect_four' else 5
    for r,row in enumerate(b):
        for c,v in enumerate(row):
            if v=='.':continue
            for dr,dc in [(0,1),(1,0),(1,1),(1,-1)]:
                if all(0<=r+dr*k<len(b) and 0<=c+dc*k<n and b[r+dr*k][c+dc*k]==v for k in range(needed)):return v
    return 'draw' if not any('.' in row for row in b) else None

def move(g,action):
    g=copy.deepcopy(g)
    if action not in legal(g):raise ValueError('非法落子或对局已结束')
    kind=g['game'];side=g['turn'];again=False
    if kind=='dots_and_boxes_3x3':
        g['edges'][action]=side
        for r in range(1,4):
            for c in range(1,4):
                k=f'{r},{c}'
                if k not in g['boxes'] and all(e in g['edges'] for e in box_edges(r,c)):g['boxes'][k]=side;again=True
    elif action=='pass':g['passes']+=1
    else:
        r,c=coord(g,action);change=flips(g,r,c) if kind.startswith('othello') else [];g['board'][r][c]=side;g['passes']=0
        for rr,cc in change:g['board'][rr][cc]=side
    if not again:g['turn']='O' if side=='X' else 'X'
    g['winner']=terminal(g)
    prev=g.get('control',{})
    effect={'action':action,'actor':side,'event':'terminal' if g['winner'] else 'move_complete',
            'changed_visible_state':action!='pass','failure_reason':None}
    g['control']={'subgoal':'扩大控制并阻止对手获胜','status':'completed',
                  'recent_effects':(prev.get('recent_effects',[])+[effect])[-6:],
                  'events':[effect['event']], 'fallback_actions':0}
    return g

def from_record(record):
    s=record['state'];g=fresh(s['game']);g['turn']=s['side_to_move'];text=s['board'];kind=g['game'];n=g['n']
    if kind=='dots_and_boxes_3x3':
        for e in re.findall(r'[HV]\d+,\d+',text):g['edges'][e]='?'
        for side in ['X','O']:
            line=next((x for x in text.splitlines() if x.startswith('Boxes owned by '+side)), '')
            for r,c in re.findall(r'(\d+),(\d+)',line):g['boxes'][r+','+c]=side
    elif kind=='gomoku_19x19':
        for side in ['X','O']:
            line=next(x for x in text.splitlines() if x.startswith('Stones '+side))
            for x,y in re.findall(r'(\d+),(\d+)',line):g['board'][n-int(y)][int(x)-1]=side
    elif kind=='tic_tac_toe':
        rows=[x.split('|') for x in text.splitlines() if '|' in x];g['board']=[[v.strip() or '.' for v in row] for row in rows]
    else:
        rows=[]
        for line in text.splitlines():
            chars=re.findall(r'(?<!\w)[.XO](?!\w)',line)
            if len(chars)==n:rows.append(chars)
        if len(rows)!=len(g['board']):raise ValueError('棋盘行数不符')
        g['board']=rows
    g['winner']=terminal(g);return g

def visible(g):
    return {**{k:v for k,v in g.items() if not k.startswith('_')},'legal':legal(g),'name':GAMES[g['game']][0]}

def as_record(g):
    kind=g['game'];n=g['n'];b=g['board'];actions=legal(g);note=''
    if kind=='gomoku_19x19':
        occupied=[(r,c) for r in range(n) for c in range(n) if b[r][c]!='.']
        if occupied:
            candidates=[a for a in actions if any(max(abs(coord(g,a)[0]-r),abs(coord(g,a)[1]-c))<=2 for r,c in occupied)]
            actions=sorted(candidates,key=lambda a:(min(max(abs(coord(g,a)[0]-r),abs(coord(g,a)[1]-c)) for r,c in occupied),a))[:255]
        else:actions=['10,10']
        note=' Candidate actions are empty cells within Chebyshev distance 2 of an occupied cell, capped at 255; this is a candidate subset, not all legal moves.'
        board='Board encoding: 1-based x,y.\n'+'\n'.join('Stones '+s+': '+(', '.join(key(g,r,c) for r in range(n) for c in range(n) if b[r][c]==s) or 'none') for s in ['X','O'])
    elif kind=='dots_and_boxes_3x3':board='\n'.join([t+' edges drawn: '+(', '.join(e for e in g['edges'] if e.startswith(prefix)) or 'none') for t,prefix in [('Horizontal','H'),('Vertical','V')]]+['Boxes owned by '+s+': '+(', '.join(k for k,v in g['boxes'].items() if v==s) or 'none') for s in ['X','O']])
    elif kind=='tic_tac_toe':board='Board state:\n'+'\n---------\n'.join(' | '.join(' ' if c=='.' else c for c in row) for row in b)
    elif kind=='connect_four':board='C1 C2 C3 C4 C5 C6 C7\n'+'\n'.join(' '.join(row) for row in b)
    else:board='  '+' '.join(chr(97+c) for c in range(n))+'\n'+'\n'.join((' '*r if kind=='hex_7x7' else '')+str(n-r)+' '+' '.join(row) for r,row in enumerate(b))
    rules=RULES.get(kind,f'Othello on a {n}x{n} board. Place a disc bracketing one or more opponent discs; bracketed discs flip. Pass only when no placement is legal. Two passes or a full board ends the game; most discs wins. Coordinates use letters and 1-based rows.')
    focus={'tic_tac_toe':'优先直接连成三子，其次阻止对方下一手成线。','connect_four':'优先直接连成四子，其次阻止对方下一手成线，留意重力落点。','gomoku_19x19':'优先直接连成五子，其次阻止对方的直接胜利；候选集只覆盖已有棋子附近。','hex_7x7':'优先形成连接两侧的连续路径，同时注意对手的切断点。','dots_and_boxes_3x3':'逐个检查候选边相邻盒子的已画边数：优先完成已有三条边的盒子，完成盒子可继续走；否则尽量选不会把一个盒子从两条边变成三条边的安全边，避免白送对手得分。若只剩送分边，选让对手最少获利的边。'}
    detail=focus.get(kind,'优先检查能否扩大己方控制或阻止对手下一步取得明显优势。')
    prompt='你执 '+g['turn']+' 方。先按 state.rules 检查局面和坐标；仅从给定合法候选中选择一项。'+detail+' 不要输出候选集合之外的动作。'
    state={'game':kind,'rules':rules+note,'side_to_move':g['turn'],'board':board}
    from jev_game_control import control_view
    state['control']=control_view({**state,'control':g.get('control',{})},kind)
    if kind=='dots_and_boxes_3x3':
        state['box_edge_counts']={f'{r},{c}':sum(edge in g['edges'] for edge in box_edges(r,c)) for r in range(1,4) for c in range(1,4)}
        state['candidate_box_effects']={action:{
            'boxes_completed':sum(action in box_edges(r,c) and state['box_edge_counts'][f'{r},{c}']==3
                                  for r in range(1,4) for c in range(1,4)),
            'three_edge_boxes_created':sum(action in box_edges(r,c) and state['box_edge_counts'][f'{r},{c}']==2
                                            for r in range(1,4) for c in range(1,4))}
            for action in actions}
        prompt='你执 '+g['turn']+' 方。目标是整局取得更多盒子；state.candidate_box_effects 只按当前公开边线计算。优先选择 boxes_completed 最多的合法边，完成盒子后还可继续行动；若没有可完成的盒子，优先 three_edge_boxes_created=0 的安全边，避免给对手立即收盒机会。若只剩危险边，考虑对手将得到的盒子数。只输出合法动作 ID。'
    record={'schema_version':'jev.training.v1','id':'demo-live','group_id':'demo-live','state':state,'questions':{'decision':{'type':'choice','instructions':prompt,'criteria':{a:a for a in actions},'option_order':actions}},'labels':{},'provenance':{'data_source':'jev.demo.live','source_id':'live','source_split':'demo'},'metadata':{'domain':'games','sub_domain':kind}}
    from jev_board_visible_facts import enrich
    return enrich(__import__(__name__),g,record,actions),actions
