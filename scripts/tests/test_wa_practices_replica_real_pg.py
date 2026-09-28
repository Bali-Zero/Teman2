"""Opt-in real-Postgres companion to test_wa_practices_replica.py — proves
run_sync's UPSERT/re-key/rollback/FK-census semantics against an ACTUAL
Postgres, not just the in-memory fake. Skipped unless a local `pg_ctl`/
`initdb` are on PATH AND WA_PRACTICES_REPLICA_REAL_PG=1 is set; never runs by
default. Same throwaway-cluster shape as test_wa_team_promises_real_pg.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import pytest
import pytest_asyncio

_PG_CTL = shutil.which("pg_ctl")
_INITDB = shutil.which("initdb")
pytestmark = pytest.mark.skipif(
    os.environ.get("WA_PRACTICES_REPLICA_REAL_PG") != "1" or not (_PG_CTL and _INITDB),
    reason="opt-in: set WA_PRACTICES_REPLICA_REAL_PG=1 with pg_ctl/initdb on PATH",
)

if _PG_CTL and _INITDB:
    import asyncpg

    from scripts.wa_practices_replica import _DATA_COLUMNS, _PRACTICE_TYPES_DATA_COLUMNS, run_sync

_PG_COLUMN_TYPE = {
    "text": "TEXT", "numeric": "NUMERIC(12,2)", "date": "DATE",
    "timestamptz": "TIMESTAMPTZ", "jsonb": "JSONB", "boolean": "BOOLEAN",
    "integer": "INTEGER", "text[]": "TEXT[]",
}

# practice_types FIRST (practices' practice_type_code FK needs it to exist),
# with the SAME auto-named `practice_types_code_key`/`practices_uuid_key`
# constraints the real Fly/Pro schemas carry (verified 2026-09-28) — `code
# TEXT NOT NULL UNIQUE` on a table literally named `practice_types` gets
# that exact name from Postgres's own default-constraint-naming convention,
# never hand-picked here.
_SCHEMA_SQL = (
    "CREATE TABLE practice_types (\n"
    "  id SERIAL PRIMARY KEY,\n"
    "  code TEXT NOT NULL UNIQUE,\n"
    + "".join(
        f"  {col} {_PG_COLUMN_TYPE[pgtype]},\n" for col, pgtype in _PRACTICE_TYPES_DATA_COLUMNS
    ).rstrip(",\n")
    + "\n);\n"
    "CREATE TABLE clients (id SERIAL PRIMARY KEY, uuid UUID NOT NULL UNIQUE);\n"
    "CREATE TABLE practices (\n"
    "  id SERIAL PRIMARY KEY,\n"
    "  uuid UUID NOT NULL UNIQUE,\n"
    "  client_id INTEGER REFERENCES clients(id),\n"
    + "".join(
        f"  {col} {_PG_COLUMN_TYPE[pgtype]}"
        + (" REFERENCES practice_types(code)" if col == "practice_type_code" else "")
        + ",\n"
        for col, pgtype in _DATA_COLUMNS
    ).rstrip(",\n")
    + "\n);"
) if _PG_CTL and _INITDB else ""


_NON_NULL_DEFAULT_BY_TYPE = {
    # Every non-boolean/jsonb type gets a real (non-None) default too —
    # round-2 finding: the ORIGINAL version of this fixture defaulted
    # date/timestamptz/numeric/text to None, so no real-PG test here ever
    # bound an actual date/timestamptz value through asyncpg, and the same
    # class of bug _coerce_param's boolean branch had already fixed (a raw
    # `str` rejected by asyncpg's codec) shipped silently for both — caught
    # only by the Pro pre-PR dry-run against REAL Fly data, never by this
    # suite. Every branch here now exercises a real value.
    "text": "sample-text", "numeric": "123.45", "date": "2026-09-28",
    "timestamptz": "2026-09-28 12:30:00.123456+08", "integer": "42",
}


def _fly_row(uuid: str, client_uuid: str | None, **overrides) -> dict[str, str | None]:
    row: dict[str, str | None] = {"uuid": uuid, "client_uuid": client_uuid}
    for col, pgtype in _DATA_COLUMNS:
        if col in overrides:
            row[col] = overrides[col]
        elif col == "practice_type_code":
            # FK to practice_types(code) — NULL by default so every fixture
            # that isn't specifically about the FK census doesn't also have
            # to seed a matching catalog row. The FK-specific tests below
            # override this explicitly.
            row[col] = None
        elif pgtype == "boolean":
            row[col] = "true"
        elif pgtype == "jsonb":
            row[col] = "{}"
        else:
            row[col] = _NON_NULL_DEFAULT_BY_TYPE[pgtype]
    return row


def _pt_row(code: str, **overrides) -> dict[str, str | None]:
    row: dict[str, str | None] = {"code": code}
    for col, pgtype in _PRACTICE_TYPES_DATA_COLUMNS:
        if col in overrides:
            row[col] = overrides[col]
        elif pgtype == "boolean":
            row[col] = "true"
        elif pgtype == "text[]":
            row[col] = "[]"
        else:
            row[col] = _NON_NULL_DEFAULT_BY_TYPE[pgtype]
    return row


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_practices_replica_real_pg")
    sockdir = tempfile.mkdtemp(prefix="wprpg_")
    subprocess.run([_INITDB, "-D", str(data), "-U", "postgres", "--auth=trust"],
                    check=True, capture_output=True)
    subprocess.run([_PG_CTL, "-D", str(data), "-w", "-o", f"-k {sockdir} -h ''",
                     "-l", str(data / "log"), "start"], check=True, capture_output=True)
    try:
        yield sockdir
    finally:
        subprocess.run([_PG_CTL, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sockdir, ignore_errors=True)


@pytest_asyncio.fixture
async def pro_pool(pg_socket_dir):
    admin = await asyncpg.connect(host=str(pg_socket_dir), user="postgres", database="postgres")
    db = "wprpg_scratch"
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{db}"')
        await admin.execute(f'CREATE DATABASE "{db}"')
    finally:
        await admin.close()
    pool = await asyncpg.create_pool(host=str(pg_socket_dir), user="postgres",
                                      database=db, min_size=1, max_size=1)
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA_SQL)
    try:
        yield pool
    finally:
        await pool.close()
        admin2 = await asyncpg.connect(host=str(pg_socket_dir), user="postgres", database="postgres")
        try:
            await admin2.execute(f'DROP DATABASE IF EXISTS "{db}"')
        finally:
            await admin2.close()


@pytest.mark.asyncio
async def test_real_pg_insert_update_unchanged_idempotent(pro_pool):
    # A fixed literal uuid (not gen_random_uuid()) — no pgcrypto dependency,
    # and it doubles as a readable fixture.
    client_uuid = "11111111-1111-1111-1111-111111111111"
    prac_uuid = "22222222-2222-2222-2222-222222222222"
    async with pro_pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (uuid) VALUES ($1::uuid) RETURNING id", client_uuid
        )

    m1 = await run_sync(pro_pool, [_fly_row(prac_uuid, client_uuid, title="hello")], [], dry_run=False)
    assert (m1.inserted, m1.updated, m1.unchanged, m1.skipped_no_client) == (1, 0, 0, 0)
    async with pro_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT client_id, title FROM practices WHERE uuid = $1::uuid", prac_uuid)
    assert row["client_id"] == client_id
    assert row["title"] == "hello"

    m2 = await run_sync(pro_pool, [_fly_row(prac_uuid, client_uuid, title="hello")], [], dry_run=False)
    assert (m2.inserted, m2.updated, m2.unchanged) == (0, 0, 1)

    m3 = await run_sync(pro_pool, [_fly_row(prac_uuid, client_uuid, title="revised")], [], dry_run=False)
    assert (m3.inserted, m3.updated, m3.unchanged) == (0, 1, 0)
    async with pro_pool.acquire() as conn:
        title = await conn.fetchval("SELECT title FROM practices WHERE uuid = $1::uuid", prac_uuid)
    assert title == "revised"


@pytest.mark.asyncio
async def test_real_pg_null_date_and_timestamptz_columns_insert_cleanly(pro_pool):
    """The NULL branch of every typed column, proven against real PG —
    a Fly practice with no expiry_date/completion_date yet is the common
    case, not the edge case."""
    client_uuid = "12121212-1212-1212-1212-121212121212"
    prac_uuid = "13131313-1313-1313-1313-131313131313"
    async with pro_pool.acquire() as conn:
        await conn.execute("INSERT INTO clients (uuid) VALUES ($1::uuid)", client_uuid)
    row = _fly_row(prac_uuid, client_uuid, expiry_date=None, completion_date=None)
    m = await run_sync(pro_pool, [row], [], dry_run=False)
    assert m.inserted == 1
    async with pro_pool.acquire() as conn:
        stored = await conn.fetchrow(
            "SELECT expiry_date, completion_date FROM practices WHERE uuid = $1::uuid", prac_uuid
        )
    assert stored["expiry_date"] is None
    assert stored["completion_date"] is None


@pytest.mark.asyncio
async def test_real_pg_dry_run_leaves_no_trace(pro_pool):
    client_uuid = "33333333-3333-3333-3333-333333333333"
    async with pro_pool.acquire() as conn:
        await conn.execute("INSERT INTO clients (uuid) VALUES ($1::uuid)", client_uuid)

    m = await run_sync(
        pro_pool, [_fly_row("44444444-4444-4444-4444-444444444444", client_uuid)], [], dry_run=True,
    )
    assert m.inserted == 1  # PostgreSQL computed a real insert, then it was rolled back
    async with pro_pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM practices")
    assert count == 0


@pytest.mark.asyncio
async def test_real_pg_skipped_no_client_creates_no_client_row(pro_pool):
    m = await run_sync(
        pro_pool,
        [_fly_row("55555555-5555-5555-5555-555555555555", "99999999-9999-9999-9999-999999999999")],
        [],
        dry_run=False,
    )
    assert m.skipped_no_client == 1
    async with pro_pool.acquire() as conn:
        clients_count = await conn.fetchval("SELECT count(*) FROM clients")
        practices_count = await conn.fetchval("SELECT count(*) FROM practices")
    assert clients_count == 0
    assert practices_count == 0


@pytest.mark.asyncio
async def test_real_pg_pro_only_row_kept_never_deleted(pro_pool):
    async with pro_pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (uuid) VALUES ($1::uuid) RETURNING id",
            "66666666-6666-6666-6666-666666666666",
        )
        await conn.execute(
            "INSERT INTO practices (uuid, client_id) VALUES ($1::uuid, $2)",
            "77777777-7777-7777-7777-777777777777", client_id,
        )
    m = await run_sync(pro_pool, [], [], dry_run=False)
    assert m.pro_only_kept == 1
    async with pro_pool.acquire() as conn:
        still_there = await conn.fetchval(
            "SELECT count(*) FROM practices WHERE uuid = $1::uuid",
            "77777777-7777-7777-7777-777777777777",
        )
    assert still_there == 1


@pytest.mark.asyncio
async def test_real_pg_column_set_mismatch_fails_closed(pro_pool):
    """A column this replica's UPSERT expects, dropped from Pro's table —
    the write must fail loudly (PostgreSQL raises), never silently drop the
    column's data or half-write the row. `discount_reason` carries no FK, so
    this is a genuinely different failure than the FK-census guilt case
    below, and it still must abort the WHOLE run (not just skip a row) —
    only a ForeignKeyViolationError gets the per-row fail-closed treatment."""
    async with pro_pool.acquire() as conn:
        await conn.execute("ALTER TABLE practices DROP COLUMN discount_reason")
        await conn.execute(
            "INSERT INTO clients (uuid) VALUES ($1::uuid)",
            "88888888-8888-8888-8888-888888888888",
        )
    with pytest.raises(asyncpg.PostgresError):
        await run_sync(
            pro_pool,
            [_fly_row("00000000-0000-0000-0000-000000000001", "88888888-8888-8888-8888-888888888888")],
            [],
            dry_run=False,
        )
    async with pro_pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM practices")
    assert count == 0  # the failed row's own transaction rolled back — nothing partial landed


# --- FK census: practice_types replicated first (in the SAME transaction),
#     and the fail-closed net for anything that still slips through.


@pytest.mark.asyncio
async def test_real_pg_practice_type_only_on_fly_is_replicated_first_then_practice_lands(pro_pool):
    """The scenario the FK-census ruling exists for: a code that is on Fly
    but was never on Pro. practice_types syncs first, in the same
    transaction, so the practices row referencing it lands cleanly instead
    of hitting `practices_practice_type_code_fkey`."""
    client_uuid = "14141414-1414-1414-1414-141414141414"
    async with pro_pool.acquire() as conn:
        await conn.execute("INSERT INTO clients (uuid) VALUES ($1::uuid)", client_uuid)
        assert await conn.fetchval(
            "SELECT count(*) FROM practice_types WHERE code = 'visa_c1_tourism'"
        ) == 0

    prac_uuid = "15151515-1515-1515-1515-151515151515"
    m = await run_sync(
        pro_pool,
        [_fly_row(prac_uuid, client_uuid, practice_type_code="visa_c1_tourism")],
        [_pt_row("visa_c1_tourism", name="Tourist Visa C1")],
        dry_run=False,
    )
    assert m.types_inserted == 1
    assert m.inserted == 1
    assert m.skipped_fk == 0
    async with pro_pool.acquire() as conn:
        stored = await conn.fetchval(
            "SELECT practice_type_code FROM practices WHERE uuid = $1::uuid", prac_uuid
        )
    assert stored == "visa_c1_tourism"


@pytest.mark.asyncio
async def test_real_pg_practice_type_absent_on_both_sides_is_skipped_fk_not_a_crash(pro_pool):
    """Guilt case: a code absent from BOTH Fly's practice_types payload AND
    Pro's table — the FK the census exists for actually fires. It must be
    caught per row (skipped_fk), and it must NOT abort the sibling row in
    the same batch."""
    client_uuid = "16161616-1616-1616-1616-161616161616"
    async with pro_pool.acquire() as conn:
        await conn.execute("INSERT INTO clients (uuid) VALUES ($1::uuid)", client_uuid)

    bad_uuid = "17171717-1717-1717-1717-171717171717"
    good_uuid = "18181818-1818-1818-1818-181818181818"
    m = await run_sync(
        pro_pool,
        [
            _fly_row(bad_uuid, client_uuid, practice_type_code="nonexistent_code"),
            _fly_row(good_uuid, client_uuid),  # practice_type_code=None — no FK risk
        ],
        [],  # no practice_types payload at all this run
        dry_run=False,
    )
    assert m.skipped_fk == 1
    assert m.inserted == 1  # the sibling row still lands — the run did not abort
    async with pro_pool.acquire() as conn:
        bad_count = await conn.fetchval(
            "SELECT count(*) FROM practices WHERE uuid = $1::uuid", bad_uuid
        )
        good_count = await conn.fetchval(
            "SELECT count(*) FROM practices WHERE uuid = $1::uuid", good_uuid
        )
    assert bad_count == 0
    assert good_count == 1


@pytest.mark.asyncio
async def test_real_pg_practice_types_idempotent_and_updates_in_place(pro_pool):
    m1 = await run_sync(pro_pool, [], [_pt_row("visa_c1_tourism", name="Tourist Visa C1")], dry_run=False)
    assert (m1.types_inserted, m1.types_updated) == (1, 0)

    m2 = await run_sync(pro_pool, [], [_pt_row("visa_c1_tourism", name="Tourist Visa C1")], dry_run=False)
    assert (m2.types_inserted, m2.types_updated) == (0, 0)  # unchanged

    m3 = await run_sync(pro_pool, [], [_pt_row("visa_c1_tourism", name="Renamed")], dry_run=False)
    assert (m3.types_inserted, m3.types_updated) == (0, 1)
    async with pro_pool.acquire() as conn:
        name = await conn.fetchval("SELECT name FROM practice_types WHERE code = 'visa_c1_tourism'")
    assert name == "Renamed"


@pytest.mark.asyncio
async def test_real_pg_practice_types_required_documents_array_round_trips(pro_pool):
    """The one column whose bind parameter is NOT a plain `$n::type` — the
    JSON-array-text bridge (see _value_expr) must preserve NULL vs empty vs
    populated, and special characters, against a real cluster."""
    await run_sync(
        pro_pool, [],
        [
            _pt_row("code_null_docs", required_documents=None),
            _pt_row("code_empty_docs", required_documents="[]"),
            _pt_row("code_real_docs", required_documents='["passport", "photo, 4x6", "KTP\\"copy"]'),
        ],
        dry_run=False,
    )
    async with pro_pool.acquire() as conn:
        null_docs = await conn.fetchval(
            "SELECT required_documents FROM practice_types WHERE code = 'code_null_docs'"
        )
        empty_docs = await conn.fetchval(
            "SELECT required_documents FROM practice_types WHERE code = 'code_empty_docs'"
        )
        real_docs = await conn.fetchval(
            "SELECT required_documents FROM practice_types WHERE code = 'code_real_docs'"
        )
    assert null_docs is None
    assert empty_docs == []
    assert real_docs == ["passport", "photo, 4x6", 'KTP"copy']
