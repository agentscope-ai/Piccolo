"""Actor control for existing social/probability frontend engine primitives.

This adapter changes who chooses an existing legal action. It supplies only
the actor's visible cards, public history and already exposed opponent views.
It does not implement chance, movement, betting settlement or victory rules.
"""
import copy
import random
import math
import json


def wire_value(value):
    """The actual frontend JSON boundary converts tuples and object keys."""
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def same_wire_value(left, right):
    return wire_value(left) == wire_value(right)


def joint_choice_probability(record, action, policy):
    """Validate the probability of this one actual Choice, never an outer turn."""
    if policy.get('forced'):
        return None
    if list(record['questions']) != ['decision'] or record['questions']['decision']['type'] != 'choice':
        raise ValueError('native actor transitions require one joint decision Choice')
    probabilities = policy['old_probabilities']
    values = policy['candidate_values']
    index = policy['selected_index']
    if (len(values) != len(probabilities) or not 0 <= index < len(values)
            or values[index] != action or set(values) != set(record['questions']['decision']['criteria'])):
        raise ValueError('sampled Choice probability/action mapping mismatch')
    if (any(not math.isfinite(float(p)) or p < 0 or p > 1 for p in probabilities)
            or abs(sum(probabilities) - 1) > 1e-5 or probabilities[index] <= 0):
        raise ValueError('invalid sampled Choice distribution')
    return float(probabilities[index])


def doudizhu_record(native, game, actor):
    if actor == 0:
        return native.as_record(game)
    candidates = native.social.dzoptions(game, actor)
    options = {key: '不出／过牌' if pattern is None else native.social.dzname(pattern[3])
               for key, pattern in candidates.items()}
    observation = {'hand': list(game['hands'][actor]),
        'other_hand_counts': {str(i): len(game['hands'][i]) for i in range(3) if i != actor},
        'last_play': copy.deepcopy(game['last']), 'leader': game['leader'],
        'turn': actor, 'history': copy.deepcopy(game['history'][-8:])}
    return native.social_opponents._record('doudizhu',
        f'你是农民{actor}，与另一名农民合作对抗地主0',
        '标准斗地主出牌、跟牌、炸弹和火箭规则；只能使用自己的手牌和公开历史。地主先出完则农民败，任一农民先出完则农民胜。',
        observation, options,
        '尽量比地主更早出完团队手牌；根据可见组合与对手剩牌决策，不能假设隐藏手牌。只输出合法动作 ID。')


def rule_actor0(native, record, seed, outer):
    """Existing rule policy, applied to legal public actor-0 observations.

    Poker's asymmetric action sets require the existing public-information
    pokerbest reference, recorded explicitly as a different engine role.
    """
    kind = record['metadata']['sub_domain']
    options = record['questions']['decision']['criteria']
    if len(options) == 1:
        return next(iter(options))
    obs = record['state']['observation']
    if kind == 'texas_holdem':
        visible = {'kind': kind, 'hands': [obs['hand'], []], 'board': obs['board'],
                   'stacks': obs['stacks'], 'pot': obs['pot'], 'to_call': obs['to_call']}
        return native.social.pokerbest(visible)
    if kind == 'property_tycoon':
        position = obs['positions'][0]
        price = obs['prices'].get(str(position), obs['prices'].get(position, 0))
        return 'buy' if 'buy' in options and obs['cash'][0] - price >= 250 else 'skip'
    if kind == 'pig_dice':
        target = 14 if obs['scores'][0] >= obs['scores'][1] else 18
        return 'hold' if 'hold' in options and (obs['turn_points'] >= target or
            obs['scores'][0] + obs['turn_points'] >= 50) else 'roll'
    if kind == 'zha_jin_hua':
        if not obs['seen']:
            return 'peek'
        rank = native.probability.rank3(tuple(obs['hand']))
        weak = rank[0] == 0 and rank[1] <= 10
        if obs['round'] >= 2 and weak and random.Random(f'{seed}/{outer + 1}').random() < .28:
            return 'fold'
        return 'call' if 'call' in options else 'fold'
    raise ValueError('unsupported visible actor-0 rule policy')


async def play(sampler, native, job, *, transitions=False):
    kind, seed, mode, side = (job[k] for k in ('kind', 'seed', 'mode', 'side'))
    game = native.fresh(kind, seed, 'rule')
    initial = copy.deepcopy(game)
    trace, events = [], []
    qwen_calls = 0
    pending = {}

    def bind_execution(item, before, after, execution_before=None, execution_after=None):
        item.update(before_state=copy.deepcopy(before), after_state=copy.deepcopy(after),
                    execution_before=copy.deepcopy(execution_before),
                    execution_after=copy.deepcopy(execution_after),
                    choice_probability=joint_choice_probability(item['record'], item['action'], item['policy']),
                    probability_scope='one_actual_decision_choice',
                    acceptance_subdecision=False)
        trace.append(item)
        sampler.journal(job, 'executed', item)

    async def choose(record, actor, ordinal):
        nonlocal qwen_calls
        if transitions:
            record = wire_value(record)
        options = record['questions']['decision']['criteria']
        if len(options) == 1:
            action, detail = next(iter(options)), {'forced': True, 'origin': 'deterministic_execution'}
        elif actor == side:
            action, detail = await sampler.policy_action(record, job['episode_id'], ordinal)
        elif mode == 'qwen3.8-max':
            action, detail = await sampler.qwen(kind, seed, ordinal, record)
            qwen_calls += 1
        else:
            raise ValueError('rule actor must select via the existing engine policy')
        if action not in options:
            raise ValueError('actor selected an illegal action')
        if actor == side:
            item = {'actor': actor, 'ordinal': ordinal, 'record': copy.deepcopy(record),
                    'action': action, 'policy': detail, 'acceptance_subdecision': True}
            if transitions:
                if ordinal in pending:
                    raise ValueError('duplicate controlled native decision ordinal')
                joint_choice_probability(item['record'], action, detail)
                pending[ordinal] = item
                sampler.journal(job, 'decision', item)
            else:
                trace.append(item)
                sampler.journal(job, 'executed', item)
        return action

    if kind == 'doudizhu':
        for ordinal in range(native.LIMITS[kind] * 3):
            if game.get('outcome') or (game['steps'] >= native.LIMITS[kind] and game['turn'] == 0):
                break
            actor = game['turn']
            record = doudizhu_record(native, game, actor)
            before = copy.deepcopy(game) if transitions and actor == side else None
            if actor != side and mode == 'rule_engine':
                action = native.social.dzbest(game, actor)
            else:
                action = await choose(record, actor, ordinal)
            if actor == 0:
                game['steps'] += 1
            native.social.dzplay(game, actor, action)
            if not game['outcome']:
                game['event'] = '轮到玩家' + str(game['turn']) + '出牌'
                game['score'] = 20 - len(game['hands'][0])
            game['history'] = game['history'][-12:]
            if transitions and actor == side:
                bind_execution(pending.pop(ordinal), before, game)
            events.append({'type': 'doudizhu_actor', 'actor': actor, 'record': record,
                           'action': action, 'after_state': copy.deepcopy(game)})
    else:
        # Preserve native actor-0 outer steps and the frontend opponent's
        # exact callback contexts. Subject seat 1 controls those callbacks.
        for outer in range(native.LIMITS[kind]):
            if game.get('outcome'):
                break
            options = native.choices(game)
            if not options:
                break
            record = native.as_record(game)
            before = copy.deepcopy(game) if transitions and side == 0 else None
            if side == 0 or mode == 'qwen3.8-max':
                action = await choose(record, 0, outer)
            else:
                action = rule_actor0(native, record, seed, outer)
            responses = []
            execution_events = []
            use_callbacks = side == 1 or mode == 'qwen3.8-max'
            if use_callbacks:
                async def callback(opponent_record, substep):
                    observed = copy.deepcopy(opponent_record)
                    chosen = await choose(observed, 1, substep)
                    responses.append({'record': observed, 'ordinal': substep, 'action': chosen})
                    return chosen
                async def observer(event):
                    execution_events.append(copy.deepcopy(event))
                    if event['actor'] == side:
                        item = pending.pop(event['ordinal'], None)
                        if item is None:
                            # _ask mechanically executes a sole legal action
                            # without calling the policy. Keep its real effect
                            # as B, without inventing a model probability.
                            allowed = event['record']['questions']['decision']['criteria']
                            if len(allowed) != 1 or event['action'] != next(iter(allowed)):
                                raise ValueError('unmatched non-forced native callback execution')
                            item = {'actor': side, 'ordinal': event['ordinal'],
                                    'record': wire_value(event['record']), 'action': event['action'],
                                    'policy': {'forced': True, 'origin': 'deterministic_execution'}}
                        if not same_wire_value(item['record'], event['record']) or item['action'] != event['action']:
                            raise ValueError('native post-execution input/action mismatch')
                        bind_execution(item, event['before_state'], event['after_state'],
                                       event['execution_before'], event['execution_after'])
                if transitions:
                    game, _ = await native.social_opponents.step(game, action, callback,
                        post_execution_observer=observer)
                else:
                    game, _ = await native.social_opponents.step(game, action, callback)
            else:
                game = native.step(game, action)
            if transitions and side == 0:
                bind_execution(pending.pop(outer), before, game)
            event = {'type': 'outer', 'record': record, 'action': action,
                           'used_callbacks': use_callbacks, 'responses': responses,
                           'after_state': copy.deepcopy(game)}
            if transitions:
                event['execution_events'] = execution_events
            events.append(event)
    if pending:
        raise ValueError('controlled native Choice has no actual execution result')
    outcome = game.get('outcome') or 'budget_exhausted'
    if side != 0:
        outcome = {'win': 'loss', 'loss': 'win'}.get(outcome, outcome)
    return initial, game, trace, outcome, {'qwen_calls': qwen_calls, 'events': events,
        'opponent': mode, 'native_social_actor_control': True,
        'role_asymmetry': 'landlord_vs_cooperative_farmers' if kind == 'doudizhu' else
            'asymmetric_action_sets' if kind in ('texas_holdem', 'zha_jin_hua') else
            'actor0_starts_each_round',
        'engine_actor0_policy': 'existing_public_pokerbest_reference' if kind == 'texas_holdem' else
            'existing_rule_opponent_policy_applied_to_actor0' if side == 1 else 'not_used',
        'reward_export_prohibited': not transitions,
        'transition_revision': 'native-actor-step-v1' if transitions else None}


async def replay(native, job, initial, final, extra):
    extra.pop('native_zero_controlled_terminal', None)
    game = native.fresh(job['kind'], job['seed'], 'rule')
    if not same_wire_value(game, initial):
        raise ValueError('social seat initial state changed')
    for event in extra['events']:
        if event['type'] == 'doudizhu_actor':
            actor = game['turn']
            if actor != event['actor'] or not same_wire_value(doudizhu_record(native, game, actor), event['record']):
                raise ValueError('social actor public input changed on replay')
            if actor == 0:
                game['steps'] += 1
            native.social.dzplay(game, actor, event['action'])
            if not game['outcome']:
                game['event'] = '轮到玩家' + str(game['turn']) + '出牌'
                game['score'] = 20 - len(game['hands'][0])
            game['history'] = game['history'][-12:]
        else:
            if not same_wire_value(native.as_record(game), event['record']):
                raise ValueError('social actor-0 public input changed on replay')
            if event['action'] not in event['record']['questions']['decision']['criteria']:
                raise ValueError('social actor-0 action is not a legal Choice on replay')
            if event['used_callbacks']:
                responses = iter(event['responses'])
                async def callback(record, ordinal):
                    saved = next(responses)
                    if not same_wire_value(record, saved['record']) or ordinal != saved['ordinal']:
                        raise ValueError('social actor-1 public input changed on replay')
                    return saved['action']
                if extra.get('transition_revision'):
                    observed_effects = iter(event['execution_events'])
                    async def observer(effect):
                        expected = next(observed_effects)
                        if not same_wire_value(effect, expected):
                            raise ValueError('native actor before/after effect changed on replay')
                    game, _ = await native.social_opponents.step(game, event['action'], callback,
                        post_execution_observer=observer)
                    if next(observed_effects, None) is not None:
                        raise ValueError('unused native actor effect on replay')
                else:
                    game, _ = await native.social_opponents.step(game, event['action'], callback)
                if next(responses, None) is not None:
                    raise ValueError('unused social actor callback on replay')
            else:
                game = native.step(game, event['action'])
        if not same_wire_value(game, event['after_state']):
            raise ValueError('social seat physical state changed on replay')
    if not same_wire_value(game, final):
        raise ValueError('social seat terminal state changed on replay')
    # An opponent can terminate before the controlled seat receives a Choice
    # (for example, actor 0 peeks and folds). This is a real terminal result,
    # but provides no student action
    # to optimize. Publish only replay-verified public execution facts, never
    # the private native states or opponent cards used by exact engine replay.
    events = extra.get('events', [])
    opponent_actions = []
    for ordinal, event in enumerate(events):
        if (event.get('type') == 'outer' and job.get('side') != 0
                and event.get('used_callbacks') is True and event.get('responses') == []
                and event.get('execution_events') == []):
            actor = 0
        elif event.get('type') == 'doudizhu_actor' and event.get('actor') != job.get('side'):
            actor = event['actor']
        else:
            break
        opponent_actions.append({'actor': actor, 'ordinal': ordinal, 'action': event['action']})
    if (type(job.get('side')) is int and job['side'] in (0, 1)
            and extra.get('transition_revision') == 'native-actor-step-v1'
            and extra.get('native_social_actor_control') is True
            and not extra.get('reward_export_prohibited')
            and initial.get('outcome') is None and final.get('outcome') in ('win', 'loss', 'draw')
            and events and len(opponent_actions) == len(events)):
        if extra.get('trace', []) != []:
            raise ValueError('native zero-controlled terminal has an unexplained student trace')
        extra['native_zero_controlled_terminal'] = {
            'revision': 'jev.native-zero-controlled-terminal.v1', 'verified': True,
            'kind': job['kind'], 'seed': job['seed'], 'side': job['side'],
            'policy_version': job['policy_version'], 'episode_id': job['episode_id'],
            'transition_revision': extra['transition_revision'],
            'initial_outcome': initial['outcome'], 'native_outcome': final['outcome'],
            'controlled_outcome': ({'win': 'loss', 'loss': 'win'}.get(final['outcome'], final['outcome'])
                                   if job['side'] else final['outcome']),
            'initial_steps': initial['steps'], 'terminal_steps': final['steps'],
            'opponent_actions': opponent_actions,
            'controlled_actions': 0, 'controlled_choice_requests': 0,
            'model_strategy_decisions': 0, 'learning_signal': False}
