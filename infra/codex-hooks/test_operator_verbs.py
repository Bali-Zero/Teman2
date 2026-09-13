"""The last two council residuals, both on the operator path.

  * release() did not refuse while a launch was in flight, although its own
    docstring declared that it must: popping launch_nonce makes the live
    supervisor raise "launch ownership changed", which rewrites
    rollover=needs_attention OVER the released state and re-freezes the source.
  * three different causes were raised as bare RuntimeError, so the except
    recorded `type(exc).__name__` and collapsed them into one token; retry policy
    downstream then could not tell "the destination exited" (worth retrying) from
    "the operator cancelled" (never).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import context_bridge as bridge
from test_context_bridge import setup, token  # noqa: F401


# --- residual: release() during an in-flight launch ------------------------


def _park(sid: str, **extra) -> None:
    bridge.save(
        bridge.state_path(sid),
        {"session_id": sid, "rollover": "needs_attention", **extra},
    )


def test_release_refuses_while_a_launch_is_in_flight(setup: tuple) -> None:
    sid = "src-in-flight"
    # os.getpid() is alive by construction: this is a launch still running.
    _park(sid, supervisor_pid=os.getpid(), launch_nonce="nonce-1")

    with pytest.raises(ValueError, match="still in flight"):
        bridge.release(sid)

    # The state must be untouched — no half-release.
    state = bridge.load(bridge.state_path(sid))
    assert state["rollover"] == "needs_attention"
    assert state["launch_nonce"] == "nonce-1"
    assert "released" not in state


def test_release_proceeds_once_the_supervisor_has_finished(setup: tuple) -> None:
    sid = "src-finished"
    _park(
        sid,
        supervisor_pid=os.getpid(),
        supervisor_finished=True,
        launch_nonce="nonce-2",
    )

    assert bridge.release(sid) == {"released": True}
    state = bridge.load(bridge.state_path(sid))
    assert state["released"]["from"] == "needs_attention"
    assert "launch_nonce" not in state
    assert "rollover" not in state


def test_release_still_refuses_a_source_that_is_not_parked(setup: tuple) -> None:
    sid = "src-live"
    bridge.save(bridge.state_path(sid), {"session_id": sid, "rollover": "starting"})
    with pytest.raises(ValueError, match="parked"):
        bridge.release(sid)


# --- residual: failure classified by exception type ------------------------


def test_the_three_runtime_causes_get_distinct_codes() -> None:
    codes = {
        bridge.failure_code(RuntimeError("launch ownership changed")),
        bridge.failure_code(RuntimeError("continuation cancelled")),
        bridge.failure_code(RuntimeError("owned destination exited without completion")),
    }
    assert len(codes) == 3, "all three collapsed into one token again"


def test_an_exited_destination_stays_retryable() -> None:
    code = bridge.failure_code(
        RuntimeError("owned destination exited without completion")
    )
    assert code in bridge.TRANSIENT_FAILURES


def test_a_cancelled_or_reowned_launch_is_terminal() -> None:
    # Retrying either of these is what the single RuntimeError token used to do.
    assert bridge.failure_code(RuntimeError("continuation cancelled")) not in (
        bridge.TRANSIENT_FAILURES
    )
    assert bridge.failure_code(RuntimeError("launch ownership changed")) not in (
        bridge.TRANSIENT_FAILURES
    )


def test_an_unmapped_failure_falls_back_to_its_type_name() -> None:
    assert bridge.failure_code(TimeoutError("slow")) == "TimeoutError"
    assert bridge.failure_code(TimeoutError("slow")) in bridge.TRANSIENT_FAILURES
    # And an unclassified RuntimeError is NOT retried blindly any more.
    assert bridge.failure_code(RuntimeError("something new")) == "RuntimeError"
    assert "RuntimeError" not in bridge.TRANSIENT_FAILURES
