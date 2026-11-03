#!/usr/bin/env python3
"""Cycle 1 helper: strip leading '# HOT'/'# COLD' lines that BREAK a file.

Uses the canonical marker_guard.marker_safe() as the single source of truth:
if marker_safe() says the marker may never be written there, then a marker
already sitting there is damage and must be removed.

Rule 3 respected: *.bak / *.backup are never touched (left for the operator).
Rule 4 respected: nothing is deleted, only the injected marker line is removed.
"""
import os
import sys

sys.path.insert(0, '/home/thomas/LivingCode/orchestration/scripts')
from marker_guard import marker_safe  # noqa: E402

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.gradle', '.idea', '.vscode'}
SKIP_EXT = {'.bak', '.backup', '.pyc', '.pyo'}

ROOTS = [
    '/home/thomas/LivingCode/Projects/elemental-life',
]

changed = []
skipped_bak = 0
for root_dir in ROOTS:
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1] in SKIP_EXT:
                skipped_bak += 1
                continue
            path = os.path.join(root, name)
            if marker_safe(path):
                continue  # marker is a legal comment here -> leave it
            try:
                with open(path, 'rb') as fh:
                    raw = fh.read()
            except OSError:
                continue
            if b'\x00' in raw[:8192]:
                continue  # real binary: never rewrite
            text = raw.decode('utf-8', errors='replace')
            lines = text.splitlines(keepends=True)
            if not lines or lines[0].strip() not in ('# HOT', '# COLD'):
                continue
            rest = ''.join(lines[1:])
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(rest)
            changed.append((path, lines[0].strip(), len(raw) - len(rest.encode('utf-8'))))

for path, marker, removed in changed:
    print(f'stripped {marker:6s} (-{removed}B)  {path}')
print(f'\ntotal: {len(changed)} files repaired; {skipped_bak} .bak/.backup/pyc left untouched (rule 3)')