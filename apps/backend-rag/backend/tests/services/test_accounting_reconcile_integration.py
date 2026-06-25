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

from backend.services.accounting.reconcile_service import confirm_payment

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db" / "migrations_v2" / "238_accounting_asya.sql"
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


def _forward_sql() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    # apply only the part before the ROLLBACK marker (mirrors the runner)
    return re.split(r"^-- === ROLLBACK ===\s*$", text, maxsplit=1, flags=re.MULTILINE)[0]


async def _try_connect() -> asyncpg.Connection | None:
    dsn = os.environ.get("TEST_DATABASE_URL")
    candidates = [dsn] if dsn else []
    user = os.environ.get("USER", "postgres")
    candidates += [f"postgresql://{user}@localhost:5432/postgres", "postgresql://localhost:5432/postgres"]
    for c in candidates:
        if not c:
            continue
        try:
            return await asyncpg.connect(c)
        except Exception:
            continue
    return None


async def _fresh_db() -> tuple[asyncpg.Connection, str, str]:
    """Create an ephemeral DB with the migration applied + minimal stubs.

    Returns (conn, dbname, user). Caller is responsible for teardown via
    _drop_db(). Skips the test if no local Postgres is reachable.
    """
    admin = await _try_connect()
    if admin is None:
        pytest.skip("no local Postgres reachable for reconcile integration test")
    dbname = f"acc_recon_{uuid.uuid4().hex[:10]}"
    await admin.execute(f'CREATE DATABASE "{dbname}"')
    await admin.close()
    user = os.environ.get("USER", "postgres")
    conn = await asyncpg.connect(f"postgresql://{user}@localhost:5432/{dbname}")
    await conn.execute(STUBS)
    await conn.execute(_forward_sql())
    return conn, dbname, user


async def _drop_db(conn: asyncpg.Connection, dbname: str, user: str) -> None:
    await conn.close()
    admin2 = await asyncpg.connect(f"postgresql://{user}@localhost:5432/postgres")
    try:
        await admin2.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    finally:
        await admin2.close()


@pytest.mark.asyncio
async def test_confirm_payment_full_side_effects() -> None:
    admin = await _try_connect()
    if admin is None:
        pytest.skip("no local Postgres reachable for reconcile integration test")

    dbname = f"acc_recon_{uuid.uuid4().hex[:10]}"
    await admin.execute(f'CREATE DATABASE "{dbname}"')
    await admin.close()

    user = os.environ.get("USER", "postgres")
    conn = await asyncpg.connect(f"postgresql://{user}@localhost:5432/{dbname}")
    try:
        await conn.execute(STUBS)
        await conn.execute(_forward_sql())

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
        await conn.close()
        admin2 = await asyncpg.connect(f"postgresql://{user}@localhost:5432/postgres")
        try:
            await admin2.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        finally:
            await admin2.close()


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
