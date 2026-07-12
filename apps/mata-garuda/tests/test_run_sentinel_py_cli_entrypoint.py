"""Regression coverage for run_sentinel_py.py's heartbeat instrumentation
(2026-07-08, healer tick — PENDING-ARMS ledger-overdue).

`mata_garuda.sentinel_daily.mini` (the Mini `com.matagaruda.sentinel.daily`
cron, live ProgramArguments invoking THIS script) was flagged never_armed by
the healer receptor indefinitely: a prior instrumentation pass (PR #2090)
wired emit_heartbeat into run_sentinel_cell.py under this same organ_id, on
the unverified assumption that script was the Mini daily cron target — it is
actually what Pro's separate hourly cron invokes. The Mini daily cron kept
writing no sidecar at all.

`_cli_entrypoint` follows the same shape as run_normalizer.py /
run_intel_bridge.py (2026-07-07, PR #2107): catches `Exception` only, so a
`sys.exit()` inside `main` would propagate untouched instead of being
relabeled as a failure.

Guilt: a genuine exception from `main()` still gets a fail heartbeat + re-raise.
Innocence: a normal successful return does NOT emit a second (wrong) heartbeat.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from scripts.run_sentinel_py import _cli_entrypoint  # noqa: E402


def test_successful_main_does_not_emit_fail_heartbeat():
    """Innocence: main() returning 0 must not trigger the exception-path heartbeat."""
    with patch("scripts.run_sentinel_py.emit_heartbeat") as mock_emit:
        rc = _cli_entrypoint(lambda: 0)
    assert rc == 0
    mock_emit.assert_not_called()


def test_exception_in_main_emits_fail_heartbeat_and_reraises():
    """Guilt: a real exception still gets a fail heartbeat and propagates."""
    def boom():
        raise RuntimeError("sentinel exploded")

    with patch("scripts.run_sentinel_py.emit_heartbeat") as mock_emit:
        with pytest.raises(RuntimeError, match="sentinel exploded"):
            _cli_entrypoint(boom)
    mock_emit.assert_called_once()
    args, kwargs = mock_emit.call_args
    assert args[1] == "fail"
    assert "RuntimeError" in kwargs["metadata"]["error"]


def test_sys_exit_from_main_is_not_swallowed():
    """A main() that itself calls sys.exit() (SystemExit, not Exception) must
    propagate untouched and must NOT be treated as a failure."""
    def calls_sys_exit():
        sys.exit(0)

    with patch("scripts.run_sentinel_py.emit_heartbeat") as mock_emit:
        with pytest.raises(SystemExit):
            _cli_entrypoint(calls_sys_exit)
    mock_emit.assert_not_called()


def test_zero_items_harvested_still_emits_ok_heartbeat():
    """The early-return (no items harvested) path is not an error — it must
    still emit an 'ok' heartbeat, not leave the organ silent for the day."""
    from scripts.run_sentinel_py import main, ORGAN_ID

    empty_counts = {"arxiv": 0, "rss": 0, "github": 0, "youtube": 0, "errors": 0}
    with patch("scripts.run_sentinel_py.harvest", return_value=empty_counts):
        with patch("scripts.run_sentinel_py.emit_heartbeat") as mock_emit:
            rc = main()
    assert rc == 0
    mock_emit.assert_called_once_with(
        ORGAN_ID, "ok", metadata={"harvested": empty_counts, "normalized": 0, "scored": 0}
    )
