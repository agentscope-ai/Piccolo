"""Private append-only rollout artifacts and a rebuildable, disk-backed index.

Only one process may own a directory. SQLite indexes identities and small page
summaries; public receipts, start identities and journals remain ordinary JSON.
No old artifact is replaced or removed during recovery.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid


_ID = re.compile(r'^[a-f0-9]{32}$')
_TERMINAL = frozenset(('complete', 'error', 'timeout', 'cancelled'))


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_json(path, value, *, default=None):
    """Atomically publish a new 0600 artifact without replacing an old file."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = path.parent / ('.' + uuid.uuid4().hex + '.pending')
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, default=default)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(staging, path)  # link is exclusive; an existing receipt is sacred.
        _sync_directory(path.parent)
    finally:
        # This is only our unpublished staging link, never an old audit artifact.
        staging.unlink(missing_ok=True)


class RolloutStore:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.pid = os.getpid()
        self.closed = False
        self.connection = None
        self.lock_fd = os.open(self.root / '.writer.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError('rollout_storage_already_owned') from error
            index = self.root / 'rollout-index.sqlite3'
            try:
                fd = os.open(index, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
            self.connection = sqlite3.connect(index)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    ident TEXT UNIQUE NOT NULL,
                    owner TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome TEXT,
                    receipt_path TEXT,
                    UNIQUE(owner, episode_id)
                );
                CREATE INDEX IF NOT EXISTS owner_page ON sessions(owner, sequence);
            ''')
            self.connection.commit()
        except BaseException:
            self.close()
            raise

    def _check(self):
        if self.closed or os.getpid() != self.pid:
            raise RuntimeError('rollout_storage_is_closed_or_process_changed')

    @staticmethod
    def _validate_metadata(meta):
        if (not isinstance(meta, dict) or meta.get('schema_version') != 'jev.rollout.storage.v1'
                or not _ID.fullmatch(str(meta.get('rollout_id', '')))
                or not isinstance(meta.get('owner'), str) or not meta['owner']
                or not isinstance(meta.get('job'), dict)
                or not isinstance(meta.get('start_body'), dict)
                or meta['job'].get('episode_id') != meta['start_body'].get('episode_id')):
            raise ValueError('invalid_rollout_storage_identity')

    def _index_metadata(self, meta):
        self._check()
        self._validate_metadata(meta)
        previous = self.connection.execute('SELECT metadata FROM sessions WHERE ident=?',
                                           (meta['rollout_id'],)).fetchone()
        if previous:
            if json.loads(previous['metadata']) != meta:
                raise ValueError('immutable_rollout_identity_changed')
            return
        with self.connection:
            self.connection.execute('''INSERT INTO sessions
                (ident,owner,episode_id,metadata,status) VALUES (?,?,?,?,?)''',
                (meta['rollout_id'], meta['owner'], meta['job']['episode_id'], _dumps(meta), 'running'))

    def create(self, meta):
        self._check()
        self._validate_metadata(meta)
        _publish_json(self.root / 'sessions' / (meta['rollout_id'] + '.json'), meta)
        self._index_metadata(meta)

    def _ensure_metadata(self, meta):
        path = self.root / 'sessions' / (meta['rollout_id'] + '.json')
        if not path.exists():
            _publish_json(path, meta)
        elif json.loads(path.read_text(encoding='utf-8')) != meta:
            raise ValueError('immutable_rollout_identity_changed')
        self._index_metadata(meta)

    def append_journal(self, ident, row):
        self._check()
        folder = self.root / 'journals'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(folder / (ident + '.jsonl'), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a', encoding='utf-8') as stream:
            stream.write(_dumps(row) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def _journal_rows(self, ident):
        path = self.root / 'journals' / (ident + '.jsonl')
        try:
            stream = path.open(encoding='utf-8')
        except FileNotFoundError:
            return
        with stream:
            for line in stream:
                # A killed append can leave a partial final line. Preserve the
                # artifact, never mistake that fragment for an accepted reply.
                if not line.endswith('\n'):
                    break
                yield json.loads(line)

    def ticket(self, ident, ticket_id):
        """Read just one historic ticket; do not cache an episode's private log."""
        self._check()
        captured = None
        for row in self._journal_rows(ident):
            value = row.get('value', {})
            if row.get('event') == 'decision_captured' and value.get('ticket_id') == ticket_id:
                captured = {**value, 'answer': None}
            elif (captured is not None and row.get('event') == 'policy_answer'
                  and value.get('ordinal') == captured['ordinal']
                  and value.get('ticket_id', ticket_id) == ticket_id):
                captured['answer'] = {'action': value['action'], 'policy': value['policy']}
                break
        return captured

    def decision_count(self, ident):
        return sum(row.get('event') == 'decision_captured' for row in self._journal_rows(ident))

    @staticmethod
    def _row(row):
        if row is None:
            return None
        result = dict(row)
        result['metadata'] = json.loads(result['metadata'])
        return result

    def get(self, ident, owner):
        self._check()
        return self._row(self.connection.execute(
            'SELECT * FROM sessions WHERE ident=? AND owner=?', (ident, owner)).fetchone())

    def identity(self, owner, episode_id):
        self._check()
        return self._row(self.connection.execute(
            'SELECT * FROM sessions WHERE owner=? AND episode_id=?', (owner, episode_id)).fetchone())

    @staticmethod
    def _validate_receipt(meta, receipt):
        if (not isinstance(receipt, dict) or receipt.get('schema_version') != 'jev.rollout.receipt.v1'
                or receipt.get('rollout_id') != meta['rollout_id']
                or receipt.get('status') not in _TERMINAL
                or any(receipt.get(key) != value for key, value in meta['job'].items())
                or receipt.get('counts_in_denominator') is not True):
            raise ValueError('invalid_persisted_rollout_receipt')

    def _index_receipt(self, meta, receipt, path):
        self._validate_receipt(meta, receipt)
        with self.connection:
            self.connection.execute('''UPDATE sessions SET status=?,outcome=?,receipt_path=?
                WHERE ident=?''', (receipt['status'], receipt.get('outcome'),
                                  str(path.relative_to(self.root)), meta['rollout_id']))

    def prepare_save(self, meta, receipt):
        """Small metadata/index operations must stay on the SQLite owner thread."""
        self._check()
        self._ensure_metadata(meta)
        self._validate_receipt(meta, receipt)

    def publish_result(self, meta, receipt, raw=None, *, default=None):
        """Pure file publication, safe on the bounded terminal worker; no SQLite."""
        self._check()
        self._validate_receipt(meta, receipt)
        ident = meta['rollout_id']
        if raw is not None:
            _publish_json(self.root / 'episodes' / (ident + '.private.json'), raw, default=default)
        path = self.root / 'episodes' / (ident + '.json')
        _publish_json(path, receipt)
        return path

    def commit_result(self, meta, receipt, path):
        self._check()
        self._index_receipt(meta, receipt, path)

    def save(self, meta, receipt, raw=None, *, default=None):
        self.prepare_save(meta, receipt)
        path = self.publish_result(meta, receipt, raw, default=default)
        self.commit_result(meta, receipt, path)

    def publish_failure(self, meta, receipt):
        """Preserve every old artifact; no index connection is used here."""
        self._check()
        path = self.root / 'recoveries' / (meta['rollout_id'] + '.json')
        try:
            _publish_json(path, receipt)
        except FileExistsError:
            receipt = json.loads(path.read_text(encoding='utf-8'))
        return receipt, path

    def save_failure(self, meta, receipt):
        """Failure supersedes a possibly partial write, leaving old bytes intact."""
        self.prepare_save(meta, receipt)
        receipt, path = self.publish_failure(meta, receipt)
        self.commit_result(meta, receipt, path)
        return receipt

    def load_result(self, row):
        self._check()
        path = row.get('receipt_path')
        if path is None:
            return None
        receipt = json.loads((self.root / path).read_text(encoding='utf-8'))
        self._validate_receipt(row['metadata'], receipt)
        return receipt

    def recover(self, make_error):
        """Restore terminal identities; never call a runner for an old attempt."""
        self._check()
        folder = self.root / 'sessions'
        if folder.exists():
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name.endswith('.json') and entry.is_file(follow_symlinks=False):
                        meta = json.loads(Path(entry.path).read_text(encoding='utf-8'))
                        self._index_metadata(meta)
        restored = interrupted = 0
        # This cursor retains one small metadata row, not the historical records.
        for row in self.connection.execute('SELECT * FROM sessions ORDER BY sequence'):
            indexed = self._row(row)
            meta, ident = indexed['metadata'], indexed['ident']
            recovery = self.root / 'recoveries' / (ident + '.json')
            public = self.root / 'episodes' / (ident + '.json')
            indexed_path = self.root / indexed['receipt_path'] if indexed['receipt_path'] else None
            if (indexed['status'] in _TERMINAL and indexed_path in (recovery, public)
                    and indexed_path.is_file()
                    and (indexed_path == recovery or not recovery.exists())):
                # A committed index survives ordinary restarts. Load its large
                # receipt only on demand; index rebuilds still inspect artifacts.
                restored += 1
                continue
            chosen, receipt = None, None
            for path in (recovery, public):
                if not path.exists():
                    continue
                try:
                    candidate = json.loads(path.read_text(encoding='utf-8'))
                    self._validate_receipt(meta, candidate)
                except (ValueError, TypeError, KeyError):
                    if path == recovery:
                        raise ValueError('corrupt_rollout_recovery_receipt') from None
                    continue
                chosen, receipt = path, candidate
                break
            if receipt is None:
                try:
                    decisions = self.decision_count(ident)
                    reason = 'backend_interrupted'
                except (ValueError, TypeError):
                    decisions, reason = 0, 'interrupted_audit_invalid'
                receipt = make_error(meta, reason, decisions)
                self.save_failure(meta, receipt)
                interrupted += 1
            else:
                self._index_receipt(meta, receipt, chosen)
                restored += 1
        return {'restored': restored, 'interrupted': interrupted}

    def page(self, owner, cursor, limit):
        self._check()
        rows = self.connection.execute('''SELECT * FROM sessions
            WHERE owner=? AND sequence>? ORDER BY sequence LIMIT ?''', (owner, cursor, limit + 1)).fetchall()
        total = self.connection.execute('SELECT COUNT(*) FROM sessions WHERE owner=?', (owner,)).fetchone()[0]
        selected = rows[:limit]
        items = []
        for row in selected:
            meta = json.loads(row['metadata'])
            items.append({'rollout_id': row['ident'], **meta['job'], 'status': row['status'],
                          'outcome': row['outcome'], 'counts_in_denominator': True,
                          'result_available': row['receipt_path'] is not None})
        return {'items': items, 'total': total,
                'next_cursor': selected[-1]['sequence'] if len(rows) > limit else None}

    def close(self):
        if self.closed:
            return
        if self.connection is not None:
            self.connection.close()
        if getattr(self, 'lock_fd', None) is not None:
            os.close(self.lock_fd)
        self.closed = True
