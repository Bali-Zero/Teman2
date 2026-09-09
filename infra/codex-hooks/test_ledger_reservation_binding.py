"""Two council residuals on how a reservation binds to its child.

Both were declared, not fixed, when the child ledger shipped (#6046):

  * the unstarted sweep defaulted to 60 s against context_bridge's 240 s
    handshake, so a concurrent reserve() under a shared mandate id swept a
    HEALTHY mid-handshake row to expired_unstarted;
  * observe() claimed a pending reservation only for a START, so a stop that
    arrived first (reordered or missing hook delivery) left the row `reserved`
    while the child was recorded stopped.
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
    path = root / (hashlib.sha256(mandate.encode()).hexdigest() + ".json")
    return json.loads(path.read_text())


def _rows(root: Path) -> list[dict]:
    return list(_state(root).get("reservations", {}).values())


# --- residual: unstarted_ttl vs ACKNOWLEDGE_SECONDS -------------------------


def test_unstarted_sweep_defaults_to_the_handshake_window():
    # Derived, not merely equal: two independent literals drifted once already.
    assert budget.ACKNOWLEDGE_SECONDS == 240

    from context_bridge import ACKNOWLEDGE_SECONDS as bridge_window

    assert bridge_window is budget.ACKNOWLEDGE_SECONDS


def test_a_row_younger_than_the_handshake_is_not_swept(tmp_path: Path) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    # Age it past the OLD 60 s default but well inside the 240 s handshake.
    state = _state(tmp_path)
    for row in state["reservations"].values():
        row["created"] = time.time() - 100
    path = tmp_path / (hashlib.sha256(b"root").hexdigest() + ".json")
    path.write_text(json.dumps(state))

    assert budget.reserve(tmp_path, "root", "two", LIMITS) is None
    statuses = {r["status"] for r in _rows(tmp_path)}
    assert "expired_unstarted" not in statuses


def test_a_row_older_than_the_handshake_is_still_swept(tmp_path: Path) -> None:
    # The cure must not disable the sweep, only stop it firing early.
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    state = _state(tmp_path)
    for row in state["reservations"].values():
        row["created"] = time.time() - (budget.ACKNOWLEDGE_SECONDS + 60)
    path = tmp_path / (hashlib.sha256(b"root").hexdigest() + ".json")
    path.write_text(json.dumps(state))

    assert budget.reserve(tmp_path, "root", "two", LIMITS) is None
    assert "expired_unstarted" in {r["status"] for r in _rows(tmp_path)}


# --- residual: a stop observed before its start -----------------------------


def test_a_stop_before_its_start_claims_the_reservation(tmp_path: Path) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    # No start observation ever arrives — the stop is delivered first.
    budget.observe(tmp_path, "root", "child-a", stopped=True)

    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["child"] == "child-a"
    assert rows[0]["status"] == "returned_unverified"


def test_a_stop_before_its_start_does_not_report_attention(tmp_path: Path) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    budget.observe(tmp_path, "root", "child-a", stopped=True)

    state = _state(tmp_path)
    assert state.get("status") != "needs_attention"
    assert "without a dispatch reservation" not in (state.get("reason") or "")


def test_a_stop_with_no_reservation_at_all_still_reports_attention(
    tmp_path: Path,
) -> None:
    # The cure must not swallow the genuine case it was masking.
    budget.observe(tmp_path, "root", "orphan", stopped=True)

    state = _state(tmp_path)
    assert state["status"] == "needs_attention"
    assert "without a dispatch reservation" in state["reason"]


def test_the_normal_start_then_stop_order_is_unchanged(tmp_path: Path) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS) is None
    budget.observe(tmp_path, "root", "child-a")
    assert _rows(tmp_path)[0]["status"] == "active"
    budget.observe(tmp_path, "root", "child-a", stopped=True)
    assert _rows(tmp_path)[0]["status"] == "returned_unverified"
