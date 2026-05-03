"""ChannelSensor — inbound webhook queue depth per channel.

Reports how many ``inbound_webhooks`` rows are still pending (not yet
processed by the WebhookProcessor) per channel. This is Cell's signal
that the ack-first persistence layer (P0-6 audit 2026-04-29) is healthy:

  green   ≤ 20 pending per channel — normal queue depth
  yellow  21-100 pending           — processor is falling behind
  red     > 100 pending            — processor stuck or external retry storm

Reads from the database via an asyncpg connection; the sensor is meant
to be called from Cell's PulseLoop with a per-machine connection.

Sprint 1.B 2026-05-02: bridge_channels_to_sidecar() polls per-channel
HTTP /api/channels/{name}/health and emits ~/.organism/last_seen/channel.{name}.json
sidecar files for genome_aggregator_sensor consumption (closes gap 2 of
Era Post-Agentica brief for channel.* organi).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from cell.utils.organ_emitter import emit_organ_last_seen

logger = logging.getLogger("cell.sensors.channel")


# Same thresholds as elsewhere in the audit — keep in sync with brainstorm
# doc P0-6_channels_ack_first.md.
_YELLOW_THRESHOLD = 20
_RED_THRESHOLD = 100

# Window for "recent" pending rows. Anything older than this is excluded
# from the green/yellow/red classification — a row stuck for >2 days is
# effectively a dead letter, not a live queue depth signal.
_RECENT_WINDOW_MINUTES = 60

# Sprint 1.B Cell-side bridge — known channels + backend base URL
_KNOWN_CHANNELS: tuple[str, ...] = ("whatsapp", "telegram", "instagram", "web")
_BACKEND_BASE_URL = os.environ.get(
    "NUZANTARA_BACKEND_BASE_URL",
    "https://nuzantara-rag.fly.dev",
)


@dataclass
class ChannelReading:
    """One sensor reading for the inbound-webhook queue.

    Attributes:
      status: "green" | "yellow" | "red" — overall verdict.
      per_channel: {"whatsapp": 3, "telegram": 0, ...} — pending count per
        channel within the recent window.
      max_pending: max value across per_channel — the value that drove
        the status verdict.
      metadata: free-form diagnostics (window minutes, thresholds).
    """

    status: str
    per_channel: dict[str, int] = field(default_factory=dict)
    max_pending: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelSensor:
    """Reports inbound webhook queue depth per channel.

    Usage::

        async with db_pool.acquire() as conn:
            reading = await ChannelSensor().read(conn)
            if reading.status == "red":
                ...  # PulseLoop alerts
    """

    name = "channels_inbound"

    def __init__(
        self,
        *,
        yellow_threshold: int = _YELLOW_THRESHOLD,
        red_threshold: int = _RED_THRESHOLD,
        window_minutes: int = _RECENT_WINDOW_MINUTES,
    ) -> None:
        self._yellow = int(yellow_threshold)
        self._red = int(red_threshold)
        self._window = int(window_minutes)

    async def read(self, conn: Any) -> ChannelReading:
        """Query inbound_webhooks and classify the queue depth.

        Args:
            conn: an asyncpg.Connection (or any object exposing
                ``fetch(sql, *args) -> list[Record]``).

        Returns:
            ChannelReading with per_channel counts + status verdict.
        """
        try:
            rows = await conn.fetch(
                f"""
                SELECT channel, COUNT(*) AS pending
                FROM inbound_webhooks
                WHERE processed_at IS NULL
                  AND received_at > NOW() - INTERVAL '{self._window} minutes'
                GROUP BY channel
                """,
            )
        except Exception as exc:  # noqa: BLE001 — sensor must never crash PulseLoop
            return ChannelReading(
                status="red",
                metadata={
                    "reason": f"query failed: {exc}",
                    "window_minutes": self._window,
                },
            )

        per_channel = {row["channel"]: int(row["pending"]) for row in rows}
        max_pending = max(per_channel.values(), default=0)

        if max_pending > self._red:
            status = "red"
        elif max_pending > self._yellow:
            status = "yellow"
        else:
            status = "green"

        return ChannelReading(
            status=status,
            per_channel=per_channel,
            max_pending=max_pending,
            metadata={
                "window_minutes": self._window,
                "yellow_threshold": self._yellow,
                "red_threshold": self._red,
            },
        )

    async def _http_get_channel_health(self, url: str) -> dict[str, Any]:
        """HTTP GET wrapper, returns parsed JSON. Raises on network/HTTP error.

        Override-friendly seam for tests.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    async def bridge_channels_to_sidecar(self) -> dict[str, str]:
        """Poll /api/channels/{name}/health for each known channel + emit sidecar.

        Sprint 1.B 2026-05-02: closes gap 2 (channel.* visibility) for the
        genome_aggregator_sensor on Pro. Each channel becomes one sidecar
        file at ~/.organism/last_seen/channel.{name}.json.

        Returns:
            dict {channel_name: emitted_status} — always 4 entries.

        Best-effort:
            - A single channel HTTP failure produces fail status for that
              channel only; others continue.
            - emit_organ_last_seen failures are logged at debug, never raise.
        """
        results: dict[str, str] = {}
        for name in _KNOWN_CHANNELS:
            url = f"{_BACKEND_BASE_URL}/api/channels/{name}/health"
            organ_id = f"channel.{name}"
            try:
                body = await self._http_get_channel_health(url)
                status = body.get("status", "fail")
                metadata: dict[str, Any] = {
                    "queue_depth": body.get("queue_depth", -1),
                    "last_event_seen_at": body.get("last_event_seen_at"),
                }
            except Exception as exc:  # noqa: BLE001
                status = "fail"
                metadata = {"error": str(exc)[:200]}
            results[name] = status
            try:
                emit_organ_last_seen(organ_id, status, metadata=metadata)
            except Exception as exc:  # pragma: no cover — best-effort
                logger.debug(f"sidecar emit failed for {organ_id}: {exc}")
        return results


__all__ = ["ChannelReading", "ChannelSensor"]
