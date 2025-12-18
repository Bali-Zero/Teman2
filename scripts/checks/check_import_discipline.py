#!/usr/bin/env python3
"""
ENTERPRISE: Import Discipline Checker
Verifies that all imports use `backend.*` pattern instead of `app.*` to prevent
import path inconsistencies across deployment environments.

Usage:
    python apps/backend-rag/scripts/check_import_discipline.py

Exit codes:
    0: All imports are compliant
    1: Found non-compliant imports
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Project root (apps/backend-rag)
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# Patterns to check
FORBIDDEN_PATTERNS = [
    (r"^from\s+app\.", "from app.* imports (use backend.app.*)"),
    (r"^import\s+app\.", "import app.* statements (use backend.app.*)"),
]

# Directories to check
CHECK_DIRS = [
    BACKEND_DIR / "services",
    BACKEND_DIR / "routers",
    BACKEND_DIR / "modules",
    BACKEND_DIR / "llm",
    BACKEND_DIR / "middleware",
]

# Files to exclude (e.g., generated files, migrations)
EXCLUDE_PATTERNS = [
    r".*__pycache__.*",
    r".*\.pyc$",
    r".*migrations.*",
]


def should_exclude(file_path: Path) -> bool:
    """Check if file should be excluded from checking"""
    path_str = str(file_path)
    return any(re.match(pattern, path_str) for pattern in EXCLUDE_PATTERNS)


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check a single Python file for forbidden import patterns"""
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                for pattern, description in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line):
                        violations.append((line_num, line.strip(), description))
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
    return violations


def main() -> int:
    """Main entry point"""
    all_violations = []
    checked_files = 0

    for check_dir in CHECK_DIRS:
        if not check_dir.exists():
            continue

        for py_file in check_dir.rglob("*.py"):
            if should_exclude(py_file):
                continue

            checked_files += 1
            violations = check_file(py_file)
            if violations:
                rel_path = py_file.relative_to(PROJECT_ROOT)
                all_violations.append((rel_path, violations))

    # Report results
    if all_violations:
        print("❌ Import discipline violations found:\n", file=sys.stderr)
        for file_path, violations in all_violations:
            print(f"  {file_path}:", file=sys.stderr)
            for line_num, line_content, description in violations:
                print(f"    Line {line_num}: {description}", file=sys.stderr)
                print(f"      {line_content}", file=sys.stderr)
        print(
            f"\nTotal: {sum(len(v) for _, v in all_violations)} violations in "
            f"{len(all_violations)} files",
            file=sys.stderr,
        )
        return 1

    print(f"✅ All imports compliant ({checked_files} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

