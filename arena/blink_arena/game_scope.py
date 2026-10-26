"""Read-only current-game projection of an immutable historical Arena result."""
from copy import deepcopy

from jev_control_scope import active_games, policy


def project_arena(saved):
    """Keep per-game ratings; recompute their mean and counts after retirement.

    This is a historical subset, not a new model evaluation. The original
    snapshot and replays remain on disk. Missing newer games earn no score.
    """
    original = saved.get('by_game', {})
    kinds = active_games(original)
    if len(kinds) == len(original):
        return saved
    result = deepcopy(saved)
    tables = result['by_game'] = {kind: result['by_game'][kind] for kind in kinds}
    result['game_scope'] = {
        'revision': policy()['revision'], 'source_run_id': saved.get('run_id'),
        'historical_subset': True, 'games': list(kinds),
        'excluded_games': [kind for kind in original if kind not in kinds],
        'aggregation': 'equal_mean_of_remaining_per_game_ratings',
        'new_evaluation': False,
        'control_audit_scope': 'original_snapshot_including_retired_games',
    }
    for section in ('fixed_config', 'options'):
        if section in result and 'games' in result[section]:
            result[section]['games'] = [g for g in result[section]['games'] if g['id'] in kinds]
    from jev_demo_elo import _rank, ENGINE
    overall = []
    counters = ('played', 'wins', 'draws', 'losses', 'errors')
    if saved.get('source') == 'imported_ratings':
        for table in tables.values():
            for item in table:
                item.update({key: None for key in counters}, match_counts_available=False)
    for old in saved.get('overall', []):
        row = deepcopy(old)
        games = [item for table in tables.values() for item in table if item['id'] == row['id']]
        scored = [item for item in games if item.get('rating') is not None]
        full = bool(kinds) and len(scored) == len(kinds)
        eligible = row['id'] != ENGINE
        row.update(rating=sum(g['rating'] for g in scored)/len(scored) if full and eligible else None,
                   coverage=len(scored), required_games=len(kinds), coverage_complete=full,
                   overall_eligible=eligible, provisional=True)
        for key in counters:
            # Imported score axes have no per-game match ledger; the source
            # currently repeats global counters on every axis. Never add them.
            row[key] = (None if saved.get('source') == 'imported_ratings'
                        else sum(g.get(key, 0) or 0 for g in games))
        if saved.get('source') == 'imported_ratings':
            row['match_counts_available'] = False
        # Old aggregate stability is over a different decision population.
        row.pop('stability', None)
        overall.append(row)
    result['overall'] = _rank(overall)
    result['matches'] = [m for m in result.get('matches', []) if m.get('kind') in kinds]
    result['completed'] = len(result['matches'])
    result['planned'] = len(result['matches']) if saved.get('completed') == saved.get('planned') else None
    result['scored'] = sum(m.get('status') == 'complete' for m in result['matches'])
    result['progress'] = {}
    result.pop('baseline_progress', None)
    # Keep source control provenance, but never reuse its counts for this subset.
    audit = result.get('snapshot', {}).get('control_audit')
    if audit:
        result['source_control_audit'] = deepcopy(audit)
    result.pop('snapshot', None)
    return result
