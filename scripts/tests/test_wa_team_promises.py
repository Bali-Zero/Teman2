"""T3 promise extractor tests — no real DB (round 1, after codex BLOCK on
PR #7316; spec_7316_r1.md A-F).

Covers: clause-scoped tense split guilt/innocence (id/en/it, including the
round-0 corpus verbatim), the local-judge layer (mocked, guilt/innocence +
fail-fast unjudged), the Pro-local DSN guard, error-line sanitization, the
catalog index verification, thread_key, due_at cue vs D6 default, watermark
round-trip, the rolling 30-day backfill floor, and a payload test proving
the digest line can never carry a body window or a name.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from scripts.wa_team_promises import (
    DEFAULT_DUE_AT_HOURS,
    DsnGuardError,
    ExtractMetrics,
    _BATCH_SQL,
    _Candidate,
    _build_dsn,
    _digest_line,
    _fail_line,
    _guard_local_dsn,
    _load_watermark,
    _save_watermark,
    _thread_key,
    find_candidates_in_message,
    judge_candidates,
    run_tick,
    verify_unique_index,
)
import scripts.wa_team_promises as wa_team_promises

BASE = _dt.datetime(2026, 9, 25, 10, 0, tzinfo=_dt.timezone.utc)


def _scan(body: str, base: _dt.datetime = BASE):
    return find_candidates_in_message(
        message_id=1, client_id=42, team_member_phone="628110000000",
        team_member_email="adit@balizero.com", chat_jid="628299999999@s.whatsapp.net",
        counterpart_phone=None, counterpart_lid=None, body=body, base_dt=base,
    )


def _mk(text, ptype="send", from_cue=False):
    return _Candidate(
        message_id=1, conversation_id=None, client_id=5, thread_key="k",
        team_member_email="a@balizero.com", promise_text=text, promise_type=ptype,
        due_at=BASE + _dt.timedelta(hours=DEFAULT_DUE_AT_HOURS), from_cue=from_cue,
    )


# ---------------------------------------------------------------------------
# Clause-scoped candidate generation (Layer 1: pure, deterministic)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "akan saya kirim dokumennya besok pagi",
    "I will send the documents tomorrow",
    "invierò i documenti domani",
])
def test_innocence_future_tense_is_a_candidate(body):
    candidates, fulfilments = _scan(body)
    assert len(candidates) == 1
    assert candidates[0].promise_type == "send"
    assert fulfilments == 0


@pytest.mark.parametrize("body", [
    "sudah saya kirim dokumennya tadi pagi",
    "I have already sent the documents",
    "già inviato tutto stamattina",
])
def test_guilt_past_tense_narrow_match_is_not_a_candidate(body):
    candidates, fulfilments = _scan(body)
    assert candidates == []
    assert fulfilments == 1


# round-0 corpus (review_7316_out.txt finding #3), verbatim.
@pytest.mark.parametrize("body", [
    "sudah saya cek",
    "telah saya kirim",
    "sudah saya update",
])
def test_round0_past_marker_outside_narrow_match_is_not_a_candidate(body):
    """The past marker sits BEFORE the matched verb phrase (e.g. "saya cek"
    alone is tense-neutral) — clause-level PAST_TENSE_RE must still catch
    it because it scans the WHOLE clause, not just the regex match span."""
    candidates, fulfilments = _scan(body)
    assert candidates == [], f"{body!r} must not become a candidate"
    assert fulfilments == 1


@pytest.mark.parametrize("body,expect_type", [
    ("already sent … I will send tomorrow", "send"),
    ("sudah kirim tadi … akan saya kirim lagi besok", "send"),
    ("gia inviato … invierò domani", "send"),
])
def test_round0_mixed_past_and_future_keeps_the_future_one(body, expect_type):
    """Dedup must apply AFTER a clause is confirmed non-past — marking the
    type "seen" on the past clause alone used to swallow the genuine future
    commitment right after it (round-0 bug #2)."""
    candidates, fulfilments = _scan(body)
    assert [c.promise_type for c in candidates] == [expect_type]
    assert fulfilments == 1


@pytest.mark.parametrize("body,ptype", [
    ("Please send today", "send"),
    ("non invierò i documenti", "send"),
    ("il processo è terminato ieri", "process"),
])
def test_round0_ambiguous_clauses_still_become_candidates_for_the_judge(body, ptype):
    """Imperative, negated-future and past-narrative clauses are NOT
    resolvable by regex alone (round-0 bug #3's remaining cases) — the
    candidate layer still proposes them; judge_candidates (below) is what
    must reject them."""
    candidates, _ = _scan(body)
    assert [c.promise_type for c in candidates] == [ptype]


# ---------------------------------------------------------------------------
# Local judge (Layer 2: mocked — never calls a real Ollama endpoint)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_judge_innocence_accepts_a_real_future_commitment(monkeypatch):
    async def fake_true(text):
        return {"future_commitment_by_sender": True, "due_hint": None}
    monkeypatch.setattr(wa_team_promises, "_ollama_judge", fake_true)
    accepted, jt, jf, unj = await judge_candidates([_mk("I will send tomorrow")], BASE)
    assert (len(accepted), jt, jf, unj) == (1, 1, 0, 0)


@pytest.mark.asyncio
async def test_judge_guilt_rejects_imperative_negation_and_narrative(monkeypatch):
    async def fake_false(text):
        return {"future_commitment_by_sender": False, "due_hint": None}
    monkeypatch.setattr(wa_team_promises, "_ollama_judge", fake_false)
    candidates = [
        _mk("Please send today"),
        _mk("non invierò i documenti"),
        _mk("il processo è terminato ieri", ptype="process"),
    ]
    accepted, jt, jf, unj = await judge_candidates(candidates, BASE)
    assert (len(accepted), jt, jf, unj) == (0, 0, 3, 0)


@pytest.mark.asyncio
async def test_judge_unreachable_marks_unjudged_and_fails_fast(monkeypatch):
    calls = {"n": 0}

    async def fake_unreachable(text):
        calls["n"] += 1
        return None
    monkeypatch.setattr(wa_team_promises, "_ollama_judge", fake_unreachable)
    accepted, jt, jf, unj = await judge_candidates([_mk("a"), _mk("b"), _mk("c")], BASE)
    assert (len(accepted), jt, jf, unj) == (0, 0, 0, 3)
    assert calls["n"] == 1, "a dead Ollama must not be retried once per remaining candidate"


@pytest.mark.asyncio
async def test_judge_uses_due_hint_only_when_the_clause_had_no_cue(monkeypatch):
    async def fake_hint(text):
        return {"future_commitment_by_sender": True, "due_hint": "tomorrow"}
    monkeypatch.setattr(wa_team_promises, "_ollama_judge", fake_hint)
    accepted, *_ = await judge_candidates([_mk("I will check this for you")], BASE)
    assert accepted[0].from_cue is True
    assert accepted[0].due_at == BASE + _dt.timedelta(hours=24)


# ---------------------------------------------------------------------------
# B — Pro-local DSN guard
# ---------------------------------------------------------------------------

def test_dsn_guard_innocence_local_dsn_passes():
    assert _guard_local_dsn("postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev") is None
    assert _guard_local_dsn("postgresql://nuzantara@localhost:5432/nuzantara_dev") is None


@pytest.mark.parametrize("dsn", [
    "postgresql://user:pass@remote-fly-host.internal:5432/nuzantara_dev",
    "postgresql://nuzantara@127.0.0.1:5432/some_other_db",
])
def test_dsn_guard_guilt_rejects_remote_host_and_wrong_dbname(dsn):
    with pytest.raises(DsnGuardError):
        _guard_local_dsn(dsn)


def test_dsn_guard_guilt_rejects_fly_environment(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "nuzantara-rag")
    with pytest.raises(DsnGuardError):
        _guard_local_dsn("postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev")


def test_build_dsn_has_no_database_url_fallback(monkeypatch):
    monkeypatch.delenv("WA_TEAM_PROMISES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@remote-fly-host.internal/other_db")
    # DATABASE_URL must be ignored entirely — _build_dsn falls back to the
    # guarded local default, not to the generic env var.
    assert _build_dsn() == wa_team_promises.DEFAULT_DSN


# ---------------------------------------------------------------------------
# C — errors never carry data
# ---------------------------------------------------------------------------

def test_fail_line_never_leaks_exception_message_or_detail():
    class SyntheticFKViolation(Exception):
        sqlstate = "23503"

    exc = SyntheticFKViolation(
        'insert or update on table "team_promises" violates foreign key '
        'constraint "team_promises_client_id_fkey"\nDETAIL:  Key (client_id)'
        '=(424242) is not present in table "clients".'
    )
    line = _fail_line(exc, "tick", None)
    assert line == "wa_team_promises: FAIL SyntheticFKViolation sqlstate=23503 stage=tick counts=n/a"
    assert "424242" not in line
    assert "DETAIL" not in line
    assert "clients" not in line


def test_fail_line_falls_back_to_dash_sqlstate_for_non_postgres_errors():
    line = _fail_line(TimeoutError("connect timed out to 10.0.0.5"), "connect", None)
    assert line == "wa_team_promises: FAIL TimeoutError sqlstate=- stage=connect counts=n/a"
    assert "10.0.0.5" not in line


def test_fail_line_counts_are_numeric_only():
    metrics = ExtractMetrics(total_scanned=10, candidate_messages=3, promises_created=2)
    line = _fail_line(RuntimeError("boom"), "tick", metrics)
    assert "boom" not in line
    assert "total_scanned=10" in line


# ---------------------------------------------------------------------------
# A — catalog index verification (fake connection, no real DB)
# ---------------------------------------------------------------------------

class _FakeConn:
    def __init__(self, row):
        self._row = row

    async def fetchrow(self, _sql, _table, _index):
        return self._row


@pytest.mark.asyncio
async def test_verify_unique_index_innocence_correct_definition():
    row = {"indisunique": True, "indisvalid": True, "has_predicate": False,
           "columns": ["message_id", "promise_type"]}
    result = await verify_unique_index(_FakeConn(row), "team_promises",
                                        "uix_team_promises_msg_type", ["message_id", "promise_type"])
    assert result is None


@pytest.mark.parametrize("row", [
    {"indisunique": True, "indisvalid": True, "has_predicate": False, "columns": ["message_id"]},
    {"indisunique": False, "indisvalid": True, "has_predicate": False,
     "columns": ["message_id", "promise_type"]},
    {"indisunique": True, "indisvalid": False, "has_predicate": False,
     "columns": ["message_id", "promise_type"]},
    {"indisunique": True, "indisvalid": True, "has_predicate": True,
     "columns": ["message_id", "promise_type"]},
    None,
])
@pytest.mark.asyncio
async def test_verify_unique_index_guilt_aborts_on_any_mismatch(row):
    with pytest.raises(RuntimeError):
        await verify_unique_index(_FakeConn(row), "team_promises",
                                   "uix_team_promises_msg_type", ["message_id", "promise_type"])


# ---------------------------------------------------------------------------
# E — rolling 30-day backfill floor on EVERY tick, not just the seed
# ---------------------------------------------------------------------------

def test_batch_sql_always_carries_the_30_day_created_at_floor():
    """round-0 bug #6: an id-only seed fell back to 0 with no rows in the
    window, then scanned the FULL archive unbounded. The fix bakes the
    floor into the batch query itself, so watermark=0 is always safe."""
    assert "created_at >= now() - interval '30 days'" in _BATCH_SQL
    assert "id > $1" in _BATCH_SQL


# ---------------------------------------------------------------------------
# run_tick — the batch cursor must ADVANCE (Pro dry-run caught this live:
# offset_id was set once before the loop and never updated, so every batch
# refetched the SAME 200 rows — 196,800 "scanned" rows / 81 minutes wall
# time on a 30-day window that should hold a few thousand at most, until a
# flaky Ollama call finally broke the loop). Fake pool/conn, no real DB;
# `fetch` filters an in-memory row set by `id > offset_id` exactly like the
# real SQL, so a non-advancing cursor reproduces the bug's shape here too.
# ---------------------------------------------------------------------------

class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_exc):
        return False


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


class _FakeTickConn:
    def __init__(self, rows):
        self._rows = rows
        self.fetch_offsets: list[int] = []

    async def fetch(self, _sql, offset_id, limit):
        self.fetch_offsets.append(offset_id)
        return [r for r in self._rows if r["id"] > offset_id][:limit]

    def transaction(self):
        return _FakeTxn()

    async def execute(self, *_args):
        return "INSERT 0 1"

    async def fetchrow(self, *_args):
        return {"open_total": 0, "overdue_total": 0}


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


def _row(rid: int) -> dict:
    return {
        "id": rid, "client_id": None, "team_member_phone": "628", "team_member_email": None,
        "chat_jid": "jid", "counterpart_phone": None, "counterpart_lid": None,
        "base_dt": BASE, "body": "no promise pattern here, plain text",
    }


@pytest.mark.asyncio
async def test_run_tick_cursor_advances_across_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(wa_team_promises, "WATERMARK_FILE", tmp_path / "wm.txt")
    conn = _FakeTickConn([_row(1), _row(2), _row(3)])
    pool = _FakePool(conn)

    metrics = await run_tick(pool, apply=False, limit=10, batch_size=2)

    assert metrics.total_scanned == 3, (
        "a non-advancing cursor re-scans the same batch until `limit` is "
        "exhausted — 10 here, not 3"
    )
    assert conn.fetch_offsets == [0, 2, 3]


# ---------------------------------------------------------------------------
# due_at: cue vs D6 default
# ---------------------------------------------------------------------------

def test_due_at_uses_temporal_cue_when_present():
    candidates, _ = _scan("akan saya kirim besok")
    assert candidates[0].from_cue is True
    assert candidates[0].due_at == BASE + _dt.timedelta(hours=24)


def test_due_at_falls_back_to_d6_default_without_a_cue():
    candidates, _ = _scan("I will check this for you")
    assert candidates[0].from_cue is False
    assert candidates[0].due_at == BASE + _dt.timedelta(hours=DEFAULT_DUE_AT_HOURS)


# ---------------------------------------------------------------------------
# thread_key
# ---------------------------------------------------------------------------

def test_thread_key_prefers_chat_jid_then_counterpart_phone_then_lid():
    via_jid = _thread_key("6281", "jid@x", "6282", "lid@x")
    via_phone = _thread_key("6281", None, "6282", "lid@x")
    via_lid = _thread_key("6281", None, None, "lid@x")
    assert via_jid != via_phone != via_lid
    assert _thread_key(None, "jid@x", None, None) is None


# ---------------------------------------------------------------------------
# Watermark idempotency
# ---------------------------------------------------------------------------

def test_watermark_round_trip_and_idempotent_reload(tmp_path, monkeypatch):
    wm_file = tmp_path / "wa_team_promises_last_id.txt"
    monkeypatch.setattr(wa_team_promises, "WATERMARK_FILE", wm_file)
    assert _load_watermark() is None

    _save_watermark(1000)
    assert _load_watermark() == 1000
    _save_watermark(1000)
    assert _load_watermark() == 1000
    assert wm_file.read_text().strip() == "1000"


# ---------------------------------------------------------------------------
# Payload test — the digest line must never carry a body window or a name
# ---------------------------------------------------------------------------

def test_digest_line_never_carries_a_body_window_or_a_name():
    secret_client_name = "Ida Ayu Ratih Purnamasari"
    body = f"akan saya kirim paspor {secret_client_name} besok ke kantor imigrasi"
    candidates, _ = _scan(body)
    assert candidates
    assert secret_client_name in candidates[0].promise_text  # stored locally — OK

    metrics = ExtractMetrics(promises_created=3, open_total=7, overdue_total=2, unjudged=1,
                              by_type={"send": 3})
    line = _digest_line(metrics)

    assert line == "promises: new 3 open 7 overdue 2 unjudged 1"
    assert secret_client_name not in line
    assert body not in line
    assert candidates[0].promise_text not in line
