"""Structural checks for migration 107 promotion + 193 ledger reconcile.

Background (2026-05-23 panel synthesis Gemini+DeepSeek+Codex):
`bridge_outbox` was originally created by the legacy Python migration
`apps/backend-rag/backend/migrations/migration_107_bridge_outbox.py` and only
recorded in `_schema_versions`. Migration 192 (jsonb double-encoding repair)
assumed the table exists — it does on prod, but fails on fresh CI DBs without
a v2 source-of-truth.

This PR adds:
- `107_bridge_outbox.sql` — promotes the legacy DDL into migrations_v2/ so
  fresh CI DBs build the table the same way prod has it.
- `193_reconcile_107_bridge_outbox_tracking.sql` — backfills
  `schema_migrations(107)` from `_schema_versions(107)` because the v2 runner
  computes pending migrations by number from `_schema_versions`, so 107.sql
  is SKIPPED on prod and never logs into `schema_migrations` itself.

What this test enforces (no Postgres needed):
- both files present;
- both carry the `-- === ROLLBACK ===` marker;
- forward + rollback blocks non-empty;
- 107 uses IF NOT EXISTS on every CREATE (idempotency invariant);
- 107 column type fidelity: BIGSERIAL matches the legacy Python migration;
- ROLLBACK section of 107 is non-destructive (no table-removal verb) —
  the table holds live event payloads on prod.
- 193 INSERT is guarded by NOT EXISTS subquery + ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIG_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"

PROMOTION_FILE = "107_bridge_outbox.sql"
RECONCILE_FILE = "193_reconcile_107_bridge_outbox_tracking.sql"

_ROLLBACK_MARKER = re.compile(r"^--\s*===\s*ROLLBACK\s*===\s*$", re.MULTILINE | re.IGNORECASE)


def _strip_sql_comments(sql: str) -> str:
    out: list[str] = []
    for line in sql.splitlines():
        idx = line.find("--")
        out.append(line[:idx] if idx >= 0 else line)
    return "\n".join(out)


def _split(sql_text: str) -> tuple[str, str]:
    parts = _ROLLBACK_MARKER.split(sql_text, maxsplit=1)
    forward = _strip_sql_comments(parts[0]).strip()
    rollback = _strip_sql_comments(parts[1]).strip() if len(parts) == 2 else ""
    return forward, rollback


@pytest.fixture(scope="module")
def promotion_sql() -> str:
    path = MIG_DIR / PROMOTION_FILE
    assert path.exists(), f"missing migration file: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def reconcile_sql() -> str:
    path = MIG_DIR / RECONCILE_FILE
    assert path.exists(), f"missing migration file: {path}"
    return path.read_text(encoding="utf-8")


def test_both_files_present() -> None:
    """Both halves of the promotion must ship together (see panel synthesis)."""
    assert (MIG_DIR / PROMOTION_FILE).exists(), f"missing {PROMOTION_FILE}"
    assert (MIG_DIR / RECONCILE_FILE).exists(), f"missing {RECONCILE_FILE}"


def test_files_have_rollback_marker(promotion_sql: str, reconcile_sql: str) -> None:
    assert _ROLLBACK_MARKER.search(promotion_sql), f"{PROMOTION_FILE}: missing rollback marker"
    assert _ROLLBACK_MARKER.search(reconcile_sql), f"{RECONCILE_FILE}: missing rollback marker"


def test_forward_and_rollback_blocks_non_empty(promotion_sql: str, reconcile_sql: str) -> None:
    for name, sql in ((PROMOTION_FILE, promotion_sql), (RECONCILE_FILE, reconcile_sql)):
        forward, rollback = _split(sql)
        assert forward, f"{name}: forward block empty"
        assert rollback, f"{name}: rollback block empty"


def test_promotion_uses_if_not_exists(promotion_sql: str) -> None:
    """107 forward must be idempotent — prod already has the table."""
    forward, _ = _split(promotion_sql)
    create_table_pat = re.compile(r"\bCREATE\s+TABLE\b(?!\s+IF\s+NOT\s+EXISTS)", re.IGNORECASE)
    create_index_pat = re.compile(
        r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?!\s+(?:CONCURRENTLY\s+)?IF\s+NOT\s+EXISTS)",
        re.IGNORECASE,
    )
    assert not create_table_pat.findall(forward), (
        f"{PROMOTION_FILE}: CREATE TABLE without IF NOT EXISTS"
    )
    assert not create_index_pat.findall(forward), (
        f"{PROMOTION_FILE}: CREATE INDEX without IF NOT EXISTS"
    )


def test_promotion_id_type_fidelity_bigserial(promotion_sql: str) -> None:
    """id column must be BIGSERIAL to match the legacy Python migration.

    DeepSeek panelist assumed SERIAL — empirical check 2026-05-23 of
    `apps/backend-rag/backend/migrations/migration_107_bridge_outbox.py` line 34
    confirms legacy is BIGSERIAL. Using SERIAL would create cross-environment
    schema drift on fresh CI DBs while prod stays BIGSERIAL.
    """
    forward, _ = _split(promotion_sql)
    assert re.search(r"\bid\s+BIGSERIAL\s+PRIMARY\s+KEY\b", forward, re.IGNORECASE), (
        f"{PROMOTION_FILE}: id must be BIGSERIAL PRIMARY KEY (matches legacy .py)"
    )


def test_promotion_rollback_is_non_destructive(promotion_sql: str) -> None:
    """ROLLBACK of 107 must not remove the bridge_outbox table or its data.

    On prod the table predates the v2 row and holds live event payloads the
    WR3 bridge consumer replays. A CLI rollback that issued a removal verb
    would destroy event history. The rollback block must be a no-op.
    """
    _, rollback = _split(promotion_sql)
    removal_verbs = re.compile(
        r"\b(?:DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM)\b",
        re.IGNORECASE,
    )
    assert not removal_verbs.search(rollback), (
        f"{PROMOTION_FILE}: rollback must be non-destructive "
        "(bridge_outbox holds live event payloads on prod)"
    )


def test_reconcile_insert_is_guarded(reconcile_sql: str) -> None:
    """193 must NOT EXISTS-guard + ON CONFLICT DO NOTHING the schema_migrations insert.

    Either guard alone would let a duplicate slip through if the runner ever
    re-applies the migration (legacy + v2 tracker disagree). Both are required.
    """
    forward, _ = _split(reconcile_sql)
    assert "NOT EXISTS" in forward.upper(), (
        f"{RECONCILE_FILE}: forward must guard with NOT EXISTS subquery"
    )
    assert re.search(r"ON\s+CONFLICT\b.*DO\s+NOTHING", forward, re.IGNORECASE | re.DOTALL), (
        f"{RECONCILE_FILE}: forward must use ON CONFLICT DO NOTHING"
    )


def test_reconcile_targets_migration_number_107(reconcile_sql: str) -> None:
    """193 must explicitly reconcile migration_number=107 — not a generic backfill.

    This is a targeted repair for the 107 tracker divergence. If the SELECT
    ever loses the `WHERE sv.migration_number = 107` clause, the migration
    would copy every legacy row into schema_migrations, breaking the invariant.
    """
    forward, _ = _split(reconcile_sql)
    assert re.search(r"migration_number\s*=\s*107", forward), (
        f"{RECONCILE_FILE}: must explicitly target migration_number = 107"
    )
