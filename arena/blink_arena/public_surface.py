"""Public resource boundary, including stale mounted website directories."""
from pathlib import PurePosixPath
from pathlib import Path
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

REMOVED_FILES = frozenset((
    'arena.json', 'arena-elo.json', 'arena-independent.json', 'arena-ratings.json',
    'arena-replays.json', 'visible-control.js', 'elo.js', 'elo.css',
    'arena-independent.js', 'replay.js', 'replay.css',
))

def unavailable_path(path):
    parts = PurePosixPath(path).parts
    return (PurePosixPath(path).name in REMOVED_FILES
            or path == '/api/elo' or path.startswith('/api/elo/')
            or path == '/api/v1/evaluations' or path.startswith('/api/v1/evaluations/')
            or path == '/api/v1/leaderboards/arena'
            or ('leaderboard' in parts and 'history' in parts))


class PublicStaticFiles(StaticFiles):
    """Reject stale entrypoints as well as the known archived resources."""
    async def get_response(self, path, scope):
        if unavailable_path('/' + path.lstrip('/')):
            return Response(status_code=404)
        response = await super().get_response(path, scope)
        source = Path(response.path) if hasattr(response, 'path') else None
        if source and source.name in {'index.html', 'piccolo.html', 'leaderboard.js', 'content.js'}:
            text = source.read_text()
            if any(marker in text for marker in (
                    'gameEloPanel', 'gamejevbench', 'GameJevArena', 'GAMEJEVARENA',
                    'JevArenaReplayArchive', '/api/elo')):
                return Response(status_code=404)
        return response
