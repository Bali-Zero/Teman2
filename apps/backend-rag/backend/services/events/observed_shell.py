"""ObservedShellBus — lightweight observability sink for the observed-shell tier.

Sprint 0 Track C2. Reference: brainstorm 2026-05-02 round 2 § "Codex
observed-shell tier proposal".

Why this exists:

The brainstorm round 2 unanimously chose Opzione C ("split clean") for the
runtime layer: cron-agent-python keeps 18/19 strategies, OpenClaw keeps
Telegram + Lobster + Knowledge Agents. But there's a third class of
automations that don't fit either side cleanly — they're not cell candidates
(would fail 7 Leggi admission), but they DO need a durable trace of their
runs so monitoring catches silent failures.

Examples Codex named: translation hourly cron, BI exchange-rate daily,
imigrasi-monitor / oss-monitor / pajak-monitor, fly-pg-backup,
qdrant-snapshot, mos-maintenance, sync-memory-to-nlm, webhooks. They
emit events without importing cell-core.

What's the shape:

    from backend.services.events.observed_shell import ObservedShellBus

    bus = ObservedShellBus(db_pool)
    await bus.emit("translate.hourly", "ok", {
        "duration_ms": 1234,
        "items": 42,
    })

If the DB pool is unavailable (None or connection error), `emit()` falls
back to a JSONL file at ``~/logs/observed-shell.jsonl`` so the trace
survives restart and a later sync can hydrate the DB row. This is the
"graceful degradation" pattern from Symbiosis Law 4 applied at the
observability layer — we never let observability outages cascade into
the parent automation.

This module is INTENTIONALLY simpler than ``outbox.py`` (which has
replay/ack semantics for cell IPC). observed_shell is fire-and-store:
no replay, no ack, no dispatch.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import pathlib
import sys
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

VALID_STATUSES = ("ok", "error", "warning", "skipped")

JSONL_FALLBACK = pathlib.Path("~/logs/observed-shell.jsonl").expanduser()


class ObservedShellBus:
    """Emit observed-shell events to Postgres or fall back to a JSONL file.

    Construct once per process (preferably bound to the FastAPI lifespan
    `app.state.observed_shell_bus`) and reuse. The class itself is
    stateless beyond the pool reference; multiple instances against the
    same pool are safe.
    """

    def __init__(self, db_pool: asyncpg.Pool | None = None) -> None:
        self.db_pool = db_pool

    async def emit(
        self,
        automation_name: str,
        status: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Record one observed-shell event.

        On success: a row in ``observed_shell_events`` (mig 151) with
        the payload JSON-serialised. On failure (no pool, conn error,
        DB write error): a line appended to JSONL_FALLBACK.

        This function NEVER raises. The caller's automation must not
        fail because observability is unavailable.
        """
        if status not in VALID_STATUSES:
            logger.warning(
                "ObservedShellBus.emit: invalid status %r for %r — coercing to 'error'",
                status,
                automation_name,
            )
            status = "error"

        record = {
            "automation_name": automation_name,
            "status": status,
            "payload": payload or {},
            "trace_id": trace_id,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

        if self.db_pool is None:
            self._fallback_to_jsonl(record, reason="no db_pool")
            return

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO observed_shell_events
                        (automation_name, status, payload, trace_id)
                    VALUES ($1, $2, $3::jsonb, $4)
                    """,
                    automation_name,
                    status,
                    json.dumps(record["payload"]),
                    trace_id,
                )
        except (asyncpg.PostgresError, OSError) as e:
            self._fallback_to_jsonl(record, reason=f"db error: {e!r}")
        except Exception as e:  # noqa: BLE001
            # Defensive net: ANY exception falls back. Observability MUST
            # NOT cascade into automation failure.
            self._fallback_to_jsonl(record, reason=f"unexpected: {e!r}")

    @staticmethod
    def _fallback_to_jsonl(record: dict[str, Any], reason: str) -> None:
        """Append the record to the JSONL fallback file."""
        try:
            JSONL_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps({**record, "_fallback_reason": reason})
            with JSONL_FALLBACK.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as e:
            # Last resort: stderr. Don't crash the caller.
            print(
                f"observed-shell: fallback FAILED ({e}). lost record: "
                f"{record}",
                file=sys.stderr,
            )


async def emit_one(
    db_pool: asyncpg.Pool | None,
    automation_name: str,
    status: str,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> None:
    """Convenience function — construct a bus and emit a single event."""
    await ObservedShellBus(db_pool).emit(automation_name, status, payload, trace_id)


__all__ = ["ObservedShellBus", "emit_one", "JSONL_FALLBACK", "VALID_STATUSES"]
