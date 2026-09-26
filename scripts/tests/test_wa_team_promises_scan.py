"""T3 promise gate tests — PR-2 (scanner -> team_promise_candidates), pure
unit half. No real DB here: batch/cursor/upsert semantics moved to
test_wa_team_promises_scan_real_pg.py (opt-in, WA_TEAM_PROMISES_REAL_PG=1) —
REWORK per the spec addendum's A7, since the fake pool/conn fixtures that
used to live here re-implemented the cursor and ON CONFLICT logic in Python
instead of exercising the real SQL. This file keeps the splitter/catalog/
digest/lock tests, which need no DB. See test_wa_team_promises.py for the
PR-1 fakes this file deliberately does NOT import (parallel builder owns
that file).
"""
from __future__ import annotations

import dataclasses
import logging

import pytest

import scripts.wa_team_promises as wtp
from scripts.wa_team_promises import (
    ScanMetrics,
    _CANDIDATE_UPSERT_SQL,
    _digest_line,
    _fail_line,
    _hash_clause,
    _match_clause,
    _SCAN_HI_SQL,
    _SCAN_SELECT_SQL,
    _split_clauses,
)


# A — clause splitter: `.`, `!`, `?`, `;`, newline (round-2 review's HIGH —
# the predecessor dropped `;`/newline), plus a conjunction boundary
# (EN/ID/IT: but/tapi/ma..., and — REWORK A3 — and/dan/serta/e).


@pytest.mark.parametrize("body,expected", [
    ("I will check today. I will send tomorrow", ["I will check today", "I will send tomorrow"]),
    ("saya cek dulu; akan saya kirim besok", ["saya cek dulu", "akan saya kirim besok"]),
    ("controllo oggi\nti aggiorno domani", ["controllo oggi", "ti aggiorno domani"]),
    ("sudah saya cek, tapi akan saya submit besok",
     ["sudah saya cek,", "tapi akan saya submit besok"]),
    ("I'll check it but I will send it later",
     ["I'll check it", "but I will send it later"]),
    # REWORK A3 — conjunction split fixed BEFORE first activation.
    ("I will send tomorrow and I will check today",
     ["I will send tomorrow", "and I will check today"]),
    ("akan saya kirim besok dan saya akan cek hari ini",
     ["akan saya kirim besok", "dan saya akan cek hari ini"]),
    ("akan saya kirim besok serta saya akan cek hari ini",
     ["akan saya kirim besok", "serta saya akan cek hari ini"]),
    ("controllo oggi e ti aggiorno domani",
     ["controllo oggi", "e ti aggiorno domani"]),
    ("Controllo oggi E ti aggiorno domani",  # case-insensitive
     ["Controllo oggi", "E ti aggiorno domani"]),
])
def test_split_clauses_covers_punctuation_semicolon_newline_and_conjunction(body, expected):
    assert _split_clauses(body) == expected


@pytest.mark.parametrize("body", [
    "the candidate will send it tomorrow",  # "and" inside "candidate"
    "my Android will send it tomorrow",  # "and" inside "Android"
    "che cosa mi manda domani",  # "e" inside "che"
    "vado in sede domani",  # "e" inside "sede"
])
def test_split_clauses_conjunction_boundary_is_whole_word_only(body):
    """A bare substring match ("and" inside "candidate"/"Android", "e" inside
    "che"/"sede") must never split — the addendum's innocence case for A3."""
    assert _split_clauses(body) == [body]


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


# C — SQL text: static assertions only (the real cursor/upsert behavior is
# proven against real Postgres in test_wa_team_promises_scan_real_pg.py).


def test_scan_queries_have_no_offset_and_carry_the_30_day_floor_on_every_call():
    for sql in (_SCAN_HI_SQL, _SCAN_SELECT_SQL):
        assert "OFFSET" not in sql.upper()
        assert "interval '30 days'" in sql
        assert "direction = 'outbound'" in sql
    assert "id > $1" in _SCAN_SELECT_SQL and "id <= $2" in _SCAN_SELECT_SQL


def test_candidate_upsert_revises_only_unjudged_rows_with_changed_text():
    """REWORK A2: the DO UPDATE is guarded to unjudged rows whose clause
    text actually changed — a judged/quarantined row, or an unchanged
    resubmit, must be untouched (asserted for real in
    test_wa_team_promises_scan_real_pg.py)."""
    assert "ON CONFLICT (message_id, clause_idx) DO UPDATE SET" in _CANDIDATE_UPSERT_SQL
    assert "status = 'unjudged'" in _CANDIDATE_UPSERT_SQL
    assert "clause_hash IS DISTINCT FROM EXCLUDED.clause_hash" in _CANDIDATE_UPSERT_SQL
    assert "RETURNING (xmax = 0) AS inserted" in _CANDIDATE_UPSERT_SQL


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
# path into the line the gateway sends. REWORK A4: three counts now
# (today/revised/unjudged); REWORK A6: the gateway-failure path is sanitized.


def test_digest_line_is_exactly_the_three_counts():
    assert _digest_line(3, 1, 7) == "promises: candidates today 3 (revised 1), unjudged 7"


def test_digest_line_only_ever_accepts_int_counts():
    with pytest.raises(TypeError):
        _digest_line("3 (client 42, +628123456789)", 0, 7)  # type: ignore[arg-type]


def test_scan_metrics_every_field_is_a_bare_int():
    """Structural guard: the digest is built ONLY from ScanMetrics-shaped
    counts — if a future edit ever added a str field (e.g. a body/clause
    snippet "for debugging"), this test fails before that field could reach
    a Telegram message."""
    for f in dataclasses.fields(ScanMetrics):
        assert f.type == "int", f"{f.name} is {f.type}, not int"


def test_send_scan_digest_message_carries_only_the_three_counts_and_day_key(monkeypatch):
    captured = {}

    class _FakeResult:
        returncode = 0
        stderr = "tg_notify: spooled\n"

    def _fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeResult()

    monkeypatch.setattr(wtp.subprocess, "run", _fake_run)
    wtp._send_scan_digest(5, 2, 12, day_label="2026-09-26")

    argv = captured["argv"]
    text = argv[-1]
    assert text == "promises: candidates today 5 (revised 2), unjudged 12"
    poison = ["client_id", "phone", "+62", "clause", "message_id"]
    assert not any(p in text for p in poison)
    dedup_idx = argv.index("--dedup-key")
    assert argv[dedup_idx + 1] == "wa-team-promises:2026-09-26"


def test_send_scan_digest_never_raises_on_gateway_failure(monkeypatch):
    def _boom(*_a, **_kw):
        raise OSError("gateway unreachable")

    monkeypatch.setattr(wtp.subprocess, "run", _boom)
    result = wtp._send_scan_digest(1, 0, 2, day_label="2026-09-26")  # must not raise
    assert result is None


def test_send_scan_digest_sanitizes_a_poisoned_exception_text(monkeypatch, caplog):
    """REWORK A6: the gateway-failure warning used to print str(exc)
    directly — this proves a poisoned exception message never reaches the
    log line, only the sanitized _fail_line() form does."""
    poison = "SYNTHETIC_CLIENT_PII +6281234567890 client_id=424242"

    def _boom(*_a, **_kw):
        raise RuntimeError(poison)

    monkeypatch.setattr(wtp.subprocess, "run", _boom)
    with caplog.at_level(logging.WARNING, logger="wa_team_promises"):
        wtp._send_scan_digest(1, 0, 2, day_label="2026-09-26")

    full_log = "\n".join(r.message for r in caplog.records)
    assert poison not in full_log
    assert "+6281234567890" not in full_log
    assert "client_id=424242" not in full_log
    assert full_log == _fail_line(RuntimeError(poison), "digest")
