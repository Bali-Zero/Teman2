#!/usr/bin/env python3
"""
Fix B904 errors in common router files
"""

import os


def fix_b904_in_file(file_path):
    """Fix B904 errors in a single file"""
    try:
        with open(file_path) as f:
            content = f.read()

        lines = content.split('\n')
        in_except = False

        for i, line in enumerate(lines):
            if line.strip().startswith('except ') and (' as e:' in line or ' as e' in line):
                in_except = True
            elif line.strip().startswith(('except', 'finally', 'try', 'def', 'class', 'if', 'for', 'while', 'return', 'raise')) and not line.strip().startswith('except '):
                in_except = False

            if in_except and 'raise HTTPException(' in line and 'from e' not in line and 'from None' not in line:
                lines[i] = line + ' from e'

        content = '\n'.join(lines)

        with open(file_path, 'w') as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def main():
    # Common router files that likely have B904 errors
    router_files = [
        'backend/app/routers/team_activity.py',
        'backend/app/routers/knowledge_visa.py',
        'backend/app/routers/image_generation.py',
        'backend/app/routers/auth.py',
        'backend/app/routers/preview.py',
        'backend/app/routers/crm_practices.py',
        'backend/app/routers/agents.py',
    ]

    fixed_count = 0
    for file_path in router_files:
        if os.path.exists(file_path):
            if fix_b904_in_file(file_path):
                fixed_count += 1
                print(f"Fixed: {file_path}")
        else:
            print(f"Not found: {file_path}")

    print(f"\nFixed B904 errors in {fixed_count} files")

if __name__ == "__main__":
    main()
