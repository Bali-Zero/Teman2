"""Regression test for the SystemExit-swallows-success heartbeat bug (2026-07-07).

`_cli_entrypoint` wraps `main()` for `run_normalizer.py`'s `if __name__` guard.
The previous code did `except BaseException` around `sys.exit(main())`, which
catches `SystemExit` too — so a NORMAL successful `sys.exit(0)` was caught and
re-labeled as a "fail" heartbeat (metadata `{"error": "SystemExit: 0"}"`),
clobbering the correct status `main()` had just written. This organ ran fine
(launchd exit 0, 184 runs) while its `~/.organism/last_seen` sidecar always
said `fail` — the exact "breathing but status=fail" signature the healer
receptor flagged.

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

from scripts.run_normalizer import _cli_entrypoint  # noqa: E402


def test_successful_main_does_not_emit_fail_heartbeat():
    """Innocence: main() returning 0 must not trigger the exception-path heartbeat."""
    with patch("scripts.run_normalizer.emit_heartbeat") as mock_emit:
        rc = _cli_entrypoint(lambda: 0)
    assert rc == 0
    mock_emit.assert_not_called()


def test_exception_in_main_emits_fail_heartbeat_and_reraises():
    """Guilt: a real exception still gets a fail heartbeat and propagates."""
    def boom():
        raise RuntimeError("normalizer exploded")

    with patch("scripts.run_normalizer.emit_heartbeat") as mock_emit:
        with pytest.raises(RuntimeError, match="normalizer exploded"):
            _cli_entrypoint(boom)
    mock_emit.assert_called_once()
    args, kwargs = mock_emit.call_args
    assert args[1] == "fail"
    assert "RuntimeError" in kwargs["metadata"]["error"]


def test_sys_exit_from_main_is_not_swallowed():
    """A main() that itself calls sys.exit() (SystemExit, not Exception) must
    propagate untouched and must NOT be treated as a failure — this is the
    exact class of bug that clobbered every successful run."""
    def calls_sys_exit():
        sys.exit(0)

    with patch("scripts.run_normalizer.emit_heartbeat") as mock_emit:
        with pytest.raises(SystemExit):
            _cli_entrypoint(calls_sys_exit)
    mock_emit.assert_not_called()
