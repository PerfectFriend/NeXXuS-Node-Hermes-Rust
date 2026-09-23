#!/home/thomas/bin/python3
import os
import subprocess
import datetime
import json

# List of projects to audit
projects = [
    ("/home/thomas/LivingCode/Projects/elemental-life", "elemental-life"),
    ("/home/thomas/LivingCode/Projects/elemental-life-2", "elemental-life-2"),
    ("/home/thomas/LivingCode/Projects/superguard", "superguard"),
    ("/home/thomas/LivingCode/Projects/boss_fight_system", "boss_fight_system"),
    ("/home/thomas/LivingCode/Projects/main_menu_ui", "main_menu_ui"),
    ("/home/thomas/LivingCode/Projects/cybertarot", "cybertarot"),
    ("/home/thomas/LivingCode/Projects/elemental-life-game-by-toto", "elemental-life-game-by-toto"),
    ("/home/thomas/LivingCode/CompleteProjects/superguard_20260816_232832", "superguard_20260816_232832"),
    ("/home/thomas/LivingCode/projects/LivingCode-elemental-life-001", "LivingCode-elemental-life-001"),
    ("/home/thomas/LivingCode/projects/LivingCode-superguard-001", "LivingCode-superguard-001"),
]

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=5)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1

def check_readme(project_path):
    readme_path = os.path.join(project_path, "README.md")
    if os.path.isfile(readme_path):
        return "✅ README.md присутствует"
    else:
        return "❌ README.md отсутствует"

def check_tests(project_path):
    # Check for package.json with test script
    package_json = os.path.join(project_path, "package.json")
    if os.path.isfile(package_json):
        try:
            with open(package_json, 'r') as f:
                data = json.load(f)
            if 'scripts' in data and 'test' in data['scripts']:
                return "🔍 Найден test скрипт в package.json"
        except:
            pass
    # Check for Python test configuration
    if os.path.isfile(os.path.join(project_path, "pytest.ini")) or \
       os.path.isfile(os.path.join(project_path, "requirements.txt")) or \
       os.path.isfile(os.path.join(project_path, "setup.py")) or \
       os.path.isfile(os.path.join(project_path, "tox.ini")):
        return "🐍 Python проект (проверьте наличие тестов)"
    return "🧪 Тесты: Не определён тип проекта"

def check_secrets(project_path):
    # Search for eval, exec, process.env, API_KEY, SECRET, PASSWORD, TOKEN
    patterns = [r'eval\(', r'exec\(', r'process\.env', r'API_KEY', r'SECRET', r'PASSWORD', r'TOKEN']
    found = []
    for pattern in patterns:
        cmd = f"grep -r -i -m 1 --include='*.js' --include='*.ts' --include='*.py' --include='*.json' --exclude-dir={{node_modules,.git,dist,build,__pycache__}} '{pattern}' {project_path} 2>/dev/null || true"
        out, _, _ = run_cmd(cmd)
        if out:
            # Take first line only
            line = out.split('\n')[0]
            if line:
                found.append(line)
    if found:
        return "⚠️ Найдены потенциально опасные паттерны:\n" + "\n".join(found[:5])
    else:
        return "✅ Очевидных опасных паттернов не найдено"

def check_shell_injection(project_path):
    # Check for system(, popen(, exec (, spawn ( with concatenation or backticks
    patterns = [r'system\(', r'popen\(', r'exec\s*\(', r'spawn\s*\(.*\+', r'`.*`']
    found = []
    for pattern in patterns:
        cmd = f"grep -r -m 1 --include='*.js' --include='*.ts' --include='*.py' --exclude-dir={{node_modules,.git,dist,build,__pycache__}} '{pattern}' {project_path} 2>/dev/null || true"
        out, _, _ = run_cmd(cmd)
        if out:
            line = out.split('\n')[0]
            if line:
                found.append(line)
    if found:
        return "⚠️ Возможные shell-инъекции:\n" + "\n".join(found[:3])
    else:
        return "✅ Паттернов shell-инъекций не обнаружено"

def check_syntax(project_path):
    # Quick syntax check for JS and Python files
    js_files = []
    py_files = []
    for root, dirs, files in os.walk(project_path):
        # Skip node_modules, .git, dist, build, __pycache__
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', 'dist', 'build', '__pycache__')]
        for f in files:
            if f.endswith('.js'):
                js_files.append(os.path.join(root, f))
            elif f.endswith('.py'):
                py_files.append(os.path.join(root, f))
    # Limit to first 5 of each
    js_files = js_files[:5]
    py_files = py_files[:5]
    results = []
    for f in js_files:
        cmd = f"node -c '{f}' 2>&1"
        out, err, rc = run_cmd(cmd)
        if rc == 0:
            results.append(f"  ✅ {f}")
        else:
            results.append(f"  ❌ {f} (ошибка синтаксиса)")
    for f in py_files:
        cmd = f"python3 -m py_compile '{f}' 2>&1"
        out, err, rc = run_cmd(cmd)
        if rc == 0:
            results.append(f"  ✅ {f}")
        else:
            results.append(f"  ❌ {f} (ошибка синтаксиса)")
    if not results:
        return "Не проверено (нет JS или Python файлов)"
    return "Проверка синтаксиса:\n" + "\n".join(results)

def check_docs(project_path):
    docs_path = os.path.join(project_path, "docs")
    if os.path.isdir(docs_path):
        return "📂 Наличие каталога docs/ ✅"
    else:
        return "📂 Каталог docs/ отсутствует"

def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    report_dir = "/home/thomas/LivingCode/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"auditor-{timestamp}.md")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Аудиторский отчёт\n")
        f.write(f"**Дата:** {datetime.datetime.now().strftime('%a %d %b %Y %H:%M:%S %Z')}\n")
        f.write("**Аудитор:** Антон Викторович\n\n")
        
        for proj_path, proj_name in projects:
            f.write(f"## Аудит проекта: {proj_name}\n")
            f.write(f"**Путь:** {proj_path}\n\n")
            
            if not os.path.isdir(proj_path):
                f.write("❌ Проект не найден\n\n")
                continue
            
            f.write(f"{check_readme(proj_path)}\n\n")
            f.write(f"{check_tests(proj_path)}\n\n")
            f.write("🔒 Проверка на опасные паттерны:\n")
            f.write(f"{check_secrets(proj_path)}\n\n")
            f.write("🔒 Проверка на shell-инъекции:\n")
            f.write(f"{check_shell_injection(proj_path)}\n\n")
            f.write("🔍 Проверка синтаксиса:\n")
            f.write(f"{check_syntax(proj_path)}\n\n")
            f.write(f"{check_docs(proj_path)}\n\n")
            f.write("--\n\n")
        
        f.write("## Заключение\n")
        f.write("Аудит завершен. Рекомендации: устранить предупреждения, добавить недостающие тесты и документацию.\n")
    
    print(f"Report written to {report_file}")

if __name__ == "__main__":
    main()