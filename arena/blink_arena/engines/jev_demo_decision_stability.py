"""Single decisions for realtime games; three order probes for other games.

Probabilities are aligned by action ID, never by shuffled answer token. The
Jensen-Shannon distance uses base two and the square-root convention of SciPy.
This measures sensitivity to option order, not accuracy or calibrated confidence.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import copy
from itertools import combinations
import math
import random
import statistics
import time

from fastapi import HTTPException

REPEAT_COUNT = 3
REVISION = 'jev-decision-option-order-stability-v1'
POLICY_REVISION = 'jev-game-decision-policy-v2-realtime-single'
REALTIME_GAME_KINDS = frozenset(('terraria_survival', 'mario_platformer',
                                'racing_sprint', 'snake_navigation', 'tetris_placement'))


def decision_policy(kind):
    realtime = kind in REALTIME_GAME_KINDS
    return {'revision': 'jev-tetris-decision-policy-v1-realtime-single' if kind == 'tetris_placement' else POLICY_REVISION,
            'repeat_count': 1 if realtime else REPEAT_COUNT,
            'option_order': 'original' if realtime else 'three_shuffled_orders',
            'reason': 'realtime_game' if realtime else 'option_order_stability'}


def shuffled_orders(candidate_order, rng=None):
    """Use three distinct orders when possible; two options expose both orders."""
    rng = rng or random.SystemRandom()
    first = list(candidate_order)
    rng.shuffle(first)
    if len(first) == 2:
        second = first[::-1]
        return [first, second, list(rng.choice((first, second)))]
    orders = [first]
    for _ in range(30):
        order = list(candidate_order)
        rng.shuffle(order)
        if order not in orders:
            orders.append(order)
        if len(orders) == REPEAT_COUNT:
            return orders
    # A bounded fallback also handles deterministic RNGs without a retry loop.
    for shift in range(1, len(first)):
        order = first[shift:] + first[:shift]
        if order not in orders:
            orders.append(order)
        if len(orders) == REPEAT_COUNT:
            return orders
    raise ValueError('at_least_two_candidates_required')


def _distribution(distribution, candidate_order, coverage=None):
    if not isinstance(distribution, list):
        raise ValueError('candidate_distribution_missing')
    aligned = {}
    for row in distribution:
        if not isinstance(row, dict):
            raise ValueError('invalid_candidate_distribution')
        value = row.get('value')
        if not isinstance(value, str) or value not in candidate_order or value in aligned:
            raise ValueError('candidate_identity_mismatch')
        probability = row.get('probability')
        if probability is not None and (type(probability) not in (float, int)
                or not math.isfinite(probability) or not 0 <= probability <= 1):
            raise ValueError('invalid_candidate_probability')
        aligned[value] = probability
    complete = (len(aligned) == len(candidate_order)
                and all(aligned[value] is not None for value in candidate_order))
    if coverage is not None and coverage.get('complete') is False:
        complete = False
    if complete and not math.isclose(sum(aligned.values()), 1, rel_tol=1e-7, abs_tol=1e-7):
        raise ValueError('candidate_probabilities_not_normalized')
    return aligned, complete


def probability_metrics(candidate_order, distributions, coverages=None):
    """Return sample variance (ddof=1) and mean pairwise JS distance, or nulls.

    A partial distribution is never padded, renormalized or used for a distance.
    Input lists remain unchanged, including any explicitly missing probabilities.
    """
    if len(distributions) != REPEAT_COUNT:
        raise ValueError('three_distributions_required')
    coverages = [None]*REPEAT_COUNT if coverages is None else coverages
    if len(coverages) != REPEAT_COUNT:
        raise ValueError('three_coverages_required')
    aligned = [_distribution(distribution, candidate_order, coverage)
               for distribution, coverage in zip(distributions, coverages)]
    complete = all(item[1] for item in aligned)
    result = {'probability_complete': complete,
              'candidate_probability_variance': None, 'mean_probability_variance': None,
              'mean_js_distance': None, 'probability_stability': None}
    if not complete:
        return result
    vectors = [[probabilities[value] for value in candidate_order]
               for probabilities, _ in aligned]
    variances = {value: statistics.variance(vector[index] for vector in vectors)
                 for index, value in enumerate(candidate_order)}
    distances = []
    for a, b in combinations(vectors, 2):
        divergence = 0.0
        for p, q in zip(a, b):
            middle = (p+q)/2
            if p:
                divergence += .5*p*math.log2(p/middle)
            if q:
                divergence += .5*q*math.log2(q/middle)
        distances.append(math.sqrt(min(1.0, max(0.0, divergence))))
    mean_distance = statistics.mean(distances)
    return {**result, 'candidate_probability_variance': variances,
            'mean_probability_variance': statistics.mean(variances.values()),
            'mean_js_distance': mean_distance, 'probability_stability': 1-mean_distance}


def _failure(error, index):
    # Provider exception text and headers may contain credentials or request data.
    status = error.status_code if isinstance(error, HTTPException) else 502
    allowed = {'connection_failed', 'invalid_response', 'timeout', 'cancelled',
               'authentication_failed', 'rate_limited', 'endpoint_not_found',
               'upstream_unavailable'}
    detail = error.detail if isinstance(error, HTTPException) else None
    cause = detail.get('code') if isinstance(detail, dict) else None
    if cause not in allowed:
        cause = {401: 'authentication_failed', 403: 'authentication_failed',
                 404: 'endpoint_not_found', 429: 'rate_limited',
                 503: 'upstream_unavailable', 504: 'timeout'}.get(status, 'connection_failed')
    return HTTPException(status, detail={'code': 'decision_repeat_failed', 'cause': cause,
        'error_type': type(error).__name__, 'sample_index': index})


async def repeated_predict(predict_once, record, qid, model=None, *, rng=None):
    """Choose one action after three independent calls on the same copied state.

    Calls overlap at most two at a time within this decision. The underlying
    predictor retains its existing per-model concurrency and provider limits.
    Non-choice and forced one-option decisions retain their existing single call.
    On any failure, unfinished probes are cancelled and no action is returned.
    """
    question = record.get('questions', {}).get(qid)
    if not isinstance(question, dict):
        raise HTTPException(422, 'decision_question_missing')
    metadata = record.get('metadata') or {}
    state = record.get('state') or {}
    kind = metadata.get('sub_domain') or (state.get('kind') if isinstance(state, dict) else None)
    # Terramai's existing public contract predates the showcase game ID.
    kind = {'terramai_directional': 'terraria_survival'}.get(kind, kind)
    if kind in REALTIME_GAME_KINDS:
        result = await predict_once(record, qid, model=model)
        # A single judgement has no variance/agreement estimate. Do not invent
        # perfect stability or let a provider's stale field reach aggregation.
        result = {key: value for key, value in result.items() if key != 'decision_stability'}
        result['decision_policy'] = decision_policy(kind)
        return result
    criteria = question.get('criteria')
    if question.get('type') != 'choice' or not isinstance(criteria, dict) or len(criteria) < 2:
        return await predict_once(record, qid, model=model)
    # Freeze once before scheduling: a realtime caller may update its own state
    # while these calls are awaiting the provider, without changing our probes.
    snapshot = copy.deepcopy(record)
    question = snapshot['questions'][qid]
    criteria = question['criteria']
    candidate_order = question.get('option_order', list(criteria))
    if (not isinstance(candidate_order, list) or len(candidate_order) != len(criteria)
            or any(not isinstance(value, str) or value not in criteria for value in candidate_order)
            or len(set(candidate_order)) != len(criteria)):
        raise HTTPException(422, 'invalid_candidate_order')
    orders = shuffled_orders(candidate_order, rng)
    semaphore = asyncio.Semaphore(2)
    began = time.perf_counter()

    async def sample(index, order):
        try:
            probe = copy.deepcopy(snapshot)
            probe_question = probe['questions'][qid]
            probe_question['option_order'] = list(order)
            probe_question['criteria'] = {value: probe_question['criteria'][value] for value in order}
            async with semaphore:
                started = time.perf_counter()
                result = await predict_once(probe, qid, model=model)
                elapsed = time.perf_counter()-started
            if (not isinstance(result, dict) or not isinstance(result.get('model'), str)
                    or model is not None and result.get('model') != model
                    or result.get('value') not in criteria):
                raise ValueError('model_or_action_identity_mismatch')
            aligned, complete = _distribution(result.get('distribution'), candidate_order,
                                               result.get('probability_coverage'))
            if result['value'] not in aligned:
                raise ValueError('selected_candidate_distribution_missing')
            latency = result.get('latency_seconds')
            if type(latency) not in (float, int) or not math.isfinite(latency) or latency < 0:
                latency = elapsed
            return result, {'sample_index': index, 'order': list(order),
                            'value': result['value'], 'distribution': copy.deepcopy(result['distribution']),
                            'model': result['model'], 'served_model': result.get('served_model'),
                            'latency_seconds': latency, 'probability_complete': complete}
        except Exception as error:
            raise _failure(error, index) from None

    tasks = [asyncio.create_task(sample(index, order)) for index, order in enumerate(orders)]
    try:
        responses = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    results, samples = zip(*responses)
    if len({(result['model'], result.get('served_model')) for result in results}) != 1:
        raise _failure(ValueError('repeated_model_identity_mismatch'), None)
    metrics = probability_metrics(candidate_order, [sample['distribution'] for sample in samples],
                                  [result.get('probability_coverage') for result in results])
    counts = Counter(sample['value'] for sample in samples)
    leading = max(counts.values())
    tied = [value for value in candidate_order if counts[value] == leading]
    selection_method = 'majority_vote'
    if len(tied) > 1:
        if metrics['probability_complete']:
            aligned = [_distribution(sample['distribution'], candidate_order)[0] for sample in samples]
            means = {value: statistics.mean(row[value] for row in aligned) for value in tied}
            selected = max(tied, key=lambda value: means[value])
            selection_method = 'vote_tie_mean_probability_then_original_order'
        else:
            selected = tied[0]
            selection_method = 'vote_tie_original_order_partial_probabilities'
    else:
        selected = tied[0]
    representative_index = next(index for index, sample in enumerate(samples) if sample['value'] == selected)
    output = copy.deepcopy(results[representative_index])
    selected_row = next(row for row in output['distribution'] if row['value'] == selected)
    output['label'] = selected_row.get('label', selected)
    output['comparison'] = None
    output.pop('comparison_unavailable', None)
    output['distribution_source'] = 'representative_sample'
    output['representative_sample_index'] = representative_index
    output['candidate_probability_note'] = (output.get('candidate_probability_note', '')
        + ' 当前分布来自支持最终动作的一次真实判断，并非三次平均分布；三次结果按动作 ID 对齐计算稳定性。')
    output['latency_seconds'] = round(time.perf_counter()-began, 6)
    tokens = [result.get('input_tokens') for result in results]
    output['input_tokens'] = sum(tokens) if all(type(value) is int and value >= 0 for value in tokens) else None
    output['decision_stability'] = {'revision': REVISION, 'repeat_count': REPEAT_COUNT,
        'candidate_order': list(candidate_order), 'samples': list(samples), **metrics,
        'agreement_rate': leading/REPEAT_COUNT, 'unanimous': leading == REPEAT_COUNT,
        'selection_method': selection_method, 'variance_ddof': 1, 'js_log_base': 2,
        'js_distance_definition': 'sqrt_jensen_shannon_divergence',
        'representative_sample_index': representative_index,
        'note': '选项顺序扰动下的重复判断一致性；不表示正确率或校准置信度。'}
    return output
