"""Authoritative wall-clock adapter shared by Snake HTTP and policy runners."""
import copy
import time
import jev_snake_realtime as game

CLOCK_CONTRACT = 'snake-wall-clock-v1-first-input-autoforward-1200-to-950ms'
MODEL_TIMEOUT_SECONDS = 90.
MIN_DECISION_SECONDS = 1.


def start(session, now=None):
    session['snake_clock_at'] = time.monotonic() if now is None else now
    return session


def tick(session, now=None):
    now = time.monotonic() if now is None else now
    if 'snake_clock_at' not in session:
        start(session, now)
    session['world'] = game.advance_idle(session['world'], max(0., now - session['snake_clock_at']))
    session['snake_clock_at'] = now
    return session['world']


def capture(session):
    tick(session)
    before = copy.deepcopy(session['world'])
    return before, game.as_record(before)


def commit(session, action, controller='model', observed=None):
    # Direction legality is checked against the current arrival state. A prior
    # observation does not freeze heading or movement while the policy thinks.
    tick(session)
    arrived = copy.deepcopy(session['world'])
    if arrived['outcome']:
        return {'applied': False, 'arrival_state': arrived, 'reason': 'game_finished_while_waiting'}
    if action not in game.choices(arrived):
        return {'applied': False, 'arrival_state': arrived, 'reason': 'direction_changed_while_waiting'}
    session['world'] = game.step(arrived, action, controller=controller)
    return {'applied': True, 'arrival_state': arrived, 'reason': None}


def fail(session, reason):
    tick(session)
    if not session['world']['outcome']:
        session['world'].update(outcome='loss', event='model_error', failure_reason=reason)
    return session['world']
