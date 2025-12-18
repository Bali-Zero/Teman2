#!/usr/bin/env python3
"""
Test Generator - Auto-generates test skeleton for Python modules

Scans source code using AST and creates pytest test files with:
- Proper imports
- Test class per source class
- Test function per source method
- Async support
- Mock setup
- AAA pattern (Arrange, Act, Assert)
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Any


class TestGenerator:
    """Genera automaticamente test skeleton per moduli Python"""

    def __init__(self, source_dir: str, test_dir: str):
        self.source_dir = Path(source_dir)
        self.test_dir = Path(test_dir)

    def find_untested_modules(self) -> List[Path]:
        """Trova moduli Python senza test corrispondente"""
        untested = []

        for py_file in self.source_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue

            # Calculate relative path from source_dir
            rel_path = py_file.relative_to(self.source_dir)
            test_file_name = f"test_{py_file.stem}.py"
            test_file_path = self.test_dir / test_file_name

            if not test_file_path.exists():
                untested.append(py_file)

        return untested

    def analyze_module(self, module_path: Path) -> Dict[str, Any]:
        """Analizza modulo Python ed estrae funzioni/classi"""
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
        except Exception as e:
            print(f"Error parsing {module_path}: {e}")
            return {"classes": [], "functions": [], "async_functions": []}

        classes = []
        functions = []
        async_functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "args": [arg.arg for arg in item.args.args if arg.arg != 'self']
                        })
                classes.append({"name": node.name, "methods": methods})

            elif isinstance(node, ast.FunctionDef) and not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                if not node.name.startswith("_"):
                    functions.append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args]
                    })

            elif isinstance(node, ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    async_functions.append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args]
                    })

        return {"classes": classes, "functions": functions, "async_functions": async_functions}

    def generate_test_code(self, module_path: Path, analysis: Dict[str, Any]) -> str:
        """Genera codice test skeleton con imports, fixtures, AAA pattern"""
        module_name = module_path.stem
        lines = []

        # Header
        lines.append('"""')
        lines.append(f'Tests for {module_name}')
        lines.append('Auto-generated test skeleton - PLEASE COMPLETE IMPLEMENTATION')
        lines.append('"""')
        lines.append('')
        lines.append('import pytest')
        lines.append('from unittest.mock import MagicMock, AsyncMock, patch, Mock')
        lines.append('')

        # Import the module
        rel_path = module_path.relative_to(self.source_dir)
        import_path = str(rel_path.with_suffix('')).replace('/', '.')
        lines.append(f'# TODO: Fix import path if needed')
        lines.append(f'# from backend.{import_path} import *')
        lines.append('')

        # Generate tests for classes
        for cls in analysis["classes"]:
            lines.append(f'class Test{cls["name"]}:')
            lines.append(f'    """Tests for {cls["name"]} class"""')
            lines.append('')

            # Fixture for class instance
            lines.append('    @pytest.fixture')
            lines.append(f'    def {module_name}_instance(self):')
            lines.append(f'        """Fixture for {cls["name"]} instance"""')
            lines.append(f'        # TODO: Create and return {cls["name"]} instance')
            lines.append('        pass')
            lines.append('')

            # Generate test for each method
            for method in cls["methods"]:
                test_name = f'test_{method["name"]}'

                if method["is_async"]:
                    lines.append('    @pytest.mark.asyncio')
                    lines.append(f'    async def {test_name}(self, {module_name}_instance):')
                else:
                    lines.append(f'    def {test_name}(self, {module_name}_instance):')

                lines.append(f'        """Test: {method["name"]}() method"""')
                lines.append(f'        # TODO: Implement test for {method["name"]}')
                lines.append('        # Arrange')
                lines.append('        ')
                lines.append('        # Act')
                lines.append('        ')
                lines.append('        # Assert')
                lines.append('        pass')
                lines.append('')

            lines.append('')

        # Generate tests for standalone functions
        for func in analysis["functions"]:
            lines.append(f'def test_{func["name"]}():')
            lines.append(f'    """Test: {func["name"]}() function"""')
            lines.append(f'    # TODO: Implement test for {func["name"]}')
            lines.append('    # Arrange')
            lines.append('    ')
            lines.append('    # Act')
            lines.append('    ')
            lines.append('    # Assert')
            lines.append('    pass')
            lines.append('')

        # Generate tests for async functions
        for func in analysis["async_functions"]:
            lines.append('@pytest.mark.asyncio')
            lines.append(f'async def test_{func["name"]}():')
            lines.append(f'    """Test: {func["name"]}() async function"""')
            lines.append(f'    # TODO: Implement test for {func["name"]}')
            lines.append('    # Arrange')
            lines.append('    ')
            lines.append('    # Act')
            lines.append('    ')
            lines.append('    # Assert')
            lines.append('    pass')
            lines.append('')

        return '\n'.join(lines)

    def generate_tests(self, dry_run: bool = False) -> None:
        """Genera test per tutti i moduli non testati"""
        untested = self.find_untested_modules()

        if not untested:
            print("✅ All modules have tests!")
            return

        print(f"Found {len(untested)} untested modules:")
        for module in untested:
            print(f"  - {module.relative_to(self.source_dir)}")

        print()

        for module_path in untested:
            analysis = self.analyze_module(module_path)
            test_code = self.generate_test_code(module_path, analysis)

            test_file_name = f"test_{module_path.stem}.py"
            test_file_path = self.test_dir / test_file_name

            if dry_run:
                print(f"[DRY RUN] Would create: {test_file_path}")
            else:
                with open(test_file_path, 'w', encoding='utf-8') as f:
                    f.write(test_code)
                print(f"✅ Created: {test_file_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Auto-generate test skeletons')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created without creating files')
    parser.add_argument('--source-dir', default='apps/backend-rag/backend/services', help='Source directory')
    parser.add_argument('--test-dir', default='apps/backend-rag/tests/unit', help='Test directory')

    args = parser.parse_args()

    generator = TestGenerator(args.source_dir, args.test_dir)
    generator.generate_tests(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
