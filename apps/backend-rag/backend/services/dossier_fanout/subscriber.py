"""IntelEventSubscriber — bridge pg_notify('intel_event') → fanout.

Registered on the existing :class:`EventBus` for the ``intel.event`` event
type (mapped from PG channel ``intel_event`` in migration 113 / event_bus
PG_CHANNEL_MAP).

Payload shape (from :class:`IntelEventPayload`):
    - event_type: trend_signal_detected | dossier_created | dossier_updated
    - dossier_id: UUID when dossier event
    - slug: str when dossier event

We only react to ``dossier_created`` / ``dossier_updated``. Trend events are
consumed by the Compiler (Sprint 13), not the fanout.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.services.dossier_fanout.dispatcher import (
    DomainFanoutDispatcher,
    FanoutResult,
)
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


DOSSIER_EVENT_TYPES = {"dossier_created", "dossier_updated"}


class IntelEventSubscriber:
    """Handler registered on EventBus for ``intel.event``.

    Usage:
        subscriber = IntelEventSubscriber(repo=repo, dispatcher=dispatcher)
        bus.subscribe("intel.event", subscriber.handle)
    """

    def __init__(
        self,
        repo: IntelRepository,
        dispatcher: DomainFanoutDispatcher,
    ) -> None:
        self.repo = repo
        self.dispatcher = dispatcher
        self.logger = logger

    async def handle(self, payload: dict[str, Any]) -> FanoutResult | None:
        """EventBus handler. Always returns (never raises)."""
        event_type = payload.get("event_type")
        if event_type not in DOSSIER_EVENT_TYPES:
            return None

        dossier_id_raw = payload.get("dossier_id")
        if not dossier_id_raw:
            self.logger.debug(
                "intel.event missing dossier_id: %s", payload,
            )
            return None

        try:
            dossier_id = UUID(str(dossier_id_raw))
        except (TypeError, ValueError):
            self.logger.warning(
                "intel.event bad dossier_id %r", dossier_id_raw,
            )
            return None

        try:
            dossier = await self.repo.get_dossier(dossier_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "intel.event get_dossier failed %s: %s", dossier_id, exc,
            )
            return None

        if dossier is None:
            self.logger.info(
                "intel.event dossier %s not found (deleted?)", dossier_id,
            )
            return None

        try:
            return await self.dispatcher.dispatch(dossier)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "intel.event dispatch failed %s: %s", dossier_id, exc,
                exc_info=True,
            )
            return None
