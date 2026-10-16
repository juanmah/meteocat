#!/usr/bin/env python3
"""Bump the version in pyproject.toml (patch|minor|major)."""

import re
import sys
from pathlib import Path

BUMPS = {'patch', 'minor', 'major'}


def main() -> None:
    bump = sys.argv[1] if len(sys.argv) > 1 else 'patch'
    if bump not in BUMPS:
        sys.stderr.write(f'Invalid BUMP: {bump} (expected one of {sorted(BUMPS)})\n')
        raise SystemExit(1)

    path = Path('pyproject.toml')
    content = path.read_text()

    match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"$', content, re.MULTILINE)
    if not match:
        sys.stderr.write('Could not find version in pyproject.toml\n')
        raise SystemExit(1)

    major, minor, patch = (int(part) for part in match.groups())
    current = f'{major}.{minor}.{patch}'

    if bump == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump == 'minor':
        minor += 1
        patch = 0
    else:
        patch += 1

    new_version = f'{major}.{minor}.{patch}'
    new_content = re.sub(
        r'^version = "\d+\.\d+\.\d+"$',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    path.write_text(new_content)
    sys.stdout.write(f'Bumped version: {current} -> {new_version}\n')


if __name__ == '__main__':
    main()
