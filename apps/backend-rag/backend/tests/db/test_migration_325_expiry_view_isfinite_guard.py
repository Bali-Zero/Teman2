"""Migration 325: `client_expiry_alerts_view` survives an infinite expiry date.

Every DB case runs inside `db_tx` (rolled back at teardown) in a private
schema holding minimal copies of the three source tables, so it behaves the
same on CI's fresh database (which has no `client_family_members`) and on a
developer machine. The PRE-325 view is rebuilt from the migration's own text
by stripping exactly the two guards: if the guards were anything more than
`isfinite`, the "same rows as before" case would see the difference.
"""

from __future__ import annotations

import re
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_manager import _extract_rollback_sql

pytestmark = pytest.mark.integration

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "325_expiry_view_isfinite_guard.sql"
)

# `pg_attribute` of the PROD view, read 2026-10-12 (names only, no data).
_LIVE_COLUMNS = [
    "entity_type",
    "entity_id",
    "entity_name",
    "client_id",
    "client_name",
    "document_type",
    "expiry_date",
    "days_until_expiry",
    "alert_color",
    "assigned_to",
]

_CONSTRAINTS = {
    ("clients", "clients_passport_expiry_finite"),
    ("client_family_members", "client_family_members_passport_expiry_finite"),
    ("client_family_members", "client_family_members_visa_expiry_finite"),
    ("documents", "documents_expiry_date_finite"),
}

_SCHEMA = """
CREATE SCHEMA m325_t;
SET LOCAL search_path TO m325_t;
CREATE TABLE clients (
    id SERIAL PRIMARY KEY, full_name VARCHAR(255) NOT NULL, passport_expiry DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'active', assigned_to VARCHAR(255));
CREATE TABLE client_family_members (
    id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
    full_name VARCHAR(255) NOT NULL, passport_expiry DATE, visa_expiry DATE);
CREATE TABLE documents (
    id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
    document_type VARCHAR(100) NOT NULL, expiry_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', is_archived BOOLEAN DEFAULT FALSE);
INSERT INTO clients (id, full_name, passport_expiry, status) VALUES
    (1, 'Client A', CURRENT_DATE + 30, 'active'),
    (2, 'Client B', CURRENT_DATE - 5, 'active'),
    (3, 'Client C', CURRENT_DATE + 400, 'inactive');
SELECT setval(pg_get_serial_sequence('clients', 'id'), 100);
INSERT INTO client_family_members (client_id, full_name, passport_expiry, visa_expiry) VALUES
    (1, 'Member A', CURRENT_DATE + 200, NULL),
    (2, 'Member B', NULL, CURRENT_DATE + 10);
INSERT INTO documents (client_id, document_type, expiry_date, status) VALUES
    (1, 'kitas', CURRENT_DATE + 60, 'approved'),
    (2, 'npwp', CURRENT_DATE + 90, 'rejected');
"""

_ROWS = "SELECT * FROM client_expiry_alerts_view ORDER BY entity_type, entity_id, document_type"


def _forward() -> str:
    text = _MIGRATION.read_text(encoding="utf-8")
    forward = text.split("-- === ROLLBACK ===")[0].strip()
    assert forward and _extract_rollback_sql(text)
    return forward


def _view_text() -> str:
    match = re.search(r"\$view\$(.*?)\$view\$", _forward(), re.S)
    assert match, "325 must carry its view DDL between $view$ quotes"
    return match.group(1).strip()


def _pre_325_view() -> str:
    """The live pre-325 definition: the same text minus both guards."""
    text = re.sub(r" AND isfinite\([\w.]+\)", "", _view_text())
    text = re.sub(
        r"CASE\s+WHEN isfinite\(([\w.]+)\) THEN \1 - CURRENT_DATE\s+ELSE NULL::integer\s+END",
        r"\1 - CURRENT_DATE",
        text,
    )
    assert "isfinite" not in text
    return text


def test_view_keeps_the_live_column_list_in_order() -> None:
    select_list = _view_text().split("UNION ALL")[0]
    aliases = re.findall(r"\bAS (\w+)(?=,?\s*$)", select_list, re.M)
    # `c.assigned_to` is the one un-aliased column, last in every branch.
    assert aliases + ["assigned_to"] == _LIVE_COLUMNS
    assert _view_text().count("UNION ALL") == 3


def test_forward_adds_four_not_valid_finite_checks() -> None:
    forward = _forward()
    for _, con in _CONSTRAINTS:
        assert f"'{con}'" in forward
    assert "CHECK (%I IS NULL OR isfinite(%I)) NOT VALID" in forward
    code = "\n".join(ln for ln in forward.splitlines() if not ln.strip().startswith("--"))
    assert "VALIDATE CONSTRAINT" not in code


@pytest.mark.asyncio
async def test_infinite_row_breaks_the_old_view_and_not_the_new_one(
    db_tx: asyncpg.Connection,
) -> None:
    await db_tx.execute(_SCHEMA)
    await db_tx.execute(_pre_325_view())
    before = [dict(r) for r in await db_tx.fetch(_ROWS)]
    assert len(before) == 5  # A, B, Member A passport, Member B visa, kitas

    await db_tx.execute(
        "INSERT INTO clients (id, full_name, passport_expiry) VALUES (9, 'Client Inf', '-infinity')"
    )
    await db_tx.execute(
        "INSERT INTO documents (client_id, document_type, expiry_date) VALUES (1, 'kitap', 'infinity')"
    )
    with pytest.raises(asyncpg.DataError, match="infinite"):
        async with db_tx.transaction():
            await db_tx.fetch(_ROWS)

    await db_tx.execute(_forward())
    await db_tx.execute(_forward())  # re-run is a no-op

    after = [dict(r) for r in await db_tx.fetch(_ROWS)]
    assert after == before  # finite rows identical, infinite ones excluded
    pushed = await db_tx.fetchval(
        "SELECT count(*) FROM client_expiry_alerts_view WHERE days_until_expiry <= 60"
    )
    assert pushed == 4

    cons = await db_tx.fetch(
        "SELECT conrelid::regclass::text AS tbl, conname, convalidated FROM pg_constraint "
        "WHERE conname LIKE '%\\_finite' AND connamespace = 'm325_t'::regnamespace"
    )
    assert {(c["tbl"], c["conname"]) for c in cons} == _CONSTRAINTS
    assert not any(c["convalidated"] for c in cons)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("insert", "value"),
    [
        (
            "INSERT INTO clients (full_name, passport_expiry) VALUES ('X', $1::text::date)",
            "-infinity",
        ),
        (
            "INSERT INTO client_family_members (client_id, full_name, passport_expiry) "
            "VALUES (1, 'X', $1::text::date)",
            "infinity",
        ),
        (
            "INSERT INTO client_family_members (client_id, full_name, visa_expiry) "
            "VALUES (1, 'X', $1::text::date)",
            "-infinity",
        ),
        (
            "INSERT INTO documents (client_id, document_type, expiry_date) VALUES (1, 'x', $1::text::date)",
            "infinity",
        ),
    ],
)
async def test_new_infinite_dates_are_rejected_and_null_still_admitted(
    db_tx: asyncpg.Connection, insert: str, value: str
) -> None:
    await db_tx.execute(_SCHEMA)
    await db_tx.execute(_forward())
    await db_tx.execute(insert, None)
    with pytest.raises(asyncpg.CheckViolationError):
        await db_tx.execute(insert, value)
