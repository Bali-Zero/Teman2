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
