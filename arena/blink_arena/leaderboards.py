"""Importable leaderboard data, independent of training or benchmark directories."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from .schemas import LeaderboardDocument
from .storage import write_json as _write
from .paths import leaderboard_directory

class Leaderboards:
    def __init__(self, data=None, seed=None, *, directory=None):
        # Positional arguments remain accepted for existing integrations; public
        # standings now have one explicit location, separate from runtime data.
        self.data = self.seed = leaderboard_directory(directory)

    def path(self, ident):
        # Native Arena snapshots retain their matches/protocol. An optional
        # normalized ratings import must never overwrite that different schema.
        return self.data / ('arena-ratings.json' if ident == 'arena' else ident + '.json')

    def get(self, ident):
        return self._snapshot(ident)[0]

    def _snapshot(self, ident):
        path = self.path(ident)
        try:
            with path.open() as source:
                doc = LeaderboardDocument.model_validate_json(source.read())
                # Read metadata from the same open file, even across atomic imports.
                modified = os.fstat(source.fileno()).st_mtime
        except FileNotFoundError:
            return None, None
        return doc, datetime.fromtimestamp(modified, timezone.utc).isoformat()

    def put(self, doc):
        old = self.get(doc.benchmark_id)
        if old:
            _write(self.data/'history'/f'{doc.benchmark_id}-{time.time_ns()}.json', old.model_dump(mode='json'))
        _write(self.path(doc.benchmark_id), doc.model_dump(mode='json'))

    def projection(self, prefix=''):
        benchmarks = []
        for ident in ('jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench'):
            doc, updated_at = self._snapshot(ident)
            if not doc:
                benchmarks.append({'id': ident, 'title': ident, 'status': 'pending', 'groups': [], 'display_rows': []})
                continue
            rows = []
            ordered = sorted(doc.rows, key=lambda r: ((-r.score if doc.higher_is_better else r.score) if r.score is not None else float('inf'), r.model_id))
            for item in ordered:
                row = {'model_key': item.model_id, 'model': item.model_name, 'score': item.score,
                       'score_display': '—' if item.score is None else (f'{item.score:.2f} / 100' if doc.score_scale[1]==100 else f'{100*item.score:.2f}%'),
                       'metric': doc.metric, 'primary_metric': doc.metric, 'status': item.status,
                       'benchmark_version': doc.version, 'samples': item.samples, 'completed': item.samples,
                       'errors': item.errors, 'notes': item.notes, 'score_scale': list(doc.score_scale),
                       'evaluated_at': item.evaluated_at, 'runtime_protocol': item.protocol,
                       'source_id': f'{ident}-{item.model_id}', 'source_url': f'{prefix}/api/leaderboard/source/{ident}-{item.model_id}',
                       'model_identity': {'source_model': item.model_id, 'provider': 'imported'},
                       'calibration': {'brier': item.metrics.get('brier'), 'ece': item.metrics.get('ece')},
                       'display_metrics': {**item.metrics, 'accuracy': item.metrics.get('accuracy', item.metrics.get('acc'))},
                       'radar': {'revision': 'jev-benchmark-radars-v2', 'metric': 'portable_dimensions',
                                 'scale': list(doc.axis_scale), 'display_scale': [0, 100], 'higher_is_better': True,
                                 'axes': [{'id': a.id, 'label': a.label_zh, 'label_en': a.label_en, 'label_zh': a.label_zh,
                                           'score': a.score, 'metric': a.metric, 'samples': a.samples} for a in item.axes]}}
                if ident == 'harnessjevbench':
                    row['hard'] = {'accuracy': item.metrics.get('accuracy', item.metrics.get('acc')), 'brier': item.metrics.get('brier'), 'ece': item.metrics.get('ece')}
                if item.logo:
                    row['logo'] = item.logo
                rows.append(row)
            benchmarks.append({'id': ident, 'title': doc.title, 'version': doc.version, 'metric_label': doc.metric,
                               'updated_at': updated_at, 'source_file': self.path(ident).name,
                               'status': 'available', 'display_rows': rows, 'display_group_id': 'imported',
                               'groups': [{'id': 'imported', 'current': True, 'rows': rows}], 'dataset': {},
                               'display_policy': 'portable JSON import', 'archived_group_count': 0})
        ratings = self.path('arena')
        independent = self.data / 'arena-independent.json'
        published_elo = self.data / 'arena-elo.json'
        arena = (published_elo if published_elo.exists() else independent if independent.exists()
                 else ratings if ratings.exists() else self.data / 'arena.json')
        try:
            arena_updated_at = datetime.fromtimestamp(arena.stat().st_mtime, timezone.utc).isoformat()
        except FileNotFoundError:
            arena_updated_at = None
        benchmarks.append({'id': 'gamejevbench', 'title': 'Piccolo Arena', 'groups': [], 'display_rows': [],
                           'updated_at': arena_updated_at, 'source_file': arena.name})
        latest = max((b['updated_at'] for b in benchmarks if b.get('updated_at')), default=None)
        return {'revision': 'jev.portable-leaderboards.v1', 'updated_at': latest,
                'benchmarks': benchmarks}
