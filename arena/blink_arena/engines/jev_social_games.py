"""Local-rule card/property games, with explicit bounded training objectives."""
import copy,itertools,random,collections,functools,math,json
SCENES={
 'doudizhu':{'name':'斗地主','mode':'game','note':'你是地主；三人出牌、跟牌与过牌。','source_label':'合成数据 · CuES 斗地主规则引擎'},
 'texas_holdem':{'name':'德州扑克','mode':'game','note':'双人虚拟筹码；下注、公共牌与摊牌。','source_label':'合成数据 · CuES 德扑规则引擎'},
 'property_tycoon':{'name':'大富翁','mode':'game','note':'掷骰、买地、收租与资产经营。','source_label':'合成数据 · CuES 地产棋盘规则引擎'}}
RANK={**{i:str(i) for i in range(3,11)},11:'J',12:'Q',13:'K',14:'A',15:'2',16:'小王',17:'大王'}
_DZ_CARD_FIELDS=('_hand_card_ids','_history_card_ids','_last_card_ids')
def dzcardrank(card_id):
 # Rank-major physical identities; each ordinary rank has spade/heart/club/diamond.
 return card_id//4+3 if card_id<52 else card_id-36
def dzname(cards):return ' '.join(RANK[c] for c in cards)
def dzpatterns(hand):
 c=collections.Counter(hand);out={}
 def put(a,t,v):
  a=tuple(sorted(a))
  if all(collections.Counter(a)[k]<=c[k] for k in set(a)):out[','.join(map(str,a))]=(t,v,len(a),a)
 for k,n in c.items():
  for count,t in [(1,'single'),(2,'pair'),(3,'triple'),(4,'bomb')]:
   if n>=count:put([k]*count,t,k)
  if n>=3:
   for s,ns in c.items():
    if s!=k:
     put([k]*3+[s],'triple_single',k)
     if ns>=2:put([k]*3+[s]*2,'triple_pair',k)
  if n>=4:
   rest=[s for s in hand if s!=k]
   for pair in set(itertools.combinations(rest,2)):put([k]*4+list(pair),'four_two',k)
   for pair in itertools.combinations([s for s in c if s!=k and c[s]>=2],2):put([k]*4+[v for v in pair for _ in range(2)],'four_pairs',k)
 for mult,minimum,t in [(1,5,'straight'),(2,3,'pair_run'),(3,2,'plane')]:
  for low in range(3,15):
   for n in range(minimum,(14-low)+2):
    core=[k for k in range(low,low+n) for _ in range(mult)]
    if any(c[k]<mult for k in range(low,low+n)):break
    put(core,t,low+n-1)
    if mult==3:
     rest=[k for k in hand if k not in range(low,low+n)]
     for wings in set(itertools.combinations(rest,n)):put(core+list(wings),'plane_single',low+n-1)
     for wings in itertools.combinations([k for k in c if k not in range(low,low+n) and c[k]>=2],n):put(core+[k for k in wings for _ in range(2)],'plane_pair',low+n-1)
 if c[16] and c[17]:put([16,17],'rocket',17)
 return out

def dzbeats(p,last):
 if not last:return True
 if p[0]=='rocket':return last[0]!='rocket'
 if last[0]=='rocket':return False
 if p[0]=='bomb' and last[0]!='bomb':return True
 return p[0]==last[0] and p[2]==last[2] and p[1]>last[1]
def dzoptions(g,side):
 patterns=dzpatterns(g['hands'][side]);lead=g['leader']==side or not g['last'];legal={k:p for k,p in patterns.items() if lead or dzbeats(p,g['last'])}
 # The model contract can express at most 255 candidates. Preserve a stable,
 # size-diverse subset; all retained moves remain legal.
 legal=dict(sorted(legal.items(),key=lambda kv:(-kv[1][2],kv[1][1],kv[0]))[:254])
 if not lead:legal['pass']=None
 return legal

def fresh(kind,seed=0):
 rng=random.Random(seed);base={'kind':kind,'seed':seed,'steps':0,'score':0,'outcome':None,'event':'新一局','history':[]}
 if kind=='doudizhu':
  # Shuffle the same 54 positions once: the existing seeded rank deal is unchanged.
  card_deck=list(range(54));rng.shuffle(card_deck);deck=list(map(dzcardrank,card_deck))
  card_hands=[sorted(hand,key=dzcardrank) for hand in (card_deck[:20],card_deck[20:37],card_deck[37:])]
  return {**base,'hands':[list(map(dzcardrank,hand)) for hand in card_hands],'_hand_card_ids':card_hands,'_history_card_ids':[],'_last_card_ids':None,'leader':0,'last':None,'passes':0,'turn':0,'landlord':0,'bottom':deck[17:20]}
 if kind=='texas_holdem':
  deck=list(range(52));rng.shuffle(deck)
  return {**base,'hands':[deck[:2],deck[2:4]],'deck':deck[4:],'board':[],'street':0,'stacks':[980,970],'pot':50,'to_call':10,'event':'盲注已投入，轮到你行动','opponent_last':'下注 10'}
 names=['起点','梧桐街','机会','银杏街','税务','枫林路','地铁站','柳荫路','休息','桃源里','机会','竹影巷','税务','松涛路','车站','海棠街']
 prices={i:80+20*(i//2) for i in [1,3,5,7,9,11,13,15]}
 return {**base,'names':names,'prices':prices,'owners':{},'levels':{},'cash':[1200,1200],'positions':[0,0],'phase':'roll','round':0,'dice':None}

def choices(g):
 if g.get('outcome'):return {}
 if g['kind']=='doudizhu':return {k:'不出／过牌' if p is None else dzname(p[3]) for k,p in dzoptions(g,0).items()}
 if g['kind']=='texas_holdem':
  o={'fold':'弃牌'} if g['to_call'] else {}
  o['call' if g['to_call'] else 'check']='跟注 '+str(min(g['to_call'],g['stacks'][0])) if g['to_call'] else '过牌'
  if min(g['stacks'])>g['to_call']+20:o['raise']='加注 '+str(g['to_call']+40)
  return o
 if g['phase']=='roll':return {'roll':'掷骰前进'}
 if g['phase']=='buy':return ({'buy':'购买地块'} if g['cash'][0]>=g['prices'].get(g['positions'][0],0) else {})|{'skip':'暂不购买'}
 if g['phase']=='build':return ({'build':'升级地块'} if g['cash'][0]>=g['prices'].get(g['positions'][0],0)/2 else {})|{'skip':'暂不升级'}
 return {'next':'结束回合'}

def dzplay(g,side,action,card_ids=None):
 p=dzoptions(g,side)[action]
 identities=g.get('_hand_card_ids')
 if identities is not None and [list(map(dzcardrank,h)) for h in identities]!=g['hands']:
  # Rank-only counterfactual rollouts may replace hidden hands. Their old physical
  # identities are no longer evidence; keep those rollouts rank-only.
  if card_ids is not None:raise ValueError('牌面与手牌不一致')
  identities=None
 ranks=list(p[3]) if p else []
 if card_ids is not None:
  if (not isinstance(card_ids,list) or any(type(c) is not int or not 0<=c<54 for c in card_ids)
      or len(set(card_ids))!=len(card_ids) or sorted(map(dzcardrank,card_ids))!=ranks
      or (card_ids and (identities is None or any(c not in identities[side] for c in card_ids)))):
   raise ValueError('所选牌与合法动作不一致')
  selected=sorted(card_ids,key=dzcardrank)
 elif identities is not None:
  available=list(identities[side]);selected=[]
  for rank in ranks:
   chosen=next(c for c in available if dzcardrank(c)==rank);available.remove(chosen);selected.append(chosen)
 else:selected=None
 # Validate before changing either the rank state or its optional rendering data.
 if identities is None:
  for key in _DZ_CARD_FIELDS:g.pop(key,None)
 else:
  history=g.get('_history_card_ids',[])
  g['_history_card_ids']=(history[-len(g['history']):] if g['history'] else [])+[selected]
  for card_id in selected:identities[side].remove(card_id)
 if p is None:
  g['passes']+=1;g['history'].append({'player':side,'move':'过'})
  if g['passes']==2:
   g['last']=None;g['passes']=0
   if identities is not None:g['_last_card_ids']=None
 else:
  for c in p[3]:g['hands'][side].remove(c)
  if identities is not None:g['_last_card_ids']=selected
  g['last']=p;g['leader']=side;g['passes']=0;g['history'].append({'player':side,'move':dzname(p[3])})
  if not g['hands'][side]:g['outcome']='win' if side==0 else 'loss';g['event']='地主获胜！' if side==0 else '农民获胜。';g['score']=1 if side==0 else 0
 g['turn']=(side+1)%3

def dzbest(g,side=0):
 options=dzoptions(g,side)
 if 'pass' in options and side!=0 and g['leader'] not in [0,side]:return 'pass'
 moves=[(k,p) for k,p in options.items() if p]
 if not moves:return 'pass'
 return min(moves,key=lambda kv:(-kv[1][2],kv[1][0] in ['bomb','rocket'],kv[1][1],kv[0]))[0]

@functools.lru_cache(maxsize=100000)
def rank5(cards):
 ranks=sorted((c%13+2 for c in cards),reverse=True);c=collections.Counter(ranks);groups=sorted(((n,k) for k,n in c.items()),reverse=True);flush=len({v//13 for v in cards})==1;u=sorted(set(ranks));straight=(5 if u==[2,3,4,5,14] else u[-1] if len(u)==5 and u[-1]-u[0]==4 else 0)
 if flush and straight:return (8,straight)
 if groups[0][0]==4:return (7,groups[0][1],groups[1][1])
 if [x[0] for x in groups]==[3,2]:return (6,groups[0][1],groups[1][1])
 if flush:return (5,*ranks)
 if straight:return (4,straight)
 if groups[0][0]==3:return (3,groups[0][1],*sorted((k for k in c if c[k]==1),reverse=True))
 pairs=sorted((k for k in c if c[k]==2),reverse=True)
 if len(pairs)==2:return (2,*pairs,next(k for k in c if c[k]==1))
 if pairs:return (1,*pairs,*sorted((k for k in c if c[k]==1),reverse=True))
 return (0,*ranks)
def rank(cards):return max(rank5(tuple(sorted(a))) for a in itertools.combinations(cards,5))
def equity(g,draws=128):
 # Only public information and one's own cards enter the simulation.
 known=g['hands'][0]+g['board'];deck=[i for i in range(52) if i not in known];rng=random.Random(str(sorted(known)));total=0.
 for _ in range(draws):
  rest=rng.sample(deck,2+5-len(g['board']));board=g['board']+rest[2:];a=rank(g['hands'][0]+board);b=rank(rest[:2]+board);total+=1 if a>b else .5 if a==b else 0
 return total/draws

def pokerbest(g):
 eq=equity(g);cost=min(g['to_call'],g['stacks'][0]);o=choices(g)
 # Explicit bounded policy, not a claim of game-theoretic optimal betting.
 if 'raise' in o and eq>=.70 and g['stacks'][0]>=4*(cost+40):return 'raise'
 if 'check' in o:return 'check'
 return 'call' if eq*(g['pot']+cost)-cost>=0 else 'fold'

def settle(g):
 a=rank(g['hands'][0]+g['board']);b=rank(g['hands'][1]+g['board']);g['outcome']='win' if a>b else 'loss' if a<b else 'draw';g['event']='你赢下底池！' if a>b else '对手赢下底池。' if a<b else '平局，平分底池。';g['stacks'][0]+=g['pot'] if a>b else g['pot']/2 if a==b else 0;g['stacks'][1]+=g['pot'] if a<b else g['pot']/2 if a==b else 0;g['score']=g['stacks'][0]-1000;g['showdown']=True

def rent(g,i):return 15+int(g['prices'].get(i,g['prices'].get(str(i),80)))*.15+25*g['levels'].get(str(i),0)
def propertybest(g):
 o=choices(g);i=g['positions'][0];price=g['prices'].get(i,g['prices'].get(str(i),0));reserve=200+max([rent(g,int(k)) for k,v in g['owners'].items() if v==1] or [0])
 if 'buy' in o:return 'buy' if g['cash'][0]-price>=reserve else 'skip'
 if 'build' in o:return 'build' if g['cash'][0]-price/2>=reserve else 'skip'
 return next(iter(o))

def property_move(g,side,rng):
 dice=rng.randint(1,6)+rng.randint(1,6);old=g['positions'][side];pos=(old+dice)%16;g['positions'][side]=pos;g['dice']=dice
 if old+dice>=16:g['cash'][side]+=200
 g['event']=('你' if side==0 else '对手')+'掷出 '+str(dice)+'，到达'+g['names'][pos]
 if pos in [4,12]:g['cash'][side]-=100
 elif pos in [2,10]:g['cash'][side]+=rng.choice([-80,40,80,120])
 elif str(pos) in g['owners'] and g['owners'][str(pos)]!=side:
  amount=rent(g,pos);g['cash'][side]-=amount;g['cash'][1-side]+=amount
 elif pos in g['prices']:
  if side==0:g['phase']='build' if g['owners'].get(str(pos))==0 and g['levels'].get(str(pos),0)<3 else 'buy' if str(pos) not in g['owners'] else 'end'
  elif str(pos) not in g['owners'] and g['cash'][side]-g['prices'][pos]>=250:g['owners'][str(pos)]=side;g['cash'][side]-=g['prices'][pos]
 if min(g['cash'])<0:g['outcome']='loss' if g['cash'][0]<0 else 'win';g['event']='你破产了。' if g['cash'][0]<0 else '对手破产，你赢了！'

def step(g,action,*,card_ids=None):
 if action not in choices(g):raise ValueError('非法动作')
 if card_ids is not None and g['kind']!='doudizhu':raise ValueError('仅斗地主支持具体牌选择')
 g=copy.deepcopy(g);g['steps']+=1;rng=random.Random(f"{g['seed']}/{g['steps']}");g['event']=choices(g)[action]
 if g['kind']=='doudizhu':
  dzplay(g,0,action,card_ids=card_ids)
  while not g['outcome'] and g['turn']!=0:dzplay(g,g['turn'],dzbest(g,g['turn']))
  if not g['outcome']:g['event']='轮到你出牌';g['score']=20-len(g['hands'][0])
 elif g['kind']=='texas_holdem':
  if action=='fold':g['outcome']='loss';g['stacks'][1]+=g['pot'];g['event']='你弃牌，对手赢下底池。'
  else:
   amount=min(g['to_call']+(40 if action=='raise' else 0),g['stacks'][0],g['stacks'][1]+g['to_call']);g['stacks'][0]-=amount;g['pot']+=amount
   if action=='raise':pay=min(40,g['stacks'][1]);g['stacks'][1]-=pay;g['pot']+=pay
   n=3 if not g['board'] else 1 if len(g['board'])<5 else 0;g['board']+=g['deck'][:n];g['deck']=g['deck'][n:];g['street']+=1
   if len(g['board'])>=5 and g['street']>=4:settle(g)
   else:
    if len(g['board'])>5:g['board']=g['board'][:5]
    wager=min(rng.choice([0,10,20,40]),*g['stacks']);g['stacks'][1]-=wager;g['pot']+=wager;g['to_call']=wager;g['opponent_last']='过牌' if wager==0 else '下注 '+str(wager);g['event']=g['opponent_last']+'，轮到你'
   if not g['outcome'] and min(g['stacks'])<=0:
    missing=5-len(g['board']);g['board']+=g['deck'][:missing];settle(g)
 else:
  if action=='roll':g['phase']='end';property_move(g,0,rng)
  else:
   i=g['positions'][0];price=g['prices'].get(i,0)
   if action=='buy':g['owners'][str(i)]=0;g['cash'][0]-=price
   if action=='build':g['levels'][str(i)]=g['levels'].get(str(i),0)+1;g['cash'][0]-=price/2
   property_move(g,1,rng);g['phase']='roll';g['round']+=1
   if not g['outcome'] and g['round']>=20:
    totals=[g['cash'][p]+sum(g['prices'][int(i)]*(1+.5*g['levels'].get(i,0)) for i,v in g['owners'].items() if v==p) for p in [0,1]];g['outcome']='win' if totals[0]>totals[1] else 'loss' if totals[0]<totals[1] else 'draw';g['event']='20 回合结束，按现金与地产价值结算：'+str(totals);g['score']=totals[0]
 g['history']=g['history'][-12:]
 if '_history_card_ids' in g:g['_history_card_ids']=g['_history_card_ids'][-12:]
 return g

def best(g):return dzbest(g) if g['kind']=='doudizhu' else pokerbest(g) if g['kind']=='texas_holdem' else propertybest(g)
def public(g):
 z={k:copy.deepcopy(v) for k,v in g.items() if k not in ('hands','deck','seed',*_DZ_CARD_FIELDS)}
 if 'hands' in g:z['hand']=list(g['hands'][0]);z['opponent_counts']=[len(h) for h in g['hands'][1:]]
 if g['kind']=='doudizhu' and '_hand_card_ids' in g:
  z['hand_card_ids']=list(g['_hand_card_ids'][0]);z['last_card_ids']=copy.deepcopy(g.get('_last_card_ids'))
  history=g.get('_history_card_ids',[])
  if len(history)>=len(z['history']):
   for event,ids in zip(z['history'],history[-len(z['history']):] if z['history'] else []):event['card_ids']=list(ids)
 if g.get('showdown'):z['opponent_hand']=g['hands'][1]
 return json.loads(json.dumps(z))

def as_record(g):
 obs=public(g);kind=g['kind']
 if kind=='doudizhu':
  # Physical suits only render cards. Choice remains rank-based, including the
  # exact previous observation and the opponent policy's unchanged rank history.
  obs.pop('hand_card_ids',None);obs.pop('last_card_ids',None)
  obs['history']=copy.deepcopy(g['history'])
  # A record crosses the frontend JSON boundary. Native play patterns use
  # tuples, which are not JsonValue objects accepted by TrainingRecord.
  obs=json.loads(json.dumps(obs,ensure_ascii=False,allow_nan=False))
 if kind=='texas_holdem':obs['equity_estimate']=round(equity(g),6);obs['card_encoding']='0..12=♠2..A,13..25=♥2..A,26..38=♣2..A,39..51=♦2..A';obs['equity_source']='仅可见牌的 Monte Carlo 估计，未使用对手底牌'
 if kind=='property_tycoon':
  obs['opponent_max_rent']=max([rent(g,int(i)) for i,owner in g['owners'].items() if owner==1] or [0])
  obs['cash_reserve']=200+obs['opponent_max_rent']
 if kind=='doudizhu':
  rules='标准三人斗地主，玩家0为地主，先出完手牌的一方获胜。支持单张、对子、三张及带牌、顺子、连对、飞机带翅膀、四带二、炸弹和火箭；2与王不能进顺子。跟牌须同型同张数且主点数更大，炸弹压普通牌、火箭最大。连续两家过牌后重新领出。部分手牌组合很多时只列最多254种合法出法，另加过牌。手牌和历史记录属于公开给你的信息；两名农民的底牌不可见。'
  prompt='你是地主，目标是比两名农民先出完手牌。先检查能否直接走完，再估计剩余牌能否组成顺子、连对等大组合；对手剩牌少时争夺出牌权，避免无意义过牌。炸弹和火箭可用于关键夺权，不必机械保留；不要假设农民的隐藏手牌。只输出合法动作 ID。'
 elif kind=='texas_holdem':
  rules='双人固定下注档位德扑仿真，只使用虚拟筹码；2张手牌、最多5张公共牌，最佳5张比大小，A2345为最小顺子。候选为弃牌、过牌/跟注、固定加注40。observation.equity_estimate 是仅据可见牌作 128 次蒙特卡洛抽样的摊牌权益估计，有抽样误差；它没有读取对手底牌。弃牌会立即判负；跟注或过牌可继续到后续公共牌与摊牌。'
  prompt='目标是赢得本局底池。结合可见手牌、公共牌、底池、跟注额和权益估计决策。可免费过牌时不要弃牌；面对小额跟注，考虑继续看牌的权益与底池赔率；强牌或高权益再考虑加注。弃牌会立即结束本局，只有胜率与跟注成本明显不合算时才考虑。不得推断对手隐藏手牌。只输出合法动作 ID。'
 else:
  rules='16格地产棋盘，双方起始1200现金，经过起点+200，税务-100，机会为固定分布事件。未拥有地产可买，自有地产最多升3级，踩对手地产交租。升级费用是当前地块价格的一半。20回合按现金+地产价值结算，负现金破产。observation.cash_reserve 是公开局面下的保守现金参考值，不是硬约束；购地可增加终局资产，升级可增加租金，但过低现金有破产风险。'
  prompt='目标是在第 20 回合拥有比对手更高的现金加地产价值，并避免破产。看清当前阶段：掷骰/结束阶段执行唯一合法动作；买地或升级阶段权衡购置后的现金余量、可能交租和终局资产，不要因保守参考值机械放弃全部投资。只输出合法动作 ID。'
 return {'schema_version':'jev.training.v1','id':'live-'+kind,'group_id':'live-'+kind,'state':{'role':'玩家0','rules':rules,'observation':obs},'questions':{'decision':{'type':'choice','instructions':prompt,'criteria':choices(g),'option_order':list(choices(g))}},'labels':{},'provenance':{'data_source':'cues_social_games_v1','source_id':'live','source_split':'demo'},'metadata':{'domain':'games','sub_domain':kind,'scenario':'interactive_control','task_category':'control'}}
