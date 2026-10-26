#!/usr/bin/env python3
"""Validate and import a public leaderboard snapshot from a local JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Run from any cwd while retaining the complete source distribution's assets.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from blink_arena.leaderboards import Leaderboards
from blink_arena.paths import leaderboard_directory
from blink_arena.schemas import LeaderboardDocument


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='校验并导入本地 jev.leaderboard.v1 JSON；不调用模型服务。')
    parser.add_argument('file', type=Path, help='完整榜单 JSON 文件')
    parser.add_argument('--leaderboard-dir', type=Path, help='统一榜单目录，默认 JEV_LEADERBOARD_DIR 或仓库 leaderboard/')
    args = parser.parse_args(argv)
    try:
        document = LeaderboardDocument.model_validate_json(args.file.read_bytes())
    except ValidationError as exc:
        # Pydantic's formatted errors include raw input. Report only error types.
        kinds = sorted({error['type'] for error in exc.errors()})
        print('Invalid leaderboard document: ' + ', '.join(kinds), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'Cannot read leaderboard file ({type(exc).__name__})', file=sys.stderr)
        return 2

    store = Leaderboards(directory=leaderboard_directory(args.leaderboard_dir))
    try:
        store.put(document)
    except ValidationError:
        print('Existing leaderboard failed validation; import was not completed.', file=sys.stderr)
        return 2
    except OSError as exc:
        print(f'Cannot write leaderboard ({type(exc).__name__})', file=sys.stderr)
        return 2

    print(json.dumps({'benchmark_id': document.benchmark_id, 'imported': len(document.rows),
                      'destination': store.path(document.benchmark_id).name},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
