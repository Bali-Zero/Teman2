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
        # supersede it for a real out-of-band hash change).
        ok = await _apply_true(
            pool, cid, original_hash, message_id=908, promise_text="I will send it tomorrow",
            promise_type="send", due_at=created_at + timedelta(hours=24), dry_run=False,
        )

        assert ok is False
        assert await _promises(pool) == []
        row = await _candidate_row(pool, cid)
        assert row["status"] == "unjudged"  # untouched — the scanner's own revision stands
        assert row["clause_hash"] == new_hash


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
