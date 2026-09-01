"""Execute migration 303 — the price it moves is the one clients are quoted.

Migration 303 reversed the e-VOA issuance price to 750.000 IDR after the owner
revoked the 790.000 figure that migration 302 had already applied in
production. Nothing in this repo executed either file before merging it: they
were read, reasoned about, and shipped. That is the gap this closes for 303.

The harness is NOT new — `test_migration_114_115_116_roundtrip.py` has been
applying migrations_v2 files against a real Postgres through the `db_tx`
fixture all along. Claiming otherwise (as an earlier evidence pack of mine did,
in the words "this repo has no execution harness for migrations_v2 at all") was
wrong, and the correction matters more than the test: the tool was there, only
the test for this file was missing.

The forward/rollback split uses `_extract_rollback_sql`, the RUNNER's own
splitter, rather than a private one. A test that disagreed with the runner
about where the forward section ends would be exercising a file the runner
never runs.

`db_tx` wraps every case in a transaction rolled back at teardown, so the rows
written here never survive the test.
"""

from __future__ import annotations

import pathlib

import asyncpg
import pytest

from backend.db.migration_manager import _extract_rollback_sql

pytestmark = pytest.mark.integration

_MIG = (
    pathlib.Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "303_practice_types_voa_price_750.sql"
)

_RULED_PRICE = 750_000
_SUPERSEDED_PRICE = 790_000


def _sections() -> tuple[str, str]:
    text = _MIG.read_text(encoding="utf-8")
    forward = text.split("-- === ROLLBACK ===")[0].strip()
    rollback = _extract_rollback_sql(text) or ""
    assert forward, "303 has no forward section"
    assert rollback, "303 has no ROLLBACK section"
    return forward, rollback


def _update_statement(forward: str) -> str:
    """The bare UPDATE, so a rerun's ROW COUNT can be read.

    Needed because the obvious idempotency assertion does not work: `db_tx`
    wraps the whole test in ONE transaction, and Postgres freezes
    CURRENT_TIMESTAMP at transaction start — so a guard-less rerun rewrites the
    row with the IDENTICAL timestamp and a before/after comparison of
    `updated_at` sees nothing. Measured: deleting the value guard from the
    migration left that version of this test GREEN. asyncpg returns the command
    tag ("UPDATE 0" / "UPDATE 1"), which is the thing that actually distinguishes
    a guarded rerun from an unguarded one.
    """
    start = forward.index("UPDATE practice_types")
    return forward[start : forward.index(";", start) + 1]


def _postcondition_block(forward: str) -> str:
    """The `DO $$ ... $$;` guard, on its own.

    It is deliberately UNREACHABLE in normal operation — the value-guarded
    UPDATE above it always lands the ruled price first — so the only way to
    prove it fires is to run it against a row the UPDATE did not touch.
    Extracting it is what makes that provable instead of asserted.
    """
    start = forward.index("DO $$")
    end = forward.index("$$;", start) + len("$$;")
    return forward[start:end]


async def _seed(conn: asyncpg.Connection, price: int | None) -> None:
    """Put `practice_types` in a known state inside this transaction.

    CREATE TABLE IF NOT EXISTS rather than assuming the schema: this suite runs
    both against CI's freshly-migrated database and against developer machines
    whose local copy is behind.
    """
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS practice_types ("
        "  code text PRIMARY KEY,"
        "  name text,"
        "  base_price numeric,"
        "  updated_at timestamptz DEFAULT now())"
    )
    await conn.execute("DELETE FROM practice_types WHERE code = 'visa_b1_voa'")
    if price is not None:
        await conn.execute(
            "INSERT INTO practice_types (code, name, base_price) "
            "VALUES ('visa_b1_voa', 'B1 - VOA', $1)",
            price,
        )


async def _price(conn: asyncpg.Connection) -> int | None:
    value = await conn.fetchval(
        "SELECT base_price FROM practice_types WHERE code = 'visa_b1_voa'"
    )
    return None if value is None else int(value)


@pytest.mark.asyncio
async def test_forward_moves_the_superseded_price_to_the_ruled_one(
    db_tx: asyncpg.Connection,
) -> None:
    """The production case: the row 302 left at 790.000 becomes 750.000."""
    forward, _ = _sections()
    await _seed(db_tx, _SUPERSEDED_PRICE)

    await db_tx.execute(forward)

    assert await _price(db_tx) == _RULED_PRICE


@pytest.mark.asyncio
async def test_re_applying_it_touches_no_row(db_tx: asyncpg.Connection) -> None:
    """Idempotent by the ROW COUNT, not by landing on the same value twice.

    The value guard (`AND base_price IS DISTINCT FROM 750000`) is what keeps a
    rerun from churning `updated_at` on every deploy and making the catalogue's
    own audit trail useless. Reading the command tag is the only assertion that
    can see it — see `_update_statement` for why the timestamp cannot.
    """
    forward, _ = _sections()
    await _seed(db_tx, _SUPERSEDED_PRICE)

    first = await db_tx.execute(_update_statement(forward))
    assert first == "UPDATE 1", f"the first apply moved no row: {first!r}"
    assert await _price(db_tx) == _RULED_PRICE

    second = await db_tx.execute(_update_statement(forward))
    assert second == "UPDATE 0", (
        f"a rerun touched {second!r} — the WHERE clause has lost its value "
        "guard, so every deploy would churn updated_at on an unchanged price"
    )
    await db_tx.execute(forward)  # and the whole section still runs clean
    assert await _price(db_tx) == _RULED_PRICE


@pytest.mark.asyncio
async def test_an_absent_row_raises_instead_of_recording_success(
    db_tx: asyncpg.Connection,
) -> None:
    """The finding the codex-gpt-5.6-sol seat raised against 302, cured in 303.

    302 answered a missing row with a NOTICE and a clean RETURN. The runner's
    generic verification always returns True and writes the ledger regardless,
    so that database would have ended with the migration marked applied and no
    VOA price at all. 303 must refuse.
    """
    forward, _ = _sections()
    await _seed(db_tx, None)

    with pytest.raises(asyncpg.PostgresError, match="ABSENT"):
        await db_tx.execute(forward)


@pytest.mark.asyncio
async def test_the_postcondition_fires_when_the_update_did_not_land(
    db_tx: asyncpg.Connection,
) -> None:
    """Belt and braces, proven rather than trusted.

    Run the guard alone against a row holding a third value. If it stayed
    silent here, a future edit that broke the UPDATE would record a successful
    migration over a wrong price — which is the failure mode the guard exists
    for, and the one nobody would notice.
    """
    forward, _ = _sections()
    await _seed(db_tx, 900_000)

    with pytest.raises(asyncpg.PostgresError, match="expected 750000"):
        await db_tx.execute(_postcondition_block(forward))


@pytest.mark.asyncio
async def test_the_rollback_restores_the_superseded_price(
    db_tx: asyncpg.Connection,
) -> None:
    """The ROLLBACK section does what its own header says it does.

    Note what this does NOT prove, and what 303's header says explicitly: a
    rollback through `MigrationManager` clears only `_schema_versions` while
    `_is_applied` reads `schema_migrations`, so the next apply-all skips the
    forward section and leaves the superseded price behind a green run. That is
    a runner defect, tracked separately. Here only the SQL is under test.
    """
    forward, rollback = _sections()
    await _seed(db_tx, _SUPERSEDED_PRICE)
    await db_tx.execute(forward)
    assert await _price(db_tx) == _RULED_PRICE

    await db_tx.execute(rollback)

    assert await _price(db_tx) == _SUPERSEDED_PRICE
