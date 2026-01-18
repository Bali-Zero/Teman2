#!/usr/bin/env python3
"""
Test Coverage Generator
Analyzes codebase and generates missing tests for high coverage
"""

import ast
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag" / "backend"
TESTS_DIR = BACKEND_DIR / "tests"


class TestCoverageAnalyzer:
    """Analyzes test coverage and identifies missing tests"""

    def __init__(self):
        self.source_modules: Dict[str, Path] = {}
        self.test_modules: Dict[str, Path] = {}
        self.missing_tests: List[str] = []

    def find_python_modules(self, directory: Path, prefix: str = "") -> Dict[str, Path]:
        """Find all Python modules in directory"""
        modules = {}
        for file_path in directory.rglob("*.py"):
            if "__pycache__" in str(file_path) or file_path.name == "__init__.py":
                continue

            # Get relative path from backend directory
            rel_path = file_path.relative_to(BACKEND_DIR)
            module_name = str(rel_path).replace("/", ".").replace(".py", "")
            modules[module_name] = file_path

        return modules

    def find_test_modules(self) -> Dict[str, Path]:
        """Find all test modules"""
        tests = {}
        if not TESTS_DIR.exists():
            return tests

        for file_path in TESTS_DIR.rglob("test_*.py"):
            # Extract module name from test file
            rel_path = file_path.relative_to(TESTS_DIR)
            # Remove 'test_' prefix and '.py' suffix
            module_name = (
                str(rel_path).replace("/", ".").replace("test_", "").replace(".py", "")
            )
            tests[module_name] = file_path

        return tests

    def get_module_classes_and_functions(self, file_path: Path) -> Dict[str, List[str]]:
        """Extract classes and functions from Python file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            classes = []
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.FunctionDef) and not isinstance(
                    node.parent, ast.ClassDef
                ):
                    functions.append(node.name)

            return {"classes": classes, "functions": functions}
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return {"classes": [], "functions": []}

    def analyze_coverage(self):
        """Analyze test coverage"""
        print("🔍 Analyzing test coverage...")
        print(f"Backend directory: {BACKEND_DIR}")
        print(f"Tests directory: {TESTS_DIR}")

        # Find all source modules
        self.source_modules = self.find_python_modules(BACKEND_DIR)
        print(f"\n📦 Found {len(self.source_modules)} source modules")

        # Find all test modules
        self.test_modules = self.find_test_modules()
        print(f"🧪 Found {len(self.test_modules)} test modules")

        # Identify missing tests
        print("\n📊 Coverage Analysis:")
        print("=" * 60)

        # Focus on LLM modules
        llm_modules = {
            k: v for k, v in self.source_modules.items() if k.startswith("llm.")
        }
        llm_tests = {k: v for k, v in self.test_modules.items() if "llm" in k}

        print(f"\n🤖 LLM Modules: {len(llm_modules)}")
        print(f"🧪 LLM Tests: {len(llm_tests)}")

        missing = []
        for module_name, file_path in llm_modules.items():
            # Check if test exists
            test_found = False
            for test_name in llm_tests.keys():
                if (
                    module_name.replace("llm.", "") in test_name
                    or test_name in module_name
                ):
                    test_found = True
                    break

            if not test_found:
                missing.append(module_name)
                print(f"  ❌ Missing: {module_name}")

        print(f"\n⚠️  Missing tests: {len(missing)}")
        return missing

    def generate_test_template(self, module_name: str, file_path: Path) -> str:
        """Generate test template for module"""
        module_info = self.get_module_classes_and_functions(file_path)

        test_content = f'''"""
Unit tests for {module_name}
Auto-generated test template for high coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from {module_name} import *


class Test{module_name.split(".")[-1].title().replace("_", "")}:
    """Tests for {module_name}"""

    def test_module_import(self):
        """Test that module can be imported"""
        import {module_name}
        assert {module_name} is not None
'''

        # Add class tests
        for class_name in module_info.get("classes", []):
            test_content += f'''
    def test_{class_name.lower()}_init(self):
        """Test {class_name} initialization"""
        # TODO: Implement initialization test
        pass

    def test_{class_name.lower()}_methods(self):
        """Test {class_name} methods"""
        # TODO: Implement method tests
        pass
'''

        # Add function tests
        for func_name in module_info.get("functions", []):
            if not func_name.startswith("_"):
                test_content += f'''
    def test_{func_name}(self):
        """Test {func_name} function"""
        # TODO: Implement function test
        pass
'''

        return test_content

    def generate_missing_tests(self):
        """Generate test files for missing modules"""
        missing = self.analyze_coverage()

        if not missing:
            print("\n✅ All modules have tests!")
            return

        print(f"\n📝 Generating {len(missing)} test templates...")

        for module_name in missing[:10]:  # Limit to first 10
            file_path = self.source_modules[module_name]
            test_content = self.generate_test_template(module_name, file_path)

            # Determine test file path
            rel_path = file_path.relative_to(BACKEND_DIR)
            test_rel_path = Path("unit") / rel_path.parent / f"test_{rel_path.name}"
            test_file_path = TESTS_DIR / test_rel_path

            # Create directory if needed
            test_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write test file
            if not test_file_path.exists():
                with open(test_file_path, "w", encoding="utf-8") as f:
                    f.write(test_content)
                print(f"  ✅ Created: {test_file_path.relative_to(PROJECT_ROOT)}")
            else:
                print(f"  ⚠️  Exists: {test_file_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    analyzer = TestCoverageAnalyzer()
    analyzer.generate_missing_tests()
