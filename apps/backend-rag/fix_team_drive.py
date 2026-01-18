#!/usr/bin/env python3
"""
Fix B904 errors in team_drive.py
"""

def fix_b904_team_drive(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    in_except = False

    for i, line in enumerate(lines):
        if line.strip().startswith('except ') and (' as e:' in line or 'as e' in line):
            in_except = True
        elif line.strip().startswith(('except', 'finally', 'try', 'def', 'class', 'if', 'for', 'while')):
            if not line.strip().startswith('except '):
                in_except = False

        if in_except and 'raise HTTPException(' in line and 'from e' not in line:
            lines[i] = line + ' from e'

    content = '\n'.join(lines)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed B904 errors in {file_path}")

if __name__ == "__main__":
    fix_b904_team_drive("backend/app/routers/team_drive.py")
