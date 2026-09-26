"""Opt-in real-Postgres companion to test_wa_team_promises.py — proves
run_init_schema's DDL/rollback/catalog-verification against an ACTUAL
Postgres, not just fakes. Skipped unless a local `pg_ctl`/`initdb` are on
PATH AND WA_TEAM_PROMISES_REAL_PG=1 is set; never runs by default. Spins up
a throwaway cluster, torn down at the end either way.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import pytest

_PG_CTL = shutil.which("pg_ctl")
_INITDB = shutil.which("initdb")
pytestmark = pytest.mark.skipif(
    os.environ.get("WA_TEAM_PROMISES_REAL_PG") != "1" or not (_PG_CTL and _INITDB),
    reason="opt-in: set WA_TEAM_PROMISES_REAL_PG=1 with pg_ctl/initdb on PATH",
)

if _PG_CTL and _INITDB:
    import asyncpg

    from scripts.wa_team_promises import SchemaMismatchError, run_init_schema
    from scripts.tests.test_wa_team_promises_sql_crosscheck import (
        UnrecognizedSqlShapeError,
        parse_declared_columns,
    )


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_real_pg")
    # unix sockets have a kernel ~103-byte path limit pytest's own nested
    # tmp_path blows through — only a short /tmp dir fits (scratchpad too).
    sockdir = tempfile.mkdtemp(prefix="watppg_")
    subprocess.run([_INITDB, "-D", str(data), "-U", "postgres", "--auth=trust"],
                    check=True, capture_output=True)
    subprocess.run([_PG_CTL, "-D", str(data), "-w", "-o", f"-k {sockdir} -h ''",
                     "-l", str(data / "log"), "start"], check=True, capture_output=True)
    try:
        yield sockdir
    finally:
        subprocess.run([_PG_CTL, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sockdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_real_pg_init_schema_complete_idempotent_domain_then_index_guilt(pg_socket_dir):
    pool = await asyncpg.create_pool(host=str(pg_socket_dir), user="postgres",
                                      database="postgres", min_size=1, max_size=1)
    try:
        await run_init_schema(pool)
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT to_regclass('public.team_promises')") is not None
            assert await conn.fetchval("SELECT to_regclass('public.team_promise_candidates')") is not None
            assert await conn.fetchval(
                "SELECT count(*) FROM pg_attribute WHERE attrelid = to_regclass('public.team_promises')"
                "::oid AND attname = 'thread_key' AND atttypid = 'text'::regtype") == 1
        await run_init_schema(pool)  # idempotent re-run must not raise

        # round-2 #2: a domain over text must NOT pass as if it were plain text.
        async with pool.acquire() as conn:
            await conn.execute("CREATE DOMAIN my_text_domain AS TEXT")
            await conn.execute("ALTER TABLE team_promises ALTER COLUMN thread_key "
                                "TYPE my_text_domain USING thread_key::my_text_domain")
        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "team_promises.thread_key"
        async with pool.acquire() as conn:
            # rolled back — the column is still the domain, not silently "fixed".
            assert await conn.fetchval(
                "SELECT atttypid = 'text'::regtype FROM pg_attribute WHERE attrelid = "
                "to_regclass('public.team_promises')::oid AND attname = 'thread_key'") is False
            await conn.execute("ALTER TABLE team_promises ALTER COLUMN thread_key "
                                "TYPE text USING thread_key::text")
            await conn.execute("DROP DOMAIN my_text_domain")

        # round-1 #4: an incompatible SECOND-index-shaped mismatch, columns untouched.
        async with pool.acquire() as conn:
            await conn.execute("DROP INDEX uix_team_promise_candidates_msg_clause")
            await conn.execute("CREATE UNIQUE INDEX uix_team_promise_candidates_msg_clause "
                                "ON team_promise_candidates (message_id)")
        with pytest.raises(SchemaMismatchError) as exc_info:
            await run_init_schema(pool)
        assert exc_info.value.identifier == "uix_team_promise_candidates_msg_clause"
    finally:
        await pool.close()


# --- Round 2 (condition C-A, PR #7395's PASS-WITH-CONDITIONS gate): a
# subset of the R1-R8 residuals re-proven directly against a REAL cluster
# (not just PG-truth captured by hand into the static unit test above) —
# picked because PG truth is cheap to assert here: a SchemaMismatchError-
# style catalog read, or PG refusing the DDL outright. Each is its own
# scratch database inside the SAME cluster (never the module's own
# `postgres` database, which the sibling test above owns) so a bad DDL can
# never touch that test's tables. ---


async def _fresh_scratch_db(sockdir, name: str, sql: str):
    """Runs `sql` against a brand-new, empty scratch database, returns the
    pg_attribute catalog (atttypid-only — this reads PG's OWN acceptance,
    independent of whichever normalization the static parser chooses) for
    every user table, or the exception PG raised. Drops the database either
    way."""
    admin = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(host=str(sockdir), user="postgres", database=name)
    try:
        try:
            async with conn.transaction():
                await conn.execute(sql)
        except Exception as e:  # PG refused the DDL outright
            return f"PG-ERROR {type(e).__name__}"
        rows = await conn.fetch(
            "SELECT c.relname AS t, a.attname AS n, format_type(a.atttypid, NULL) AS ty, "
            "a.attnotnull AS nn FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_namespace s ON s.oid = c.relnamespace WHERE s.nspname = 'public' "
            "AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped"
        )
        out: dict[str, set[tuple[str, str, bool]]] = {}
        for r in rows:
            out.setdefault(r["t"], set()).add((r["n"], r["ty"], r["nn"]))
        return out
    finally:
        await conn.close()
        admin2 = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
        try:
            await admin2.execute(f'DROP DATABASE IF EXISTS "{name}"')
        finally:
            await admin2.close()


_ROUND2_CA_REAL_PG_CASES = [
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT NOT NULL);\n"
        "CREATE TABLE IF NOT EXISTS t (a TEXT NOT NULL, b TEXT);",
        {"t": {("a", "text", True)}},
        id="R1-repeated-create-table-if-not-exists-is-a-no-op-in-PG",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "ALTER TABLE other.t ADD COLUMN IF NOT EXISTS b TEXT NOT NULL;",
        "PG-ERROR InvalidSchemaNameError",  # schema "other" does not exist
        id="R4-non-public-schema-qualifier-errors-in-PG-on-a-fresh-db",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TIMESTAMPTZ(3), d VARCHAR(10) NOT NULL);",
        {"t": {("c", "timestamp with time zone", False), ("d", "character varying", True)}},
        id="R5-PG-accepts-a-typmod-the-static-parser-must-still-reject",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (c TEXT,);",
        "PG-ERROR PostgresSyntaxError",
        id="R6a-trailing-comma-is-a-real-PG-syntax-error",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (thread_Key TEXT);",
        {"t": {("thread_Key", "text", False)}},
        id="R7-PG-keeps-a-non-ascii-identifier-byte-for-byte",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("sql, expected", _ROUND2_CA_REAL_PG_CASES)
async def test_round2_ca_residual_matches_real_pg_catalog(pg_socket_dir, sql, expected, request):
    case_id = request.node.callspec.id
    db = f"ca_{case_id[:2].lower()}_{id(sql) % 100000}"
    truth = await _fresh_scratch_db(pg_socket_dir, db, sql)
    if isinstance(expected, str):
        assert isinstance(truth, str) and truth.startswith(expected)
        # REWORK S5(c): this branch used to return here, never calling the
        # static parser at all — R4/R6a proved only that PG errors, not
        # that OUR parser also does. Both are cases the static parser must
        # reject too (a non-`public` schema qualifier, a trailing comma).
        with pytest.raises(UnrecognizedSqlShapeError):
            parse_declared_columns(sql)
        return
    assert truth == expected
    if case_id.startswith(("R5", "R7")):
        # R5's own residual (REWORK S1) and R7's are the same shape: PG
        # accepts and stores this SQL (truth above), but the static parser
        # must reject it outright rather than silently normalize it to
        # something PG's own catalog would never produce for the same
        # input (R5: a dropped typmod; R7: a non-ASCII identifier folded
        # by Python but not by PG).
        with pytest.raises(UnrecognizedSqlShapeError):
            parse_declared_columns(sql)
        return
    # Everywhere else, the static parser (no DB at all) must land on the
    # SAME column set PG itself produced.
    assert parse_declared_columns(sql) == expected


# --- S6 (carried-forward condition on PR #7413's re-gate,
# pull/7413#issuecomment-5847256465): pre-existing, silent only in the
# static layer — measured here against the SAME throwaway PG17 cluster. ---

_S6_REAL_PG_CASES = [
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a SMALLSERIAL, b FLOAT, c CHAR);",
        {"t": {("a", "smallint", True), ("b", "double precision", False), ("c", "character", False)}},
        id="S6c-smallserial-float-char-type-fallback",
    ),
    pytest.param(
        f"CREATE TABLE IF NOT EXISTS t ({'a' * 64} TEXT);",
        {"t": {("a" * 63, "text", False)}},
        id="S6b-64-byte-identifier-is-silently-truncated-by-pg-not-rejected",
    ),
    pytest.param(
        "CREATE TABLE IF NOT EXISTS t (a TEXT);\n"
        "CREATE UNIQUE INDEX IF NOT EXISTS conflict_slot ON t (a);\n"
        "CREATE TABLE IF NOT EXISTS conflict_slot (bogus_col TEXT NOT NULL);",
        {"t": {("a", "text", False)}},
        id="S6a-index-table-namespace-skips-the-later-create-table",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("sql, expected", _S6_REAL_PG_CASES)
async def test_s6_residual_matches_real_pg_catalog(pg_socket_dir, sql, expected, request):
    case_id = request.node.callspec.id
    db = f"s6_{case_id[:4].lower()}_{id(sql) % 100000}"
    truth = await _fresh_scratch_db(pg_socket_dir, db, sql)
    assert truth == expected
    if case_id.startswith("S6b"):
        # S6(b): PG accepts and silently truncates (truth above) — the
        # static parser must reject outright rather than risk a collision
        # it cannot detect, same as R5/R7's precedent.
        with pytest.raises(UnrecognizedSqlShapeError):
            parse_declared_columns(sql)
        return
    # S6a/S6c: the static parser (no DB at all) must land on the SAME
    # column set PG itself produced.
    assert parse_declared_columns(sql) == expected
