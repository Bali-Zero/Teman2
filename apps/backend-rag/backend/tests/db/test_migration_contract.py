"""
Migration contract tests.

Scans all files in backend/migrations/ and verifies:
1. Every file that is NOT in LEGACY_NO_ROLLBACK_WHITELIST (i.e., post-cutoff)
   supplies a rollback_sql if it uses BaseMigration.
2. Legacy files are not expected to have rollback.
3. File naming follows the convention: migration_NNNx?_description.py
   (no bare migration_NNN.py duplicates — the rename pass should have fixed them).
"""

import ast
import re
from pathlib import Path

import pytest

from backend.db.migration_base import LEGACY_NO_ROLLBACK_WHITELIST

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"

# Pattern: migration_NNN.py (bare number, no suffix) — should not exist post-rename
BARE_NUMBER_PATTERN = re.compile(r"^migration_(\d{3})\.py$")

# Pattern: duplicates — same NNN with different suffixes sharing a number
VALID_FILE_PATTERN = re.compile(r"^migration_\d{3}[a-z]?(?:_[a-zA-Z0-9]+)*\.py$")


def get_all_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("migration_*.py"))


def extract_migration_stem(path: Path) -> str:
    """Return stem without .py, e.g. migration_080a_renewal_dedup"""
    return path.stem


# ---------------------------------------------------------------------------
# 1. No bare migration_NNN.py files (duplicates should have a/b/c suffix)
# ---------------------------------------------------------------------------

def test_no_bare_number_duplicates() -> None:
    """After rename, no file should be migration_NNN.py with a sibling migration_NNN_something.py."""
    files = get_all_migration_files()
    # Build map: number → list of files with that number
    number_map: dict[str, list[Path]] = {}
    for f in files:
        m = re.match(r"^migration_(\d{3})", f.stem)
        if m:
            num = m.group(1)
            number_map.setdefault(num, []).append(f)

    violations = []
    for num, group in number_map.items():
        if len(group) > 1:
            # Check if any is bare (no suffix letter after NNN)
            bare = [f for f in group if re.match(rf"^migration_{num}\.py$", f.name)]
            if bare:
                violations.append(f"Bare file {bare[0].name} has siblings: {[f.name for f in group]}")

    assert not violations, "Found bare-number files with siblings:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# 2. No sibling duplicates: no two files share exact NNN without a/b/c
# ---------------------------------------------------------------------------

def test_no_duplicate_numbers_without_suffix() -> None:
    """No two files should have same NNN with no suffix distinction."""
    files = get_all_migration_files()
    seen: dict[str, list[str]] = {}
    for f in files:
        m = re.match(r"^migration_(\d{3})([a-c]?)_?", f.stem)
        if m:
            num = m.group(1)
            suffix = m.group(2)
            key = f"{num}{suffix}"
            seen.setdefault(key, []).append(f.name)

    dups = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dups, f"Duplicate migration keys found: {dups}"


# ---------------------------------------------------------------------------
# 3. Valid file naming convention
# ---------------------------------------------------------------------------

def test_all_files_follow_naming_convention() -> None:
    """Every migration_*.py must match migration_NNN[a-z?]_description.py or migration_NNN.py (legacy bare allowed if solo)."""
    files = get_all_migration_files()
    violations = []
    for f in files:
        if not VALID_FILE_PATTERN.match(f.name):
            violations.append(f.name)
    assert not violations, f"Files not matching naming convention: {violations}"


# ---------------------------------------------------------------------------
# 4. Legacy whitelist covers all pre-cutoff files
# ---------------------------------------------------------------------------

def test_all_current_files_in_whitelist_or_post_cutoff() -> None:
    """Every file in migrations/ should either be in the legacy whitelist OR
    be a genuinely new file (number > 111). This test catches new files that
    forgot to supply rollback_sql via the BaseMigration constructor check."""
    files = get_all_migration_files()
    unaccounted = []
    for f in files:
        stem = f.stem
        m = re.match(r"^migration_(\d{3})", stem)
        if not m:
            continue
        number = int(m.group(1))
        if number <= 111 and stem not in LEGACY_NO_ROLLBACK_WHITELIST:
            unaccounted.append(stem)
    assert not unaccounted, (
        "These pre-cutoff migration stems are NOT in LEGACY_NO_ROLLBACK_WHITELIST. "
        "Add them to the whitelist in migration_base.py:\n" + "\n".join(unaccounted)
    )


# ---------------------------------------------------------------------------
# 5. Post-cutoff files (> 111) use BaseMigration with rollback_sql
#    We check via AST — no DB connection needed.
# ---------------------------------------------------------------------------

def _has_rollback_sql_kwarg(source: str) -> bool:
    """Return True if source contains a BaseMigration() call with rollback_sql keyword."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in ("BaseMigration", "super"):
                for kw in node.keywords:
                    if kw.arg == "rollback_sql":
                        return True
    return False


def get_post_cutoff_files() -> list[Path]:
    files = get_all_migration_files()
    result = []
    for f in files:
        m = re.match(r"^migration_(\d{3})", f.stem)
        if m and int(m.group(1)) > 111:
            result.append(f)
    return result


@pytest.mark.parametrize("migration_file", get_post_cutoff_files(), ids=lambda p: p.stem)
def test_post_cutoff_migration_has_rollback_sql(migration_file: Path) -> None:
    """Every post-cutoff migration that uses BaseMigration must declare rollback_sql."""
    source = migration_file.read_text(encoding="utf-8")

    # If it doesn't use BaseMigration at all, it's a standalone script — skip.
    if "BaseMigration" not in source:
        pytest.skip(f"{migration_file.name} does not use BaseMigration, skipping rollback check")

    assert _has_rollback_sql_kwarg(source), (
        f"{migration_file.name} uses BaseMigration but does not pass rollback_sql. "
        "All post-2026-04-18 migrations require explicit rollback_sql."
    )
