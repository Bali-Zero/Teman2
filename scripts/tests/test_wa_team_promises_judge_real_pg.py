"""T3 promise gate — PR-3 (the local judge), opt-in real-Postgres half.
Skipped unless a local `pg_ctl`/`initdb` are on PATH AND
WA_TEAM_PROMISES_REAL_PG=1 is set — same gate, same throwaway-cluster/
per-test-database pattern as test_wa_team_promises_scan_real_pg.py and
test_wa_team_promises_gate_conditions_real_pg.py.

Covers exactly what a fake pool/conn cannot prove for real: the guarded
UPDATE's WHERE clause actually blocking a concurrent scanner revision (never
a Python re-implementation of the guard), the ON CONFLICT dedup on
team_promises, and the status-CHECK schema upgrade from the PR-1/PR-2
4-value shape (with rows) to the 5-value one, idempotent on rerun. Ollama
itself is monkeypatched out everywhere here (`_call_ollama`) — the model
call's own request shape / strict validation / transport handling are unit
tests in test_wa_team_promises_judge.py; this file only exercises the DB
guard and schema behavior around it.
"""
from __future__ import annotations

import asyncio
import logging
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
    from scripts.wa_team_promises import (
        SchemaMismatchError,
        _apply_true,
        _hash_clause,
        _split_clauses,
        run_init_schema,
        run_judge,
    )


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_judge_real_pg")
    sockdir = tempfile.mkdtemp(prefix="watppgj_")
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


# Same minimal Node-mirror stub as test_wa_team_promises_scan_real_pg.py —
# only the columns the judge's own SQL reads (id, body, message_text,
# created_at; direction is read by the SCANNER, not the judge, but is kept
# here for shape parity with the real table).
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


async def _insert_wmc(pool, *, msg_id: int, body: str | None, created_at: datetime) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whatsapp_message_context (id, direction, body, created_at) "
            "VALUES ($1, 'outbound', $2, $3)",
            msg_id, body, created_at,
        )


async def _update_wmc_body(pool, *, msg_id: int, body: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE whatsapp_message_context SET body = $1 WHERE id = $2", body, msg_id)


async def _insert_candidate(
    pool, *, message_id: int, clause_idx: int, clause_hash: str, promise_type: str = "send",
    due_at_hint: str | None = None, status: str = "unjudged", attempts: int = 0,
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO team_promise_candidates "
            "(message_id, clause_idx, clause_hash, promise_type, due_at_hint, status, attempts) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            message_id, clause_idx, clause_hash, promise_type, due_at_hint, status, attempts,
        )
    return row["id"]


async def _candidate_row(pool, candidate_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, message_id, clause_idx, clause_hash, promise_type, due_at_hint, status, "
            "attempts FROM team_promise_candidates WHERE id = $1",
            candidate_id,
        )
    return dict(row)


async def _promises(pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT message_id, promise_text, promise_type, due_at, extractor_version, "
            "conversation_id, client_id, thread_key, team_member_email "
            "FROM team_promises ORDER BY message_id, promise_type"
        )
    return [dict(r) for r in rows]


def _seed_candidate_for_body(body: str, clause_idx: int = 0) -> tuple[str, str]:
    """Returns (clause_text, clause_hash) exactly as the SCANNER would have
    computed them for `body` at `clause_idx` — never hand-typed, so a test
    can never accidentally seed a hash the real splitter wouldn't produce."""
    clauses = _split_clauses(body)
    return clauses[clause_idx], _hash_clause(clauses[clause_idx])


# === C2 — the judge re-verifies the CURRENT body before ever calling Ollama ===
# (PENDING-ARMS PWC-CONDITIONS for PR #7367). Each case must reach `run_judge`
# with `_call_ollama` monkeypatched to RAISE — proving no model call happens.


@pytest.mark.asyncio
async def test_c2_message_row_gone_marks_superseded_no_ollama_call(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_c2_gone") as pool:
        await _setup(pool)
        # message_id 900 never inserted at all — the mirror row is gone.
        await _insert_candidate(pool, message_id=900, clause_idx=0, clause_hash="whatever")

        def _must_not_call(*_a, **_kw):
            raise AssertionError("Ollama must not be called for a superseded candidate")
        monkeypatch.setattr(wtp, "_call_ollama", _must_not_call)

        metrics = await run_judge(pool, limit=20, dry_run=False)

        assert metrics.superseded == 1
        assert metrics.raced == 0
        assert await _promises(pool) == []


@pytest.mark.asyncio
async def test_c2_message_body_now_empty_marks_superseded(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_c2_empty") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        await _insert_wmc(pool, msg_id=901, body="", created_at=created_at)
        await _insert_candidate(pool, message_id=901, clause_idx=0, clause_hash="whatever")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Ollama must not be called")))

        metrics = await run_judge(pool, limit=20, dry_run=False)
        assert metrics.superseded == 1


@pytest.mark.asyncio
async def test_c2_clause_idx_out_of_range_after_body_shrank_marks_superseded(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_c2_shrank") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        original_body = "I will send it tomorrow. I will check it today"
        clause_text, clause_hash = _seed_candidate_for_body(original_body, clause_idx=1)
        assert clause_text == "I will check it today"
        await _insert_wmc(pool, msg_id=902, body=original_body, created_at=created_at)
        await _insert_candidate(pool, message_id=902, clause_idx=1, clause_hash=clause_hash)

        # the message is edited down to ONE clause — index 1 no longer exists.
        await _update_wmc_body(pool, msg_id=902, body="I will send it tomorrow")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Ollama must not be called")))

        metrics = await run_judge(pool, limit=20, dry_run=False)
        assert metrics.superseded == 1


@pytest.mark.asyncio
async def test_c2_hash_mismatch_after_body_edited_marks_superseded(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_c2_edited") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        original_body = "I will send it tomorrow"
        _clause_text, clause_hash = _seed_candidate_for_body(original_body, clause_idx=0)
        await _insert_wmc(pool, msg_id=903, body=original_body, created_at=created_at)
        await _insert_candidate(pool, message_id=903, clause_idx=0, clause_hash=clause_hash)

        # same clause_idx still exists, but the WORDING changed underneath it.
        await _update_wmc_body(pool, msg_id=903, body="I will send it today")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Ollama must not be called")))

        metrics = await run_judge(pool, limit=20, dry_run=False)
        assert metrics.superseded == 1


# === innocence: body unchanged, Ollama (mocked) says true -> team_promises ===


@pytest.mark.asyncio
async def test_innocence_unchanged_body_true_verdict_inserts_team_promises_row(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_true_insert") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=904, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=904, clause_idx=0, clause_hash=clause_hash,
                                       promise_type="send", due_at_hint="tomorrow")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: True)

        metrics = await run_judge(pool, limit=20, dry_run=False)

        assert metrics.true == 1
        assert metrics.raced == 0
        row = await _candidate_row(pool, cid)
        assert row["status"] == "judged_true"
        promises = await _promises(pool)
        assert len(promises) == 1
        p = promises[0]
        assert p["message_id"] == 904
        assert p["promise_text"] == clause_text
        assert p["promise_type"] == "send"
        assert p["due_at"] == created_at + timedelta(hours=24)  # "tomorrow"
        assert p["extractor_version"] == wtp._EXTRACTOR_VERSION
        # P2/P5 own these — the judge leaves them NULL.
        assert p["conversation_id"] is None
        assert p["client_id"] is None
        assert p["thread_key"] is None
        assert p["team_member_email"] is None


@pytest.mark.asyncio
async def test_innocence_false_verdict_marks_judged_false_no_promises_row(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_false") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=905, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=905, clause_idx=0, clause_hash=clause_hash)

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: False)

        metrics = await run_judge(pool, limit=20, dry_run=False)

        assert metrics.false == 1
        row = await _candidate_row(pool, cid)
        assert row["status"] == "judged_false"
        assert await _promises(pool) == []


@pytest.mark.asyncio
async def test_d6_true_verdict_without_a_hint_defaults_to_48h(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "judge_d6_default") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it"  # no temporal cue at all
        _clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=906, body=body, created_at=created_at)
        await _insert_candidate(pool, message_id=906, clause_idx=0, clause_hash=clause_hash,
                                 due_at_hint=None)

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: True)
        await run_judge(pool, limit=20, dry_run=False)

        promises = await _promises(pool)
        assert len(promises) == 1
        assert promises[0]["due_at"] == created_at + timedelta(hours=48)  # D6 default


# === judged_true dedup: two candidates, same message_id+promise_type ===


@pytest.mark.asyncio
async def test_judged_true_dedup_two_candidates_same_message_and_type_one_promises_row(
    pg_socket_dir, monkeypatch,
):
    async with _fresh_database(pg_socket_dir, "judge_dedup") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow. I will send it today"
        clauses = _split_clauses(body)
        assert len(clauses) == 2
        await _insert_wmc(pool, msg_id=907, body=body, created_at=created_at)
        await _insert_candidate(pool, message_id=907, clause_idx=0,
                                 clause_hash=_hash_clause(clauses[0]), promise_type="send")
        await _insert_candidate(pool, message_id=907, clause_idx=1,
                                 clause_hash=_hash_clause(clauses[1]), promise_type="send")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: True)
        metrics = await run_judge(pool, limit=20, dry_run=False)

        assert metrics.true == 2  # both candidate rows get marked judged_true
        promises = await _promises(pool)
        assert len(promises) == 1  # but only ONE team_promises row (ON CONFLICT DO NOTHING)
        assert promises[0]["message_id"] == 907
        assert promises[0]["promise_type"] == "send"


# === race: the scanner revises a candidate BETWEEN the judge's read and its ===
# === guarded write -> the UPDATE affects 0 rows -> raced, no promises row  ===


@pytest.mark.asyncio
async def test_race_scanner_revision_mid_tick_guard_fails_no_promises_row(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_race") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, original_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=908, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=908, clause_idx=0, clause_hash=original_hash)

        # Simulates the scanner revising this SAME unjudged row mid-tick
        # (a new clause_hash, attempts reset) — exactly what
        # _CANDIDATE_UPSERT_SQL's own guarded DO UPDATE does, applied
        # directly here since true concurrency needs two live connections
        # racing a shared lock the test cannot deterministically land
        # between the judge's read and its write; the OUTCOME (row still
        # 'unjudged', clause_hash changed under it) is identical either way,
        # and that outcome — not the interleaving — is what the guard reacts
        # to.
        new_hash = "a" * 64
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE team_promise_candidates SET clause_hash = $1, attempts = 0 WHERE id = $2",
                new_hash, cid,
            )

        # _apply_true is called with the STALE hash the judge "read" before
        # the revision above — proving the guard, not run_judge's own
        # selection (which would legitimately re-read the new row and just
        # supersede it for a real out-of-band hash change). The message body
        # is UNCHANGED here (only the candidate row was revised), so
        # _apply_true's own second read matches judged_hash and it reaches
        # the candidate-side guard, which is what this test is about.
        outcome = await _apply_true(
            pool, cid, original_hash, message_id=908, clause_idx=0,
            promise_type="send", due_at_hint=None, dry_run=False,
        )

        assert outcome == "raced"
        assert await _promises(pool) == []
        row = await _candidate_row(pool, cid)
        assert row["status"] == "unjudged"  # untouched — the scanner's own revision stands
        assert row["clause_hash"] == new_hash


# === round-1 council finding #2: the TOCTOU window between the judge's ===
# === FIRST read (pre-Ollama-call) and the write is closed by a SECOND,   ===
# === FOR-SHARE-locked read inside _apply_true itself.                    ===


@pytest.mark.asyncio
async def test_toctou_message_edited_after_first_read_before_apply_true_marks_superseded(
    pg_socket_dir,
):
    async with _fresh_database(pg_socket_dir, "judge_toctou") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        original_body = "I will send it tomorrow"
        _clause_text, original_hash = _seed_candidate_for_body(original_body)
        await _insert_wmc(pool, msg_id=909, body=original_body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=909, clause_idx=0, clause_hash=original_hash,
                                       promise_type="send", due_at_hint="tomorrow")

        # Simulates the message being edited WHILE an Ollama call for the
        # ORIGINAL clause is in flight: the candidate row's own clause_hash
        # is untouched (the scanner has not ticked yet), but the body under
        # it has already changed by the time _apply_true runs.
        await _update_wmc_body(pool, msg_id=909, body="I will send it NEXT WEEK instead")

        # judged_hash is the hash of the ORIGINAL clause — exactly what the
        # judge would still be holding after a slow Ollama call returned a
        # verdict for text that is no longer current.
        outcome = await _apply_true(
            pool, cid, original_hash, message_id=909, clause_idx=0,
            promise_type="send", due_at_hint="tomorrow", dry_run=False,
        )

        # A mutant that reverts to the pre-fix _apply_true (writing the
        # caller's OWN promise_text/due_at with no second read) would return
        # "true" here and insert the STALE "I will send it tomorrow" text —
        # this asserts the fix's actual, structural guarantee instead.
        assert outcome == "superseded"
        assert await _promises(pool) == []
        row = await _candidate_row(pool, cid)
        assert row["status"] == "superseded"
        assert row["clause_hash"] == original_hash  # untouched — only status flipped


@pytest.mark.asyncio
async def test_toctou_message_unchanged_apply_true_inserts_from_its_own_fresh_read(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_toctou_ok") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=910, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=910, clause_idx=0, clause_hash=clause_hash,
                                       promise_type="send", due_at_hint="tomorrow")

        outcome = await _apply_true(
            pool, cid, clause_hash, message_id=910, clause_idx=0,
            promise_type="send", due_at_hint="tomorrow", dry_run=False,
        )

        assert outcome == "true"
        row = await _candidate_row(pool, cid)
        assert row["status"] == "judged_true"
        promises = await _promises(pool)
        assert len(promises) == 1
        assert promises[0]["promise_text"] == clause_text
        assert promises[0]["due_at"] == created_at + timedelta(hours=24)


# Delta-round finding (codex-gpt-5.6-sol): the two TOCTOU tests above prove
# the OUTCOME of the second read (a mismatch supersedes, a match inserts),
# but neither one PROVES a lock is actually held — a mutant that dropped
# `FOR SHARE` from _JUDGE_MESSAGE_FOR_SHARE_SQL entirely would still pass
# both, since this test file never runs two connections against the same
# row at once. This test opens two REAL, independent connections (bypassing
# the pool's own max_size=1 — a second `pool.acquire()` would just wait for
# the first to free up, which would hide the very lock this test exists to
# prove) and shows a concurrent UPDATE on the message row genuinely blocks
# until the FOR-SHARE-holding transaction commits.
@pytest.mark.asyncio
async def test_for_share_lock_genuinely_blocks_a_concurrent_message_update(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_for_share_lock") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        await _insert_wmc(pool, msg_id=916, body=body, created_at=created_at)

        conn_reader = await asyncpg.connect(host=pg_socket_dir, user="postgres",
                                             database="judge_for_share_lock")
        conn_writer = await asyncpg.connect(host=pg_socket_dir, user="postgres",
                                             database="judge_for_share_lock")
        try:
            reader_tx = conn_reader.transaction()
            await reader_tx.start()
            row = await conn_reader.fetchrow(wtp._JUDGE_MESSAGE_FOR_SHARE_SQL, 916)
            assert row["body"] == body  # the lock IS held from this point

            update_task = asyncio.create_task(
                conn_writer.execute(
                    "UPDATE whatsapp_message_context SET body = $1 WHERE id = $2",
                    "edited while locked", 916,
                )
            )
            await asyncio.sleep(0.3)
            # The concurrent UPDATE must NOT have completed yet — FOR SHARE
            # conflicts with the ROW EXCLUSIVE lock an UPDATE needs.
            assert not update_task.done(), (
                "a concurrent UPDATE completed while FOR SHARE was held — "
                "the lock is not actually blocking (finding not closed)"
            )

            await reader_tx.commit()
            await asyncio.wait_for(update_task, timeout=5.0)  # now unblocks

            post = await conn_reader.fetchrow(
                "SELECT body FROM whatsapp_message_context WHERE id = $1", 916,
            )
            assert post["body"] == "edited while locked"
        finally:
            await conn_reader.close()
            await conn_writer.close()


# === round-1 council finding #4/#6 (codex + kimi-code/k3, independently): ===
# === the false/superseded guarded UPDATEs were only proven for _apply_true ===
# === against real PG; a dropped `AND clause_hash=$2` on either would pass  ===
# === the whole suite otherwise.                                            ===


@pytest.mark.asyncio
async def test_race_judged_false_guard_fails_on_stale_hash_no_status_change(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_race_false") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, original_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=911, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=911, clause_idx=0, clause_hash=original_hash)

        new_hash = "b" * 64
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE team_promise_candidates SET clause_hash = $1, attempts = 0 WHERE id = $2",
                new_hash, cid,
            )

        held = await wtp._apply_guarded(pool, wtp._JUDGE_MARK_FALSE_SQL, cid, original_hash, False)

        assert held is False
        row = await _candidate_row(pool, cid)
        assert row["status"] == "unjudged"
        assert row["clause_hash"] == new_hash


@pytest.mark.asyncio
async def test_race_superseded_guard_fails_on_stale_hash_no_status_change(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_race_superseded") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, original_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=912, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=912, clause_idx=0, clause_hash=original_hash)

        new_hash = "c" * 64
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE team_promise_candidates SET clause_hash = $1, attempts = 0 WHERE id = $2",
                new_hash, cid,
            )

        held = await wtp._apply_guarded(pool, wtp._JUDGE_MARK_SUPERSEDED_SQL, cid, original_hash, False)

        assert held is False
        row = await _candidate_row(pool, cid)
        assert row["status"] == "unjudged"
        assert row["clause_hash"] == new_hash


# === round-1 council finding #6 (kimi-code/k3): the attempt-increment ===
# === guard now also pins `attempts`, so a racing SECOND increment against ===
# === the value the judge itself read at selection time loses this guard  ===
# === exactly like every other path already loses its own.                ===


@pytest.mark.asyncio
async def test_race_attempt_guard_pins_selection_time_attempts_double_judge_loses(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_race_attempt") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=913, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=913, clause_idx=0, clause_hash=clause_hash,
                                       attempts=2)

        # First "judge" instance applies an attempt increment for the
        # attempts=2 value it read at selection time.
        outcome1 = await wtp._apply_attempt(pool, cid, clause_hash, 2, False)
        assert outcome1 == "unjudged"

        # A second, RACING instance that ALSO read attempts=2 at selection
        # time (before the first one committed) tries the SAME increment —
        # without AND attempts=$3 this would double-count; with it, the
        # guard now fails because attempts is 3, not 2.
        outcome2 = await wtp._apply_attempt(pool, cid, clause_hash, 2, False)
        assert outcome2 is None  # raced

        row = await _candidate_row(pool, cid)
        assert row["attempts"] == 3  # incremented exactly ONCE, not twice


@pytest.mark.asyncio
async def test_attempt_fourth_failure_quarantines_on_real_pg(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_quarantine") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        _clause_text, clause_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=914, body=body, created_at=created_at)
        cid = await _insert_candidate(pool, message_id=914, clause_idx=0, clause_hash=clause_hash,
                                       attempts=4)

        # The 5th failed attempt (attempts 4 -> 5 == _JUDGE_MAX_ATTEMPTS)
        # quarantines in the SAME guarded UPDATE.
        outcome = await wtp._apply_attempt(pool, cid, clause_hash, 4, False)

        assert outcome == "quarantined"
        row = await _candidate_row(pool, cid)
        assert row["status"] == "quarantined"
        assert row["attempts"] == 5

        # And a quarantined row is no longer selected at all (attempts <
        # _JUDGE_MAX_ATTEMPTS in _JUDGE_SELECT_SQL, kimi finding #5).
        async with pool.acquire() as conn:
            selected = await conn.fetch(wtp._JUDGE_SELECT_SQL, 20)
        assert cid not in [r["id"] for r in selected]


# === round-1 council finding #1 (codex) — RETRACTED with evidence: the      ===
# === judge's body/message_text COALESCE is the SAME expression the         ===
# === scanner's own selection query uses (scripts/wa_team_promises.py:315,  ===
# === on origin/main before this PR), so a raw `body=''` with a non-empty   ===
# === `message_text` is NOT "the current body is empty" from this module's  ===
# === own, pre-existing, shared definition of "body" — it is exactly the    ===
# === same message the scanner itself would still treat as having content. ===
# === This is not a new inconsistency PR-3 introduces; it is parity with a  ===
# === query already on main.                                                ===


@pytest.mark.asyncio
async def test_message_text_fallback_is_not_a_c2_bypass_matches_scanner_selection(
    pg_socket_dir, monkeypatch,
):
    async with _fresh_database(pg_socket_dir, "judge_message_text_fallback") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body = "I will send it tomorrow"
        clause_text, clause_hash = _seed_candidate_for_body(body)
        # body='' (falsy), message_text carries the SAME content the
        # candidate was created from — COALESCE(NULLIF(body,''), ...) makes
        # this indistinguishable, on purpose, from a normal non-empty body.
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO whatsapp_message_context (id, direction, body, message_text, created_at) "
                "VALUES ($1, 'outbound', '', $2, $3)",
                915, body, created_at,
            )
        cid = await _insert_candidate(pool, message_id=915, clause_idx=0, clause_hash=clause_hash,
                                       promise_type="send")

        monkeypatch.setattr(wtp, "_call_ollama", lambda *_a, **_kw: True)
        metrics = await run_judge(pool, limit=20, dry_run=False)

        # NOT superseded — the effective body (per the shared COALESCE) is
        # unchanged, so the judge proceeds exactly as it would for a message
        # whose `body` column was never empty in the first place.
        assert metrics.superseded == 0
        assert metrics.true == 1
        row = await _candidate_row(pool, cid)
        assert row["status"] == "judged_true"
        promises = await _promises(pool)
        assert len(promises) == 1
        assert promises[0]["promise_text"] == clause_text


# === schema upgrade: the PR-1/PR-2 4-value shape, WITH ROWS, to 5-value ===


_PRE_PR3_COMPLETE_SHAPE_DDL = """
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revised_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uix_team_promise_candidates_msg_clause
    ON team_promise_candidates (message_id, clause_idx);

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
    thread_key TEXT,
    team_member_email TEXT,
    extractor_version TEXT,
    resolution_kind TEXT
);
CREATE UNIQUE INDEX uix_team_promises_msg_type ON team_promises (message_id, promise_type);
"""


@pytest.mark.asyncio
async def test_status_check_upgrade_from_4value_shape_with_rows_then_idempotent_rerun(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_upgrade") as pool:
        async with pool.acquire() as conn:
            await conn.execute(_PRE_PR3_COMPLETE_SHAPE_DDL)
            # the auto-generated name for an inline, unnamed CHECK on this
            # column IS wa_team_promises.py's own _STATUS_CHECK_NAME — this
            # is exactly why the ledger names it explicitly rather than
            # inventing a fresh one to migrate away from.
            assert await conn.fetchval(
                "SELECT conname FROM pg_constraint WHERE conrelid = "
                "to_regclass('public.team_promise_candidates')::oid AND contype = 'c'"
            ) == wtp._STATUS_CHECK_NAME
            await conn.execute(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, "
                "promise_type, status) VALUES (1, 0, 'h1', 'send', 'unjudged'), "
                "(2, 0, 'h2', 'send', 'judged_true')"
            )

        await run_init_schema(pool)

        async with pool.acquire() as conn:
            definition = await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = "
                "to_regclass('public.team_promise_candidates')::oid AND conname = $1",
                wtp._STATUS_CHECK_NAME,
            )
        assert definition == wtp._expected_status_check_def()
        rows = await _candidates_status_only(pool)
        assert rows == {(1, "unjudged"), (2, "judged_true")}  # rows intact, values unchanged

        # a candidate carrying the NEW status value must now be insertable —
        # proof the constraint genuinely admits it, not just that its text matches.
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, "
                "promise_type, status) VALUES (3, 0, 'h3', 'send', 'superseded')"
            )

        # idempotent rerun: no error, rows (now 3) still intact.
        await run_init_schema(pool)
        rows_after_rerun = await _candidates_status_only(pool)
        assert rows_after_rerun == {(1, "unjudged"), (2, "judged_true"), (3, "superseded")}


async def _candidates_status_only(pool) -> set[tuple[int, str]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT message_id, status FROM team_promise_candidates")
    return {(r["message_id"], r["status"]) for r in rows}


# === verify_status_check itself: fails closed on a genuinely wrong value ===
# === set under the RIGHT name (proves the catalog comparison, not just    ===
# === that _expected_status_check_def() matches itself). run_init_schema's ===
# === own DDL cannot organically produce this state (its DROP+ADD always  ===
# === self-heals the constraint before verification runs) — this exercises ===
# === the guard function directly, the same way the column/index verifiers ===
# === are proven against a hand-built mismatch in test_wa_team_promises_   ===
# === real_pg.py rather than through a run_init_schema rerun.              ===


@pytest.mark.asyncio
async def test_verify_status_check_rejects_a_wrong_value_set_under_the_right_name(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "judge_status_guard") as pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "CREATE TABLE team_promise_candidates (status TEXT NOT NULL DEFAULT 'unjudged' "
                f"CONSTRAINT {wtp._STATUS_CHECK_NAME} CHECK (status IN ('unjudged', 'judged_true')))"
            )
            with pytest.raises(SchemaMismatchError) as exc_info:
                await wtp.verify_status_check(conn)
            assert exc_info.value.identifier == wtp._STATUS_CHECK_NAME


@pytest.mark.asyncio
async def test_bad_preexisting_status_row_blocks_the_new_check_and_rolls_back(pg_socket_dir):
    """A row already holding a status value outside BOTH the old 4-value set
    and the new 5-value one (data corruption, or a hand-run INSERT) makes
    Postgres itself refuse `ADD CONSTRAINT ... CHECK (...)` — the whole
    `run_init_schema` transaction rolls back rather than silently accepting
    corrupt data under a constraint that claims to forbid it."""
    async with _fresh_database(pg_socket_dir, "judge_bad_row") as pool:
        async with pool.acquire() as conn:
            # same complete pre-PR-3 shape, but WITHOUT its own CHECK, so the
            # bogus INSERT below is not itself rejected before the test begins.
            await conn.execute(_PRE_PR3_COMPLETE_SHAPE_DDL.replace(
                "        CHECK (status IN ('unjudged', 'judged_true', 'judged_false', 'quarantined'))",
                "",
            ))
            await conn.execute(
                "INSERT INTO team_promise_candidates (message_id, clause_idx, clause_hash, "
                "promise_type, status) VALUES (1, 0, 'h1', 'send', 'totally_bogus_status')"
            )

        with pytest.raises(asyncpg.CheckViolationError):
            await run_init_schema(pool)

        # rolled back: no status_check constraint exists at all (the ALTER
        # that would add it never committed), and the bogus row is untouched.
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT count(*) FROM pg_constraint WHERE conrelid = "
                "to_regclass('public.team_promise_candidates')::oid AND conname = $1",
                wtp._STATUS_CHECK_NAME,
            )
        assert exists == 0
        rows = await _candidates_status_only(pool)
        assert rows == {(1, "totally_bogus_status")}


# === Gate condition C1 (fresh-Opus Gear-3 gate on PR #7597, pull/7597#issuecomment-5885208473) ===
# === G1-G7 (+ G-LOW-1/G-LOW-2): permanent guilt tests for mutants that survived the corpus, found  ===
# === by two fresh-Opus gates (#7597, #7646 comments). Counts are deliberately NOT written here:    ===
# === nothing re-measures a number in a comment, and the CI floor step in                           ===
# === wa-team-promises-tests.yml is the one place a count lives. Each test names its mutants in its ===
# === own comment. No production code changed: every mutant was already fixed on main; these tests ===
# === only make sure a REGRESSION turns red in future.                                              ===

POISON = "SYNTHETIC-POISON +6280000000000 Jane Roe"


# G1 (mutants M07/M08 and the gate-#7646 status-half survivors M07b/c/d,
# M08b, MSUP, MATT) — C2's guard has TWO halves: clause_hash AND status.
# Every existing race test pins the clause_hash half; this pins the STATUS
# half as a full matrix: each of the four guarded writes (MARK_TRUE via
# _apply_true, MARK_FALSE and MARK_SUPERSEDED via _apply_guarded, MARK_ATTEMPT
# via _apply_attempt) is aimed, with a MATCHING clause_hash (and matching
# attempts for the attempt write), at a row that is ALREADY in each terminal
# status (judged_true / judged_false / superseded / quarantined). Every one of
# those 16 cells must lose the guard and leave the row untouched. A guard
# relaxed to any status set other than exactly `= 'unjudged'` (dropped,
# IN (...), <>) turns at least one cell red, because each relaxation admits
# at least one of the four terminal statuses tested against the write it
# relaxes.
_G1_TERMINAL_STATUSES = ("judged_true", "judged_false", "superseded", "quarantined")


@pytest.mark.asyncio
async def test_g1_guarded_writes_also_require_status_unjudged_not_just_the_hash(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "g1") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        _clause, h = _seed_candidate_for_body(body)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)

        msg_id = 100
        for write in ("TRUE", "FALSE", "SUPERSEDED", "ATTEMPT"):
            for status in _G1_TERMINAL_STATUSES:
                msg_id += 1
                cell = f"{write} x {status}"
                await _insert_wmc(pool, msg_id=msg_id, body=body, created_at=created_at)
                cid = await _insert_candidate(pool, message_id=msg_id, clause_idx=0, clause_hash=h,
                                               status=status, attempts=0)
                if write == "TRUE":
                    outcome = await _apply_true(pool, cid, h, message_id=msg_id, clause_idx=0,
                                                 promise_type="send", due_at_hint=None, dry_run=False)
                    assert outcome == "raced", cell
                elif write == "FALSE":
                    assert await wtp._apply_guarded(pool, wtp._JUDGE_MARK_FALSE_SQL, cid, h, False) is False, cell
                elif write == "SUPERSEDED":
                    assert await wtp._apply_guarded(pool, wtp._JUDGE_MARK_SUPERSEDED_SQL, cid, h, False) is False, cell
                else:
                    assert await wtp._apply_attempt(pool, cid, h, 0, False) is None, cell
                row = await _candidate_row(pool, cid)
                assert row["status"] == status, cell
                assert row["attempts"] == 0, cell
        assert await _promises(pool) == []


# G2 (mutant M10) — the attempt-increment guard's `AND attempts=$3` pin
# (round-1 council finding) only catches a race whose attempts value
# actually MOVED. A scanner revision resets attempts to 0 (same value the
# judge already read), so it is the CLAUSE_HASH half of this SAME guard that
# must still catch it — a mutant that dropped clause_hash from
# _JUDGE_MARK_ATTEMPT_SQL (leaving only the attempts pin) would pass every
# existing attempt-guard test, since none of them revise clause_hash while
# leaving attempts unchanged.
@pytest.mark.asyncio
async def test_g2_attempt_guard_clause_hash_half_catches_a_same_attempts_revision(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "g2") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        _clause, old_hash = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=3, body=body, created_at=datetime(2026, 9, 20, 8, tzinfo=timezone.utc))
        cid = await _insert_candidate(pool, message_id=3, clause_idx=0, clause_hash=old_hash)

        # Scanner revises this SAME unjudged row mid-tick: new clause_hash,
        # attempts explicitly reset to 0 — the SAME value the judge already
        # read at selection time, so the attempts pin alone cannot catch it.
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE team_promise_candidates SET clause_hash = 'revised-by-scanner', attempts = 0 "
                "WHERE id = $1", cid,
            )

        outcome = await wtp._apply_attempt(pool, cid, old_hash, 0, False)
        assert outcome is None  # raced — the guard must still fail
        row = await _candidate_row(pool, cid)
        assert row["attempts"] == 0
        assert row["status"] == "unjudged"
        assert row["clause_hash"] == "revised-by-scanner"


# G3 (mutants M12/M13) — the earlier FOR SHARE lock test
# (test_for_share_lock_genuinely_blocks_a_concurrent_message_update) proves
# the SQL primitive works, called directly against a raw connection. It does
# NOT prove _apply_true's OWN transaction actually holds that lock through
# ITS OWN commit — a mutant that reads under FOR SHARE but in a SEPARATE,
# already-committed transaction (or drops the transaction wrapper entirely)
# would still pass that test. This slows _apply_true's own guarded UPDATE
# down with pg_sleep so a concurrent UPDATE has a real window to race it.
@pytest.mark.asyncio
async def test_g3_apply_true_holds_the_message_lock_through_its_own_commit(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "g3") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        clause, h = _seed_candidate_for_body(body)
        await _insert_wmc(pool, msg_id=4, body=body, created_at=datetime(2026, 9, 20, 8, tzinfo=timezone.utc))
        cid = await _insert_candidate(pool, message_id=4, clause_idx=0, clause_hash=h)

        # Stalls _apply_true's own guarded UPDATE for 1.2s, AFTER its FOR
        # SHARE read but BEFORE its commit — the window a competing writer
        # needs to prove the lock is (or is not) still held.
        slow_mark_true = wtp._JUDGE_MARK_TRUE_SQL.replace(
            "RETURNING id",
            "AND (SELECT count(*) FROM (SELECT pg_sleep(1.2)) AS _stall) = 1\nRETURNING id",
        )
        assert slow_mark_true != wtp._JUDGE_MARK_TRUE_SQL
        monkeypatch.setattr(wtp, "_JUDGE_MARK_TRUE_SQL", slow_mark_true)

        writer = await asyncpg.connect(host=pg_socket_dir, user="postgres", database="g3")
        judge_task = None
        update_task = None
        try:
            judge_task = asyncio.create_task(_apply_true(
                pool, cid, h, message_id=4, clause_idx=0, promise_type="send",
                due_at_hint=None, dry_run=False,
            ))
            # Deterministic wait, not a fixed guess: poll pg_stat_activity
            # (over the writer's own connection — the pool itself is
            # max_size=1 and already held by judge_task's transaction)
            # until _apply_true's stalled query is actually ACTIVE. A
            # loaded runner can make _apply_true slower to reach its FOR
            # SHARE read than any fixed sleep would assume, which used to
            # turn "the UPDATE is still blocked" into a false RED on
            # otherwise-correct code (round-1 council finding).
            #
            # `pid <> pg_backend_pid()` is LOAD-BEARING, not defensive
            # styling: without it the poll's own query text (which itself
            # contains the literal substring "_stall", inside its own
            # `'%_stall%'` pattern / this comment's literal) matches on the
            # very first iteration, so the loop breaks immediately and
            # waits for nothing — reintroducing the exact false-RED race
            # this fix exists to remove (delta-round finding, both seats,
            # independently). `position('_stall' in query) > 0` replaces
            # ILIKE's wildcard pattern for the same reason `_` is itself a
            # single-character ILIKE wildcard (kimi's delta-round finding),
            # so a query merely containing "install" would also match.
            deadline = asyncio.get_running_loop().time() + 5.0
            while True:
                row = await writer.fetchrow(
                    "SELECT 1 FROM pg_stat_activity "
                    "WHERE state = 'active' AND datname = current_database() "
                    "AND pid <> pg_backend_pid() "
                    "AND position('_stall' in query) > 0"
                )
                if row is not None:
                    break
                if asyncio.get_running_loop().time() > deadline:
                    raise TimeoutError("_apply_true's stalled query never went active within 5s")
                await asyncio.sleep(0.02)

            update_task = asyncio.create_task(
                writer.execute("UPDATE whatsapp_message_context SET body = 'edited' WHERE id = 4")
            )
            await asyncio.sleep(0.5)
            assert not update_task.done(), (
                "the message UPDATE completed while _apply_true's own transaction was "
                "still mid-flight — the lock is not held through _apply_true's own commit"
            )
            assert await judge_task == "true"
            await asyncio.wait_for(update_task, timeout=5.0)
        finally:
            # `gather(..., return_exceptions=True)` (not a `.done()`-gated
            # cancel+await) so a task that already finished EXCEPTIONALLY
            # before this block runs — e.g. judge_task raising before the
            # poll's timeout, or an assertion above firing mid-flight — is
            # still collected instead of left as an uncollected exception
            # (delta-round finding, codex).
            tasks = [t for t in (judge_task, update_task) if t is not None]
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await writer.close()

        promises = await _promises(pool)
        assert [p["promise_text"] for p in promises] == [clause]


# G4 (mutants M23/M46/M47) — --dry-run must write NOTHING, on every terminal
# path (true/false/invalid/quarantine/superseded), proven end-to-end through
# run_judge against a real database snapshot taken before and after.
@pytest.mark.asyncio
async def test_g4_dry_run_writes_nothing_on_any_path(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "g4") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
        body_true = "I will send it tomorrow"
        body_false = "I will call you tomorrow"
        body_invalid = "I will pay it tomorrow"
        body_invalid_ordinary = "I will fix it tomorrow"
        clause_true, hash_true = _seed_candidate_for_body(body_true)
        clause_false, hash_false = _seed_candidate_for_body(body_false)
        clause_invalid, hash_invalid = _seed_candidate_for_body(body_invalid)
        clause_invalid_ordinary, hash_invalid_ordinary = _seed_candidate_for_body(body_invalid_ordinary)

        await _insert_wmc(pool, msg_id=5, body=body_true, created_at=created_at)
        await _insert_wmc(pool, msg_id=6, body=body_false, created_at=created_at)
        await _insert_wmc(pool, msg_id=7, body=body_invalid, created_at=created_at)
        await _insert_wmc(pool, msg_id=11, body=body_invalid_ordinary, created_at=created_at)
        await _insert_candidate(pool, message_id=5, clause_idx=0, clause_hash=hash_true)
        await _insert_candidate(pool, message_id=6, clause_idx=0, clause_hash=hash_false)
        # attempts=4: one more invalid verdict would quarantine on a REAL run.
        await _insert_candidate(pool, message_id=7, clause_idx=0, clause_hash=hash_invalid, attempts=4)
        # attempts=0: an ORDINARY invalid verdict, not the quarantine
        # boundary — a mutant that only suppressed the dry-run write on the
        # quarantine branch (e.g. narrowing `_apply_attempt`'s unconditional
        # `if dry_run: return ...` to `if dry_run and attempts + 1 >=
        # _JUDGE_MAX_ATTEMPTS: return ...`) would still pass the attempts=4
        # case above while silently writing the attempts-increment here
        # (round-1 council finding — the attempts=4 case alone never
        # exercises this branch).
        await _insert_candidate(pool, message_id=11, clause_idx=0, clause_hash=hash_invalid_ordinary)
        # message_id 999 never inserted — a superseded candidate too.
        await _insert_candidate(pool, message_id=999, clause_idx=0, clause_hash="gone")

        verdicts = {
            clause_true: True, clause_false: False,
            clause_invalid: None, clause_invalid_ordinary: None,
        }
        monkeypatch.setattr(wtp, "_call_ollama", lambda _opener, clause: verdicts[clause])

        async def _snapshot():
            async with pool.acquire() as conn:
                candidates = await conn.fetch("SELECT * FROM team_promise_candidates ORDER BY id")
                promises = await conn.fetch("SELECT * FROM team_promises")
            return [dict(r) for r in candidates], [dict(r) for r in promises]

        before = await _snapshot()
        metrics = await run_judge(pool, limit=10, dry_run=True)

        # Every terminal path is exercised — this is the point of the test,
        # not incidental: a dry-run that skipped a branch would prove
        # nothing about that branch's own write-suppression.
        assert (
            metrics.true, metrics.false, metrics.invalid, metrics.quarantined,
            metrics.superseded, metrics.raced,
        ) == (1, 1, 1, 1, 1, 0)
        assert await _snapshot() == before


LEAD_INVALID = "ZQINV-7741"
LEAD_SUPERSEDED = "ZQSUP-8852"


# G7 (mutants M40/M41b/c and the truncating M40t/M41t/M40x) — no clause/body
# text reaches any record captured by caplog (propagating loggers, DEBUG and
# up; not just stdout/stderr) on the invalid-verdict and superseded
# (hash-mismatch) paths — the two paths a candidate reaches WITHOUT
# necessarily going through the top-level cli_main output line this file's
# other tests pin.
@pytest.mark.asyncio
async def test_g7_no_clause_text_in_log_records_on_invalid_and_superseded_paths(pg_socket_dir, monkeypatch, caplog):
    async with _fresh_database(pg_socket_dir, "g7") as pool:
        await _setup(pool)
        created_at = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)

        body_invalid = f"{LEAD_INVALID} I will send it to {POISON} tomorrow"
        clause_invalid, hash_invalid = _seed_candidate_for_body(body_invalid)
        await _insert_wmc(pool, msg_id=8, body=body_invalid, created_at=created_at)
        await _insert_candidate(pool, message_id=8, clause_idx=0, clause_hash=hash_invalid)

        body_superseded = f"{LEAD_SUPERSEDED} I will call {POISON} tomorrow"
        clause_superseded, _ = _seed_candidate_for_body(body_superseded)
        await _insert_wmc(pool, msg_id=9, body=body_superseded, created_at=created_at)
        # A stale hash the current body no longer matches -> superseded,
        # never reaches _call_ollama at all.
        await _insert_candidate(pool, message_id=9, clause_idx=0, clause_hash="stale-hash-not-in-body")

        monkeypatch.setattr(wtp, "_call_ollama", lambda _opener, _clause: None)

        with caplog.at_level(logging.DEBUG):
            metrics = await run_judge(pool, limit=10, dry_run=False)

        assert (metrics.invalid, metrics.superseded) == (1, 1)
        # getMessage() alone misses structured fields (`extra={...}`),
        # attached exceptions and stack info, and can itself raise on a
        # malformed msg/args pair, so every record is rendered defensively
        # and every non-standard attribute is folded into the searched text.
        standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

        def _render(record):
            try:
                message = record.getMessage()
            except (TypeError, ValueError):
                message = f"{record.msg!r} {record.args!r}"
            extras = {k: v for k, v in record.__dict__.items() if k not in standard}
            return f"{message} {extras!r} {record.exc_info!r} {record.exc_text} {record.stack_info}"

        log_text = "\n".join(_render(record) for record in caplog.records)
        assert POISON not in log_text
        assert clause_invalid not in log_text
        # A truncated leak (e.g. `clause_text[:20]`) passes the full-string
        # checks above and never reaches the PII tail, so the LEADING
        # fragment of each body/clause is asserted absent too: a unique,
        # non-PII marker sits in the first 20 characters of each body.
        assert LEAD_INVALID not in log_text
        assert LEAD_SUPERSEDED not in log_text
        # ...and a 5-character prefix cut of each marker (leaks that cut
        # shorter than 5 characters carry no unique signal to assert on).
        assert LEAD_INVALID[:5] not in log_text
        assert LEAD_SUPERSEDED[:5] not in log_text
        assert clause_invalid[:20] not in log_text
        assert body_superseded[:20] not in log_text
        assert clause_superseded not in log_text
        assert clause_superseded[:20] not in log_text


# G-LOW-2 (mutant M58, gate table, LOW) — _apply_true's OWN "message gone"
# branch (its second, FOR-SHARE read — reachable when the message existed
# at _judge_one's first read but is deleted before _apply_true's own
# transaction) must route through _JUDGE_MARK_SUPERSEDED_SQL and return
# "superseded", never "true" without writing anything. Called directly
# (bypassing _judge_one's own pre-check, which never even reaches this
# code path) against a message_id that was never inserted at all.
@pytest.mark.asyncio
async def test_g_low2_apply_true_second_read_message_gone_is_superseded_not_true(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "g_low2") as pool:
        await _setup(pool)
        body = "I will send it tomorrow"
        _clause, h = _seed_candidate_for_body(body)
        # message_id 10 is NEVER inserted into whatsapp_message_context —
        # simulates the message having been deleted between _judge_one's
        # first read and _apply_true's own second one.
        cid = await _insert_candidate(pool, message_id=10, clause_idx=0, clause_hash=h)

        outcome = await _apply_true(pool, cid, h, message_id=10, clause_idx=0,
                                     promise_type="send", due_at_hint=None, dry_run=False)

        assert outcome == "superseded"
        assert await _promises(pool) == []
        row = await _candidate_row(pool, cid)
        assert row["status"] == "superseded"
