"""Tests for scripts/modus_enqueue.py (Unit 1 — Producer adapter).

Isolation: monkeypatches sentinel_lib.escalations.write_escalation and
read_all_escalations with in-memory fakes backed by a plain list — no real
JSONL file or SQLite mirror is ever touched, so this test cannot collide
with a sibling session's live queue (scar family #5).

Run:
    cd ~/Desktop/nuzantara/.worktrees/ops-modus-autoloop
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
    kwargs = dict(
        job="resolvable-job",
        source="regulatory-watcher",
        mandate="finding",
        klass="green",
        perimeter="research/**",
    )
    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 1

    fake_queue[0]["status"] = "resolved"

    modus_enqueue.enqueue_task(**kwargs)
    assert len(fake_queue) == 2  # not pending anymore, so a new entry is allowed
