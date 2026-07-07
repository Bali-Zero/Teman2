"""Integration test for the reconcile confirm service against a real Postgres.

Applies migration 238 to an ephemeral DB, seeds a practice + invoice + bank
transaction, runs confirm_payment(), and asserts every side effect: practice
status/paid_amount, invoice payment fields, bank txn reconciled, weekly_cashout
row with decomposition, and the immutable reconciliation_log row.

Skipped automatically if a local Postgres isn't reachable (CI uses mocks for the
router; this test is the real-DB belt-and-braces for the single writer).
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import date
from pathlib import Path

import asyncpg
import pytest
from asyncpg.exceptions import CheckViolationError

from backend.services.accounting.cashout_service import cashbook_summary
from backend.services.accounting.reconcile_service import confirm_payment

MIGRATION_238 = (
    Path(__file__).resolve().parents[2]
    / "db" / "migrations_v2" / "238_accounting_asya.sql"
)
MIGRATION_239 = (
    Path(__file__).resolve().parents[2]
    / "db" / "migrations_v2" / "239_cashout_worksheet_type.sql"
)

STUBS = """
CREATE TABLE IF NOT EXISTS team_members (id VARCHAR PRIMARY KEY);
CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, full_name VARCHAR);
CREATE TABLE IF NOT EXISTS practices (
    id SERIAL PRIMARY KEY, client_id INT, payment_status VARCHAR DEFAULT 'unpaid',
    paid_amount NUMERIC DEFAULT 0, updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY, practice_id INT UNIQUE, invoice_number VARCHAR,
    amount_idr BIGINT, generated_at TIMESTAMPTZ DEFAULT now());
"""


def _forward_sql_of(migration: Path) -> str:
    text = migration.read_text(encoding="utf-8")
    # apply only the part before the ROLLBACK marker (mirrors the runner)
    return re.split(r"^-- === ROLLBACK ===\s*$", text, maxsplit=1, flags=re.MULTILINE)[0]


def _base_dsn() -> str:
    """One DSN for every connection in this test.

    CI provides a password-protected Postgres service and sets TEST_DATABASE_URL
    (postgresql://test:test@localhost/nuzantara_test) — every connect MUST carry
    those credentials. On a dev box TEST_DATABASE_URL is unset and we fall back to
    the local peer/trust-auth socket (passwordless $USER@localhost). asyncpg lets
    us reuse this base DSN and only override the `database=` per connection, so we
    never rebuild a passwordless `{user}@localhost` DSN that auth-fails in CI.
    """
    return os.environ.get(
        "TEST_DATABASE_URL",
        f"postgresql://{os.environ.get('USER', 'postgres')}@localhost:5432/postgres",
    )


async def _try_connect() -> asyncpg.Connection | None:
    try:
        # connect to the admin/maintenance DB (postgres) using the base creds
        return await asyncpg.connect(_base_dsn(), database="postgres")
    except Exception:
        return None


async def _fresh_db() -> tuple[asyncpg.Connection, str, str]:
    """Create an ephemeral DB with the migration applied + minimal stubs.

    Returns (conn, dbname, user). Caller is responsible for teardown via
    _drop_db(). Skips the test if no Postgres is reachable.
    """
    admin = await _try_connect()
    if admin is None:
        pytest.skip("no Postgres reachable for reconcile integration test")
    dbname = f"acc_recon_{uuid.uuid4().hex[:10]}"
    await admin.execute(f'CREATE DATABASE "{dbname}"')
    await admin.close()
    user = os.environ.get("USER", "postgres")
    conn = await asyncpg.connect(_base_dsn(), database=dbname)
    await conn.execute(STUBS)
    await conn.execute(_forward_sql_of(MIGRATION_238))
    await conn.execute(_forward_sql_of(MIGRATION_239))
    return conn, dbname, user


async def _drop_db(conn: asyncpg.Connection, dbname: str, user: str) -> None:
    await conn.close()
    admin2 = await asyncpg.connect(_base_dsn(), database="postgres")
    try:
        await admin2.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    finally:
        await admin2.close()


@pytest.mark.asyncio
async def test_confirm_payment_full_side_effects() -> None:
    conn, dbname, user = await _fresh_db()
    try:
        # seed
        cid = await conn.fetchval("INSERT INTO clients (full_name) VALUES ('Dina B') RETURNING id")
        pid = await conn.fetchval(
            "INSERT INTO practices (client_id, payment_status) VALUES ($1, 'unpaid') RETURNING id", cid
        )
        iid = await conn.fetchval(
            "INSERT INTO invoices (practice_id, invoice_number, amount_idr) VALUES ($1, 'INV-1', 4000000) RETURNING id",
            pid,
        )
        btid = await conn.fetchval(
            """INSERT INTO bank_statements (source_format) VALUES ('csv') RETURNING id"""
        )
        txid = await conn.fetchval(
            """INSERT INTO bank_transactions (statement_id, txn_date, amount_idr, direction)
               VALUES ($1, $2, 4000000, 'credit') RETURNING id""",
            btid, date(2026, 6, 25),
        )

        # act
        result = await confirm_payment(
            conn,
            bank_txn_id=txid,
            practice_id=pid,
            invoice_id=iid,
            amount_applied_idr=4_000_000,
            new_status="paid",
            confirmed_by="asya@balizero.com",
            payment_reference="CIMB-REF-123",
            pnbp_idr=1_000_000,
            margin_idr=3_000_000,
            movement_date=date(2026, 6, 25),
        )

        # assert: practice updated
        prac = await conn.fetchrow("SELECT payment_status, paid_amount FROM practices WHERE id=$1", pid)
        assert prac["payment_status"] == "paid"
        assert int(prac["paid_amount"]) == 4_000_000

        # invoice filled
        inv = await conn.fetchrow(
            "SELECT paid_date, payment_method, payment_reference, paid_amount_idr FROM invoices WHERE id=$1", iid
        )
        assert inv["paid_date"] is not None
        assert inv["payment_reference"] == "CIMB-REF-123"
        assert int(inv["paid_amount_idr"]) == 4_000_000

        # bank txn reconciled + linked
        tx = await conn.fetchrow(
            "SELECT reconciled_status, matched_practice_id, matched_invoice_id FROM bank_transactions WHERE id=$1", txid
        )
        assert tx["reconciled_status"] == "matched"
        assert tx["matched_practice_id"] == pid
        assert tx["matched_invoice_id"] == iid

        # cashout row with decomposition
        co = await conn.fetchrow("SELECT * FROM weekly_cashout WHERE id=$1", result.cashout_id)
        assert co["type"] == "invoice_payment"
        assert co["direction"] == "in"
        assert int(co["amount_idr"]) == 4_000_000
        assert int(co["pnbp_idr"]) == 1_000_000
        assert int(co["margin_idr"]) == 3_000_000
        assert int(co["final_price_idr"]) == 4_000_000  # pnbp+urgent+rptka+margin
        assert co["linked_practice_id"] == pid

        # immutable audit row
        rl = await conn.fetchrow("SELECT * FROM reconciliation_log WHERE id=$1", result.reconciliation_log_id)
        assert rl["status_before"] == "unpaid"
        assert rl["status_after"] == "paid"
        assert int(rl["amount_applied_idr"]) == 4_000_000
        assert rl["practice_id"] == pid
    finally:
        await _drop_db(conn, dbname, user)


@pytest.mark.asyncio
async def test_confirm_payment_without_movement_date_uses_db_clock() -> None:
    """D2: when no movement_date is passed, the cashout row is written via the
    CURRENT_DATE SQL branch (reconcile_service.py else-path). week_label is NULL
    (no client-supplied date to derive an ISO week), movement_date = today's DB
    date, and the single-writer still flips practices.payment_status."""
    conn, dbname, user = await _fresh_db()
    try:
        cid = await conn.fetchval("INSERT INTO clients (full_name) VALUES ('Marina P') RETURNING id")
        pid = await conn.fetchval(
            "INSERT INTO practices (client_id, payment_status) VALUES ($1, 'unpaid') RETURNING id", cid
        )
        iid = await conn.fetchval(
            "INSERT INTO invoices (practice_id, invoice_number, amount_idr) VALUES ($1, 'INV-2', 9000000) RETURNING id",
            pid,
        )
        btid = await conn.fetchval("INSERT INTO bank_statements (source_format) VALUES ('csv') RETURNING id")
        txid = await conn.fetchval(
            """INSERT INTO bank_transactions (statement_id, txn_date, amount_idr, direction)
               VALUES ($1, $2, 9000000, 'credit') RETURNING id""",
            btid, date(2026, 6, 25),
        )

        # act — NO movement_date -> CURRENT_DATE branch
        result = await confirm_payment(
            conn,
            bank_txn_id=txid,
            practice_id=pid,
            invoice_id=iid,
            amount_applied_idr=9_000_000,
            new_status="paid",
            confirmed_by="asya@balizero.com",
            payment_reference="CIMB-REF-456",
            margin_idr=9_000_000,
            movement_date=None,
        )

        # single writer still flipped the status
        prac = await conn.fetchrow("SELECT payment_status FROM practices WHERE id=$1", pid)
        assert prac["payment_status"] == "paid"

        # cashout row landed via the CURRENT_DATE branch
        co = await conn.fetchrow(
            "SELECT movement_date, week_label, type, direction FROM weekly_cashout WHERE id=$1",
            result.cashout_id,
        )
        assert co["week_label"] is None  # no supplied date -> no ISO week label
        today = await conn.fetchval("SELECT CURRENT_DATE")
        assert co["movement_date"] == today
        assert co["type"] == "invoice_payment" and co["direction"] == "in"

        # audit row still written
        rl = await conn.fetchrow("SELECT status_before, status_after FROM reconciliation_log WHERE id=$1",
                                 result.reconciliation_log_id)
        assert rl["status_before"] == "unpaid" and rl["status_after"] == "paid"
    finally:
        await _drop_db(conn, dbname, user)


@pytest.mark.asyncio
async def test_cashbook_summary_excludes_worksheet_from_totals() -> None:
    """Worksheet rows (type='cashout_worksheet') are Asya's planning draft, not
    confirmed cash: they MUST be excluded from the headline P&L totals
    (income/net/margin) but KEPT in the by_type breakdown so she sees the pending
    mass. A confirmed invoice_payment of 4M plus a worksheet draft of 5M must
    report income=4M (not 9M), margin only from the confirmed row, while by_type
    still lists both."""
    conn, dbname, user = await _fresh_db()
    try:
        await conn.execute(
            """INSERT INTO weekly_cashout
                 (movement_date, week_label, direction, type, amount_idr,
                  pnbp_idr, margin_idr, final_price_idr)
               VALUES
                 ($1, '2026-W10', 'in', 'invoice_payment', 4000000,
                  1000000, 1000000, 4000000),
                 ($1, '2026-W10', 'in', 'cashout_worksheet', 5000000,
                  0, 2000000, 5000000)""",
            date(2026, 3, 6),
        )

        summary = await cashbook_summary(conn)

        # headline totals exclude the worksheet draft entirely
        assert summary["income_idr"] == 4_000_000   # not 9M
        assert summary["outgoing_idr"] == 0
        assert summary["net_idr"] == 4_000_000       # not 9M
        assert summary["margin_total_idr"] == 1_000_000  # only confirmed row
        assert summary["row_count"] == 1             # only confirmed row counted

        # by_type breakdown still surfaces the pending worksheet mass
        by_type = {row["type"]: row for row in summary["by_type"]}
        assert "invoice_payment" in by_type
        assert "cashout_worksheet" in by_type
        assert int(by_type["cashout_worksheet"]["total_idr"]) == 5_000_000
    finally:
        await _drop_db(conn, dbname, user)


@pytest.mark.asyncio
async def test_cashout_worksheet_type_accepted_by_constraint() -> None:
    """Migration 239 widens ck_cashout_type to accept 'cashout_worksheet', keeps
    every existing value, and still rejects anything off the list. (Contract test
    for the DROP+re-ADD; PG has no ALTER-CHECK-value so this guards the rewrite.)
    """
    conn, dbname, user = await _fresh_db()
    try:
        # new value accepted (migration 239's whole point)
        await conn.execute(
            "INSERT INTO weekly_cashout (movement_date, direction, type, amount_idr) "
            "VALUES ($1, 'in', 'cashout_worksheet', 100)",
            date(2026, 3, 6),
        )
        # a pre-existing value still accepted (the rewrite didn't drop any)
        await conn.execute(
            "INSERT INTO weekly_cashout (movement_date, direction, type, amount_idr) "
            "VALUES ($1, 'in', 'invoice_payment', 100)",
            date(2026, 3, 6),
        )
        # a bogus value is still rejected by the CHECK
        with pytest.raises(CheckViolationError):
            await conn.execute(
                "INSERT INTO weekly_cashout (movement_date, direction, type, amount_idr) "
                "VALUES ($1, 'in', 'bogus_type', 100)",
                date(2026, 3, 6),
            )
    finally:
        await _drop_db(conn, dbname, user)
