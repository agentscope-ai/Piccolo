"""Publish aggregate independent-game results; private trajectories stay outside Git."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blink_arena.privacy import assert_public_document
from blink_arena.storage import write_json
from jev_engine_registry import get_engine

SCHEMA = 'jev.arena.independent-results.v1'
ONESHOT = 'oneshot-w22m05r02-v5best-avg50'
LABELS = {
    'othello_6x6': ('Othello 6×6', '黑白棋 6×6'), 'hex_7x7': ('Hex', '六角棋'),
    'dots_and_boxes_3x3': ('Dots and Boxes', '点格棋'), 'terraria_survival': ('Terraria', '泰拉瑞亚'),
    'tetris_placement': ('Tetris', '俄罗斯方块'), 'snake_navigation': ('Snake', '贪吃蛇'),
    'merge_2048': ('2048', '2048'), 'sokoban_puzzle': ('Sokoban', '推箱子'),
    'mario_platformer': ('Mario', '马里奥'), 'doudizhu': ('Dou Dizhu', '斗地主'),
    'texas_holdem': ('Texas Hold’em', '德州扑克'), 'property_tycoon': ('Property Tycoon', '地产大亨'),
    'chess': ('Chess', '国际象棋'), 'liars_dice': ('Liar’s Dice', '吹牛骰子'),
    'blackjack': ('Blackjack', '二十一点'), 'zha_jin_hua': ('Golden Flower', '炸金花'),
    'checkers': ('Checkers', '西洋跳棋'), 'xiangqi': ('Xiangqi', '中国象棋'),
    'guess_the_number': ('Guess the Number', '猜数字'), 'minesweeper': ('Minesweeper', '扫雷'),
    'sudoku': ('Sudoku', '数独'), 'uno': ('UNO', 'UNO'),
}


def build(summary, plan, model_summary, replay_audit, errors):
    if summary['state'] != 'complete' or summary['cohort_mode'] != 'independent':
        raise ValueError('only_settled_independent_results_can_be_published')
    kinds = plan['kinds']
    if set(kinds) != set(LABELS) or plan['seeds'] != 8:
        raise ValueError('publication_game_scope_or_seed_count_changed')
    stats = {r['id']: r for r in model_summary['rows']}
    metrics = {(r['model'], r['game']): r for r in summary['metrics']}
    if sum(r['finished_episodes'] for r in summary['overall']) != summary['finished']:
        raise ValueError('publication_counts_inconsistent')

    def row(ident, name, source, current, overall=False):
        planned = source['planned_episodes']
        valid = source['valid_episodes']
        wins = source['successes']
        count = source['finished_episodes']
        if valid+source['errors'] != count or count+source['pending'] != planned or wins>valid:
            raise ValueError('publication_episode_counts_inconsistent')
        current_latency = ({'requests': current['http_current_n'],
                            **{k+'_seconds': current['http_current_'+k] for k in ('mean', 'p50', 'p95')},
                            'http_errors': sum(current['http_current_http_error_counts'].values())}
                           if overall else {'requests': source['http_current_requests'],
                            **{k+'_seconds': source['http_current_'+k+'_seconds'] for k in ('mean', 'p50', 'p95')}})
        all_latency = None if overall else {'requests': source['http_requests'],
                        **{k+'_seconds': source['http_'+k+'_seconds'] for k in ('mean', 'p50', 'p95')}}
        return {'id': ident, 'name': name, 'score': wins/planned,
                'success_rate': wins/planned, 'success_rate_valid': wins/valid if valid else None,
                'planned': planned, 'completed': count, 'valid': valid, 'wins': wins,
                'draws': source['draws'], 'losses': source['losses'], 'errors': source['errors'],
                'pending': source['pending'], 'budget_exhausted': source['budget_exhausted'],
                'status': 'complete_with_errors' if source['errors'] else 'complete',
                'coverage': (sum(metrics[ident, k]['valid_episodes']==8 for k in kinds) if overall else valid),
                'required': len(kinds) if overall else planned,
                'latency_current': current_latency, 'latency_all': all_latency,
                'http_errors': None if overall else source['http_errors'],
                'episode_error_counts': {} if overall else source['episode_error_counts']}

    def placeholder():
        return {'id': ONESHOT, 'name': 'Blink', 'status': 'pending',
                **dict.fromkeys(('score','success_rate','success_rate_valid','planned','completed','valid','wins',
                    'draws','losses','errors','pending','budget_exhausted','coverage','required',
                    'latency_current','latency_all','http_errors'), None), 'episode_error_counts': {}}

    overall = [row(r['id'], r['name'], r, stats[r['id']], True) for r in summary['overall']]
    overall.sort(key=lambda r: (-r['score'], r['id']))
    overall.append(placeholder())
    by_game = {kind: sorted([row(p['id'], p['name'], metrics[p['id'], kind], None)
                            for p in plan['participants']], key=lambda r: (-r['score'], r['id']))+[placeholder()]
               for kind in kinds}
    games = [{'id': k, 'name': get_engine(k).name, 'label_en': LABELS[k][0],
              'label_zh': LABELS[k][1], 'mode': 'independent'} for k in kinds]
    result = {'schema_version': SCHEMA, 'source': 'published_independent_results',
        'run_id': 'gamejev-public-20261021-independent-v4',
        'state': 'complete_with_errors' if summary['errors'] else 'complete',
        'updated_at': datetime.fromtimestamp(summary['updated_at'], timezone.utc).isoformat(),
        'completed': summary['finished'], 'planned': summary['planned'], 'scored': summary['valid'],
        'errors': summary['errors'], 'managed_externally': True, 'controls_available': False,
        'protocol': {'run_type': 'independent-fixed-opponent-v1', 'seeds': 8, 'seed_base': plan['seed_base'],
            'metric': 'game_macro_success_rate', 'score_denominator': 'planned_episodes',
            'opponents': 'native fixed rule opponents or environment',
            'decision_policy': 'jev-game-decision-policy-v2-realtime-single',
            'per_model_concurrency': 5, 'max_games': 20,
            'model_input': 'selected-v1', 'kinds': kinds,
            'participants': [{'id': r['id'], 'name': r['name']} for r in overall],
            'source_commit': '1b9c7567bd139f60a017e966a4d712aa17ddd4cb',
            'latency': 'HTTP seconds; current and inherited requests remain separate',
            'error_policy': 'errors remain explicit; planned-denominator success is a lower bound when errors exist'},
        'fixed_config': {'games': games, 'baseline': [{'id': r['id'], 'name': r['name']} for r in overall],
                         'seeds': 8, 'seed_base': plan['seed_base']},
        'overall': overall, 'by_game': by_game, 'matches': [],
        'replay_validation': {'mario': {k: replay_audit[k] for k in
            ('finished','planned','strict_passed','episode_errors','old_failed_total','old_failed_completed')}},
        'episode_errors': [{k: e[k] for k in ('kind','seed','a','error_code','http_status')} for e in errors['errors']]}
    if result['planned'] != len(plan['participants'])*len(kinds)*8:
        raise ValueError('publication_plan_denominator_inconsistent')
    if len(result['episode_errors']) != result['errors']:
        raise ValueError('publication_error_evidence_missing')
    assert_public_document(result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--analysis', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    load = lambda path: json.loads(path.read_text())
    result = build(load(args.run/'summary.json'), load(args.run/'plan.json'),
                   load(args.analysis/'model_summary.json'), load(args.analysis/'mario_replay_audit.json'),
                   load(args.analysis/'episode_errors.json'))
    write_json(args.out, result)
    print(json.dumps({'models': len(result['overall']), 'games': len(result['by_game']),
                      'completed': result['completed'], 'errors': result['errors'], 'oneshot': 'pending'}))
