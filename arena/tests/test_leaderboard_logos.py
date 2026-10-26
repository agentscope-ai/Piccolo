"""Optional display assets survive imports without altering result identities."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from blink_arena.app import create_app
from blink_arena.leaderboards import Leaderboards
from blink_arena.schemas import AppConfig, LeaderboardDocument, LeaderboardRow


@pytest.mark.parametrize('benchmark', ['jevbench', 'decisionindex', 'harnessjevbench', 'arena'])
def test_optional_logo_import_roundtrip_and_projection(tmp_path, benchmark):
    store = Leaderboards(directory=tmp_path/'leaderboards')
    plain = LeaderboardRow(model_id='plain', model_name='Plain', score=.5)
    branded = LeaderboardRow(model_id='branded', model_name='Branded', score=.75,
                             logo='./playground/logos/qwen.png')
    before = LeaderboardDocument(benchmark_id=benchmark, title=benchmark, version='fixture',
                                 metric='accuracy', rows=[plain])
    store.put(before)
    doc = before.model_copy(update={'rows': [plain, branded]})
    store.put(doc)
    assert list((tmp_path/'leaderboards/history').glob('*.json'))
    assert 'logo' not in store.get(benchmark).rows[0].model_dump()
    assert store.get(benchmark).rows[1].logo == branded.logo
    with TestClient(create_app(data=tmp_path/'runtime', config=AppConfig(),
                              leaderboard_dir=tmp_path/'leaderboards')) as client:
        rows = client.get('/api/v1/leaderboards/'+benchmark).json()['rows']
        assert 'logo' not in rows[0] and rows[1]['logo'] == branded.logo
        if benchmark != 'arena':
            result = next(b for b in client.get('/api/leaderboard').json()['benchmarks'] if b['id']==benchmark)
            projected = {r['model_key']: r for r in result['display_rows']}
        else:
            projected = {r['id']: r for r in client.get('/api/elo').json()['overall']}
        assert projected['branded']['logo'] == branded.logo
        assert 'logo' not in projected['plain']
        assert rows[1]['score'] == .75 and rows[1]['model_id'] == 'branded'


@pytest.mark.parametrize('value', [None, '', './playground/logos/example.svg', 'playground/logos/example.png',
                                  '/playground/logos/example.webp', 'https://example.com/logo.png'])
def test_valid_local_and_public_image_locations(value):
    row = LeaderboardRow(model_id='model', model_name='Model', logo=value)
    doc = LeaderboardDocument(benchmark_id='jevbench', title='JevBench', version='test',
                              metric='accuracy', rows=[row])
    assert doc.rows[0].logo == (value or None)


@pytest.mark.parametrize('value', ['javascript:alert(1)', 'data:image/svg+xml,anything', '//example.com/a.png',
                                  'https://user:password@example.com/a.png', '../secret.svg',
                                  'https://127.0.0.1/logo.png', 'https://host.internal/logo.png',
                                  '/var/private.png', 'https://example.com/logo\n.png'])
def test_logo_does_not_bypass_public_metadata_boundary(value):
    with pytest.raises(ValidationError):
        LeaderboardRow(model_id='model', model_name='Model', logo=value)
