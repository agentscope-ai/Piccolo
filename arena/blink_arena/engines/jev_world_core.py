"""Async driver for the exact JS core shared with the frontend, without a browser."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil

RUNTIME_REVISION = 'jev.shared-core.node.v1'


def asset_directory():
    configured = os.environ.get('JEV_ENGINE_ASSET_DIRECTORY')
    if configured:
        return Path(configured)
    location = Path(__file__).resolve()
    packaged = location.parents[2] / 'web' / 'playground'
    if packaged.is_dir():
        return packaged
    # The retained source-tools adapter can consume the sibling standalone
    # package; installed standalone releases resolve the first path above.
    return location.parents[3] / 'BlinkArena' / 'web' / 'playground'


class WorldCoreDriver:
    def __init__(self, kind, seed, *, replay=False, options=None, frame=None,
                 startup_timeout=90., operation_timeout=120., assets=None,
                 viewport_width=None, viewport_height=None, inference_world_paused=False):
        self.kind, self.seed, self.replay = kind, seed, replay
        self.inference_world_paused = inference_world_paused
        self.options, self.frame = options, frame
        self.startup_timeout, self.operation_timeout = startup_timeout, operation_timeout
        self.assets = Path(assets) if assets else asset_directory()
        from jev_engine_registry import get_engine
        specification = get_engine(kind)
        if not specification.core_module:
            raise ValueError('engine_does_not_register_a_shared_js_core')
        self.core_module = specification.core_module
        self.viewport_width = viewport_width or specification.core_viewport[0]
        self.viewport_height = viewport_height or specification.core_viewport[1]
        self.process = None
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.initial = None

    async def start(self):
        if self.process is not None:
            raise RuntimeError('world_core_driver_already_started')
        executable = os.environ.get('JEV_NODE_EXECUTABLE') or shutil.which('node')
        if not executable:
            raise RuntimeError('Node.js is required for shared JavaScript engines')
        worker = self.assets / 'world-core-worker.cjs'
        self.process = await asyncio.create_subprocess_exec(executable, str(worker),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=16 * 1024 * 1024)
        try:
            self.initial = await self.call('init', timeout=self.startup_timeout,
                kind=self.kind, seed=self.seed, replay=self.replay, options=self.options,
                frame=self.frame, width=self.viewport_width, height=self.viewport_height,
                core_module=self.core_module, inference_world_paused=self.inference_world_paused)
            return self.initial
        except BaseException:
            await self.close()
            raise

    async def call(self, method, *, timeout=None, **params):
        async with self.lock:
            if self.process is None or self.process.returncode is not None:
                raise RuntimeError('world_core_worker_not_running')
            self.sequence += 1
            request = {'id': self.sequence, 'method': method, 'params': params}
            try:
                async with asyncio.timeout(timeout or self.operation_timeout):
                    self.process.stdin.write((json.dumps(request, allow_nan=False) + '\n').encode())
                    await self.process.stdin.drain()
                    line = await self.process.stdout.readline()
                    if not line:
                        raise RuntimeError('world_core_worker_exited_without_response')
                    reply = json.loads(line)
                    if reply.get('id') != self.sequence:
                        raise RuntimeError('world_core_response_identity_mismatch')
                    if 'error' in reply:
                        error = reply['error']
                        raise RuntimeError('world_core_' + error['type'] + ':' + error['message'])
                    return reply['result']
            except BaseException:
                # A timed-out or cancelled pipe cannot safely serve another
                # request: an old reply could be mistaken for a new decision.
                self.process.terminate() if self.process.returncode is None else None
                raise

    async def reset(self, seed, options=None):
        if self.process is not None:
            raise RuntimeError('use_a_fresh_driver_for_each_seeded_episode')
        self.seed, self.options = seed, options
        return (await self.start())['state']

    async def capture(self):
        return await self.call('capture')

    async def step(self, observation, action, **kwargs):
        result = await self.call('commit', action=action, observed=observation)
        return {**result, 'arrival': result['arrival_state'], 'after': result['after_state']}

    async def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        if process.stdin:
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 5.)
        except TimeoutError:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5.)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.close()
