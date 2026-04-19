"""DossierConsumer ABC + shared data contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.services.intel.dossier_models import ConsumerType, ResearchDossier


class FanoutSkipReason(str, Enum):
    DOMAIN_NOT_MATCHED = "domain_not_matched"
    ALREADY_CONSUMED = "already_consumed"
    DISABLED = "disabled"
    NOT_PUBLIC_SAFE = "not_public_safe"


@dataclass
class ConsumeResult:
    consumer_type: ConsumerType
    ok: bool
    skipped: bool = False
    skip_reason: FanoutSkipReason | None = None
    entity_id: str | None = None   # e.g. Qdrant point id, CRM alert id
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class DossierConsumer(ABC):
    """One consumer of a dossier.

    Each implementation binds a ``ConsumerType`` (from design §16) to
    the side effect it performs. Dispatcher calls :meth:`consume` if
    ``self.consumer_type.value in dossier.domains``.

    Implementations MUST NOT raise from :meth:`consume`: surface errors via
    ``ConsumeResult(ok=False, error=…)`` so the dispatcher can keep other
    consumers running (Law 4 Graceful degradation).
    """

    consumer_type: ConsumerType
    require_public_safe: bool = False

    @abstractmethod
    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        ...

    async def noop_skip(
        self,
        reason: FanoutSkipReason,
    ) -> ConsumeResult:
        return ConsumeResult(
            consumer_type=self.consumer_type,
            ok=True,
            skipped=True,
            skip_reason=reason,
        )
