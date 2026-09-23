import re
import sys

textbook_path = '/home/thomas/Documents/ObsidianVault/Учебник.md'
with open(textbook_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Map line index to priority (nearest preceding section with priority)
priority_at_line = [0] * len(lines)
current_priority = 0
for i, line in enumerate(lines):
    # Match section headers like "### 1. Graph Engineering & Evolution (priority: 10)"
    m = re.search(r'### .*\(priority: (\d+)\)', line)
    if m:
        current_priority = int(m.group(1))
    priority_at_line[i] = current_priority

# Pattern for not-studied items: "- [ ] something — 🔴"
pattern = re.compile(r'^- \[ \] (.+?)(?: — 🔴| — 🟡| — 🟢)')
red_items = []  # only 🔴
for i, line in enumerate(lines):
    if '🔴' in line:
        m = pattern.search(line)
        if m:
            topic = m.group(1).strip()
            prio = priority_at_line[i]
            red_items.append((prio, i+1, topic, line.strip()))

# Sort by priority descending, then line number
red_items.sort(key=lambda x: (-x[0], x[1]))
# Output as JSON for easier consumption
import json
print(json.dumps(red_items, indent=2, ensure_ascii=False))
