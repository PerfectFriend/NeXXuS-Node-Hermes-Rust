# HOT
#!/bin/bash
set -e
PROJECTS=(
    "elemental-life"
    "elemental-life-2"
    "superguard"
    "LivingCode-boss_fight_system-001"
    "LivingCode-main_menu_ui-001"
    "cybertarot"
    "elemental-life-game-by-toto"
    "LivingCode-elemental-life-001"
    "LivingCode-elemental-life-2-001"
    "LivingCode-superguard-001"
)
BASE="/home/thomas/LivingCode/Projects"
REPORT_DIR="/home/thomas/LivingCode/reports"
TIMESTAMP=$(date +%Y%m%d-%H%M)
REPORT_FILE="${REPORT_DIR}/auditor-${TIMESTAMP}.md"
mkdir -p "$REPORT_DIR"
echo "# Отчёт аудитора-Аудитора Алексей Иванович" > "$REPORT_FILE"
echo "Дата: $(date '+%Y-%m-%d %H:%M:%S')" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## Список аудируемых проектов" >> "$REPORT_FILE"
for i in "${!PROJECTS[@]}"; do
    echo "$((i+1)). ${PROJECTS[$i]}" >> "$REPORT_FILE"
done
echo "" >> "$REPORT_FILE"
echo "## Результаты аудита" >> "$REPORT_FILE"
for proj in "${PROJECTS[@]}"; do
    echo "### $proj" >> "$REPORT_FILE"
    proj_path="${BASE}/${proj}"
    if [[ ! -d "$proj_path" ]]; then
        echo "**Ошибка:** Директория не найдена: $proj_path" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        continue
    fi
    echo "Путь: $proj_path" >> "$REPORT_FILE"
    # README
    if [[ -f "$proj_path/README.md" ]]; then
        echo "- README.md: найден" >> "$REPORT_FILE"
    else
        echo "- README.md: **отсутствует**" >> "$REPORT_FILE"
    fi
    # Security check: grep for dangerous patterns (simplified)
    echo "- Выполняется проверка на опасные паттерны..." >> "$REPORT_FILE"
    # We'll search for eval, exec, hardcoded secrets, etc.
    # Use grep -r with --include patterns
    SEC_ISSUES=$(grep -r -i --include="*.py" --include="*.js" --include="*.ts" --include="*.java" --include="*.cpp" --include="*.c" --include="*.cs" --include="*.go" --include="*.rb" --include="*.php" "eval\s*\|exec\s*\|os\.system\|subprocess\.call.*shell=True\|subprocess\.run.*shell=True\|password\s*=\|passwd\s*=\|secret\s*=\|api[_-]?key\s*=\|token\s*=\|Bearer\s" "$proj_path" 2>/dev/null | head -20 || true)
    if [[ -n "$SEC_ISSUES" ]]; then
        echo "- **Проблемы безопасности:**" >> "$REPORT_FILE"
        echo "$SEC_ISSUES" | while read -r line; do
            echo "  - $line" >> "$REPORT_FILE"
        done
    else
        echo "- Проблемы безопасности: **не обнаружены**" >> "$REPORT_FILE"
    fi
    # Test check
    echo "- Проверка наличия тестов..." >> "$REPORT_FILE"
    TEST_DIRS=("tests" "test" "__tests__" "spec")
    TEST_FOUND=0
    for td in "${TEST_DIRS[@]}"; do
        if [[ -d "$proj_path/$td" ]]; then
            TEST_FOUND=1
            break
        fi
    done
    if [[ $TEST_FOUND -eq 0 ]]; then
        # look for test files
        if find "$proj_path" -type f -name "test_*.py" -o -name "*_test.py" -o -name "*.test.js" -o -name "*.spec.js" -o -name "*_test.go" -o -name "*_test.rs" | head -5 | grep -q .; then
            TEST_FOUND=1
        fi
    fi
    if [[ $TEST_FOUND -eq 1 ]]; then
        echo "- Тестовая директория: найдена" >> "$REPORT_FILE"
        # Try to run tests based on project type
        if [[ -f "$proj_path/package.json" ]]; then
            echo "- Запуск npm test..." >> "$REPORT_FILE"
            (cd "$proj_path" && npm test 2>&1 | head -30) >> "$REPORT_FILE" 2>&1 || echo "npm test завершился с ошибкой (см. выше)" >> "$REPORT_FILE"
        elif [[ -f "$proj_path/pyproject.toml" || -f "$proj_path/setup.py" || -f "$proj_path/requirements.txt" || -f "$proj_path/Pipfile" ]]; then
            echo "- Запуск pytest..." >> "$REPORT_FILE"
            (cd "$proj_path" && python -m pytest 2>&1 | head -30) >> "$REPORT_FILE" 2>&1 || echo "pytest завершился с ошибкой" >> "$REPORT_FILE"
        elif [[ -f "$proj_path/Cargo.toml" ]]; then
            echo "- Запуск cargo test..." >> "$REPORT_FILE"
            (cd "$proj_path" && cargo test 2>&1 | head -30) >> "$REPORT_FILE" 2>&1 || echo "cargo test завершился с ошибкой" >> "$REPORT_FILE"
        else
            echo "- Тесты: не удалось определить тип проекта для автоматического запуска" >> "$REPORT_FILE"
        fi
    else
        echo "- Тестовая директория: **отсутствует**" >> "$REPORT_FILE"
    fi
    # Documentation check
    echo "- Проверка документации..." >> "$REPORT_FILE"
    DOC_DIRS=("docs" "doc" "documentation")
    DOC_FOUND=0
    for dd in "${DOC_DIRS[@]}"; do
        if [[ -d "$proj_path/$dd" ]]; then
            DOC_FOUND=1
            break
        fi
    done
    if [[ $DOC_FOUND -eq 1 ]]; then
        echo "- Документация (директория docs/): найдена" >> "$REPORT_FILE"
    else
        echo "- Документация (директория docs/): **отсутствует**" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"
done
echo "## Вывод" >> "$REPORT_FILE"
echo "Аудит завершён." >> "$REPORT_FILE"