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

import asyncpg  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.db.migration_manager import MigrationManager  # noqa: E402

logger = logging.getLogger(__name__)


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
    pool: asyncpg.Pool, required: list[str],
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
        "tracking_divergence",
        "required_tables",
    ]
    findings: list[Finding] = []
    try:
        findings.extend(await _check_pending_migrations(manager))
        findings.extend(await _check_tracking_divergence(manager.pool))
        findings.extend(await _check_required_tables(manager.pool, required_tables))
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
    except Exception as exc:  # noqa: BLE001
        logger.exception("schema audit crashed")
        sys.stderr.write(f"ERROR: schema audit crashed: {exc}\n")
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True, indent=2))
    else:
        print(_format_human(report))

    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    sys.exit(main())
