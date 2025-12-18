#!/usr/bin/env python3
"""
Analyze integration test coverage by examining which modules are imported/tested.
This provides an approximation of integration test coverage.
"""
import ast
import subprocess
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict

def find_integration_test_files() -> List[Path]:
    """Find all integration test files"""
    test_dir = Path(__file__).parent.parent / 'tests' / 'integration'
    test_files = []
    
    # Find all test files in integration directory
    for test_file in test_dir.rglob('test_*.py'):
        test_files.append(test_file)
    
    # Also check for files with _test.py suffix
    for test_file in test_dir.rglob('*_test.py'):
        if test_file not in test_files:
            test_files.append(test_file)
    
    return sorted(test_files)

def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all imports from a Python file"""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return imports

def map_imports_to_backend_files(imports: Set[str], backend_dir: Path) -> Set[Path]:
    """Map import names to actual backend file paths"""
    backend_files = set()
    
    for imp in imports:
        # Skip standard library and third-party imports
        if imp in ['sys', 'os', 'json', 'typing', 'pathlib', 'datetime', 'asyncio', 
                   'pytest', 'unittest', 'mock', 'faker', 'httpx', 'fastapi', 
                   'pydantic', 'sqlalchemy', 'asyncpg', 'redis', 'qdrant']:
            continue
        
        # Try to find the file
        # backend.app.* -> backend/app/
        # backend.services.* -> backend/services/
        # backend.core.* -> backend/core/
        # etc.
        
        if imp == 'app' or imp.startswith('app.'):
            # Check app directory
            module_path = imp.replace('app.', '').replace('.', '/')
            if module_path:
                potential_file = backend_dir / 'app' / f"{module_path}.py"
                if potential_file.exists():
                    backend_files.add(potential_file)
            
            # Also check __init__.py
            init_file = backend_dir / 'app' / '__init__.py'
            if init_file.exists():
                backend_files.add(init_file)
        
        # Check for direct backend imports
        if imp.startswith('backend.'):
            parts = imp.replace('backend.', '').split('.')
            if parts:
                potential_file = backend_dir / '/'.join(parts[:-1]) / f"{parts[-1]}.py"
                if potential_file.exists():
                    backend_files.add(potential_file)
        
        # Check common patterns
        for pattern in ['services', 'core', 'llm', 'db', 'agents', 'middleware', 'utils']:
            if imp.startswith(pattern) or pattern in imp:
                module_path = imp.replace(f'{pattern}.', '').replace('.', '/')
                potential_file = backend_dir / pattern / f"{module_path}.py"
                if potential_file.exists():
                    backend_files.add(potential_file)
    
    return backend_files

def get_all_backend_python_files(backend_dir: Path) -> List[Path]:
    """Get all Python files in backend directory"""
    python_files = []
    
    # Exclude test files and migrations
    exclude_dirs = {'tests', 'migrations', '__pycache__', '.pytest_cache', '.venv'}
    
    for py_file in backend_dir.rglob('*.py'):
        # Skip if in excluded directory
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        python_files.append(py_file)
    
    return sorted(python_files)

def analyze_integration_coverage():
    """Main analysis function"""
    backend_dir = Path(__file__).parent.parent / 'backend'
    test_files = find_integration_test_files()
    
    print(f"Found {len(test_files)} integration test files")
    print("Analyzing imports...\n")
    
    # Collect all imports from integration tests
    all_imports = set()
    file_imports = defaultdict(set)
    
    for test_file in test_files:
        imports = extract_imports_from_file(test_file)
        all_imports.update(imports)
        file_imports[test_file] = imports
    
    # Get all backend Python files
    all_backend_files = get_all_backend_python_files(backend_dir)
    
    print(f"Total backend Python files: {len(all_backend_files)}")
    
    # Try to match imports to files (simplified approach)
    # Instead of complex matching, we'll use a simpler heuristic:
    # Check which backend files are likely tested based on common patterns
    
    # Files that are likely tested (have corresponding test files or are imported)
    likely_tested = set()
    
    # Check for direct file references in test files
    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for imports that suggest backend files
            for backend_file in all_backend_files:
                # Get relative path from backend/
                rel_path = backend_file.relative_to(backend_dir)
                module_path = str(rel_path).replace('/', '.').replace('.py', '')
                
                # Check if module is imported
                if module_path in content or f"from {module_path}" in content or f"import {module_path}" in content:
                    likely_tested.add(backend_file)
        except Exception as e:
            print(f"Warning: Could not analyze {test_file}: {e}")
    
    # Calculate coverage approximation
    tested_files = likely_tested
    untested_files = set(all_backend_files) - tested_files
    
    print(f"\n{'=' * 80}")
    print("INTEGRATION TEST COVERAGE ANALYSIS (Approximation)")
    print(f"{'=' * 80}")
    print(f"\nFiles likely tested by integration tests: {len(tested_files)}")
    print(f"Files likely NOT tested by integration tests: {len(untested_files)}")
    print(f"Estimated coverage: {len(tested_files) / len(all_backend_files) * 100:.1f}%")
    
    # Group untested files by directory
    by_dir = defaultdict(list)
    for file_path in sorted(untested_files):
        rel_path = file_path.relative_to(backend_dir)
        dir_path = str(rel_path.parent)
        by_dir[dir_path].append((str(rel_path), file_path))
    
    print(f"\n{'=' * 80}")
    print("FILES LIKELY NOT COVERED BY INTEGRATION TESTS")
    print(f"{'=' * 80}\n")
    
    for dir_path in sorted(by_dir.keys()):
        print(f"\n📁 {dir_path}/")
        print(f"{'─' * 80}")
        for rel_path, _ in sorted(by_dir[dir_path]):
            print(f"  {rel_path}")
    
    return 0

if __name__ == '__main__':
    exit(analyze_integration_coverage())

