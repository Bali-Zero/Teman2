"""War Room Event Sensor — consumes `war_room.event` PG LISTEN/NOTIFY channel.

The channel already exists (migration 112) and carries events like
`article_published`, `carousel_posted`, `newsletter_sent`. The SEO
Cell listens to correlate publishing activity with downstream GSC/GA4
deltas — did publishing article X for query Q move the needle 14 days
later?

Decision memo rejected the fictional `cms:articles_published` channel
(doesn't exist); this is the real one from war-room-v2.

Sprint 1: stub. Returns yellow with empty events.
Sprint 2: connects a Redis subscriber fanned out from event_bus.py,
drains events since last pulse, buffers to STM for the thinker.
"""
from __future__ import annotations

from cell_core.types import SensorReading

from apps.evaluator.seo_cell.config import WAR_ROOM_EVENT_CHANNEL


class WarRoomEventSensor:
    name = "war_room_event"

    def __init__(self, channel: str = WAR_ROOM_EVENT_CHANNEL) -> None:
        self._channel = channel

    async def read(self, **context) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={"events": []},
            metadata={
                "stub": True,
                "channel": self._channel,
                "note": "Sprint 2 drains Redis fanout subscriber",
            },
        )
