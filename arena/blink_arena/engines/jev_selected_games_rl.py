"""Seat-aware rollout and exact replay for the eight selected native engines."""
from copy import deepcopy
from jev_engine_registry import get_engine
import jev_selected_games as games


async def play(sampler, job):
    engine = get_engine(job['kind'])
    side = job.get('side', 0)
    if type(side) is not int or not 0 <= side < engine.seat_count:
        raise ValueError('Invalid controlled seat')
    mode = job.get('mode', engine.opponent_modes[0])
    if mode not in engine.opponent_modes:
        raise ValueError('Invalid selected-game opponent mode')
    initial = engine.reset(job['seed'])
    state = deepcopy(initial)
    trace, events = [], []
    qwen_calls = 0
    budget = min(job.get('max_decisions', engine.limit), engine.limit)
    for ordinal in range(engine.limit):
        if engine.outcome(state, side) or len(trace) >= budget:
            break
        if state.get('handoff'):
            state = engine.environment.reveal(state)
            events.append({'type': 'reveal', 'after_state': deepcopy(state)})
        actor = games.actor(state)
        options = engine.legal_actions(state)
        if not options:
            break
        record = engine.observe(state)
        controlled = actor == side
        if len(options) == 1:
            action = next(iter(options))
            details = {'forced': True, 'origin': 'deterministic_execution'}
        elif controlled:
            action, details = await sampler.policy_action(record, job['episode_id'], ordinal)
        elif mode == 'qwen3.8-max':
            action, details = await sampler.qwen(job['kind'], job['seed'], ordinal, record)
            qwen_calls += 1
        else:
            action, details = games.rule_action(state, ordinal), {'forced': False, 'origin': 'rule_engine'}
        if action not in options:
            raise ValueError('Policy selected an illegal native action')
        before = deepcopy(state)
        state = engine.step(state, action)
        event = {'type': 'action', 'actor': actor, 'controlled': controlled,
                 'ordinal': ordinal, 'record': deepcopy(record), 'action': action,
                 'before_state': before, 'after_state': deepcopy(state)}
        events.append(event)
        if controlled:
            row = {'ordinal': ordinal, 'record': deepcopy(record), 'action': action,
                   'before_state': before, 'after_state': deepcopy(state), 'policy': details,
                   'actor': actor}
            trace.append(row)
            sampler.journal(job, 'decision', {'ordinal': ordinal, 'record': record, 'action': action, 'policy': details})
            sampler.journal(job, 'executed', row)
    outcome = engine.outcome(state, side) or 'budget_exhausted'
    extra = {'selected_game_revision': games.REVISION, 'events': events,
             'controlled_side': side, 'opponent': mode, 'qwen_calls': qwen_calls,
             'decision_limit': budget, 'rule_opponent': 'seeded_legal_random_v1'}
    return initial, state, trace, outcome, extra


def verify(job, initial, final, extra, trace=None):
    engine = get_engine(job['kind'])
    if extra.get('opponent') != job.get('mode', engine.opponent_modes[0]):
        raise ValueError('Selected-game opponent condition changed')
    state = engine.reset(job['seed'])
    if state != initial or extra.get('controlled_side') != job.get('side', 0) or extra.get('selected_game_revision') != games.REVISION:
        raise ValueError('Selected-game initial state or controlled seat changed')
    reconstructed = []
    for event in extra['events']:
        if event['type'] == 'reveal':
            state = engine.environment.reveal(state)
        elif event['type'] == 'action':
            if (event['ordinal'] != state['steps'] or state != event['before_state'] or games.actor(state) != event['actor']
                    or event['controlled'] != (event['actor'] == extra['controlled_side'])
                    or engine.observe(state) != event['record']
                    or event['action'] not in engine.legal_actions(state)):
                raise ValueError('Selected-game observation, actor or legal action changed')
            if not event['controlled'] and extra['opponent']=='rule_engine' and event['action'] != games.rule_action(state,event['ordinal']):
                raise ValueError('Rule opponent action changed')
            state = engine.step(state, event['action'])
            if event['controlled']:
                reconstructed.append({key: event[key] for key in ('ordinal', 'record', 'action', 'before_state', 'after_state', 'actor')})
        else:
            raise ValueError('Unknown selected-game replay event')
        if state != event['after_state']:
            raise ValueError('Selected-game transition changed')
    if state != final:
        raise ValueError('Selected-game final state changed')
    if trace is None:
        raise ValueError('Selected-game replay requires the executed student trace')
    projected = [{key: row[key] for key in ('ordinal', 'record', 'action', 'before_state', 'after_state', 'actor')} for row in trace]
    if projected != reconstructed:
        raise ValueError('Selected-game student trace changed')
    return True
