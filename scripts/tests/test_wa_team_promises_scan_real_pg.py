"""T3 promise gate — PR-2 REWORK real-Postgres tests (spec addendum A7, after
the gate's REWORK-DESIGN at 3adc6c0e89). Same opt-in gate as
test_wa_team_promises_real_pg.py: skipped unless `pg_ctl`/`initdb` are on
PATH AND WA_TEAM_PROMISES_REAL_PG=1. Own module-scoped throwaway cluster;
each test isolates itself in its own logical database via CREATE/DROP
DATABASE (mirrors test_wa_team_promises_gate_conditions_real_pg.py's
_fresh_database pattern from PR #7366).

These replace the fake pool/conn fixtures that used to live in
test_wa_team_promises_scan.py for batch/cursor/insert behavior — those fakes
re-implemented the cursor and ON CONFLICT logic in Python instead of
exercising the real SQL, so a real bug in the SQL text itself could pass
unnoticed. Covers: out-of-order commit, late body fill, revision (unjudged
updated, judged untouched), two-tick idempotency, mid-batch rollback +
next-tick recovery, and metrics/digest running only after commit while still
holding the scan lock (A5). "A poisoned exception text never reaches
stdout/log" (A6) needs no DB and lives in test_wa_team_promises_scan.py
instead.

Guilt: test_out_of_order_commit_is_found_on_the_next_tick and
test_late_body_fill_is_found_on_the_next_tick both FAIL against 3adc6c0e89
(the pre-REWORK head) — NOT with a TypeError (`run_scan`'s own signature,
`pool, *, batch_size, dry_run`, is IDENTICAL on both heads; the persisted
watermark lives entirely inside the function body via module-level state).
The failure is a semantic assertion (`assert 0 == 1`): the old code's
monotonic watermark, once advanced past a row's id, never looks at that id
again even after it becomes eligible later — proven by running BOTH tests
against the old `.py` (verified this turn with `$HOME` redirected to a
scratch dir, see the PR body's Rework section for the exact output).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime

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
    from scripts.wa_team_promises import run_init_schema, run_scan


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_scan_real_pg")
    # unix sockets have a kernel ~103-byte path limit pytest's own nested
    # tmp_path blows through — only a short /tmp dir fits.
    sockdir = tempfile.mkdtemp(prefix="watppgs_")
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


# Minimal stub of the Node-runtime-maintained mirror — only the columns the
# scanner's own SQL reads (id, direction, body, message_text, created_at).
_WMC_DDL = """
CREATE TABLE whatsapp_message_context (
    id           BIGINT PRIMARY KEY,
    direction    TEXT,
    body         TEXT,
    message_text TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def _setup(pool) -> None:
    await run_init_schema(pool)
    async with pool.acquire() as conn:
        await conn.execute(_WMC_DDL)


async def _insert_wmc(pool, *, msg_id: int, body: str | None = "", message_text: str | None = None,
                       direction: str = "outbound", created_at: datetime | None = None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whatsapp_message_context (id, direction, body, message_text, created_at) "
            "VALUES ($1, $2, $3, $4, COALESCE($5, now()))",
            msg_id, direction, body, message_text, created_at,
        )


async def _update_wmc_body(pool, *, msg_id: int, body: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE whatsapp_message_context SET body = $1 WHERE id = $2", body, msg_id)


async def _candidates(pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT message_id, clause_idx, clause_hash, promise_type, due_at_hint, status, "
            "attempts, last_attempt_at, revised_at FROM team_promise_candidates "
            "ORDER BY message_id, clause_idx"
        )
    return [dict(r) for r in rows]


# === A1 guilt#1 — out-of-order commit: found on the NEXT tick's full rescan ===


@pytest.mark.asyncio
async def test_out_of_order_commit_is_found_on_the_next_tick(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "scan_ooo") as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=102, body="I will send it tomorrow")

        m1 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m1.candidates_new == 1
        assert {r["message_id"] for r in await _candidates(pool)} == {102}

        # id 101 commits LATE, out of order relative to 102 already scanned —
        # a persisted monotonic watermark would never look at it again.
        await _insert_wmc(pool, msg_id=101, body="I will check it tomorrow")

        m2 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m2.candidates_new == 1  # only the new one — 102's text is unchanged
        assert {r["message_id"] for r in await _candidates(pool)} == {101, 102}


# === A1 guilt#2 — late body fill: NULL body -> filled -> candidates next tick ===
#
# id=201's body arrives NULL; a HIGHER id=205 already has real content, so
# the very first tick's own `max(id)` (whether that's the old persisted
# watermark or the new tick-local `hi`) jumps straight past 201 without ever
# examining it — 201 only had NULL body, it never even matched the SELECT's
# WHERE clause. The defect this guards is what happens on the tick AFTER
# 201's body is filled: an old monotonic watermark parked at 205 would never
# look at id 201 again; the REWORK's full-window rescan does.


@pytest.mark.asyncio
async def test_late_body_fill_is_found_on_the_next_tick(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "scan_latefill") as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=201, body=None, message_text=None)  # no text yet
        await _insert_wmc(pool, msg_id=205, body="I will send it tomorrow")  # higher id, real content

        m1 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m1.scanned == 1  # only 205 — 201 doesn't match the WHERE at all yet
        assert m1.candidates_new == 1
        assert {r["message_id"] for r in await _candidates(pool)} == {205}

        await _update_wmc_body(pool, msg_id=201, body="I will submit it tomorrow")

        m2 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m2.candidates_new == 1  # 201, newly eligible — 205's text is unchanged
        assert {r["message_id"] for r in await _candidates(pool)} == {201, 205}


# === A2 — revision updates an unjudged row in place, never a judged one ===


@pytest.mark.asyncio
async def test_revision_updates_unjudged_but_never_a_judged_row(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "scan_revision") as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=301, body="I will send it tomorrow")  # will be judged
        await _insert_wmc(pool, msg_id=302, body="I will send it tomorrow")  # stays unjudged

        await run_scan(pool, batch_size=200, dry_run=False)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE team_promise_candidates SET status = 'judged_true' WHERE message_id = 301"
            )
        before = {(r["message_id"], r["clause_idx"]): r for r in await _candidates(pool)}

        # same promise_type ("send"), different wording/due hint — clause_hash
        # changes, the catalog match still fires.
        await _update_wmc_body(pool, msg_id=301, body="I will send it today")
        await _update_wmc_body(pool, msg_id=302, body="I will send it today")

        m2 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m2.candidates_revised == 1
        assert m2.candidates_new == 0
        after = {(r["message_id"], r["clause_idx"]): r for r in await _candidates(pool)}

        # judged row: byte-for-byte untouched (same hash, cue, status).
        assert after[(301, 0)] == before[(301, 0)]
        # unjudged row: revised — new hash/cue, attempts/last_attempt_at
        # reset, revised_at now set.
        assert after[(302, 0)]["clause_hash"] != before[(302, 0)]["clause_hash"]
        assert after[(302, 0)]["due_at_hint"] == "today"
        assert after[(302, 0)]["status"] == "unjudged"
        assert after[(302, 0)]["attempts"] == 0
        assert after[(302, 0)]["last_attempt_at"] is None
        assert after[(302, 0)]["revised_at"] is not None


# === two ticks back-to-back are idempotent (no drift, no duplicate work) ===


@pytest.mark.asyncio
async def test_two_ticks_back_to_back_are_idempotent(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "scan_idempotent") as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=401, body="I will send it tomorrow")

        m1 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m1.candidates_new == 1
        m2 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m2.candidates_new == 0
        assert m2.candidates_revised == 0  # unchanged text — the WHERE excludes it
        assert len(await _candidates(pool)) == 1


# === mid-batch error: the WHOLE batch rolls back, next tick recovers ===


class _FlakyConnProxy:
    """Wraps a REAL asyncpg connection — `transaction()`/`fetch`/`fetchval`
    pass straight through (real commit/rollback semantics), but the Nth
    `fetchrow` call (the candidate upsert) raises synthetically, so the
    surrounding `async with conn.transaction():` in run_scan_batch rolls
    back for real."""

    def __init__(self, real_conn, boom_after: int):
        self._real = real_conn
        self._n = 0
        self._boom_after = boom_after

    def transaction(self):
        return self._real.transaction()

    async def fetch(self, *a, **kw):
        return await self._real.fetch(*a, **kw)

    async def fetchval(self, *a, **kw):
        return await self._real.fetchval(*a, **kw)

    async def fetchrow(self, *a, **kw):
        self._n += 1
        if self._n == self._boom_after:
            raise RuntimeError("synthetic mid-batch failure")
        return await self._real.fetchrow(*a, **kw)


class _FlakyAcquire:
    def __init__(self, real_cm, boom_after: int):
        self._cm = real_cm
        self._boom_after = boom_after

    async def __aenter__(self):
        real_conn = await self._cm.__aenter__()
        return _FlakyConnProxy(real_conn, self._boom_after)

    async def __aexit__(self, *exc):
        return await self._cm.__aexit__(*exc)


class _FlakyPool:
    def __init__(self, real_pool, boom_after: int):
        self._real = real_pool
        self._boom_after = boom_after

    def acquire(self):
        return _FlakyAcquire(self._real.acquire(), self._boom_after)


@pytest.mark.asyncio
async def test_mid_batch_error_rolls_back_the_whole_batch_and_next_tick_recovers(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "scan_midbatch") as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=501, body="I will send it tomorrow")
        await _insert_wmc(pool, msg_id=502, body="I will check it tomorrow")

        # boom on the 2nd fetchrow inside the batch's ONE transaction —
        # candidate 501's own upsert must NOT survive candidate 502's failure.
        flaky = _FlakyPool(pool, boom_after=2)
        with pytest.raises(RuntimeError, match="synthetic mid-batch failure"):
            await run_scan(flaky, batch_size=200, dry_run=False)

        assert await _candidates(pool) == []  # whole batch rolled back, nothing committed

        m2 = await run_scan(pool, batch_size=200, dry_run=False)
        assert m2.candidates_new == 2
        assert {r["message_id"] for r in await _candidates(pool)} == {501, 502}


# === A5 — metrics + digest run only after commit, and while still locked ===


class _NoCloseProxyPool:
    """`asyncpg.Pool.close` is a read-only Cython attribute — can't
    monkeypatch it on the instance. Wrap instead: cli_main's own
    `await pool.close()` becomes a no-op, the fixture's `_fresh_database`
    still owns the real close+dropdb at test teardown."""

    def __init__(self, real_pool):
        self._real = real_pool

    def acquire(self):
        return self._real.acquire()

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_digest_and_metrics_run_after_commit_and_while_still_locked(
    pg_socket_dir, monkeypatch, tmp_path,
):
    db_name = "scan_lockorder"
    async with _fresh_database(pg_socket_dir, db_name) as pool:
        await _setup(pool)
        await _insert_wmc(pool, msg_id=601, body="I will send it tomorrow")

        no_close_pool = _NoCloseProxyPool(pool)

        async def _fake_create_pool(**_kwargs):
            return no_close_pool

        monkeypatch.setattr(wa_team_promises.asyncpg, "create_pool", _fake_create_pool)
        monkeypatch.setattr(wa_team_promises, "STATE_DIR", tmp_path)
        monkeypatch.setattr(wa_team_promises, "_SCAN_LOCK_FILE", tmp_path / "scan.lock")
        monkeypatch.setattr(wa_team_promises, "_SCAN_METRICS_FILE", tmp_path / "metrics.json")
        # REWORK B2: the digest is only attempted during the midnight WITA
        # hour — this test is about lock/commit ORDERING, not the daily
        # cadence gate (that's test_digest_cadence_sends_exactly_once_per_
        # day_with_the_true_previous_day_total's job), so force the gate
        # open regardless of the real wall clock at test-run time.
        monkeypatch.setattr(wa_team_promises, "_is_first_digest_opportunity_of_the_day", lambda _now: True)
        for k in list(os.environ):
            if k.startswith("FLY_"):
                monkeypatch.delenv(k, raising=False)

        def _independent_committed_count() -> int:
            # REWORK B4 (Codex MEDIUM): a fresh connection, opened INSIDE the
            # callback itself — not the pool cli_main is using, not a check
            # deferred until after cli_main returns. Moving these callbacks
            # before an eventual commit could still pass a same-pool or
            # after-the-fact check; a brand-new connection can only see what
            # is actually durably committed at the moment it queries. The
            # callbacks are sync, called from inside the running event loop
            # cli_main awaits on, so the query runs on its OWN loop in a
            # separate thread (asyncio.run in-loop would raise "already
            # running").
            async def _q() -> int:
                conn = await asyncpg.connect(
                    host=str(pg_socket_dir), user="postgres", database=db_name,
                )
                try:
                    return await conn.fetchval("SELECT count(*) FROM team_promise_candidates")
                finally:
                    await conn.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, _q()).result()

        order: list[str] = []
        committed_counts: dict[str, int] = {}
        real_save_metrics = wa_team_promises._save_scan_metrics

        def _spy_save_metrics(metrics):
            # flock is per open-file-description, not per process — a second
            # acquire from the SAME process still conflicts with cli_main's
            # own held lock, so this failing to grab it proves the lock is
            # still held here.
            assert wa_team_promises._acquire_scan_lock_or_none() is None, "lock released too early"
            committed_counts["metrics"] = _independent_committed_count()
            order.append("metrics")
            return real_save_metrics(metrics)

        def _spy_send_digest(*_a, **_kw):
            assert wa_team_promises._acquire_scan_lock_or_none() is None, "lock released too early"
            committed_counts["digest"] = _independent_committed_count()
            order.append("digest")

        monkeypatch.setattr(wa_team_promises, "_save_scan_metrics", _spy_save_metrics)
        monkeypatch.setattr(wa_team_promises, "_send_scan_digest", _spy_send_digest)

        rc = await wa_team_promises.cli_main(["--scan"])

        assert rc == 0
        assert order == ["metrics", "digest"]
        # committed and visible to an INDEPENDENT connection, from INSIDE
        # both callbacks — not inferred after cli_main returned.
        assert committed_counts == {"metrics": 1, "digest": 1}
        assert len(await _candidates(pool)) == 1

        # released once cli_main returns
        fd = wa_team_promises._acquire_scan_lock_or_none()
        assert fd is not None
        wa_team_promises._release_scan_lock(fd)
