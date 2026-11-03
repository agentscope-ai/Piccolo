#!/usr/bin/env python3
"""Preview static website and real leaderboard APIs without game-engine dependencies."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import uvicorn
from blink_arena.leaderboards import Leaderboards
from blink_arena.paths import WEB
from blink_arena.game_scope import project_arena
from blink_arena.privacy import assert_public_document


def create_preview_app(*, leaderboard_dir=None, web=WEB):
    store = Leaderboards(directory=leaderboard_dir)
    app = FastAPI()

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'ready': False, 'models': [], 'model': '', 'default_model': ''}

    @app.get('/api/showcases')
    def showcases():
        return []

    @app.get('/api/catalog')
    def catalog():
        # Same empty decision catalog as production; game engines are outside this preview.
        return {'categories': [], 'games': [], 'total': 0}

    @app.get('/api/leaderboard')
    def leaderboard():
        return store.projection()

    @app.get('/api/elo')
    def arena():
        # Match production's published-result precedence and active-game scope.
        # Reading the snapshot never loads an evaluator or starts model calls.
        for filename, schema in (
            ('arena-elo.json', 'jev.arena.published-elo.v1'),
            ('arena-independent.json', 'jev.arena.independent-results.v1'),
        ):
            try:
                saved = json.loads((store.data / filename).read_text())
            except FileNotFoundError:
                continue
            except ValueError:
                raise HTTPException(503, 'Published Arena results are unavailable.')
            try:
                if not isinstance(saved, dict) or saved.get('schema_version') != schema:
                    raise ValueError('Unknown published Arena schema')
                assert_public_document(saved)
                result = project_arena(saved)
            except ValueError:
                raise HTTPException(503, 'Published Arena results are unavailable.')
            return {**result, 'controls_available': False}
        return {'state': 'idle', 'overall': [], 'by_game': {}, 'matches': [],
                'planned': 0, 'completed': 0, 'controls_available': False,
                'fixed_config': {'games': [], 'baseline': []}}

    @app.get('/api/leaderboard/source/{ident}')
    def source(ident: str):
        for benchmark in ('jevbench', 'decisionindex', 'harnessjevbench', 'datajevbench'):
            if ident.startswith(benchmark + '-'):
                doc = store.get(benchmark)
                if doc:
                    for row in doc.rows:
                        if row.model_id == ident[len(benchmark) + 1:]:
                            return {'benchmark': benchmark, 'version': doc.version,
                                    'result': row.model_dump(mode='json')}
        raise HTTPException(404, 'Result not found')

    @app.get('/api/v1/leaderboards/{ident}')
    def document(ident: str):
        if ident not in {'harnessjevbench','datajevbench','jevbench','decisionindex'}:
            raise HTTPException(404)
        doc = store.get(ident)
        if doc is None:
            raise HTTPException(404)
        return doc.model_dump(mode='json')

    app.mount('/', StaticFiles(directory=web, html=True), name='website')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18086)
    args = parser.parse_args()
    uvicorn.run(create_preview_app(), host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
