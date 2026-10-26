"""Expose existing verified episode execution as a model-independent callback.

This is a wiring adapter, not another game loop. The frontend/RL registry,
real-time clocks, seat controllers, replay verifiers and rewards remain shared.
"""
from __future__ import annotations

import asyncio
from copy import copy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


def make_runner(args, pool=None, browser=None, *, opponent=None):
    """Return async(proxy, job) using the same execution methods as Sampler.

    No model/tokenizer is loaded. All student requests are delegated to tickets.
    Browser engines require the actual frontend URL and Playwright browser.
    ``opponent(kind, seed, ordinal, record)`` is an asynchronous callback that
    returns an action and policy metadata. The host owns providers/credentials.
    ``pool`` remains a positional alias only for an already callable adapter.
    """
    from jev_engine_episode_runner import EngineEpisodeRunner
    from jev_engine_registry import get_engine
    from jev_gameplay_reward_contract import default_config
    if opponent is not None and pool is not None:
        raise ValueError('specify only one opponent callback')
    opponent = opponent if opponent is not None else pool
    if opponent is not None and not callable(opponent):
        raise TypeError('opponent must be an asynchronous policy callback')

    class ExternalPolicyRunner(EngineEpisodeRunner):
        def __init__(self, proxy, job):
            self.proxy = proxy
            self.args = copy(args)
            # Keep the existing runner's controlled-seat/on-policy branch. This
            # sentinel is never requested: policy_action is overridden below.
            self.args.model_url = 'external-policy-callback'
            self.args.policy_version = job['policy_version']
            self.args.out = str(Path(args.out) / 'engine-audit' / uuid4().hex)
            self.args.reward_config = getattr(args, 'reward_config', None) or default_config([job['kind']])
            self.args.frontend = getattr(args, 'frontend', None) or getattr(args, 'frontend_url', None)
            self.browser = browser
            self.opponent_sem = asyncio.Semaphore(getattr(args, 'qwen_concurrency', 16))

        async def policy_action(self, record, episode_id, ordinal):
            return await self.proxy.policy_action(record, episode_id, ordinal)

        async def compute_record(self, operation, *values):
            if hasattr(self.proxy, 'compute_record'):
                return await self.proxy.compute_record(operation, *values)
            # Compatibility for standalone callback fixtures without a backend.
            return operation(*values), {}

        def journal(self, job, event, value):
            self.proxy.journal(job, event, value)

        async def qwen(self, kind, seed, ordinal, record):
            if opponent is None:
                raise ValueError('configured_opponent_provider_unavailable')
            async with self.opponent_sem:
                return await opponent(kind, seed, ordinal, record)

    async def run(proxy, job):
        if job['mode'] == 'qwen3.8-max' and opponent is None:
            raise ValueError('configured_opponent_provider_unavailable')
        runner = ExternalPolicyRunner(proxy, job)
        if get_engine(job['kind']).backend == 'browser' and (browser is None or not runner.args.frontend):
            raise ValueError('browser_rollout_requires_frontend_url_and_real_driver')
        return await runner.episode(job)

    return run


def create_app(*, storage_dir, frontend_url=None, pool=None, opponent=None, decision_timeout=90., max_active=16):
    """Standalone local service, or mount RolloutBackend in an existing host."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from jev_engine_rollout_backend import RolloutBackend, install
    from jev_engine_registry import engine_manifest
    from blink_arena.rollouts import Rollouts
    if pool is not None and opponent is not None:
        raise ValueError('specify only one opponent callback')
    rollouts = Rollouts(storage_dir, frontend_url, opponent=opponent if opponent is not None else pool,
                        decision_timeout=decision_timeout, max_active=max_active)
    backend = RolloutBackend(rollouts._episode, decision_timeout=decision_timeout,
                             storage_dir=storage_dir, max_active=max_active)
    rollouts.backend=backend

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await rollouts.close()

    app = FastAPI(lifespan=lifespan)
    app.state.rollout_backend = backend
    install(app, '', backend)

    @app.get('/api/engines')
    async def engines():
        return engine_manifest()

    return app


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-dir', required=True)
    parser.add_argument('--frontend-url')
    parser.add_argument('--port', type=int, default=45191)
    parser.add_argument('--decision-timeout', type=float, default=90.)
    parser.add_argument('--max-active', type=int, default=16)
    args = parser.parse_args()
    app = create_app(storage_dir=args.storage_dir, frontend_url=args.frontend_url,
                     decision_timeout=args.decision_timeout, max_active=args.max_active)
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
