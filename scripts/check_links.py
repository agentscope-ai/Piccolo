#!/usr/bin/env python3
"""Check repository-local Markdown links and HTML asset references."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def tracked_files():
    return [ROOT / path for path in subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if path]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ('href', 'src', 'poster') and value:
                self.urls.append(value)


def check():
    errors, count = [], 0
    for path in tracked_files():
        if not path.exists() or path.suffix.lower() not in ('.md', '.html'):
            continue
        text = path.read_text()
        if path.suffix.lower() == '.md':
            text = re.sub(r'^\s*```.*?^\s*```\s*$', '', text, flags=re.M | re.S)
            text = re.sub(r'`[^`\n]*`', '', text)
        parser = Links()
        parser.feed(text)
        urls = parser.urls
        if path.suffix.lower() == '.md':
            urls += [m.group(1) or m.group(2) for m in re.finditer(
                r'!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\)', text)]
            urls += re.findall(r'^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?', text, re.M)
        for url in urls:
            parsed = urlsplit(unescape(url))
            if parsed.scheme or parsed.netloc or not parsed.path or '{' in parsed.path:
                continue
            target = unquote(parsed.path)
            # Runtime routes are exercised by the browser/API tests.
            if target.startswith('/') or target.startswith('./api/'):
                continue
            dest = (path.parent / target).resolve()
            count += 1
            if not dest.exists():
                errors.append(f'{path.relative_to(ROOT)} -> {url}')
    if errors:
        print('Broken local links:\n' + '\n'.join(sorted(set(errors))), file=sys.stderr)
        return 1
    print(f'Checked {count} local links and asset references.')
    return 0


if __name__ == '__main__':
    sys.exit(check())
