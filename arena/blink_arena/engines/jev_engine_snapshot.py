"""Fast independent snapshots of trusted in-memory engine values.

No external pickle bytes are accepted. The only decoder input is the encoder's
immediate output in this function. Keep this boundary limited to private engine
state/audit arguments; do not use it as a file or RPC deserializer.
"""
import pickle


def snapshot(value):
    return pickle.loads(pickle.dumps(value, protocol=5))


CONTROL_CLOCK_MODES = ('realtime', 'request_pause')
REQUEST_PAUSE_REVISION = 'jev.rl-request-pause.v1'


def control_clock_mode(value='realtime'):
    if not isinstance(value, str) or value not in CONTROL_CLOCK_MODES:
        raise ValueError('invalid_control_clock_mode')
    return value


def _request_pause_text(value):
    """Rewrite clock wording only; numerical facts/actions/candidates stay intact."""
    if isinstance(value, str):
        for old, new in (
            ('首个操作开始计时，之后重力在思考、等待网络和没有新输入时持续生效。', '首个操作开始计时，主动仿真期间重力持续生效；本RL请求等待期间冻结。'),
            ('操作和推理期间仍会自然下落，请提前决定。', '意图机械执行期间仍自然下落；本RL请求等待期间冻结。'),
            ('推理、等待网络和没有输入时都沿当前方向继续走，不会暂停。', '主动仿真且没有新输入时沿当前方向前进；本RL捕获、准备和请求等待期间暂停。'),
            ('推理期间仍前进，提前转弯', '主动仿真期间仍前进，本RL请求等待暂停；按捕获状态选择转向'),
            ('回复到达时蛇可能已向前多格，动作才开始生效。', '本RL请求等待不会移动蛇，回复应用后按原移动时钟继续。'),
            ('发车后等待模型时物理继续。', '发车后本RL请求等待时物理暂停；主动仿真继续。'),
            ('墙钟赛时', '主动仿真赛时'),
            ('发车后松油门、停车和等模型仍正常计时', '发车后主动仿真中的松油门和停车正常计时，本RL请求等待除外'),
            ('推理等待时世界继续运行、按键松开，模型看到的是请求发起时的观测。', '本RL请求等待时世界冻结，模型看到捕获观测；回复后按原物理执行。'),
            ('实时推理期间方向松开但物理继续', '主动仿真松开方向时物理继续，本RL请求等待期间冻结'),
            ('下一次推理时原地坠落', '后续主动松键仿真中原地坠落（本RL请求等待暂停）'),
            ('下一次推理等待时原地落坑', '后续主动松键仿真中原地落坑（本RL请求等待暂停）'),
            ('假设API等待1秒', '假设主动推进1秒'),
        ):
            value = value.replace(old, new)
        return value
    if isinstance(value, dict):
        return {key: _request_pause_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_request_pause_text(item) for item in value]
    return value


def control_record(record, mode):
    mode = control_clock_mode(mode)
    if mode == 'realtime':
        return record
    # This is the actual model input, not a receipt-only audit annotation.
    record = _request_pause_text(snapshot(record))
    state = record['state']
    observed = state.get('observation', state)
    timing = observed.setdefault('timing', {})
    timing.update(control_clock_mode=mode, mode='request_paused_simulation',
        continues_during_inference=False, request_wait_advances_world=False)
    record['questions']['decision']['instructions'] = (
        '本RL对局在捕获候选、准备输入与等待模型期间暂停世界；回复应用后按原物理执行。'
        '等待本身不推进重力、敌人或仿真期限。下述延迟情景仅表示主动推进相同仿真时长的反事实，'
        '不表示本次推理期间会发生；HTTP超时仍按墙钟计为失败。\n'
        + record['questions']['decision']['instructions'])
    return record


def simulation_seconds(state):
    if 'elapsed' in state:
        return float(state['elapsed'])
    return float(state['frame']) / 60.


def pause_proof(mode, before, arrival, waiting):
    mode = control_clock_mode(mode)
    if mode == 'realtime':
        return {}
    begin, end = simulation_seconds(before), simulation_seconds(arrival)
    if begin != end:
        raise ValueError('paused_request_advanced_simulation')
    return {'control_clock_mode': mode, 'simulation_wait_seconds': 0.,
        'request_wall_seconds': waiting, 'request_clock': {
            'revision': REQUEST_PAUSE_REVISION, 'control_clock_mode': mode,
            'request_wall_seconds': waiting, 'simulation_wait_seconds': 0.,
            'before_simulation_seconds': begin, 'arrival_simulation_seconds': end,
            'paused_simulation_delta_seconds': end-begin,
            'pause_released': True, 'resumed_without_catchup': True}}


def replay_wait(event, mode):
    mode = control_clock_mode(mode)
    if mode == 'realtime':
        return event['waiting_seconds']
    expected = pause_proof(mode, event['before_state'], event['arrival_state'], event['waiting_seconds'])
    if any(event.get(key) != value for key, value in expected.items()):
        raise ValueError('paused_request_clock_proof_mismatch')
    return 0.
