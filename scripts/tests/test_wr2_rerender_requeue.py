"""Tests for the re-render verb CLI's queue-state guard (Codex 2026-07-13).

The DB never learns an entry was published (damar flips only the queue JSON),
so check_queue_state is the only thing standing between `wr2_rerender_requeue`
and clobbering a published carousel's PNG dir on a same-day re-render.
tmp_path only — no DB.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


req = _load("wr2_rerender_requeue")


def _queue(tmp_path: Path, items: list[dict]) -> Path:
    qp = tmp_path / "human-review-queue.json"
    qp.write_text(json.dumps(items))
    return qp


def test_published_entry_refused(tmp_path):
    """GUILT: a published queue entry blocks the requeue by default."""
    qp = _queue(tmp_path, [{"draft_id": "d1", "state": "published"}])
    ok, reason = req.check_queue_state("d1", queue_path=qp)
    assert ok is False
    assert "published" in reason


def test_prepublish_states_allowed(tmp_path):
    """INNOCENCE: every damar pre-publish state passes the guard."""
    for state in ("drafted", "reviewed", "rejected", "drafted_needs_human_edit"):
        qp = _queue(tmp_path, [{"draft_id": "d1", "state": state}])
        ok, reason = req.check_queue_state("d1", queue_path=qp)
        assert ok is True, f"state={state} should be requeue-able"
        assert state in reason


def test_absent_entry_allowed(tmp_path):
    """INNOCENCE: a draft with no queue entry (pre-queue era) proceeds."""
    qp = _queue(tmp_path, [{"draft_id": "other", "state": "published"}])
    ok, reason = req.check_queue_state("d1", queue_path=qp)
    assert ok is True
    assert "no queue entry" in reason


def test_unreadable_queue_proceeds_with_reason(tmp_path):
    """INNOCENCE: missing queue file (e.g. CLI run off-Pro) does not brick the
    verb — DB-side guards still apply; the reason says why."""
    ok, reason = req.check_queue_state("d1", queue_path=tmp_path / "nope.json")
    assert ok is True
    assert "not readable" in reason


def test_legacy_no_state_entry_refused(tmp_path):
    """A legacy entry without `state` is indistinguishable from history —
    refuse by default (--force exists for a reason)."""
    qp = _queue(tmp_path, [{"draft_id": "d1"}])
    ok, reason = req.check_queue_state("d1", queue_path=qp)
    assert ok is False
    assert "None" in reason


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
