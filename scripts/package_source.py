#!/usr/bin/env python3
"""Package the tracked Piccolo source and assets for CI downloads."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'arena'))
from scripts.build_release import excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    paths = [p for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p]
    paths = [p for p in paths if not excluded(p.removeprefix('arena/'))]
    required = {'README.md', 'arena/web/piccolo.html', 'arena/web/blog/content.js',
                'arena/web/blog/assets/data-architecture.svg', 'examples/workflows/cases.json',
                'evaluation/reproduce.py', '.github/workflows/ci.yml',
                'arena/web/playground/data/home-decision.json', 'arena/web/playground/home-demo.js'}
    if required - set(paths):
        raise ValueError('Required source files are not tracked: ' + ', '.join(sorted(required - set(paths))))
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / 'Piccolo-source.tar.gz'
    manifest = []
    with tarfile.open(archive, 'w:gz') as tar:
        for name in sorted(paths):
            path = ROOT / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('Expected a regular tracked file: ' + name)
            if set(Path(name).parts) & {'var', '.venv', 'node_modules', '.git', 'dist'}:
                raise ValueError('Runtime content must not be packaged: ' + name)
            data = path.read_bytes()
            if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                raise ValueError("LFS media is missing; run git lfs pull: " + name)
            info = tarfile.TarInfo('Piccolo/' + name)
            info.size = len(data)
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            tar.addfile(info, io.BytesIO(data))
            manifest.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    (args.output / 'Piccolo-source.manifest.json').write_text(json.dumps({'files': manifest}, indent=2) + '\n')
    with tarfile.open(archive) as tar:
        assert tar.getnames() == ['Piccolo/' + p['path'] for p in manifest]
        for item in manifest:
            assert hashlib.sha256(tar.extractfile('Piccolo/' + item['path']).read()).hexdigest() == item['sha256']
    print(f'Packaged and verified {len(manifest)} files: {archive}')


if __name__ == '__main__':
    main()
