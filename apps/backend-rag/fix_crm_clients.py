#!/usr/bin/env python3
"""
Fix B904 and F841 errors in crm_clients.py
"""

import re

def fix_crm_clients(file_path):
    """Fix B904 and F841 errors"""

    with open(file_path, 'r') as f:
        content = f.read()

    lines = content.split('\n')

    # Track state
    in_except = False

    for i, line in enumerate(lines):
        # Check if we're entering an except block
        if line.strip().startswith('except ') and ' as e:' in line:
            in_except = True
        elif line.strip().startswith(('except', 'finally', 'try', 'def', 'class', 'if', 'for', 'while')):
            if not line.strip().startswith('except '):
                in_except = False

        # Fix B904: Add 'from e' to raise HTTPException statements in except blocks
        if in_except and 'raise HTTPException(' in line and 'from e' not in line:
            lines[i] = line + ' from e'

        # Fix F841: Remove unused variables (simple cases)
        if 'start_time = time.time()' in line:
            # Check if start_time is used later in the function
            func_start = i
            func_end = i
            for j in range(i, len(lines)):
                if lines[j].strip().startswith(('def ', 'class ', '@')):
                    func_end = j
                    break
            # Check if start_time is used
            used = False
            for j in range(i, func_end):
                if 'start_time' in lines[j] and 'time.time()' not in lines[j]:
                    used = True
                    break
            if not used:
                lines[i] = line.replace('start_time = time.time()', '# start_time = time.time()  # Unused')

        # Fix trailing whitespace
        if line.endswith(' '):
            lines[i] = line.rstrip()

    content = '\n'.join(lines)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed errors in {file_path}")

if __name__ == "__main__":
    fix_crm_clients("backend/app/routers/crm_clients.py")
