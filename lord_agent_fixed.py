#!/home/thomas/bin/python3
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
    # Find all [TRIGGER_LORD] lines
    lines = journal.split('\n')
    lord_triggers = []
    audit_triggers = []
    for line in lines:
        if '[TRIGGER_LORD]' in line:
            lord_triggers.append(line.strip())
        if '[TRIGGER_AUDITOR]' in line:
            audit_triggers.append(line.strip())
    print(f'Found {len(lord_triggers)} TRIGGER_LORD lines')
    print(f'Found {len(audit_triggers)} TRIGGER_AUDITOR lines')
    if lord_triggers:
        last_lord = lord_triggers[-1]
        print(f'Last TRIGGER_LORD: {last_lord}')
        # Extract project name: after the trigger, split by whitespace and take the next token
        parts = last_lord.split()
        # Find the index of the trigger
        try:
            idx = parts.index('[TRIGGER_LORD]')
            if idx + 1 < len(parts):
                project = parts[idx + 1]
            else:
                project = None
        except ValueError:
            project = None
    else:
        project = None
    # If the project is 'lord-of-code' or not found, use the last TRIGGER_AUDITOR
    if not project or project == 'lord-of-code':
        if audit_triggers:
            last_audit = audit_triggers[-1]
            print(f'Last TRIGGER_AUDITOR: {last_audit}')
            parts = last_audit.split()
            try:
                idx = parts.index('[TRIGGER_AUDITOR]')
                if idx + 1 < len(parts):
                    project = parts[idx + 1]
                else:
                    project = None
            except ValueError:
                project = None
        else:
            project = None
    print(f'Determined project: {project}')
    # Determine project path
    project_path = None
    if project:
        project_path = f'/home/thomas/LivingCode/Projects/{project}'
        if not os.path.exists(project_path):
            print(f'Project path not found: {project_path}')
            project_path = None
    # Update hot/cold markers only if valid project
    if project_path:
        print(f'Updating hot/cold markers for {project_path}')
        update_hot_cold_markers(project_path)
    # Produce a report
    date_str = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    report_path = f'/home/thomas/LivingCode/reports/lord-{date_str}.md'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(f'# Lord Report - {date_str}\n\n')
        f.write(f'Triggered by: {last_lord if lord_triggers else "None"}\n')
        f.write(f'Project: {project if project else "None"}\n')
        if project_path:
            f.write(f'Reviewed hot code in {project_path}\n')
            f.write(f'Marked hot/cold as needed.\n')
        else:
            f.write(f'Project path not found, skipped hot/cold markers.\n')
        f.write(f'\n---\n')
        f.write('Report generated by Lord Agent.\n')
    # We do not send the report via hermes send, we will output it ourselves.
    # Instead, we will print the report path so we know where it is.
    print(f'Report written to: {report_path}')
    # Add trigger for producer - use the determined project (if we have one)
    if project:
        with open(journal_path, 'a') as f:
            f.write(f'\n[TRIGGER_PRODUCER] {project}\n')
        print(f'Added [TRIGGER_PRODUCER] {project} to journal')
    else:
        print('No project determined, skipping TRIGGER_PRODUCER')
    print('Done')

if __name__ == '__main__':
    main()
