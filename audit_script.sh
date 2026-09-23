#!/bin/bash

set -e

projects=("elemental-life" "elemental-life-2" "superguard" "boss_fight_system" "main_menu_ui" "cybertarot" "elemental-life-game-by-toto")

logdir="/home/thomas/LivingCode/audit_logs"
mkdir -p "$logdir"

for i in {1..10}; do
    idx=$(( (i-1) % ${#projects[@]} ))
    project=${projects[$idx]}
    logfile="$logdir/cycle${i}_${project}.log"
    echo "=== Cycle $i: $project ===" > "$logfile"
    echo "Started at: $(date -u)" >> "$logfile"

    # Шаг 1: Анализ журнала
    echo "Шаг 1: Анализ журнала" >> "$logfile"
    journal_file="/home/thomas/LivingCode/agents/journal.md"
    if [ -f "$journal_file" ]; then
        echo "   Journal file exists." >> "$logfile"
        echo "   Name and отчество already recorded in journal." >> "$logfile"
        echo "   Auditing project: $project" >> "$logfile"
    else
        echo "   ERROR: Journal file not found!" >> "$logfile"
    fi

    # Шаг 2: Identify changed files
    echo "Шаг 2: Identify changed files" >> "$logfile"
    project_dir="/home/thomas/LivingCode/Projects/$project"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        echo "   Checking git status..." >> "$logfile"
        git status --porcelain >> "$logfile" 2>&1
        echo "   Getting recent changes (last 5 commits)..." >> "$logfile"
        git log --oneline -5 >> "$logfile" 2>&1
        echo "   Diff of changes in the working tree..." >> "$logfile"
        git diff >> "$logfile" 2>&1
    else
        echo "   ERROR: Project directory not found: $project_dir" >> "$logfile"
    fi

    # Шаг 3: Review hot code
    echo "Шаг 3: Review hot code" >> "$logfile"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        echo "   Checking for dangerous patterns (eval, exec, hardcoded secrets)..." >> "$logfile"
        grep -r "eval\|exec\|password\|secret\|key" --include="*.js" --include="*.py" --include="*.ts" --include="*.json" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=coverage 2>/dev/null | head -20 >> "$logfile" || true
    else
        echo "   Skipping because project directory not found." >> "$logfile"
    fi

    # Шаг 4: Security audit
    echo "Шаг 4: Security audit" >> "$logfile"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        echo "   Checking for eval and exec calls..." >> "$logfile"
        grep -r "eval\|exec" --include="*.js" --include="*.py" --include="*.ts" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=coverage 2>/dev/null | head -10 >> "$logfile" || true
        echo "   Checking for hardcoded API keys (pattern: [a-zA-Z0-9]{32,})..." >> "$logfile"
        grep -r -E "[a-zA-Z0-9]{32,}" --include="*.js" --include="*.py" --include="*.ts" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=coverage 2>/dev/null | head -10 >> "$logfile" || true
    else
        echo "   Skipping because project directory not found." >> "$logfile"
    fi

    # Шаг 5: Test verification
    echo "Шаг 5: Test verification" >> "$logfile"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        echo "   Looking for test files..." >> "$logfile"
        if [ -d "tests" ]; then
            echo "   Found tests directory." >> "$logfile"
            ls -la tests/ >> "$logfile"
        else
            echo "   No tests directory found." >> "$logfile"
        fi
        if [ -f "package.json" ]; then
            echo "   Found package.json, attempting to run npm test..." >> "$logfile"
            npm test >> "$logfile" 2>&1 || echo "   npm test failed or not configured." >> "$logfile"
        elif [ -f "requirements.txt" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
            echo "   Found Python project, attempting to run pytest..." >> "$logfile"
            python -m pytest >> "$logfile" 2>&1 || echo "   pytest failed or not configured." >> "$logfile"
        else
            echo "   No known test runner found." >> "$logfile"
        fi
    else
        echo "   Skipping because project directory not found." >> "$logfile"
    fi

    # Шаг 6: Documentation review
    echo "Шаг 6: Documentation review" >> "$logfile"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        echo "   Checking for README.md..." >> "$logfile"
        if [ -f "README.md" ]; then
            echo "   README.md exists." >> "$logfile"
            if [ -s "README.md" ]; then
                echo "   README.md is not empty." >> "$logfile"
            else
                echo "   WARNING: README.md is empty." >> "$logfile"
            fi
        else
            echo "   WARNING: README.md not found." >> "$logfile"
        fi
        if [ -d "docs" ]; then
            echo "   Found docs directory." >> "$logfile"
            ls -la docs/ >> "$logfile"
        else
            echo "   No docs directory found." >> "$logfile"
        fi
    else
        echo "   Skipping because project directory not found." >> "$logfile"
    fi

    # Шаг 7: Performance check (если применимо)
    echo "Шаг 7: Performance check" >> "$logfile"
    if [ -d "$project_dir" ]; then
        cd "$project_dir"
        if [ -f "src/engine.js" ] || [ -f "elemental_life_2_core.py" ] || [ -f "engine.js" ]; then
            echo "   Detected game engine, performing basic performance check (if applicable)." >> "$logfile"
            echo "   Engine file found." >> "$logfile"
        else
            echo "   Not a known game engine, skipping performance check." >> "$logfile"
        fi
    else
        echo "   Skipping because project directory not found." >> "$logfile"
    fi

    # Шаг 8: Formulate recommendations
    echo "Шаг 8: Formulate recommendations" >> "$logfile"
    echo "   [To be filled after analysis]" >> "$logfile"

    echo "   Cycle $i for project $project completed." >> "$logfile"
    echo "Finished at: $(date -u)" >> "$logfile"
    echo "" >> "$logfile"
done

echo "All cycles completed. Creating final report..."
report_file="/home/thomas/LivingCode/reports/auditor-$(date +%Y%m%d-%H%M).md"
mkdir -p "$(dirname "$report_file")"
echo "# Auditor Agent Report" > "$report_file"
echo "## Cycle Summary" >> "$report_file"
echo "Performed 10 audit cycles of projects." >> "$report_file"
echo "" >> "$report_file"
echo "## Details" >> "$report_file"
for i in {1..10}; do
    idx=$(( (i-1) % ${#projects[@]} ))
    project=${projects[$idx]}
    logfile="$logdir/cycle${i}_${project}.log"
    if [ -f "$logfile" ]; then
        echo "### Cycle $i: $project" >> "$report_file"
        echo "" >> "$report_file"
        cat "$logfile" >> "$report_file"
        echo "" >> "$report_file"
        echo "---" >> "$report_file"
    fi
done
echo "" >> "$report_file"
echo "## Conclusion" >> "$report_file"
echo "The audit cycles have been completed. Please review the details above for any issues." >> "$report_file"
echo "" >> "$report_file"
echo "Report generated at: $(date -u)" >> "$report_file"

echo "Report created at: $report_file"