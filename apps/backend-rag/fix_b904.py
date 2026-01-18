#!/usr/bin/env python3
"""
Fix B904 errors in zoho_email.py by adding 'from e' to exception raises
"""

import re


def fix_b904_errors(file_path):
    """Add 'from e' to all raise statements in except blocks"""

    with open(file_path) as f:
        content = f.read()

    # Pattern to match raise statements in except blocks
    pattern = r'(except\s+\w+\s+as\s+e:\s*\n.*?)(raise\s+HTTPException\([^)]+\))'

    def replace_func(match):
        except_block = match.group(1)
        raise_statement = match.group(2)
        # Add 'from e' to the raise statement
        if 'from e' not in raise_statement:
            raise_statement = raise_statement.replace(')', ') from e')
        return except_block + raise_statement

    content = re.sub(pattern, replace_func, content, flags=re.MULTILINE | re.DOTALL)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed B904 errors in {file_path}")

if __name__ == "__main__":
    fix_b904_errors("backend/app/routers/zoho_email.py")
