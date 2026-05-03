"""Abstract base classes for Measurer samplers + data contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from backend.services.war_room.models import MetricSource, Platform, WarRoomPost

# Canonical metric names — keeps war_room_metrics queries consistent.
METRIC_REACH = "reach"
METRIC_IMPRESSIONS = "impressions"
METRIC_SAVES = "saves"
METRIC_SHARES = "shares"
METRIC_LIKES = "likes"
METRIC_COMMENTS = "comments"
METRIC_CLICKS = "clicks"
METRIC_LEADS_ATTRIBUTED = "leads_attributed"
METRIC_VIDEO_VIEWS = "video_views"

ALL_METRIC_NAMES: frozenset[str] = frozenset({
    METRIC_REACH,
    METRIC_IMPRESSIONS,
    METRIC_SAVES,
    METRIC_SHARES,
    METRIC_LIKES,
    METRIC_COMMENTS,
    METRIC_CLICKS,
    METRIC_LEADS_ATTRIBUTED,
    METRIC_VIDEO_VIEWS,
})


class SamplerError(RuntimeError):
    """Raised on configuration errors. Per-call failures surface in SamplerResult."""


@dataclass
class MetricDatum:
    """A single (metric_name, value, source, timestamp) tuple bound to a post."""

    metric_name: str
    value: float
    source: MetricSource
    collected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    meta: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metric_name not in ALL_METRIC_NAMES:
            # Not a hard error — allow extensions — but warn loudly
            # so accidental typos surface during code review.
            import logging

            logging.getLogger(__name__).debug(
                "non-canonical metric name: %s", self.metric_name,
            )


@dataclass
class SamplerResult:
    sampler_name: str
    post_id: UUID
    ok: bool
    data: list[MetricDatum] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    partial: bool = False  # True when sampler returned some but not all expected datums


class MetricSampler(ABC):
    """Abstract sampler. One sampler == one data source for one platform.

    Implementations should never raise from :meth:`sample` — errors surface
    via ``SamplerResult.ok=False``.
    """

    name: str
    platforms: tuple[Platform, ...]
    source: MetricSource

    def supports(self, platform: Platform) -> bool:
        return platform in self.platforms

    @abstractmethod
    async def sample(self, post: WarRoomPost) -> SamplerResult:
        ...
