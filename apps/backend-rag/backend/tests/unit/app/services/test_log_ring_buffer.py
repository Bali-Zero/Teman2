"""
Tests for log_ring_buffer module (TODO #79).

The RingBufferLogHandler is the in-memory backing store for the
GET /api/debug/logs debug endpoint. It captures recent log records from the
root logger so operators can inspect them without flyctl auth or external
log aggregation (Loki/CloudWatch).
"""

from __future__ import annotations

import logging

import pytest

from backend.app.services.log_ring_buffer import (
    RingBufferLogHandler,
    get_ring_buffer_handler,
)


def _make_record(
    *,
    name: str = "test.logger",
    level: int = logging.INFO,
    msg: str = "hello",
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname="/tmp/x.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_ring_buffer_appends_records() -> None:
    handler = RingBufferLogHandler(capacity=10)
    handler.emit(_make_record(msg="one"))
    handler.emit(_make_record(msg="two"))
    handler.emit(_make_record(msg="three"))

    snapshot = handler.snapshot()
    assert len(snapshot) == 3
    # Most-recent-first ordering — easier to consume in /debug/logs.
    assert snapshot[0]["message"] == "three"
    assert snapshot[-1]["message"] == "one"


def test_ring_buffer_respects_capacity() -> None:
    handler = RingBufferLogHandler(capacity=5)
    for i in range(20):
        handler.emit(_make_record(msg=f"msg-{i}"))

    snapshot = handler.snapshot(limit=100)
    assert len(snapshot) == 5
    # Oldest dropped — only msg-15..msg-19 survive, most-recent-first.
    assert snapshot[0]["message"] == "msg-19"
    assert snapshot[-1]["message"] == "msg-15"


def test_ring_buffer_filter_by_module() -> None:
    handler = RingBufferLogHandler(capacity=20)
    handler.emit(_make_record(name="zantara.alpha", msg="alpha-msg"))
    handler.emit(_make_record(name="zantara.beta", msg="beta-msg"))
    handler.emit(_make_record(name="zantara.alpha.sub", msg="alpha-sub-msg"))

    # Exact match on module name OR dotted-prefix match (logger hierarchy).
    snapshot = handler.snapshot(module="zantara.alpha")
    messages = {entry["message"] for entry in snapshot}
    assert messages == {"alpha-msg", "alpha-sub-msg"}


def test_ring_buffer_filter_by_level() -> None:
    handler = RingBufferLogHandler(capacity=20)
    handler.emit(_make_record(level=logging.DEBUG, msg="debug-msg"))
    handler.emit(_make_record(level=logging.INFO, msg="info-msg"))
    handler.emit(_make_record(level=logging.WARNING, msg="warning-msg"))
    handler.emit(_make_record(level=logging.ERROR, msg="error-msg"))

    snapshot = handler.snapshot(level="WARNING")
    messages = {entry["message"] for entry in snapshot}
    assert messages == {"warning-msg", "error-msg"}


def test_ring_buffer_filter_invalid_level_falls_back_to_no_filter() -> None:
    handler = RingBufferLogHandler(capacity=5)
    handler.emit(_make_record(level=logging.INFO, msg="info-msg"))
    handler.emit(_make_record(level=logging.ERROR, msg="error-msg"))

    snapshot = handler.snapshot(level="NOPE")
    assert len(snapshot) == 2


def test_ring_buffer_limit_caps_results() -> None:
    handler = RingBufferLogHandler(capacity=100)
    for i in range(50):
        handler.emit(_make_record(msg=f"m-{i}"))

    snapshot = handler.snapshot(limit=10)
    assert len(snapshot) == 10
    # limit picks the 10 most recent.
    assert snapshot[0]["message"] == "m-49"
    assert snapshot[-1]["message"] == "m-40"


def test_ring_buffer_singleton_identity() -> None:
    a = get_ring_buffer_handler()
    b = get_ring_buffer_handler()
    assert a is b


def test_ring_buffer_records_include_required_fields() -> None:
    handler = RingBufferLogHandler(capacity=5)
    handler.emit(_make_record(name="my.logger", level=logging.WARNING, msg="probe"))

    entry = handler.snapshot()[0]
    assert entry["module"] == "my.logger"
    assert entry["level"] == "WARNING"
    assert entry["message"] == "probe"
    assert "timestamp" in entry  # ISO 8601 UTC


def test_ring_buffer_exception_emit_does_not_crash() -> None:
    """Logging must never crash the app even if formatting fails."""
    handler = RingBufferLogHandler(capacity=5)
    # Record with args that will fail formatting
    bad = logging.LogRecord(
        name="t", level=logging.INFO, pathname="x", lineno=1,
        msg="value=%s", args=(object(),), exc_info=None,
    )
    # Should not raise — logging.Handler.handleError swallows internally
    handler.emit(bad)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
