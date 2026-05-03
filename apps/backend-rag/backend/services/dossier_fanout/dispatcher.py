"""DomainFanoutDispatcher — one dossier → N consumers in parallel."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.services.dossier_fanout.base import (
    ConsumeResult,
    DossierConsumer,
    FanoutSkipReason,
)
from backend.services.intel.dossier_models import (
    ResearchDossier,
)
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


@dataclass
class FanoutResult:
    dossier_id: Any
    ran_at: datetime
    per_consumer: list[ConsumeResult] = field(default_factory=list)
    recorded_reuses: int = 0

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.per_consumer if r.ok and not r.skipped)

    @property
    def skip_count(self) -> int:
        return sum(1 for r in self.per_consumer if r.skipped)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.per_consumer if not r.ok and not r.skipped)


class DomainFanoutDispatcher:
    """Routes a dossier to all registered consumers whose type is in
    ``dossier.domains``; skips others. Runs them in parallel.

    Also enforces ``public_safe`` filter: consumers with
    ``require_public_safe=True`` skip non-public dossiers (design §16.3
    OSINT blindato Law 2 mapping).
    """

    def __init__(
        self,
        consumers: list[DossierConsumer],
        repo: IntelRepository | None = None,
        *,
        record_reuse: bool = True,
    ) -> None:
        self.consumers = consumers
        self.repo = repo
        self.record_reuse = record_reuse
        self.logger = logger

    async def dispatch(self, dossier: ResearchDossier) -> FanoutResult:
        result = FanoutResult(
            dossier_id=dossier.id,
            ran_at=datetime.now(timezone.utc),
        )

        async def _one(consumer: DossierConsumer) -> ConsumeResult:
            declared_domains = set(dossier.domains or [])
            if consumer.consumer_type.value not in declared_domains:
                return await consumer.noop_skip(
                    FanoutSkipReason.DOMAIN_NOT_MATCHED,
                )
            if consumer.require_public_safe and not dossier.public_safe:
                return await consumer.noop_skip(
                    FanoutSkipReason.NOT_PUBLIC_SAFE,
                )
            try:
                return await consumer.consume(dossier)
            except Exception as exc:  # noqa: BLE001 — consumers shouldn't raise
                self.logger.warning(
                    "consumer %s raised on dossier %s: %s",
                    consumer.consumer_type.value,
                    dossier.id,
                    exc,
                    exc_info=True,
                )
                return ConsumeResult(
                    consumer_type=consumer.consumer_type,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )

        result.per_consumer = await asyncio.gather(
            *[_one(c) for c in self.consumers],
        )

        if self.record_reuse and self.repo is not None:
            for r in result.per_consumer:
                if not r.ok or r.skipped:
                    continue
                try:
                    await self.repo.record_reuse(
                        dossier.id,
                        r.consumer_type,
                        consumer_entity_id=r.entity_id,
                        context=r.meta or None,
                    )
                    result.recorded_reuses += 1
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "record_reuse failed dossier=%s consumer=%s: %s",
                        dossier.id,
                        r.consumer_type.value,
                        exc,
                    )

        return result
