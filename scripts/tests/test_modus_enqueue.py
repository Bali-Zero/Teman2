"""Tests for scripts/modus_enqueue.py (Unit 1 — Producer adapter).

Isolation: monkeypatches sentinel_lib.escalations.write_escalation and
read_all_escalations with in-memory fakes backed by a plain list — no real
JSONL file or SQLite mirror is ever touched, so this test cannot collide
with a sibling session's live queue (scar family #5).

Run:
    cd ~/nuzantara/.worktrees/ops-modus-autoloop
    source apps/backend-rag/.venv/bin/activate
    python -m pytest scripts/tests/test_modus_enqueue.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentinel_lib import escalations  # noqa: E402
import modus_enqueue  # noqa: E402


@pytest.fixture
def fake_queue(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """In-memory fake replacing the real per-machine JSONL + SQLite queue."""
    store: list[dict] = []

    def _fake_write(entry: dict) -> None:
        record = {**entry, "status": entry.get("status", "pending")}
        store.append(record)

    def _fake_read_all(include_resolved: bool = False) -> list[dict]:
        if include_resolved:
            return list(store)
        return [e for e in store if e.get("status") != "resolved"]

    monkeypatch.setattr(escalations, "write_escalation", _fake_write)
    monkeypatch.setattr(escalations, "read_all_escalations", _fake_read_all)
    return store


def test_valid_green_enqueue_writes_one_record(fake_queue: list[dict]) -> None:
    modus_enqueue.enqueue_task(
        job="regulatory-delta-2026-07-12",
        source="regulatory-watcher",
        mandate="Capture the PP-28 delta into research/regulatory/...",
        klass="green",
        perimeter="research/regulatory/**",
    )

    assert len(fake_queue) == 1
    record = fake_queue[0]
    assert record["job"] == "regulatory-delta-2026-07-12"
    assert record["source"] == "regulatory-watcher"
    assert record["class"] == "green"
    assert record["perimeter"] == "research/regulatory/**"
    assert record["severity"] == "normal"
    assert record["status"] == "pending"
    # 'klass' must never leak as a literal key — only the JSON 'class' key.
    assert "klass" not in record


def test_invalid_class_raises(fake_queue: list[dict]) -> None:
    with pytest.raises(ValueError):
        modus_enqueue.enqueue_task(
            job="some-job",
            source="some-cron",
            mandate="do something",
            klass="red",  # not "green" or "proposal"
            perimeter="scripts/**",
        )
    assert len(fake_queue) == 0


def test_reenqueue_of_pending_job_does_not_double_write(fake_queue: list[dict]) -> None:
    kwargs = dict(
        job="dup-job-123",
        source="regulatory-watcher",
        mandate="same finding again",
        klass="proposal",
        perimeter="apps/backend-rag/**",
    )
    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 1

    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 1  # still one — second call was skipped


def test_reenqueue_after_resolution_is_allowed(fake_queue: list[dict]) -> None:
    """The queue is append-only: resolution APPENDS a new record, it never
    mutates the original pending one (matches sentinel_lib.escalations'
    real mark_resolved() semantics — see test_reenqueue_after_ancient_
    resolution_is_allowed below for why a fake that mutates in place would
    hide the actual production bug this guards against)."""
    kwargs = dict(
        job="resolvable-job",
        source="regulatory-watcher",
        mandate="finding",
        klass="green",
        perimeter="research/**",
    )
    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 1

    fake_queue.append({"job": "resolvable-job", "status": "resolved", "ts": 2})

    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 3  # not pending anymore, so a new entry is allowed


def test_reenqueue_after_ancient_resolution_is_allowed(fake_queue: list[dict]) -> None:
    """Regression test for the append-only staleness bug: an OLD pending
    entry for a job must not block re-enqueue once a LATER resolved marker
    exists for that same job — even though the old pending entry's own
    'status' field still literally reads 'pending' forever (immutable log).
    Pre-fix, _already_pending() did a naive per-entry status scan and would
    see the ancient pending entry and refuse to re-enqueue, silently
    swallowing every future recurrence of an already-fixed job."""
    fake_queue.append({"job": "flaky-job", "status": "pending", "ts": 1})
    fake_queue.append({"job": "flaky-job", "status": "resolved", "ts": 2})
    assert len(fake_queue) == 2

    modus_enqueue.enqueue_task(
        job="flaky-job",
        source="regulatory-watcher",
        mandate="recurred after being fixed once",
        klass="green",
        perimeter="research/**",
    )
    assert len(fake_queue) == 3  # new pending record written, not skipped
