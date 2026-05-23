#!/usr/bin/env python3
"""W41 (2026-05-23) — migration-number uniqueness lint.

Closes the direct-push bypass discovered in W40 (cicatrix 2026-05-23):
`.github/workflows/lint-migration-numbers.yml` exists since P0-7
(2026-04-29 cicatrix duplicate 129/130) but only fires on `pull_request`.
L2 autonomous-ops policy allows direct-push to main, which silently
skips the lint. W37 1234c9114 went direct-to-main and dropped
194_organism_incident_ledger.sql while PR #828 was simultaneously
merging 194_reconcile_107_bridge_outbox_tracking.sql. Migration runner
`_assert_unique_migration_numbers` would have hard-failed the next
deploy, blocking ALL pending migrations.

This script is the local-checkout twin of the CI workflow. Used by:
1. `.husky/pre-commit` — fires when staged files include migrations_v2/
2. `.github/workflows/lint-migration-numbers.yml` — also wired to `push`
   in W41 so post-push regression is caught even when PR is bypassed

Exit 0 if clean. Exit 1 with a duplicate report.

The uniqueness algorithm is intentionally INLINED (not imported from
`backend.db.migration_manager`) because the manager's import chain pulls
in `Settings()` which requires JWT_SECRET_KEY/API_KEYS — unavailable in
local dev shells, hook contexts, and CI lint jobs. Drift mitigation:
the algorithm is 6 lines, identical in both places, and there is a
companion test `test_lint_migration_numbers.py` that locks the contract.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "db" / "migrations_v2"


def find_duplicates(sql_files: Iterable[Path]) -> dict[int, list[str]]:
    """Inlined twin of `backend.db.migration_manager._assert_unique_migration_numbers`.

    Returns {number: [filename, filename, ...]} for any prefix shared by ≥2
    files. Files that don't start with `NNN_` are ignored (manager logs a
    warning later in its own discovery path).
    """
    seen: dict[int, str] = {}
    duplicates: dict[int, list[str]] = {}
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if num in seen:
            duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
        else:
            seen[num] = sql_file.name
    return duplicates


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(
            f"❌ migration-numbers lint: directory not found: {MIGRATIONS_DIR}",
            file=sys.stderr,
        )
        return 2

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print(f"⚠️  migration-numbers lint: no .sql files under {MIGRATIONS_DIR}")
        return 0

    duplicates = find_duplicates(sql_files)
    if duplicates:
        details = ", ".join(
            f"{num}: [{', '.join(files)}]" for num, files in sorted(duplicates.items())
        )
        print(
            f"❌ migration-numbers lint: duplicate prefixes in migrations_v2/: {details}\n"
            "\n"
            "Resolution (cicatrix W40 2026-05-23 convention):\n"
            "  The file that arrived SECOND (in git log time) yields and is\n"
            "  renamed to the next-available number. Workflow:\n"
            "\n"
            "    git mv apps/backend-rag/backend/db/migrations_v2/NNN_<later>.sql \\\n"
            "           apps/backend-rag/backend/db/migrations_v2/MMM_<later>.sql\n"
            "    # update the SQL header comment to match MMM\n"
            "    # update any tests/* that reference the old NNN_ path\n"
            "    git commit -m 'fix(migrations): rename collision NNN -> MMM'\n"
            "\n"
            "Reference: cicatrix RESOLVED 2026-05-23 W40 +\n"
            "research/operations/2026-05-23-w40-migration-194-collision.md",
            file=sys.stderr,
        )
        return 1

    print(f"✅ migration-numbers lint: {len(sql_files)} files, all unique prefixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
