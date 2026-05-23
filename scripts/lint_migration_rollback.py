#!/usr/bin/env python3
"""W42 (2026-05-23) — migration ROLLBACK marker presence lint.

Closes the deploy-blocker discovered immediately after W37 (commit
2d864e402, mig 195 ROLLBACK marker missing). `BaseMigration.__init__`
(post-2026-04-18 enforcement at apps/backend-rag/backend/db/migration_base.py)
requires every migration_number > 111 (NOT in LEGACY_NO_ROLLBACK_WHITELIST)
to contain an inline `-- === ROLLBACK ===` marker. Without it the runner
raises ValueError at module-import time, blocking ALL pending migrations.

W37 shipped 195_organism_incident_ledger.sql without the marker. The
rollback procedure WAS documented (research/operations/2026-05-23-w37-
incident-ledger.md), but the runner checks the SQL file inline, not docs.
Deploy would have hard-failed on next run. Caught by sibling agent
~10min after W37 land; fix committed as 2d864e402. W42 closes the gap
at commit-time.

Companion to W41 lint_migration_numbers.py. Same 3-layer defense:
1. This script (standalone, no Settings() dependency)
2. .husky/pre-commit (commit-time block)
3. .github/workflows/lint-migration-rollback.yml (PR + push trigger
   from day 1 — learns from W41 root cause that PR-only triggers
   miss direct-push to main)

Exit 0 if clean. Exit 1 with offending file list + remediation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "db" / "migrations_v2"

# Canonical regex from apps/backend-rag/backend/db/migration_base.py:29
# Inlined per W41 decision (Settings() import-chain unavailable in hooks).
# Drift mitigation: test_drift_check_vs_canonical asserts byte-equal output.
ROLLBACK_MARKER_RE = re.compile(
    r"^\s*--\s*===\s*ROLLBACK\s*===\s*$",
    re.MULTILINE,
)

# Migrations <= 111 are grandfathered (pre-2026-04-18 cutoff in
# BaseMigration.__init__:242). New migrations must include the marker
# unless explicitly added to LEGACY_NO_ROLLBACK_WHITELIST (rare —
# legitimate use case is post-cutoff scaffolding work). Keep this in
# sync with apps/backend-rag/backend/db/migration_base.py:68.
LEGACY_CUTOFF_NUMBER = 111


def find_missing_rollback(sql_files: Iterable[Path]) -> list[Path]:
    """Return migrations that need a ROLLBACK marker but lack one.

    Files are considered "needing a marker" when number > LEGACY_CUTOFF_NUMBER.
    Files <= cutoff are grandfathered (the migration_manager handles them
    via LEGACY_NO_ROLLBACK_WHITELIST; this lint doesn't second-guess).
    """
    offenders: list[Path] = []
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if num <= LEGACY_CUTOFF_NUMBER:
            continue
        try:
            content = sql_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not ROLLBACK_MARKER_RE.search(content):
            offenders.append(sql_file)
    return offenders


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(
            f"❌ migration-rollback lint: directory not found: {MIGRATIONS_DIR}",
            file=sys.stderr,
        )
        return 2

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print(f"⚠️  migration-rollback lint: no .sql files under {MIGRATIONS_DIR}")
        return 0

    offenders = find_missing_rollback(sql_files)
    new_files = [
        p for p in sql_files
        if (int(p.stem.split("_")[0]) if p.stem.split("_")[0].isdigit() else 0) > LEGACY_CUTOFF_NUMBER
    ]

    if offenders:
        print(
            f"❌ migration-rollback lint: {len(offenders)} migration(s) > "
            f"{LEGACY_CUTOFF_NUMBER} missing `-- === ROLLBACK ===` marker:\n"
        )
        for path in offenders:
            print(f"  - apps/backend-rag/backend/db/migrations_v2/{path.name}")
        print(
            "\n"
            "BaseMigration.__init__ requires every migration > "
            f"{LEGACY_CUTOFF_NUMBER} to declare a rollback SQL section\n"
            "INLINE in the .sql file (docs alone don't count — the runner\n"
            "checks the SQL file).\n"
            "\n"
            "Fix template (append to end of offending .sql file):\n"
            "\n"
            "    -- === ROLLBACK ===\n"
            "    DROP TABLE IF EXISTS <table_name> CASCADE;\n"
            "    -- (or whatever reverses the forward migration)\n"
            "\n"
            "Reference:\n"
            "  - apps/backend-rag/backend/db/migration_base.py:29 (regex)\n"
            "  - apps/backend-rag/backend/db/migration_base.py:239 (enforcement)\n"
            "  - cicatrix 2026-04-18 (post-cutoff enforcement)\n"
            "  - W42 cicatrix 2026-05-23 (lint introduction)",
            file=sys.stderr,
        )
        return 1

    print(
        f"✅ migration-rollback lint: {len(new_files)} post-cutoff migrations, "
        f"all have ROLLBACK marker"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
