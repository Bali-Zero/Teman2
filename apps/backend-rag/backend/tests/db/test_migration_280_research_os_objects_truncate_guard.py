"""Verify migration 280 closes the TRUNCATE gap on research_os_objects.

Migration 279 (`research_os_contract_core`) creates `public.research_os_objects`
and enforces append-only via a ROW-level `BEFORE UPDATE OR DELETE` trigger.
PostgreSQL never fires row-level triggers for TRUNCATE (it is a statement-level
operation with no per-row event) — so any role holding TRUNCATE privilege on
the table could wipe the entire evidence substrate in one statement, with the
append-only guard never engaged. `grep -ci truncate` on 279 returns 0.

Migration 280 closes that gap additively: one new `FOR EACH STATEMENT` trigger
on the TRUNCATE event, reusing 279's existing
`reject_research_os_objects_mutation()` function verbatim (its body only
references the built-in `TG_TABLE_NAME`, never NEW/OLD, so it is already valid
for statement-level invocation — no function change required). This is the
same established convention migrations 250/251, 252/253, and 264 already
applied to the visa engine's write substrate.

Cicatrix: 2026-04-19-migration-runner — ROLLBACK marker mandatory.
Cicatrix: 2026-04-26-atlas-paywalled — Squawk lint applies at PR time.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import ROLLBACK_MARKER_RE, split_migration_sql

pytestmark_integration = pytest.mark.integration

_MIG_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
MIGRATION_279 = _MIG_DIR / "279_research_os_contract_core.sql"
MIGRATION_280 = _MIG_DIR / "280_research_os_objects_truncate_guard.sql"


def _code_lines(sql_section: str) -> str:
    """Strip comment-only and blank lines, keeping executable SQL only.

    A naive substring check against the raw section text is exactly the
    trap this migration's own header warns about: this file's prose
    legitimately *discusses* tokens like "CREATE FUNCTION" or the name of
    279's row-level trigger inside `--`-prefixed comment lines, without
    those tokens appearing as executable statements. Filtering to
    non-comment lines before asserting keeps the checks anchored to what
    Postgres would actually execute.
    """
    return "\n".join(
        line
        for line in sql_section.splitlines()
        if line.strip() and not line.strip().startswith("--")
    )


# ---------------------------------------------------------------------------
# 1. Static file assertions — no DB required.
# ---------------------------------------------------------------------------


def test_migration_file_exists():
    assert MIGRATION_280.exists(), f"Migration file missing: {MIGRATION_280}"


def test_migration_has_rollback_marker_exactly_once():
    """Cicatrix 2026-04-19 enforces `-- === ROLLBACK ===`.

    Anchored to a whole line via the real `ROLLBACK_MARKER_RE` from
    migration_base.py, never a bare substring match — a naive
    `sql.count("-- === ROLLBACK ===")` over-matches this very file: its own
    prose legitimately *discusses* the marker inline inside backticks (as
    279 also does, twice), which is a real substring occurrence but not a
    standalone marker LINE. This file's actual marker line count is 1.
    """
    sql = MIGRATION_280.read_text()
    matches = ROLLBACK_MARKER_RE.findall(sql)
    assert len(matches) == 1, (
        f"Migration must include exactly one `-- === ROLLBACK ===` marker LINE, found {len(matches)}"
    )


def test_forward_and_rollback_are_both_non_empty():
    sql = MIGRATION_280.read_text()
    forward, rollback = split_migration_sql(sql)
    assert forward.strip() != "", "forward section must not be empty"
    assert rollback is not None, "rollback section must be present"
    assert rollback.strip() != "", "rollback section must not be empty"


def test_forward_adds_statement_level_truncate_trigger_reusing_279_function():
    sql = MIGRATION_280.read_text()
    forward, _ = split_migration_sql(sql)
    code = _code_lines(forward)
    assert "CREATE TRIGGER research_os_objects_no_wipe" in code
    assert "BEFORE TRUNCATE ON public.research_os_objects" in code
    assert "FOR EACH STATEMENT" in code
    # Reuses 279's existing function verbatim — no companion function, no
    # CREATE FUNCTION / CREATE OR REPLACE FUNCTION statement in this file
    # (the header prose discusses that choice in comments, which is fine —
    # `code` below is comment-stripped, so only real statements count).
    assert "EXECUTE FUNCTION public.reject_research_os_objects_mutation()" in code
    assert "CREATE FUNCTION" not in code
    assert "CREATE OR REPLACE FUNCTION" not in code


def test_forward_does_not_touch_279s_objects():
    """Additive only: no ALTER/DROP on the table, columns, or 279's own trigger."""
    sql = MIGRATION_280.read_text()
    forward, _ = split_migration_sql(sql)
    code = _code_lines(forward)
    assert "ALTER TABLE" not in code
    assert "DROP TABLE" not in code
    assert "research_os_objects_immutable" not in code  # 279's row-level trigger
    # Exactly one statement in the forward section: the new CREATE TRIGGER.
    assert code.count("CREATE TRIGGER") == 1


def test_rollback_drops_only_the_new_trigger():
    sql = MIGRATION_280.read_text()
    _, rollback = split_migration_sql(sql)
    assert rollback is not None
    assert "DROP TRIGGER IF EXISTS research_os_objects_no_wipe" in rollback
    assert "ON public.research_os_objects" in rollback
    # Must not remove 279's table/function/row-level trigger — this
    # migration owns exactly one trigger.
    assert "DROP TABLE" not in rollback
    assert "DROP FUNCTION" not in rollback


# ---------------------------------------------------------------------------
# 2. Live-DB proof: apply 279 + 280 against a real connection, transaction-
#    scoped via the shared `db_tx` fixture (rolled back at teardown, so this
#    never touches any real committed schema regardless of whether 279 has
#    already been applied there). Clean-slate-drops 279's owned objects
#    first, inside the same transaction, so this is safe either way.
# ---------------------------------------------------------------------------

_CLEAN_SLATE_SQL = """
DROP TRIGGER IF EXISTS research_os_objects_no_wipe ON public.research_os_objects;
DROP TRIGGER IF EXISTS research_os_objects_immutable ON public.research_os_objects;
DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
DROP TABLE IF EXISTS public.research_os_objects;
"""


async def _apply_clean(conn: asyncpg.Connection) -> None:
    await conn.execute(_CLEAN_SLATE_SQL)
    forward_279, _ = split_migration_sql(MIGRATION_279.read_text())
    await conn.execute(forward_279)
    forward_280, _ = split_migration_sql(MIGRATION_280.read_text())
    await conn.execute(forward_280)


async def _insert_object(conn: asyncpg.Connection, object_id: str) -> None:
    await conn.execute(
        "INSERT INTO research_os_objects "
        "(object_kind, object_id, object_hash, contract_version, payload) "
        "VALUES ('workflow_run', $1, repeat('a', 64), 'research-os/v1.0.0', '{}'::jsonb)",
        object_id,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_truncate_guard_blocks_truncate_but_not_insert(db_tx: asyncpg.Connection) -> None:
    await _apply_clean(db_tx)
    await _insert_object(db_tx, "wr-truncate-guard-innocence")
    count = await db_tx.fetchval("SELECT count(*) FROM research_os_objects")
    assert count == 1, "INSERT must still succeed after the TRUNCATE guard is added"

    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await db_tx.execute("TRUNCATE research_os_objects")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_truncate_guard_rollback_restores_truncate_then_reapply_reblocks(
    db_tx: asyncpg.Connection,
) -> None:
    """Guilt-arm: prove the NEW trigger, not something else, is what blocks TRUNCATE."""
    await _apply_clean(db_tx)
    await _insert_object(db_tx, "wr-truncate-guard-guilt-arm")

    _, rollback_280 = split_migration_sql(MIGRATION_280.read_text())
    assert rollback_280 is not None
    await db_tx.execute(rollback_280)

    # With the guard's own rollback applied, TRUNCATE succeeds again.
    await db_tx.execute("TRUNCATE research_os_objects")
    count = await db_tx.fetchval("SELECT count(*) FROM research_os_objects")
    assert count == 0

    # Re-apply is clean, and TRUNCATE is rejected again.
    forward_280, _ = split_migration_sql(MIGRATION_280.read_text())
    await db_tx.execute(forward_280)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await db_tx.execute("TRUNCATE research_os_objects")
