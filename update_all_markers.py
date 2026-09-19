import os
import time
from pathlib import Path

def update_file_markers(filepath, hot_threshold_seconds=2*24*3600):
    try:
        mtime = os.path.getmtime(filepath)
        now = time.time()
        is_hot = (now - mtime) < hot_threshold_seconds
        expected_marker = '# HOT' if is_hot else '# COLD'
        with open(filepath, 'r') as f:
            content = f.read()
        if content.startswith(expected_marker) or content.startswith(expected_marker + '\\n'):
            return
        lines = content.splitlines(keepends=True)
        if lines and (lines[0].strip() == '# HOT' or lines[0].strip() == '# COLD'):
            content = ''.join(lines[1:])
        new_content = expected_marker + '\\n' + content
        with open(filepath, 'w') as f:
            f.write(new_content)
    except Exception:
        pass

projects = ['superguard', 'elemental-life', 'elemental-life-2', 'cybertarot']
base = Path('/home/thomas/LivingCode/Projects')
for proj in projects:
    proj_path = base / proj
    if not proj_path.exists():
        continue
    for root, dirs, files in os.walk(proj_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv', 'env', '.git', 'build', 'dist', 'target')]
        for file in files:
            if file.endswith(('.json', '.log', '.md', '.txt', '.sh', '.bak', '.backup', '.pyc', '.pyo')):
                continue
            filepath = os.path.join(root, file)
            if '/.git/' in filepath or filepath.startswith('.git') or filepath.endswith('.git'):
                continue
            update_file_markers(filepath)
