#!/usr/bin/env python3
"""Preview static website and real leaderboard APIs without game-engine dependencies."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import uvicorn
from blink_arena.leaderboards import Leaderboards
from blink_arena.paths import WEB


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18086)
    args = parser.parse_args()
    store = Leaderboards()
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

    @app.get('/api/v1/leaderboards/{ident}')
    def document(ident: str):
        if ident not in {'harnessjevbench','datajevbench','jevbench','decisionindex'}:
            raise HTTPException(404)
        doc = store.get(ident)
        if doc is None:
            raise HTTPException(404)
        return doc.model_dump(mode='json')

    app.mount('/', StaticFiles(directory=WEB, html=True), name='website')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
