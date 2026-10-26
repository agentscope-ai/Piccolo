"""Explicit, opt-in distillation clock; default gameplay remains realtime."""
import copy
import math
import random

PAUSED_SUFFIX = '+inference-paused-v1'
SIMULATED_REVISION = 'simulated-wait-2-4s-v1'
SIMULATED_GAMES = {'snake_navigation', 'mario_platformer', 'terraria_survival'}
SIMULATED_NOTICE = (
    '\n本局采用实时模拟等待：每次观察后、你的动作到达前，世界独立均匀随机推进2–4秒'
    '（60Hz的120–240帧），与模型实际回复耗时无关；只公布范围，不提前公布本次时长。'
    '这段时间沿用游戏原生等待行为：蛇沿当前方向移动，马里奥和泰拉瑞亚松开按键，'
    '重力、敌人和已选择的持续意图仍按原规则推进。请对整个2–4秒窗口内的安全性作决策；'
    '动作到达时重新校验，等待期间死亡或动作失效照常计入结果。动作执行阶段物理正常推进。')


def simulated(job):
    value = job.get('inference_simulated_wait', False)
    if type(value) is not bool:
        raise ValueError('inference_simulated_wait_must_be_boolean')
    if value and (job.get('inference_world_paused', False) or job.get('kind') not in SIMULATED_GAMES):
        raise ValueError('invalid_simulated_wait_job')
    return value


def frozen_wait(job):
    return paused(job) or simulated(job)


def wait_seconds(job, ordinal, wall_seconds):
    if simulated(job):
        # Independent of wall time, retries, teacher identity, and engine RNG.
        rng = random.Random(f'{SIMULATED_REVISION}/{job["kind"]}/{job["seed"]}/{ordinal}')
        return rng.randint(120, 240) / 60.
    return 0. if paused(job) else wall_seconds


def simulated_marker():
    return {'mode': 'realtime', 'revision': SIMULATED_REVISION,
            'clock_source': 'simulated_delay', 'waiting_advances_world': True,
            'execution_advances_world': True, 'actual_inference_latency_drives_world': False,
            'waiting_distribution': 'uniform_integer_frames', 'waiting_frames': [120, 240],
            'frames_per_second': 60, 'waiting_seconds_bounds': [2, 4]}


def observation_for_clock(observation, job):
    if not simulated(job):
        return observation
    observation = copy.deepcopy(observation)
    if isinstance(observation.get('timing'), dict):
        observation['timing'].update(mode='realtime', clock_contract='realtime-v1',
            inference_world_paused=False, clock_source='simulated_delay',
            note='实时模拟等待：每次动作到达前独立推进2–4秒，实际接口延迟不影响该时长。')
    return observation


def paused(job):
    value = job.get('inference_world_paused', False)
    if type(value) is not bool:
        raise ValueError('inference_world_paused_must_be_boolean')
    return value


def contract(job, realtime_contract):
    return realtime_contract + ('+' + SIMULATED_REVISION if simulated(job) else
                                PAUSED_SUFFIX if paused(job) else '')


def policy_timeout(job, realtime_default):
    """A longer wall-clock retry budget is opt-in and confined to paused jobs."""
    if not frozen_wait(job):
        return realtime_default
    value = job.get('simulated_policy_timeout_seconds' if simulated(job) else
                    'paused_policy_timeout_seconds', realtime_default)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 3600:
        raise ValueError('invalid_paused_policy_timeout_seconds')
    return float(value)


def record_for_clock(record, job):
    if simulated(job):
        record = copy.deepcopy(record)
        record['state']['sampling_clock'] = simulated_marker()
        if isinstance(record['state'].get('timing'), dict):
            record['state']['timing'].update(mode='realtime_simulated_delay',
                clock_source='simulated_delay', actual_inference_latency_drives_world=False)
        record['questions']['decision']['instructions'] += SIMULATED_NOTICE
        return record
    if not paused(job):
        return record
    record = copy.deepcopy(record)
    record['state']['sampling_clock'] = {
        'mode': 'inference_paused', 'revision': 'inference-paused-v1',
        'waiting_advances_world': False, 'execution_advances_world': True}
    record['questions']['decision']['instructions'] += (
        '\n本局时钟约定：构造观察和等待模型回复期间世界暂停；动作执行期间物理正常推进。'
        '上文及候选中的推理延迟风险仅为实时模式的反事实预测，本局等待延迟取0；'
        '仍须考虑动作执行中的碰撞、重力、敌人和资源变化。')
    return record


def verify_clock(job, extra, realtime_contract):
    expected = contract(job, realtime_contract)
    if extra.get('clock_contract') != expected or extra.get('inference_world_paused', False) != paused(job):
        raise ValueError('inference_clock_contract_mismatch')
    if extra.get('inference_simulated_wait', False) != simulated(job):
        raise ValueError('simulated_inference_clock_contract_mismatch')
    for event in extra['replay_events']:
        if event.get('clock_contract') != expected:
            raise ValueError('inference_clock_event_mismatch')
        if simulated(job) and not event.get('no_request'):
            seconds = wait_seconds(job, event['ordinal'], 0)
            if (extra.get('inference_simulated_wait') is not True or
                    event.get('waiting_seconds') != seconds or
                    event.get('wall_waiting_seconds', -1) < 0 or
                    event.get('sampling_clock_source') != SIMULATED_REVISION):
                raise ValueError('simulated_inference_wait_did_not_replay')
            before, arrival = event['before_state'], event['arrival_state']
            if 'frame' in before:
                advanced = arrival['frame'] - before['frame']
                terminal = bool(arrival.get('outcome') or arrival.get('wins', 0) > before.get('wins', 0))
                if not 0 <= advanced <= round(seconds * 60) or (not terminal and advanced != round(seconds * 60)):
                    raise ValueError('simulated_inference_frames_did_not_replay')
        if paused(job) and not event.get('no_request'):
            if event.get('waiting_seconds') != 0 or event.get('wall_waiting_seconds', -1) < 0:
                raise ValueError('paused_inference_wait_must_not_advance_world')
