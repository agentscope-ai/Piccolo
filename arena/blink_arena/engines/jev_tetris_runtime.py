"""Authoritative Tetris clock shared by HTTP control and policy episodes.

Every observation/input catches up the monotonic clock. Polling frequency and
model latency cannot pause gravity; only an actual first input starts it.
"""
import copy
import time

import jev_tetris_realtime as game

CLOCK_CONTRACT = 'tetris-wall-clock-v1-first-input-gravity-piece-bound'
MODEL_TIMEOUT_SECONDS = 90.
MIN_DECISION_SECONDS = .5


def piece_id(state):
    return (state.get('active') or {}).get('piece_id')


def discard_reason(before, arrived, action):
    if arrived.get('outcome'):
        return 'game_finished_while_waiting'
    if piece_id(before) is None or piece_id(before) != piece_id(arrived):
        return 'piece_changed_while_waiting'
    if action not in game.choices(arrived):
        return 'action_changed_while_waiting'
    return None


def start(session, now=None):
    session['tetris_clock_at'] = time.monotonic() if now is None else now
    return session


def tick(session, now=None):
    now = time.monotonic() if now is None else now
    if 'tetris_clock_at' not in session:
        start(session, now)
    session['world'] = game.advance_idle(session['world'], max(0., now - session['tetris_clock_at']))
    session['tetris_clock_at'] = now
    return session['world']


def capture(session, *, for_policy=True):
    before = copy.deepcopy(tick(session))
    allowed = game.needs_decision(before) if for_policy else bool(game.choices(before))
    return before, game.as_record(before) if allowed else None


def commit(session, action, controller='model', observed=None):
    arrived = copy.deepcopy(tick(session))
    reason = discard_reason(observed or arrived, arrived, action)
    if reason:
        return {'applied': False, 'arrival_state': arrived, 'reason': reason}
    session['world'] = game.step(arrived, action, controller=controller)
    return {'applied': True, 'arrival_state': arrived, 'reason': None}


def fail(session, reason):
    tick(session)
    if not session['world']['outcome']:
        session['world'].update(outcome='loss', event='model_error', failure_reason=reason)
    return session['world']
