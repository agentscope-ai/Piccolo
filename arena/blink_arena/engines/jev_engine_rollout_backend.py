"""Trainer-neutral tickets around the existing verified engine episode runners.

The backend owns physics, opponents, replay and rewards. The caller supplies
only the action and its actual behavior-policy receipt. No game loop, model
client, tokenizer, optimizer or frontend application is implemented here.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import dataclass, field
import inspect
import json
import math
from pathlib import Path
import random
import re
import time
from typing import Any
import uuid

from jev_engine_registry import get_engine

REVISION = 'jev.rollout.backend.v1'
DECISION_SCHEMA = 'jev.rollout.decision.v1'
RECEIPT_SCHEMA = 'jev.rollout.receipt.v1'
_IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')
_TERMINAL = frozenset(('complete', 'error', 'timeout', 'cancelled'))
_POLICY_FIELDS = frozenset((
    'origin', 'forced', 'policy_version', 'candidate_values', 'candidate_labels',
    'candidate_token_ids', 'input_token_ids', 'selected_index', 'old_probabilities',
    'sampling_epsilon', 'sampling_temperature', 'sampling_uniform_draw',
    'behavior_logprob', 'choice_probability', 'probability_scope',
    'tokenizer_revision', 'prompt_template_revision',
))
_REWARD_FIELDS = (
    'reward_revision', 'reward_discount', 'reward_setting', 'reward_audit',
    'process_rewards', 'terminal_utility', 'episode_utility',
    'training_utility', 'unowned_process_reward', 'process_reward_components',
    'terminal_margin_reward', 'realtime_score', 'scoring_revision', 'terminal_score',
)


class RolloutError(ValueError):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def _json_default(value):
    if isinstance(value, random.Random):
        return {'random_state': value.getstate()}
    raise TypeError('non-JSON engine audit value: ' + type(value).__name__)


def _wire(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False, default=_json_default))


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _identifier(value, name):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise RolloutError(422, 'invalid_' + name)
    return value


@dataclass
class _Ticket:
    ticket_id: str
    request_token: str
    sequence: int
    ordinal: int
    record: dict
    created_at: float
    expires_at: float
    future: asyncio.Future
    status: str = 'pending'
    answer: dict | None = None
    accepted_at: float | None = None
    answer_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    answer_task: asyncio.Task | None = None


@dataclass
class _Session:
    ident: str
    owner: str
    job: dict
    start_body: dict
    created_at: float
    created_at_wall: float = field(default_factory=time.time)
    status: str = 'running'
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    tickets: list = field(default_factory=list)
    journals: list = field(default_factory=list)
    task: asyncio.Task | None = None
    initialization_task: asyncio.Task | None = None
    result: dict | None = None
    cancel_reason: str | None = None
    persisted: bool = False
    serialized_bytes: int = 0
    settlement_task: asyncio.Task | None = None
    journal_tail: asyncio.Task | None = None
    journal_timings: list = field(default_factory=list)


class PolicyBridge:
    """The single callback existing runners already await for student choices."""
    def __init__(self, backend, session):
        self.backend, self.session = backend, session

    @property
    def policy_version(self):
        return self.session.job['policy_version']

    async def policy_action(self, record, episode_id, ordinal):
        if episode_id != self.session.job['episode_id']:
            raise ValueError('runner_episode_identity_changed')
        return await self.backend._decision(self.session, record, ordinal)

    def journal(self, job, event, value):
        if job['episode_id'] != self.session.job['episode_id']:
            raise ValueError('runner_journal_identity_changed')
        self.backend._queue_journal(self.session, event, value)

    async def compute_record(self, operation, *args):
        """Immutable captured input; queue/CPU time still belongs to world time."""
        captured = copy.deepcopy(args)
        submitted = time.monotonic()
        def compute():
            started = time.monotonic()
            result = operation(*captured)
            return result, {'record_cpu_queue_seconds': started-submitted,
                            'record_cpu_seconds': time.monotonic()-started}
        return await self.backend._worker(self.backend._decision_executor,
            self.backend._decision_slot, compute)


class RolloutBackend:
    """In-process service core; runner_factory is async(proxy, job) -> episode.

    A successful runner result must already be replay-verified and settled by
    the authoritative reward contract. Failed/cancelled attempts remain results
    and count in the denominator. storage_dir is an explicit deployment setting;
    it is never inferred from a training checkout or the frontend data tree.
    """
    def __init__(self, runner_factory, *, decision_timeout=90., storage_dir=None, max_active=256,
                 completed_cache_size=64, completed_cache_bytes=64 * 1024 * 1024):
        if not callable(runner_factory):
            raise TypeError('runner_factory must be callable')
        if not _number(decision_timeout) or decision_timeout <= 0:
            raise ValueError('decision_timeout must be positive')
        if type(max_active) is not int or max_active <= 0:
            raise ValueError('max_active must be a positive integer')
        if type(completed_cache_size) is not int or completed_cache_size < 0:
            raise ValueError('completed_cache_size must be a nonnegative integer')
        if type(completed_cache_bytes) is not int or completed_cache_bytes < 0:
            raise ValueError('completed_cache_bytes must be a nonnegative integer')
        if storage_dir is None and (not completed_cache_size or not completed_cache_bytes):
            raise ValueError('zero-cache operation requires durable storage')
        self.runner_factory = runner_factory
        self.decision_timeout = float(decision_timeout)
        self.storage_dir = Path(storage_dir) if storage_dir is not None else None
        self.max_active = max_active
        self.sessions = {}
        self.identities = {}
        self.completed_cache_size = completed_cache_size
        self.completed_cache_bytes = completed_cache_bytes
        self._completed = OrderedDict()
        self._cache_bytes = 0
        self._closed = self._closing = self._storage_fault = False
        self._cpu_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-receipt")
        self._cpu_slot = asyncio.Semaphore(1)
        self._response_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-result")
        self._response_slot = asyncio.Semaphore(1)
        # Keep active-world work away from large completed receipt/replay jobs.
        # Python threads yield the GIL regularly; no unbounded executor backlog.
        self._decision_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jev-decision")
        self._decision_slot = asyncio.Semaphore(2)
        self._journal_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-journal")
        self._journal_slot = asyncio.Semaphore(1)
        self._cpu_pending = set()
        self._worker_count = 0
        self._workers_idle = asyncio.Event()
        self._workers_idle.set()
        self._response_closing = False
        self.store = None
        self.recovery_summary = {'restored': 0, 'interrupted': 0}
        if self.storage_dir is not None:
            from jev_engine_rollout_store import RolloutStore
            self.store = RolloutStore(self.storage_dir)
            try:
                self.recovery_summary = self.store.recover(self._recovery_receipt)
            except BaseException:
                self.store.close()
                raise

    @staticmethod
    def _owner(owner):
        if not isinstance(owner, str) or not owner or len(owner) > 512:
            raise RolloutError(422, 'invalid_rollout_owner')
        return owner

    @staticmethod
    def _metadata(session):
        return {'schema_version': 'jev.rollout.storage.v1', 'rollout_id': session.ident,
                'owner': session.owner, 'job': session.job, 'start_body': session.start_body,
                'created_at': session.created_at_wall}

    @staticmethod
    def _recovery_receipt(meta, reason, decision_count):
        return {'schema_version': RECEIPT_SCHEMA, 'backend_revision': REVISION,
                'rollout_id': meta['rollout_id'], **meta['job'], 'status': 'error', 'outcome': 'error',
                'error_type': reason, 'trace': [], 'replay_events': [], 'process_rewards': [],
                'terminal_utility': None, 'replay_verified': False, 'on_policy': False,
                'policy_origin': 'student', 'counts_in_denominator': True,
                'decision_requests': decision_count, 'decisions': 0, 'trainable_decisions': 0,
                'rule_takeover_count': 0, 'seconds': max(0., time.time() - meta['created_at']),
                'recovered_after_restart': True}

    async def _worker(self, executor, slot, operation, *args, **kwargs):
        """Submit only after admission; cancellation cannot release work's slot early."""
        self._worker_count += 1
        self._workers_idle.clear()
        def retired():
            self._worker_count -= 1
            if self._worker_count == 0:
                self._workers_idle.set()
        try:
            await slot.acquire()
        except BaseException:
            retired()
            raise
        try:
            future = asyncio.get_running_loop().run_in_executor(
                executor, lambda: operation(*args, **kwargs))
        except BaseException:
            slot.release()
            retired()
            raise
        self._cpu_pending.add(future)
        def done(task):
            self._cpu_pending.discard(task)
            slot.release()
            retired()
            if not task.cancelled():
                task.exception()
        future.add_done_callback(done)
        return await asyncio.shield(future)

    async def _cpu(self, operation, *args, **kwargs):
        return await self._worker(self._cpu_executor, self._cpu_slot, operation, *args, **kwargs)

    async def _response_cpu(self, operation, *args, **kwargs):
        # A completed result must not queue behind up to32 large terminal
        # publications and consume the caller's180s HTTP deadline.
        if self._response_closing or self._closed:
            raise RolloutError(503, 'rollout_backend_closed')
        return await self._worker(self._response_executor, self._response_slot, operation, *args, **kwargs)

    async def encode_response(self, value, status_code=200):
        # Starlette's JSONResponse constructor encodes synchronously.
        from fastapi.responses import JSONResponse
        return await self._response_cpu(JSONResponse, value, status_code=status_code)

    def _cache_terminal(self, session):
        if self.store is None or not session.persisted:
            return
        # Exact old replies remain in the journal, fetched one ticket at a time.
        session.tickets.clear()
        session.journals.clear()
        session.task = None
        old_size = self._completed.pop(session.ident, 0)
        self._cache_bytes -= old_size
        size = session.serialized_bytes if session.result is not None else 0
        size += len(json.dumps(session.job)) + len(json.dumps(session.start_body))
        self.sessions[session.ident] = session
        self.identities[(session.owner, session.job['episode_id'])] = session.ident
        self._completed[session.ident] = size
        self._cache_bytes += size
        while (len(self._completed) > self.completed_cache_size
               or self._cache_bytes > self.completed_cache_bytes):
            ident, size = self._completed.popitem(last=False)
            cached = self.sessions.pop(ident)
            self.identities.pop((cached.owner, cached.job['episode_id']), None)
            self._cache_bytes -= size

    def cache_info(self):
        completed = len(self._completed) if self.store is not None else sum(
            s.status in _TERMINAL for s in self.sessions.values())
        size = self._cache_bytes if self.store is not None else sum(
            s.serialized_bytes for s in self.sessions.values() if s.result is not None)
        return {'active': sum(s.status not in _TERMINAL for s in self.sessions.values()),
                'completed': completed, 'serialized_bytes': size,
                'max_completed': self.completed_cache_size,
                'max_serialized_bytes': self.completed_cache_bytes,
                'durable': self.store is not None, 'storage_fault': self._storage_fault}

    def _journal(self, session, event, value):
        if isinstance(value, dict) and 'error' in value:
            # Provider exceptions can contain URLs or credential-bearing request
            # details. Keep an error category, never a copied exception message.
            value = {key: item for key, item in value.items() if key != 'error'}
            value.setdefault('error_type', 'runner_error')
        row = {'event': event, 'time': time.time(), 'value': _wire(value)}
        if self.store is not None:
            self.store.append_journal(session.ident, row)
        else:
            # Disk-backed runs must not retain a second in-memory copy of every
            # private engine state. In-memory audit is useful for small fixtures.
            session.journals.append(row)

    def _queue_journal(self, session, event, value):
        # Existing runner callbacks are synchronous. Enqueue an immutable copy,
        # then drain before exposing a ticket, accepting an answer or settlement.
        # A failed predecessor prevents later rows from hiding an audit gap.
        previous, frozen = session.journal_tail, copy.deepcopy(value)
        enqueued = time.monotonic()
        def operation():
            started = time.monotonic()
            self._journal(session, event, frozen)
            return {'event': event, 'ordinal': frozen.get('ordinal') if isinstance(frozen,dict) else None,
                    'journal_queue_seconds': started-enqueued,
                    'journal_write_seconds': time.monotonic()-started}
        async def write():
            if previous is not None:
                await asyncio.shield(previous)
            timing = await self._worker(self._journal_executor, self._journal_slot, operation)
            session.journal_timings.append(timing)
        task = asyncio.create_task(write())
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        session.journal_tail = task
        return task

    async def _journal_async(self, session, event, value):
        await asyncio.shield(self._queue_journal(session, event, value))

    async def _drain_journal(self, session):
        if session.journal_tail is not None:
            await asyncio.shield(session.journal_tail)

    def _require(self, ident, owner):
        self._owner(owner)
        if self._closed:
            raise RolloutError(503, 'rollout_backend_closed')
        session = self.sessions.get(ident)
        if session is None and self.store is not None:
            row = self.store.get(ident, owner)
            if row is not None:
                meta = row['metadata']
                session = _Session(ident, owner, meta['job'], meta['start_body'],
                    time.monotonic() - max(0., time.time() - meta['created_at']),
                    created_at_wall=meta['created_at'], status=row['status'], persisted=True)
                self._cache_terminal(session)
        if session is None or session.owner != owner:
            raise RolloutError(404, 'rollout_not_found')
        if ident in self._completed:
            self._completed.move_to_end(ident)
        return session

    @staticmethod
    def _start_job(body):
        allowed = {'episode_id', 'game', 'seed', 'policy_version', 'request_token',
                   'group_id', 'trial', 'mode', 'side', 'max_decisions'}
        if not isinstance(body, dict) or set(body) - allowed:
            raise RolloutError(422, 'unknown_start_fields')
        for name in ('episode_id', 'game', 'policy_version', 'request_token'):
            _identifier(body.get(name), name)
        if type(body.get('seed')) is not int or not 0 <= body['seed'] <= 4294967295:
            raise RolloutError(422, 'invalid_seed')
        try:
            engine = get_engine(body['game'])
        except ValueError as error:
            raise RolloutError(422, 'unknown_game') from error
        mode = body.get('mode', engine.opponent_modes[0])
        if mode not in engine.opponent_modes:
            raise RolloutError(422, 'invalid_opponent_mode')
        limit = body.get('max_decisions', engine.limit)
        if type(limit) is not int or not 1 <= limit <= engine.limit:
            raise RolloutError(422, 'invalid_decision_limit')
        trial = body.get('trial', 0)
        if type(trial) is not int or trial < 0:
            raise RolloutError(422, 'invalid_trial')
        group_id = _identifier(body.get('group_id', body['episode_id']), 'group_id')
        side = body.get('side', 'X' if engine.family == 'board' else 0)
        valid_sides = ('X', 'O') if engine.family == 'board' else tuple(range(engine.seat_count))
        if type(side) is not (str if engine.family == 'board' else int) or side not in valid_sides:
            raise RolloutError(422, 'invalid_side')
        return {key: body[key] for key in ('episode_id', 'game', 'seed', 'policy_version')} | {
            'kind': body['game'], 'group_id': group_id, 'trial': trial,
            'mode': mode, 'side': side, 'max_decisions': limit}

    async def start(self, body, owner='local'):
        self._owner(owner)
        if self._closed or self._closing:
            raise RolloutError(503, 'rollout_backend_closed')
        job = self._start_job(body)
        identity = (owner, job['episode_id'])
        existing = self.identities.get(identity)
        if existing is None and self.store is not None:
            stored = self.store.identity(owner, job['episode_id'])
            existing = stored['ident'] if stored is not None else None
        if existing:
            session = self._require(existing, owner)
            if session.start_body != _wire(body):
                raise RolloutError(409, 'episode_identity_reused_with_different_request')
            if session.initialization_task is not None:
                await asyncio.shield(session.initialization_task)
            return {'schema_version': REVISION, 'rollout_id': existing,
                    'episode_id': job['episode_id'], 'status': session.status, 'duplicate': True}
        if self._storage_fault:
            raise RolloutError(503, 'rollout_storage_unavailable')
        if self.store is None and (len(self.sessions) >= self.completed_cache_size or
                sum(s.serialized_bytes for s in self.sessions.values() if s.result is not None)
                >= self.completed_cache_bytes):
            raise RolloutError(429, 'in_memory_history_limit_requires_storage')
        if sum(s.status not in _TERMINAL for s in self.sessions.values()) >= self.max_active:
            raise RolloutError(429, 'active_rollout_limit')
        ident = uuid.uuid4().hex
        session = _Session(ident, owner, job, _wire(body), time.monotonic())
        self.sessions[ident] = session
        self.identities[identity] = ident
        # Identity registration and task ownership precede the first await.
        # An HTTP disconnect must not orphan a registered, never-started world.
        session.initialization_task = asyncio.create_task(self._initialize(session))
        await asyncio.shield(session.initialization_task)
        return {'schema_version': REVISION, 'rollout_id': ident, 'episode_id': job['episode_id'],
                'status': session.status, 'duplicate': False}

    async def _initialize(self, session):
        try:
            if self.store is not None:
                self.store.create(self._metadata(session))
            await self._journal_async(session, 'started', {'job': session.job, 'backend_revision': REVISION})
        except Exception as error:
            session.result = self._failed_receipt(session, 'error', type(error).__name__)
            await self._finish(session)
        else:
            if session.status == 'cancelling' or self._closing:
                session.result = self._failed_receipt(
                    session, 'cancelled', session.cancel_reason or 'backend_shutdown')
                await self._finish(session)
            else:
                session.task = asyncio.create_task(self._run(session))

    async def _decision(self, session, record, ordinal):
        if session.status != 'running':
            raise asyncio.CancelledError
        if type(ordinal) is not int or ordinal < 0:
            raise ValueError('invalid_decision_ordinal')
        record = _wire(record)
        if record.get('schema_version') != 'jev.training.v1':
            raise ValueError('runner_must_supply_original_training_record')
        questions = record.get('questions', {})
        if list(questions) != ['decision'] or questions['decision'].get('type') != 'choice':
            raise ValueError('rollout_requires_one_joint_decision_choice')
        question = questions['decision']
        candidates = question.get('criteria', {})
        order = question.get('option_order', list(candidates))
        if not candidates or len(set(order)) != len(order) or set(order) != set(candidates):
            raise ValueError('invalid_captured_candidate_order')
        if len(candidates) == 1:
            return next(iter(candidates)), {'forced': True, 'origin': 'deterministic_execution'}
        if any(t.ordinal == ordinal for t in session.tickets):
            raise ValueError('duplicate_runner_decision_ordinal')
        if len(session.tickets) >= session.job['max_decisions']:
            raise ValueError('runner_exceeded_decision_limit')
        now = time.monotonic()
        ticket = _Ticket(uuid.uuid4().hex, uuid.uuid4().hex, len(session.tickets), ordinal,
                         record, now, now + self.decision_timeout, asyncio.get_running_loop().create_future())
        ticket.status = 'publishing'
        session.tickets.append(ticket)
        await self._journal_async(session, 'decision_captured', {'ordinal': ordinal, 'sequence': ticket.sequence,
            'record': record, 'ticket_id': ticket.ticket_id, 'request_token': ticket.request_token,
            'timeout_seconds': self.decision_timeout})
        if session.status != 'running':
            raise asyncio.CancelledError
        ticket.status = 'pending'
        session.changed.set()
        try:
            answer = await asyncio.wait_for(asyncio.shield(ticket.future),
                                           max(0., ticket.expires_at-time.monotonic()))
            return answer['action'], copy.deepcopy(answer['policy'])
        except asyncio.TimeoutError:
            # An answer durably accepted before the deadline wins even when
            # loop scheduling delays the wait_for(shield(...)) continuation.
            # Late answers are still rejected in answer(); no deadline changes.
            if ticket.answer_task is not None:
                # Preserve the prior contract: a reply admitted before the
                # deadline can finish its durable write; no early ack/execute.
                try:
                    await asyncio.shield(ticket.answer_task)
                except Exception:
                    pass
            if (ticket.answer is not None and ticket.accepted_at is not None
                    and ticket.accepted_at < ticket.expires_at):
                return ticket.answer['action'], copy.deepcopy(ticket.answer['policy'])
            ticket.status = 'expired'
            ticket.future.cancel()
            await self._journal_async(session, 'decision_expired', {'ordinal': ordinal, 'ticket_id': ticket.ticket_id})
            session.changed.set()
            raise
        except asyncio.CancelledError:
            ticket.status = 'cancelled'
            ticket.future.cancel()
            session.changed.set()
            raise

    def _ticket_view(self, session, ticket):
        question = ticket.record['questions']['decision']
        return {'ticket_id': ticket.ticket_id, 'request_token': ticket.request_token,
                'episode_id': session.job['episode_id'], 'policy_version': session.job['policy_version'],
                'sequence': ticket.sequence, 'ordinal': ticket.ordinal,
                'record': copy.deepcopy(ticket.record),
                'candidate_values': list(question.get('option_order', question['criteria'])),
                'legal_actions': copy.deepcopy(question['criteria']),
                'expires_in_seconds': max(0., ticket.expires_at - time.monotonic()),
                'clock': get_engine(session.job['kind']).clock,
                'inference_pauses_environment': get_engine(session.job['kind']).clock != 'realtime'}

    async def next_decision(self, ident, owner='local', after=-1, timeout=25.):
        session = self._require(ident, owner)
        if type(after) is not int or after < -1 or not _number(timeout) or not 0 <= timeout <= 30:
            raise RolloutError(422, 'invalid_poll_parameters')
        deadline = time.monotonic() + timeout
        while True:
            pending = next((t for t in session.tickets if t.sequence > after and t.status == 'pending'
                            and time.monotonic() < t.expires_at), None)
            if pending is not None:
                return {'schema_version': DECISION_SCHEMA, 'rollout_id': ident,
                        'status': 'awaiting_action', 'ticket': self._ticket_view(session, pending)}
            if session.status in _TERMINAL:
                return {'schema_version': DECISION_SCHEMA, 'rollout_id': ident,
                        'status': session.status, 'ticket': None, 'result_available': True}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {'schema_version': DECISION_SCHEMA, 'rollout_id': ident,
                        'status': session.status, 'ticket': None, 'result_available': False}
            session.changed.clear()
            try:
                await asyncio.wait_for(session.changed.wait(), remaining)
            except asyncio.TimeoutError:
                return {'schema_version': DECISION_SCHEMA, 'rollout_id': ident,
                        'status': session.status, 'ticket': None, 'result_available': False}

    @staticmethod
    def _validate_policy(policy, ticket, action, version):
        if not isinstance(policy, dict) or set(policy) - _POLICY_FIELDS:
            raise RolloutError(422, 'unknown_policy_fields_or_client_reward')
        if policy.get('origin', 'student_model') != 'student_model' or policy.get('forced', False):
            raise RolloutError(422, 'ticket_requires_student_behavior_policy')
        if policy.get('policy_version', version) != version:
            raise RolloutError(409, 'policy_version_changed')
        values, probs, index = (policy.get(k) for k in ('candidate_values', 'old_probabilities', 'selected_index'))
        allowed = ticket.record['questions']['decision']['criteria']
        order = ticket.record['questions']['decision'].get('option_order', list(allowed))
        if (not isinstance(values, list) or any(not isinstance(v, str) for v in values)
                or len(set(values)) != len(values) or values != list(order)
                or not isinstance(probs, list) or len(probs) != len(values)
                or type(index) is not int or not 0 <= index < len(values) or values[index] != action):
            raise RolloutError(422, 'behavior_choice_mapping_mismatch')
        if (any(not _number(p) or not 0 <= p <= 1 for p in probs)
                or not math.isclose(math.fsum(probs), 1., rel_tol=0., abs_tol=1e-5)
                or probs[index] <= 0):
            raise RolloutError(422, 'invalid_behavior_probabilities')
        for key in ('input_token_ids', 'candidate_token_ids'):
            if key in policy and (not isinstance(policy[key], list) or
                    any(type(t) is not int or t < 0 for t in policy[key])):
                raise RolloutError(422, 'invalid_' + key)
        tokens = policy.get('candidate_token_ids')
        if tokens is not None and (len(tokens) != len(values) or len(set(tokens)) != len(tokens)):
            raise RolloutError(422, 'ambiguous_candidate_token_mapping')
        labels = policy.get('candidate_labels')
        if labels is not None and (not isinstance(labels, list) or len(labels) != len(values)
                or any(not isinstance(v, str) for v in labels) or len(set(labels)) != len(labels)):
            raise RolloutError(422, 'invalid_candidate_labels')
        for key in ('sampling_epsilon', 'sampling_uniform_draw'):
            if key in policy and (not _number(policy[key]) or not 0 <= policy[key] <= 1):
                raise RolloutError(422, 'invalid_' + key)
        if 'sampling_temperature' in policy and (not _number(policy['sampling_temperature']) or policy['sampling_temperature'] <= 0):
            raise RolloutError(422, 'invalid_sampling_temperature')
        if 'choice_probability' in policy and (not _number(policy['choice_probability']) or
                not math.isclose(policy['choice_probability'], probs[index], abs_tol=1e-8)):
            raise RolloutError(422, 'joint_choice_probability_mismatch')
        if 'behavior_logprob' in policy and (not _number(policy['behavior_logprob']) or
                not math.isclose(policy['behavior_logprob'], math.log(probs[index]), abs_tol=1e-6)):
            raise RolloutError(422, 'behavior_logprob_mismatch')
        if policy.get('probability_scope', 'one_actual_decision_choice') != 'one_actual_decision_choice':
            raise RolloutError(422, 'unsupported_joint_probability_scope')
        result = _wire(policy)
        result.update(forced=False, origin='student_model', policy_version=version)
        return result

    async def answer(self, ident, body, owner='local'):
        session = self._require(ident, owner)
        if not isinstance(body, dict) or set(body) != {'ticket_id', 'request_token', 'policy_version', 'action', 'policy'}:
            raise RolloutError(422, 'invalid_answer_fields')
        ticket = next((t for t in session.tickets if t.ticket_id == body['ticket_id']), None)
        if ticket is None and session.status in _TERMINAL and self.store is not None:
            stored = await self._response_cpu(self.store.ticket, ident, body['ticket_id'])
            if stored is not None and stored.get('request_token'):
                ticket = _Ticket(stored['ticket_id'], stored['request_token'], stored['sequence'],
                    stored['ordinal'], stored['record'], 0., 0., None,
                    status='finished', answer=stored['answer'])
        if ticket is None or body['request_token'] != ticket.request_token:
            raise RolloutError(409, 'unknown_or_stale_decision_token')
        if body['policy_version'] != session.job['policy_version']:
            raise RolloutError(409, 'policy_version_changed')
        policy = self._validate_policy(body['policy'], ticket, body['action'], body['policy_version'])
        normalized = {'action': body['action'], 'policy': policy}
        async with ticket.answer_lock:
            if ticket.answer_task is not None:
                await asyncio.shield(ticket.answer_task)
            if ticket.answer is not None:
                if ticket.answer != normalized:
                    raise RolloutError(409, 'decision_already_answered_differently')
                return {'accepted': True, 'duplicate': True, 'ticket_id': ticket.ticket_id,
                        'execution_status': 'see_episode_result'}
            accepted_at = time.monotonic()
            if session.status != 'running' or ticket.status != 'pending' or accepted_at >= ticket.expires_at:
                raise RolloutError(409, 'decision_expired_or_episode_finished')
            async def commit():
                try:
                    await self._journal_async(session, 'policy_answer', {
                        'ordinal': ticket.ordinal, 'ticket_id': ticket.ticket_id,
                        'action': body['action'], 'policy': policy,
                        'audit_timing': {'answer_received_monotonic': accepted_at}})
                except Exception as error:
                    raise RolloutError(503, 'policy_answer_audit_unavailable') from error
                if session.status != 'running' or ticket.future.cancelled():
                    raise RolloutError(409, 'decision_expired_or_episode_finished')
                ticket.answer, ticket.status, ticket.accepted_at = normalized, 'answered', accepted_at
                ticket.future.set_result(normalized)
                session.changed.set()
            ticket.answer_task = asyncio.create_task(commit())
            ticket.answer_task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            await asyncio.shield(ticket.answer_task)
            return {'accepted': True, 'duplicate': False, 'ticket_id': ticket.ticket_id,
                    'execution_status': 'pending_engine_commit'}

    @staticmethod
    def _state_view(engine, state):
        if state is None:
            return None
        if engine.family in ('agent', 'social', 'probability'):
            # After a turn, public() may expose the *next* actor's private hand.
            # The learner receives its exact record plus an execution summary;
            # private engine snapshots remain only in the server replay audit.
            keys = ('kind', 'game', 'steps', 'frame', 'elapsed', 'outcome', 'score',
                    'turn', 'phase', 'event', 'control', 'execution_status', 'rule_takeover_count')
            return {**{key: copy.deepcopy(state[key]) for key in keys if key in state},
                    'state_view': 'public_execution_summary'}
        return _wire(engine.public(state))

    def _receipt(self, session, episode):
        if not isinstance(episode, dict):
            raise ValueError('runner_returned_no_episode')
        status = episode.get('status', 'complete')
        if status not in _TERMINAL:
            raise ValueError('runner_returned_nonterminal_status')
        for key in ('episode_id', 'kind', 'game', 'seed', 'group_id', 'trial', 'mode', 'side', 'policy_version'):
            if key in episode and episode[key] != session.job[key]:
                raise ValueError('runner_changed_episode_condition_' + key)
        engine = get_engine(session.job['kind'])
        raw_trace = episode.get('trace', [])
        rewards = episode.get('process_rewards')
        verified = episode.get('replay_verified') is True
        if status == 'complete' and (not verified or not isinstance(rewards, list)
                or len(rewards) != len(raw_trace) or any(not _number(v) for v in rewards)
                or not _number(episode.get('terminal_utility'))):
            raise ValueError('complete_episode_requires_verified_authoritative_rewards')
        tickets = {t.ordinal: t for t in session.tickets}
        trace, used = [], set()
        for original in raw_trace:
            row = _wire(original)
            if not row.get('action_applied', row.get('applied', True)):
                raise ValueError('unexecuted_choice_in_training_trace')
            policy = row.get('policy', {})
            if not policy.get('forced'):
                ticket = tickets.get(row.get('ordinal'))
                if ticket is None or ticket.answer is None or ticket.ordinal in used:
                    raise ValueError('trace_has_no_unique_accepted_policy_ticket')
                if (row.get('record') != ticket.record or row.get('action') != ticket.answer['action']
                        or any(policy.get(k) != v for k, v in ticket.answer['policy'].items())):
                    raise ValueError('executed_trace_differs_from_captured_policy_input')
                used.add(ticket.ordinal)
            else:
                options = row.get('record', {}).get('questions', {}).get('decision', {}).get('criteria', {})
                if len(options) != 1 or row.get('action') != next(iter(options)):
                    raise ValueError('forced_execution_is_not_a_single_legal_choice')
            safe = {key: row[key] for key in ('ordinal', 'record', 'action', 'policy', 'actor',
                    'probability_scope', 'choice_probability', 'credit_revision', 'clock_contract', 'control_ownership',
                    'waiting_seconds', 'pre_decision_seconds', 'post_action_seconds', 'discard_reason',
                    'latency_breakdown') if key in row}
            safe.update(applied=True, action_applied=True)
            for key in ('before_state', 'arrival_state', 'after_state', 'credit_before_state', 'credit_after_state'):
                if key in original:
                    safe[key] = self._state_view(engine, original[key])
            trace.append(safe)
        result = {'schema_version': RECEIPT_SCHEMA, 'backend_revision': REVISION,
                  'rollout_id': session.ident, **session.job, 'status': status,
                  'outcome': episode.get('outcome', 'error'), 'trace': trace,
                  'replay_verified': verified,
                  'policy_origin': episode.get('policy_origin', 'student'),
                  'on_policy': status == 'complete' and verified and episode.get('on_policy', True)
                               and episode.get('policy_origin', 'student') == 'student',
                  'rule_takeover_count': int(episode.get('rule_takeover_count', 0)),
                  'decisions': len(trace), 'trainable_decisions': sum(not t['policy'].get('forced') for t in trace),
                  'decision_requests': len(session.tickets),
                  'discarded_replies': len([t for t in session.tickets if t.answer is not None and t.ordinal not in used]),
                  'seconds': time.monotonic() - session.created_at,
                  'counts_in_denominator': True, 'engine': engine.descriptor()}
        for key in _REWARD_FIELDS:
            if key in episode:
                result[key] = _wire(episode[key])
        for key in ('real_time_seconds', 'simulation_seconds', 'terminal_clock', 'clock_contract',
                    'inference_world_paused', 'unattributed_initial_seconds', 'forced_actions',
                    'deterministic_student_actions', 'deterministic_opponent_actions', 'environment_generation',
                    'engine_runtime', 'engine_viewport', 'replay_validation', 'native_zero_controlled_terminal',
                    'reward_export_prohibited', 'error_type'):
            if key in episode:
                result[key] = _wire(episode[key])
        if 'error' in episode:
            result.setdefault('error_type', 'runner_error')
        for key in ('initial_state', 'final_state'):
            if key in episode:
                result[key] = self._state_view(engine, episode[key])
        result['replay_events'] = []
        for event in episode.get('replay_events', []):
            safe = {key: _wire(event[key]) for key in ('ordinal', 'record', 'policy', 'action', 'action_applied', 'discard_reason',
                    'reason', 'waiting_seconds', 'post_action_seconds', 'clock_contract', 'status', 'error_type',
                    'latency_breakdown') if key in event}
            for key in ('before_state', 'arrival_state', 'after_state'):
                if key in event:
                    safe[key] = self._state_view(engine, event[key])
            result['replay_events'].append(safe)
        return result

    def _failed_receipt(self, session, status, reason):
        return {'schema_version': RECEIPT_SCHEMA, 'backend_revision': REVISION,
                'rollout_id': session.ident, **session.job, 'status': status, 'outcome': status,
                'error_type': reason, 'trace': [], 'replay_events': [], 'process_rewards': [],
                'terminal_utility': None, 'replay_verified': False, 'on_policy': False,
                'policy_origin': 'student', 'counts_in_denominator': True,
                'decision_requests': len(session.tickets), 'decisions': 0, 'trainable_decisions': 0,
                'rule_takeover_count': 0, 'seconds': time.monotonic() - session.created_at}

    async def _settle(self, session, raw):
        # Freeze the terminal input before yielding: no late ticket can change it.
        session.status = 'settling'
        for ticket in session.tickets:
            if ticket.status in ('pending', 'publishing'):
                ticket.status = 'cancelled'
                ticket.future.cancel()
        try:
            session.result = await self._cpu(self._receipt, session, raw)
        except Exception as error:
            session.result = self._failed_receipt(session, 'error', type(error).__name__)
        await self._finish(session, raw)

    async def _run(self, session):
        raw = None
        try:
            raw = await self.runner_factory(PolicyBridge(self, session), copy.deepcopy(session.job))
            session.status = 'settling'
            session.settlement_task = asyncio.create_task(self._settle(session, raw))
            await asyncio.shield(session.settlement_task)
        except asyncio.CancelledError:
            if session.settlement_task is not None:
                # Completed physics/reward settlement is immutable. Finish its
                # audit before shutdown; never leave a worker writing into a
                # closed store or label completed work as a fresh cancelled game.
                await asyncio.shield(session.settlement_task)
            else:
                session.result = self._failed_receipt(session, 'cancelled', session.cancel_reason or 'cancelled')
        except asyncio.TimeoutError:
            session.result = self._failed_receipt(session, 'timeout', 'policy_timeout')
        except Exception as error:
            session.result = self._failed_receipt(session, 'error', type(error).__name__)
        finally:
            if session.settlement_task is None:
                if session.result is None:
                    session.result = self._failed_receipt(session, 'error', 'runner_terminated_without_result')
                await self._finish(session, raw)

    async def _finish(self, session, raw=None):
        session.status = 'settling'
        for ticket in session.tickets:
            if ticket.status in ('pending', 'publishing'):
                ticket.status = 'cancelled'
                ticket.future.cancel()
        try:
            await self._drain_journal(session)
            session.result['backend_timing'] = {
                'revision': 'jev.backend-latency.v1',
                'journal_writes': copy.deepcopy(session.journal_timings),
                'scope': 'audit only; never model input or reward'}
            if self.store is not None:
                safe_raw = {key: value for key, value in raw.items() if key != 'error'} if raw is not None else None
                meta = self._metadata(session)
                # SQLite remains on its owning event-loop thread. Only JSON
                # projection, encoding and durable file writes leave that thread.
                self.store.prepare_save(meta, session.result)
                path = await self._cpu(self.store.publish_result, meta, session.result,
                                       safe_raw, default=_json_default)
                self.store.commit_result(meta, session.result, path)
                session.serialized_bytes = path.stat().st_size
                session.persisted = True
            else:
                session.serialized_bytes = await self._cpu(
                    lambda: len(json.dumps(session.result, ensure_ascii=False).encode('utf-8')))
        except Exception as error:
            session.result.update(status='error', on_policy=False, persistence_error_type=type(error).__name__)
            try:
                meta = self._metadata(session)
                self.store.prepare_save(meta, session.result)
                session.result, path = await self._cpu(
                    self.store.publish_failure, meta, session.result)
                self.store.commit_result(meta, session.result, path)
                session.serialized_bytes = path.stat().st_size
                session.persisted = True
            except Exception:
                self._storage_fault = True
        finally:
            session.status = session.result['status']
            session.changed.set()
            self._cache_terminal(session)

    async def result(self, ident, owner='local'):
        session = self._require(ident, owner)
        if session.status == 'settling':
            return {'schema_version': RECEIPT_SCHEMA, 'rollout_id': ident,
                    'status': 'running', 'result_available': False}
        if session.result is None and session.persisted:
            try:
                stored = self.store.get(ident, owner)
                session.result = await self._response_cpu(self.store.load_result, stored)
                session.serialized_bytes = (self.store.root / stored['receipt_path']).stat().st_size
            except (OSError, ValueError, TypeError):
                raise RolloutError(503, 'persisted_rollout_receipt_unavailable') from None
            self._cache_terminal(session)
        if session.result is None:
            return {'schema_version': RECEIPT_SCHEMA, 'rollout_id': ident,
                    'status': session.status, 'result_available': False}
        return await self._response_cpu(copy.deepcopy, session.result)

    async def list_results(self, owner='local', cursor=0, limit=50):
        """Small summaries only; fetch an individual full receipt with result()."""
        self._owner(owner)
        if self._closed:
            raise RolloutError(503, 'rollout_backend_closed')
        if type(cursor) is not int or cursor < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise RolloutError(422, 'invalid_result_page')
        if self.store is not None:
            if self._storage_fault and any(
                    self.store.get(s.ident, owner) is None
                    for s in self.sessions.values() if s.owner == owner):
                raise RolloutError(503, 'rollout_history_incomplete_storage_unavailable')
            page = self.store.page(owner, cursor, limit)
            for item in page['items']:
                resident = self.sessions.get(item['rollout_id'])
                if resident is not None:
                    item.update(status=resident.status,
                                outcome=(resident.result or {}).get('outcome'),
                                result_available=resident.result is not None or resident.persisted)
        else:
            owned = [s for s in self.sessions.values() if s.owner == owner]
            page = {'items': [{'rollout_id': s.ident, **s.job, 'status': s.status,
                              'outcome': (s.result or {}).get('outcome'), 'counts_in_denominator': True,
                              'result_available': s.result is not None} for s in owned[cursor:cursor+limit]],
                    'total': len(owned), 'next_cursor': cursor+limit if cursor+limit < len(owned) else None}
        return {'schema_version': 'jev.rollout.page.v1', **page}

    async def cancel(self, ident, reason='cancelled_by_client', owner='local'):
        session = self._require(ident, owner)
        if not isinstance(reason, str) or not _IDENTIFIER.fullmatch(reason):
            raise RolloutError(422, 'invalid_cancel_reason')
        if session.status in _TERMINAL:
            return await self.result(ident, owner)
        session.cancel_reason = reason
        if session.status == 'settling':
            return {'schema_version': RECEIPT_SCHEMA, 'rollout_id': ident,
                    'status': 'running', 'result_available': False}
        session.status = 'cancelling'
        if session.initialization_task is not None and not session.initialization_task.done():
            # Do not cancel an admitted durable startup write. The initializer
            # sees 'cancelling' and settles without entering the runner.
            try:
                await asyncio.wait_for(asyncio.shield(session.initialization_task), 5.)
            except asyncio.TimeoutError:
                return {'schema_version': RECEIPT_SCHEMA, 'rollout_id': ident,
                        'status': 'cancelling', 'result_available': False}
            if session.status in _TERMINAL:
                return await self.result(ident, owner)
        session.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(session.task), 5.)
        except asyncio.TimeoutError:
            return {'schema_version': RECEIPT_SCHEMA, 'rollout_id': ident,
                    'status': 'cancelling', 'result_available': False}
        except asyncio.CancelledError:
            # A task cancelled before its first event-loop turn has not entered
            # _run's finally block; still retain this attempted episode.
            if session.result is None:
                session.result = self._failed_receipt(session, 'cancelled', reason)
                await self._finish(session)
        return await self.result(ident, owner)

    async def close(self):
        if self._closed:
            return
        self._closing = True
        for session in list(self.sessions.values()):
            if session.status not in _TERMINAL:
                await self.cancel(session.ident, 'backend_shutdown', session.owner)
        initializing = [s.initialization_task for s in self.sessions.values()
                        if s.initialization_task is not None and not s.initialization_task.done()]
        if initializing:
            await asyncio.gather(*(asyncio.shield(task) for task in initializing))
        settling = [s.settlement_task for s in self.sessions.values()
                    if s.settlement_task is not None and not s.settlement_task.done()]
        if settling:
            await asyncio.gather(*(asyncio.shield(task) for task in settling))
        self._response_closing = True
        # Count both admitted waiters and submitted futures; a snapshot can
        # miss the next worker submitted when a completed job releases its slot.
        await self._workers_idle.wait()
        if any(s.task is not None and not s.task.done() for s in self.sessions.values()):
            raise RuntimeError('rollout_tasks_did_not_stop_storage_lock_retained')
        if self.store is not None:
            self.store.close()
        self._cpu_executor.shutdown(wait=False)
        self._response_executor.shutdown(wait=False)
        self._decision_executor.shutdown(wait=False)
        self._journal_executor.shutdown(wait=False)
        self._closed = True


def install(app, prefix, backend, *, owner_resolver=None):
    """Add rollout and paginated history routes to a FastAPI app; no UI dependency.

    owner_resolver(request) uses the host's existing authentication/session
    identity. With no resolver the service is intended for a trusted private
    training network. This module never accepts model endpoints or credentials.
    """
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    async def owner(request):
        value = owner_resolver(request) if owner_resolver else 'local'
        return await value if inspect.isawaitable(value) else value

    async def call(operation):
        try:
            return await operation
        except RolloutError as error:
            raise HTTPException(error.status_code, error.detail) from None

    async def start(body: dict, request):
        return await call(backend.start(body, await owner(request)))

    async def listing(request, cursor: int = 0, limit: int = 50):
        return await call(backend.list_results(await owner(request), cursor, limit))

    async def next_decision(ident: str, request, after: int = -1, timeout: float = 25.):
        return await call(backend.next_decision(ident, await owner(request), after, timeout))

    async def answer(ident: str, body: dict, request):
        return await call(backend.answer(ident, body, await owner(request)))

    async def result(ident: str, request):
        value = await call(backend.result(ident, await owner(request)))
        return await backend.encode_response(value, status_code=202 if value.get('result_available') is False else 200)

    async def cancel(ident: str, body: dict, request):
        if set(body) - {'reason'}:
            raise HTTPException(422, 'invalid_cancel_fields')
        value = await call(backend.cancel(ident, body.get('reason', 'cancelled_by_client'), await owner(request)))
        return await backend.encode_response(value)

    # Keep the core importable without FastAPI. Actual Request annotations must
    # be objects (not locally scoped forward-reference strings) for route wiring.
    for function in (start, listing, next_decision, answer, result, cancel):
        function.__annotations__['request'] = Request
    base = prefix.rstrip('/') + '/api/v1/rollouts'
    app.add_api_route(base, start, methods=['POST'], status_code=201)
    app.add_api_route(base, listing, methods=['GET'])
    app.add_api_route(base + '/{ident}/next-decision', next_decision, methods=['GET'])
    app.add_api_route(base + '/{ident}/answers', answer, methods=['POST'])
    app.add_api_route(base + '/{ident}/result', result, methods=['GET'])
    app.add_api_route(base + '/{ident}/cancel', cancel, methods=['POST'])
    return backend
