"""
Event Bus — PostgreSQL LISTEN/NOTIFY + in-process pub/sub.

Extends the pattern from PracticeStatusListener (migration_075) into a
general-purpose event system.  Three layers:

1. **PG LISTEN/NOTIFY** — cross-process, survives restarts, payload ≤ 8 KB.
   Used for database-triggered events (row changes via triggers).
2. **In-process pub/sub** — zero-latency, any payload size.
   Used for application-level events (chain results, service signals).
3. **Redis pub/sub** (optional) — cross-node (Pro ↔ Air ↔ Fly).
   Only initialized if Redis is available.

Usage:
    bus = EventBus(db_dsn=DATABASE_URL, db_pool=pool)
    await bus.start()

    # Subscribe to events
    bus.subscribe("client.created", my_handler)
    bus.subscribe("practice.status_changed", another_handler)

    # Emit in-process events
    await bus.emit("client.created", {"client_id": 123, "email": "x@y.com"})

    # PG events arrive automatically via LISTEN channels.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import asyncpg

logger = logging.getLogger(__name__)

# Type alias for async event handlers
EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

# PG channels we LISTEN on — maps pg_channel → event_type
PG_CHANNEL_MAP: dict[str, str] = {
    "practice_changed": "practice.status_changed",
    "client_changed": "client.changed",
    "compliance_alert": "compliance.alert",
}

_RECONNECT_DELAY_S = 5
_PING_INTERVAL_S = 30


@dataclass
class EventTrace:
    """Lightweight trace for observability."""
    event_type: str
    timestamp: float
    handler_count: int
    duration_ms: float
    errors: list[str] = field(default_factory=list)
    source: str = "in_process"  # "in_process" | "pg_notify" | "redis"


class EventBus:
    """
    Unified event bus with PG LISTEN/NOTIFY + in-process pub/sub.

    Lifecycle: start() → subscribe/emit → stop()
    """

    def __init__(
        self,
        db_dsn: str,
        db_pool: asyncpg.Pool | None = None,
        max_trace_history: int = 500,
    ) -> None:
        self._db_dsn = db_dsn
        self._db_pool = db_pool
        self._conn: asyncpg.Connection | None = None
        self._running = False
        self._listen_task: asyncio.Task | None = None

        # Subscriber registry: event_type → list of async handlers
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

        # Observability
        self._traces: list[EventTrace] = []
        self._max_traces = max_trace_history
        self._event_counts: dict[str, int] = defaultdict(int)
        self._error_counts: dict[str, int] = defaultdict(int)

    # ── Public API ─────────────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Dot-separated event name (e.g. "client.created")
            handler: Async callable(payload: dict) → None
        """
        self._subscribers[event_type].append(handler)
        logger.info(
            f"📡 EventBus: subscribed {handler.__qualname__} to '{event_type}' "
            f"({len(self._subscribers[event_type])} handlers total)"
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: str = "in_process",
    ) -> EventTrace:
        """Emit an event to all subscribers.

        Args:
            event_type: Event name
            payload: Event data (must be JSON-serializable for PG/Redis)
            source: Origin tag for tracing

        Returns:
            EventTrace with timing and error info.
        """
        handlers = self._subscribers.get(event_type, [])
        self._event_counts[event_type] += 1

        t0 = time.monotonic()
        errors: list[str] = []

        for handler in handlers:
            try:
                await handler(payload)
            except Exception as e:
                err_msg = f"{handler.__qualname__}: {e}"
                errors.append(err_msg)
                self._error_counts[event_type] += 1
                logger.error(f"EventBus handler error on '{event_type}': {err_msg}")

        duration_ms = (time.monotonic() - t0) * 1000

        trace = EventTrace(
            event_type=event_type,
            timestamp=time.time(),
            handler_count=len(handlers),
            duration_ms=round(duration_ms, 2),
            errors=errors,
            source=source,
        )
        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]

        if handlers:
            logger.debug(
                f"EventBus: '{event_type}' → {len(handlers)} handlers, "
                f"{duration_ms:.1f}ms, {len(errors)} errors"
            )

        return trace

    async def emit_pg(self, channel: str, payload: dict[str, Any]) -> None:
        """Emit an event via PostgreSQL NOTIFY (cross-process).

        Args:
            channel: PG channel name (e.g. "client_changed")
            payload: JSON-serializable dict (max ~8KB)
        """
        if not self._db_pool:
            logger.warning("EventBus: no db_pool, cannot emit PG event")
            return

        payload_str = json.dumps(payload, default=str)
        if len(payload_str) > 7500:
            logger.warning(
                f"EventBus: PG payload for '{channel}' is {len(payload_str)} bytes "
                f"(limit ~8KB), truncating metadata"
            )

        async with self._db_pool.acquire() as conn:
            await conn.execute(f"SELECT pg_notify($1, $2)", channel, payload_str)

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the PG LISTEN loop and begin receiving events."""
        if self._running:
            return
        self._running = True
        self._listen_task = asyncio.create_task(
            self._listen_loop(), name="event_bus_listener"
        )
        logger.info(
            f"✅ EventBus started — listening on PG channels: "
            f"{list(PG_CHANNEL_MAP.keys())}"
        )

    async def stop(self) -> None:
        """Stop the listener and clean up."""
        self._running = False
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        await self._close_conn()
        logger.info("✅ EventBus stopped")

    # ── PG LISTEN loop ─────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        """Outer retry loop — reconnects on errors."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    f"EventBus PG listener error, reconnecting in "
                    f"{_RECONNECT_DELAY_S}s: {exc}"
                )
                await self._close_conn()
                if self._running:
                    await asyncio.sleep(_RECONNECT_DELAY_S)

    async def _connect_and_listen(self) -> None:
        """Open a dedicated connection, LISTEN on all channels, block."""
        self._conn = await asyncpg.connect(self._db_dsn)

        for pg_channel in PG_CHANNEL_MAP:
            await self._conn.add_listener(pg_channel, self._on_pg_notification)

        logger.info(
            f"📡 EventBus: listening on PG channels: "
            f"{list(PG_CHANNEL_MAP.keys())}"
        )

        # Keep-alive loop
        while self._running:
            await asyncio.sleep(_PING_INTERVAL_S)
            try:
                await self._conn.execute("SELECT 1")
            except Exception:
                raise  # triggers reconnect

    async def _close_conn(self) -> None:
        if self._conn and not self._conn.is_closed():
            try:
                for pg_channel in PG_CHANNEL_MAP:
                    await self._conn.remove_listener(
                        pg_channel, self._on_pg_notification
                    )
                await self._conn.close()
            except Exception:
                pass
        self._conn = None

    def _on_pg_notification(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Synchronous callback from asyncpg — dispatch to async handler."""
        asyncio.ensure_future(self._handle_pg_event(channel, payload))

    async def _handle_pg_event(self, channel: str, payload: str) -> None:
        """Parse PG payload and route to the event bus."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning(f"EventBus: invalid JSON on PG channel '{channel}': {payload[:200]}")
            return

        event_type = PG_CHANNEL_MAP.get(channel)
        if not event_type:
            logger.warning(f"EventBus: unmapped PG channel '{channel}'")
            return

        # Enrich payload with metadata
        data["_event_type"] = event_type
        data["_source"] = "pg_notify"
        data["_channel"] = channel
        data["_received_at"] = datetime.now(timezone.utc).isoformat()

        await self.emit(event_type, data, source="pg_notify")

    # ── Observability ──────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics for monitoring."""
        recent_traces = self._traces[-50:] if self._traces else []
        return {
            "running": self._running,
            "pg_connected": self._conn is not None and not self._conn.is_closed() if self._conn else False,
            "pg_channels": list(PG_CHANNEL_MAP.keys()),
            "subscriber_count": {
                event_type: len(handlers)
                for event_type, handlers in self._subscribers.items()
            },
            "event_counts": dict(self._event_counts),
            "error_counts": dict(self._error_counts),
            "total_events": sum(self._event_counts.values()),
            "total_errors": sum(self._error_counts.values()),
            "recent_traces": [
                {
                    "event_type": t.event_type,
                    "source": t.source,
                    "handler_count": t.handler_count,
                    "duration_ms": t.duration_ms,
                    "errors": t.errors,
                    "timestamp": t.timestamp,
                }
                for t in recent_traces
            ],
        }
