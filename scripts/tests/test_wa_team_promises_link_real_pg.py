"""T3 promise gate — P2 (the linker), opt-in real-Postgres half.
Skipped unless a local `pg_ctl`/`initdb` are on PATH AND
WA_TEAM_PROMISES_REAL_PG=1 is set — same gate and throwaway-cluster pattern
as test_wa_team_promises_judge_real_pg.py.

Covers what a fake pool cannot prove: the guarded UPDATEs really never
overwrite a value that is already set, are idempotent, leave a promise
alone when its message is gone or carries no value, and the insert done by
the judge (`_apply_true`) copies `client_id` / `team_member_email` from the
message row in the same statement. All fixtures are synthetic: numeric ids
and `member-N@example.invalid` addresses only.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

_PG_CTL = shutil.which("pg_ctl")
_INITDB = shutil.which("initdb")
pytestmark = pytest.mark.skipif(
    os.environ.get("WA_TEAM_PROMISES_REAL_PG") != "1" or not (_PG_CTL and _INITDB),
    reason="opt-in: set WA_TEAM_PROMISES_REAL_PG=1 with pg_ctl/initdb on PATH",
)

if _PG_CTL and _INITDB:
    import asyncpg

    import scripts.wa_team_promises as wtp
    from scripts.wa_team_promises import _apply_true, _hash_clause, _split_clauses, run_init_schema

CREATED = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_link_real_pg")
    sockdir = tempfile.mkdtemp(prefix="watppgl_")
    subprocess.run([_INITDB, "-D", str(data), "-U", "postgres", "--auth=trust"],
                    check=True, capture_output=True)
    subprocess.run([_PG_CTL, "-D", str(data), "-w", "-o", f"-k {sockdir} -h ''",
                     "-l", str(data / "log"), "start"], check=True, capture_output=True)
    try:
        yield sockdir
    finally:
        subprocess.run([_PG_CTL, "-D", str(data), "-m", "immediate", "stop"], capture_output=True, check=False)
        shutil.rmtree(sockdir, ignore_errors=True)


@asynccontextmanager
async def _fresh_database(sockdir, name: str):
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


# The mirror columns the linker reads: client_id and team_member_email exist
# on the real table (mig 173 + the mirror's own client resolution). `clients`
# and `team_members` are the two roster tables the audit counts against.
_DDL = """
CREATE TABLE whatsapp_message_context (
    id                BIGINT PRIMARY KEY,
    direction         TEXT,
    body              TEXT,
    message_text      TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id         BIGINT,
    team_member_email TEXT
);
CREATE TABLE clients (id BIGINT PRIMARY KEY);
CREATE TABLE team_members (email TEXT PRIMARY KEY);
"""


async def _setup(pool) -> None:
    await run_init_schema(pool)
    async with pool.acquire() as conn:
        await conn.execute(_DDL)


async def _wmc(pool, msg_id: int, *, client_id=None, email=None, body="I will send it tomorrow") -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whatsapp_message_context "
            "(id, direction, body, created_at, client_id, team_member_email) "
            "VALUES ($1, 'outbound', $2, $3, $4, $5)",
            msg_id, body, CREATED, client_id, email,
        )


async def _promise(pool, msg_id: int, *, client_id=None, email=None, ptype="send") -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO team_promises (message_id, promise_text, promise_type, due_at, client_id, "
            "team_member_email) VALUES ($1, 'x', $2, $3, $4, $5) RETURNING promise_id",
            msg_id, ptype, CREATED, client_id, email,
        )


async def _row(pool, promise_id: int) -> tuple:
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT client_id, team_member_email FROM team_promises WHERE promise_id = $1", promise_id
        )
    return (r["client_id"], r["team_member_email"])


@pytest.mark.asyncio
async def test_link_fills_both_fields_and_normalises_the_email(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_fill") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=11, email="  Member-1@Example.INVALID ")
        pid = await _promise(pool, 1)
        metrics = await wtp.run_link(pool, dry_run=False)
        assert (metrics.client_linked, metrics.member_linked) == (1, 1)
        assert await _row(pool, pid) == (11, "member-1@example.invalid")


@pytest.mark.asyncio
async def test_link_is_idempotent(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_idem") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")
        pid = await _promise(pool, 1)
        first = await wtp.run_link(pool, dry_run=False)
        second = await wtp.run_link(pool, dry_run=False)
        assert (first.client_linked, first.member_linked) == (1, 1)
        assert (second.client_linked, second.member_linked) == (0, 0)
        assert await _row(pool, pid) == (11, "member-1@example.invalid")


@pytest.mark.asyncio
async def test_link_never_overwrites_a_value_that_is_already_set(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_guard") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")
        await _wmc(pool, 2, client_id=22, email="member-2@example.invalid")
        await _wmc(pool, 3, client_id=33, email="member-3@example.invalid")
        both_set = await _promise(pool, 1, client_id=999, email="kept-1@example.invalid")
        only_client = await _promise(pool, 2, client_id=998)
        only_member = await _promise(pool, 3, email="kept-3@example.invalid")
        metrics = await wtp.run_link(pool, dry_run=False)
        assert await _row(pool, both_set) == (999, "kept-1@example.invalid")
        assert await _row(pool, only_client) == (998, "member-2@example.invalid")
        assert await _row(pool, only_member) == (33, "kept-3@example.invalid")
        assert (metrics.client_linked, metrics.member_linked) == (1, 1)


@pytest.mark.asyncio
async def test_link_leaves_a_promise_alone_when_the_message_has_no_value_or_is_gone(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_missing") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=None, email="member-1@example.invalid")
        await _wmc(pool, 2, client_id=22, email="   ")
        no_client = await _promise(pool, 1)
        blank_member = await _promise(pool, 2)
        orphan = await _promise(pool, 404)  # message 404 was never inserted
        metrics = await wtp.run_link(pool, dry_run=False)
        assert await _row(pool, no_client) == (None, "member-1@example.invalid")
        assert await _row(pool, blank_member) == (22, None)  # blank -> NULL, never ''
        assert await _row(pool, orphan) == (None, None)
        assert (metrics.client_linked, metrics.member_linked) == (1, 1)


@pytest.mark.asyncio
async def test_link_dry_run_reports_the_counts_and_writes_nothing(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_dry") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")
        await _wmc(pool, 2, client_id=None, email="member-2@example.invalid")
        a = await _promise(pool, 1)
        b = await _promise(pool, 2)
        metrics = await wtp.run_link(pool, dry_run=True)
        assert (metrics.client_linked, metrics.member_linked) == (1, 2)
        assert await _row(pool, a) == (None, None)
        assert await _row(pool, b) == (None, None)


@pytest.mark.asyncio
async def test_judge_insert_copies_client_and_member_from_the_message(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_insert") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        clause = _split_clauses(body)[0]
        await _wmc(pool, 1, client_id=11, email="Member-1@example.invalid", body=body)
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, promise_type) "
                "VALUES (1, 0, $1, 'send') RETURNING id", _hash_clause(clause),
            )
        outcome = await _apply_true(pool, cid, _hash_clause(clause), message_id=1, clause_idx=0,
                                     promise_type="send", due_at_hint=None, dry_run=False)
        assert outcome == "true"
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT client_id, team_member_email FROM team_promises WHERE message_id = 1")
        assert (row["client_id"], row["team_member_email"]) == (11, "member-1@example.invalid")


@pytest.mark.asyncio
async def test_link_audit_counts_only_and_flags_conflicts(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_audit") as pool:
        await _setup(pool)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO clients (id) VALUES (11), (22)")
            await conn.execute("INSERT INTO team_members (email) VALUES ('member-1@example.invalid')")
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")   # fully known
        await _wmc(pool, 2, client_id=77, email="stranger@example.invalid")   # client + member unknown
        await _wmc(pool, 3, client_id=22, email="member-1@example.invalid")   # promise disagrees
        await _wmc(pool, 4, client_id=11, email="member-1@example.invalid")   # same address, other case
        await _promise(pool, 1)
        await _promise(pool, 2)
        await _promise(pool, 3, client_id=11)
        await _promise(pool, 4, client_id=11, email=" MEMBER-1@example.invalid ")
        audit = await wtp.audit_link_counts(pool)
        assert audit == {
            "total": 4, "client_null": 2, "member_null": 3,
            "linkable_client": 2, "linkable_member": 3,
            "client_not_in_clients": 1, "member_not_in_roster": 1,
            "conflicts": 1,
        }


@pytest.mark.asyncio
async def test_judge_with_a_missing_message_row_inserts_nothing_and_is_not_counted_true(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_insert_gone") as pool:
        await _setup(pool)
        clause = _split_clauses("I will send it tomorrow")[0]
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, promise_type) "
                "VALUES (404, 0, $1, 'send') RETURNING id", _hash_clause(clause),
            )
        outcome = await _apply_true(pool, cid, _hash_clause(clause), message_id=404, clause_idx=0,
                                     promise_type="send", due_at_hint=None, dry_run=False)
        assert outcome == "superseded"
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM team_promises") == 0


@pytest.mark.asyncio
async def test_judge_insert_leaves_client_null_and_blank_email_null(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_insert_null") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        clause = _split_clauses(body)[0]
        await _wmc(pool, 1, client_id=None, email="   ", body=body)
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, promise_type) "
                "VALUES (1, 0, $1, 'send') RETURNING id", _hash_clause(clause),
            )
        assert await _apply_true(pool, cid, _hash_clause(clause), message_id=1, clause_idx=0,
                                  promise_type="send", due_at_hint=None, dry_run=False) == "true"
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT client_id, team_member_email FROM team_promises WHERE message_id = 1")
        assert (row["client_id"], row["team_member_email"]) == (None, None)


@pytest.mark.asyncio
async def test_audit_counts_unknown_values_on_already_linked_promises(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_audit_linked") as pool:
        await _setup(pool)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO clients (id) VALUES (11)")
            await conn.execute("INSERT INTO team_members (email) VALUES ('member-1@example.invalid')")
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")
        await _wmc(pool, 2, client_id=None, email=None)
        await _promise(pool, 1, client_id=11, email="member-1@example.invalid")   # both known
        await _promise(pool, 2, client_id=77, email="stranger@example.invalid")   # linked, both unknown
        audit = await wtp.audit_link_counts(pool)
        assert audit["client_null"] == 0 and audit["member_null"] == 0
        assert audit["client_not_in_clients"] == 1
        assert audit["member_not_in_roster"] == 1


@pytest.mark.asyncio
async def test_judge_insert_binds_its_own_message_when_several_messages_exist(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_insert_many") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        clause = _split_clauses(body)[0]
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid", body=body)
        await _wmc(pool, 2, client_id=22, email="member-2@example.invalid", body=body)
        await _wmc(pool, 3, client_id=33, email="member-3@example.invalid", body=body)
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, promise_type) "
                "VALUES (3, 0, $1, 'send') RETURNING id", _hash_clause(clause),
            )
        assert await _apply_true(pool, cid, _hash_clause(clause), message_id=3, clause_idx=0,
                                  promise_type="send", due_at_hint=None, dry_run=False) == "true"
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT message_id, client_id, team_member_email FROM team_promises")
        assert [(r["message_id"], r["client_id"], r["team_member_email"]) for r in rows] == [
            (3, 33, "member-3@example.invalid")
        ]


@pytest.mark.asyncio
async def test_link_dry_run_ignores_a_target_that_is_already_set(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "link_dry_set") as pool:
        await _setup(pool)
        await _wmc(pool, 1, client_id=11, email="member-1@example.invalid")
        await _wmc(pool, 2, client_id=22, email="member-2@example.invalid")
        await _promise(pool, 1, client_id=999, email="kept-1@example.invalid")
        await _promise(pool, 2, client_id=998)
        metrics = await wtp.run_link(pool, dry_run=True)
        assert (metrics.client_linked, metrics.member_linked) == (0, 1)
