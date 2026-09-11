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
import re
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

# A real checksum is a sha256 hex digest. ANYTHING ELSE is a SYMBOLIC value
# written by a migration that deliberately did not execute the SQL it is
# claiming, and it must be allowlisted or reported. Matching the SHAPE rather
# than a list of known strings is what makes this close the CLASS: the first
# draft allowlisted one literal, and a blind refuter found THREE symbolic
# values in the tree -- `legacy_fake_checksum`, `tracked-by-migration-165` and
# `tracked-by-migration-166` -- plus `legacy-107-bridge-outbox`. Comparing
# those against real sha256 digests would have failed the `release_command` on
# a PERFECTLY HEALTHY production database: a verifier turned into an outage,
# which is the worst possible outcome for a check whose whole purpose is to
# make deploys safer.
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")

LEGACY_CHECKSUM_SENTINEL = "legacy_fake_checksum"

# (migration_number, migration_name) -> why this row may carry a symbolic
# checksum. Keyed on the PAIR, not the number alone: a number-only key lets any
# future row renumbered to 1 skip verification, and the divergence checker
# compares numbers only, so nothing else would notice.
# Keyed on (number, name) AND bound to the EXACT symbolic value the row must
# carry: `(number, name) -> (expected_checksum, reason)`.
#
# Value-binding closes a real bypass, raised as CONFIRMED by a second
# cross-family seat (Kimi K3, 2026-08-31): keyed on the pair ALONE, adding a
# migration here exempts it UNCONDITIONALLY -- including after its file is
# tampered with, and including if its stored checksum later becomes a real
# digest that ought to be verified. Bound to the value, an entry excuses
# exactly one known string and nothing else: a real sha256 on an allowlisted
# row is verified normally, and a DIFFERENT symbolic value is an error.
SYMBOLIC_CHECKSUM_ALLOWLIST: dict[tuple[int, str], tuple[str, str]] = {
    (1, "001_baseline_v2.sql"): (
        "legacy_fake_checksum",
        "marked applied WITHOUT executing its SQL when the runner adopts a "
        "pre-existing database (migration_manager.py:451-462); the text never ran, "
        "so there is no honest checksum to record.",
    ),
    (107, "107_bridge_outbox"): (
        "legacy-107-bridge-outbox",
        "the ledger row is BACKFILLED by migration 194 with the literal "
        "'legacy-107-bridge-outbox'; 107 itself was promoted from a legacy Python "
        "migration, so the row records the promotion rather than an execution of "
        "this file's text.",
    ),
    (165, "165_reconcile_schema_migrations_duplicates"): (
        "tracked-by-migration-165",
        "this migration INSERTS ITS OWN ledger row with 'tracked-by-migration-165', "
        "and `_log_migration` then uses ON CONFLICT DO NOTHING, so the symbolic "
        "value is never replaced by a real digest.",
    ),
    (166, "166_reconcile_client_email_duplicates"): (
        "tracked-by-migration-166",
        "same self-inserting shape as 165, with 'tracked-by-migration-166'; the "
        "ON CONFLICT DO NOTHING in `_log_migration` leaves the symbolic value in "
        "place for the lifetime of the row.",
    ),
}

# NOTE ON THE NAMES: three of these four carry NO `.sql` suffix, and that is not
# a typo. The runner writes `migration_name` from the FILENAME (with suffix),
# but 165, 166 and 194 write their own rows with a hand-written name string that
# omits it. The allowlist must match what is actually IN the column, not what
# the filename looks like -- measured by reading those INSERT statements.

# Kept as a derived view so callers and tests can ask "is this number allowed"
# without duplicating the pair logic.
LEGACY_CHECKSUM_ALLOWLIST: dict[int, str] = {
    number: reason for (number, _name), (_value, reason) in SYMBOLIC_CHECKSUM_ALLOWLIST.items()
}


# Enforcement stage for the two CHECKSUM findings, and only those two.
#
# This verifier was armed fail-closed on 2026-08-30 (#5335) against a
# production `_schema_versions` it had never been measured against: 17 rows
# carry a symbolic checksum ('manual_apply', 'manual-fix', 'manual', '', and
# one MD5) and 8 more disagree with the file on disk. All 25 predate the check.
# The result was exactly the outage this module's own comment above warns
# about -- every backend deploy failed its `release_command` from 19:02 UTC
# onward, stranding 25+ merged commits, because a row written in January can
# never become verifiable no matter how long the deploy stays broken.
#
# The first cure (#5376) demoted the two checksum findings to WARNING for the
# whole CLASS. That unblocked the deploy and it was the wrong shape: a
# class-wide demotion disarms the check for FUTURE drift too, so the price of
# ending the outage was a permanent blind spot -- exactly the trade that turns
# an incident into a silent hole nobody re-opens.
#
# THIS IS NO LONGER WHAT THE CODE DOES. #5383 replaced the class demotion with
# LEGACY_CHECKSUM_BASELINE below: the two checksum findings are ERROR again by
# default, and ONLY the 25 exact rows in that table are demoted to warning, and
# only while their fingerprint still matches -- `stored` for all 25, plus
# `recomputed` for the 8 mismatches. Edit the file behind a baselined mismatch,
# or change the stored value of any baselined row, and it is an error again.
# A migration that is not in the table has never been covered.
#
# So the 8 mismatches DO have a mechanism of their own now; the sentence that
# stood here until 2026-08-31 said they had none, which was true of #5376 and
# false of the code it was sitting in.
#
# SCHEMA_AUDIT_CHECKSUM_ENFORCE promotes even the baselined rows to error --
# the same canary shape the rest of this repo uses (E33_CLAIM_GUARD_ENFORCE,
# VISA_ENGINE_EVALUATE_MODE), so arming it is `fly secrets set`, not a revert.
# It RAISES on a value it does not recognise rather than failing open, because
# a flag that silently ignores a typo disarms a gate exactly when someone
# believes they armed it.
#
# What must be true before flipping it: somebody reads the 8 mismatch diffs and
# writes down, per migration, whether the file was edited after it was applied
# or the recorded hash was wrong -- and then DELETES that row from the baseline.
# A row that stays in the table is still unguarded, whatever comment sits
# beside it.
#
# LIMIT, stated because "baselined" reads like "verified" and is not: for the
# 17 SENTINEL rows the file is never hashed AT ALL. `_check_migration_checksums`
# takes the `if not _SHA256_HEX.match(stored)` branch and `continue`s before it
# reaches `actual = hashlib.sha256(path.read_text(...))`, so rewriting the .sql
# behind migration 2, 3, ... 182 produces no finding at any severity. That is
# inherent to a stored value that was never a digest -- there is nothing to
# compare against -- and it is NOT introduced by the baseline; the baseline
# only decides the severity of a finding that the sentinel branch has already
# raised about the stored VALUE. Do not read a green checksum audit as evidence
# that those 17 files are unchanged.
#
# DELIBERATELY NOT DEMOTED: every other finding in this module. A pending
# migration, a duplicate number, a tracking divergence or a missing required
# table still fails the deploy, because each of those describes something the
# CURRENT deploy is about to get wrong.
# The 25 rows production was already carrying when this verifier was armed on
# 2026-08-30, read verbatim out of the failing `release_command` — number,
# name, and the EXACT stored value, plus the recomputed digest for the eight
# whose file disagrees. Not transcribed by hand: extracted from the run's own
# `details:` JSON.
#
# WHY A BASELINE AND NOT A CLASS-WIDE DEMOTION. The first cure (#5376) demoted
# the whole checksum CLASS to warning, which unblocked the fleet but also
# disarmed the check against corruption that has not happened yet: tamper with
# migration 300 tomorrow and the deploy would still exit 0. A cross-family
# refuter (Codex gpt-5.6-sol, xhigh) named that as its lead finding and it was
# right. Pinning the 25 known rows instead restores fail-closed for everything
# else — a NEW anomaly, even on one of these same migration numbers, is an
# error again.
#
# BOUND TO THE VALUES, NOT THE ROW. A sentinel entry excuses one exact stored
# string; a mismatch entry excuses one exact (stored, recomputed) PAIR. So
# editing one of those eight legacy .sql files turns the deploy red rather
# than silently re-excusing a different divergence. That is deliberate and it
# is the one real cost of this design: those eight files are effectively
# frozen until someone re-baselines. Editing an already-applied migration is
# precisely the event this check exists to stop, so the cost is the feature.
LegacyFingerprint = tuple[str, str | None]

LEGACY_CHECKSUM_BASELINE: dict[tuple[int, str], LegacyFingerprint] = {
    (2, "002_portal_sync_tables.sql"): ("manual_apply", None),
    (3, "003_portal_performance_indexes.sql"): ("manual_apply", None),
    (4, "004_query_analytics.sql"): ("manual_apply", None),
    (5, "005_workflow_analytics.sql"): ("manual_apply", None),
    (6, "006_performance_indexes_advanced"): ("", None),
    (19, "migration_019"): ("", None),
    (22, "022_dedup_constraints"): ("manual-fix", None),
    (23, "migration_023"): ("", None),
    (26, "026_review_queue"): ("manual-fix", None),
    (34, "034_company_centric_crm"): ("manual", None),
    (40, "040_documents_drive_integrity"): ("", None),
    (41, "041_workflow_jobs_context"): ("", None),
    (42, "042_clients_tax_ids"): ("", None),
    (43, "043_invoices_table"): ("", None),
    (44, "044_cleanup_practices_invoice_jsonb"): ("", None),
    (45, "045_visa_records_type_fk"): ("", None),
    (182, "182_companies_tax_dept_folder"): (
        "031c4d196dcc3860b6ee0598d0db7853",  # pragma: allowlist secret
        None,
    ),
    # --- mismatches ---
    (127, "127_war_room_canva_url"): (
        "ff34400ec9cd949199a00d66ce2a60601c376ebe45591fee9f95fc4a6011ca76",  # pragma: allowlist secret
        "9a493d1f70c814bc15bcd21e613bf0fb8881505526e07761dab1d6602cff066b",  # pragma: allowlist secret
    ),
    (157, "157_practice_types_2026_pricing_delta"): (
        "f602c9afefc92ff7750ca0d5c63145771756d79bdab6819bc582d2b7b6412512",  # pragma: allowlist secret
        "4caafd4a22cb66c915425e11d5f07401960310678a90717948b39a61b14d2d43",  # pragma: allowlist secret
    ),
    (158, "158_practices_discount_columns"): (
        "86cbe9765757450b42f2f075394c0f54364d89de2cd9cda86deb35893545e190",  # pragma: allowlist secret
        "1a1c1931d2a5e48dcb813c8cb8df2adff6b0a8adf63fa556a8ff28eb0119d13a",  # pragma: allowlist secret
    ),
    (186, "186_crm_phone_dedup_2026_05_20"): (
        "431e0465a0e055c36e5b51615c627da36d557845b542f5c950ba7d49ae0e1ba9",  # pragma: allowlist secret
        "ea743cce867034bfd0600ed64903d6265891ea3caff231d1f52b3d88f25afa5c",  # pragma: allowlist secret
    ),
    (192, "192_bridge_outbox_jsonb_double_encoding_repair"): (
        "6a070dbdb8c2dd9de289c5c42e45798816b9a6475af65d2e6f98c3fe773e2083",  # pragma: allowlist secret
        "df865b0734d7e98c8ea421bb93bfddbd74c68a0a984eb797adbc8029fc045bfb",  # pragma: allowlist secret
    ),
    (200, "200_wa_copilot_infrastructure"): (
        "70d0962f1d17f8bd0413b5c2160b94812d0a7e9a8a8054f505427108365b0fe8",  # pragma: allowlist secret
        "e32d488b2c6c5a9c799159fd83be4979d3d6928181f845db0d1b62ea48658845",  # pragma: allowlist secret
    ),
    (207, "207_team_admin_runtime_grants"): (
        "a101bc5f13f47357e96b59d0e1815cae8befd0e3329e9b9560e16df06623edca",  # pragma: allowlist secret
        "280a7abc2e1209f7dee167a8fac837f9f033a4e90238f67c83760d84ff88b9c5",  # pragma: allowlist secret
    ),
    (217, "217_intake_commit_audit"): (
        "4404de267c13064f25929089b227b8d269f65b52924117a2fa68094e7378540a",  # pragma: allowlist secret
        "5522a284fbf7fb958c4b088a2ce591dccc2d5f72b44c26124bdd2a565d7daef9",  # pragma: allowlist secret
    ),
}


def _baseline_covers(number: int, name: str, stored: str | None, recomputed: str | None) -> bool:
    """True iff this exact row is one of the 25 known-legacy rows.

    `recomputed is None` in the table means a sentinel entry (there is no
    honest digest to compare); a mismatch entry pins BOTH sides.
    """
    entry = LEGACY_CHECKSUM_BASELINE.get((number, name))
    if entry is None:
        return False
    baseline_stored, baseline_recomputed = entry
    if stored != baseline_stored:
        return False
    return baseline_recomputed is None or baseline_recomputed == recomputed


_CHECKSUM_ENFORCE_ENV = "SCHEMA_AUDIT_CHECKSUM_ENFORCE"
_TRUTHY = frozenset({"1", "true", "yes", "on", "enforce"})
_FALSY = frozenset({"0", "false", "no", "off"})


def _enforcement_armed() -> str | None:
    """The raw flag value if enforcement is armed, else None.

    Read per call, never cached at import: the release_command is a fresh
    process, but a long-lived caller must not be pinned to whatever value the
    module happened to see first.

    An UNRECOGNISED non-empty value raises rather than reading as "off". A
    flag whose typo fails open is the failure this whole file is about:
    `SCHEMA_AUDIT_CHECKSUM_ENFORCE=treu` would otherwise leave the gate
    disarmed with no error and no log line, and the operator who typed it
    would have every reason to believe it was on. `ENFORCE` is accepted
    because the neighbouring `VISA_ENGINE_EVALUATE_MODE` takes that literal
    word, and an operator carrying the habit across must not be silently
    wrong.
    """
    raw = os.environ.get(_CHECKSUM_ENFORCE_ENV, "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in _TRUTHY:
        return raw
    if lowered in _FALSY:
        return None
    raise ValueError(
        f"{_CHECKSUM_ENFORCE_ENV}={raw!r} is not a recognised value. "
        f"Use one of {sorted(_TRUTHY)} to arm, {sorted(_FALSY)} to disarm, or "
        "leave it unset. Refusing to guess: a flag that reads an unknown value "
        "as 'off' disarms the gate exactly when someone believed they armed it."
    )


def _checksum_severity(
    number: int, name: str, stored: str | None, recomputed: str | None = None
) -> str:
    """Severity for ONE checksum finding.

    `error` for everything, EXCEPT the 25 fingerprints in
    `LEGACY_CHECKSUM_BASELINE`, which are `warning` until enforcement is armed.
    A row that is not in the baseline — or is, but with a different value — is
    a new anomaly and fails the deploy.
    """
    if _enforcement_armed() is not None:
        return "error"
    return "warning" if _baseline_covers(number, name, stored, recomputed) else "error"


def _migration_sql_by_number() -> dict[int, Path]:
    """On-disk migration files keyed by number, discovered the same way the
    runner discovers them so the audit cannot drift from what actually applies."""
    found: dict[int, Path] = {}
    for path in sorted(MIGRATIONS_V2_DIR.glob("*.sql")):
        head = path.name.split("_", 1)[0]
        if head.isdigit():
            found[int(head)] = path
    return found


async def _check_migration_checksums(
    manager: MigrationManager, *, table: str = "_schema_versions"
) -> list[Finding]:
    """Recompute every applied migration's checksum from disk and compare.

    Rows whose file is absent are NOT reported here: that is the orphan case
    `_check_tracking_divergence` already owns, and duplicating it would make
    one schema problem produce two findings with different names.
    """
    findings: list[Finding] = []
    assert manager.pool is not None
    on_disk = _migration_sql_by_number()

    async with manager.pool.acquire() as conn:
        has_table = await _table_exists(conn, table)
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
        rows = await conn.fetch(f"SELECT * FROM {table} ORDER BY migration_number")

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
        if not _SHA256_HEX.match(stored or ""):
            allowed = SYMBOLIC_CHECKSUM_ALLOWLIST.get((number, row["migration_name"]))
            if allowed is not None and allowed[0] == stored:
                continue
            findings.append(
                Finding(
                    code="migration_checksum_unallowed_sentinel",
                    severity=_checksum_severity(number, row["migration_name"], stored),
                    message=(
                        f"migration {number} ({row['migration_name']}) stores "
                        f"{stored!r}, which is not a sha256 digest, and the pair "
                        "(number, name) is not in SYMBOLIC_CHECKSUM_ALLOWLIST. A "
                        "symbolic checksum means 'this SQL was never executed'; "
                        "allowing it implicitly would let any row opt out of "
                        "verification by storing a non-digest string. An allowlist "
                        "entry excuses exactly ONE known value, so a DIFFERENT "
                        "symbolic string on an allowlisted row still lands here."
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
                    severity=_checksum_severity(number, row["migration_name"], stored, actual),
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


def _plural(count: int, noun: str) -> str:
    """`1 error` / `2 errors` — not `1 error(s)`. A deploy log is read at 03:00
    by someone deciding whether to scroll; `(s)` is one more thing to parse."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _format_human(report: AuditReport) -> str:
    lines = ["=" * 70, "SCHEMA AUDIT", "=" * 70]
    lines.append(f"Checks run: {', '.join(report.checks_run)}")
    errors = sum(1 for f in report.findings if f.severity == "error")
    warnings = len(report.findings) - errors
    # A warning-only report must never render as an empty success. The whole
    # risk of demoting a finding is that the summary line starts impersonating
    # "nothing was found" -- so the count is always stated, on both branches.
    suffix = f" ({_plural(warnings, 'warning')})" if warnings else ""
    if report.ok:
        lines.append(f"Result: OK — no errors{suffix}")
    else:
        lines.append(f"Result: FAIL — {_plural(errors, 'error')}{suffix}")
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
