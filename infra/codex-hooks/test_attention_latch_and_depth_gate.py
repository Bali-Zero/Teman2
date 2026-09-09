"""Two council residuals about signals the ledger raises but never revises.

  * `needs_attention` latched: eight writers set it, nothing ever cleared it, so a
    child that later returned cleanly left its alarm standing and the attention
    report accumulated resolved alarms — the same signal pollution R1 was written
    to stop, one level up.
  * the `depth > max_depth` branch was the only limit in reserve()'s chain NOT
    gated on `strict`, so it denied interactive callers that the other four let
    through, duplicating a structural rule the adapter already enforces above it.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import mandate_budget as budget

LIMITS = {"max_active": 4, "max_attempts": 8, "max_seconds": 600, "max_depth": 1}


def _state(root: Path, mandate: str = "root") -> dict:
    return json.loads(
        (root / (hashlib.sha256(mandate.encode()).hexdigest() + ".json")).read_text()
    )


def _write(root: Path, state: dict, mandate: str = "root") -> None:
    (root / (hashlib.sha256(mandate.encode()).hexdigest() + ".json")).write_text(
        json.dumps(state)
    )


# --- residual: needs_attention latches -------------------------------------


def test_an_alarm_is_superseded_when_the_child_turns_out_to_have_a_reservation(
    tmp_path: Path,
) -> None:
    # Raise it the way the live path does: a stop with no reservation at all.
    budget.observe(tmp_path, "root", "orphan", stopped=True)
    assert _state(tmp_path)["status"] == "needs_attention"

    # Now the same ledger sees a properly reserved child return.
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    budget.observe(tmp_path, "root", "child-a")

    state = _state(tmp_path)
    assert state.get("status") != "needs_attention"
    assert state.get("reason") is None


def test_the_history_keeps_the_alarm_that_was_superseded(tmp_path: Path) -> None:
    budget.observe(tmp_path, "root", "orphan", stopped=True)
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    budget.observe(tmp_path, "root", "child-a")

    history = _state(tmp_path)["attention_history"]
    assert any(h.get("key") == "observed_without_reservation" for h in history), (
        "the alarm must survive in the ledger even though the live flag cleared"
    )
    assert any(h.get("resolved") == "observed_without_reservation" for h in history)


def test_an_unrelated_alarm_is_not_cleared(tmp_path: Path) -> None:
    # A mandate-limit alarm says nothing about reservations; a clean child return
    # must NOT silence it.
    limits = dict(LIMITS, max_attempts=1)
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    assert budget.reserve(tmp_path, "root", "two", limits) is not None
    assert _state(tmp_path)["attention_key"] == "mandate_limit"

    budget.observe(tmp_path, "root", "child-a")
    state = _state(tmp_path)
    assert state["status"] == "needs_attention"
    assert state["attention_key"] == "mandate_limit"


def test_a_live_heartbeat_supersedes_a_liveness_unknown_alarm(tmp_path: Path) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    budget.observe(tmp_path, "root", "child-a")
    state = _state(tmp_path)
    state["status"] = "needs_attention"
    state["reason"] = "Child transcript liveness UNKNOWN; slot retained"
    state["attention_key"] = "liveness_unknown"
    _write(tmp_path, state)

    # The row is heartbeating well inside its TTL: the doubt is contradicted.
    budget.reserve(tmp_path, "root", "two", LIMITS)
    assert _state(tmp_path).get("status") != "needs_attention"


# --- residual: the ungated depth branch ------------------------------------


def test_depth_denies_under_a_strict_mandate(tmp_path: Path) -> None:
    verdict = budget.reserve(
        tmp_path, "root", "deep", dict(LIMITS, strict=True), depth=2
    )
    assert verdict is not None
    assert "depth" in verdict


def test_depth_does_not_deny_an_interactive_session(tmp_path: Path) -> None:
    # The other four limits in this chain are gated on strict; this one was not.
    assert (
        budget.reserve(tmp_path, "root", "deep", dict(LIMITS, strict=False), depth=2)
        is None
    )


def test_depth_within_the_limit_is_untouched_either_way(tmp_path: Path) -> None:
    assert (
        budget.reserve(tmp_path, "a", "ok", dict(LIMITS, strict=True), depth=1) is None
    )
    assert (
        budget.reserve(tmp_path, "b", "ok", dict(LIMITS, strict=False), depth=1) is None
    )
