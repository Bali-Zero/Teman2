"""T3 promise gate — P2 resolver, opt-in real-Postgres half. Skipped unless a
local `pg_ctl`/`initdb` are on PATH AND WA_TEAM_PROMISES_REAL_PG=1 — same gate
and throwaway-cluster pattern as test_wa_team_promises_link_real_pg.py.

Covers what a fake pool cannot prove: the thread join, the after-the-promise /
right-direction / window rules in SQL, the fill-only guard on the write,
idempotence, dry-run parity, and the digest consumer. Synthetic fixtures only:
numeric ids, `line-N` / `peer-N` placeholders and example.invalid addresses.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

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
    from scripts.wa_team_promises import run_init_schema

T0 = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
NOW = T0 + timedelta(days=30)


def _h(hours):
    return T0 + timedelta(hours=hours)


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_resolve_real_pg")
    sockdir = tempfile.mkdtemp(prefix="watppr_")
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


_DDL = """
CREATE TABLE whatsapp_message_context (
    id                BIGINT PRIMARY KEY,
    direction         TEXT,
    body              TEXT,
    message_text      TEXT,
    media_type        TEXT,
    message_date      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    team_member_phone TEXT,
    counterpart_phone TEXT,
    counterpart_lid   TEXT,
    group_jid         TEXT,
    client_id         BIGINT,
    team_member_email TEXT
);
CREATE TABLE team_members (email TEXT PRIMARY KEY, name TEXT);
"""


async def _setup(pool) -> None:
    await run_init_schema(pool)
    async with pool.acquire() as conn:
        await conn.execute(_DDL)


async def _msg(pool, msg_id, direction, at, *, text=None, media=None, line="line-1", peer="peer-1",
               lid=None, group=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whatsapp_message_context (id, direction, body, media_type, message_date, "
            "team_member_phone, counterpart_phone, counterpart_lid, group_jid) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            msg_id, direction, text, media, at, line, peer, lid, group,
        )


async def _promise_on(pool, msg_id, *, ptype="send", due=None, email=None, resolved=False,
                      resolved_at=None, by=None, kind=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO team_promises (message_id, promise_text, promise_type, due_at, "
            "team_member_email, resolved, resolved_at, resolved_by_message_id, resolution_kind) "
            "VALUES ($1, 'x', $2, $3, $4, $5, $6, $7, $8) RETURNING promise_id",
            msg_id, ptype, due or _h(24), email, resolved, resolved_at, by, kind,
        )


async def _promise(pool, msg_id=1, **kw) -> int:
    await _msg(pool, msg_id, "outbound", T0, text="I will send it tomorrow")
    return await _promise_on(pool, msg_id, **kw)


async def _state(pool, promise_id):
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT resolved, resolved_at, resolved_by_message_id, resolution_kind "
            "FROM team_promises WHERE promise_id = $1", promise_id)
    return (r["resolved"], r["resolved_at"], r["resolved_by_message_id"], r["resolution_kind"])


OPEN = (False, None, None, None)


@pytest.mark.asyncio
async def test_media_in_the_same_thread_resolves_and_fills_all_four_fields(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_media") as pool:
        await _setup(pool)
        pid = await _promise(pool)
        await _msg(pool, 2, "outbound", _h(3), media="document")
        m = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert (m.scanned, m.media_sent, m.team_confirmed, m.client_ack) == (1, 1, 0, 0)
        assert await _state(pool, pid) == (True, _h(3), 2, "media_sent")


@pytest.mark.asyncio
async def test_strongest_kind_wins_and_earliest_within_it(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_strength") as pool:
        await _setup(pool)
        pid = await _promise(pool)
        await _msg(pool, 2, "inbound", _h(1), text="ok thanks")
        await _msg(pool, 3, "outbound", _h(2), text="already sent")
        await _msg(pool, 5, "outbound", _h(5), media="image")
        await _msg(pool, 4, "outbound", _h(4), media="document")
        await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert await _state(pool, pid) == (True, _h(4), 4, "media_sent")


@pytest.mark.asyncio
async def test_team_confirmed_needs_the_same_type_in_past_tense(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_confirmed") as pool:
        await _setup(pool)
        pid = await _promise(pool)
        await _msg(pool, 2, "outbound", _h(1), text="I will send it tomorrow")   # future
        await _msg(pool, 3, "outbound", _h(2), text="gia controllato")            # other type
        assert (await wtp.run_resolve(pool, dry_run=False, now=NOW)).no_evidence == 1
        assert await _state(pool, pid) == OPEN
        await _msg(pool, 4, "outbound", _h(3), text="already sent")
        await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert await _state(pool, pid) == (True, _h(3), 4, "team_confirmed")


@pytest.mark.asyncio
async def test_guilt_cases_leave_the_promise_open(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_guilt") as pool:
        await _setup(pool)
        pid = await _promise(pool)
        await _msg(pool, 2, "outbound", _h(-2), media="document")                       # before the promise
        await _msg(pool, 3, "outbound", _h(2), media="document", peer="peer-2")         # another thread
        await _msg(pool, 4, "outbound", _h(2), media="document", line="line-2")         # another line
        await _msg(pool, 5, "inbound", _h(2), media="document")                         # wrong direction
        await _msg(pool, 6, "inbound", _h(2), text="already sent")                      # wrong direction
        await _msg(pool, 7, "outbound", _h(2), text="thanks")                           # ack from the team
        await _msg(pool, 8, "outbound", _h(2), media="sticker")                         # not a deliverable
        await _msg(pool, 9, "outbound", T0 + wtp._RESOLVE_WINDOW + timedelta(hours=1), media="document")
        m = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert (m.media_sent, m.team_confirmed, m.client_ack, m.no_evidence) == (0, 0, 0, 1)
        assert await _state(pool, pid) == OPEN


@pytest.mark.asyncio
async def test_a_set_value_is_never_overwritten_and_the_row_is_not_even_selected(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_guard") as pool:
        await _setup(pool)
        await _msg(pool, 1, "outbound", T0, text="I will send it tomorrow")
        await _msg(pool, 2, "outbound", T0 + timedelta(hours=1), text="x")
        await _msg(pool, 3, "outbound", T0 + timedelta(hours=2), media="document")
        done = await _promise_on(pool, 1, resolved=True, resolved_at=_h(9), by=999, kind="team_confirmed")
        half = await _promise_on(pool, 2, resolved=False, resolved_at=_h(9))
        kind_only = await _promise_on(pool, 3, kind="client_ack")
        m = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert m.scanned == 0
        assert await _state(pool, done) == (True, _h(9), 999, "team_confirmed")
        assert await _state(pool, half) == (False, _h(9), None, None)
        assert await _state(pool, kind_only) == (False, None, None, "client_ack")
        async with pool.acquire() as conn:
            assert await conn.fetchrow(wtp._RESOLVE_UPDATE_SQL, done, _h(1), 2, "media_sent") is None
        assert await _state(pool, done) == (True, _h(9), 999, "team_confirmed")


@pytest.mark.asyncio
async def test_second_run_resolves_nothing(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_idem") as pool:
        await _setup(pool)
        await _promise(pool)
        await _msg(pool, 2, "outbound", _h(3), media="document")
        first = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        second = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert first.media_sent == 1
        assert (second.scanned, second.media_sent, second.team_confirmed, second.client_ack) == (0, 0, 0, 0)


@pytest.mark.asyncio
async def test_dry_run_counts_what_a_real_run_resolves_and_writes_nothing(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_dry") as pool:
        await _setup(pool)
        a = await _promise(pool, 1)
        b = await _promise(pool, 10, ptype="send")
        await _msg(pool, 2, "outbound", _h(3), media="document")
        await _msg(pool, 11, "outbound", _h(2), text="already sent", peer="peer-9")
        await _msg(pool, 12, "outbound", _h(3), text="already sent")
        dry = await wtp.run_resolve(pool, dry_run=True, now=NOW)
        assert await _state(pool, a) == OPEN and await _state(pool, b) == OPEN
        real = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert dataclasses_tuple(dry) == dataclasses_tuple(real)


def dataclasses_tuple(m):
    return (m.scanned, m.unthreadable, m.media_sent, m.team_confirmed, m.client_ack, m.no_evidence, m.raced)


@pytest.mark.asyncio
async def test_a_group_thread_is_keyed_by_group_and_a_lid_only_peer_still_threads(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_threads") as pool:
        await _setup(pool)
        await _msg(pool, 1, "outbound", T0, text="I will send it tomorrow", peer=None, group="group-1")
        g = await _promise_on(pool, 1)
        await _msg(pool, 2, "outbound", _h(1), text="I will send it tomorrow", peer=None, lid="lid-1")
        lid = await _promise_on(pool, 2)
        await _msg(pool, 3, "outbound", _h(2), media="document", peer="peer-1")      # direct chat, not the group
        await _msg(pool, 4, "outbound", _h(3), media="document", peer=None, group="group-1")
        await _msg(pool, 5, "outbound", _h(3), media="image", peer=None, lid="lid-1")
        await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert (await _state(pool, g))[2] == 4
        assert (await _state(pool, lid))[2] == 5


@pytest.mark.asyncio
async def test_a_promise_without_a_thread_is_unthreadable_and_untouched(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_unthreadable") as pool:
        await _setup(pool)
        await _msg(pool, 1, "outbound", T0, text="I will send it tomorrow", peer=None)
        pid = await _promise_on(pool, 1)
        m = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert (m.scanned, m.unthreadable) == (1, 1)
        assert await _state(pool, pid) == OPEN


@pytest.mark.asyncio
async def test_client_ack_waits_for_the_window_to_close(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_ack") as pool:
        await _setup(pool)
        pid = await _promise(pool)
        await _msg(pool, 2, "inbound", _h(5), text="ok thanks")
        early = await wtp.run_resolve(pool, dry_run=False, now=_h(48))
        assert (early.client_ack, early.no_evidence) == (0, 1)
        assert await _state(pool, pid) == OPEN
        late = await wtp.run_resolve(pool, dry_run=False, now=NOW)
        assert late.client_ack == 1
        assert await _state(pool, pid) == (True, _h(5), 2, "client_ack")


@pytest.mark.asyncio
async def test_digest_line_counts_kinds_and_overdue_per_member_by_first_name(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "res_digest") as pool:
        await _setup(pool)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO team_members (email, name) VALUES "
                               "('member-1@example.invalid', 'Alpha Tester'), "
                               "('member-2@example.invalid', '4242 +628000000000')")
        await _promise_on(pool, 1, resolved=True, resolved_at=_h(1), kind="media_sent")
        await _promise_on(pool, 2, resolved=True, resolved_at=_h(1), kind="team_confirmed")
        await _promise_on(pool, 3, resolved=True, resolved_at=_h(1), kind="client_ack")
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        await _promise_on(pool, 4, due=past, email="Member-1@example.invalid")
        await _promise_on(pool, 5, due=past, email="member-1@example.invalid")
        await _promise_on(pool, 6, due=past, email="member-2@example.invalid")
        await _promise_on(pool, 7, due=past, email="unknown@example.invalid")
        await _promise_on(pool, 8, due=future, email="member-1@example.invalid")   # not overdue
        line = await wtp._fetch_resolution_digest(pool)
        assert line.startswith(
            "promises resolved: media_sent 1 team_confirmed 1 client_ack 1; overdue unresolved 4: Alpha 2, ")
        assert "42" not in line and "628" not in line and "example" not in line
        assert line.count("member-") == 2
