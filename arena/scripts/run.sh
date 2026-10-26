#!/usr/bin/env bash
set -euo pipefail

jev_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$jev_repo_dir"
if [[ -n "${JEV_PYTHON:-}" ]]; then
    jev_python="$JEV_PYTHON"
elif [[ -x "$jev_repo_dir/.venv/bin/python" ]]; then
    jev_python="$jev_repo_dir/.venv/bin/python"
else
    jev_python=python3
fi

exec "$jev_python" -m blink_arena \
    --host "${JEV_HOST:-127.0.0.1}" \
    --port "${JEV_PORT:-8080}" \
    --prefix "${JEV_PREFIX:-}" "$@"
