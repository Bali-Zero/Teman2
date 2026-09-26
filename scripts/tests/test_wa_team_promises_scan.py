"""T3 promise gate tests — PR-2 (scanner -> team_promise_candidates). No real
DB: a fake pool/conn simulates whatsapp_message_context as an ordered,
already-eligible row set (direction/created_at filtering is the SQL's job,
asserted separately as static text below) and team_promise_candidates as an
in-memory conflict set. See test_wa_team_promises.py for the PR-1 fakes this
file deliberately does NOT import (parallel builder owns that file).
"""
from __future__ import annotations

import dataclasses
import math

import pytest

import scripts.wa_team_promises as wtp
from scripts.wa_team_promises import (
    ScanMetrics,
    _CANDIDATE_INSERT_SQL,
    _digest_line,
    _hash_clause,
    _match_clause,
    _SCAN_SELECT_SQL,
    _split_clauses,
    run_scan,
    run_scan_batch,
)


class _FakeTxn:
    def __init__(self, log):
        self._log = log

    async def __aenter__(self):
        self._log.append("BEGIN")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._log.append("ROLLBACK" if exc_type is not None else "COMMIT")
        return False


class _FakeConn:
    """`rows` is the FULL ordered dataset (id, body); fetch() applies the
    id-cursor + LIMIT itself so tests can drive multi-batch runs exactly as
    Postgres would, without re-implementing direction/created_at filtering
    (that half of the contract is asserted as static SQL text, not fakeable
    meaningfully)."""

    def __init__(self, rows, log, unjudged_count=0):
        self._rows = rows
        self._log = log
        self._inserted: set[tuple[int, int]] = set()
        self._unjudged_count = unjudged_count

    def transaction(self):
        return _FakeTxn(self._log)

    async def fetch(self, sql, watermark, batch_size):
        self._log.append(("fetch", sql, watermark, batch_size))
        eligible = [r for r in self._rows if r["id"] > watermark]
        return eligible[:batch_size]

    async def execute(self, sql, message_id, clause_idx, clause_hash, promise_type, cue, due_at_hint):
        self._log.append(("execute", sql, message_id, clause_idx, promise_type))
        key = (message_id, clause_idx)
        if key in self._inserted:
            return "INSERT 0 0"
        self._inserted.add(key)
        return "INSERT 0 1"

    async def fetchval(self, sql):
        self._log.append(("fetchval", sql))
        return self._unjudged_count


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_exc):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


def _rows(n, body_fn=lambda i: f"i will send it tomorrow (msg {i})"):
    return [{"id": i, "body": body_fn(i)} for i in range(1, n + 1)]


# A — clause splitter: `.`, `!`, `?`, `;`, newline (round-2 review's HIGH —
# the predecessor dropped `;`/newline), plus a conjunction boundary.


@pytest.mark.parametrize("body,expected", [
    ("I will check today. I will send tomorrow", ["I will check today", "I will send tomorrow"]),
    ("saya cek dulu; akan saya kirim besok", ["saya cek dulu", "akan saya kirim besok"]),
    ("controllo oggi\nti aggiorno domani", ["controllo oggi", "ti aggiorno domani"]),
    ("sudah saya cek, tapi akan saya submit besok",
     ["sudah saya cek,", "tapi akan saya submit besok"]),
    ("I'll check it but I will send it later",
     ["I'll check it", "but I will send it later"]),
])
def test_split_clauses_covers_punctuation_semicolon_newline_and_conjunction(body, expected):
    assert _split_clauses(body) == expected


def test_split_clauses_never_produces_empty_or_whitespace_only_entries():
    assert _split_clauses("...   ;;\n\n   ") == []


# B — matcher: no dedup, no past-tense discard at this stage (the judge in
# PR-3 owns both calls — round-2 review's other HIGH on the predecessor).


def test_match_clause_accepts_a_past_tense_commitment_the_judge_will_rule_on():
    """"already sent" IS a v1 catalog match — PR-2 must propose it as a
    candidate, never discard it as fulfilment itself. Discarding here would
    resurrect the exact defect (b) the T37 spec calls out."""
    result = _match_clause("already sent it yesterday")
    assert result is not None
    promise_type, cue, due_hint = result
    assert promise_type == "send"
    assert due_hint is None


def test_match_clause_captures_temporal_cue_as_a_label_not_a_timestamp():
    promise_type, cue, due_hint = _match_clause("i will send it tomorrow")
    assert promise_type == "send"
    assert due_hint == "tomorrow"


def test_match_clause_cue_is_always_drawn_from_the_closed_catalog_vocabulary():
    """`cue` cannot carry a name/phone/client id: every catalog pattern is a
    fixed keyword sequence with no open capture group, so match.group(0) is
    always one of the catalog's own phrases."""
    clause = "i will send it to +6281234567890 tomorrow, ask for Jane Doe"
    promise_type, cue, _due = _match_clause(clause)
    assert "+6281234567890" not in cue
    assert "Jane Doe" not in cue


def test_match_clause_no_catalog_hit_returns_none():
    assert _match_clause("the weather is nice today") is None


def test_hash_clause_is_stable_and_case_whitespace_insensitive():
    assert _hash_clause("I Will   Send  Tomorrow") == _hash_clause("i will send tomorrow")
    assert _hash_clause("i will send tomorrow") != _hash_clause("i will check tomorrow")


# C — batch/cursor: id-based, never OFFSET (the predecessor's 81-minute
# same-200-rows bug). Watermark advances, and the 30-day floor rides every
# query including the seed (asserted as static SQL text — no OFFSET path
# exists in this file to regress into).


def test_scan_select_sql_has_no_offset_and_carries_the_30_day_floor_on_every_call():
    assert "OFFSET" not in wtp.__dict__["_SCAN_SELECT_SQL"].upper()
    assert "id > $1" in _SCAN_SELECT_SQL
    assert "interval '30 days'" in _SCAN_SELECT_SQL
    assert "direction = 'outbound'" in _SCAN_SELECT_SQL


@pytest.mark.asyncio
async def test_run_scan_batch_advances_watermark_by_max_row_id_seen():
    log: list = []
    conn = _FakeConn(_rows(5), log)
    pool = _FakePool(conn)
    metrics = ScanMetrics()

    new_watermark = await run_scan_batch(
        pool, watermark=0, batch_size=200, dry_run=False, metrics=metrics,
    )

    assert new_watermark == 5
    assert metrics.scanned == 5
    assert metrics.candidates_new == 5  # every synthetic row matches "send"


@pytest.mark.asyncio
async def test_run_scan_batch_empty_result_returns_the_same_watermark():
    log: list = []
    conn = _FakeConn(_rows(3), log)
    pool = _FakePool(conn)
    metrics = ScanMetrics()

    new_watermark = await run_scan_batch(
        pool, watermark=999, batch_size=200, dry_run=False, metrics=metrics,
    )

    assert new_watermark == 999
    assert metrics.scanned == 0


@pytest.mark.asyncio
async def test_run_scan_drains_multiple_batches_with_a_strictly_advancing_cursor(monkeypatch):
    """Regression for the v1 predecessor's 81-minute same-200-rows bug: the
    watermark argument passed to fetch() on batch N+1 must be STRICTLY
    greater than on batch N — an OFFSET-shaped pager (or one that forgot to
    persist between batches) would replay the same `$1` forever."""
    saved: list[int] = []
    monkeypatch.setattr(wtp, "_save_scan_watermark", lambda v: saved.append(v))
    monkeypatch.setattr(wtp, "_load_scan_watermark", lambda: 0)

    log: list = []
    total = 450
    conn = _FakeConn(_rows(total), log)
    pool = _FakePool(conn)

    metrics = await run_scan(pool, batch_size=200, dry_run=False)

    assert metrics.scanned == total
    fetch_watermarks = [call[2] for call in log if call[0] == "fetch"]
    assert fetch_watermarks == sorted(set(fetch_watermarks)), "watermark must strictly advance"
    assert fetch_watermarks[0] == 0
    assert len(fetch_watermarks) == math.ceil(total / 200) + 1  # last call empty, ends the loop
    # the cursor is saved per batch, not once at the very end — a crash
    # mid-tick after batch 1 must not lose batch 1's progress.
    assert saved == [200, 400, 450]


@pytest.mark.asyncio
async def test_run_scan_dry_run_writes_nothing_no_candidates_no_watermark(monkeypatch):
    save_calls: list[int] = []
    monkeypatch.setattr(wtp, "_save_scan_watermark", lambda v: save_calls.append(v))
    load_calls = {"n": 0}

    def _spy_load():
        load_calls["n"] += 1
        return 0

    monkeypatch.setattr(wtp, "_load_scan_watermark", _spy_load)

    log: list = []
    conn = _FakeConn(_rows(5), log)
    pool = _FakePool(conn)

    metrics = await run_scan(pool, batch_size=200, dry_run=True)

    assert metrics.scanned == 5
    assert metrics.candidates_new == 5  # counted, never persisted
    assert save_calls == []
    assert load_calls["n"] == 0  # dry-run never even reads the real watermark
    assert not any(call[0] == "execute" for call in log)  # no INSERT attempted


@pytest.mark.asyncio
async def test_run_scan_batch_on_conflict_do_nothing_is_idempotent_on_replay():
    log: list = []
    conn = _FakeConn(_rows(4), log)
    pool = _FakePool(conn)

    m1 = ScanMetrics()
    await run_scan_batch(pool, watermark=0, batch_size=200, dry_run=False, metrics=m1)
    assert m1.candidates_new == 4

    # same rows again (simulating a watermark that was NOT advanced by the
    # caller) — ON CONFLICT DO NOTHING means zero NEW candidates, not an error.
    m2 = ScanMetrics()
    await run_scan_batch(pool, watermark=0, batch_size=200, dry_run=False, metrics=m2)
    assert m2.candidates_new == 0
    assert m2.scanned == 4


@pytest.mark.asyncio
async def test_candidate_insert_uses_on_conflict_do_nothing_on_message_clause():
    assert "ON CONFLICT (message_id, clause_idx) DO NOTHING" in _CANDIDATE_INSERT_SQL


# D — lock: exclusive, non-blocking, releasable (scar #5 sibling-race).


def test_scan_lock_is_exclusive_then_releasable(tmp_path, monkeypatch):
    monkeypatch.setattr(wtp, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wtp, "_SCAN_LOCK_FILE", tmp_path / "scan.lock")

    fd1 = wtp._acquire_scan_lock_or_none()
    assert fd1 is not None
    fd2 = wtp._acquire_scan_lock_or_none()
    assert fd2 is None  # second holder refused, not blocked

    wtp._release_scan_lock(fd1)
    fd3 = wtp._acquire_scan_lock_or_none()
    assert fd3 is not None
    wtp._release_scan_lock(fd3)


# E — digest: counts only. A clause, name, phone or client id must have NO
# path into the line the gateway sends.


def test_digest_line_is_exactly_the_two_counts():
    assert _digest_line(3, 7) == "promises: candidates new 3, unjudged 7"


def test_digest_line_only_ever_accepts_the_two_int_counts():
    with pytest.raises(TypeError):
        _digest_line("3 (client 42, +628123456789)", 7)  # type: ignore[arg-type]


def test_scan_metrics_every_field_is_a_bare_int():
    """Structural guard: the digest is built ONLY from ScanMetrics fields —
    if a future edit ever added a str field (e.g. a body/clause snippet
    "for debugging"), this test fails before that field could reach a
    Telegram message."""
    for f in dataclasses.fields(ScanMetrics):
        assert f.type == "int", f"{f.name} is {f.type}, not int"


def test_send_scan_digest_message_carries_only_the_two_counts(monkeypatch):
    captured = {}

    class _FakeResult:
        returncode = 0
        stderr = "tg_notify: spooled\n"

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeResult()

    monkeypatch.setattr(wtp.subprocess, "run", _fake_run)
    wtp._send_scan_digest(5, 12)

    text = captured["argv"][-1]
    assert text == "promises: candidates new 5, unjudged 12"
    poison = ["client_id", "phone", "+62", "clause", "message_id"]
    assert not any(p in text for p in poison)


def test_send_scan_digest_never_raises_on_gateway_failure(monkeypatch):
    def _boom(*_a, **_kw):
        raise OSError("gateway unreachable")

    monkeypatch.setattr(wtp.subprocess, "run", _boom)
    result = wtp._send_scan_digest(1, 2)  # must not raise
    assert result is None
