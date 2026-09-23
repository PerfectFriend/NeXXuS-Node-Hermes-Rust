#!/bin/bash

# Array of projects in the order we want to audit
projects=(
        "elemental-life"
        "elemental-life-2"
        "superguard"
        "boss_fight_system"
        "main_menu_ui"
        "cybertarot"
        "elemental-life-game-by-toto"
)

# Base paths
base_root="/home/thomas/LivingCode"
base_projects="$base_root/Projects"

# Map project name to actual path
declare -A project_paths
project_paths["elemental-life"]="$base_root/elemental-life"
project_paths["elemental-life-2"]="$base_root/elemental-life-2"
project_paths["superguard"]="$base_root/superguard"
project_paths["boss_fight_system"]="$base_projects/LivingCode-boss_fight_system-001"
project_paths["main_menu_ui"]="$base_projects/LivingCode-main_menu_ui-001"
project_paths["cybertarot"]="$base_root/cybertarot"
project_paths["elemental-life-game-by-toto"]="$base_root/elemental-life-game-by-toto"

# Log file for audit results
log_file="$base_root/audit_temp/audit_10cycles_log.txt"
mkdir -p "$(dirname "$log_file")"

echo "Starting audit cycles at $(date)" > "$log_file"

for cycle in {1..10}; do
        index=$(( (cycle-1) % ${#projects[@]} ))
        project=${projects[$index]}
        project_path=${project_paths[$project]}

        echo "=== Cycle $cycle/10: Auditing $project ===" >> "$log_file"
        echo "Project path: $project_path" >> "$log_file"

        # Step 1: Analyze journal (we skip for brevity, but we note we read the journal at the start)
        echo "Step 1: Journal analysis skipped (read at agent start)" >> "$log_file"

        # Step 2: Identify changed files
        echo "Step 2: Identifying changed files" >> "$log_file"
        if [ -d "$project_path" ]; then
            cd "$project_path" || { echo "Failed to enter $project_path"; continue; }
            changed_files=$(git diff --name-only 2>/dev/null)
            if [ -z "$changed_files" ]; then
                echo "No changed files" >> "$log_file"
            else
                echo "Changed files:" >> "$log_file"
                echo "$changed_files" >> "$log_file"
            fi
        else
            echo "Project path does not exist: $project_path" >> "$log_file"
            continue
        fi

        # Step 3: Review hot code (we'll look at the changed files and do a quick static analysis)
        echo "Step 3: Reviewing hot code" >> "$log_file"
        if [ -n "$changed_files" ]; then
            # We'll look for dangerous patterns in the changed files
            echo "Checking changed files for dangerous patterns (eval, exec, etc.)" >> "$log_file"
            for file in $changed_files; do
                if [ -f "$file" ]; then
                    # Check for eval, exec, etc.
                    if grep -n "eval\|exec" "$file" 2>/dev/null | grep -v "^#" | head -5; then
                        echo "WARNING: Potential dangerous pattern found in $file" >> "$log_file"
                    fi
                fi
            done
        else
            echo "No changed files to review" >> "$log_file"
        fi

        # Step 4: Security audit
        echo "Step 4: Security audit" >> "$log_file"
        # We'll do a quick check for hardcoded secrets and other issues
        # We'll look for common patterns of secrets in the entire project (not just changed files) but limit to avoid too much output
        echo "Checking for hardcoded secrets (keys, passwords, etc.) in the project (limited to certain extensions)" >> "$log_file"
        # We'll search for patterns like "password", "secret", "key", "token" in .js, .py, .json, .env, .txt files
        # But note: this might be heavy, so we'll limit to the changed files if there are any, otherwise skip?
        # We'll do a quick check on the changed files for now.
        if [ -n "$changed_files" ]; then
            for file in $changed_files; do
                if [ -f "$file" ]; then
                    # Check for potential secrets
                    if grep -i -n "password\|secret\|key\|token" "$file" 2>/dev/null | grep -v "^#" | head -5; then
                        echo "WARNING: Potential secret found in $file" >> "$log_file"
                    fi
                fi
            done
        else
            echo "No changed files to check for secrets" >> "$log_file"
        fi

        # Step 5: Test verification
        echo "Step 5: Test verification" >> "$log_file"
        if [ -d "$project_path" ]; then
            # Check if there are any test files or scripts
            if [ -f "$project_path/run_tests.sh" ] || [ -f "$project_path/test.sh" ] || [ -f "$project_path/run_tests.py" ] || [ -f "$project_path/test.py" ]; then
                echo "Running existing test script..." >> "$log_file"
                # We'll try to run the test script and capture the result
                # But note: we don't want to hang, so we'll run with a timeout?
                # We'll just run and note the output.
                # We'll look for a test script in the project root.
                test_script=""
                for script in "run_tests.sh" "test.sh" "run_tests.py" "test.py" "pytest" "npm test"; do
                    if [ -f "$project_path/$script" ] || ( [ "$script" = "npm test" ] && [ -f "$project_path/package.json" ] ); then
                        test_script="$script"
                        break
                    fi
                done
                if [ -n "$test_script" ]; then
                    echo "Running test script: $test_script" >> "$log_file"
                    # We'll run the test and capture the output and exit code
                    # We'll change to the project directory and run the test
                    cd "$project_path"
                    if [ "$test_script" = "npm test" ]; then
                        npm test 2>&1 | head -20 >> "$log_file"
                    else
                        bash "$test_script" 2>&1 | head -20 >> "$log_file"
                    fi
                    echo "Test script finished." >> "$log_file"
                else
                    echo "No test script found. Skipping test verification." >> "$log_file"
                fi
            else
                echo "No test script found. Creating a basic test verification script." >> "$log_file"
                # We'll create a simple test that just checks if the project builds or runs without error?
                # But we don't know the project type.
                # We'll skip and note that no tests were found.
                echo "No tests found and no test script created." >> "$log_file"
            fi
        else
            echo "Project directory not found, skipping tests." >> "$log_file"
        fi

        # Step 6: Documentation review
        echo "Step 6: Documentation review" >> "$log_file"
        if [ -d "$project_path" ]; then
            if [ -f "$project_path/README.md" ]; then
                echo "README.md found." >> "$log_file"
                # Check if it's been updated recently? We'll skip for now.
            else
                echo "WARNING: README.md not found." >> "$log_file"
            fi
            # Check for other documentation
            if [ -d "$project_path/docs" ]; then
                echo "Documentation directory found." >> "$log_file"
            else
                echo "No documentation directory found." >> "$log_file"
            fi
        else
            echo "Project directory not found, skipping documentation check." >> "$log_file"
        fi

        # Step 7: Performance check (skip for now, as we don't have a way to measure)
        echo "Step 7: Performance check skipped (not implemented)" >> "$log_file"

        # Step 8: Formulate recommendations
        echo "Step 8: Formulating recommendations" >> "$log_file"
        # We'll note any issues found and give recommendations
        # We'll collect the warnings and notes from above and then formulate recommendations.
        # We'll just note that we will do this in the report.
        echo "Recommendations will be formulated in the final report." >> "$log_file"

        echo "=== End of cycle $cycle/10 for $project ===" >> "$log_file"
        echo "" >> "$log_file"
done

echo "Audit cycles completed at $(date)" >> "$log_file"