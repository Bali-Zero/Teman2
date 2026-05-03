"""AnomalyEventSubscriber — bridge intel.event → AnomalyDetector.

Listens on ``intel.event`` (PG channel ``intel_event``, registered in
event_bus.PG_CHANNEL_MAP) and invokes the detector on newly created
dossiers. Analogous to :class:`IntelEventSubscriber` in the fanout
package, but only reacts to ``dossier_created`` (not updates, which
may be refreshes and shouldn't spam the alerter).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.services.cognitive.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
)
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


TRIGGER_EVENT_TYPES = {"dossier_created"}


class AnomalyEventSubscriber:
    """EventBus handler: intel.event:dossier_created → detector."""

    def __init__(
        self,
        intel_repo: IntelRepository,
        detector: AnomalyDetector,
    ) -> None:
        self.intel_repo = intel_repo
        self.detector = detector
        self.logger = logger

    async def handle(self, payload: dict[str, Any]) -> AnomalyResult | None:
        event_type = payload.get("event_type")
        if event_type not in TRIGGER_EVENT_TYPES:
            return None

        dossier_id_raw = payload.get("dossier_id")
        if not dossier_id_raw:
            self.logger.debug("anomaly subscriber: missing dossier_id")
            return None
        try:
            dossier_id = UUID(str(dossier_id_raw))
        except (TypeError, ValueError):
            self.logger.warning(
                "anomaly subscriber bad dossier_id %r", dossier_id_raw,
            )
            return None

        try:
            dossier = await self.intel_repo.get_dossier(dossier_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "anomaly subscriber get_dossier failed %s: %s",
                dossier_id,
                exc,
            )
            return None
        if dossier is None:
            self.logger.info(
                "anomaly subscriber dossier %s not found", dossier_id,
            )
            return None

        try:
            return await self.detector.analyze_dossier(dossier)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "anomaly subscriber analyze failed %s: %s",
                dossier_id,
                exc,
                exc_info=True,
            )
            return None
