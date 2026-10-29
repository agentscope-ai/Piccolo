"""Build a portable source archive from an explicit, private-file-safe scope."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import tarfile
import uuid


ROOT_FILES = frozenset(('README.md', 'pyproject.toml', 'requirements.txt', 'MANIFEST.in',
                        'Dockerfile', 'compose.yaml', '.dockerignore', '.gitignore'))
SOURCE_DIRS = ('blink_arena', 'web', 'config', 'deploy', 'docs', 'scripts', 'tests',
               'leaderboard', 'data/seed')
BLOCKED_PARTS = frozenset(('.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'var', 'build', 'dist', 'htmlcov', 'test-results',
    'playwright-report', '.codex', '.claude', 'node_modules', 'releases'))
BLOCKED_SUFFIXES = ('.pyc', '.pyo', '.log', '.pem', '.key', '.p12', '.pfx',
                    '.sqlite', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.db')
FORBIDDEN_IMPORTS = frozenset(('project_z', 'transformers', 'torch', 'jev_gameplay_rl_v3',
                             'jev_frontend_game_audit', 'jev_recipe_full_benchmark'))
PRIVATE_TEXT = (
    ('machine_path', re.compile(r'/(?:mnt/(?:data|workspace)|root)/')),
    ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('provider_credential', re.compile(r'\bsk-[A-Za-z0-9]{24,}\b')),
)
REQUIRED = frozenset(('web/index.html', 'web/playground/leaderboard.js', 'leaderboard/arena.json',
    'leaderboard/arena-replays.json', 'leaderboard/jevbench.json', 'leaderboard/decisionindex.json',
    'leaderboard/harnessjevbench.json', 'leaderboard/datajevbench.json', 'web/playground/logos/blink.svg', 'blink_arena/rollouts.py',
    'blink_arena/engines/jev_engine_rollout_backend.py', 'blink_arena/engines/jev_engine_rollout_store.py',
    'blink_arena/engines/jev_engine_episode_runner.py', 'docs/ROLLOUT.md',
    'tests/rollout_http_smoke.py', 'web/playground/world-arrival.js'))


def excluded(relative):
    path = Path(relative)
    name = path.name.lower()
    return (any(part in BLOCKED_PARTS or part.endswith('.egg-info') for part in path.parts)
            or relative in ('docs/ENGINE_INTEGRATION_HANDOFF.md', 'docs/HANDOFF_ACK.md')
            or relative.startswith('leaderboard/history/')
            or name in ('.ds_store', '.coverage', 'credentials.json', 'credentials.yaml',
                        'tokens.json', 'auth.json', 'settings.local.json') or name.startswith('.env')
            or name.endswith(BLOCKED_SUFFIXES))


def files(root):
    result = []
    for name in sorted(ROOT_FILES):
        result.append(root / name)
    for directory in SOURCE_DIRS:
        for current, children, names in os.walk(root / directory, followlinks=False):
            children[:] = [name for name in sorted(children)
                           if not excluded((Path(current) / name).relative_to(root).as_posix())]
            for name in children:
                if (Path(current) / name).is_symlink():
                    raise ValueError('release includes a directory symlink')
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                if not excluded(relative):
                    result.append(path)
    result = sorted(set(result))
    for path in result:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('release includes a link or non-file: ' + path.relative_to(root).as_posix())
    missing = REQUIRED - {path.relative_to(root).as_posix() for path in result}
    if missing:
        raise ValueError('required release files missing: ' + ', '.join(sorted(missing)))
    return result


def checked_payloads(root):
    selected = files(root)
    local_modules = {path.stem for path in selected if path.suffix == '.py'}
    payloads = []
    for path in selected:
        relative = path.relative_to(root).as_posix()
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError('release source changed while reading: ' + relative)
        if path.suffix in ('.py', '.js', '.cjs', '.json', '.html', '.css', '.md', '.txt', '.yaml', '.sh'):
            text = data.decode('utf-8')
            for rule, pattern in PRIVATE_TEXT:
                if pattern.search(text):
                    raise ValueError('private-content rule ' + rule + ' matched file ' + relative)
        if path.suffix == '.py':
            for node in ast.walk(ast.parse(data, filename=relative)):
                modules = ([entry.name for entry in node.names] if isinstance(node, ast.Import)
                           else [node.module] if isinstance(node, ast.ImportFrom) and not node.level
                           else [])
                for module in modules:
                    first = (module or '').split('.')[0]
                    if first in FORBIDDEN_IMPORTS or (module or '').startswith('src.tools'):
                        raise ValueError('external training import in ' + relative)
                    if first.startswith('jev_') and first != 'blink_arena' and first not in local_modules:
                        raise ValueError('missing bundled engine import in ' + relative + ': ' + first)
        payloads.append((relative, data, before.st_mtime_ns, bool(before.st_mode & 0o111)))
    return payloads


def build(root, output, name=None, *, check_only=False):
    root = root.resolve()
    payloads = checked_payloads(root)
    summary = {'files': len(payloads), 'source_bytes': sum(len(data) for _, data, _, _ in payloads),
               'web_files': sum(relative.startswith('web/') for relative, *_ in payloads),
               'leaderboard_files': sum(relative.startswith('leaderboard/') for relative, *_ in payloads)}
    if check_only:
        return {'checked': True, **summary}
    output = output.resolve()
    if output.is_relative_to(root):
        raise ValueError('release output must be outside the source repository')
    output.mkdir(parents=True, exist_ok=True)
    name = name or 'Piccolo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-rollout'
    if not re.fullmatch(r'(?:Piccolo|PiccoloArena)-[A-Za-z0-9._-]+', name):
        raise ValueError('invalid release name')
    archive, manifest = output / (name + '.tar.gz'), output / (name + '.manifest.json')
    if archive.exists() or manifest.exists():
        raise FileExistsError('release name already exists; choose a new version')
    temporary = output / ('.' + uuid.uuid4().hex + '.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as raw:
            with tarfile.open(fileobj=raw, mode='w:gz', format=tarfile.PAX_FORMAT) as tar:
                for relative, data, mtime, executable in payloads:
                    member = tarfile.TarInfo('PiccoloArena/' + relative)
                    member.size, member.mode, member.mtime = len(data), 0o755 if executable else 0o644, mtime // 1_000_000_000
                    tar.addfile(member, io.BytesIO(data))
            raw.flush()
            os.fsync(raw.fileno())
        for relative, data, mtime, _ in payloads:
            current = (root / relative).stat()
            if (current.st_size, current.st_mtime_ns) != (len(data), mtime):
                raise RuntimeError('source changed before archive publication: ' + relative)
        os.link(temporary, archive)  # Exclusive publication, preserving every old release.
    finally:
        temporary.unlink(missing_ok=True)
    record = {'schema_version': 'jev.release.manifest.v1', 'release': name, 'archive': archive.name,
              'archive_bytes': archive.stat().st_size, **summary,
              'included_directories': list(SOURCE_DIRS),
              'excluded_directory_names': sorted(BLOCKED_PARTS),
              'excluded_suffixes': list(BLOCKED_SUFFIXES),
              'excluded_paths': ['leaderboard/history', 'docs/ENGINE_INTEGRATION_HANDOFF.md', 'docs/HANDOFF_ACK.md', '.env*'],
              'files': [{'path': relative, 'bytes': len(data)} for relative, data, _, _ in payloads]}
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'archive': str(archive), 'manifest': str(manifest), 'archive_bytes': archive.stat().st_size, **summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--name')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    output = args.output_dir or args.root.resolve().parent / 'releases'
    print(json.dumps(build(args.root, output, args.name, check_only=args.check_only), ensure_ascii=False))


if __name__ == '__main__':
    main()
