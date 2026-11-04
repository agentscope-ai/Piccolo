#!/usr/bin/env python3
"""Preview static website and real leaderboard APIs without game-engine dependencies."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, HTTPException
from blink_arena.public_surface import PublicStaticFiles
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

    @app.middleware('http')
    async def public_surface(request, call_next):
        from blink_arena.public_surface import unavailable_path
        from fastapi.responses import Response
        if unavailable_path(request.url.path):
            return Response(status_code=404)
        return await call_next(request)

    app.mount('/', PublicStaticFiles(directory=web, html=True), name='website')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18086)
    args = parser.parse_args()
    uvicorn.run(create_preview_app(), host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
