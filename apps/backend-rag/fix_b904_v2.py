#!/usr/bin/env python3
"""
Fix B904 errors in zoho_email.py by adding 'from e' to exception raises
"""

import re

def fix_b904_errors(file_path):
    """Add 'from e' to all raise statements in except blocks"""

    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to match raise statements in except blocks and fix them
    # Look for: raise HTTPException(...)\n and replace with: raise HTTPException(...) from e
    pattern = r'(\s+)(raise HTTPException\([^)]+\))\n'

    def replace_func(match):
        indent = match.group(1)
        raise_statement = match.group(2)
        # Add 'from e' after the raise statement
        return f"{indent}{raise_statement} from e\n"

    # Only apply in except blocks
    lines = content.split('\n')
    in_except = False
    for i, line in enumerate(lines):
        if line.strip().startswith('except ') and ' as e:' in line:
            in_except = True
        elif line.strip().startswith(('except', 'finally', 'try', 'def', 'class', 'if', 'for', 'while')):
            in_except = False
        elif in_except and 'raise HTTPException(' in line and 'from e' not in line:
            # Add 'from e' before the newline
            lines[i] = line + ' from e'

    content = '\n'.join(lines)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed B904 errors in {file_path}")

if __name__ == "__main__":
    fix_b904_errors("backend/app/routers/zoho_email.py")
