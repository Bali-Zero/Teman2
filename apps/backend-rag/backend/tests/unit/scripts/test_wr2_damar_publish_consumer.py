"""Unit tests for scripts/wr2_damar_publish_consumer.py — STRATO 2.

Tests the pure parser and batch-processing logic with an injected mark_fn — no
Postgres, no queue file, no asyncpg. Covers the real-message shapes (Italian
PUBBLICATO with double-B, English PUBLISHED, noise, malformed) and the
cursor/unmatched accounting that protects the loop from silently dropping or
mis-applying a signal.
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Load the module from repo-root scripts/ ────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[6]
_MODULE_PATH = _REPO_ROOT / "scripts" / "wr2_damar_publish_consumer.py"
_spec = importlib.util.spec_from_file_location("wr2_damar_publish_consumer", _MODULE_PATH)
dc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = dc
_spec.loader.exec_module(dc)

# A real ref-code (sha1-derived) for one of the live items, computed via STRATO 1.
REAL_REF = dc._qw.compute_ref_code("pg-3fc8cb52-1778433536")  # e.g. WR2-A8274F
HEX = REAL_REF[len("WR2-"):]
URL = "https://www.instagram.com/p/Cabc123_-/"


# ── parse_publish_command ──────────────────────────────────────────────────


def test_parse_italian_pubblicato_double_b():
    # "PUBBLICATO" has a double B — the regex must still match it.
    ref, url = dc.parse_publish_command(f"PUBBLICATO {REAL_REF} {URL}")
    assert ref == REAL_REF and url == URL


def test_parse_english_published():
    ref, url = dc.parse_publish_command(f"Published {REAL_REF}: {URL}")
    assert ref == REAL_REF and url == URL


def test_parse_tolerates_missing_prefix_and_lowercase():
    ref, url = dc.parse_publish_command(f"pubblicato {HEX.lower()} {URL}")
    assert ref == REAL_REF and url == URL


def test_parse_tolerates_extra_text_and_newlines():
    msg = f"Ciao! Ho PUBBLICATO il carosello {REAL_REF}\nlink: {URL}\ngrazie"
    ref, url = dc.parse_publish_command(msg)
    assert ref == REAL_REF and url == URL


def test_parse_reel_url():
    reel = "https://instagram.com/reel/Xyz789/"
    ref, url = dc.parse_publish_command(f"PUBBLICATO {REAL_REF} {reel}")
    assert url == reel


def test_parse_rejects_plain_client_message():
    assert dc.parse_publish_command("Hi, how much is a KITAS?") is None


def test_parse_rejects_command_without_url():
    assert dc.parse_publish_command(f"PUBBLICATO {REAL_REF} done") is None


def test_parse_rejects_non_instagram_url():
    assert dc.parse_publish_command(f"PUBBLICATO {REAL_REF} https://example.com/p/abc/") is None


def test_parse_rejects_command_without_refcode():
    assert dc.parse_publish_command(f"PUBBLICATO {URL}") is None


def test_parse_none_and_empty():
    assert dc.parse_publish_command("") is None
    assert dc.parse_publish_command(None) is None


# ── Fake mark_fn ───────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, status, detail=""):
        self.status = status
        self.detail = detail


def _recording_mark(status="published"):
    calls = []

    def mark_fn(ref, url, published_at):
        calls.append((ref, url, published_at))
        return _FakeResult(status)

    mark_fn.calls = calls
    return mark_fn


# ── process_message ────────────────────────────────────────────────────────


def test_process_message_command_calls_mark_once():
    mark = _recording_mark("published")
    when = datetime(2026, 6, 12, 8, 0, tzinfo=timezone.utc)
    out = dc.process_message({"id": 7, "text": f"PUBBLICATO {REAL_REF} {URL}", "message_date": when}, mark)
    assert out.parsed and out.status == "published"
    assert out.ref_code == REAL_REF and out.ig_url == URL
    assert len(mark.calls) == 1
    # message_date passed through as iso utc
    assert mark.calls[0][2] == when.isoformat()


def test_process_message_noise_does_not_call_mark():
    mark = _recording_mark()
    out = dc.process_message({"id": 9, "text": "what's my visa status?", "message_date": None}, mark)
    assert out.parsed is False and out.status == "not_a_command"
    assert mark.calls == []


def test_process_message_naive_datetime_handled():
    mark = _recording_mark()
    naive = datetime(2026, 6, 12, 8, 0)  # no tzinfo
    out = dc.process_message({"id": 3, "text": f"PUBBLICATO {REAL_REF} {URL}", "message_date": naive}, mark)
    assert out.parsed
    assert len(mark.calls) == 1  # did not raise on naive dt


# ── process_batch ──────────────────────────────────────────────────────────


def test_process_batch_advances_cursor_to_max_id():
    mark = _recording_mark("published")
    msgs = [
        {"id": 10, "text": f"PUBBLICATO {REAL_REF} {URL}", "message_date": None},
        {"id": 12, "text": "random client noise", "message_date": None},
    ]
    report = dc.process_batch(msgs, mark, cursor_before=5)
    assert report.cursor_after == 12  # advances past noise too (not re-scanned forever)
    assert report.published == 1
    assert len(mark.calls) == 1


def test_process_batch_unmatched_collects_failed_applies():
    mark = _recording_mark("not_found")  # ref didn't resolve
    msgs = [{"id": 20, "text": f"PUBBLICATO {REAL_REF} {URL}", "message_date": None}]
    report = dc.process_batch(msgs, mark, cursor_before=0)
    assert report.published == 0
    assert len(report.unmatched) == 1
    assert report.unmatched[0].status == "not_found"


def test_process_batch_already_published_is_not_unmatched():
    mark = _recording_mark("already_published")
    msgs = [{"id": 21, "text": f"PUBBLICATO {REAL_REF} {URL}", "message_date": None}]
    report = dc.process_batch(msgs, mark, cursor_before=0)
    assert report.unmatched == []  # idempotent no-op is success, not a human-needed case


def test_process_batch_empty_keeps_cursor():
    report = dc.process_batch([], _recording_mark(), cursor_before=42)
    assert report.cursor_after == 42 and report.outcomes == []


# ── cursor persistence ─────────────────────────────────────────────────────


def test_cursor_roundtrip(tmp_path):
    p = tmp_path / "cursor.json"
    assert dc.load_cursor(p) == 0  # absent -> 0
    dc.save_cursor(p, 123)
    assert dc.load_cursor(p) == 123


def test_append_unmatched_writes_jsonl(tmp_path):
    import json
    p = tmp_path / "unmatched.jsonl"
    out = dc.MessageOutcome(row_id=5, parsed=True, status="conflict", ref_code=REAL_REF, ig_url=URL, detail="x")
    dc.append_unmatched(p, out)
    dc.append_unmatched(p, out)
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["status"] == "conflict" and rec["ref_code"] == REAL_REF
