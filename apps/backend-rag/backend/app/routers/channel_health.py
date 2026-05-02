"""Channel health endpoint for Cell-side heartbeat bridge.

Sprint 1.B (2026-05-02) — exposes per-channel health for Cell's
channel_sensor to poll. Cell on Pro then writes sidecar files to
~/.organism/last_seen/channel.{name}.json which genome_aggregator_sensor
consumes.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5

Status thresholds (mirror of ChannelSensor):
- ok:        queue_depth <= 20
- degraded:  21 <= queue_depth <= 100
- fail:      queue_depth > 100
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_optional_database_pool

router = APIRouter(prefix="/api/channels", tags=["channels", "health"])

KNOWN_CHANNELS: frozenset[str] = frozenset(
    {"whatsapp", "telegram", "instagram", "web"}
)

_OK_CEILING = 20
_DEGRADED_CEILING = 100


def _classify(queue_depth: int) -> str:
    if queue_depth <= _OK_CEILING:
        return "ok"
    if queue_depth <= _DEGRADED_CEILING:
        return "degraded"
    return "fail"


@router.get("/{name}/health")
async def channel_health(
    name: str,
    db_pool: Any = Depends(get_optional_database_pool),
) -> dict[str, Any]:
    """Return current health for a known channel name.

    Args:
        name: one of whatsapp/telegram/instagram/web.

    Returns:
        {status, ts, channel, queue_depth, last_event_seen_at, metadata}.

    Raises:
        404: if name not in KNOWN_CHANNELS.
    """
    if name not in KNOWN_CHANNELS:
        raise HTTPException(status_code=404, detail=f"unknown channel: {name}")

    queue_depth = 0
    last_event_seen_at: float | None = None

    if db_pool is not None:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE processed_at IS NULL) AS pending,
                    EXTRACT(EPOCH FROM MAX(received_at)) AS last_ts
                FROM inbound_webhooks
                WHERE channel = $1 AND received_at >= NOW() - INTERVAL '60 minutes'
                """,
                name,
            )
            if row is not None:
                queue_depth = int(row["pending"] or 0)
                last_event_seen_at = (
                    float(row["last_ts"]) if row["last_ts"] is not None else None
                )

    return {
        "status": _classify(queue_depth),
        "ts": time.time(),
        "channel": name,
        "queue_depth": queue_depth,
        "last_event_seen_at": last_event_seen_at,
        "metadata": {
            "thresholds": {"ok": _OK_CEILING, "degraded": _DEGRADED_CEILING},
            "window_minutes": 60,
        },
    }
