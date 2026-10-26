"""Standard training RPC assembled from the same lightweight game runners.

No training framework, checkpoint, model URL or model credential is required.
Resources are acquired only when a rollout client first uses the service.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace


class Rollouts:
    def __init__(self, directory, frontend, *, opponent=None, decision_timeout=90.,
                 max_active=16, completed_cache_size=32, completed_cache_bytes=64*1024*1024):
        self.directory = Path(directory)
        self.frontend, self.opponent = frontend, opponent
        self.options = dict(decision_timeout=decision_timeout, max_active=max_active,
                            completed_cache_size=completed_cache_size, completed_cache_bytes=completed_cache_bytes)
        self.backend = None
        self.browser = None
        self.playwright = None
        self.lock = asyncio.Lock()
        self.browser_lock = asyncio.Lock()

    async def _ready(self):
        if self.backend is None:
            async with self.lock:
                if self.backend is None:
                    from jev_engine_rollout_backend import RolloutBackend
                    self.backend = RolloutBackend(self._episode, storage_dir=self.directory, **self.options)
        return self.backend

    async def _browser(self):
        if self.browser is None:
            async with self.browser_lock:
                if self.browser is None:
                    from playwright.async_api import async_playwright
                    self.playwright = await async_playwright().start()
                    try:
                        self.browser = await self.playwright.chromium.launch(headless=True)
                    except BaseException:
                        await self.playwright.stop()
                        self.playwright = None
                        raise
        return self.browser

    async def _episode(self, proxy, job):
        from jev_engine_registry import get_engine
        from jev_engine_episode import make_runner
        browser = await self._browser() if get_engine(job['kind']).backend == 'browser' else None
        args = SimpleNamespace(out=str(self.directory / 'execution'), frontend=self.frontend,
                               qwen_concurrency=8)
        return await make_runner(args, browser=browser, opponent=self.opponent)(proxy, job)

    async def start(self, *args, **kwargs):
        return await (await self._ready()).start(*args, **kwargs)

    async def next_decision(self, *args, **kwargs):
        return await (await self._ready()).next_decision(*args, **kwargs)

    async def answer(self, *args, **kwargs):
        return await (await self._ready()).answer(*args, **kwargs)

    async def result(self, *args, **kwargs):
        return await (await self._ready()).result(*args, **kwargs)

    async def encode_response(self, *args, **kwargs):
        return await (await self._ready()).encode_response(*args, **kwargs)

    async def cancel(self, *args, **kwargs):
        return await (await self._ready()).cancel(*args, **kwargs)

    async def list_results(self, *args, **kwargs):
        return await (await self._ready()).list_results(*args, **kwargs)

    async def close(self):
        if self.backend is not None:
            await self.backend.close()
            self.backend = None
        if self.browser is not None:
            await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None
