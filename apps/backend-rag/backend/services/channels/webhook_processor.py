"""Inbound webhook background processor (P0-6 zero-crash audit 2026-04-29).

Drains the ``inbound_webhooks`` table populated by the ack-first webhook
routers. Uses PG LISTEN on the Outbox channel ``inbound_webhook_queued``
for low-latency wake-up + a 5s polling fallback in case NOTIFY was missed
during a listener disconnect.

Lifecycle: started from ``app_factory.lifespan()`` as an asyncio task.
A single processor per machine is sufficient — concurrency safety is via
``FOR UPDATE SKIP LOCKED`` so multiple machines could each run their own
processor without double-processing.

Retry policy: 5 attempts with linear backoff (5min × attempt number).
After the 5th failure the row is marked processed with a "GIVING UP"
error message so it does not pollute the pending queue.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from backend.services.channels.inbound_webhook_repo import NOTIFY_CHANNEL

logger = logging.getLogger(__name__)


# Retry policy — see migration 145_inbound_webhooks.sql for rationale.
MAX_ATTEMPTS = 5
_BACKOFF_BASE_SECONDS = 300  # 5 minutes per attempt (linear)

# Worker tuning.
_POLL_FALLBACK_SECONDS = 5    # Drain pending if no NOTIFY for 5s.
_DRAIN_BATCH_SIZE = 50        # Rows fetched per drain pass.

# Type alias for per-channel handlers.
ChannelHandler = Callable[[dict[str, Any]], Awaitable[None]]


def _compute_backoff_seconds(*, attempts: int) -> int:
    """Compute next-retry delay in seconds.

    Linear: 5 min × attempt number. Attempt N here is the value AFTER
    increment, so the first failure gives 300s, second 600s, etc.
    """
    if attempts < 1:
        attempts = 1
    return _BACKOFF_BASE_SECONDS * attempts


def _coerce_payload_to_dict(raw: Any, *, row_id: int) -> dict[str, Any] | None:
    """Normalise asyncpg JSONB result to dict.

    Some asyncpg codec configs return JSONB as already-decoded dict;
    others return str. Handle both. Returns None on undecodable input.
    """
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "WebhookProcessor: invalid JSON in row id=%d: %s",
                row_id, exc,
            )
            return None
    logger.error(
        "WebhookProcessor: unexpected payload type %s for id=%d",
        type(raw).__name__, row_id,
    )
    return None


class WebhookProcessor:
    """LISTEN-based async worker that drains the ``inbound_webhooks`` table.

    Concurrency model:
      - Single asyncio task per machine.
      - Selects pending rows with ``FOR UPDATE SKIP LOCKED`` so multiple
        machines could each run their own processor without double-work.
      - Each row is processed inside its own short transaction; the dispatch
        itself runs OUTSIDE the transaction so a long-running handler does
        not pin a connection.

    Wake-up:
      - PG LISTEN on ``inbound_webhook_queued`` (the Outbox channel emitted
        by ``inbound_webhook_repo.persist``). Triggers immediate drain.
      - 5s polling fallback so a missed NOTIFY (listener disconnect window)
        is recovered within one cycle.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        handlers: dict[str, ChannelHandler],
    ) -> None:
        self._pool = db_pool
        self._handlers = dict(handlers)
        self._stopped = False
        self._wake_event: asyncio.Event = asyncio.Event()
        self._listen_task: asyncio.Task[None] | None = None
        self._run_task: asyncio.Task[None] | None = None

    # ── public lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        """Spawn the run loop + listener as asyncio tasks. Returns immediately."""
        self._stopped = False
        self._wake_event = asyncio.Event()
        if self._run_task is None or self._run_task.done():
            self._run_task = asyncio.create_task(
                self.run(), name="webhook-processor-run",
            )
            logger.info("WebhookProcessor: started")

    async def stop(self) -> None:
        """Signal stop and wait for the run loop to exit."""
        self._stopped = True
        self._wake_event.set()
        if self._listen_task is not None:
            self._listen_task.cancel()
        if self._run_task is not None:
            try:
                await asyncio.wait_for(self._run_task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("WebhookProcessor: stop timed out")
        logger.info("WebhookProcessor: stopped")

    # ── main loop ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main loop: drain pending, then wait for NOTIFY or 5s timeout."""
        # Spawn the listener concurrently — it pings _wake_event on NOTIFY.
        self._listen_task = asyncio.create_task(
            self._listener_loop(), name="webhook-processor-listen",
        )

        try:
            while not self._stopped:
                try:
                    await self.drain_pending()
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "WebhookProcessor: drain_pending crashed: %s", exc,
                    )

                # Wait for either NOTIFY (wake_event) or 5s timeout.
                try:
                    await asyncio.wait_for(
                        self._wake_event.wait(),
                        timeout=_POLL_FALLBACK_SECONDS,
                    )
                except asyncio.TimeoutError:
                    pass  # 5s elapsed, drain again.
                finally:
                    self._wake_event.clear()
        finally:
            if self._listen_task is not None and not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _listener_loop(self) -> None:
        """Acquire a dedicated connection, LISTEN, and ping the wake-event.

        Reconnects on disconnect with a small backoff; the polling fallback
        in run() covers the gap.
        """
        while not self._stopped:
            try:
                async with self._pool.acquire() as conn:
                    def _on_notify(_conn, _pid, channel, payload):  # noqa: ANN001
                        logger.debug(
                            "WebhookProcessor: NOTIFY on %s payload=%s",
                            channel, payload[:80] if payload else "",
                        )
                        self._wake_event.set()

                    await conn.add_listener(NOTIFY_CHANNEL, _on_notify)
                    logger.info(
                        "WebhookProcessor: LISTEN active on %s",
                        NOTIFY_CHANNEL,
                    )
                    # Hold the connection open until stopped.
                    while not self._stopped:
                        await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "WebhookProcessor: listener loop crashed (%s); "
                    "reconnect in 5s", exc,
                )
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    return

    # ── drain pass ────────────────────────────────────────────────────

    async def drain_pending(self) -> int:
        """Process all eligible pending rows. Returns count processed.

        SELECT FOR UPDATE SKIP LOCKED ensures multiple processors do not
        contend; SKIP LOCKED also makes the SELECT non-blocking so a
        long-running handler on machine A does not delay the drain on
        machine B.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT id, channel, payload, attempts
                    FROM inbound_webhooks
                    WHERE processed_at IS NULL
                      AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                    ORDER BY received_at
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                    """,
                    _DRAIN_BATCH_SIZE,
                )

                processed_count = 0
                for row in rows:
                    await self._process_one(conn, row)
                    processed_count += 1
                return processed_count

    async def _process_one(self, conn: asyncpg.Connection, row: Any) -> None:
        """Dispatch one row to its channel handler with retry semantics."""
        row_id = int(row["id"])
        channel = row["channel"]
        attempts = int(row["attempts"])

        handler = self._handlers.get(channel)
        if handler is None:
            await conn.execute(
                """
                UPDATE inbound_webhooks
                SET processed_at = NOW(),
                    error_message = $2
                WHERE id = $1
                """,
                row_id,
                f"no handler registered for channel={channel}",
            )
            logger.warning(
                "WebhookProcessor: no handler for channel=%s id=%d "
                "(marked terminal)",
                channel, row_id,
            )
            return

        payload = _coerce_payload_to_dict(row["payload"], row_id=row_id)
        if payload is None:
            await conn.execute(
                """
                UPDATE inbound_webhooks
                SET processed_at = NOW(),
                    error_message = $2
                WHERE id = $1
                """,
                row_id,
                "undecodable payload (json.loads failed)",
            )
            return

        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001 — every channel exception is retryable
            logger.exception(
                "WebhookProcessor: handler crashed for id=%d channel=%s: %s",
                row_id, channel, exc,
            )
            new_attempts = await conn.fetchval(
                """
                UPDATE inbound_webhooks
                SET attempts = attempts + 1,
                    error_message = $2,
                    next_retry_at = NOW() + (INTERVAL '1 second' * $3)
                WHERE id = $1
                RETURNING attempts
                """,
                row_id,
                str(exc)[:500],
                _compute_backoff_seconds(attempts=attempts + 1),
            )
            if int(new_attempts or 0) >= MAX_ATTEMPTS:
                # Terminal: stop retrying, free the queue.
                await conn.execute(
                    """
                    UPDATE inbound_webhooks
                    SET processed_at = NOW(),
                        error_message = $2
                    WHERE id = $1
                    """,
                    row_id,
                    f"GIVING UP after {MAX_ATTEMPTS} attempts: {str(exc)[:300]}",
                )
                logger.error(
                    "WebhookProcessor: GIVING UP id=%d channel=%s after %d "
                    "attempts", row_id, channel, MAX_ATTEMPTS,
                )
            return

        # Success.
        await conn.execute(
            "UPDATE inbound_webhooks SET processed_at = NOW() WHERE id = $1",
            row_id,
        )
        logger.debug(
            "WebhookProcessor: processed id=%d channel=%s", row_id, channel,
        )


__all__ = [
    "MAX_ATTEMPTS",
    "WebhookProcessor",
    "_compute_backoff_seconds",
]
