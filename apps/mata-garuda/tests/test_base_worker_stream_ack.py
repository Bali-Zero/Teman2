"""W14: base_worker.stream_ack silent-failure detection.

XACK returns the count of messages acked (≥1 = success, 0 = msg not in
PEL — silent failure). Previously stream_ack discarded this. W14 makes it
return bool + log WARNING on silent failure.
"""
from __future__ import annotations
from unittest.mock import patch
import logging

from mata_garuda.workers import base_worker


def _mock_redis_cmd(reply: str):
    return patch.object(base_worker, "redis_cmd", return_value=reply)


def test_stream_ack_success_returns_true():
    with _mock_redis_cmd("1"):
        assert base_worker.stream_ack("garuda:raw", "g", "1-0") is True


def test_stream_ack_silent_failure_returns_false_and_warns(caplog):
    """XACK returned 0 → False + WARNING log so operator sees PEL drift."""
    with _mock_redis_cmd("0"):
        caplog.set_level(logging.WARNING, logger="mata_garuda.workers")
        result = base_worker.stream_ack("garuda:raw", "g", "1-0")
    assert result is False
    assert any(
        "XACK returned 0" in r.message and "1-0" in r.message
        for r in caplog.records
    )


def test_stream_ack_redis_error_returns_false_and_warns(caplog):
    with _mock_redis_cmd("[ERROR] redis-cli: connection refused"):
        caplog.set_level(logging.WARNING, logger="mata_garuda.workers")
        result = base_worker.stream_ack("garuda:raw", "g", "1-0")
    assert result is False
    assert any(
        "redis-cli error" in r.message for r in caplog.records
    )


def test_stream_ack_unparseable_returns_false_and_warns(caplog):
    """XACK reply not an integer (malformed redis-cli output) → False + log."""
    with _mock_redis_cmd("OK"):
        caplog.set_level(logging.WARNING, logger="mata_garuda.workers")
        result = base_worker.stream_ack("garuda:raw", "g", "1-0")
    assert result is False
    assert any(
        "unparseable XACK reply" in r.message for r in caplog.records
    )


def test_stream_ack_callers_remain_backward_compatible():
    """All ~10 existing callers use statement form (ignore return value).
    Verify the new bool-returning signature doesn't break them.
    """
    with _mock_redis_cmd("1"):
        # Statement-form invocation (like all current callers) — must not raise
        base_worker.stream_ack("garuda:raw", "g", "1-0")
    with _mock_redis_cmd("0"):
        base_worker.stream_ack("garuda:raw", "g", "1-0")  # also no-raise
