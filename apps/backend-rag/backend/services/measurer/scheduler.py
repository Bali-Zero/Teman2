"""MeasurementScheduler — run the orchestrator at T+24h / T+72h / T+7d.

Cron shape (design §13): every 6h the scheduler sweeps published posts
whose age falls inside one of three ±1h windows centred on the design
milestones. For each qualifying post, it invokes
:class:`MeasurerOrchestrator.measure(post)`.

Idempotence: multiple cron runs within the same window will re-measure
(metric rows in war_room_metrics are append-only — that's intentional,
they form a time series). We tag each cron run with a ``window`` meta
(t_24h, t_72h, t_7d) via the orchestrator's result so the dashboard can
pick one datum per window if it wants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

import asyncpg

from backend.services.measurer.orchestrator import (
    MeasurerOrchestrator,
    MeasurerResult,
)
from backend.services.war_room.models import (
    Platform,
    RegisterTone,
    WarRoomPost,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


class MeasurementWindow(str, Enum):
    T_24H = "t_24h"
    T_72H = "t_72h"
    T_7D = "t_7d"


_WINDOW_AGE: dict[MeasurementWindow, timedelta] = {
    MeasurementWindow.T_24H: timedelta(hours=24),
    MeasurementWindow.T_72H: timedelta(hours=72),
    MeasurementWindow.T_7D: timedelta(days=7),
}

# Half-width of each ±window centered on the age milestone. With cron every
# 6h, a half-width of 3h+15min safely covers even a missed tick without
# double-counting (we accept the append-only nature of war_room_metrics).
DEFAULT_HALF_WIDTH: timedelta = timedelta(hours=3, minutes=15)


@dataclass
class SchedulerResult:
    ran_at: datetime
    posts_measured: int = 0
    windows_hit: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    per_post: list[MeasurerResult] = field(default_factory=list)


class MeasurementScheduler:
    """Find posts in age windows + invoke orchestrator per post."""

    def __init__(
        self,
        repo: WarRoomRepository,
        orchestrator: MeasurerOrchestrator,
        *,
        half_width: timedelta | None = None,
        windows: tuple[MeasurementWindow, ...] | None = None,
    ) -> None:
        self.repo = repo
        self.orchestrator = orchestrator
        self.half_width = half_width or DEFAULT_HALF_WIDTH
        self.windows = windows or tuple(MeasurementWindow)
        self.logger = logger

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> SchedulerResult:
        now = now or datetime.now(timezone.utc)
        result = SchedulerResult(ran_at=now)

        seen: set[UUID] = set()
        for window in self.windows:
            age = _WINDOW_AGE[window]
            lower_age = age - self.half_width
            upper_age = age + self.half_width
            published_before = now - lower_age
            published_after = now - upper_age

            try:
                posts = await self._posts_in_age_window(
                    published_after=published_after,
                    published_before=published_before,
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"fetch {window.value}: {type(exc).__name__}: {exc}"
                )
                continue

            new_posts = [p for p in posts if p.id not in seen]
            result.windows_hit[window.value] = len(new_posts)

            for post in new_posts:
                seen.add(post.id)
                try:
                    measurement = await self.orchestrator.measure(post)
                    result.per_post.append(measurement)
                    result.posts_measured += 1
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(
                        f"measure {post.id}: {type(exc).__name__}: {exc}"
                    )
        return result

    # ── DB helpers ─────────────────────────────────────────────────

    async def _posts_in_age_window(
        self,
        *,
        published_after: datetime,
        published_before: datetime,
    ) -> list[WarRoomPost]:
        rows = await self.repo.fetch_safe(
            """
            SELECT id, draft_id, platform, post_external_id, post_url,
                   register, published_at, final_text
              FROM war_room_posts
             WHERE published_at >= $1
               AND published_at <  $2
             ORDER BY published_at ASC;
            """,
            published_after,
            published_before,
        )
        return [_row_to_post(row) for row in rows]


def _row_to_post(row: asyncpg.Record | dict) -> WarRoomPost:
    register = row["register"]
    return WarRoomPost(
        id=row["id"],
        draft_id=row["draft_id"],
        platform=Platform(row["platform"]),
        post_external_id=row["post_external_id"],
        post_url=row["post_url"],
        tone_register=RegisterTone(register) if register else None,
        published_at=row["published_at"],
        final_text=row["final_text"],
    )
