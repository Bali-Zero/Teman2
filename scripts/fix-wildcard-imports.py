#!/usr/bin/env python3
"""
Script to replace wildcard imports with explicit imports
Analyzes __all__ or module contents to determine what to import
"""

import re
import ast
import sys
from pathlib import Path
from typing import List, Set

def get_module_exports(file_path: Path) -> Set[str]:
    """Parse Python file to find exported symbols"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        exports = set()
        
        # Check for __all__
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    exports.add(elt.value)
        
        # If no __all__, collect top-level definitions
        if not exports:
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    exports.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    exports.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            exports.add(target.id)
        
        return exports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return set()

def replace_wildcard_import(file_path: Path) -> bool:
    """Replace wildcard import with explicit imports"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Find wildcard imports
        wildcard_pattern = r'from\s+([\w.]+)\s+import\s+\*'
        matches = list(re.finditer(wildcard_pattern, content))
        
        if not matches:
            return False
        
        for match in reversed(matches):  # Process from end to avoid offset issues
            import_module = match.group(1)
            import_line = match.group(0)
            
            # Try to find the module file
            module_parts = import_module.split('.')
            base_path = file_path.parent
            
            # Navigate to module
            module_file = None
            for part in module_parts:
                potential_file = base_path / f"{part}.py"
                potential_init = base_path / part / "__init__.py"
                
                if potential_file.exists():
                    module_file = potential_file
                    break
                elif potential_init.exists():
                    module_file = potential_init
                    base_path = base_path / part
                    break
                else:
                    base_path = base_path / part
                    if not base_path.exists():
                        break
            
            if module_file and module_file.exists():
                exports = get_module_exports(module_file)
                if exports:
                    # Create explicit import
                    exports_sorted = sorted(exports)
                    explicit_import = f"from {import_module} import (\n"
                    for exp in exports_sorted:
                        explicit_import += f"    {exp},\n"
                    explicit_import = explicit_import.rstrip(',\n') + "\n)"
                    
                    # Replace wildcard import
                    content = content[:match.start()] + explicit_import + content[match.end():]
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False

def main():
    """Main function"""
    base_path = Path(__file__).parent.parent
    
    # Files with wildcard imports (from grep)
    target_files = [
        base_path / "apps/backend-rag/backend/tests/unit/llm/test_base.py",
        base_path / "apps/backend-rag/backend/tests/unit/llm/test_provider_registry.py",
        base_path / "apps/backend-rag/backend/tests/unit/llm/providers/test_vertex.py",
        base_path / "apps/backend-rag/backend/tests/unit/llm/providers/test_deepseek.py",
        base_path / "apps/backend-rag/backend/tests/unit/llm/adapters/test_gemini.py",
        base_path / "apps/backend-rag/backend/tests/unit/llm/adapters/test_base.py",
    ]
    
    modified = 0
    for file_path in target_files:
        if file_path.exists():
            if replace_wildcard_import(file_path):
                modified += 1
                print(f"✓ {file_path.relative_to(base_path)}")
    
    print(f"\nModified {modified} files")

if __name__ == '__main__':
    main()
