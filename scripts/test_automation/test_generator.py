#!/usr/bin/env python3
"""
Test Generator - Automatic Test Creation
Genera automaticamente test skeleton per moduli Python non testati
"""

import ast
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

            # Determina nome test file
            relative_path = py_file.relative_to(self.source_dir)
            test_file_name = f"test_{py_file.stem}.py"
            test_file_path = self.test_dir / test_file_name

            if not test_file_path.exists():
                untested.append(py_file)

        return untested

    def analyze_module(self, module_path: Path) -> Dict[str, Any]:
        """Analizza modulo Python ed estrae funzioni/classi"""
        with open(module_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                return {"classes": [], "functions": [], "async_functions": []}

        classes = []
        functions = []
        async_functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(
                            {
                                "name": item.name,
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "args": [arg.arg for arg in item.args.args],
                            }
                        )
                classes.append({"name": node.name, "methods": methods})
            elif isinstance(node, ast.AsyncFunctionDef) and not isinstance(
                node, ast.ClassDef
            ):
                async_functions.append(
                    {"name": node.name, "args": [arg.arg for arg in node.args.args]}
                )
            elif isinstance(node, ast.FunctionDef) and not any(
                isinstance(p, ast.ClassDef) for p in ast.walk(tree)
            ):
                functions.append(
                    {"name": node.name, "args": [arg.arg for arg in node.args.args]}
                )

        return {
            "classes": classes,
            "functions": functions,
            "async_functions": async_functions,
        }

    def generate_test_code(self, module_path: Path, analysis: Dict[str, Any]) -> str:
        """Genera codice test skeleton"""
        module_name = module_path.stem
        import_path = (
            str(module_path.relative_to(self.source_dir.parent))
            .replace("/", ".")
            .replace(".py", "")
        )

        lines = [
            '"""',
            f"Tests for {module_name}",
            "Auto-generated test skeleton - PLEASE COMPLETE IMPLEMENTATION",
            '"""',
            "",
            "import pytest",
            "from unittest.mock import MagicMock, AsyncMock, patch",
            "",
            "# Import module under test",
            f"# from {import_path} import ...",
            "",
        ]

        # Generate test classes for each class
        for cls in analysis["classes"]:
            lines.append(f'class Test{cls["name"]}:')
            lines.append(f'    """Tests for {cls["name"]} class"""')
            lines.append("")

            # Setup fixture
            lines.append("    @pytest.fixture")
            lines.append(f'    def {cls["name"].lower()}_instance(self):')
            lines.append(f'        """Fixture for {cls["name"]} instance"""')
            lines.append(f'        # TODO: Create and return {cls["name"]} instance')
            lines.append("        pass")
            lines.append("")

            # Generate test for each method
            for method in cls["methods"]:
                test_name = f'test_{method["name"]}'
                lines.append("    @pytest.mark.asyncio" if method["is_async"] else "")
                lines.append(
                    f'    {"async " if method["is_async"] else ""}def {test_name}(self, {cls["name"].lower()}_instance):'
                )
                lines.append(f'        """Test: {method["name"]}() method"""')
                lines.append(f'        # TODO: Implement test for {method["name"]}')
                lines.append("        # Arrange")
                lines.append("        # Act")
                lines.append("        # Assert")
                lines.append("        pass")
                lines.append("")

        # Generate tests for standalone async functions
        if analysis["async_functions"]:
            lines.append(
                "# ============================================================================"
            )
            lines.append("# ASYNC FUNCTION TESTS")
            lines.append(
                "# ============================================================================"
            )
            lines.append("")

            for func in analysis["async_functions"]:
                lines.append("@pytest.mark.asyncio")
                lines.append(f'async def test_{func["name"]}():')
                lines.append(f'    """Test: {func["name"]}() function"""')
                lines.append(f'    # TODO: Implement test for {func["name"]}')
                lines.append("    # Arrange")
                lines.append("    # Act")
                lines.append("    # Assert")
                lines.append("    pass")
                lines.append("")

        # Generate tests for standalone functions
        if analysis["functions"]:
            lines.append(
                "# ============================================================================"
            )
            lines.append("# FUNCTION TESTS")
            lines.append(
                "# ============================================================================"
            )
            lines.append("")

            for func in analysis["functions"]:
                lines.append(f'def test_{func["name"]}():')
                lines.append(f'    """Test: {func["name"]}() function"""')
                lines.append(f'    # TODO: Implement test for {func["name"]}')
                lines.append("    # Arrange")
                lines.append("    # Act")
                lines.append("    # Assert")
                lines.append("    pass")
                lines.append("")

        return "\n".join(lines)

    def generate_tests_for_untested(self, dry_run: bool = False) -> List[str]:
        """Genera test per tutti i moduli non testati"""
        untested = self.find_untested_modules()
        generated_files = []

        print(f"📊 Found {len(untested)} untested modules")

        for module_path in untested:
            print(f"  Analyzing: {module_path.name}")
            analysis = self.analyze_module(module_path)

            if not any(
                [
                    analysis["classes"],
                    analysis["functions"],
                    analysis["async_functions"],
                ]
            ):
                print("    ⏭️  Skipping (no testable code)")
                continue

            test_code = self.generate_test_code(module_path, analysis)
            test_file_name = f"test_{module_path.stem}.py"
            test_file_path = self.test_dir / test_file_name

            if dry_run:
                print(f"    📝 Would create: {test_file_path}")
            else:
                with open(test_file_path, "w", encoding="utf-8") as f:
                    f.write(test_code)
                print(f"    ✅ Generated: {test_file_path}")
                generated_files.append(str(test_file_path))

        return generated_files


def main():
    import sys

    # Configuration
    source_dir = "apps/backend-rag/backend/services"
    test_dir = "apps/backend-rag/tests/unit"

    dry_run = "--dry-run" in sys.argv

    generator = TestGenerator(source_dir, test_dir)

    print("🤖 Test Generator - Automatic Test Creation")
    print("=" * 60)
    print(f"Source: {source_dir}")
    print(f"Tests: {test_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    print("=" * 60)
    print()

    generated = generator.generate_tests_for_untested(dry_run=dry_run)

    print()
    print("=" * 60)
    print(f"✅ Complete! Generated {len(generated)} test files")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No files created")
        print("Run without --dry-run to create files")


if __name__ == "__main__":
    main()
