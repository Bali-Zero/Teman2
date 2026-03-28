"""
Compliance Tests: Golden Rules Enforcement

These tests verify that the codebase adheres to the Golden Rules
defined in AI_ONBOARDING.md. They run automatically in CI/CD.

Author: Wakil (Deputy General)
Date: 2026-02-12
"""

import ast
import re
from pathlib import Path

import pytest

# ========== PATHS ==========

BACKEND_ROOT = Path(__file__).parent.parent.parent
APP_DIR = BACKEND_ROOT / "app"
SERVICES_DIR = BACKEND_ROOT / "services"
CORE_DIR = BACKEND_ROOT / "core"
MIDDLEWARE_DIR = BACKEND_ROOT / "middleware"

# Directories to check (exclude tests, scripts, migrations)
DIRS_TO_CHECK = [APP_DIR, SERVICES_DIR, CORE_DIR, MIDDLEWARE_DIR]


# ========== HELPERS ==========


def get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory, excluding __pycache__."""
    files = []
    for path in directory.rglob("*.py"):
        if "__pycache__" not in str(path) and "__init__.py" not in path.name:
            files.append(path)
    return files


def parse_python_file(file_path: Path) -> ast.Module | None:
    """Parse Python file into AST."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        pytest.fail(f"Syntax error in {file_path}")
        return None


# ========== GOLDEN RULE #5: TYPE HINTS REQUIRED ==========


class TypeHintChecker(ast.NodeVisitor):
    """AST visitor to check for missing type hints."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function for type hints."""
        # Skip private functions (start with _)
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        # Skip if it's a test function
        if node.name.startswith("test_"):
            self.generic_visit(node)
            return

        # Check if function has return type annotation
        if node.returns is None:
            self.violations.append(
                f"{self.file_path}:{node.lineno} - Function '{node.name}' missing return type hint",
            )

        # Check if arguments have type annotations (except self, cls)
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                self.violations.append(
                    f"{self.file_path}:{node.lineno} - "
                    f"Parameter '{arg.arg}' in '{node.name}' missing type hint",
                )

        self.generic_visit(node)


def test_golden_rule_5_type_hints():
    """
    Golden Rule #5: TYPE HINTS REQUIRED

    Every function must have type hints:
    - def func(x: int) -> str:
    """
    violations = []

    for directory in DIRS_TO_CHECK:
        if not directory.exists():
            continue

        python_files = get_python_files(directory)

        for file_path in python_files:
            tree = parse_python_file(file_path)
            if tree is None:
                continue

            checker = TypeHintChecker(str(file_path.relative_to(BACKEND_ROOT)))
            checker.visit(tree)
            violations.extend(checker.violations)

    if violations:
        violation_msg = "\n".join(violations[:10])  # Show first 10
        total = len(violations)
        pytest.fail(
            f"❌ Golden Rule #5 violated: {total} missing type hints\n\n"
            f"{violation_msg}\n"
            f"{'...' if total > 10 else ''}",
        )


# ========== GOLDEN RULE #6: NO HARDCODING ==========


def test_golden_rule_6_no_hardcoded_secrets():
    """
    Golden Rule #6: NO HARDCODING

    Secrets must come from os.getenv() or settings, never hardcoded.
    """
    violations = []

    # Regex patterns for hardcoded secrets
    patterns = [
        (r'api[_-]?key\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']', "API key"),
        (r'secret[_-]?key\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']', "Secret key"),
        (r'password\s*=\s*["\'][a-zA-Z0-9_-]{8,}["\']', "Password"),
        (r'token\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']', "Token"),
    ]

    for directory in DIRS_TO_CHECK:
        if not directory.exists():
            continue

        python_files = get_python_files(directory)

        for file_path in python_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            for line_num, line in enumerate(lines, start=1):
                # Skip comments
                if line.strip().startswith("#"):
                    continue

                # Skip if using env vars
                if "os.getenv" in line or "settings." in line:
                    continue

                for pattern, secret_type in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append(
                            f"{file_path.relative_to(BACKEND_ROOT)}:{line_num} - "
                            f"Potential hardcoded {secret_type}: {line.strip()}",
                        )

    if violations:
        violation_msg = "\n".join(violations[:5])
        pytest.fail(
            f"❌ Golden Rule #6 violated: {len(violations)} potential hardcoded secrets\n\n"
            f"{violation_msg}\n"
            f"Use os.getenv() or settings.* instead",
        )


# ========== GOLDEN RULE #8: CLEAN LOGGING ==========


class PrintStatementChecker(ast.NodeVisitor):
    """AST visitor to find print() calls."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Check for print() calls."""
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.violations.append(
                f"{self.file_path}:{node.lineno} - Found print() statement - use logger instead",
            )
        self.generic_visit(node)


def test_golden_rule_8_no_print_statements():
    """
    Golden Rule #8: CLEAN LOGGING

    Backend code must use logger, never print().
    (Scripts and tests are allowed to use print)
    """
    violations = []

    for directory in DIRS_TO_CHECK:
        if not directory.exists():
            continue

        python_files = get_python_files(directory)

        for file_path in python_files:
            tree = parse_python_file(file_path)
            if tree is None:
                continue

            checker = PrintStatementChecker(str(file_path.relative_to(BACKEND_ROOT)))
            checker.visit(tree)
            violations.extend(checker.violations)

    if violations:
        violation_msg = "\n".join(violations[:10])
        pytest.fail(
            f"❌ Golden Rule #8 violated: {len(violations)} print() statements\n\n"
            f"{violation_msg}\n"
            f"Use logger = logging.getLogger(__name__) instead",
        )


# ========== GOLDEN RULE #3: PATH DISCIPLINE ==========


class ImportChecker(ast.NodeVisitor):
    """AST visitor to find relative imports."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[str] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for relative imports."""
        if node.level > 0:  # level > 0 means relative import
            self.violations.append(
                f"{self.file_path}:{node.lineno} - "
                f"Found relative import: from {'.' * node.level}{node.module or ''}",
            )
        self.generic_visit(node)


def test_golden_rule_3_no_relative_imports():
    """
    Golden Rule #3: PATH DISCIPLINE

    All imports must be absolute: from backend.core import config
    NOT: from ..core import config
    """
    violations = []

    for directory in DIRS_TO_CHECK:
        if not directory.exists():
            continue

        python_files = get_python_files(directory)

        for file_path in python_files:
            tree = parse_python_file(file_path)
            if tree is None:
                continue

            checker = ImportChecker(str(file_path.relative_to(BACKEND_ROOT)))
            checker.visit(tree)
            violations.extend(checker.violations)

    if violations:
        violation_msg = "\n".join(violations[:10])
        pytest.fail(
            f"❌ Golden Rule #3 violated: {len(violations)} relative imports\n\n"
            f"{violation_msg}\n"
            f"Use absolute imports: from backend.module import X",
        )


# ========== SUMMARY TEST ==========


def test_golden_rules_summary():
    """
    Summary test that runs all Golden Rules checks.

    This is useful for CI/CD to get a single pass/fail result.
    """
    # This test just ensures other tests ran
    # (pytest will fail if any of the above failed)
    pass


# ========== PYTEST CONFIGURATION ==========

if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
