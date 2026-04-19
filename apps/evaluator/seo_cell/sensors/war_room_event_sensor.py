"""War Room Event Sensor — polls war_room_posts for recent publications.

Design choice vs LISTEN/NOTIFY:
The war_room.event channel (migration 112) fans out via PG LISTEN/
NOTIFY. The cell pulses every 24h, so a long-lived LISTEN connection
between pulses adds no value — we only need a snapshot of what got
published since the last pulse. We therefore **poll war_room_posts
by published_at** instead of subscribing. This keeps the sensor
stateless, avoids holding a DB connection across the 24h idle window,
and still captures every publish event (the table is the source of
truth; the pub/sub is just an optimization for consumers that need
real-time).

Returns a SensorReading carrying:
  value.event_count    — total posts published in the last window
  value.by_platform    — {platform: count} for blog/carousel/etc.
  value.recent_posts   — last N posts with platform, published_at, uri

Window defaults to 24h (the pulse interval). Since we run daily, each
pulse sees all posts published since yesterday.

Failure policy mirrors GSCSensor/GA4Sensor: sensor never raises.
  - no DATABASE_URL                 → yellow, error_code=db_url_missing
  - asyncpg import failure          → red,    error_code=import_error
  - connection/query error          → red,    error_code=db_error
  - any other exception             → red,    error_code=unexpected
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from cell_core.types import SensorReading

logger = logging.getLogger("seo_cell.sensors.war_room_event")

_DEFAULT_WINDOW_HOURS = 24
_TOP_N_KEEP = 50


class WarRoomEventSensor:
    name = "war_room_event"

    def __init__(
        self,
        window_hours: int = _DEFAULT_WINDOW_HOURS,
        db_url: str | None = None,
    ) -> None:
        self._window_hours = window_hours
        # Defer resolution to read() so env changes between runs are honored
        self._db_url_override = db_url

    def _resolve_db_url(self) -> str | None:
        return self._db_url_override or os.environ.get("DATABASE_URL")

    async def read(self, **context) -> SensorReading:
        db_url = self._resolve_db_url()
        if not db_url:
            return self._yellow(
                "db_url_missing",
                "DATABASE_URL not set (and no override)",
            )

        try:
            rows = await self._fetch_posts(db_url)
        except _WarRoomEventError as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[war_room_event] unexpected failure")
            return self._red("unexpected", repr(e))

        by_platform: dict[str, int] = {}
        recent = []
        for r in rows:
            platform = r.get("platform") or "unknown"
            by_platform[platform] = by_platform.get(platform, 0) + 1
            recent.append(
                {
                    "platform": platform,
                    "published_at": _isoformat_or_none(r.get("published_at")),
                    "post_url": r.get("post_url"),
                    "draft_id": str(r.get("draft_id")) if r.get("draft_id") else None,
                    "register": r.get("register"),
                }
            )

        # Sort recent by published_at desc, keep top N
        recent.sort(key=lambda p: p.get("published_at") or "", reverse=True)
        recent = recent[:_TOP_N_KEEP]

        status = "green" if rows else "yellow"
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value={
                "event_count": len(rows),
                "by_platform": by_platform,
                "recent_posts": recent,
            },
            metadata={
                "window_hours": self._window_hours,
                "table": "war_room_posts",
            },
        )

    # ── internal ──────────────────────────────────────────────────────────

    async def _fetch_posts(self, db_url: str) -> list[dict[str, Any]]:
        """Query war_room_posts for rows published in the window."""
        try:
            import asyncpg
        except ImportError as e:
            raise _WarRoomEventError("import_error", f"missing dep: {e}") from e

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._window_hours)
        try:
            conn = await asyncpg.connect(db_url, timeout=10)
        except Exception as e:
            raise _WarRoomEventError(
                "db_error", f"connect failed: {e!r}"
            ) from e
        try:
            # Defensive query — SELECT * with specific columns we need, ignore
            # extras. Matches migration 112 schema without binding to it tightly.
            rows = await conn.fetch(
                """
                SELECT draft_id, platform, published_at, post_url, register
                FROM war_room_posts
                WHERE published_at >= $1
                ORDER BY published_at DESC
                LIMIT 500
                """,
                cutoff,
            )
        except Exception as e:
            raise _WarRoomEventError(
                "db_error", f"query failed: {e!r}"
            ) from e
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "event_count": 0,
                "by_platform": {},
                "recent_posts": [],
            },
            metadata={
                "window_hours": self._window_hours,
                "error_code": code,
                "error": msg,
            },
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[war_room_event] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "event_count": 0,
                "by_platform": {},
                "recent_posts": [],
            },
            metadata={
                "window_hours": self._window_hours,
                "error_code": code,
                "error": msg,
            },
        )


class _WarRoomEventError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _isoformat_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
