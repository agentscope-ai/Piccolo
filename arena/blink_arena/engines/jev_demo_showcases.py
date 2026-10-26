"""Interactive pilot scenes using the same deployed checkpoint and schema."""
import asyncio,copy,json,time,uuid
from fastapi import HTTPException
from pydantic import BaseModel,Field
from jev_showcase_common import ROOT,SCENES,LIVE_ONLY_SCENES
from jev_showcase_games import fresh as game_fresh,choices as game_choices,step as game_step,as_record as game_record
import jev_demo_robot_pick as robot
import jev_social_games as social_games
import jev_agent_games as agent_games
import jev_probability_games as probability_games
import jev_racing_game as racing
import jev_racing_runtime as racing_runtime
import jev_snake_realtime as snake
import jev_snake_runtime as snake_runtime
import jev_tetris_realtime as tetris
import jev_tetris_runtime as tetris_runtime
from jev_gameplay_contract import adapt_record
from typing import Literal, Annotated
from jev_environment_seeds import condition_info
from jev_engine_registry import get_engine, get_archived_engine, list_engines

Seed = Annotated[int, Field(strict=True, ge=0, le=4294967295)]

def fresh(kind,seed,opponent='human'):
    engine=get_engine(kind)
    # Historical callers used this native function for archived Terra states.
    # Live browser creation never comes through this compatibility facade.
    if kind=='terraria_survival':engine=get_archived_engine(kind)
    return engine.reset(seed, {'opponent':opponent} if engine.family in ('agent','selected','strategy') else {})
def choices(g):
    return get_engine(g['kind'],g).legal_actions(g)
def _step(g,action,*,card_ids=None,controller=None):
    kwargs=({'card_ids':card_ids} if card_ids is not None else {})
    if controller is not None:kwargs['controller']=controller
    return get_engine(g['kind'],g).raw_step(g,action,**kwargs)
def step(g,action,*,card_ids=None,controller=None):
    # Compatibility facade: HTTP, evaluation and RL share the same adapter.
    kwargs=({'card_ids':card_ids} if card_ids is not None else {})
    if controller is not None:kwargs['controller']=controller
    return get_engine(g['kind'],g).step(g,action,**kwargs)
def as_record(g):
    return get_engine(g['kind'],g).observe(g)

from jev_terraria_contract import OPTIONS as TERRA_OPTIONS,as_record as terra_record
from jev_mario_contract import OPTIONS as MARIO_OPTIONS,as_record as mario_record

SENSOR_SCENES={'robot_grasp_force':{'name':'机械臂 · 夹持状态','mode':'sensor',
    'note':'真实夹爪力／力矩记录：判断夹持过松、合适或过紧，支持曲线回放。',
    'url':'https://huggingface.co/datasets/yuezh23/UMI-Gripper-Grasping',
    'source':'https://huggingface.co/datasets/yuezh23/UMI-Gripper-Grasping',
    'source_label':'数据集 · UMI-Gripper-Grasping（实测）'}}

class New(BaseModel):
    kind:str
    seq:int|None=None
    seed:Seed|None=None
    opponent:Literal['human','rule']='human'
class Move(BaseModel):
    session_id:str
    revision:int
    action:str|None=None
    model:bool=False
    reference:bool=False
    piece_id:Annotated[int,Field(strict=True,ge=0)]|None=None
    card_ids:list[Annotated[int,Field(strict=True,ge=0,le=53)]]|None=Field(default=None,max_length=20)
class WorldDecision(BaseModel):
    state:dict
    kind:str='terraria_survival'
class WorldObservation(BaseModel):
    state:dict
class Text(BaseModel):
    seq:int
    text:str=Field(min_length=1,max_length=4000)
    context:str=Field(max_length=4000)
class RacingControl(BaseModel):
    session_id:str

def install(app,prefix,getcase,predict,db):
    sessions={}
    def payload(ident):
        s=sessions[ident];g=s['world']
        if g['kind']==racing.KIND:
            r=as_record(g) if not g['outcome'] else None
            opts=r['questions']['decision']['criteria'] if r else {}
        else:
            opts=choices(g)
            r=as_record(g) if len(opts)>=2 else None
        engine=get_engine(g['kind'],g)
        world=engine.public(g,**({'include_trace':True} if engine.runtime else {}))
        return {'session_id':ident,'revision':s['revision'],'world':world,'choices':opts,
            'environment':s.get('environment'),
            'goal':engine.goal,'input':{'state':r['state'],'prompt':r['questions']['decision']['instructions'],'option':r['questions']['decision']['criteria']} if r else None}

    @app.get(prefix+'/api/engines')
    async def engine_listing():
        return {'schema_version':'jev.engine-registry.v1',
                'engines':[engine.descriptor() for engine in list_engines()]}

    @app.get(prefix+'/api/engines/{kind}')
    async def engine_descriptor(kind:str):
        try:return get_engine(kind).descriptor()
        except (KeyError,ValueError):raise HTTPException(404,'未知游戏引擎')

    @app.post(prefix+'/api/engines/{kind}/observe')
    async def engine_observation(kind:str,body:WorldObservation):
        if len(json.dumps(body.state,ensure_ascii=False))>24000:raise HTTPException(413,'世界观测过长')
        try:engine=get_engine(kind)
        except (KeyError,ValueError):raise HTTPException(404,'未知游戏引擎')
        if not (engine.backend=='browser' or engine.backend=='worker' and engine.family=='world'):raise HTTPException(422,'原生环境请通过会话获取观测')
        return {'schema_version':'jev.engine-observation.v1','record':engine.observe(body.state)}

    @app.get(prefix+'/api/showcases')
    async def listing():
        from jev_demo_catalog import ROOT as DEMO
        path=DEMO/'catalog.json'
        catalog=json.loads(path.read_text()) if path.exists() else {'categories':[]}
        categories=catalog.get('categories',[])
        mapping_path=DEMO/'scene_category_mapping.json'
        mapping=json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
        cats={x['id']:x for x in categories}
        result=[]
        # Text tasks retain their existing independent schemas. All games come
        # from the shared registry, including plugins registered before startup.
        scenes=[]  # Text benchmark examples are not shipped; MBTI has its own API.
        scenes.extend((engine.kind,engine.scene_descriptor(),engine)
                      for engine in list_engines(include_internal=False)
                      if engine.family!='board')
        for kind,info,engine in scenes:
            category=mapping.get(kind)
            if category not in cats:
                category=next((x['id'] for x in categories if x['family']==kind),None)
            item={**info,'kind':kind,'category_id':category,
                  'sample_count':cats.get(category,{}).get('available_examples',0)}
            if engine:
                item.update(name=engine.name,engine=engine.descriptor(),
                            sft_export_prohibited=engine.sft_export_prohibited)
                # Archived turn-based data is not a replay of realtime rules.
                if engine.clock=='realtime':item.update(category_id=None,sample_count=0)
            result.append(item)
        return result

    @app.post(prefix+'/api/showcases/world')
    async def world_decision(body:WorldDecision):
        if len(json.dumps(body.state,ensure_ascii=False))>24000:raise HTTPException(413,'世界观测过长')
        try:engine=get_engine(body.kind)
        except (KeyError,ValueError):raise HTTPException(422,'未知游戏引擎')
        if not (engine.backend=='browser' or engine.backend=='worker' and engine.family=='world'):raise HTTPException(422,'不是共享世界环境')
        r=engine.observe(body.state)
        result=await predict(r,'decision');return {'result':result,'input':{'state':r['state'],'prompt':r['questions']['decision']['instructions'],'option':r['questions']['decision']['criteria']}}

    @app.post(prefix+'/api/showcases/new')
    async def new(body:New):
        try:engine=get_engine(body.kind)
        except (KeyError,ValueError):raise HTTPException(422,'未知游戏')
        if (engine.backend!='native' and body.seq is None) or engine.family=='board':raise HTTPException(422,'请使用对应的浏览器或棋盘入口')
        if body.seq is not None and body.seed is not None:raise HTTPException(422,'样例回放与种子开局不能同时指定')
        seed=body.seed if body.seed is not None else int(uuid.uuid4().hex[:8],16)
        if body.seq is not None:
            r=getcase(body.seq)['record']
            if r['metadata']['sub_domain']!=body.kind:raise HTTPException(422,'样例不属于这个游戏')
            from jev_demo_catalog import ROOT as DEMO
            world_path=DEMO/'interactive_worlds.json'
            worlds=json.loads((world_path if world_path.exists() else ROOT/'game_worlds.json').read_text())
            if r['id'] not in worlds:raise HTTPException(422,'没有对应游戏状态')
            g=copy.deepcopy(worlds[r['id']])
            if g['kind'] in agent_games.SCENES and '_rng_seed' in g:
                import random
                g['_rng']=random.Random(g['_rng_seed'])
            if g['kind']=='property_tycoon' and 'prices' in g:
                g['prices']={int(k):v for k,v in g['prices'].items()}
        else:g=fresh(body.kind,seed,body.opponent)
        engine=get_engine(body.kind,g)
        for ident in list(sessions):
            if sessions[ident]['updated']<time.monotonic()-86400 and not sessions[ident]['busy']:del sessions[ident]
        if len(sessions)>=1000:raise HTTPException(503,'当前对局过多')
        ident=uuid.uuid4().hex;sessions[ident]={'world':g,'revision':0,'busy':False,'updated':time.monotonic(),
            'environment':condition_info(body.kind,seed,replay=body.seq is not None)}
        if body.kind==racing.KIND:racing_runtime.start(sessions[ident])
        if snake.is_realtime(g):
            snake_runtime.start(sessions[ident])
            sessions[ident]['environment'].update(revision=snake.SEED_REVISION,description=snake.GOAL)
        if tetris.is_realtime(g):
            tetris_runtime.start(sessions[ident])
            sessions[ident]['environment'].update(revision=tetris.SEED_REVISION,description=tetris.GOAL)
        if engine.clock=='realtime' and body.kind not in (racing.KIND,snake.KIND,tetris.KIND):
            engine.runtime.start(sessions[ident])
        return payload(ident)

    def registered_session(kind,ident):
        s=sessions.get(ident)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if s['world']['kind']!=kind:raise HTTPException(422,'游戏类型不匹配')
        engine=get_engine(kind,s['world'])
        if engine.backend!='native' or engine.clock!='realtime':raise HTTPException(422,'不是原生实时环境')
        return s,engine

    @app.post(prefix+'/api/engines/{kind}/tick')
    async def registered_tick(kind:str,body:RacingControl):
        s,engine=registered_session(kind,body.session_id)
        engine.runtime.tick(s);s['updated']=time.monotonic()
        # Tick never replaces the exact input captured for a pending decision.
        return {'session_id':body.session_id,'revision':s['revision'],
                'world':engine.public(s['world'],include_trace=True),'busy':s['busy'],
                'clock_contract':engine.runtime.CLOCK_CONTRACT}

    @app.post(prefix+'/api/engines/{kind}/cancel')
    async def registered_cancel(kind:str,body:RacingControl):
        s,engine=registered_session(kind,body.session_id)
        engine.runtime.tick(s)
        key={racing.KIND:'racing_request_generation',snake.KIND:'snake_request_generation',
             tetris.KIND:'tetris_request_generation'}.get(kind,'engine_request_generation')
        s[key]=s.get(key,0)+1;s['busy']=False
        return {'cancelled':True,'session_id':body.session_id}

    async def registered_advance(body,s,engine):
        """Standard extension path; built-in realtime HTTP receipts stay stable."""
        if body.reference:raise HTTPException(422,'实时环境未注册规则接管')
        if body.revision!=s['revision'] or (body.model and s['busy']):raise HTTPException(409,'对局状态已变化')
        runtime=engine.runtime
        if not body.model:
            # Reject malformed human input before cancelling a valid in-flight
            # model decision. Physics still advances to the input arrival time.
            runtime.tick(s)
            if body.action not in engine.legal_actions(s['world']):raise HTTPException(422,'非法动作')
            s['engine_request_generation']=s.get('engine_request_generation',0)+1
        generation=s.get('engine_request_generation',0);s['busy']=bool(body.model)
        result=None;record=None;action=body.action;failure=None;reason=None
        started=time.monotonic()
        try:
            if body.model:
                delay=max(0.,s.get('engine_next_decision_at',0.)-time.monotonic())
                if delay:await asyncio.sleep(delay)
                if generation!=s.get('engine_request_generation',0):
                    return {**payload(body.session_id),'applied':False,'discard_reason':'cancelled','result':None}
            before,record=runtime.capture(s)
            if engine.outcome(before):raise HTTPException(422,'本局已结束')
            if body.model and (record is None or not record['questions']['decision']['criteria']):
                return {**payload(body.session_id),'result':None,'action':None,'applied':False,
                        'discard_reason':'no_decision_available','previous_input':None,'forced':False,
                        'execution':{'status':'discarded','reason':'no_decision_available',
                                     'clock_contract':runtime.CLOCK_CONTRACT}}
            options=record['questions']['decision']['criteria'] if body.model else engine.legal_actions(before)
            if body.model:
                s['engine_next_decision_at']=time.monotonic()+runtime.MIN_DECISION_SECONDS
                try:
                    result=await asyncio.wait_for(predict(record,'decision'),runtime.MODEL_TIMEOUT_SECONDS)
                    action=result['value']
                    if action not in options:raise ValueError('invalid_registered_action')
                except Exception as exc:failure='model_timeout' if isinstance(exc,TimeoutError) else 'model_error'
            elif action not in options:raise HTTPException(422,'非法动作')
            if generation!=s.get('engine_request_generation',0):
                runtime.tick(s);applied=False;reason='cancelled'
            elif failure:
                runtime.tick(s);applied=False
                if engine.outcome(s['world']):reason='game_finished_while_waiting'
                else:runtime.fail(s,failure);reason=failure
            else:
                receipt=runtime.commit(s,action,controller='model' if body.model else 'human',
                                       observed=before if body.model else None)
                applied=receipt['applied'];reason=receipt.get('reason')
            if reason!='cancelled':s['revision']+=1
            s['updated']=time.monotonic()
            previous_input={'state':record['state'],'prompt':record['questions']['decision']['instructions'],
                            'option':record['questions']['decision']['criteria']} if body.model else None
            return {**payload(body.session_id),'result':result,'action':action,
                    'action_name':options.get(action,action),'applied':applied,'discard_reason':reason,
                    'forced':False,'controller':'model' if body.model else 'human','previous_input':previous_input,
                    'execution':{'status':'executed' if applied else 'discarded','reason':reason,
                                 'waiting_seconds':time.monotonic()-started,'clock_contract':runtime.CLOCK_CONTRACT}}
        finally:
            if generation==s.get('engine_request_generation',0):s['busy']=False

    def racing_session(ident):
        s=sessions.get(ident)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if s['world']['kind']!=racing.KIND:raise HTTPException(422,'不是实时赛车对局')
        return s

    async def racing_tick(body:RacingControl):
        s=racing_session(body.session_id)
        racing_runtime.tick(s)
        s['updated']=time.monotonic()
        # Polls advance physics even while predict() is awaiting. They never
        # create a new decision input or overwrite the captured prompt.
        return {'session_id':body.session_id,'revision':s['revision'],
                'world':racing.public(s['world'],include_trace=True),
                'busy':s['busy'],'clock_contract':racing_runtime.CLOCK_CONTRACT}

    async def racing_cancel(body:RacingControl):
        s=racing_session(body.session_id)
        racing_runtime.tick(s)
        s['racing_request_generation']=s.get('racing_request_generation',0)+1
        s['busy']=False
        return {'cancelled':True,'session_id':body.session_id}

    def racing_manual(body,s):
        # Human steering is immediate; only model queries have a 1 s cadence.
        # Invalidate an outstanding reply before it can take over the new input.
        if body.reference:raise HTTPException(422,'赛车没有规则策略代驾')
        before=racing_runtime.tick(s)
        if before['outcome']:
            return {**payload(body.session_id),'applied':False,'discard_reason':'terminal','result':None}
        # A human key event does not request model inference. Do not block key
        # release with candidate simulation, or manufacture a model-input receipt.
        options={action:action for action in racing._actions(before)}
        if body.action not in options:raise HTTPException(422,'非法赛车动作')
        s['racing_request_generation']=s.get('racing_request_generation',0)+1
        s['busy']=False
        receipt=racing_runtime.commit(s,body.action,controller='human')
        s.update(revision=s['revision']+1,updated=time.monotonic())
        world=s['world']
        return {'session_id':body.session_id,'revision':s['revision'],
                'world':racing.public(world,include_trace=True),
                'choices':options if not world['outcome'] else {},
                'environment':s.get('environment'),'goal':get_engine(racing.KIND).goal,
                'input':None,'input_origin':'no_model_request',
                'result':None,'action':body.action,
                'action_name':options[body.action],'applied':receipt['applied'],
                'discard_reason':receipt['reason'],'forced':False,'controller':'human',
                'previous_input':None,
                'execution':{'status':'executed' if receipt['applied'] else 'discarded',
                             'reason':receipt['reason'],'controller':'human',
                             'clock_contract':racing_runtime.CLOCK_CONTRACT}}

    async def racing_advance(body,s):
        if body.reference:raise HTTPException(422,'赛车没有规则策略代驾')
        generation=s.get('racing_request_generation',0)
        delay=max(0.,s.get('racing_next_decision_at',0.)-time.monotonic())
        if delay:await asyncio.sleep(delay)
        if generation!=s.get('racing_request_generation',0):
            return {**payload(body.session_id),'applied':False,'discard_reason':'cancelled','result':None}
        before,record=racing_runtime.capture(s)
        if before['outcome']:
            return {**payload(body.session_id),'applied':False,'discard_reason':'terminal','result':None}
        captured_at=s['racing_clock_at']
        s['racing_next_decision_at']=captured_at+racing_runtime.MIN_DECISION_SECONDS
        previous_input={'state':record['state'],'prompt':record['questions']['decision']['instructions'],
                        'option':record['questions']['decision']['criteria']}
        options=record['questions']['decision']['criteria']
        result=None;action=body.action;failure=None
        try:
            if body.model:
                result=await asyncio.wait_for(predict(record,'decision'),racing_runtime.MODEL_TIMEOUT_SECONDS)
                action=result['value']
            if action not in options:raise ValueError('invalid_racing_action')
        except Exception as exc:
            if not body.model:raise HTTPException(422,'非法赛车动作')
            failure='model_timeout' if isinstance(exc,TimeoutError) else 'model_error'
        if generation!=s.get('racing_request_generation',0):
            racing_runtime.tick(s);applied=False;reason='cancelled'
        elif failure:
            racing_runtime.fail(s,failure);applied=False;reason=failure
        else:
            receipt=racing_runtime.commit(s,action);applied=receipt['applied'];reason=receipt['reason']
        arrived=s['world']
        # A cancelled reply must not invalidate the revision of a newer human
        # input or clear the ownership of a newer model request.
        if reason!='cancelled':s['revision']+=1
        s['updated']=time.monotonic()
        execution={'status':'executed' if applied else 'discarded','reason':reason,
            'observation_elapsed':before['elapsed'],'arrival_elapsed':arrived['elapsed'],
            'waiting_seconds':time.monotonic()-captured_at,
            'inference_frames':round((arrived['elapsed']-before['elapsed'])/racing.DT),
            'rule_takeover_C':arrived['rule_takeover_count'],
            'clock_contract':racing_runtime.CLOCK_CONTRACT}
        return {**payload(body.session_id),'result':result,'action':action,
            'action_name':options.get(action,action),'applied':applied,'discard_reason':reason,
            'forced':False,'controller':'model' if body.model else 'human',
            'previous_input':previous_input,'execution':execution}

    def snake_session(ident):
        s=sessions.get(ident)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if not snake.is_realtime(s['world']):raise HTTPException(422,'不是实时贪吃蛇对局')
        return s

    @app.post(prefix+'/api/showcases/snake/tick')
    async def snake_tick(body:RacingControl):
        s=snake_session(body.session_id)
        snake_runtime.tick(s);s['updated']=time.monotonic()
        return {'session_id':body.session_id,'revision':s['revision'],
                'world':snake.public(s['world'],include_trace=True),'choices':snake.choices(s['world']),
                'busy':s['busy'],'clock_contract':snake_runtime.CLOCK_CONTRACT}

    @app.post(prefix+'/api/showcases/snake/cancel')
    async def snake_cancel(body:RacingControl):
        s=snake_session(body.session_id);snake_runtime.tick(s)
        s['snake_request_generation']=s.get('snake_request_generation',0)+1
        s['busy']=False
        return {'cancelled':True,'session_id':body.session_id}

    async def snake_advance(body,s):
        if body.reference:raise HTTPException(422,'贪吃蛇没有规则代驾')
        if s['revision']!=body.revision:raise HTTPException(409,'方向输入已变化，请刷新后重试')
        if body.model and s['busy']:raise HTTPException(409,'模型正在判断')
        # Manual steering can take control while inference runs. Its generation
        # prevents the older response from overwriting the new human direction.
        if not body.model:
            if body.action not in snake.choices(s['world']):raise HTTPException(422,'非法方向')
            s['snake_request_generation']=s.get('snake_request_generation',0)+1
        generation=s.get('snake_request_generation',0)
        s['busy']=bool(body.model)
        if body.model:
            delay=max(0.,s.get('snake_next_decision_at',0.)-time.monotonic())
            if delay:await asyncio.sleep(delay)
            if generation!=s.get('snake_request_generation',0):
                return {**payload(body.session_id),'applied':False,'discard_reason':'cancelled','result':None}
        before,record=snake_runtime.capture(s)
        captured_at=s['snake_clock_at']
        if body.model:s['snake_next_decision_at']=captured_at+snake_runtime.MIN_DECISION_SECONDS
        if before['outcome']:
            s['busy']=False
            return {**payload(body.session_id),'applied':False,'discard_reason':'terminal','result':None}
        options=record['questions']['decision']['criteria']
        previous_input={'state':record['state'],'prompt':record['questions']['decision']['instructions'],
                        'option':options} if body.model else None
        result=None;action=body.action;failure=None
        try:
            if body.model:
                try:
                    result=await asyncio.wait_for(predict(record,'decision'),snake_runtime.MODEL_TIMEOUT_SECONDS)
                    action=result['value']
                    if action not in options:raise ValueError('invalid_snake_action')
                except Exception as exc:
                    failure='model_timeout' if isinstance(exc,TimeoutError) else 'model_error'
            if generation!=s.get('snake_request_generation',0):
                snake_runtime.tick(s);applied=False;reason='cancelled'
            elif failure:
                snake_runtime.fail(s,failure);applied=False;reason=failure
            else:
                receipt=snake_runtime.commit(s,action,controller='model' if body.model else 'human')
                applied=receipt['applied'];reason=receipt['reason']
            if reason!='cancelled':s['revision']+=1
            s['updated']=time.monotonic()
            arrived=s['world']
            return {**payload(body.session_id),'result':result,'action':action,
                    'action_name':options.get(action,action),'applied':applied,'discard_reason':reason,
                    'forced':False,'controller':'model' if body.model else 'human',
                    'previous_input':previous_input,
                    'execution':{'status':'executed' if applied else 'discarded','reason':reason,
                        'observation_elapsed':before['elapsed'],'arrival_elapsed':arrived['elapsed'],
                        'waiting_seconds':time.monotonic()-captured_at,
                        'inference_moves':arrived['steps']-before['steps'],
                        'clock_contract':snake_runtime.CLOCK_CONTRACT}}
        finally:
            if generation==s.get('snake_request_generation',0):s['busy']=False

    def tetris_session(ident):
        s=sessions.get(ident)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if not tetris.is_realtime(s['world']):raise HTTPException(422,'不是实时俄罗斯方块对局')
        return s

    @app.post(prefix+'/api/showcases/tetris/tick')
    async def tetris_tick(body:RacingControl):
        s=tetris_session(body.session_id)
        tetris_runtime.tick(s);s['updated']=time.monotonic()
        return {'session_id':body.session_id,'revision':s['revision'],
                'world':tetris.public(s['world'],include_trace=True),'choices':tetris.choices(s['world']),
                'busy':s['busy'],'clock_contract':tetris_runtime.CLOCK_CONTRACT}

    @app.post(prefix+'/api/showcases/tetris/cancel')
    async def tetris_cancel(body:RacingControl):
        s=tetris_session(body.session_id);tetris_runtime.tick(s)
        s['tetris_request_generation']=s.get('tetris_request_generation',0)+1
        s['busy']=False
        return {'cancelled':True,'session_id':body.session_id}

    async def tetris_advance(body,s):
        if body.reference:raise HTTPException(422,'俄罗斯方块没有规则代驾')
        if s['revision']!=body.revision:raise HTTPException(409,'输入已变化，请刷新后重试')
        if body.model and s['busy']:raise HTTPException(409,'模型正在判断')
        if not body.model:
            tetris_runtime.tick(s)
            if s['world']['outcome'] or not tetris.choices(s['world']):
                return {**payload(body.session_id),'applied':False,
                        'discard_reason':'terminal' if s['world']['outcome'] else 'clearing','result':None}
            if body.piece_id is not None and body.piece_id!=tetris_runtime.piece_id(s['world']):
                return {**payload(body.session_id),'applied':False,
                        'discard_reason':'piece_changed_while_waiting','result':None}
            if body.action not in tetris.choices(s['world']):raise HTTPException(422,'非法俄罗斯方块动作')
            s['tetris_request_generation']=s.get('tetris_request_generation',0)+1
        generation=s.get('tetris_request_generation',0)
        s['busy']=bool(body.model)
        try:
            if body.model:
                delay=max(0.,s.get('tetris_next_decision_at',0.)-time.monotonic())
                if delay:await asyncio.sleep(delay)
                if generation!=s.get('tetris_request_generation',0):
                    return {**payload(body.session_id),'applied':False,'discard_reason':'cancelled','result':None}
            before,record=tetris_runtime.capture(s,for_policy=body.model)
            captured_at=s['tetris_clock_at']
            if before['outcome'] or record is None:
                return {**payload(body.session_id),'applied':False,
                        'discard_reason':tetris.decision_reason(before),'result':None,
                        'execution':{'status':'continuing' if tetris.decision_reason(before)=='continuing_intent' else 'idle',
                            'reason':tetris.decision_reason(before),'strategy_origin':'A','execution_origin':'B',
                            'clock_contract':tetris_runtime.CLOCK_CONTRACT}}
            if body.model:s['tetris_next_decision_at']=captured_at+tetris_runtime.MIN_DECISION_SECONDS
            options=record['questions']['decision']['criteria'] if body.model else tetris.choices(before)
            previous_input={'state':record['state'],'prompt':record['questions']['decision']['instructions'],
                            'option':options} if body.model else None
            result=None;action=body.action;failure=None
            if body.model:
                try:
                    result=await asyncio.wait_for(predict(record,'decision'),tetris_runtime.MODEL_TIMEOUT_SECONDS)
                    action=result['value']
                    if action not in options:raise ValueError('invalid_tetris_action')
                except Exception as exc:
                    failure='model_timeout' if isinstance(exc,TimeoutError) else 'model_error'
            if generation!=s.get('tetris_request_generation',0):
                tetris_runtime.tick(s);applied=False;reason='cancelled'
            elif failure:
                tetris_runtime.tick(s)
                reason='game_finished_while_waiting' if s['world']['outcome'] else failure
                tetris_runtime.fail(s,failure);applied=False
            else:
                receipt=tetris_runtime.commit(s,action,controller='model' if body.model else 'human',
                                              observed=before if body.model or body.piece_id is not None else None)
                applied=receipt['applied'];reason=receipt['reason']
            if reason!='cancelled':s['revision']+=1
            s['updated']=time.monotonic()
            arrived=s['world']
            return {**payload(body.session_id),'result':result,'action':action,
                    'action_name':options.get(action,action),'applied':applied,'discard_reason':reason,
                    'forced':False,'controller':'model' if body.model else 'human',
                    'previous_input':previous_input,
                    'execution':{'status':'executed' if applied else 'discarded','reason':reason,
                        'observation_elapsed':before['elapsed'],'arrival_elapsed':arrived['elapsed'],
                        'observation_piece_id':tetris_runtime.piece_id(before),
                        'arrival_piece_id':tetris_runtime.piece_id(arrived),
                        'waiting_seconds':time.monotonic()-captured_at,
                        'clock_contract':tetris_runtime.CLOCK_CONTRACT}}
        finally:
            if generation==s.get('tetris_request_generation',0):s['busy']=False

    @app.post(prefix+'/api/showcases/reveal')
    async def reveal(body:Move):
        s=sessions.get(body.session_id)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if s['busy'] or s['revision']!=body.revision:raise HTTPException(409,'棋局已变化，请稍后重试')
        engine=get_engine(s['world']['kind'],s['world'])
        if not s['world'].get('handoff'):
            raise HTTPException(422,'当前无需交接')
        if 'private_turns' in engine.capabilities:
            world=engine.environment.reveal(s['world'])
        elif s['world']['kind'] in agent_games.HIDDEN:
            world=agent_games.reveal(s['world'])
        else:
            raise HTTPException(422,'当前无需交接')
        s.update(world=world,revision=s['revision']+1,updated=time.monotonic())
        return payload(body.session_id)

    @app.post(prefix+'/api/showcases/step')
    async def advance(body:Move):
        s=sessions.get(body.session_id)
        if s is None:raise HTTPException(404,'对局已过期，请重新开局')
        if body.card_ids is not None and (s['world']['kind']!='doudizhu' or body.model or body.reference):
            raise HTTPException(422,'具体牌选择仅适用于人工斗地主出牌')
        if tetris.is_realtime(s['world']):return await tetris_advance(body,s)
        if snake.is_realtime(s['world']):return await snake_advance(body,s)
        engine=get_engine(s['world']['kind'],s['world'])
        if engine.clock=='realtime' and engine.kind!=racing.KIND:return await registered_advance(body,s,engine)
        if s['world']['kind']==racing.KIND and not body.model:
            if s['revision']!=body.revision:raise HTTPException(409,'赛车输入已变化，请刷新后重试')
            return racing_manual(body,s)
        if s['busy'] or s['revision']!=body.revision:raise HTTPException(409,'棋局已变化，请稍后重试')
        options=racing._actions(s['world']) if s['world']['kind']==racing.KIND else choices(s['world'])
        if not options:raise HTTPException(422,'本局已结束')
        s['busy']=True
        request_generation=s.get('racing_request_generation',0)
        try:
            if s['world']['kind']==racing.KIND:return await racing_advance(body,s)
            result=None;forced=False
            if body.reference:
                if body.model:raise HTTPException(422,'参考策略与模型决策不能同时请求')
                if 'reference_action' in engine.capabilities:
                    action=await asyncio.to_thread(engine.environment.reference_action,s['world'])
                elif s['world']['kind']=='robot_pick_cola':action=robot.best(s['world'])
                else:raise HTTPException(422,'当前游戏未注册显式参考策略')
            elif body.model:
                if len(options)==1:action=next(iter(options));forced=True
                else:
                    record=as_record(s['world'])
                    decisions=record['questions']['decision']['criteria']
                    if len(decisions)==1:action=next(iter(decisions));forced=True
                    else:result=await predict(record,'decision');action=result['value']
            else:action=body.action
            hidden=s['world']['kind'] in agent_games.HIDDEN or 'private_turns' in engine.capabilities
            previous_input=None if hidden else payload(body.session_id)['input']
            provenance='controller_provenance' in engine.capabilities
            controller=('rule_engine' if provenance and body.reference else
                        'deterministic_execution' if provenance and forced else
                        'reference' if body.reference else 'model' if body.model else 'human')
            if engine.family=='agent':
                actor_label=agent_games.names(s['world'])[agent_games.actor(s['world'])]
            elif provenance:
                before=engine.public(s['world']);actor_label=before['players'][before['current_player']]
            else:actor_label=None
            try:
                if provenance:g=await asyncio.to_thread(step,s['world'],action,controller=controller)
                elif engine.family=='agent':g=await asyncio.to_thread(step,s['world'],action)
                else:g=step(s['world'],action,card_ids=body.card_ids)
            except (ValueError,TypeError):raise HTTPException(422,'非法动作')
            s.update(world=g,revision=s['revision']+1,updated=time.monotonic())
            sealed=(g['kind']=='goofspiel' and g.get('_pending') is not None) or ('private_turns' in engine.capabilities and engine.environment.sealed(g))
            return {**payload(body.session_id),'result':None if hidden and g.get('handoff') else result,
                # Keep call timing available when private decisions are redacted.
                'decision_timing':{'latency_seconds':result.get('latency_seconds')} if result else None,
                'action':None if sealed else action,'action_name':'已密封出牌' if sealed else options[action], 'actor_label':actor_label,
                'forced':forced,'controller':controller,'previous_input':previous_input}
        finally:
            if s['world']['kind']!=racing.KIND or request_generation==s.get('racing_request_generation',0):
                s['busy']=False

    @app.post(prefix+'/api/showcases/text')
    async def classify(body:Text):
        r=copy.deepcopy(getcase(body.seq)['record']);kind=r['metadata']['sub_domain']
        if kind not in SCENES or SCENES[kind]['mode']!='text':raise HTTPException(422,'不是文本场景样例')
        if not body.text.strip():raise HTTPException(422,'请输入内容')
        modified=r['state']['text']!=body.text or r['state']['context']!=body.context
        r['state'].update(text=body.text,context=body.context)
        if modified:r['labels']={}
        result=await predict(r,'decision');q=r['questions']['decision']
        return {'result':result,'modified':modified,'input':{'state':r['state'],'prompt':q['instructions'],'option':q['criteria']}}
