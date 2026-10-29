"""Versioned session API adapting the same registered engines used by RL."""
import asyncio
import copy
import time
import uuid
from fastapi import HTTPException
from jev_engine_registry import get_engine
from jev_control_scope import active_games
from jev_world_episode_clock import install_episode_clock


class BrowserDriver:
    """Execute the registered browser bridge; no second physics implementation."""
    def __init__(self, page, bridge): self.page,self.bridge=page,bridge

    async def reset(self, seed, options):
        return await self.page.evaluate('''([b,s])=>{const api=window[b];api.reset(s);api.activate(true);
            const state=api.prepare({clock:"realtime"});window.__JevEpisodeClock.start();return state}''',[self.bridge,seed])

    async def step(self, observation, action, **kwargs):
        return await self.page.evaluate('''async ([b,a,observed])=>{const api=window[b],arrival=api.snapshot();
            const reason=arrival.outcome?'terminal':(arrival.wins||0)!==(observed.wins||0)?'world_changed':
            (arrival.deaths||0)!==(observed.deaths||0)||arrival.player?.respawning||observed.player?.respawning?'death_or_respawn':null;
            const after=reason?arrival:await api.act(a);return {arrival,after,reason};}''',[self.bridge,action,observation])


class Sessions:
    def __init__(self, predict, frontend):
        self.predict,self.frontend=predict,frontend
        self.items={}
        self.playwright=self.browser=None
        self.browser_lock=asyncio.Lock()

    async def browser_instance(self):
        async with self.browser_lock:
            if self.browser is None:
                from playwright.async_api import async_playwright
                self.playwright=await async_playwright().start()
                self.browser=await self.playwright.chromium.launch(headless=True,args=['--no-sandbox'])
        return self.browser

    async def create(self, kind, seed, owner):
        try: engine=get_engine(kind)
        except (KeyError,ValueError): raise HTTPException(422,'Unknown game') from None
        if engine.internal or not active_games([kind]): raise HTTPException(422,'Game is not enabled')
        for ident,old in list(self.items.items()):
            if time.monotonic()-old['updated']>3600 and not old['lock'].locked(): await self.remove(ident,old['owner'])
        if len(self.items)>=256: raise HTTPException(429,'Session limit reached')
        ident=uuid.uuid4().hex
        item={'kind':kind,'seed':seed,'owner':owner,'engine':engine,'revision':0,'lock':asyncio.Lock(),
              'updated':time.monotonic(),'trace':[]}
        if engine.backend=='worker' and engine.family=='world':
            from jev_world_core import WorldCoreDriver
            driver=WorldCoreDriver(kind,seed)
            try:
                item['engine']=engine.bind(driver)
                item['world']=await item['engine'].reset(seed,{})
                item['driver']=driver
            except BaseException:
                await driver.close();raise
        elif engine.backend=='browser':
            if sum('page' in s for s in self.items.values())>=8: raise HTTPException(429,'Browser session limit reached')
            browser=await self.browser_instance()
            page=await browser.new_page(viewport={'width':920,'height':700})
            try:
                await install_episode_clock(page,kind)
                await page.goto(self.frontend+'/playground/'+engine.browser_page+'.html')
                await page.wait_for_function('!!window.'+engine.browser_bridge+'?.snapshot')
                item['engine']=engine.bind(BrowserDriver(page,engine.browser_bridge))
                item['world']=await item['engine'].reset(seed,{})
                item.update(page=page,bridge=engine.browser_bridge)
            except BaseException:
                await page.close();raise
        else:
            item['world']=engine.reset(seed,{})
            if engine.runtime: engine.runtime.start(item)
        self.items[ident]=item
        return await self.view(ident,owner)

    def require(self, ident, owner):
        item=self.items.get(ident)
        if not item or item['owner']!=owner: raise HTTPException(404,'Session not found')
        return item

    async def observe(self, item):
        engine=item['engine']
        if 'driver' in item:
            item['world']=(await item['driver'].capture())['state']
        elif engine.backend=='browser':
            item['world']=await item['page'].evaluate('b=>window[b].prepare({clock:"realtime"})',item['bridge'])
        elif engine.runtime: engine.runtime.tick(item)
        # Simultaneous OpenSpiel choices have a separate handoff reveal, just
        # as the live frontend; no opponent private state enters observe().
        if engine.family=='agent' and item['world'].get('handoff'):
            import jev_agent_games
            item['world']=jev_agent_games.reveal(item['world'])
        item['updated']=time.monotonic()

    def public(self,item):
        engine=item['engine']
        return engine.public(item['world'],**({'include_trace':True} if engine.runtime else {}))

    def record(self,item):
        engine=item['engine'];state=item['world']
        if engine.outcome(state) or len(engine.legal_actions(state))<2:return None
        return engine.model_input(state)

    def private_turns(self, item):
        engine=item['engine']
        if 'private_turns' in engine.capabilities:return True
        if engine.family=='agent':
            import jev_agent_games
            return item['kind'] in jev_agent_games.HIDDEN
        return False

    def replay(self, ident, owner):
        item=self.require(ident,owner)
        steps=copy.deepcopy(item['trace'])
        private=self.private_turns(item)
        if private:
            # The server retains the exact audit, but a shared hot-seat browser
            # cannot retrieve a previous player's private hand or sealed bid.
            for row in steps:
                row['before_state']=None;row['state']=None;row['decision']=None
                if row.pop('sealed',False):row['action']=None
        return {'schema_version':'jev.session-replay.v1','game':item['kind'],'seed':item['seed'],
                'steps':steps,'private_history_redacted':private}

    async def view(self,ident,owner):
        item=self.require(ident,owner)
        async with item['lock']: return await self._view(ident,item)

    async def _view(self,ident,item):
        await self.observe(item)
        engine=item['engine'];record=self.record(item)
        return {'schema_version':'jev.session.v1','session_id':ident,'game':item['kind'],'seed':item['seed'],
                'revision':item['revision'],'state':self.public(item),'terminal':bool(engine.outcome(item['world'])),
                'legal_actions':engine.legal_actions(item['world']),
                'decision':None if record is None else {'observation':record['state'],'question':record['questions']['decision']},
                'engine':engine.descriptor()}

    async def step(self,ident,owner,body):
        item=self.require(ident,owner)
        if item['lock'].locked():raise HTTPException(409,'Session action in progress')
        async with item['lock']:
            if body.revision!=item['revision']:raise HTTPException(409,'Session revision changed')
            await self.observe(item)
            engine=item['engine'];before=copy.deepcopy(self.public(item))
            if engine.outcome(item['world']):raise HTTPException(409,'Game already finished')
            if getattr(body, 'reveal', False):
                if body.action is not None or body.model_id or body.ticks or getattr(body, 'reference', False) or 'private_turns' not in engine.capabilities:
                    raise HTTPException(422,'Invalid seat handoff request')
                try: item['world']=engine.environment.reveal(item['world'])
                except ValueError: raise HTTPException(422,'No pending seat handoff') from None
                item['revision']+=1
                return await self._view(ident,item)
            action=body.action;result=None;record=self.record(item);forced=False
            reference=getattr(body, 'reference', False)
            controller='reference' if reference else 'model' if body.model_id else 'human'
            previous_decision=None if record is None else copy.deepcopy({'observation':record['state'],'question':record['questions']['decision']})
            previous_input=None if record is None else copy.deepcopy({'state':record['state'],
                'prompt':record['questions']['decision']['instructions'],
                'option':record['questions']['decision']['criteria']})
            if reference:
                if 'reference_action' not in engine.capabilities:
                    raise HTTPException(422,'Game does not support explicit reference actions')
                action=engine.environment.reference_action(item['world'])
            if body.model_id:
                legal=engine.legal_actions(item['world'])
                if len(legal)==1:action=next(iter(legal));forced=True
                elif record:
                    result=await self.predict(record,'decision',model=body.model_id);action=result['value']
                else:raise HTTPException(409,'No decision available')
            applied=action is not None;execution=None
            if action is not None:
                try:
                    if engine.backend=='browser' or 'driver' in item:
                        execution=await engine.step(before,action)
                        item['world']=execution['after'];applied=execution['reason'] is None
                    elif engine.runtime:
                        execution=engine.runtime.commit(item,action,controller='model' if body.model_id else 'human',observed=before)
                        applied=execution['applied']
                    else:
                        execution_controller='deterministic_execution' if forced else 'rule_engine' if reference else controller
                        kwargs={'controller':execution_controller} if 'controller_provenance' in engine.capabilities else {}
                        item['world']=engine.step(item['world'],action,**kwargs)
                except (ValueError,KeyError,TypeError):raise HTTPException(422,'Illegal game action') from None
            if body.ticks:await asyncio.sleep(body.ticks/60)
            item['revision']+=1
            view=await self._view(ident,item)
            private=self.private_turns(item)
            sealed=(bool(engine.environment.sealed(item['world'])) if 'private_turns' in engine.capabilities else
                    item['kind']=='goofspiel' and item['world'].get('_pending') is not None)
            item['trace'].append({'action':action,'model':body.model_id,'applied':applied,
                                  'controller':controller,'forced':forced,
                                  **({'sealed':sealed} if private else {}),
                                  'before_state':before,'state':copy.deepcopy(view['state']),
                                  'decision':previous_decision,
                                  'latency_seconds':(result or {}).get('latency_seconds')})
            return {**view,'action':None if sealed else action,'applied':applied,
                    'result':None if private and (view['state'].get('handoff') or sealed) else result,
                    'controller':controller,'forced':forced,
                    'previous_decision':None if private else previous_decision,
                    'previous_input':None if private else previous_input}

    async def remove(self,ident,owner):
        item=self.require(ident,owner)
        if item['lock'].locked():raise HTTPException(409,'Session action in progress')
        self.items.pop(ident)
        if 'page' in item:await item['page'].close()
        if 'driver' in item:await item['driver'].close()

    async def close(self):
        for item in self.items.values():
            if 'driver' in item:await item['driver'].close()
        if self.browser:await self.browser.close()
        if self.playwright:await self.playwright.stop()
