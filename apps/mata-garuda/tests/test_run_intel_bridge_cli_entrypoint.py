"""Regression test for the SystemExit-swallows-success heartbeat bug (2026-07-07),
class-audit sibling of test_run_normalizer_cli_entrypoint.py — same
`except BaseException` around `sys.exit(main())` pattern, same fix
(`_cli_entrypoint` catches `Exception` only, so `SystemExit(0)` propagates
untouched instead of clobbering the "ok" heartbeat `main()` already wrote).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from scripts.run_intel_bridge import _cli_entrypoint  # noqa: E402


def test_successful_main_does_not_emit_fail_heartbeat():
    """Innocence: main() returning 0 must not trigger the exception-path heartbeat."""
    with patch("scripts.run_intel_bridge.emit_heartbeat") as mock_emit:
        rc = _cli_entrypoint(lambda: 0)
    assert rc == 0
    mock_emit.assert_not_called()


def test_exception_in_main_emits_fail_heartbeat_and_reraises():
    """Guilt: a real exception still gets a fail heartbeat and propagates."""
    def boom():
        raise RuntimeError("intel bridge exploded")

    with patch("scripts.run_intel_bridge.emit_heartbeat") as mock_emit:
        with pytest.raises(RuntimeError, match="intel bridge exploded"):
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

    with patch("scripts.run_intel_bridge.emit_heartbeat") as mock_emit:
        with pytest.raises(SystemExit):
            _cli_entrypoint(calls_sys_exit)
    mock_emit.assert_not_called()
