"""Wall-clock adapter shared by the live HTTP session and offline policy runners.

A timer/poll never selects a lane. It only catches up the authoritative engine.
Capturing or committing does not reset the clock, and busy inference is no pause.
"""
import copy,time
import jev_racing_game as game

CLOCK_CONTRACT='realtime_wall_clock_after_first_throttle_50ms_free_pedals_pulse035_intent4s'
MIN_DECISION_SECONDS=1.
MODEL_TIMEOUT_SECONDS=90.


def start(session, now=None):
    session['racing_clock_at']=time.monotonic() if now is None else now
    return session


def tick(session, now=None):
    now=time.monotonic() if now is None else now
    if 'racing_clock_at' not in session:start(session,now)
    elapsed=max(0.,now-session['racing_clock_at'])
    session['world']=game.advance_idle(session['world'],elapsed)
    session['racing_clock_at']=now
    return session['world']


def capture(session):
    tick(session)
    before=copy.deepcopy(session['world'])
    # The world may finish between HTTP requests or during pacing. A terminal
    # state has no legal inputs, so constructing its braking projections fails.
    return before,None if before['outcome'] else game.as_record(before)


def commit(session, action, controller="model", observed=None):
    # Driving inputs are not tied to a piece identity. Keep arrival-time
    # terminal validation; observed is the shared runtime protocol argument.
    tick(session)
    arrived=copy.deepcopy(session['world'])
    if arrived['outcome']:return {'applied':False,'arrival_state':arrived,'reason':'race_finished_while_waiting'}
    session['world']=game.step(arrived,action,controller=controller)
    return {'applied':True,'arrival_state':arrived,'reason':None}


def fail(session, reason):
    tick(session)
    session['world'].update(outcome='loss',event='模型响应失败，本局计为失败',failure_reason=reason)
    return session['world']


def replay_transition(before, transition):
    state=game.advance_idle(before,transition['waiting_seconds'])
    if state!=transition['arrival_state']:raise ValueError('racing arrival state replay mismatch')
    if transition['action_applied']:
        if state['outcome']:raise ValueError('racing action applied after terminal')
        state=game.step(state,transition['action'])
    state=game.advance_idle(state,transition.get('post_action_seconds',0.))
    if state!=transition['after_state']:raise ValueError('racing after-state replay mismatch')
    return state
