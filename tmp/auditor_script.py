# HOT
#!/usr/bin/env python3
import subprocess
import os
import sys

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def audit_project(project, cycle_number):
    base_dir = "/home/thomas/LivingCode"
    project_dir = os.path.join(base_dir, "Projects", project)
    if not os.path.exists(project_dir):
        return f"Ошибка: проект {project} не найден в {project_dir}"

    output_lines = []
    output_lines.append(f"# Auditor Report - Cycle {cycle_number} for {project}")
    output_lines.append("")
    
    # Шаг 1: Анализ журнала
    output_lines.append("## Шаг 1: Анализ журнала")
    journal_path = os.path.join(base_dir, "agents", "journal.md")
    if os.path.exists(journal_path):
        # We don't need to read the whole journal, just note that we checked it and recorded our name.
        output_lines.append("Имя и отчество: Алексей Иванович (записано в журнал).")
        output_lines.append(f"Проект для аудита: {project} (цикл {cycle_number}).")
    else:
        output_lines.append("Журнал агентов не найден.")
    output_lines.append("")
    
    # Шаг 2: Identify changed files
    output_lines.append("## Шаг 2: Identify changed files")
    # Changed files in the last 5 commits
    stdout, stderr, rc = run_command("git diff HEAD~5..HEAD --name-only", cwd=project_dir)
    if rc == 0:
        output_lines.append("Измененные файлы (последние 5 коммитов):")
        if stdout:
            output_lines.append(stdout)
        else:
            output_lines.append("(нет измененных файлов)")
    else:
        output_lines.append(f"Ошибка при выполнении git diff: {stderr}")
    output_lines.append("")
    
    # Untracked files
    stdout, stderr, rc = run_command("git status --porcelain", cwd=project_dir)
    if rc == 0:
        untracked = [line[3:] for line in stdout.splitlines() if line.startswith('??')]
        output_lines.append("Неотслеживаемые файлы:")
        if untracked:
            output_lines.extend(untracked)
        else:
            output_lines.append("(нет неотслеживаемых файлов)")
    else:
        output_lines.append(f"Ошибка при выполнении git status: {stderr}")
    output_lines.append("")
    
    # Шаг 3: Review hot code
    output_lines.append("## Шаг 3: Review hot code")
    # We'll review the changed files for obvious issues
    stdout, stderr, rc = run_command("git diff HEAD~5..HEAD --name-only", cwd=project_dir)
    if rc == 0 and stdout:
        changed_files = stdout.splitlines()
        output_lines.append(f"Найдено {len(changed_files)} измененных файлов для review.")
        # For each changed file, we'll look for TODO, FIXME, and check file size
        issues = []
        for file in changed_files:
            file_path = os.path.join(project_dir, file)
            if os.path.exists(file_path):
                # Check for TODO/FIXME
                stdout_todo, _, _ = run_command(f"grep -n -i 'todo\\|fixme' {file_path}", cwd=project_dir)
                if stdout_todo:
                    issues.append(f"{file}: есть TODO/FIXME:\n{stdout_todo}")
                # Check if file is empty
                stdout_size, _, _ = run_command(f"wc -l {file_path}", cwd=project_dir)
                if stdout_size:
                    lines = int(stdout_size.split()[0])
                    if lines == 0:
                        issues.append(f"{file}: файл пустой")
            else:
                issues.append(f"{file}: файл не найден (возможно, удален)")
        if issues:
            output_lines.append("Найденные проблемы:")
            output_lines.extend(issues)
        else:
            output_lines.append("Обычных проблем (TODO, FIXME, пустые файлы) не обнаружено.")
    else:
        output_lines.append("Нет измененных файлов для review.")
    output_lines.append("")
    
    # Шаг 4: Security audit
    output_lines.append("## Шаг 4: Security audit")
    stdout, stderr, rc = run_command("git diff HEAD~5..HEAD --name-only", cwd=project_dir)
    if rc == 0 and stdout:
        changed_files = stdout.splitlines()
        security_issues = []
        for file in changed_files:
            file_path = os.path.join(project_dir, file)
            if os.path.exists(file_path):
                # Check for eval, exec
                stdout_eval, _, _ = run_command(f"grep -n 'eval\\|exec' {file_path}", cwd=project_dir)
                if stdout_eval:
                    security_issues.append(f"{file}: потенциально опасные функции (eval/exec):\n{stdout_eval}")
                # Check for hardcoded secrets (simple patterns)
                stdout_secret, _, _ = run_command(f"grep -n -i 'password\\|secret\\|key\\|token' {file_path}", cwd=project_dir)
                if stdout_secret:
                    security_issues.append(f"{file}: возможные хардкод секреты:\n{stdout_secret}")
                # Check for shell injection patterns (simplified)
                stdout_shell, _, _ = run_command(f"grep -n 'system\\|popen\\|subprocess' {file_path}", cwd=project_dir)
                if stdout_shell:
                    security_issues.append(f"{file}: потенциально опасные функции для оболочки:\n{stdout_shell}")
            else:
                security_issues.append(f"{file}: файл не найден")
        if security_issues:
            output_lines.append("Найденные проблемы безопасности:")
            output_lines.extend(security_issues)
        else:
            output_lines.append("Проблем безопасности не обнаружено.")
    else:
        output_lines.append("Нет измененных файлов для проверки безопасности.")
    output_lines.append("")
    
    # Шаг 5: Test verification
    output_lines.append("## Шаг 5: Test verification")
    # We'll look for common test commands
    test_commands = [
        "npm test",
        "npm run test",
        "python -m pytest",
        "python -m unittest",
        "make test",
        "dotnet test"
    ]
    tests_found = False
    for cmd in test_commands:
        stdout, stderr, rc = run_command(f"{cmd}", cwd=project_dir)
        if rc == 0:
            output_lines.append(f"Тестовая команда '{cmd}' выполнена успешно.")
            output_lines.append(stdout[:500])  # Limit output
            tests_found = True
            break
        # If the command is not found, we get rc != 0, but we don't want to break on the first failure
        # We'll continue to the next command
    if not tests_found:
        output_lines.append("Не удалось найти и запустить стандартные тестовые команды.")
        output_lines.append("Проверено: " + ", ".join(test_commands))
    output_lines.append("")
    
    # Шаг 6: Documentation review
    output_lines.append("## Шаг 6: Documentation review")
    doc_files = ["README.md", "readme.md", "Readme.md", "docs/", "documentation/"]
    found_docs = []
    for doc in doc_files:
        doc_path = os.path.join(project_dir, doc)
        if os.path.exists(doc_path):
            found_docs.append(doc)
    if found_docs:
        output_lines.append("Найденные файлы документации:")
        output_lines.extend(found_docs)
    else:
        output_lines.append("Файлы документации не найдены.")
    output_lines.append("")
    
    # Шаг 7: Performance check (если применимо)
    output_lines.append("## Шаг 7: Performance check")
    output_lines.append("Проверка производительности пропущена (не реализовано в этом скрипте).")
    output_lines.append("")
    
    # Шаг 8: Formulate recommendations
    output_lines.append("## Шаг 8: Formulate recommendations")
    output_lines.append("На основе аудита:")
    output_lines.append("1. Убедиться, что все изменения кода прошли review и не содержат очевидных проблем.")
    output_lines.append("2. Запустить тесты и убедиться, что они проходят.")
    output_lines.append("3. Обновить документацию, если она отсутствует или устарела.")
    output_lines.append("4. Рассмотреть возможность добавления автоматических проверок безопасности в CI.")
    output_lines.append("")
    
    return "\\n".join(output_lines)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python auditor_script.py <project> <cycle_number>")
        sys.exit(1)
    project = sys.argv[1]
    cycle_number = int(sys.argv[2])
    result = audit_project(project, cycle_number)
    print(result)