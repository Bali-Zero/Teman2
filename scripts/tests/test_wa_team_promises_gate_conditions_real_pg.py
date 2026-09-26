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
fail — the last of these relabeled *PG statement atomicity*, since it proves
Postgres's own per-statement guarantee, not run_init_schema's wrapping
transaction) run_init_schema leaves the catalog byte-for-byte where it
started — proven by a snapshot of pg_attribute + pg_index (+ each index's
own `pg_get_indexdef`) + pg_constraint + each table's BIGSERIAL sequence
DEFINITION (name + `pg_sequences` row, Round-1: not just an existence
boolean) before and after, not just "an exception was raised". The
candidates-index guilt case's pre-existing table now omits `cue` so
run_init_schema's own ADD COLUMN IF NOT EXISTS is a genuine mutation there
too, not a no-op the rollback never has to undo. A mutation-proof test then
loads a SCRATCH copy of the module (never the real file — never
edited-then-`git checkout`ed back) with verification moved OUTSIDE the
transaction, and shows the exact same assertions go RED against it: the DDL
survives the mismatch.

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
import sys
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


async def _sequence_snapshot(conn, table_oid, table: str, serial_column: str):
    """`table`'s `serial_column` sequence — its OWN NAME plus its full
    `pg_sequences` definition row, not just an existence boolean (Round-1
    Codex nit: a boolean can't tell a live sequence apart from one that got
    renamed, retyped, or silently orphaned by a bad rollback — only a
    definition can). `None` if the table doesn't exist or the column has no
    owned sequence (`pg_get_serial_sequence` errors on a relation that
    doesn't exist, hence the early return)."""
    if table_oid is None:
        return None
    seq_name = await conn.fetchval(
        "SELECT pg_get_serial_sequence($1, $2)", f"public.{table}", serial_column
    )
    if seq_name is None:
        return None
    row = await conn.fetchrow(
        "SELECT schemaname, sequencename, data_type, start_value, min_value, "
        "max_value, increment_by, cycle FROM pg_sequences "
        "WHERE schemaname || '.' || sequencename = $1", seq_name,
    )
    return (seq_name,) + (tuple(row.values()) if row is not None else (None,))


async def _catalog_snapshot(conn) -> dict:
    """pg_attribute + pg_index (+ each index's pg_get_indexdef) +
    pg_constraint for whichever of the two tables currently exist, plus each
    table's existence flag and its BIGSERIAL PRIMARY KEY's sequence
    DEFINITION (C2 fix (c), Round-1: definitions, not existence booleans) —
    the whole catalog surface run_init_schema's DDL could possibly touch."""
    tp_oid = await conn.fetchval("SELECT to_regclass('public.team_promises')::oid")
    tpc_oid = await conn.fetchval("SELECT to_regclass('public.team_promise_candidates')::oid")
    oids = [oid for oid in (tp_oid, tpc_oid) if oid is not None] or [0]
    attrs = await conn.fetch(
        "SELECT attrelid, attname, atttypid, atttypmod, attnotnull FROM pg_attribute "
        "WHERE attrelid = ANY($1::oid[]) AND attnum > 0 AND NOT attisdropped "
        "ORDER BY attrelid, attname", oids)
    idx = await conn.fetch(
        "SELECT indrelid, indexrelid, indisunique, indisvalid, indnkeyatts, indkey::text, "
        "pg_get_indexdef(indexrelid) AS indexdef "
        "FROM pg_index WHERE indrelid = ANY($1::oid[]) ORDER BY indexrelid", oids)
    cons = await conn.fetch(
        "SELECT conrelid, conname, contype, pg_get_constraintdef(oid) AS def "
        "FROM pg_constraint WHERE conrelid = ANY($1::oid[]) ORDER BY conname", oids)
    return {
        "tp_exists": tp_oid is not None,
        "tpc_exists": tpc_oid is not None,
        "tp_seq": await _sequence_snapshot(conn, tp_oid, "team_promises", "promise_id"),
        "tpc_seq": await _sequence_snapshot(conn, tpc_oid, "team_promise_candidates", "id"),
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
    # 26 -> 27: PR #7367 (T3 PR-2 rework, spec addendum A2/B1) added
    # team_promise_candidates.revised_at — bumping the pin, not deriving it
    # from _REQUIRED_COLUMNS itself, keeps this a real sanity check rather
    # than a tautology against the same source the test is meant to verify.
    assert len(expected) == 27
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
# C2 fix (a): `cue` is deliberately ABSENT above (unlike every other
# non-core column) so team_promises.sql's own
# `ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS cue TEXT;`
# is a genuine mutation, not a no-op — without this gap, EVERY statement
# run_init_schema executes here would already be true, so before==after
# would hold trivially even if the transaction's rollback were broken.

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
async def test_pg_statement_atomicity_duplicate_rows_abort_index_creation_and_never_creates_candidates(
    pg_socket_dir,
):
    """C2 fix (b), relabeled from *_guilt_*: `CREATE UNIQUE INDEX` failing
    on a duplicate (message_id, promise_type) pair is undone by POSTGRES'S
    OWN per-statement atomicity, not by run_init_schema's wrapping
    transaction — the failing statement never reaches a second one, so
    there is nothing for OUR rollback to undo here. Kept in the C2 suite
    because it is still a scenario the caller must survive with the catalog
    byte-for-byte unchanged and candidates absent, just proven by PG's own
    guarantee rather than ours."""
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
    # REWORK (PR #7367 B1): must be registered in sys.modules BEFORE
    # exec_module runs — `@dataclass(slots=True) ScanMetrics` in the mutated
    # source resolves its own module via `sys.modules[cls.__module__]` while
    # building the slotted replacement class, so an unregistered module
    # raises `AttributeError: 'NoneType' object has no attribute '__dict__'`
    # instead of ever reaching the mutation this test means to prove RED.
    sys.modules[spec.name] = mod
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
