"""Independent-package HTTP contract smoke; fixture actions are not model scores.

Starts only its own process with PYTHONPATH cleared. Generated audits are kept.
The diagnostic route exists only in this test process, never the shipped app.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx


LAUNCHER = r'''
import importlib.abc, os, sys
class NoTraining(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden=('transformers','torch','project_z','jev_gameplay_rl_v3',
                   'jev_frontend_game_audit','jev_recipe_full_benchmark','jev_full_quality')
        if any(fullname==x or fullname.startswith(x+'.') for x in forbidden):
            raise AssertionError('independent backend imported '+fullname)
sys.meta_path.insert(0,NoTraining())
from blink_arena.app import create_app
import uvicorn
port=int(os.environ['JEV_TEST_PORT'])
app=create_app(frontend=f'http://127.0.0.1:{port}', rollout_options={
    'decision_timeout':2.0,'max_active':16,'completed_cache_size':2,
    'completed_cache_bytes':2*1024*1024})
@app.get('/__contract')
async def contract():
    backend=app.state.rollouts.backend
    return {'cache':backend.cache_info() if backend else None,
        'origins':{name:getattr(sys.modules.get(name),'__file__',None) for name in (
            'jev_engine_registry','jev_engine_episode','jev_engine_episode_runner',
            'jev_engine_rollout_backend','jev_world_replay_hooks')},
        'pythonpath':os.environ.get('PYTHONPATH')}
app.router.routes.insert(0,app.router.routes.pop())
uvicorn.run(app,host='127.0.0.1',port=port,access_log=False)
'''


def fixture_answer(ticket, *, fail=False, action=None):
    values = ticket['candidate_values']
    if action is None:
        state = ticket['record']['state']
        landings = state['candidate_landings']
        choose = max if fail else min
        action = choose(values, key=lambda value: landings[value]['distance_to_center'])
    index = values.index(action)
    probabilities = [.4 / (len(values) - 1)] * len(values)
    probabilities[index] = .6
    return {'ticket_id': ticket['ticket_id'], 'request_token': ticket['request_token'],
        'policy_version': ticket['policy_version'], 'action': action,
        'policy': {'origin': 'student_model', 'forced': False,
            'candidate_values': values, 'old_probabilities': probabilities,
            'selected_index': index, 'sampling_epsilon': 0., 'sampling_temperature': 1.}}


def job(kind, trial=0):
    return {'episode_id': f'independent-fixture-{kind}-{trial}', 'game': kind,
        'seed': 973610000, 'group_id': f'independent-fixture-{kind}', 'trial': trial,
        'policy_version': 'fixture-not-model-v1', 'request_token': f'fixture-{kind}-{trial}',
        'mode': 'environment'}


async def checked(client, method, path, *, status=200, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == status, (method, path, response.status_code, response.text[:500])
    return response.json()


async def receipt(client, ident):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        response = await client.get(f'/api/v1/rollouts/{ident}/result')
        if response.status_code == 200:
            return response.json()
        assert response.status_code == 202, response.text
        await asyncio.sleep(.1)
    raise AssertionError('receipt deadline')


async def next_ticket(client, ident, after=-1):
    return await checked(client, 'GET', f'/api/v1/rollouts/{ident}/next-decision',
                         params={'after': after, 'timeout': 25})


async def complete_jump(client, trial):
    start = await checked(client, 'POST', '/api/v1/rollouts', status=201, json=job('jump_jump', trial))
    ident, after, captured = start['rollout_id'], -1, []
    while True:
        pending = await next_ticket(client, ident, after)
        ticket = pending.get('ticket')
        if ticket is None:
            assert pending.get('result_available'), pending
            break
        answer = fixture_answer(ticket, fail=trial > 0 and ticket['ordinal'] >= trial - 1)
        await checked(client, 'POST', f'/api/v1/rollouts/{ident}/answers', json=answer)
        captured.append((ticket, answer))
        after = ticket['sequence']
    result = await receipt(client, ident)
    assert result['status'] == 'complete' and result['replay_verified'], result
    assert result['counts_in_denominator'] and result['on_policy']
    assert len(result['trace']) == len(result['process_rewards']) == len(captured)
    for transition, (ticket, answer) in zip(result['trace'], captured, strict=True):
        assert transition['record'] == ticket['record']
        assert transition['action'] == answer['action']
        assert transition['policy']['old_probabilities'] == answer['policy']['old_probabilities']
    return result, captured[0]


async def browser_probe(client, kind):
    start = await checked(client, 'POST', '/api/v1/rollouts', status=201, json=job(kind))
    ident, after, frames = start['rollout_id'], -1, []
    for _ in range(2):
        pending = await next_ticket(client, ident, after)
        ticket = pending.get('ticket')
        assert ticket, pending
        assert not ticket['inference_pauses_environment']
        observation = ticket['record']['state']['observation']
        frames.append(observation['frame'])
        await asyncio.sleep(.25)
        # Exercise the current visible action, without a hidden route/answer.
        action = ticket['candidate_values'][0]
        await checked(client, 'POST', f'/api/v1/rollouts/{ident}/answers',
                      json=fixture_answer(ticket, action=action))
        after = ticket['sequence']
    pending = await next_ticket(client, ident, after)
    assert pending.get('ticket'), pending
    frames.append(pending['ticket']['record']['state']['observation']['frame'])
    assert frames[1] > frames[0] and frames[2] > frames[1], frames
    result = await checked(client, 'POST', f'/api/v1/rollouts/{ident}/cancel', json={'reason': 'fixture_finished'})
    assert result['counts_in_denominator'] and not result['on_policy']
    assert result['status'] == 'cancelled'
    return {'rollout_id': ident, 'frames': frames, 'status': result['status']}


class Process:
    def __init__(self, package, folder, port):
        self.package, self.folder, self.port = package, folder, port
        self.process = None
        self.generation = 0
        self.stream = None

    def start(self):
        self.generation += 1
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.update(JEV_DATA_DIR=str(self.folder / 'runtime'), JEV_TEST_PORT=str(self.port))
        self.stream = (self.folder / f'server-{self.generation}.log').open('x')
        self.process = subprocess.Popen([sys.executable, '-c', LAUNCHER], cwd=self.package,
            env=env, stdout=self.stream, stderr=subprocess.STDOUT)

    async def ready(self, client):
        for _ in range(200):
            assert self.process.poll() is None, 'isolated server exited; inspect its saved log'
            try:
                return await checked(client, 'GET', '/api/engines')
            except (httpx.ConnectError, httpx.ReadError):
                await asyncio.sleep(.1)
        raise AssertionError('independent server startup timeout')

    async def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            await asyncio.to_thread(self.process.wait, timeout=20)
        if self.stream:
            self.stream.close()


async def run(args, summary):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    process = Process(args.package_root.resolve(), args.out.resolve(), port)
    async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', timeout=35) as client:
        process.start()
        try:
            catalog = await process.ready(client)
            probe = await checked(client, 'GET', '/__contract')
            assert probe['cache'] is None and probe['pythonpath'] is None, probe
            assert not (args.out / 'runtime' / 'rollouts').exists(), 'ordinary browsing acquired RL storage'
            summary['initial_catalog'] = len(catalog['engines'])
            groups = await asyncio.gather(*(complete_jump(client, trial) for trial in range(4)))
            receipts = [item[0] for item in groups]
            assert sorted(row['outcome'] for row in receipts) == ['loss', 'loss', 'loss', 'win']
            summary['four_trials'] = [{'rollout_id': row['rollout_id'], 'outcome': row['outcome'],
                'terminal_utility': row['terminal_utility'], 'decisions': len(row['trace']),
                'replay_verified': row['replay_verified']} for row in receipts]
            probe = await checked(client, 'GET', '/__contract')
            assert probe['cache']['completed'] <= 2 and probe['cache']['serialized_bytes'] <= 2*1024*1024
            for name in ('jev_engine_episode', 'jev_engine_episode_runner', 'jev_engine_rollout_backend'):
                assert Path(probe['origins'][name]).is_relative_to(args.package_root.resolve())
            summary['bounded_cache'] = probe
            for row in receipts:
                assert await receipt(client, row['rollout_id']) == row
            ident = receipts[0]['rollout_id']
            duplicate = await checked(client, 'POST', '/api/v1/rollouts', status=201, json=job('jump_jump'))
            assert duplicate['duplicate'] and duplicate['rollout_id'] == ident
            await checked(client, 'POST', '/api/v1/rollouts', status=409, json={**job('jump_jump'), 'seed': 973610001})
            await checked(client, 'POST', f'/api/v1/rollouts/{ident}/answers', json=groups[0][1][1])
            snake_job = {**job('snake_navigation'), 'seed': 42}
            start = await checked(client, 'POST', '/api/v1/rollouts', status=201, json=snake_job)
            sid = start['rollout_id']; ticket = (await next_ticket(client, sid))['ticket']
            await checked(client, 'POST', f'/api/v1/rollouts/{sid}/answers', json=fixture_answer(ticket, action='left'))
            second = (await next_ticket(client, sid, ticket['sequence']))['ticket']
            assert second and not second['inference_pauses_environment']
            timed = await receipt(client, sid)
            assert timed['replay_verified'] and timed['counts_in_denominator'] and not timed['on_policy']
            assert timed['final_state']['elapsed'] > timed['initial_state']['elapsed'] + 1.8
            assert timed['replay_events'][-1]['action_applied'] is False
            await checked(client, 'POST', f'/api/v1/rollouts/{sid}/answers', status=409,
                          json=fixture_answer(second, action=second['candidate_values'][0]))
            summary['realtime_timeout'] = {'rollout_id': sid, 'elapsed': timed['final_state']['elapsed'],
                'status': timed['status'], 'replay_verified': timed['replay_verified'],
                'trainable_decisions': timed['trainable_decisions']}
            summary['browser'] = [await browser_probe(client, kind)
                                  for kind in ('mario_platformer', 'terraria_survival')]
            history = await checked(client, 'GET', '/api/v1/rollouts', params={'limit': 2})
            assert history['total'] == 7 and history['next_cursor'] is not None, history
            summary['history_total'] = history['total']
            await process.stop()
            process.start()
            await process.ready(client)  # Preserve the original owner cookie.
            for row in receipts:
                assert await receipt(client, row['rollout_id']) == row
            duplicate = await checked(client, 'POST', '/api/v1/rollouts', status=201, json=job('jump_jump'))
            assert duplicate['duplicate'] and duplicate['rollout_id'] == ident
            await checked(client, 'POST', f'/api/v1/rollouts/{ident}/answers', json=groups[0][1][1])
            async with httpx.AsyncClient(base_url=client.base_url) as stranger:
                await checked(stranger, 'GET', '/api/engines')
                await checked(stranger, 'GET', f'/api/v1/rollouts/{ident}/result', status=404)
            summary['restart'] = {'receipts_preserved': 4, 'duplicate_start_preserved': True,
                'answer_idempotence_preserved': True, 'other_owner_rejected': True}
            summary['passed'] = True
        finally:
            await process.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    summary = {'fixture_only': True, 'model_service_called': False, 'passed': False}
    try:
        asyncio.run(run(args, summary))
    finally:
        summary['seconds'] = round(time.monotonic() - started, 3)
        (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
