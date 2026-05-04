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
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Type alias for async event handlers
EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

# PG channels we LISTEN on — maps pg_channel → event_type
PG_CHANNEL_MAP: dict[str, str] = {
    "practice_changed": "practice.status_changed",
    "client_changed": "client.changed",
    "compliance_alert": "compliance.alert",
    # Emitted by import scripts after bulk ingest of OSS tanda terima receipts.
    # Payload: {"quarter": "Q1", "year": 2026, "pt_count": N, "receipt_count": N,
    #           "report_ids": [...], "source": "tax_drive_manual"}
    # Consumers: KG Tax subgraph sync, portal notifications, audit log.
    "lkpm_ingest_completed": "lkpm.ingest_completed",
    # Emitted by war_room_drafts status change + war_room_posts INSERT triggers
    # (migration 112). Payload: {draft_id|post_id, status|platform, event_type,
    # occurred_at}. Consumers: review_handler (Telegram review gate),
    # publisher_worker, measurer_worker, dashboard_sse.
    "war_room_event": "war_room.event",
    # Emitted by trend_signals INSERT + research_dossiers INSERT/UPDATE triggers
    # (migration 113). Payload: {signal_id|dossier_id, topic|slug, event_type,
    # occurred_at}. Consumers: dossier_compiler (batch pre-compute on new trends),
    # curiosity_gap_closer, war_room_intake, zantara_rag_indexer (upsert Qdrant),
    # crm_alert_router, connector/anomaly cognitive layers.
    "intel_event": "intel.event",
    # Emitted by 4 cognitive-layer tables (migration 114): cross_dossier_theses,
    # wr_anomaly_alerts, weekly_strategic_briefs, ultra_moves. Payload:
    # {id, table, event_type, occurred_at, + table-specific fields}.
    # Consumers: dashboard SSE, Oracle (reads upstream briefs + theses),
    # Learner (skills/scars from high-perf theses), Telegram notifier for
    # critical wr_anomaly_alerts + Oracle ultra_moves.
    "cognitive_event": "cognitive.event",
    # Emitted by 15+ alert producers (cell-organism, compliance-ops, daily-ops,
    # heartbeat-check, fly-watcher, gap_scanner, WR2 supervisor, imigrasi-monitor,
    # pajak-monitor, bi-exchange, intel-feed, vision-doc, ...) that today only
    # send to Telegram. Federation Alert Dispatcher (FAD) daemon LISTENs on
    # this channel to classify, run multi-LLM consensus, sandbox-test fixes,
    # and post Telegram approval requests. See:
    #   docs/superpowers/specs/2026-04-30-federation-alert-dispatcher.md
    # Compact payload <500B (pg_notify hard limit 8000B), full payload in
    # federation_alert_proposals table (migration 147). Schema:
    #   {v: 1, proposal_id, run_id, idempotency_key, source, severity,
    #    action_hint, _outbox_id}
    "federation_alert": "federation.alert",
    # Emitted by cell_core.observatory.emit_pulse_observed() (PR-1, 2026-05-01)
    # for any cell with CELL_OBSERVATORY_EMIT=true. Payload v1:
    # {event_version, cell_id, cell_kind, pulse_id, pulse_timestamp,
    #  phase, sensors[], pulse_result{classifier_self,...},
    #  homeostatic_state{stress_level,energy_level,...}, scar_signals[],
    #  metadata{host,machine_role,...}, _outbox_id}.
    # Consumer: apps/cell-observatory-collector (PR-3, Pro local SQLite).
    "cell_pulse_observed": "cell.pulse.observed",
    # Emitted by post_metrics_history + m13_retrain_log AFTER INSERT triggers
    # (migration 152, Sprint 2 measurer event-driven compliance — Symbiosis
    # Law 4). Payload: {metric_id|retrain_id, post_id|trigger_type,
    # horizon_hours|delta_pct, metric_name, metric_value, source, event_type,
    # occurred_at, _outbox_id}. event_type ∈ {metric_recorded, retrain_executed}.
    # Consumers: M14 learner (per Sprint 2 plan), measurer dashboards (replaces
    # current 6h polling). See:
    #   docs/audits/sprint0/wr2-ipc-mechanism.md § "Violation 1"
    #   docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md
    "measurer_event": "measurer.event",
    # Emitted by crm_welcome_runs AFTER INSERT trigger (migration 153, Sprint
    # 3 W2 CRM-cell consolidation). Fires ONLY when success=true (full
    # 4-step welcome completed: practice + Drive folder + WhatsApp + email).
    # Payload: {client_id, practice_id, drive_folder_id, channels_sent[],
    # event_type='welcome_completed', occurred_at, _outbox_id}.
    # Consumers: analytics dashboards, retention loop, future onboarding cell.
    # See: docs/sprint3/crm-cell-design.md § Q2c.
    "crm_welcome_completed": "crm.welcome_completed",
    # Emitted by asset_provenance INSERT/UPDATE trigger (migration 155, Sprint
    # 3 W2 Mata-Garuda L4.5 cell promotion). Payload: {provenance_id,
    # asset_kind, asset_id, source, confidence, owner, valid_until,
    # invalidation_event_topic, invalidation_mode, event_type, occurred_at,
    # _outbox_id}. event_type ∈ {provenance_recorded, provenance_updated}.
    # Consumers: WR2 supervisor (asset_invalidated reactor), oracle citation
    # guard, KG entity demotion cron. asset_kind ∈ 12 canonical Bali-Zero
    # values (war_room_draft..measurer_metric — see migration 154).
    # See: docs/sprint3/mata-garuda-cell-design.md.
    "asset_provenance": "mata_garuda.asset_provenance",
}

_RECONNECT_DELAY_S = 5
_PING_INTERVAL_S = 30
_HANDLER_TIMEOUT_S = 10  # max seconds per handler before it is cancelled


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
                await asyncio.wait_for(handler(payload), timeout=_HANDLER_TIMEOUT_S)
            except asyncio.TimeoutError:
                err_msg = f"{handler.__qualname__}: timed out after {_HANDLER_TIMEOUT_S}s"
                errors.append(err_msg)
                self._error_counts[event_type] += 1
                logger.error(f"EventBus handler timeout on '{event_type}': {err_msg}")
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

        P0-2 phase 2: this method now delegates to
        :func:`backend.services.events.outbox.publish` so the event is
        recorded in ``events_outbox`` BEFORE the pg_notify fires. That
        makes the publication durable across listener reconnect windows:
        :meth:`_replay_outbox_on_reconnect` re-dispatches any unconsumed
        row when the listener comes back up.

        Args:
            channel: PG channel name (e.g. ``"client_changed"``). Must
                satisfy :func:`backend.services.events.outbox.validate_channel`
                — alphanumeric + underscore, ≤ 63 chars.
            payload: JSON-serializable dict (max ~8KB).
        """
        if not self._db_pool:
            logger.warning("EventBus: no db_pool, cannot emit PG event")
            return

        # Lightweight size warning preserved from phase 1 — outbox.publish
        # re-serialises with _outbox_id injected, so we flag the raw size
        # before it grows further.
        payload_str = json.dumps(payload, default=str)
        if len(payload_str) > 7500:
            logger.warning(
                f"EventBus: PG payload for '{channel}' is {len(payload_str)} bytes "
                f"(limit ~8KB), truncating metadata"
            )

        # Local import: outbox imports nothing from event_bus, but package
        # __init__ may pull both — defer to avoid module-load surprises.
        from backend.services.events.outbox import publish as outbox_publish

        async with self._db_pool.acquire() as conn:
            await outbox_publish(conn, channel, payload)

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

        # Replay events that landed in events_outbox while the listener was
        # disconnected. This closes the durability gap of pg_notify (volatile,
        # no queue) — see cicatrix scar "EventBus is PG LISTEN/NOTIFY but
        # Symbiosis docs say Redis Streams (2026-04-29)" and migration 144.
        #
        # Phase 2 (this PR): emit_pg() and the DB triggers in migration 146
        # write to events_outbox before pg_notify fires, so every event on a
        # PG_CHANNEL_MAP channel is durable. Phase 1 had only the helper +
        # this hook in place — replay was a no-op until producers wired in.
        # Best-effort: a failure here must NOT block the listener loop.
        await self._replay_outbox_on_reconnect()

        # Keep-alive loop
        while self._running:
            await asyncio.sleep(_PING_INTERVAL_S)
            try:
                await self._conn.execute("SELECT 1")
            except Exception:
                raise  # triggers reconnect

    async def _replay_outbox_on_reconnect(self) -> None:
        """Replay unconsumed events_outbox rows for every known PG channel.

        Foundation hook for the P0-2 outbox pattern (migration 144).
        Uses a connection acquired from ``self._db_pool`` rather than the
        long-lived listener connection — fetching+acking happens off the
        listen path so a slow query cannot starve the keep-alive ping.

        If ``self._db_pool`` is not set (legacy callers that constructed
        EventBus with ``db_pool=None``), the replay is silently skipped:
        the listener still works, just without durability. We log a
        single info line so the gap is visible in deployment logs.

        All exceptions are swallowed and logged: replay is best-effort
        and must never bring down the listener.
        """
        if self._db_pool is None:
            logger.info(
                "EventBus: outbox replay skipped — no db_pool configured"
            )
            return

        try:
            from backend.services.events.outbox import replay_unconsumed
        except Exception as exc:  # noqa: BLE001 — module import is the failure
            logger.error("EventBus: outbox module unavailable: %s", exc)
            return

        total = 0
        try:
            async with self._db_pool.acquire() as replay_conn:
                for pg_channel in PG_CHANNEL_MAP:
                    async def _dispatch(
                        payload: dict[str, Any], _ch: str = pg_channel
                    ) -> None:
                        await self._handle_pg_event(
                            _ch, json.dumps(payload, default=str)
                        )

                    try:
                        count = await replay_unconsumed(
                            replay_conn,
                            _dispatch,
                            channel=pg_channel,
                            max_age_minutes=60,
                        )
                    except Exception as exc:  # noqa: BLE001 — per-channel isolation
                        logger.error(
                            "EventBus: outbox replay failed for '%s': %s",
                            pg_channel,
                            exc,
                            exc_info=True,
                        )
                        continue

                    if count > 0:
                        logger.warning(
                            "📡 EventBus: replayed %d unconsumed events on '%s'",
                            count,
                            pg_channel,
                        )
                        total += count
        except Exception as exc:  # noqa: BLE001 — pool acquire / unexpected
            logger.error(
                "EventBus: outbox replay aborted: %s", exc, exc_info=True
            )
            return

        if total == 0:
            logger.debug("EventBus: outbox replay found nothing to replay")

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
