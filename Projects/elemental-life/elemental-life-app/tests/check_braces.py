"""
Living Code Project elemental-life - Cycle 999 Subcycle 1
Auto-evolved by Evolution Engine using nemotron-3-ultra
"""

import sys, re
f = open('src/App.tsx', 'r', encoding='utf-8')
content = f.read()
f.close()

matches = list(re.finditer(r'return \(', content))
# Second match is the main component JSX return
if len(matches) >= 2:
    ret_idx = matches[1].start()
else:
    ret_idx = matches[0].start()
ret_start_line = content[:ret_idx].count('\n') + 1
jsx_part = content[ret_idx:]

depth = 0
in_dq = False
in_sq = False
in_tl = False
tl_dep = 0

lines = jsx_part.split('\n')
for i, line in enumerate(lines):
    j = 0
    while j < len(line):
        ch = line[j]
        nch = line[j+1] if j+1 < len(line) else ''
        
        if in_tl:
            if ch == '`':
                in_tl = False
            elif ch == '$' and nch == '{':
                tl_dep += 1
                j += 1
            elif ch == '}' and tl_dep > 0:
                tl_dep -= 1
        elif in_dq:
            if ch == '\\':
                j += 1
            elif ch == '"':
                in_dq = False
        elif in_sq:
            if ch == '\\':
                j += 1
            elif ch == "'":
                in_sq = False
        elif ch == '`':
            in_tl = True
        elif ch == '"':
            in_dq = True
        elif ch == "'":
            in_sq = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        
        j += 1
    
    if depth < 0:
        print(f'NEGATIVE at return-line {i+1} (file line ~{ret_start_line+i})')
        print(f'  Content: {line.strip()}')
        break
    if i == len(lines) - 3:  # near the end
        print(f'Line {ret_start_line+i}: depth={depth}, content={line.strip()!r}')

print(f'Final depth: {depth}')
