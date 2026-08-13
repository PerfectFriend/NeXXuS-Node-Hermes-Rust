import sys
f = open('src/App.tsx','r',encoding='utf-8')
content = f.read()
f.close()

start = content.index('return (')
end = content.rindex(');')
jsx_section = content[start:end+2]

# Count braces ignoring strings and template literals
depth = 0
in_single = False
in_double = False
in_template = False
template_depth = 0
i = 0
line = content[:start].count('\n') + 1

while i < len(jsx_section):
    c = jsx_section[i]
    nc = jsx_section[i+1] if i+1 < len(jsx_section) else ''
    
    if in_single:
        if c == '\\':
            i += 1
        elif c == "'":
            in_single = False
    elif in_double:
        if c == '\\':
            i += 1
        elif c == '"':
            in_double = False
    elif in_template:
        if c == '`':
            in_template = False
        elif c == '$' and nc == '{':
            template_depth += 1
        elif c == '}':
            if template_depth > 0:
                template_depth -= 1
    elif c == '`':
        in_template = True
    elif c == "'":
        in_single = True
    elif c == '"':
        in_double = True
    elif c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
        if depth < 0:
            actual_line = line + jsx_section[:i].count('\n')
            context = jsx_section[max(0,i-40):i+1]
            print(f'NEGATIVE DEPTH {depth} at approx line {actual_line}')
            print(f'Context: ...{context}...')
            break
    
    i += 1

print(f'Final depth: {depth}')
if depth > 0:
    # Find where depth is still > 0
    depth = 0
    i = 0
    for i, c in enumerate(jsx_section):
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        if depth == 0 and i > len(jsx_section) * 0.9:
            actual_line = line + jsx_section[:i].count('\n')
            print(f'Depth returns to 0 at approx line {actual_line}')
            break
