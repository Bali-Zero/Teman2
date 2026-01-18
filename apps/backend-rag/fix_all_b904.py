#!/usr/bin/env python3
"""
Fix all B904 errors in the codebase
"""

import os
import re
import subprocess

def fix_b904_in_file(file_path):
    """Fix B904 errors in a single file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        in_except = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('except ') and (' as e:' in line or ' as e' in line):
                in_except = True
            elif line.strip().startswith(('except', 'finally', 'try', 'def', 'class', 'if', 'for', 'while', 'return', 'raise')):
                if not line.strip().startswith('except '):
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
    # Find all Python files with B904 errors
    result = subprocess.run(['ruff', '--select=B904', '--output-format=json'], 
                          capture_output=True, text=True)
    
    if result.returncode != 0 and result.returncode != 1:
        print("Error running ruff")
        return
    
    files_with_b904 = set()
    for line in result.stdout.strip().split('\n'):
        if line:
            try:
                import json
                data = json.loads(line)
                if 'filename' in data:
                    files_with_b904.add(data['filename'])
            except:
                pass
    
    print(f"Found {len(files_with_b904)} files with B904 errors")
    
    fixed_count = 0
    for file_path in files_with_b904:
        if fix_b904_in_file(file_path):
            fixed_count += 1
            print(f"Fixed: {file_path}")
    
    print(f"\nFixed B904 errors in {fixed_count} files")

if __name__ == "__main__":
    main()
