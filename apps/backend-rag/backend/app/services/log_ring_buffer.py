"""In-memory ring buffer for recent log records.

Closes TODO(#79) in ``backend/app/routers/debug.py`` — the
``GET /api/debug/logs`` endpoint used to return a static placeholder. This
module attaches a handler to the root logger that keeps the last N records
in a bounded deque, then exposes a snapshot API the debug router can filter
by module / level.

Why not Loki / fly logs --json
------------------------------
Loki requires extra infra; ``fly logs --json`` via subprocess requires
flyctl auth inside the container (not available on the Fly machine). An
in-process ring buffer is zero-dependency, works in dev + prod identically,
and survives the auto-stop / auto-start cycles that already lose history
on Fly anyway (the ring buffer just resets on machine restart). When we
eventually wire a real log aggregator, this handler stays as a fallback.

Capacity
--------
Default 2000 records (~5-10 minutes of typical traffic). At ~1KB per
serialized record that's ~2MB RSS — negligible. Operators tail the
debug endpoint frequently enough that long retention is unnecessary.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_DEFAULT_CAPACITY = 2000


class RingBufferLogHandler(logging.Handler):
    """A bounded, thread-safe ring buffer of recent log records.

    Each emitted ``LogRecord`` is serialized to a small dict and pushed
    onto a ``collections.deque`` with ``maxlen=capacity``. Old records are
    silently dropped from the head when the deque is full.

    Not for high-throughput audit trails — this is debugging-only. Real
    durable logs still flow through the structured stdout JSON handler
    that's already attached by :func:`backend.app.setup.logging_config.configure_logging`.
    """

    def __init__(self, capacity: int = _DEFAULT_CAPACITY) -> None:
        super().__init__(level=logging.NOTSET)
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            # Formatting failed (bad args). Fall back to the raw msg.
            # ``logging.Handler.handleError`` would normally print to stderr;
            # we don't want stderr noise from the debug buffer.
            message = str(record.msg)

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": message,
        }

        # Attach correlation id and exception summary when present, since
        # those are the two things operators look at first when something
        # goes sideways.
        if hasattr(record, "correlation_id"):
            entry["correlation_id"] = record.correlation_id
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
            }

        with self._lock:
            self._buffer.append(entry)

    def snapshot(
        self,
        *,
        module: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return the most recent N records, optionally filtered.

        Args:
            module: keep only records whose ``module`` equals this name OR
                starts with ``module + "."`` (logger-hierarchy match — so
                filtering on ``"backend.app"`` includes
                ``"backend.app.routers.dream"``).
            level: keep only records at this severity or above. Accepts
                level names (e.g. ``"WARNING"``). Unknown names are
                silently ignored (no filter).
            limit: cap the returned slice. Capped at the buffer capacity.

        Returns:
            Newest-first list of record dicts.
        """
        with self._lock:
            records = list(self._buffer)

        # Reverse to most-recent-first.
        records.reverse()

        if module:
            module_prefix = module + "."
            records = [
                r for r in records
                if r["module"] == module or r["module"].startswith(module_prefix)
            ]

        if level:
            threshold = logging.getLevelName(level.upper())
            if isinstance(threshold, int):
                records = [
                    r for r in records
                    if logging.getLevelName(r["level"]) >= threshold
                ]

        return records[: max(0, limit)]

    def clear(self) -> None:
        """Drop all stored records. Useful for tests."""
        with self._lock:
            self._buffer.clear()


_handler_singleton: RingBufferLogHandler | None = None
_singleton_lock = Lock()


def get_ring_buffer_handler() -> RingBufferLogHandler:
    """Return the process-wide ring buffer handler.

    The handler is created lazily on first call and reused thereafter.
    This is the single source of truth both for
    :func:`backend.app.setup.logging_config.configure_logging` (which
    attaches it to the root logger) and for
    :mod:`backend.app.routers.debug` (which reads its snapshot).
    """
    global _handler_singleton
    if _handler_singleton is None:
        with _singleton_lock:
            if _handler_singleton is None:
                _handler_singleton = RingBufferLogHandler()
    return _handler_singleton
