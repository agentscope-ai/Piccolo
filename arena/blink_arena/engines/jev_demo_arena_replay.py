"""Read-only, allowlisted Arena replay export for the existing static asset route.

This process never imports the server, calls a model, or writes an Arena archive.
Board frames are derived only from archived actions and published only when the
entire reconstructed final state matches the archived final state exactly.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import json
import math
import os
from pathlib import Path
import re
import time

try:
    from . import jev_demo_games as board
except ImportError:
    import jev_demo_games as board

REVISION = 'jev-arena-replay-v1'
PREFIX = 'window.JevArenaReplayArchive='
from blink_arena.paths import REPO as BASE, WEB as DEFAULT_FRONT, DATA
DEFAULT_WORLD_CACHE = DATA / "world-replays"
DEFAULT_RAW_OUTPUT = DATA / "arena-replay.json"

# Display state only. Rules, prompts, RNG internals, input records, model
# responses and per-candidate distributions are deliberately absent. Native
# game histories are retained because the table renderer uses played cards.
STATE_KEYS = set('''kind game n board turn winner edges boxes passes steps score
outcome outcome_label event body direction food obstacles walls targets box_ids
position target width height gain holds last_landing piece lines seed hand hands
bottom landlord last last_play leader opponent_counts other_hand_counts pot
street stacks to_call opponent_last own_hand own_stack player_stack
player_last_action card_encoding equity_estimate seen opponent_seen showdown
opponent_hand player_seen stake round scores turn_points last_roll own_last_roll
own_score player_last_roll player_score cash dice names prices owners levels
positions phase name opponent_max_rent current_player players bids rounds
last_move points prize remaining cards dealer handoff all_dice stats player map
enemies plants coins powerups goal_x progress collected powerups_collected
decisions frame equipment wins deaths known_goal last_known_surface health z x
speed lateral_velocity steering_input pedal elapsed race_started contacts
last_action execution_status collision_count offroad_seconds model_decisions
active_action active_controller failure_reason visible_track visible_obstacles
finish_distance time_limit remaining_distance remaining_time visible_distance
max_speed steering_pulse_remaining steering_pulse_duration history
execution_trace recent_positions recent_player_positions recent_player_tiles
replay_scene engine_revision pending_direction started move_clock move_interval
food_target target_food max_steps seconds_to_next_move collision_cell
active next_piece piece_id rotation phase gravity_clock gravity_interval lock_clock
lock_delay clearing_rows clear_clock clear_delay line_target piece_limit
intent pending_intent placement_plan input_clock simulation_clock simulation_ticks
seconds_to_next_fall seconds_to_lock ghost_y ghost_cells active_cells'''.split())
STATE_KEYS.update('''check fen initial_fen moves_uci opening_plies initialization
castling_rights en_passant_square halfmove_clock fullmove_number termination result
max_plies claim'''.split())
NESTED_KEYS = STATE_KEYS | set('''action actor automatic aim armor armorMul boss
box box_id brake car_length car_width center chest coast contact_half_length
controller curve dirt dt duration emerged end facing gem gems goal grip_speed
hard_left hard_right hp id invulnerable kill left legend level max_hp mode move
obstacle_length on_ground ore origin pedals pick pickMul pipe_x plies potArm
potAtk pts pulse_left pulse_right respawning revision right road_center_limit
road_half_width shield stand start status steering straight sword swordMul tile
tile_size tiles version vx vy y frames surface w h inv maxhp lv face ground agent type
atk digT digP column target_column target_rotation cells decision reason strategy_origin execution_origin expires_on absolute_time_limit'''.split())
NESTED_KEYS.update('''utility terminal_reward progress native_progress elapsed_seconds
time_limit time_scale_seconds time_source completed time_tiebreak comparison_key
scoring_revision'''.split())
NESTED_KEYS.update('uci san intended_uci intended_san policy_decision_class execution_class rule_takeover source generator_revision opening_uci opening_is_policy_trajectory'.split())
MATCH_KEYS = 'ordinal kind seed a b leg a_side mode status score_a winner winner_side outcome_a native_outcome steps seats seconds finished_at'.split()
RESULT_KEYS = 'outcome score score_label higher_is_better comparison_key terminal budget_exhausted natural_success winner steps status failure_reason time_score'.split()
STABILITY_KEYS = 'agreement_rate probability_stability mean_probability_variance mean_js_distance probability_complete unanimous repeat_count'.split()
EXECUTION_KEYS = 'ordinal action observation_frame execution_frame inference_frames latency_seconds status reason after_frame pre_decision_seconds waiting_seconds action_applied post_action_seconds idle_seconds no_request no_request_reason policy_request strategy_origin execution_origin observation_piece_id arrival_piece_id'.split()
SAFE_ID = re.compile(r'(?!.*\.\.)[A-Za-z0-9_][A-Za-z0-9_.-]*\Z')
COORDINATE = re.compile(r'-?\d+(?:,\d+)?\Z|[HV]\d+,\d+\Z')


def scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def display_value(value, depth=0):
    """Retain only recognized nested game fields and coordinate-keyed maps."""
    if depth > 12:
        return None
    if isinstance(value, dict):
        return {str(k): display_value(v, depth+1) for k, v in value.items()
                if str(k) in NESTED_KEYS or COORDINATE.fullmatch(str(k))}
    if isinstance(value, (list, tuple)):
        return [display_value(v, depth+1) for v in value]
    return scalar(value)


def state(value, kind):
    if not isinstance(value, dict):
        return None
    return {**{k: display_value(v) for k, v in value.items() if k in STATE_KEYS}, 'kind': kind}


def fields(value, keys):
    if not isinstance(value, dict):
        return {}
    return {k: display_value(value[k]) for k in keys if k in value}


def decision(item, index):
    result = {'index': index, **fields(item, ['player', 'action', 'latency_seconds', 'origin', 'model_call'])}
    result['actor'] = scalar(item.get('actor', item.get('side')))
    stability = fields(item.get('decision_stability'), STABILITY_KEYS)
    if stability:
        result['stability'] = stability
    return result


def board_frames(row):
    """Fail closed: no frames unless all archived actions and final state agree."""
    if row['kind'] not in board.GAMES or not row.get('initial_state') or not row.get('final_state'):
        return None
    game = copy.deepcopy(row['initial_state'])
    frames = []
    try:
        for item in row.get('trace', []):
            if item.get('side') != game.get('turn'):
                return None
            game = board.move(game, item['action'])
            frames.append(state(game, row['kind']))
        if game != row['final_state']:
            return None
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return frames


def stream(row, ident, participants, participant=None, world=None):
    kind = row['kind']
    output = {'id': ident, 'kind': kind, 'participant': participant,
              'participants': participants, 'recording': 'action_log', 'missing_frames': True,
              'initial_state': state(row.get('initial_state'), kind),
              'final_state': state(row.get('final_state'), kind),
              'result': fields(row, RESULT_KEYS), 'steps': []}
    frames = board_frames(row)
    events = row.get('replay_events') or []
    execution = row.get('execution_receipts') or []
    traces = row.get('trace') or []
    if world is not None:
        output['initial_state'] = state(world['initial_state'], kind)
        output['final_state'] = state(world['final_state'], kind)
        for index, recovered in enumerate(world['steps']):
            item = decision(traces[index], index)
            item['before_state'] = state(recovered['before_state'], kind)
            item['arrival_state'] = state(recovered['arrival_state'], kind)
            item['state'] = state(recovered['after_state'], kind)
            item['execution'] = fields(execution[index], EXECUTION_KEYS)
            # Each delta is relative to the same arrival_state, not the prior
            # frame. Arrays and replay_scene are complete replacement values.
            item['execution_frames_delta'] = True
            item['execution_frames'] = [
                {key: value for key, value in state(frame, kind).items()
                 if item['arrival_state'].get(key) != value}
                for frame in recovered.get('execution_frames', [])]
            output['steps'].append(item)
        output.update(recording='reconstructed_verified', missing_frames=False,
                      reconstruction=world['revision'])
        return output
    try:
        from .jev_demo_arena_replay_native import native_frames, partial_doudizhu
    except ImportError:
        from jev_demo_arena_replay_native import native_frames, partial_doudizhu
    try:
        recovered = native_frames(row)
    except (ValueError, KeyError, TypeError, IndexError, ImportError):
        recovered = None
    if recovered is not None:
        for index, receipt in enumerate(recovered):
            item = decision(receipt, index)
            item['before_state'] = state(receipt['before_state'], kind)
            item['state'] = state(receipt['after_state'], kind)
            if 'execution_frames' in receipt:
                item['execution_frames'] = [state(frame, kind) for frame in receipt['execution_frames']]
                item['execution'] = fields(receipt.get('execution'), EXECUTION_KEYS)
            output['steps'].append(item)
        output['recording'] = 'reconstructed_verified'
        output['missing_frames'] = False
        output['reconstruction'] = 'original-native-engine-actions-v1'
        return output
    try:
        partial = partial_doudizhu(row)
    except (ValueError, KeyError, TypeError, IndexError, ImportError):
        partial = None
    if partial is not None:
        output['initial_state'] = state(partial['initial_state'], kind)
        for index, receipt in enumerate(partial['steps']):
            item = decision(receipt, index)
            item['before_state'] = state(receipt['before_state'], kind)
            if 'after_state' in receipt:
                item['state'] = state(receipt['after_state'], kind)
            output['steps'].append(item)
        output.update(recording='reconstructed_observation_verified', partial=True,
                      reconstruction='original-native-observation-prefix-v1')
        return output
    # Real-time engines include discarded/failed replies as well as successful
    # decisions. The authoritative clock receipts determine displayed steps.
    if kind in ('racing_sprint', 'snake_navigation', 'tetris_placement') and events:
        model_index = 0
        for index, event in enumerate(events):
            matching = traces[model_index] if model_index < len(traces) else None
            item = decision(matching, index) if matching and matching.get('action') == event.get('action') else {'index': index}
            if matching and matching.get('action') == event.get('action'):
                model_index += 1
            item['action'] = scalar(event.get('action'))
            item['player'] = participant
            item['execution'] = fields(event, EXECUTION_KEYS)
            for source, target in [('before_state', 'before_state'), ('arrival_state', 'observation'), ('after_state', 'state')]:
                if isinstance(event.get(source), dict):
                    item[target] = state(event[source], kind)
            if kind in ('snake_navigation', 'tetris_placement') and item.get('before_state') and item.get('state'):
                # Retain each actually executed cell movement, including those
                # during model latency. Never re-run archived actions as steps.
                start = item['before_state'].get('elapsed', 0.)
                base = {key: value for key, value in item['before_state'].items() if key != 'execution_trace'}
                snapshots = [base]
                for source in ('arrival_state', 'after_state'):
                    for frame in (event.get(source, {}).get('execution_trace') or {}).get('frames', []):
                        snapshot = state({**base, **frame}, kind)
                        if frame.get('elapsed', -1) >= start and snapshot != snapshots[-1]:
                            snapshots.append(snapshot)
                snapshots.sort(key=lambda frame: frame.get('elapsed', 0.))
                end = {key: value for key, value in item['state'].items() if key != 'execution_trace'}
                if snapshots[-1] != end:
                    snapshots.append(end)
                item['execution_frames'] = snapshots
            output['steps'].append(item)
        output['recording'] = 'state_snapshots'
        output['missing_frames'] = any('state' not in item for item in output['steps'])
        if kind == 'tetris_placement':
            # A bounded snapshot ring cannot prove a complete realtime replay.
            # Only tetris_frames() above marks clock-verified frames complete.
            output.update(partial=True, missing_frames=True)
        return output
    for index, receipt in enumerate(traces):
        item = decision(receipt, index)
        observation = ((receipt.get('input') or {}).get('state') or {}).get('observation')
        if isinstance(observation, dict):
            item['observation'] = state(observation, kind)
            output['recording'] = 'decision_snapshots'
        if frames is not None:
            item['state'] = frames[index]
            item['before_state'] = frames[index-1] if index else output['initial_state']
        if index < len(execution):
            item['execution'] = fields(execution[index], EXECUTION_KEYS)
        output['steps'].append(item)
    if frames is not None:
        output['recording'] = 'reconstructed_verified'
        output['missing_frames'] = False
    return output


def read(path):
    return json.loads(path.read_text())


def stamp(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except FileNotFoundError:
        return None


class Exporter:
    def __init__(self, root, output, world_cache=DEFAULT_WORLD_CACHE, raw_output=None):
        self.root, self.output = Path(root), Path(output)
        self.world_cache = Path(world_cache)
        self.raw_output = Path(raw_output) if raw_output is not None else (
            DEFAULT_RAW_OUTPUT if self.output == DEFAULT_FRONT/'playground/visible-control.js'
            else self.output.with_suffix('.raw.json'))
        self.previous = None
        self.cache = {}

    def _cached(self, path, project, dependency=None):
        mark = stamp(path)
        if mark is None:
            return None
        if dependency is not None:
            mark = (mark, stamp(dependency))
        key = str(path)
        cached = self.cache.get(key)
        if cached is None or cached[0] != mark:
            value = project(read(path))
            self.cache[key] = mark, value
        return self.cache[key][1]

    def export(self, run_id=None, *, data_only=False):
        latest = read(self.root/'latest.json')
        run_id = run_id or latest.get('run_id')
        if run_id is None and data_only:
            return None
        if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
            raise ValueError('invalid_run_id')
        folder = self.root/run_id
        paths = [self.root/'latest.json', folder/'plan.json', folder/'status.json']
        paths += sorted((folder/'matches').glob('*.json'))
        paths += sorted((folder/'episodes').glob('*.json'))
        paths += sorted((self.world_cache/run_id).glob('*.json'))
        fingerprint = [(str(path), stamp(path)) for path in paths]
        if fingerprint == self.previous and self.output.exists():
            return None
        plan = read(folder/'plan.json')
        matches, replays, episodes = [], {}, {}
        for fixture in plan['schedule']:
            ordinal = fixture['ordinal']
            if type(ordinal) is not int or ordinal < 0:
                continue
            def project_match(row):
                if not all(row.get(k) == v for k, v in fixture.items()):
                    return None
                summary = fields(row, MATCH_KEYS)
                # Seat names are known IDs, but dictionary keys are model/side
                # identifiers rather than game state keys; explicitly retain.
                if isinstance(row.get('seats'), dict):
                    summary['seats'] = {str(k): scalar(v) for k, v in row['seats'].items()}
                for key in ('result_a', 'result_b'):
                    if isinstance(row.get(key), dict):
                        summary[key] = fields(row[key], RESULT_KEYS)
                replay = {**summary, 'participants': [row['a'], row['b']], 'streams': []}
                if row['mode'] == 'direct':
                    replay['streams'] = [stream(row, f'match-{ordinal:05d}', [row['a'], row['b']])]
                else:
                    refs = row.get('episode_refs') or {}
                    for player in (row['a'], row['b']):
                        ref = refs.get(player)
                        if isinstance(ref, str) and SAFE_ID.fullmatch(ref):
                            replay['streams'].append({'episode_id': ref, 'participant': player})
                return summary, replay
            projected = self._cached(folder/'matches'/f'{ordinal:05d}.json', project_match)
            if projected is None:
                continue
            summary, replay = projected
            if not all(summary.get(k) == v for k, v in fixture.items()):
                continue
            matches.append(summary)
            replays[f'{ordinal:05d}'] = replay
            for reference in replay['streams']:
                ref = reference.get('episode_id')
                if not ref or ref in episodes:
                    continue
                def project_episode(row):
                    if (row.get('episode_id') != ref or row.get('model') != reference['participant']
                            or row.get('kind') != fixture['kind'] or row.get('seed') != fixture['seed']):
                        return None
                    restored = self._world_frames(folder/'episodes'/f'{ref}.json', row, run_id)
                    return stream(row, ref, [row['model']], row['model'], restored)
                projected_episode = self._cached(folder/'episodes'/f'{ref}.json', project_episode,
                                                  self.world_cache/run_id/f'{ref}.json')
                if projected_episode is not None:
                    episodes[ref] = projected_episode
        counts = {kind: sum(row['kind'] == kind for row in matches) for kind in plan['kinds']}
        data = {'revision': REVISION, 'schema': REVISION, 'run_id': run_id,
                'updated_at': max(mark[0]/1e9 for _, mark in fingerprint if mark),
                'exported_at': time.time(), 'games': [{'kind': k, 'count': v} for k, v in counts.items()],
                'matches': matches, 'replays': replays, 'episodes': episodes}
        if data_only:
            return data
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        compressed = gzip.compress(raw.encode(), compresslevel=6, mtime=0)
        envelope = {key: data[key] for key in ('revision', 'schema', 'run_id', 'updated_at', 'exported_at')}
        envelope.update(encoding='gzip-base64', uncompressed_bytes=len(raw.encode()),
                        data=base64.b64encode(compressed).decode('ascii'))
        payload = PREFIX+json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))+';\n'
        self.raw_output.parent.mkdir(parents=True, exist_ok=True)
        raw_temp = self.raw_output.with_name(self.raw_output.name+f'.tmp-{os.getpid()}')
        raw_temp.write_text(raw)
        os.replace(raw_temp, self.raw_output)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.output.with_name(self.output.name+f'.tmp-{os.getpid()}')
        temp.write_text(payload)
        os.replace(temp, self.output)
        self.previous = fingerprint
        return {'run_id': run_id, 'matches': len(matches), 'games': len(counts),
                'episodes': len(episodes), 'bytes': len(payload.encode()),
                'uncompressed_bytes': len(raw.encode()), 'gzip_bytes': len(compressed)}

    def _world_frames(self, path, row, run_id):
        cache = self.world_cache/run_id/path.name
        if row.get('kind') not in ('mario_platformer', 'terraria_survival') or not cache.exists():
            return None
        restored = read(cache)
        source = restored.get('source') or {}
        current = stamp(path)
        if (source != {'run_id': run_id, 'mtime_ns': current[0], 'size': current[1]}
                or restored.get('revision') != 'original-world-fixed-frame-replay-v1'
                or any(restored.get(key) != row.get(key) for key in ('kind', 'seed', 'model', 'episode_id'))):
            return None
        for field in ('initial_state', 'final_state'):
            visible = {k: v for k, v in restored[field].items() if k not in ('timing', 'replay_scene')}
            archived = {k: v for k, v in row[field].items() if k != 'timing'}
            if visible != archived:
                return None
        steps, traces, receipts = restored.get('steps', []), row.get('trace', []), row.get('execution_receipts', [])
        if len(steps) != len(traces) or len(steps) != len(receipts):
            return None
        if any(step.get('action') != trace.get('action') or step.get('action') != receipt.get('action')
               for step, trace, receipt in zip(steps, traces, receipts)):
            return None
        return restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_FRONT/'game_arena')
    parser.add_argument('--output', type=Path, default=DEFAULT_FRONT/'playground/visible-control.js')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--world-cache', type=Path, default=DEFAULT_WORLD_CACHE)
    parser.add_argument('--raw-output', type=Path)
    parser.add_argument('--interval', type=float, default=30)
    args = parser.parse_args()
    if args.interval < 5:
        parser.error('--interval must be at least 5 seconds')
    exporter = Exporter(args.root, args.output, args.world_cache, args.raw_output)
    while True:
        try:
            result = exporter.export()
            if result:
                print(json.dumps(result), flush=True)
        except (OSError, ValueError, KeyError, TypeError) as error:
            # Never log archive content or exception text; an in-flight archive
            # change leaves the previous complete static export available.
            print(json.dumps({'error_type': type(error).__name__}), flush=True)
            if not args.watch:
                raise SystemExit(1)
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
