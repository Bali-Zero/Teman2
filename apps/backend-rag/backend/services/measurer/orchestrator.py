"""MeasurerOrchestrator — fan out samplers for a single post.

For a given post, pick samplers that support its platform and run them in
parallel. Aggregate :class:`SamplerResult` and record each metric datum via
:meth:`WarRoomRepository.record_metric`. Failed samplers contribute a
``source=partial`` flag but never crash the run (Law 4).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID

from backend.services.measurer.base import (
    MetricDatum,
    MetricSampler,
    SamplerResult,
)
from backend.services.war_room.models import MetricSource, WarRoomPost
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


@dataclass
class MeasurerResult:
    post_id: UUID
    sampler_results: list[SamplerResult] = field(default_factory=list)
    recorded_datums: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def any_partial(self) -> bool:
        return any(r.partial or not r.ok for r in self.sampler_results)


class MeasurerOrchestrator:
    """Dispatch samplers in parallel, record what each one produced."""

    def __init__(
        self,
        samplers: list[MetricSampler],
        repo: WarRoomRepository | None = None,
    ) -> None:
        if not samplers:
            raise ValueError("MeasurerOrchestrator requires >= 1 sampler")
        self.samplers = samplers
        self.repo = repo
        self.logger = logger

    async def measure(self, post: WarRoomPost) -> MeasurerResult:
        result = MeasurerResult(post_id=post.id)
        applicable = [s for s in self.samplers if s.supports(post.platform)]
        if not applicable:
            result.errors.append(
                f"no sampler supports platform {post.platform.value}",
            )
            return result

        sampler_results: list[SamplerResult] = await asyncio.gather(
            *[s.sample(post) for s in applicable],
        )
        result.sampler_results = sampler_results

        # record each datum; failure to record one doesn't block others
        for sr in sampler_results:
            if not sr.ok:
                result.errors.append(f"{sr.sampler_name}: {sr.error}")
            for datum in sr.data:
                try:
                    await self._record(post.id, datum, sr.partial)
                    result.recorded_datums += 1
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "record_metric failed post=%s metric=%s err=%s",
                        post.id,
                        datum.metric_name,
                        exc,
                    )
                    result.errors.append(
                        f"record {datum.metric_name}: {exc}",
                    )
        return result

    # ── Internal ──────────────────────────────────────────────────

    async def _record(
        self,
        post_id: UUID,
        datum: MetricDatum,
        partial: bool,
    ) -> None:
        if self.repo is None:
            return
        source = datum.source
        if partial:
            # Sampler returned fewer datums than expected — flag in the row
            # so dashboards can show the gap. Canonical source value used
            # for completion tracking is :class:`MetricSource.PARTIAL`.
            source = MetricSource.PARTIAL
        await self.repo.record_metric(
            post_id,
            datum.metric_name,
            datum.value,
            source,
        )
