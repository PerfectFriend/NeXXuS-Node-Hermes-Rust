#!/bin/bash

REPORT_FILE="/home/thomas/LivingCode/audit_temp/report_ru.md"

echo "# Отчёт аудита" > $REPORT_FILE
echo "Сгенерировано Агентом-Аудитором: Даниил Владимирович" >> $REPORT_FILE
echo "Дата: $(date)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

PROJECTS=(
    "superguard"
    "elemental-life"
    "cybertarot"
    "elemental-life-2"
    "LivingCode-boss_fight_system-001"
    "LivingCode-main_menu_ui-001"
    "elemental-life-game-by-toto"
    "superguard"
    "elemental-life"
    "cybertarot"
)

for PROJECT in "${PROJECTS[@]}"; do
    PROJECT_DIR="/home/thomas/LivingCode/Projects/$PROJECT"
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "Каталог проекта $PROJECT_DIR не существует. Пропуск." >> $REPORT_FILE
        continue
    fi

    cd "$PROJECT_DIR"
    echo "=== Аудит $(pwd) ===" >> "$REPORT_FILE"
    echo "## Исходные файлы" >> "$REPORT_FILE"
    find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" \) | head -20 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "## Проверка опасных шаблонов" >> "$REPORT_FILE"
    # Search for dangerous patterns in source files, excluding .git
    find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" \) | grep -v "/.git/" | xargs grep -n -i -E "eval\(|exec\(|password|secret|api_key|token" 2>/dev/null | head -20 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "## Тестовые файлы" >> "$REPORT_FILE"
    find . \( -name "test_*" -o -name "*_test.*" \) | head -20 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "## Результаты тестов" >> "$REPORT_FILE"
    # Check for Python test files and run pytest if available
    TEST_FILES=$(find . -name "test_*.py" -o -name "*_test.py" 2>/dev/null | head -5)
    if [ -n "$TEST_FILES" ]; then
        echo "Запуск pytest..." >> "$REPORT_FILE"
        python -m pytest 2>&1 | head -30 >> "$REPORT_FILE"
    else
        echo "Не найдено тестовых файлов Python." >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"
    echo "## Документация" >> "$REPORT_FILE"
    find . -name "README.md" -o -name "README.txt" -o -name "DOCUMENTATION.md" -o -name "docs/" | head -10 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "--" >> "$REPORT_FILE"
done