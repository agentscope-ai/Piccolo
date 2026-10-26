"""Public collision geometry; enumerate every gap without selecting a route.

This module receives racing.public(world), never an internal world. Lateral
times are explicitly conditional constant-speed/constant-curvature geometry,
not a second race simulator or a prediction of network/driver behavior.
"""
import math

REVISION = 'visible-obstacle-geometry-v1'
from jev_racing_game import CAR_WIDTH, CONTACT_HALF_LENGTH, ROAD_CENTER_LIMIT
DT = .05
INPUT_HORIZON = 4.
CLEARANCE_MARGIN = .1
STEERING = {'hard_left': -1., 'left': -.4, 'straight': 0., 'right': .4, 'hard_right': 1.}


def _reject_private(value):
    if isinstance(value, dict):
        if any(str(key).startswith('_') for key in value):
            raise ValueError('geometry requires public state without private fields')
        for item in value.values():
            _reject_private(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private(item)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('geometry expects finite public numbers')
    return float(value)


def _rounded(value):
    return None if value is None else round(value, 4)


def _allowed(x, blocked):
    return -ROAD_CENTER_LIMIT <= x <= ROAD_CENTER_LIMIT and not any(lo < x < hi for lo, hi in blocked)


def _merge(intervals):
    merged = []
    for lo, hi in sorted(intervals):
        # A touching pair has one exact tangent point, not a positive-width gap.
        if merged and lo < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def _free_intervals(blocked):
    result, cursor = [], -ROAD_CENTER_LIMIT
    for lo, hi in blocked:
        if hi < cursor or lo > ROAD_CENTER_LIMIT:
            continue
        if lo >= cursor:
            upper = min(lo, ROAD_CENTER_LIMIT)
            if upper > cursor or _allowed(cursor, blocked):
                result.append([cursor, upper])
        cursor = max(cursor, hi)
        if cursor > ROAD_CENTER_LIMIT:
            break
    if cursor <= ROAD_CENTER_LIMIT and (cursor < ROAD_CENTER_LIMIT or _allowed(cursor, blocked)):
        result.append([cursor, ROAD_CENTER_LIMIT])
    return result


def _conditional_lateral_paths(state):
    """The existing 50 ms tire-response recurrence with speed/curve held constant."""
    speed, x = _number(state['speed']), _number(state['x'])
    velocity = _number(state['lateral_velocity'])
    z = _number(state['z'])
    section = next((s for s in state['visible_track'] if s['start'] <= z < s['end']), None)
    if section is None:
        raise ValueError('public current road section is required')
    curve, grip = _number(section['curve']), _number(section['grip_speed'])
    drift = -math.copysign(max(0., speed-grip)*.65, curve) if curve else 0.
    paths = {}
    for name, steering in STEERING.items():
        points = [x]
        lateral = velocity
        target = steering*min(3.6, .22*speed)
        for _ in range(round(INPUT_HORIZON/DT)):
            lateral += (target-lateral)*min(1., 4.*DT)
            if speed <= 1e-9:
                lateral = 0.
            points.append(points[-1]+(lateral+drift)*DT)
        paths[name] = points
    return paths


def _gap_facts(lo, hi, x, blocked, paths, entry_time, exit_time):
    near = min(hi, max(lo, x))
    safe_lo, safe_hi = lo+CLEARANCE_MARGIN, hi-CLEARANCE_MARGIN
    interior = [safe_lo, safe_hi] if safe_lo <= safe_hi else None
    estimates = {}
    for action, points in paths.items():
        def member(value):
            return lo <= value <= hi and _allowed(value, blocked)
        entered = next((index for index, value in enumerate(points) if member(value)), None)
        margin_entered = (next((index for index, value in enumerate(points)
                               if interior[0] <= value <= interior[1]), None) if interior else None)
        contact_tick = math.ceil(entry_time/DT-1e-9) if entry_time is not None else None
        exit_tick = math.ceil(exit_time/DT-1e-9) if exit_time is not None else None
        covers_band = (all(member(value) for value in points[contact_tick:exit_tick+1])
                       if contact_tick is not None and exit_tick is not None and exit_tick < len(points) else None)
        estimates[action] = {
            'first_entry_seconds': _rounded(entered*DT) if entered is not None else None,
            'first_entry_with_margin_seconds': _rounded(margin_entered*DT) if margin_entered is not None else None,
            'x_at_contact_entry': _rounded(points[contact_tick]) if contact_tick is not None and contact_tick < len(points) else None,
            'inside_gap_through_contact_band': covers_band,
            'leaves_road_before_gap_entry': (any(abs(value) > ROAD_CENTER_LIMIT for value in points[:entered+1])
                                           if entered is not None else None),
        }
    return {
        'center_x_interval': [_rounded(lo), _rounded(hi)], 'width_m': _rounded(hi-lo),
        'lower_inclusive': _allowed(lo, blocked), 'upper_inclusive': _allowed(hi, blocked),
        'zero_width_tangent_only': hi == lo,
        'required_lateral_shift_m': _rounded(near-x),
        'required_lateral_distance_m': _rounded(abs(near-x)),
        'margin_m': CLEARANCE_MARGIN,
        'center_x_interval_with_margin': list(map(_rounded, interior)) if interior else None,
        'conditional_steering_entry_estimates': estimates,
    }


def visible_obstacle_geometry(public_state):
    """Return all visible gaps and conditional reach times; no preferred action.

    Break overlapping longitudinal bands into slices instead of taking their
    transitive union: obstacles at different z do not all block x simultaneously.
    Already-contacted obstacles are excluded because the engine damages once.
    """
    _reject_private(public_state)
    z, x, speed = (_number(public_state[key]) for key in ('z', 'x', 'speed'))
    if speed < 0:
        raise ValueError('public speed must be nonnegative')
    visibility = _number(public_state['visible_distance'])
    contacts = set(public_state.get('contacts', []))
    obstacles = []
    for obstacle in public_state['visible_obstacles']:
        oz, ox, width = (_number(obstacle[key]) for key in ('z', 'x', 'width'))
        if width <= 0:
            raise ValueError('obstacle width must be positive')
        if oz > z+visibility or oz < z-4:
            raise ValueError('obstacle exceeds public visibility')
        if obstacle['id'] in contacts or oz+CONTACT_HALF_LENGTH < z:
            continue
        half = (width+CAR_WIDTH)/2
        obstacles.append({
            'id': obstacle['id'], 'z': oz, 'x': ox,
            'longitudinal_contact_band': [oz-CONTACT_HALF_LENGTH, oz+CONTACT_HALF_LENGTH],
            'blocked_center_x_open_interval': [ox-half, ox+half],
            'current_lateral_clearance_m': _rounded(abs(x-ox)-half),
            'lateral_overlap_now': abs(x-ox) < half,
            'currently_in_longitudinal_contact_band': oz-CONTACT_HALF_LENGTH <= z <= oz+CONTACT_HALF_LENGTH,
        })
    obstacles.sort(key=lambda item: (item['z'], item['id']))
    paths = _conditional_lateral_paths(public_state)
    cuts = sorted({max(z, endpoint) for item in obstacles for endpoint in item['longitudinal_contact_band']})
    zones = []
    slices = list(zip(cuts, cuts[1:]))
    if any(item['longitudinal_contact_band'][1] == z for item in obstacles):
        slices.insert(0, (z, z))
    for lo, hi in slices:
        mid = (lo+hi)/2
        active = [item for item in obstacles if item['longitudinal_contact_band'][0] <= mid <= item['longitudinal_contact_band'][1]]
        if not active:
            continue
        blocked = _merge([item['blocked_center_x_open_interval'] for item in active])
        distance = max(0., lo-z)
        entry_time = distance/speed if speed else 0. if not distance else None
        exit_time = max(0., hi-z)/speed if speed else None
        zones.append({
            'z_interval': [_rounded(lo), _rounded(hi)], 'obstacle_ids': [item['id'] for item in active],
            'distance_to_contact_entry_m': _rounded(distance),
            'at_current_speed_entry_seconds': _rounded(entry_time),
            'at_current_speed_exit_seconds': _rounded(exit_time),
            'blocked_center_x_open_intervals': [[_rounded(a), _rounded(b)] for a, b in blocked],
            'current_center_is_clear': _allowed(x, blocked),
            'free_center_intervals': [_gap_facts(a, b, x, blocked, paths, entry_time, exit_time)
                                      for a, b in _free_intervals(blocked)],
        })
    return {
        'revision': REVISION, 'information_source': 'current_public_observation_only',
        'geometry_kind': 'deterministic_visible_collision_geometry',
        'car_width_m': CAR_WIDTH, 'obstacle_longitudinal_contact_half_length_m': CONTACT_HALF_LENGTH,
        'allowed_car_center_x': [-ROAD_CENTER_LIMIT, ROAD_CENTER_LIMIT],
        'road_edge_margin_m': {'left': _rounded(x+ROAD_CENTER_LIMIT), 'right': _rounded(ROAD_CENTER_LIMIT-x)},
        'boundary_rule': '横向严格重叠才碰撞；恰好相切合法但零余量。纵向进入障碍中心前后1.5米会检查碰撞。',
        'conditional_estimate': {
            'kind': 'constant_speed_current_curve_lateral_geometry_not_monte_carlo',
            'longitudinal_speed_mps': speed, 'dt_seconds': DT, 'horizon_seconds': INPUT_HORIZON,
            'note': '横移时间假设立即打方向、当前车速与当前曲率恒定；不含响应延迟、油门刹车、后续路段变化或其他障碍影响。null表示静止无法到达或4秒窗口内未达到/未覆盖，不代表真实动作不可能；实际动作看候选物理投影。列出所有空隙和5档方向，不选择路线。',
        },
        'obstacles': obstacles, 'contact_zones': zones,
    }
