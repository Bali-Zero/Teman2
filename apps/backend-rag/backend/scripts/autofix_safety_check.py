#!/usr/bin/env python3
"""
Safety Check for Autonomous Test-Fix Loop.

Validates that a git diff does not violate safety rails:
1. No changes to protected files
2. No banned patterns (# type: ignore, # noqa, etc.)
3. No test file modifications
4. Diff size within limits

Usage:
    python3 -m backend.scripts.autofix_safety_check
    python3 -m backend.scripts.autofix_safety_check --staged
    python3 -m backend.scripts.autofix_safety_check --commit HEAD

Returns exit code 0 if safe, 1 if violations found.
"""

import re
import subprocess
import sys

READONLY_FILES = [
    "backend/main.py",
    "backend/main_cloud.py",
    "backend/core/config.py",
    "backend/core/dependencies.py",
    "backend/prompts/",
    "alembic/",
    "fly.toml",
    "fly.staging.toml",
    "requirements.txt",
]

BANNED_PATTERNS = [
    r"#\s*type:\s*ignore",
    r"#\s*noqa",
    r"#\s*pragma:\s*no\s*cover",
    r"#\s*pylint:\s*disable",
    r"pytest\.skip\(",
    r"pytest\.mark\.skip",
    r"@unittest\.skip",
]

TEST_DIRECTORIES = [
    "backend/tests/",
    "tests/",
]

MAX_DIFF_LINES = 50
MAX_FILES_CHANGED = 3


def get_diff(staged: bool = False, commit: str | None = None) -> str:
    """Get the git diff to check."""
    cmd = ["git", "diff"]
    if commit:
        cmd.extend([f"{commit}~1", commit])
    elif staged:
        cmd.append("--staged")
    # Only look at backend files
    cmd.extend(["--", "apps/backend-rag/"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.stdout


def get_changed_files(staged: bool = False, commit: str | None = None) -> list[str]:
    """Get list of changed files."""
    cmd = ["git", "diff", "--name-only"]
    if commit:
        cmd.extend([f"{commit}~1", commit])
    elif staged:
        cmd.append("--staged")
    cmd.extend(["--", "apps/backend-rag/"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check_safety(staged: bool = False, commit: str | None = None) -> list[str]:
    """Run all safety checks. Returns list of violations (empty = safe)."""
    violations: list[str] = []

    changed_files = get_changed_files(staged=staged, commit=commit)
    diff = get_diff(staged=staged, commit=commit)

    if not changed_files:
        return []  # No changes = safe

    # Check 1: No protected files modified
    for filepath in changed_files:
        # Normalize path (remove apps/backend-rag/ prefix)
        rel_path = filepath.replace("apps/backend-rag/", "")
        for protected in READONLY_FILES:
            if rel_path.startswith(protected) or rel_path == protected:
                violations.append(f"PROTECTED_FILE: {filepath}")

    # Check 2: No test files modified
    for filepath in changed_files:
        rel_path = filepath.replace("apps/backend-rag/", "")
        for test_dir in TEST_DIRECTORIES:
            if rel_path.startswith(test_dir):
                violations.append(f"TEST_FILE_MODIFIED: {filepath}")

    # Check 3: No banned patterns in added lines
    added_lines = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    for line in added_lines:
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"BANNED_PATTERN: {pattern} in: {line.strip()[:80]}")

    # Check 4: Diff size limits
    if len(changed_files) > MAX_FILES_CHANGED:
        violations.append(f"TOO_MANY_FILES: {len(changed_files)} changed (max {MAX_FILES_CHANGED})")

    added_count = sum(
        1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    removed_count = sum(
        1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")
    )
    total_changed = added_count + removed_count
    if total_changed > MAX_DIFF_LINES:
        violations.append(f"DIFF_TOO_LARGE: {total_changed} lines changed (max {MAX_DIFF_LINES})")

    return violations


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Safety check for autofix diffs")
    parser.add_argument("--staged", action="store_true", help="Check staged changes")
    parser.add_argument("--commit", default=None, help="Check a specific commit (e.g., HEAD)")
    args = parser.parse_args()

    violations = check_safety(staged=args.staged, commit=args.commit)

    if violations:
        print(f"SAFETY CHECK FAILED: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("SAFETY CHECK PASSED: all clear")
        sys.exit(0)


if __name__ == "__main__":
    main()
