#!/usr/bin/env python3
"""Schema-state audit for the migration runner.

Strategy 01 Step 6 (see ``docs/reviews/2026-04-25-strategy-01-database-migrations.md``).

Runs a small set of structural checks against the live database and reports
findings as a structured ``AuditReport``. Designed to be invoked as:

* a CLI gate in CI / pre-deploy (``python -m backend.db.schema_audit``),
  exit 0 when clean, exit 1 when any check fails;
* a library function in tests (``run_audit(...)`` returns the report);
* eventually, an alert source for the hotfix Telegram notifier (caller
  decides — this module never sends notifications itself).

Checks implemented in this PR:

1. **Pending migrations.** Discovers ``backend/db/migrations_v2/*.sql`` and
   compares against ``schema_migrations``. Any pending entry is a finding.
2. **Tracking-table divergence.** During the migration-runner consolidation
   we have two tables in flight: ``_schema_versions`` (legacy, written by
   ``MigrationManager``) and ``schema_migrations`` (canonical, written by
   ``BaseMigration.apply()``). The audit fails when a migration number is
   recorded in one but not the other, or when either table records the same
   migration number multiple times — that signals the runner saw a
   half-success / duplicate ledger entry and the next deploy will misjudge the state.
3. **Required-tables presence (opt-in).** When the env var
   ``SCHEMA_AUDIT_REQUIRED_TABLES`` is set to a comma-separated list of
   table names, the audit fails if any of them is missing from the
   ``public`` schema. Empty by default — the project will populate it as
   Step 4 (eliminate ``create_all`` bootstrap) lands.
4. **Client email uniqueness.** The CRM treats email as an identity key;
   duplicates after trim/lowercase normalization are a data-quality failure
   because PostgreSQL's legacy ``UNIQUE(email)`` constraint is case-sensitive.

The audit deliberately does NOT:

* Compare column lists between ORM models and the DB. SQLModel and
  hand-written DDL diverge intentionally on defaults / nullability — see
  ``ci_bootstrap_schema.py`` — and a column-level diff would either spam
  warnings or freeze the schema. That comparison belongs in a different
  tool (Strategy 01 Step 4 cutover).
* Try to fix anything. It only reports.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Make the audit runnable from anywhere without PYTHONPATH gymnastics.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import hashlib

import asyncpg

from backend.app.core.config import settings
from backend.db.migration_manager import MigrationManager

logger = logging.getLogger(__name__)

# The runner discovers migrations here; the audit MUST use the same directory
# or it would verify a different set than the one that applies.
MIGRATIONS_V2_DIR = Path(__file__).resolve().parent / "migrations_v2"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One audit finding.

    ``code`` is a stable machine-readable identifier so tests and the
    Telegram notifier can match on it without parsing prose.
    """

    code: str
    severity: str  # "warning" | "error"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Result of a single audit run."""

    checks_run: list[str]
    findings: list[Finding]

    @property
    def ok(self) -> bool:
        """True iff no error-severity finding was raised."""
        return not any(f.severity == "error" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks_run": list(self.checks_run),
            "findings": [asdict(f) for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Checksum verification (migration 299)
# ---------------------------------------------------------------------------
# `migration_base.py::_log_migration` has computed `sha256(sql)` and stored it
# in `_schema_versions.checksum` for as long as the table has existed. NOTHING
# EVER READ IT BACK -- grep the tree before this PR and the column is
# write-only. A stored proof that is never verified is the same family as a
# cron that exits 0 without doing its work: it reassures without checking.
#
# What a mismatch actually means: the migration FILE on disk is no longer the
# text that was applied to this database. Either the file was edited after the
# fact (which silently diverges every fresh environment from production,
# because a fresh apply runs the NEW text while production carries the OLD
# schema), or the row was written by something other than this runner.
#
# The sentinel is real and must stay allowed. `migration_manager.py:461`
# inserts the literal string `legacy_fake_checksum` for `001_baseline_v2.sql`
# when adopting a pre-existing database -- the SQL was deliberately NOT
# executed there, so no honest checksum exists. Allowing it BY MIGRATION
# NUMBER, with a written reason, is the difference between an exception and a
# hole: a blanket "ignore anything that says legacy" would let any future row
# opt out of verification by storing that string.

LEGACY_CHECKSUM_SENTINEL = "legacy_fake_checksum"

# migration_number -> why this row is allowed to carry the sentinel.
LEGACY_CHECKSUM_ALLOWLIST: dict[int, str] = {
    1: (
        "001_baseline_v2.sql is marked applied WITHOUT executing its SQL when the "
        "runner adopts a pre-existing database (migration_manager.py:451-462); the "
        "text was never run, so there is no honest checksum to record."
    ),
}


def _migration_sql_by_number() -> dict[int, Path]:
    """On-disk migration files keyed by number, discovered the same way the
    runner discovers them so the audit cannot drift from what actually applies."""
    found: dict[int, Path] = {}
    for path in sorted(MIGRATIONS_V2_DIR.glob("*.sql")):
        head = path.name.split("_", 1)[0]
        if head.isdigit():
            found[int(head)] = path
    return found


async def _check_migration_checksums(manager: MigrationManager) -> list[Finding]:
    """Recompute every applied migration's checksum from disk and compare.

    Rows whose file is absent are NOT reported here: that is the orphan case
    `_check_tracking_divergence` already owns, and duplicating it would make
    one schema problem produce two findings with different names.
    """
    findings: list[Finding] = []
    assert manager.pool is not None
    on_disk = _migration_sql_by_number()

    async with manager.pool.acquire() as conn:
        has_table = await _table_exists(conn, "_schema_versions")
        if not has_table:
            return findings
        # SELECT * rather than naming the columns, and the reason is not style.
        # A `_schema_versions` WITHOUT a `checksum` column is a LEGITIMATE
        # shape: several fixtures in this tree create a minimal ledger, and an
        # old database may predate the column. Naming `checksum` in the SELECT
        # makes those a hard error on a schema that is not wrong -- and an
        # audit that cries on a valid shape is one people switch off.
        # The presence is then read off the ROWS, not from a second catalogue
        # round trip: fewer queries, and it cannot disagree with what was
        # actually fetched.
        rows = await conn.fetch("SELECT * FROM _schema_versions ORDER BY migration_number")

    if not rows:
        return findings
    if "checksum" not in rows[0]:
        return findings

    for row in rows:
        number = row["migration_number"]
        stored = row["checksum"]
        path = on_disk.get(number)

        # The sentinel is judged on the ROW, BEFORE the file lookup, and the
        # ordering is load-bearing rather than stylistic. `001_baseline_v2.sql`
        # -- the one migration the allowlist exists for -- has NO FILE in
        # migrations_v2/ at all (the directory starts at 092; that row is
        # written by migration_manager.py when adopting a pre-existing
        # database). Judging the sentinel after `if path is None: continue`
        # therefore made the entire allowlist UNREACHABLE: a branch that looks
        # like a guard and can never fire. Found 2026-08-31 by this check's own
        # corpus failing with KeyError, not by reading the code.
        if stored == LEGACY_CHECKSUM_SENTINEL:
            if number in LEGACY_CHECKSUM_ALLOWLIST:
                continue
            findings.append(
                Finding(
                    code="migration_checksum_unallowed_sentinel",
                    severity="error",
                    message=(
                        f"migration {number} ({row['migration_name']}) stores the "
                        f"{LEGACY_CHECKSUM_SENTINEL!r} sentinel but is not in "
                        "LEGACY_CHECKSUM_ALLOWLIST. The sentinel means 'this SQL was "
                        "never executed'; allowing it implicitly would let any row opt "
                        "out of checksum verification by storing that string."
                    ),
                    details={"migration_number": number, "migration_name": row["migration_name"]},
                )
            )
            continue

        # No file: that is the ORPHAN case, and `_check_tracking_divergence`
        # already owns it. Reporting it here too would turn one schema problem
        # into two findings with different names, which is how an operator
        # learns to ignore both.
        if path is None:
            continue

        actual = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if actual != stored:
            findings.append(
                Finding(
                    code="migration_checksum_mismatch",
                    severity="error",
                    message=(
                        f"migration {number} ({row['migration_name']}) does not match the "
                        "file on disk: the text applied to this database is not the text "
                        "in the repository. A fresh environment would apply the NEW file "
                        "and diverge from this schema."
                    ),
                    details={
                        "migration_number": number,
                        "migration_name": row["migration_name"],
                        "stored_checksum": stored,
                        "recomputed_checksum": actual,
                        "path": str(path),
                    },
                )
            )
    return findings


async def _check_pending_migrations(manager: MigrationManager) -> list[Finding]:
    status = await manager.get_status()
    pending: list[int] = list(status.get("pending_list") or [])
    if not pending:
        return []
    return [
        Finding(
            code="pending_migrations",
            severity="error",
            message=f"{len(pending)} pending migration(s) not applied",
            details={"pending": sorted(pending)},
        ),
    ]


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    """Return True if a public-schema table named ``name`` is present."""
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = $1
            )
            """,
            name,
        ),
    )


def _duplicate_numbers(numbers: list[int]) -> dict[int, int]:
    """Return duplicate migration numbers and their occurrence counts."""
    counts: dict[int, int] = {}
    for number in numbers:
        counts[number] = counts.get(number, 0) + 1
    return {number: count for number, count in sorted(counts.items()) if count > 1}


async def _check_tracking_divergence(pool: asyncpg.Pool) -> list[Finding]:
    """Compare the two tracking tables for orphan rows on either side.

    Both tables are absent on a brand-new DB; if neither exists yet the
    check is a no-op. If only the canonical table (`schema_migrations`)
    exists, the legacy side is considered empty (no divergence).
    """
    findings: list[Finding] = []
    async with pool.acquire() as conn:
        legacy_exists = await _table_exists(conn, "_schema_versions")
        canonical_exists = await _table_exists(conn, "schema_migrations")

        # Brand-new DB: neither table created yet. No divergence to check.
        if not legacy_exists and not canonical_exists:
            return []

        # Post-deprecation state: legacy table dropped (Step 4 cleanup),
        # only canonical exists. There is nothing to diverge against —
        # treat it as steady state, not a finding.
        if not legacy_exists and canonical_exists:
            return []

        legacy_number_rows: list[int] = []
        if legacy_exists:
            rows = await conn.fetch(
                "SELECT migration_number FROM _schema_versions",
            )
            legacy_number_rows = [int(r["migration_number"]) for r in rows]

        canonical_number_rows: list[int] = []
        if canonical_exists:
            rows = await conn.fetch(
                "SELECT migration_number FROM schema_migrations",
            )
            canonical_number_rows = [int(r["migration_number"]) for r in rows]

        legacy_duplicates = _duplicate_numbers(legacy_number_rows)
        canonical_duplicates = _duplicate_numbers(canonical_number_rows)
        if legacy_duplicates:
            findings.append(
                Finding(
                    code="tracking_duplicate_legacy",
                    severity="error",
                    message=(
                        f"{len(legacy_duplicates)} duplicate migration number(s) "
                        "recorded in _schema_versions"
                    ),
                    details={"duplicates": legacy_duplicates},
                ),
            )
        if canonical_duplicates:
            findings.append(
                Finding(
                    code="tracking_duplicate_canonical",
                    severity="error",
                    message=(
                        f"{len(canonical_duplicates)} duplicate migration number(s) "
                        "recorded in schema_migrations"
                    ),
                    details={"duplicates": canonical_duplicates},
                ),
            )

        legacy_numbers = set(legacy_number_rows)
        canonical_numbers = set(canonical_number_rows)

        only_in_legacy = sorted(legacy_numbers - canonical_numbers)
        only_in_canonical = sorted(canonical_numbers - legacy_numbers)

        if only_in_legacy:
            findings.append(
                Finding(
                    code="tracking_divergence_legacy_only",
                    severity="error",
                    message=(
                        f"{len(only_in_legacy)} migration(s) recorded in "
                        "_schema_versions but missing from schema_migrations"
                    ),
                    details={"only_in_legacy": only_in_legacy},
                ),
            )
        if only_in_canonical:
            findings.append(
                Finding(
                    code="tracking_divergence_canonical_only",
                    severity="error",
                    message=(
                        f"{len(only_in_canonical)} migration(s) recorded in "
                        "schema_migrations but missing from _schema_versions"
                    ),
                    details={"only_in_canonical": only_in_canonical},
                ),
            )
    return findings


def _required_tables_from_env() -> list[str]:
    raw = os.environ.get("SCHEMA_AUDIT_REQUIRED_TABLES", "").strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


async def _check_required_tables(
    pool: asyncpg.Pool,
    required: list[str],
) -> list[Finding]:
    if not required:
        return []
    missing: list[str] = []
    async with pool.acquire() as conn:
        for name in required:
            if not await _table_exists(conn, name):
                missing.append(name)
    if not missing:
        return []
    return [
        Finding(
            code="required_table_missing",
            severity="error",
            message=f"{len(missing)} required table(s) missing from public schema",
            details={"missing": missing, "configured_via": "SCHEMA_AUDIT_REQUIRED_TABLES"},
        ),
    ]


async def _check_client_email_uniqueness(pool: asyncpg.Pool) -> list[Finding]:
    """Fail when clients contain duplicate emails after trim/lowercase."""
    async with pool.acquire() as conn:
        if not await _table_exists(conn, "clients"):
            return []

        rows = await conn.fetch(
            """
            SELECT
                LOWER(BTRIM(email)) AS normalized_email,
                COUNT(*)::int AS count,
                ARRAY_AGG(id ORDER BY created_at NULLS LAST, id) AS client_ids
            FROM clients
            WHERE email IS NOT NULL
              AND BTRIM(email) <> ''
            GROUP BY LOWER(BTRIM(email))
            HAVING COUNT(*) > 1
            ORDER BY count DESC, normalized_email
            LIMIT 25
            """,
        )

    if not rows:
        return []

    duplicates = [
        {
            "normalized_email": str(row["normalized_email"]),
            "count": int(row["count"]),
            "client_ids": [int(client_id) for client_id in row["client_ids"]],
        }
        for row in rows
    ]
    return [
        Finding(
            code="client_email_duplicates",
            severity="error",
            message=(
                f"{len(duplicates)} duplicate client email group(s) after "
                "trim/lowercase normalization"
            ),
            details={"duplicates": duplicates},
        ),
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_audit(
    *,
    database_url: str | None = None,
    required_tables: list[str] | None = None,
) -> AuditReport:
    """Run every check and return a :class:`AuditReport`.

    Args:
        database_url: Override for ``settings.database_url``. Tests pass
                their own ephemeral DSN; production callers leave it None.
        required_tables: Override for ``SCHEMA_AUDIT_REQUIRED_TABLES``.
                Tests pin this explicitly; production reads env at call
                time.
    """
    if required_tables is None:
        required_tables = _required_tables_from_env()

    manager = MigrationManager(database_url=database_url)
    await manager.connect()
    assert manager.pool is not None  # connect() is the contract

    checks_run = [
        "pending_migrations",
        "migration_checksums",
        "tracking_divergence",
        "required_tables",
        "client_email_uniqueness",
    ]
    findings: list[Finding] = []
    try:
        findings.extend(await _check_pending_migrations(manager))
        findings.extend(await _check_migration_checksums(manager))
        findings.extend(await _check_tracking_divergence(manager.pool))
        findings.extend(await _check_required_tables(manager.pool, required_tables))
        findings.extend(await _check_client_email_uniqueness(manager.pool))
    finally:
        await manager.close()

    return AuditReport(checks_run=checks_run, findings=findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_human(report: AuditReport) -> str:
    lines = ["=" * 70, "SCHEMA AUDIT", "=" * 70]
    lines.append(f"Checks run: {', '.join(report.checks_run)}")
    if report.ok:
        lines.append("Result: OK — no errors")
    else:
        lines.append(f"Result: FAIL — {len(report.findings)} finding(s)")
    for f in report.findings:
        lines.append("")
        lines.append(f"[{f.severity.upper()}] {f.code}")
        lines.append(f"  {f.message}")
        if f.details:
            lines.append(f"  details: {json.dumps(f.details, sort_keys=True)}")
    lines.append("=" * 70)
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.db.schema_audit",
        description="Audit DB schema state against the migration runner.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON document on stdout instead of human-readable text.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: settings.database_url).",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    db_url = args.database_url or settings.database_url
    if not db_url:
        sys.stderr.write("ERROR: DATABASE_URL not configured\n")
        return 2

    try:
        report = await run_audit(database_url=db_url)
    except Exception as exc:
        logger.exception("schema audit crashed")
        sys.stderr.write(f"ERROR: schema audit crashed: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), sort_keys=True))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_human(report))
        sys.stdout.write("\n")

    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    sys.exit(main())
