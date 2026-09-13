"""Tests for scripts/sentinel_lib/escalations.py::is_job_open().

Direct unit coverage for the net-pending collapse-by-job logic, isolated
from any consumer (see test_modus_enqueue.py for the _already_pending()
consumer-level regression). Uses a real on-disk JSONL under tmp_path so the
append-only O_APPEND write path (write_escalation) is exercised for real,
not faked.

Run:
    cd ~/nuzantara
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_sentinel_lib_escalations.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel_lib import escalations  # noqa: E402


@pytest.fixture
def isolated_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the module at a throwaway JSONL so this test can never collide
    with a sibling session's live shared/escalations_pro.jsonl (scar #5)."""
    path = tmp_path / "escalations_pro.jsonl"
    monkeypatch.setattr(escalations, "_MACHINE_FILES", {"pro": path})
    monkeypatch.setattr(escalations, "_current_machine", lambda: "pro")
    monkeypatch.setenv("ESCALATIONS_USE_SQLITE", "false")
    return path


def test_no_entries_reads_not_open(isolated_queue: Path) -> None:
    assert escalations.is_job_open("never-escalated-job") is False


def test_pending_only_reads_open(isolated_queue: Path) -> None:
    escalations.write_escalation({"job": "job-a", "status": "pending"})
    assert escalations.is_job_open("job-a") is True


def test_ancient_pending_with_later_resolution_reads_closed(isolated_queue: Path) -> None:
    """The bug this function exists to fix: a pending entry's own status
    field never changes (immutable log) — only a LATER resolved record for
    the same job, collapsed by ts, makes the job read as closed."""
    escalations.write_escalation({"job": "job-b", "status": "pending", "ts": 100})
    escalations.write_escalation({"job": "job-b", "status": "resolved", "ts": 200})
    assert escalations.is_job_open("job-b") is False


def test_recurring_job_after_resolution_reads_open_again(isolated_queue: Path) -> None:
    """escalate -> resolve -> escalate again must read OPEN — the newest
    record wins the collapse, not 'any resolution ever happened'."""
    escalations.write_escalation({"job": "job-c", "status": "pending", "ts": 100})
    escalations.write_escalation({"job": "job-c", "status": "resolved", "ts": 200})
    escalations.write_escalation({"job": "job-c", "status": "pending", "ts": 300})
    assert escalations.is_job_open("job-c") is True


def test_unrelated_job_resolution_does_not_leak(isolated_queue: Path) -> None:
    """A resolution for job-x must never close job-y."""
    escalations.write_escalation({"job": "job-x", "status": "pending", "ts": 100})
    escalations.write_escalation({"job": "job-y", "status": "pending", "ts": 100})
    escalations.write_escalation({"job": "job-x", "status": "resolved", "ts": 200})
    assert escalations.is_job_open("job-x") is False
    assert escalations.is_job_open("job-y") is True


# --- ts coercion: readers never depend on writer discipline (W54, #6012) ---


def test_ts_epoch_coerces_every_shape_a_writer_has_emitted() -> None:
    """Numbers pass through; numeric strings and ISO-8601 strings (W54's
    dlq_autopilot shape, #6012's str(now) shape) parse; junk orders as 0.0."""
    assert escalations.ts_epoch(1700000000) == 1700000000.0
    assert escalations.ts_epoch(1700000000.5) == 1700000000.5
    assert escalations.ts_epoch("1700000000.5") == 1700000000.5  # #6012: str(time.time())
    assert escalations.ts_epoch("2026-05-23T11:55:24Z") == 1779537324.0  # W54: strftime ISO
    assert escalations.ts_epoch("2026-05-23T11:55:24+00:00") == 1779537324.0
    for junk in (None, "", "   ", "yesterday", float("nan"), True, {"ts": 1}, []):
        assert escalations.ts_epoch(junk) == 0.0, junk


def test_mixed_ts_board_reads_whole_and_sorts_newest_first(isolated_queue: Path) -> None:
    """The defect the gate found on #6002: one string ts on the board made
    sorted(..., key=ts) raise TypeError for EVERY consumer. A mixed board
    must read in full, in the right order, with the unreadable line kept."""
    escalations.write_escalation({"job": "float-old", "status": "pending", "ts": 1779537000.0})
    escalations.write_escalation({"job": "iso-mid", "status": "pending", "ts": "2026-05-23T11:55:24Z"})
    escalations.write_escalation({"job": "str-new", "status": "pending", "ts": "1779538000.0"})
    escalations.write_escalation({"job": "junk", "status": "pending", "ts": "yesterday"})
    board = escalations.read_all_escalations()
    assert [e["job"] for e in board] == ["str-new", "iso-mid", "float-old", "junk"]
    # The record is returned as written — the reader orders, it never rewrites.
    assert next(e for e in board if e["job"] == "iso-mid")["ts"] == "2026-05-23T11:55:24Z"


def test_is_job_open_collapses_across_string_and_float_ts(isolated_queue: Path) -> None:
    """A pending line with a string ts and a resolution with a float ts must
    still collapse to the newest record: resolved after pending → closed."""
    escalations.write_escalation({"job": "job-mixed", "status": "pending", "ts": "2026-05-23T11:55:24Z"})
    escalations.write_escalation({"job": "job-mixed", "status": "resolved", "ts": 1779537400.0})
    assert escalations.is_job_open("job-mixed") is False
    escalations.write_escalation({"job": "job-mixed", "status": "pending", "ts": "1779537500.0"})
    assert escalations.is_job_open("job-mixed") is True
