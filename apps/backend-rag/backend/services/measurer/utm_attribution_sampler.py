"""UTMAttributionSampler — primary ROI source for War Room.

Joins CRM leads / contacts / practices by ``utm_campaign`` back to the
war_room_post that produced them, and writes one row per attribution into
``war_room_leads`` plus a ``leads_attributed`` metric.

The actual CRM table name varies by installation. We accept an injected
``lead_lookup_fn`` that returns an iterable of :class:`AttributedLead`
tuples for a given (post, since_at) pair. This keeps the sampler DB-agnostic
and testable, while the production wiring can use a concrete query against
the ``contacts`` / ``leads`` table (path to be wired in Sprint 12).

UTM convention:
    utm_campaign = ``warroom_<slug>``       # same slug as BlogPublisher
    utm_medium   = ``<platform>``           # ig | x | linkedin | blog | newsletter
    utm_source   = ``warroom``

This sampler only reads attributions produced within the measurement window
(``since_at``), so calling at T+24h/T+72h/T+7d yields incremental samples.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from backend.services.measurer.base import (
    METRIC_LEADS_ATTRIBUTED,
    MetricDatum,
    MetricSampler,
    SamplerResult,
)
from backend.services.war_room.models import (
    ConversionStage,
    MetricSource,
    Platform,
    WarRoomPost,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


@dataclass
class AttributedLead:
    """One lead attributed to a War Room post via UTM."""

    contact_id: UUID | None
    utm_campaign: str
    utm_medium: str | None
    utm_source: str | None
    attributed_at: datetime
    conversion_stage: ConversionStage | None = None
    revenue_idr: Decimal | None = None


LeadLookupFn = Callable[[WarRoomPost, datetime], Awaitable[list[AttributedLead]]]


class UTMAttributionSampler(MetricSampler):
    """Reads CRM leads attributed by UTM; writes war_room_leads + a metric.

    Supports all platforms — attribution works identically for IG, X,
    LinkedIn, Blog, Newsletter (each gets a distinct ``utm_medium``).
    """

    name = "utm_attribution"
    platforms = (
        Platform.INSTAGRAM,
        Platform.X,
        Platform.LINKEDIN,
        Platform.BLOG,
        Platform.NEWSLETTER,
    )
    source = MetricSource.UTM_CRM

    def __init__(
        self,
        repo: WarRoomRepository,
        lead_lookup_fn: LeadLookupFn,
        *,
        persist_leads: bool = True,
    ) -> None:
        self.repo = repo
        self.lead_lookup_fn = lead_lookup_fn
        self.persist_leads = persist_leads

    async def sample(self, post: WarRoomPost) -> SamplerResult:
        start = time.perf_counter()

        # Lookback anchored at published_at — our attribution window starts
        # when the post went live.
        since_at = post.published_at
        try:
            leads = await self.lead_lookup_fn(post, since_at)
        except Exception as exc:  # noqa: BLE001
            return SamplerResult(
                sampler_name=self.name,
                post_id=post.id,
                ok=False,
                error=f"lead_lookup_fn: {type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        persist_errors = 0
        if self.persist_leads and leads:
            for lead in leads:
                try:
                    await self.repo.attribute_lead(
                        post.id,
                        contact_id=lead.contact_id,
                        utm_campaign=lead.utm_campaign,
                        utm_medium=lead.utm_medium,
                        utm_source=lead.utm_source,
                        conversion_stage=lead.conversion_stage,
                        revenue_idr=lead.revenue_idr,
                    )
                except Exception as exc:  # noqa: BLE001 — persistence must not abort sampling
                    logger.warning(
                        "attribute_lead failed for post=%s: %s",
                        post.id,
                        exc,
                    )
                    persist_errors += 1

        datum = MetricDatum(
            metric_name=METRIC_LEADS_ATTRIBUTED,
            value=float(len(leads)),
            source=MetricSource.UTM_CRM,
            meta={
                "persist_errors": persist_errors,
                "window_start": since_at.astimezone(timezone.utc).isoformat(),
            },
        )
        return SamplerResult(
            sampler_name=self.name,
            post_id=post.id,
            ok=True,
            data=[datum],
            duration_ms=(time.perf_counter() - start) * 1000,
            partial=persist_errors > 0,
        )
