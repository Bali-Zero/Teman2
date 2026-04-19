"""Measurer — post-publication metric collection + UTM attribution.

Reference: docs/war-room-2.0-design.md §13 (M13 Measurer).

Three data sources (§13):
    1. UTM + CRM PG (primary): conversions via war_room_leads
    2. Meta Graph API: IG Business insights (reach, saves, shares...)
    3. Playwright lightweight scraper: X + LinkedIn public stats

Design cadence (§13): T+24h, T+72h, T+7g measurements per post.
All non-primary sources degrade gracefully (Law 4): on failure we record
what we have and flag ``source=partial`` on missing bits.

Modules:
    - base: abstract samplers + MetricDatum
    - meta_graph_sampler: IG Business Graph API insights
    - utm_attribution_sampler: CRM leads join by utm_campaign
    - x_scraper_sampler (TODO Sprint 12): Playwright + X public tweet page
    - linkedin_scraper_sampler (TODO Sprint 12): Playwright + LinkedIn page
    - scheduler: sweep drafts at T+24h / T+72h / T+7d
    - orchestrator: fan out samplers per post + record results
"""

from backend.services.measurer.base import (
    MetricDatum,
    MetricSampler,
    SamplerError,
    SamplerResult,
)
from backend.services.measurer.meta_graph_sampler import MetaGraphSampler
from backend.services.measurer.orchestrator import (
    MeasurerOrchestrator,
    MeasurerResult,
)
from backend.services.measurer.scheduler import (
    MeasurementScheduler,
    MeasurementWindow,
    SchedulerResult,
)
from backend.services.measurer.utm_attribution_sampler import (
    UTMAttributionSampler,
)

__all__ = [
    "MeasurementScheduler",
    "MeasurementWindow",
    "MeasurerOrchestrator",
    "MeasurerResult",
    "MetaGraphSampler",
    "MetricDatum",
    "MetricSampler",
    "SamplerError",
    "SamplerResult",
    "SchedulerResult",
    "UTMAttributionSampler",
]
