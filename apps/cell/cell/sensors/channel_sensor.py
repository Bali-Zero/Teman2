"""ChannelSensor — inbound webhook queue depth per channel.

Reports how many ``inbound_webhooks`` rows are still pending (not yet
processed by the WebhookProcessor) per channel. This is Cell's signal
that the ack-first persistence layer (P0-6 audit 2026-04-29) is healthy:

  green   ≤ 20 pending per channel — normal queue depth
  yellow  21-100 pending           — processor is falling behind
  red     > 100 pending            — processor stuck or external retry storm

Reads from the database via an asyncpg connection; the sensor is meant
to be called from Cell's PulseLoop with a per-machine connection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Same thresholds as elsewhere in the audit — keep in sync with brainstorm
# doc P0-6_channels_ack_first.md.
_YELLOW_THRESHOLD = 20
_RED_THRESHOLD = 100

# Window for "recent" pending rows. Anything older than this is excluded
# from the green/yellow/red classification — a row stuck for >2 days is
# effectively a dead letter, not a live queue depth signal.
_RECENT_WINDOW_MINUTES = 60


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


__all__ = ["ChannelReading", "ChannelSensor"]
