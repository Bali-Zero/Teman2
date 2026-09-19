"""Migration 319, EXECUTED against a real PostgreSQL — not parsed.

Why this file exists, in the words of the review that demanded it
(adversarial seat, 2026-09-16): "Every migration parity test passes with
inverted constraints — I changed both `IN` predicates to `NOT IN` in memory
and all six parity tests still passed. That SQL rejects the rewritten rows and
aborts deployment."

That is exact. A test that READS the .sql can only prove the file says what
the constant says; it cannot see that the statement does the opposite of what
it must. So this test runs the migration through the SAME path the Fly
`release_command` uses — `split_migration_sql()` for the forward/rollback cut
(the 2026-04-19 scar: the runner used to execute BOTH halves in one
transaction) — over a throwaway database holding the pre-319 schema and rows,
and then asks PostgreSQL itself what is now accepted and what is refused.

No production data: the fixture creates its own database, seeds SYNTHETIC
rows, and drops it afterwards.

Skips (rather than fails) when no PostgreSQL is reachable, which is the case
in CI today — declared, not hidden: in CI this file proves nothing, and the
parity tests next to it are what run there. It is the fleet machines (Pro,
Mini and M5 all run Postgres 17) and anyone touching this migration who get
the executable proof, with one command and no setup.
"""

from __future__ import annotations

import os
import uuid

import pytest

asyncpg = pytest.importorskip("asyncpg")

from pathlib import Path  # noqa: E402

from backend.db.migration_base import split_migration_sql  # noqa: E402

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "319_align_tax_consultant_allowlist_to_team_members.sql"
)

ADMIN_DSN = os.environ.get(
    "TAX_ALLOWLIST_TEST_ADMIN_DSN",
    f"postgresql://{os.environ.get('USER', 'postgres')}@localhost:5432/postgres",
)

# Derived, never typed: `test_tax_consultant_ghost_address_guard.py` fails the
# build the moment either retired address is hard-coded anywhere under
# backend/ outside its four named settled-history files, and a test fixture is
# not one of them. Deriving is also the stronger form — if the alias map ever
# changes, this proof follows it instead of silently testing a dead string.
from backend.app.core.constants import TaxConsultantConstants  # noqa: E402

_REAL_BY_LEGACY = dict(TaxConsultantConstants.LEGACY_ALIASES)
REAL_VERONIKA = "tax@balizero.com"
REAL_FAISHA = "faysha.tax@balizero.com"
GHOST_VERONIKA = next(k for k, v in _REAL_BY_LEGACY.items() if v == REAL_VERONIKA)
GHOST_FAISHA = next(k for k, v in _REAL_BY_LEGACY.items() if v == REAL_FAISHA)

PRE_319_SCHEMA = f"""
CREATE TABLE clients (
  id SERIAL PRIMARY KEY,
  full_name VARCHAR(255) NOT NULL,
  tax_consultant VARCHAR(64),
  CONSTRAINT clients_tax_consultant_check CHECK (
    tax_consultant IS NULL OR tax_consultant IN (
      '{GHOST_VERONIKA}','kadek.tax@balizero.com','dewaayu.tax@balizero.com',
      'angel.tax@balizero.com','{GHOST_FAISHA}')
  )
);
CREATE TABLE lkpm_reports (
  id SERIAL PRIMARY KEY,
  client_id INT,
  lkpm_assigned_to VARCHAR(64),
  CONSTRAINT lkpm_reports_assigned_to_check CHECK (
    lkpm_assigned_to IS NULL OR lkpm_assigned_to IN (
      '{GHOST_VERONIKA}','kadek.tax@balizero.com','dewaayu.tax@balizero.com',
      'angel.tax@balizero.com','{GHOST_FAISHA}','krisna@balizero.com')
  )
);
CREATE TABLE team_members (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  avatar VARCHAR(255)
);
INSERT INTO clients (full_name, tax_consultant) VALUES
  ('Synthetic Alpha Ltd', '{GHOST_VERONIKA}'),
  ('Synthetic Bravo Ltd', '{GHOST_VERONIKA}'),
  ('Synthetic Charlie Ltd', 'kadek.tax@balizero.com'),
  ('Synthetic Delta Ltd', NULL);
INSERT INTO lkpm_reports (client_id, lkpm_assigned_to) VALUES
  (1,'{GHOST_FAISHA}'),(2,'{GHOST_FAISHA}'),(3,'krisna@balizero.com'),(4,NULL);
INSERT INTO team_members (email, name, avatar) VALUES
  ('{REAL_VERONIKA}','Veronika','/static/team/veronika.jpg'),
  ('angel.tax@balizero.com','Angel','/static/team/angel.jpg'),
  ('{REAL_FAISHA}','Faisha','/static/team/faisha.jpg'),
  ('sahira@balizero.com','Sahira','/static/team/sahira.jpg');
"""


@pytest.fixture
async def migrated_db():
    """A throwaway database carrying the pre-319 schema, with migration 319's
    FORWARD half applied through the real split. Dropped afterwards."""
    try:
        admin = await asyncpg.connect(ADMIN_DSN, timeout=3)
    except Exception as exc:  # no server, no role, no socket
        pytest.skip(f"no reachable PostgreSQL for the executable migration proof: {exc}")

    name = f"tax_allowlist_t_{uuid.uuid4().hex[:10]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    dsn = ADMIN_DSN.rsplit("/", 1)[0] + "/" + name
    try:
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(PRE_319_SCHEMA)
            forward, rollback = split_migration_sql(MIGRATION.read_text(encoding="utf-8"))
            assert rollback, "319 must carry a rollback section"
            async with conn.transaction():
                await conn.execute(forward)
            yield conn, rollback
        finally:
            await conn.close()
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


async def _accepts(conn, table: str, value: str) -> bool:
    """Does the CHECK currently in force accept this value? Always rolled back."""
    tx = conn.transaction()
    await tx.start()
    try:
        if table == "clients":
            await conn.execute(
                "INSERT INTO clients (full_name, tax_consultant) VALUES ($1,$2)",
                "Synthetic Probe",
                value,
            )
        else:
            await conn.execute(
                "INSERT INTO lkpm_reports (client_id, lkpm_assigned_to) VALUES (99,$1)", value
            )
        return True
    except asyncpg.exceptions.CheckViolationError:
        return False
    finally:
        await tx.rollback()


@pytest.mark.asyncio
async def test_forward_moves_every_ghost_row_onto_the_real_address(migrated_db):
    conn, _ = migrated_db
    assert await conn.fetchval(
        "SELECT count(*) FROM clients WHERE tax_consultant = $1", GHOST_VERONIKA
    ) == 0
    assert await conn.fetchval(
        "SELECT count(*) FROM clients WHERE tax_consultant = $1", REAL_VERONIKA
    ) == 2
    assert await conn.fetchval(
        "SELECT count(*) FROM lkpm_reports WHERE lkpm_assigned_to = $1", GHOST_FAISHA
    ) == 0
    assert await conn.fetchval(
        "SELECT count(*) FROM lkpm_reports WHERE lkpm_assigned_to = $1", REAL_FAISHA
    ) == 2


@pytest.mark.asyncio
async def test_forward_leaves_untouched_rows_alone(migrated_db):
    conn, _ = migrated_db
    assert await conn.fetchval(
        "SELECT count(*) FROM clients WHERE tax_consultant = 'kadek.tax@balizero.com'"
    ) == 1
    assert await conn.fetchval("SELECT count(*) FROM clients WHERE tax_consultant IS NULL") == 1
    assert await conn.fetchval(
        "SELECT count(*) FROM lkpm_reports WHERE lkpm_assigned_to = 'krisna@balizero.com'"
    ) == 1


@pytest.mark.asyncio
async def test_the_new_check_accepts_every_real_address(migrated_db):
    """The defect this migration exists to cure: two REAL consultants could
    not be written at all. If this is ever red again, the tax team is locked
    out of their own portal."""
    conn, _ = migrated_db
    for address in (
        REAL_VERONIKA,
        REAL_FAISHA,
        "angel.tax@balizero.com",
        "kadek.tax@balizero.com",
        "dewaayu.tax@balizero.com",
    ):
        assert await _accepts(conn, "clients", address), address
    assert await _accepts(conn, "lkpm_reports", "krisna@balizero.com")


@pytest.mark.asyncio
async def test_the_new_check_still_refuses_a_stranger(migrated_db):
    conn, _ = migrated_db
    assert not await _accepts(conn, "clients", "intruder@balizero.com")
    assert not await _accepts(conn, "lkpm_reports", "intruder@balizero.com")


@pytest.mark.asyncio
async def test_expand_keeps_the_retired_aliases_writable(migrated_db):
    """The EXPAND decision, executable: code that predates this deploy still
    submits the retired aliases, and `release_command` puts this migration in
    force BEFORE that code is replaced. If this turns red, the rolling deploy
    window (and any image-only rollback after it) becomes a write outage for
    the tax team."""
    conn, _ = migrated_db
    assert await _accepts(conn, "clients", GHOST_VERONIKA)
    assert await _accepts(conn, "clients", GHOST_FAISHA)
    assert await _accepts(conn, "lkpm_reports", GHOST_FAISHA)


@pytest.mark.asyncio
async def test_forward_nulls_only_the_two_deleted_portraits(migrated_db):
    conn, _ = migrated_db
    assert await conn.fetchval("SELECT avatar FROM team_members WHERE email = $1", REAL_FAISHA) is None
    assert await conn.fetchval(
        "SELECT avatar FROM team_members WHERE email = 'sahira@balizero.com'"
    ) is None
    assert await conn.fetchval(
        "SELECT avatar FROM team_members WHERE email = 'angel.tax@balizero.com'"
    ) == "/static/team/angel.jpg"


@pytest.mark.asyncio
async def test_forward_is_idempotent_on_rerun(migrated_db):
    """The two UPDATEs must match zero rows the second time. A migration that
    is not re-runnable turns a retried deploy into a second incident."""
    conn, _ = migrated_db
    forward, _ = split_migration_sql(MIGRATION.read_text(encoding="utf-8"))
    async with conn.transaction():
        await conn.execute(forward)
    assert await conn.fetchval(
        "SELECT count(*) FROM clients WHERE tax_consultant = $1", REAL_VERONIKA
    ) == 2


@pytest.mark.asyncio
async def test_rollback_restores_the_previous_state(migrated_db):
    conn, rollback = migrated_db
    async with conn.transaction():
        await conn.execute(rollback)
    assert await conn.fetchval(
        "SELECT count(*) FROM clients WHERE tax_consultant = $1", GHOST_VERONIKA
    ) == 2
    assert await conn.fetchval(
        "SELECT count(*) FROM lkpm_reports WHERE lkpm_assigned_to = $1", GHOST_FAISHA
    ) == 2
    # the pre-319 CHECK is back in force: the real address is refused again
    assert not await _accepts(conn, "clients", REAL_VERONIKA)
