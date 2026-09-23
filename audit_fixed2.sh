#!/bin/bash
set -euo pipefail

REPORT_DIR="/home/thomas/LivingCode/reports"
TIMESTAMP=$(date +%Y%m%d-%H%M)
REPORT_FILE="${REPORT_DIR}/auditor-${TIMESTAMP}.md"
mkdir -p "$REPORT_DIR"

echo "# Аудиторский отчёт" > "$REPORT_FILE"
echo "**Дата:** $(date)" >> "$REPORT_FILE"
echo "**Аудитор:** Антон Викторович" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# List of projects to audit
declare -a PROJECTS=(
    "/home/thomas/LivingCode/Projects/elemental-life"
    "/home/thomas/LivingCode/Projects/elemental-life-2"
    "/home/thomas/LivingCode/Projects/superguard"
    "/home/thomas/LivingCode/Projects/boss_fight_system"
    "/home/thomas/LivingCode/Projects/main_menu_ui"
    "/home/thomas/LivingCode/Projects/cybertarot"
    "/home/thomas/LivingCode/Projects/elemental-life-game-by-toto"
    "/home/thomas/LivingCode/CompleteProjects/superguard_20260816_232832"
    "/home/thomas/LivingCode/projects/LivingCode-elemental-life-001"
    "/home/thomas/LivingCode/projects/LivingCode-superguard-001"
)

for proj in "${PROJECTS[@]}"; do
    proj_name=$(basename "$proj")
    echo "## Аудит проекта: $proj_name" >> "$REPORT_FILE"
    echo "**Путь:** $proj" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    if [[ ! -d "$proj" ]]; then
        echo "❌ Проект не найден" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        continue
    fi
    
    # Check README
    if [[ -f "$proj/README.md" ]]; then
        echo "✅ README.md присутствует" >> "$REPORT_FILE"
    else
        echo "❌ README.md отсутствует" >> "$REPORT_FILE"
    fi
    
    # Check for test files and try to run tests
    TEST_RESULT="Неизвестно"
    if [[ -f "$proj/package.json" ]]; then
        # Node.js project
        if grep -q '"test"' "$proj/package.json"; then
            echo "🔍 Найден test скрипт в package.json" >> "$REPORT_FILE"
            # Try to run test (but may fail due to missing deps; we'll just check if script exists)
            TEST_RESULT="Тест скрипт определён"
        else
            TEST_RESULT="Нет test скрипта в package.json"
        fi
    elif [[ -f "$proj/pytest.ini" || -f "$proj/requirements.txt" || -f "$proj/setup.py" || -f "$proj/tox.ini" ]]; then
        # Python project
        TEST_RESULT="Python проект (проверьте наличие тестов)"
    else
        TEST_RESULT="Не определён тип проекта"
    fi
    echo "🧪 Тесты: $TEST_RESULT" >> "$REPORT_FILE"
    
    # Security checks: eval, exec, hardcoded secrets
    echo "🔒 Проверка на опасные паттерны:" >> "$REPORT_FILE"
    # We'll search for eval, exec, process.env, API_KEY, secret, password, etc.
    # Use grep with -i and exclude node_modules, .git, dist, etc.
    SECRETS=$(grep -r -i -m 5 -E 'eval\(|exec\(|process\.env|API_KEY|SECRET|PASSWORD|TOKEN' "$proj" --include="*.js" --include="*.ts" --include="*.py" --include="*.json" --exclude-dir={node_modules,.git,dist,build,__pycache__} 2>/dev/null || true)
    if [[ -z "$SECRETS" ]]; then
        echo "✅ Очевидных опасных паттернов не найдено" >> "$REPORT_FILE"
    else
        echo "⚠️ Найдены потенциально опасные паттерны:" >> "$REPORT_FILE"
        echo "$SECRETS" >> "$REPORT_FILE"
    fi
    
    # Check for shell injection patterns (like concatenation into exec)
    SHELL_INJ=$(grep -r -m 3 -E '(system\(|popen\(|exec\s*\(|spawn\s*\(.*\+\|`.*\`' "$proj" --include="*.js" --include="*.ts" --include="*.py" --exclude-dir={node_modules,.git,dist,build,__pycache__} 2>/dev/null || true)
    if [[ -z "$SHELL_INJ" ]]; then
        echo "✅ Паттернов shell-инъекций не обнаружено" >> "$REPORT_FILE"
    else
        echo "⚠️ Возможные shell-инъекции:" >> "$REPORT_FILE"
        echo "$SHELL_INJ" >> "$REPORT_FILE"
    fi
    
    # Try to run a quick syntax check if possible
    SYNTAX_OK="Не проверено"
    if [[ -f "$proj/package.json" ]]; then
        # Check JS files for syntax with node -c
        JS_FILES=$(find "$proj" -name "*.js" -not -path "*/node_modules/*" -not -path "*/dist/*" | head -5)
        if [[ -n "$JS_FILES" ]]; then
            SYNTAX_OK="Проверка синтаксиса JS:"
            for f in $JS_FILES; do
                if node -c "$f" 2>/dev/null; then
                    SYNTAX_OK="$SYNTAX_OK
  ✅ $f"
                else
                    SYNTAX_OK="$SYNTAX_OK
  ❌ $f (ошибка синтаксиса)"
                fi
            done
        fi
    elif [[ -f "$proj/requirements.txt" || -f "$proj/setup.py" ]]; then
        # Python syntax check
        PY_FILES=$(find "$proj" -name "*.py" -not -path "*/__pycache__/*" | head -5)
        if [[ -n "$PY_FILES" ]]; then
            SYNTAX_OK="Проверка синтаксиса Python:"
            for f in $PY_FILES; do
                if python3 -m py_compile "$f" 2>/dev/null; then
                    SYNTAX_OK="$SYNTAX_OK
  ✅ $f"
                else
                    SYNTAX_OK="$SYNTAX_OK
  ❌ $f (ошибка синтаксиса)"
                fi
            done
        fi
    fi
    echo "$SYNTAX_OK" >> "$REPORT_FILE"
    
    # Documentation beyond README
    if [[ -d "$proj/docs" ]]; then
        echo "📂 Наличие каталога docs/ ✅" >> "$REPORT_FILE"
    else
        echo "📂 Каталог docs/ отсутствует" >> "$REPORT_FILE"
    fi
    
    echo "" >> "$REPORT_FILE"
    echo "--" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
done

echo "## Заключение" >> "$REPORT_FILE"
echo "Аудит завершен. Рекомендации: устранить предупреждения, добавить недостающие тесты и документацию." >> "$REPORT_FILE"

echo "Отчёт сохранён в $REPORT_FILE"