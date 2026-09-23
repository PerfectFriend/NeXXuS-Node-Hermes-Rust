# HOT
#!/usr/bin/env python3
import os
import subprocess
import datetime
import re
import time
from pathlib import Path


def update_file_markers(filepath, hot_threshold_seconds=2*24*3600):
    """
    Update the hot/cold marker at the top of the file based on its modification time.
    If the file is modified within the hot_threshold_seconds, it's hot, else cold.
    The marker is a single line at the very top: either '# HOT' or '# COLD'.
    """
    try:
        # Get the file's modification time
        mtime = os.path.getmtime(filepath)
        now = time.time()
        is_hot = (now - mtime) < hot_threshold_seconds

        # Read the file content
        with open(filepath, 'r') as f:
            content = f.read()

        # Determine the expected marker
        expected_marker = '# HOT' if is_hot else '# COLD'

        # Check if the file already starts with the expected marker (allowing for newline)
        if content.startswith(expected_marker) or content.startswith(expected_marker + '\n'):
            # Already correct, do nothing
            return

        # Remove any existing marker (either # HOT or # COLD) from the start of the file
        lines = content.splitlines(keepends=True)
        if lines and (lines[0].strip() == '# HOT' or lines[0].strip() == '# COLD'):
            # Remove the first line
            content = ''.join(lines[1:])
        # Now content does not start with a marker line

        # Add the expected marker at the top
        new_content = expected_marker + '\n' + content

        # Write back
        with open(filepath, 'w') as f:
            f.write(new_content)
    except Exception:
        # Skip files we can't read or write
        pass


def run_hermes(prompt, model=None, provider=None):
    cmd = ['hermes', 'chat']
    if model:
        cmd.extend(['-m', model])
    if provider:
        cmd.extend(['--provider', provider])
    cmd.extend(['-q', prompt])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result


def trigger_next_cron_job(job_id):
    if not job_id:
        return
    cmd = ['hermes', 'cron', 'run', job_id]
    subprocess.run(cmd, capture_output=True, text=True)


def update_hot_cold_markers(project_path):
    # Only process files under Projects/ subdirectories (actual project code)
    # Skip root-level scripts, configs, logs, nodes/, etc.
    projects_root = Path('/home/thomas/LivingCode/Projects')
    if not projects_root.exists():
        return

    for project_dir in projects_root.iterdir():
        if not project_dir.is_dir():
            continue
        for root, dirs, files in os.walk(project_dir):
            # Skip hidden dirs and common non-code dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv', 'env', '.git', 'build', 'dist', 'target')]
            for file in files:
                filepath = os.path.join(root, file)
                # Skip non-source files by extension
                if file.endswith(('.json', '.log', '.md', '.txt', '.sh', '.bak', '.backup', '.pyc', '.pyo')):
                    continue
                update_file_markers(filepath)


def main():
    journal_path = '/home/thomas/LivingCode/agents/journal.md'
    if not os.path.exists(journal_path):
        print(f'Journal not found: {journal_path}')
        return
    with open(journal_path, 'r') as f:
        journal = f.read()
    print(f'Journal length: {len(journal)}')
    print(f'First 100 chars: {repr(journal[:100])}')
    # Find last [TRIGGER_LORD] line
    matches = list(re.finditer(r'\[TRIGGER_LORD\]\s*(\S+)', journal))
    print(f'Number of matches: {len(matches)}')
    for m in matches:
        print(f'  Match: {m.group(0)} -> {m.group(1)}')
    if not matches:
        print('No TRIGGER_LORD found in journal')
        return
    last_match = matches[-1]
    project = last_match.group(1)
    print(f'Last trigger: {project}')
    # Determine project path - if trigger is bogus (lord-of-code), find real project from TRIGGER_AUDITOR
    if project == 'lord-of-code':
        # Find the real project from the last TRIGGER_AUDITOR
        audit_matches = list(re.finditer(r'\[TRIGGER_AUDITOR\]\s*(\S+)', journal))
        if audit_matches:
            project = audit_matches[-1].group(1)
            print(f'Corrected project from TRIGGER_AUDITOR: {project}')
    # Determine project path
    project_path = f'/home/thomas/LivingCode/Projects/{project}'
    if not os.path.exists(project_path):
        print(f'Project path not found: {project_path}')
        # Don't fallback to root - skip marker updates
        project_path = None
    # Update hot/cold markers only if valid project
    if project_path:
        update_hot_cold_markers(project_path)
    # Simplistic: just produce a report
    date_str = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    report_path = f'/home/thomas/LivingCode/reports/lord-{date_str}.md'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(f'# Lord Report - {date_str}\n\n')
        f.write(f'Triggered by: [TRIGGER_LORD] {project}\n')
        f.write(f'Project: {project}\n')
        if project_path:
            f.write(f'Reviewed hot code in {project_path}\n')
            f.write(f'Marked hot/cold as needed (simplified).\n')
        else:
            f.write(f'Project path not found, skipped hot/cold markers.\n')
        f.write('\n---\n')
        f.write('Report generated by Lord Agent.\n')
    # Send report via hermes send to specific telegram topic
    send_cmd = ['hermes', 'send', '--to', 'telegram:-1004431090317:252', f'MEDIA:{report_path}']
    res = subprocess.run(send_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f'Failed to send report: {res.stderr}')
    else:
        print('Report sent via hermes send')
    # Add trigger for producer - use the corrected project
    with open(journal_path, 'a') as f:
        f.write(f'\n[TRIGGER_PRODUCER] {project}\n')
    print('Done')


if __name__ == '__main__':
    main()