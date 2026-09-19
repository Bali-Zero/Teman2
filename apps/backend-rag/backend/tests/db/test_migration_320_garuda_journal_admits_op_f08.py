"""Contract checks for migration 320's widened `transition_id` CHECK on
`garuda_order_journal` -- and a live-DB proof that OP-F08 is admitted while
a genuinely invented id is not, which a text-only check cannot distinguish.

Same harness `test_migration_303_voa_price_roundtrip.py` uses: `db_tx` wraps
every case in one transaction rolled back at teardown, so nothing written
here survives the test, and the forward SQL is re-applied inside that
transaction so this suite runs clean whether the target database already has
320 live (CI's freshly-`apply-all`'d one) or is a developer machine behind it
-- `DROP CONSTRAINT IF EXISTS` makes re-application idempotent, same
reasoning 303's own docstring gives.

WHY THE LIVE INSERT MATTERS, NOT JUST THE TEXT. `reconciliation.py`'s
per-row `except Exception: logger.exception(...); continue` would swallow a
`check_violation` raised by an un-widened constraint and report success
anyway (superscar #2) -- migration 320's own header names this as the exact
defect it exists to prevent. A test that only grepped the SQL for `'OP-F08'`
would pass just as happily against a constraint that had been WIDENED in the
file but never actually applied, or applied to the wrong table. The
`test_an_invented_transition_id_still_raises` case below is the one that
actually matters: without it, this suite would also pass against a
constraint that had been DROPPED outright rather than widened -- `OP-F08`
would insert fine either way, and only an invented id proves the CHECK is
still a closed vocabulary rather than gone.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_manager import _extract_rollback_sql

pytestmark = pytest.mark.integration

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "320_garuda_journal_admits_op_f08.sql"
)

_ORDER_ID = "ord_migration_320_test"


def _sections() -> tuple[str, str]:
    text = _MIGRATION.read_text(encoding="utf-8")
    forward = text.split("-- === ROLLBACK ===")[0].strip()
    rollback = _extract_rollback_sql(text) or ""
    assert forward, "320 has no forward section"
    assert rollback, "320 has no ROLLBACK section"
    return forward, rollback


def _code_lines(sql_section: str) -> str:
    """Strip comment-only and blank lines, keeping executable SQL only.

    The forward section's own prose comment DISCUSSES the removed `NOT
    VALID` split ("the usual `ADD ... NOT VALID` then `VALIDATE` split
    bought a shorter exclusive...") without either token appearing as
    executable SQL -- a naive substring check against the raw section
    would misread that comment as the split still being present. Same
    convention as `test_migration_280_research_os_objects_truncate_
    guard.py`'s own `_code_lines`.
    """
    return "\n".join(
        line
        for line in sql_section.splitlines()
        if line.strip() and not line.strip().startswith("--")
    )


def test_320_widens_the_check_to_admit_op_f08_only() -> None:
    """Forward is one DROP + one VALIDATING ADD -- no `NOT VALID`/`VALIDATE`
    split (a later revision removed it: the runner wraps the whole file in
    one transaction, so the split bought no shorter lock and the comment
    claiming otherwise was false). Rollback keeps `NOT VALID` for a DIFFERENT
    reason -- the journal is append-only, so a rollback-time `VALIDATE`
    could find rows this migration itself let in and take the rollback down
    with it -- so the two halves are asymmetric on purpose."""

    forward, rollback = _sections()
    forward_code = _code_lines(forward)
    rollback_code = _code_lines(rollback)

    assert "'OP-F08'" in forward_code
    assert "DROP CONSTRAINT IF EXISTS garuda_order_journal_transition_id_check" in forward_code
    assert "ADD CONSTRAINT garuda_order_journal_transition_id_check" in forward_code
    assert "NOT VALID" not in forward_code
    assert "VALIDATE CONSTRAINT" not in forward_code

    # Rollback narrows OP-F08 back out, and touches nothing else this
    # migration did not add -- OP-F04/OP-F05 (already live before 320) stay.
    # It DOES keep NOT VALID (see docstring), unlike the forward half.
    assert "'OP-F08'" not in rollback_code
    assert "'OP-F04'" in rollback_code
    assert "'OP-F05'" in rollback_code
    assert "NOT VALID" in rollback_code


async def _insert_journal_row(
    conn: asyncpg.Connection, *, transition_id: str, event_id: str
) -> None:
    await conn.execute(
        """
        INSERT INTO garuda_order_journal
            (event_id, event_name, aggregate_type, aggregate_id, transition_id,
             customer_visible, detail)
        VALUES ($1, 'payment.charge_detected_without_webhook', 'order', $2, $3,
                FALSE, '{}'::jsonb)
        """,
        event_id,
        _ORDER_ID,
        transition_id,
    )


@pytest.mark.asyncio
async def test_op_f08_journal_insert_is_admitted(db_tx: asyncpg.Connection) -> None:
    forward, _ = _sections()
    await db_tx.execute(forward)

    await _insert_journal_row(db_tx, transition_id="OP-F08", event_id="evt_migration320_admit_test")
    row = await db_tx.fetchrow(
        "SELECT transition_id FROM garuda_order_journal WHERE event_id = $1",
        "evt_migration320_admit_test",
    )
    assert row is not None
    assert row["transition_id"] == "OP-F08"


@pytest.mark.asyncio
async def test_an_invented_transition_id_still_raises(db_tx: asyncpg.Connection) -> None:
    """The half that actually matters -- see module docstring. `OP-F99`
    names nothing in STATE-MACHINE.md or events.yaml."""

    forward, _ = _sections()
    await db_tx.execute(forward)

    with pytest.raises(asyncpg.CheckViolationError):
        await _insert_journal_row(
            db_tx, transition_id="OP-F99", event_id="evt_migration320_reject_test"
        )
