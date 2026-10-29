"""The selected roster must use one evaluation snapshot for totals and dimensions."""
import math
from pathlib import Path

from blink_arena.leaderboards import Leaderboards
from blink_arena.schemas import LeaderboardDocument, LeaderboardRow

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ('harnessjevbench', 'datajevbench', 'jevbench', 'decisionindex')
PICCOLO = {'blink-27b-1028', 'blink-9b-1028', 'blink-4b-1028'}


def test_totals_and_dimensions_use_the_same_frozen_records():
    store = Leaderboards(directory=ROOT / 'leaderboard')
    expected_ids = None
    for benchmark in BENCHMARKS:
        document = store.get(benchmark)
        ids = {r.model_id for r in document.rows}
        assert len(ids) == 11 and PICCOLO <= ids
        assert all('startlux' not in ident.lower() for ident in ids)
        assert expected_ids is None or ids == expected_ids
        expected_ids = ids
        for row in document.rows:
            if row.model_id in PICCOLO:
                assert row.model_name == 'Piccolo-' + row.model_id.split('-')[1].upper()
            if benchmark == 'decisionindex':
                continue
            total = sum(axis.samples for axis in row.axes)
            assert total == {'harnessjevbench': 295, 'datajevbench': 500, 'jevbench': 231}[benchmark]
            weighted = sum(axis.score * axis.samples for axis in row.axes) / total
            assert math.isclose(weighted, row.score, abs_tol=1e-12)


def test_coverage_is_separate_from_fixed_accuracy_denominators():
    store = Leaderboards(directory=ROOT / 'leaderboard')
    hard = {r.model_id: r for r in store.get('harnessjevbench').rows}
    microsoft = hard['access-microsoft--microsoft-decision-1']
    assert microsoft.errors == 7
    assert microsoft.metrics['hard_valid'] == 296 and microsoft.metrics['accuracy_n'] == 295
    luna = hard['access-openai--gpt-6-luna-decisions']
    assert luna.errors == 0 and luna.metrics['hard_valid'] == 303
    assert luna.metrics['soft_valid'] == 46 and luna.metrics['soft_tv'] is None
    data = {r.model_id: r for r in store.get('datajevbench').rows}
    jev = data['access-typesafe--jev-1.14']
    assert jev.errors == 24 and jev.metrics['accuracy_n'] == 500
    assert jev.score == jev.metrics['correct'] / 500
    assert jev.metrics['brier'] is None and jev.metrics['ece'] is None


def test_unknown_official_error_counts_are_not_claimed_to_be_zero():
    store = Leaderboards(directory=ROOT / 'leaderboard')
    rows = store.get('decisionindex').rows
    assert sum(r.score is not None for r in rows) == 7
    for row in rows:
        assert row.errors == (0 if row.model_id in PICCOLO else None)
        if row.score is None:
            assert row.status == 'pending'
            assert all(axis.score is None for axis in row.axes)
    document = LeaderboardDocument(benchmark_id='decisionindex', title='Fixture', version='0.3',
                                   metric='index', rows=[LeaderboardRow(model_id='unknown', model_name='Unknown', errors=None)])
    assert document.model_dump()['rows'][0]['errors'] is None
