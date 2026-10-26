#!/usr/bin/env python3
"""Download a maintainer-configured release; never guess or execute model code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

DEFAULT_RELEASE = Path(__file__).resolve().parents[1] / 'assets/release.json'


def download_plan(release: dict, output: Path) -> dict:
    if not isinstance(release, dict) or release.get('status') != 'released':
        raise ValueError('model_release_not_configured')
    if release.get('schema_version') != 'blink.safety.release.v1' or release.get('provider') != 'huggingface':
        raise ValueError('unsupported_release_descriptor')
    repo, revision, patterns = release.get('repo_id'), release.get('revision'), release.get('allow_patterns')
    if not isinstance(repo, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid_model_repository')
    if not isinstance(revision, str) or not revision.strip() or revision.lower() in {'main', 'master', 'latest'}:
        raise ValueError('fixed_release_revision_required')
    if not isinstance(patterns, list) or not patterns or any(not isinstance(p, str) or not p for p in patterns):
        raise ValueError('release_file_scope_required')
    return {'repo_id': repo, 'revision': revision, 'allow_patterns': patterns,
            'local_dir': str(output.expanduser().resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, default=DEFAULT_RELEASE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true', help='Validate configuration without network or writes')
    args = parser.parse_args()
    try:
        plan = download_plan(json.loads(args.release.read_text()), args.output)
    except (OSError, ValueError, TypeError):
        print(json.dumps({'status': 'not_ready', 'reason': 'valid_released_model_descriptor_required'}))
        return 2
    if args.dry_run:
        print(json.dumps({'status': 'configured', 'downloaded': False, **plan}))
        return 0
    output = Path(plan['local_dir'])
    receipt = output / 'blink-download.json'
    binding = {k: plan[k] for k in ('repo_id', 'revision', 'allow_patterns')}
    try:
        if receipt.exists():
            if json.loads(receipt.read_text()).get('release') != binding:
                raise ValueError('existing_directory_has_different_release')
        elif output.exists() and any(output.iterdir()):
            raise ValueError('output_must_be_empty_or_a_matching_download')
        from huggingface_hub import snapshot_download
        output.mkdir(parents=True, exist_ok=True)
        # A receipt enables SDK resume only for this exact configured release.
        receipt.write_text(json.dumps({'release': binding, 'complete': False}, indent=2) + '\n')
        snapshot_download(**plan)
        payloads = [p for p in output.rglob('*') if p.is_file() and '.cache' not in p.relative_to(output).parts and p != receipt]
        if not payloads or any(p.stat().st_size == 0 for p in payloads):
            raise ValueError('download_has_no_complete_payload')
        receipt.write_text(json.dumps({'release': binding, 'complete': True}, indent=2) + '\n')
    except ImportError:
        print(json.dumps({'status': 'not_ready', 'reason': 'install_huggingface_hub'}))
        return 2
    except Exception:
        # Never echo authenticated URLs, tokens or SDK request bodies.
        print(json.dumps({'status': 'download_failed', 'reason': 'check_configuration_and_local_download_state'}))
        return 2
    print(json.dumps({'status': 'downloaded', 'model_directory': str(output), 'activated': False}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
