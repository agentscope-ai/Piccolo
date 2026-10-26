from pathlib import Path
import os

REPO = Path(__file__).resolve().parent.parent
WEB = REPO / 'web'
SEED = REPO / 'data' / 'seed'
DATA = Path(os.environ.get('JEV_DATA_DIR', str(REPO / 'var'))).resolve()
CONFIG = Path(os.environ.get('JEV_CONFIG', str(REPO / 'config' / 'app.json'))).resolve()


def leaderboard_directory(directory=None):
    """One portable directory for public benchmark, Arena and replay data."""
    value = directory if directory is not None else os.environ.get('JEV_LEADERBOARD_DIR', REPO / 'leaderboard')
    return Path(value).expanduser().resolve()
