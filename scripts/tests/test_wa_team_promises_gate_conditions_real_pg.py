"""T3 gate conditions C1 (real-PG half), C2, C3 — opt-in real-Postgres tests
for PR #7342's PASS-WITH-CONDITIONS follow-ups (see the PR's own gate
comment). Same opt-in gate as test_wa_team_promises_real_pg.py: skipped
unless `pg_ctl`/`initdb` are on PATH AND WA_TEAM_PROMISES_REAL_PG=1. Spins up
its OWN throwaway cluster (own module-scoped fixture, mirroring the sibling
file) and isolates each test in its own logical database inside that one
cluster via CREATE DATABASE/DROP DATABASE — cheaper than a fresh initdb per
test, and each test starts from a scenario it built itself, not shared state.

C1 (real-PG half): on an EMPTY db, the full pg_attribute catalog for both
tables equals `_REQUIRED_COLUMNS` exactly (26 rows) — the static parser in
test_wa_team_promises_sql_crosscheck.py proves the SQL FILE matches the
contract; this proves what actually LANDS in Postgres matches it too.

C2: for each of 6 guilt shapes (core-column wrong type, a domain hiding
behind a column name, NOT NULL missing, each of the two unique indexes in
the wrong shape, and duplicate rows that make the unique index build itself
fail) run_init_schema leaves the catalog byte-for-byte where it started —
proven by a snapshot of pg_attribute + pg_index + pg_constraint before and
after, not just "an exception was raised". A mutation-proof test then loads
a SCRATCH copy of the module (never the real file — never edited-then-`git
checkout`ed back) with verification moved OUTSIDE the transaction, and shows
the exact same assertions go RED against it: the DDL survives the mismatch.

C3: loads the LITERAL migrations_v2/200 team_promises CREATE (the one Fly
shape, frozen there — see the SQL file's own header comment) against an
otherwise-empty db (stubbing the two FK targets) and asserts it is REJECTED
fail-closed at `team_promises.resolved`, not silently upgraded — and that
the rejection leaves the mig-200 shape exactly as it found it.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

_PG_CTL = shutil.which("pg_ctl")
_INITDB = shutil.which("initdb")
pytestmark = pytest.mark.skipif(
    os.environ.get("WA_TEAM_PROMISES_REAL_PG") != "1" or not (_PG_CTL and _INITDB),
    reason="opt-in: set WA_TEAM_PROMISES_REAL_PG=1 with pg_ctl/initdb on PATH",
)

if _PG_CTL and _INITDB:
    import asyncpg

    import scripts.wa_team_promises as wa_team_promises
    from scripts.wa_team_promises import (
        _REQUIRED_COLUMNS,
        SchemaMismatchError,
        run_init_schema,
    )

_MIGRATION_200_PATH = (
    Path(__file__).resolve().parents[2]
    / "apps" / "backend-rag" / "backend" / "db" / "migrations_v2"
    / "200_wa_copilot_infrastructure.sql"
)


# --- shared cluster (own, per this file — mirrors test_wa_team_promises_real_pg.py) ---


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_gate_c2c3")
    sockdir = tempfile.mkdtemp(prefix="watppgc_")  # short — unix socket path limit
    subprocess.run([_INITDB, "-D", str(data), "-U", "postgres", "--auth=trust"],
                    check=True, capture_output=True)
    subprocess.run([_PG_CTL, "-D", str(data), "-w", "-o", f"-k {sockdir} -h ''",
                     "-l", str(data / "log"), "start"], check=True, capture_output=True)
    try:
        yield sockdir
    finally:
        subprocess.run([_PG_CTL, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sockdir, ignore_errors=True)


@asynccontextmanager
async def _fresh_database(sockdir, name: str):
    """Isolates one test in its own logical database inside the shared
    cluster: CREATE on entry, connect, DROP on exit (best-effort — a failed
    drop never masks the test's own assertion result)."""
    admin = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    pool = await asyncpg.create_pool(host=str(sockdir), user="postgres", database=name,
                                      min_size=1, max_size=1)
    try:
        yield pool
    finally:
        await pool.close()
        admin2 = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
        try:
            await admin2.execute(f'DROP DATABASE IF EXISTS "{name}"')
        finally:
            await admin2.close()


async def _catalog_snapshot(conn) -> dict:
    """pg_attribute + pg_index + pg_constraint for whichever of the two
    tables currently exist, plus each table's existence flag — the whole
    catalog surface run_init_schema's DDL could possibly touch."""
    tp_oid = await conn.fetchval("SELECT to_regclass('public.team_promises')::oid")
    tpc_oid = await conn.fetchval("SELECT to_regclass('public.team_promise_candidates')::oid")
    oids = [oid for oid in (tp_oid, tpc_oid) if oid is not None] or [0]
    attrs = await conn.fetch(
        "SELECT attrelid, attname, atttypid, atttypmod, attnotnull FROM pg_attribute "
        "WHERE attrelid = ANY($1::oid[]) AND attnum > 0 AND NOT attisdropped "
        "ORDER BY attrelid, attname", oids)
    idx = await conn.fetch(
        "SELECT indrelid, indexrelid, indisunique, indisvalid, indnkeyatts, indkey::text "
        "FROM pg_index WHERE indrelid = ANY($1::oid[]) ORDER BY indexrelid", oids)
    cons = await conn.fetch(
        "SELECT conrelid, conname, contype, pg_get_constraintdef(oid) AS def "
        "FROM pg_constraint WHERE conrelid = ANY($1::oid[]) ORDER BY conname", oids)
    return {
        "tp_exists": tp_oid is not None,
        "tpc_exists": tpc_oid is not None,
        "attrs": tuple(tuple(r.values()) for r in attrs),
        "idx": tuple(tuple(r.values()) for r in idx),
        "cons": tuple(tuple(r.values()) for r in cons),
    }


# === C1 (real-PG half): full catalog equals _REQUIRED_COLUMNS, 26 rows ===


@pytest.mark.asyncio
async def test_c1_real_pg_catalog_matches_required_columns_exactly(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c1_catalog") as pool:
        await run_init_schema(pool)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT c.relname AS table_name, a.attname, "
                "format_type(a.atttypid, a.atttypmod) AS pg_type, a.attnotnull "
                "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname IN ('team_promises', 'team_promise_candidates') "
                "AND a.attnum > 0 AND NOT a.attisdropped"
            )
    actual = {(r["table_name"], r["attname"], r["pg_type"], r["attnotnull"]) for r in rows}
    expected = {
        (table, name, pg_type, notnull)
        for table, cols in _REQUIRED_COLUMNS.items()
        for name, pg_type, notnull in cols
    }
    assert len(expected) == 26
    assert actual == expected


# === C2: real-PG rollback per guilt case, from a candidates-absent baseline ===

_CORE_COMPLETE_ALTER_COLUMNS = (
    "    thread_key TEXT,\n"
    "    team_member_email TEXT,\n"
    "    extractor_version TEXT,\n"
    "    resolution_kind TEXT\n"
)

_CORE_TYPE_MISMATCH_DDL = f"""
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_NOTNULL_MISMATCH_DDL = """
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_DOMAIN_MISMATCH_DDL = """
CREATE DOMAIN gate_c2_domain_text AS TEXT;
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    thread_key gate_c2_domain_text
);
"""

_TP_INDEX_SHAPE_MISMATCH_DDL = f"""
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
{_CORE_COMPLETE_ALTER_COLUMNS.rstrip(chr(10))}
);
CREATE UNIQUE INDEX uix_team_promises_msg_type ON team_promises (message_id);
"""

_TPC_INDEX_SHAPE_MISMATCH_DDL = f"""
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
{_CORE_COMPLETE_ALTER_COLUMNS.rstrip(chr(10))}
);
CREATE UNIQUE INDEX uix_team_promises_msg_type ON team_promises (message_id, promise_type);
CREATE TABLE team_promise_candidates (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    clause_idx INTEGER NOT NULL,
    clause_hash TEXT NOT NULL,
    promise_type TEXT NOT NULL,
    cue TEXT,
    due_at_hint TEXT,
    status TEXT NOT NULL DEFAULT 'unjudged'
        CHECK (status IN ('unjudged', 'judged_true', 'judged_false', 'quarantined')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uix_team_promise_candidates_msg_clause
    ON team_promise_candidates (message_id);
"""

_DUPLICATE_ROWS_DDL = f"""
CREATE TABLE team_promises (
    promise_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    conversation_id BIGINT,
    client_id BIGINT,
    promise_text TEXT NOT NULL,
    promise_type TEXT,
    due_at TIMESTAMPTZ,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
{_CORE_COMPLETE_ALTER_COLUMNS.rstrip(chr(10))}
);
INSERT INTO team_promises (message_id, promise_text, promise_type) VALUES
    (42, 'first', 'reply'),
    (42, 'second', 'reply');
"""


@pytest.mark.asyncio
async def test_guilt_core_type_mismatch_rolls_back_and_never_creates_candidates(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_core_type") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_CORE_TYPE_MISMATCH_DDL)
            before = await _catalog_snapshot(conn)

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.message_id"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after
        assert after["tpc_exists"] is False


@pytest.mark.asyncio
async def test_guilt_domain_mismatch_rolls_back_and_never_creates_candidates(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_domain") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_DOMAIN_MISMATCH_DDL)
            before = await _catalog_snapshot(conn)

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.thread_key"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after
        assert after["tpc_exists"] is False


@pytest.mark.asyncio
async def test_guilt_notnull_mismatch_rolls_back_and_never_creates_candidates(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_notnull") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_NOTNULL_MISMATCH_DDL)
            before = await _catalog_snapshot(conn)

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.resolved"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after
        assert after["tpc_exists"] is False


@pytest.mark.asyncio
async def test_guilt_tp_index_shape_mismatch_rolls_back_and_never_creates_candidates(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_tp_index") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_TP_INDEX_SHAPE_MISMATCH_DDL)
            before = await _catalog_snapshot(conn)

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "uix_team_promises_msg_type"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after
        assert after["tpc_exists"] is False  # DDL would have created it — rollback undid that too


@pytest.mark.asyncio
async def test_guilt_tpc_index_shape_mismatch_rolls_back_leaving_bad_index_untouched(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_tpc_index") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_TPC_INDEX_SHAPE_MISMATCH_DDL)
            before = await _catalog_snapshot(conn)
        assert before["tpc_exists"] is True  # pre-existing here, unlike the other 5 cases

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "uix_team_promise_candidates_msg_clause"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after


@pytest.mark.asyncio
async def test_guilt_duplicate_rows_abort_index_creation_and_never_creates_candidates(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "gate_c2_dup_rows") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_DUPLICATE_ROWS_DDL)
            before = await _catalog_snapshot(conn)

        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await run_init_schema(pool)

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
        assert before == after
        assert after["tpc_exists"] is False


# --- mutation proof: verify moved OUTSIDE the transaction must turn C2 RED ---

_ORIGINAL_RUN_INIT_SCHEMA_BLOCK = '''async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
            for table in _TABLES_TO_VERIFY:
                await verify_required_columns(conn, table)
            for table, index, columns in _UNIQUE_INDEXES_TO_VERIFY:
                await verify_unique_index(conn, table, index, columns)
'''

_MUTATED_RUN_INIT_SCHEMA_BLOCK = '''async def run_init_schema(pool: asyncpg.Pool) -> None:
    ddl = _SQL_PATH.read_text()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(ddl)
        for table in _TABLES_TO_VERIFY:
            await verify_required_columns(conn, table)
        for table, index, columns in _UNIQUE_INDEXES_TO_VERIFY:
            await verify_unique_index(conn, table, index, columns)
'''


def _write_mutated_module(tmp_path: Path) -> Path:
    """A SCRATCH copy of scripts/wa_team_promises.py with verification moved
    outside `conn.transaction()` — the real file on disk is never touched
    (never edited, never `git checkout`ed back)."""
    src = Path(wa_team_promises.__file__).read_text()
    assert _ORIGINAL_RUN_INIT_SCHEMA_BLOCK in src, (
        "run_init_schema's source drifted from this test's expected block — "
        "update _ORIGINAL_RUN_INIT_SCHEMA_BLOCK/_MUTATED_RUN_INIT_SCHEMA_BLOCK together"
    )
    mutated_src = src.replace(_ORIGINAL_RUN_INIT_SCHEMA_BLOCK, _MUTATED_RUN_INIT_SCHEMA_BLOCK)
    dest = tmp_path / "wa_team_promises_mutated_notxn.py"
    dest.write_text(mutated_src)
    return dest


def _import_mutated(dest_path: Path):
    spec = importlib.util.spec_from_file_location("wa_team_promises_mutated_notxn", dest_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._SQL_PATH = wa_team_promises._SQL_PATH  # the scratch copy's own __file__-relative
    return mod                                  # path is wrong; point it at the real SQL


@pytest.mark.asyncio
async def test_mutation_proof_verify_outside_transaction_lets_the_ddl_survive(pg_socket_dir, tmp_path):
    mutated = _import_mutated(_write_mutated_module(tmp_path))

    async with _fresh_database(pg_socket_dir, "gate_c2_mutation_proof") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_CORE_TYPE_MISMATCH_DDL)

        with pytest.raises(mutated.SchemaMismatchError) as exc_info:
            await mutated.run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.message_id"

        async with pool.acquire() as conn:
            # The real contract (test_guilt_core_type_mismatch_... above)
            # asserts candidates stays absent and thread_key never lands.
            # Here — verify moved OUTSIDE the transaction — is the opposite:
            # the DDL committed before the mismatch was ever noticed. If our
            # C2 assertions were run against this mutated copy, they would
            # go RED; that is what this test exists to prove stays true.
            tpc_committed = await conn.fetchval(
                "SELECT to_regclass('public.team_promise_candidates') IS NOT NULL")
            thread_key_committed = await conn.fetchval(
                "SELECT count(*) FROM pg_attribute WHERE attrelid = "
                "to_regclass('public.team_promises')::oid AND attname = 'thread_key'"
            ) == 1
    assert tpc_committed is True
    assert thread_key_committed is True


# === C3: the literal migrations_v2/200 shape is rejected, not upgraded ===

_MIG200_STUB_FKS = """
CREATE TABLE clients (id BIGSERIAL PRIMARY KEY);
CREATE TABLE whatsapp_conversations (conversation_id BIGSERIAL PRIMARY KEY);
"""


def _extract_migration_200_team_promises_block() -> str:
    sql = _MIGRATION_200_PATH.read_text()
    m = re.search(r"-- E\. team_promises\n(.*?)\n-- F\.", sql, re.DOTALL)
    assert m, (
        f"{_MIGRATION_200_PATH}: '-- E. team_promises ... -- F.' section not found — "
        "the migration file drifted, update this test's extraction anchor"
    )
    return m.group(1)


@pytest.mark.asyncio
async def test_c3_migration_200_literal_team_promises_shape_is_rejected_not_upgraded(pg_socket_dir):
    mig200_block = _extract_migration_200_team_promises_block()
    assert "CREATE TABLE IF NOT EXISTS team_promises" in mig200_block
    assert "REFERENCES clients(id)" in mig200_block
    assert "REFERENCES whatsapp_conversations(conversation_id)" in mig200_block

    async with _fresh_database(pg_socket_dir, "gate_c3_mig200") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_MIG200_STUB_FKS)
            await conn.execute(mig200_block)
            before = await _catalog_snapshot(conn)
            resolved_notnull_before = await conn.fetchval(
                "SELECT attnotnull FROM pg_attribute WHERE attrelid = "
                "to_regclass('public.team_promises')::oid AND attname = 'resolved'")
        assert resolved_notnull_before is False  # the mig-200 shape: nullable, not upgraded

        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.resolved"

        async with pool.acquire() as conn:
            after = await _catalog_snapshot(conn)
            thread_key_present = await conn.fetchval(
                "SELECT count(*) FROM pg_attribute WHERE attrelid = "
                "to_regclass('public.team_promises')::oid AND attname = 'thread_key'")
        assert before == after
        assert after["tpc_exists"] is False
        assert thread_key_present == 0  # the round-2 upgrade columns never survive the rollback
