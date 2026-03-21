#!/usr/bin/env python3
"""
Compliance Violations Auto-Fixer

Automatically fixes Golden Rules violations in the codebase:
1. Adds type hints to functions (Golden Rule #5)
2. Converts relative imports to absolute (Golden Rule #3)

Author: Wakil (Deputy General)
Date: 2026-02-12

Usage:
    python scripts/fix_compliance_violations.py --dry-run  # Preview changes
    python scripts/fix_compliance_violations.py           # Apply changes
"""

import argparse
import ast
import re
from pathlib import Path
from typing import Any

# ========== CONFIGURATION ==========

BACKEND_ROOT = Path(__file__).parent.parent / "backend"
DIRS_TO_FIX = ["app", "services", "core", "middleware"]

# Type hint defaults (conservative approach)
DEFAULT_RETURN_TYPE = "Any"
DEFAULT_PARAM_TYPE = "Any"


# ========== HELPERS ==========


def get_python_files(directory: Path) -> list[Path]:
    """Get all Python files, excluding __pycache__ and __init__.py."""
    files = []
    for path in directory.rglob("*.py"):
        if "__pycache__" not in str(path) and "__init__.py" not in path.name:
            files.append(path)
    return files


# ========== FIX #1: ADD TYPE HINTS ==========


def add_type_hints_to_file(file_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """
    Add type hints to functions missing them.

    Conservative approach:
    - Add `: Any` to parameters without annotations
    - Add `-> Any` to functions without return annotations
    - Skip private functions (_prefixed)
    - Skip test functions (test_prefixed)
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    modified = False
    changes = []

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return {"error": "Syntax error", "changes": 0}

    # Collect function definitions
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Skip private and test functions
        if node.name.startswith("_") or node.name.startswith("test_"):
            continue

        # Check if return type is missing
        if node.returns is None:
            # Find the function definition line
            func_line_idx = node.lineno - 1
            lines[func_line_idx]

            # Find the closing parenthesis of parameters
            # Handle multi-line function definitions
            paren_count = 0
            end_line_idx = func_line_idx
            found_end = False

            for i in range(func_line_idx, min(func_line_idx + 10, len(lines))):
                for char in lines[i]:
                    if char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                        if paren_count == 0:
                            end_line_idx = i
                            found_end = True
                            break
                if found_end:
                    break

            if found_end:
                end_line = lines[end_line_idx]

                # Add return type annotation
                if "->" not in end_line:
                    # Find position of closing ) and :
                    close_paren_pos = end_line.rfind(")")
                    colon_pos = end_line.find(":", close_paren_pos)

                    if close_paren_pos != -1 and colon_pos != -1:
                        new_line = (
                            end_line[: close_paren_pos + 1]
                            + f" -> {DEFAULT_RETURN_TYPE}"
                            + end_line[colon_pos:]
                        )
                        lines[end_line_idx] = new_line
                        modified = True
                        changes.append(f"Line {end_line_idx + 1}: Added return type to {node.name}")

        # Check if parameters are missing type hints
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue

            if arg.annotation is None:
                # Find the parameter in the source
                func_line_idx = node.lineno - 1

                # Multi-line search for parameter
                for i in range(func_line_idx, min(func_line_idx + 10, len(lines))):
                    line = lines[i]

                    # Match parameter name (not in string, not as substring)
                    pattern = rf"\b{re.escape(arg.arg)}\b(?!\s*:)"
                    if re.search(pattern, line):
                        # Add type hint
                        new_line = re.sub(
                            rf"\b{re.escape(arg.arg)}\b",
                            f"{arg.arg}: {DEFAULT_PARAM_TYPE}",
                            line,
                            count=1,
                        )
                        lines[i] = new_line
                        modified = True
                        changes.append(f"Line {i + 1}: Added type hint to parameter '{arg.arg}'")
                        break

    if modified and not dry_run:
        new_content = "\n".join(lines)

        # Add typing import if not present
        if "from typing import" not in new_content and DEFAULT_RETURN_TYPE == "Any":
            # Find first import or after docstring
            insert_line = 0
            in_docstring = False

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Handle docstrings
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if in_docstring:
                        in_docstring = False
                        insert_line = i + 1
                    else:
                        in_docstring = True
                elif not in_docstring and (
                    stripped.startswith("import ") or stripped.startswith("from ")
                ):
                    insert_line = i
                    break

            lines.insert(insert_line, "from typing import Any\n")

        new_content = "\n".join(lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return {"modified": modified, "changes": len(changes), "details": changes}


# ========== FIX #2: CONVERT RELATIVE IMPORTS TO ABSOLUTE ==========


def fix_relative_imports_in_file(file_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """
    Convert relative imports to absolute imports.

    Example:
        from .cors_config import X  →  from backend.app.setup.cors_config import X
        from ..memory import Y      →  from backend.services.memory import Y
    """
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    modified = False
    changes = []

    # Determine the module path for this file
    relative_to_backend = file_path.relative_to(BACKEND_ROOT)
    module_parts = list(relative_to_backend.parent.parts)

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Match relative imports: from .module or from ..module
        match = re.match(r"^from\s+(\.+)([.\w]*)\s+import\s+(.+)$", stripped)
        if not match:
            continue

        dots, module_suffix, imports = match.groups()
        level = len(dots)  # Number of dots = levels up

        # Calculate absolute module path
        if level > len(module_parts):
            # Can't go up more levels than we have
            continue

        # Go up 'level - 1' directories (one dot is current dir)
        base_parts = module_parts[: -(level - 1)] if level > 1 else module_parts

        # Build absolute import path
        absolute_parts = ["backend"] + base_parts
        if module_suffix:
            # Remove leading dot if present
            suffix_parts = module_suffix.lstrip(".").split(".")
            absolute_parts.extend(suffix_parts)

        absolute_module = ".".join(absolute_parts)

        # Reconstruct import statement
        new_line = line.replace(f"from {dots}{module_suffix}", f"from {absolute_module}")

        lines[i] = new_line
        modified = True
        changes.append(f"Line {i + 1}: {dots}{module_suffix} → {absolute_module}")

    if modified and not dry_run:
        new_content = "\n".join(lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return {"modified": modified, "changes": len(changes), "details": changes}


# ========== MAIN ==========


def main():
    parser = argparse.ArgumentParser(description="Fix Golden Rules compliance violations")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--type-hints-only", action="store_true", help="Only fix type hints")
    parser.add_argument("--imports-only", action="store_true", help="Only fix relative imports")
    args = parser.parse_args()

    print("🔧 Compliance Violations Auto-Fixer")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()

    type_hints_stats = {"files": 0, "changes": 0}
    imports_stats = {"files": 0, "changes": 0}

    for dir_name in DIRS_TO_FIX:
        directory = BACKEND_ROOT / dir_name
        if not directory.exists():
            continue

        print(f"📁 Processing {dir_name}/")
        python_files = get_python_files(directory)

        for file_path in python_files:
            relative_path = file_path.relative_to(BACKEND_ROOT)

            # Fix type hints
            if not args.imports_only:
                result = add_type_hints_to_file(file_path, dry_run=args.dry_run)
                if result.get("modified"):
                    type_hints_stats["files"] += 1
                    type_hints_stats["changes"] += result["changes"]
                    print(f"  ✅ {relative_path}: Added {result['changes']} type hints")

            # Fix relative imports
            if not args.type_hints_only:
                result = fix_relative_imports_in_file(file_path, dry_run=args.dry_run)
                if result.get("modified"):
                    imports_stats["files"] += 1
                    imports_stats["changes"] += result["changes"]
                    print(f"  ✅ {relative_path}: Fixed {result['changes']} imports")

    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    if not args.imports_only:
        print(
            f"Type Hints: {type_hints_stats['changes']} fixes in {type_hints_stats['files']} files"
        )

    if not args.type_hints_only:
        print(
            f"Relative Imports: {imports_stats['changes']} fixes in {imports_stats['files']} files"
        )

    print()

    if args.dry_run:
        print("⚠️  DRY RUN - No changes applied. Run without --dry-run to apply.")
    else:
        print("✅ Changes applied successfully!")
        print()
        print("Next steps:")
        print("1. Run tests: pytest backend/tests/compliance/test_golden_rules.py -v")
        print("2. Review changes: git diff")
        print("3. Commit: git add -A && git commit -m 'fix(compliance): Golden Rules violations'")


if __name__ == "__main__":
    main()
