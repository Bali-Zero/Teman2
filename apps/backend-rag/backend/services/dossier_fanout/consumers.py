"""Five priority consumers (Sprint 14, design §16).

Each consumer delegates its heavy work to an injected async function.
This keeps wiring flexible: production passes real clients (Qdrant,
CRM DB, NLM CLI, KG service, EventBus), tests pass mocks.

Consumers are thin and explicit. They do NOT do their own retry logic —
the dispatcher surfaces failures as ``ConsumeResult.ok=False``; cron can
replay later or the operator can rerun.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from backend.services.dossier_fanout.base import (
    ConsumeResult,
    DossierConsumer,
)
from backend.services.intel.dossier_models import ConsumerType, ResearchDossier

logger = logging.getLogger(__name__)


# ── Function contracts (typed aliases) ──────────────────────────


# All accept the dossier and return meta/error info. None of them should
# raise; if they raise, the dispatcher captures it.
RagUpsertFn = Callable[[ResearchDossier], Awaitable[dict[str, Any]]]
CRMAlertFn = Callable[[ResearchDossier], Awaitable[dict[str, Any]]]
NLMUploadFn = Callable[[ResearchDossier], Awaitable[dict[str, Any]]]
CuriosityCloseFn = Callable[[ResearchDossier], Awaitable[dict[str, Any]]]
WarRoomNotifyFn = Callable[[ResearchDossier], Awaitable[dict[str, Any]]]


# Return-shape convention for all fn's:
#   {"ok": bool, "entity_id": str | None, "error": str | None, **meta}


def _result_from_fn_output(
    consumer_type: ConsumerType,
    output: dict[str, Any] | None,
) -> ConsumeResult:
    if not isinstance(output, dict):
        return ConsumeResult(
            consumer_type=consumer_type,
            ok=False,
            error="fn returned non-dict",
        )
    ok = bool(output.get("ok", False))
    if not ok:
        return ConsumeResult(
            consumer_type=consumer_type,
            ok=False,
            entity_id=output.get("entity_id"),
            error=str(output.get("error") or "unknown"),
            meta={k: v for k, v in output.items() if k not in {"ok", "entity_id", "error"}},
        )
    return ConsumeResult(
        consumer_type=consumer_type,
        ok=True,
        entity_id=output.get("entity_id"),
        meta={k: v for k, v in output.items() if k not in {"ok", "entity_id", "error"}},
    )


# ── 1. Zantara chatbot RAG ─────────────────────────────────────

class ZantaraRAGConsumer(DossierConsumer):
    """Upsert dossier summary into Qdrant for chatbot retrieval.

    ``rag_upsert_fn`` typically embeds ``summary_medium`` (or a concatenation
    of facts + citations) and writes a Qdrant point with a flat payload.
    """

    consumer_type = ConsumerType.CHATBOT
    require_public_safe = False   # even private dossiers can inform internal replies

    def __init__(self, rag_upsert_fn: RagUpsertFn) -> None:
        self.rag_upsert_fn = rag_upsert_fn

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        output = await self.rag_upsert_fn(dossier)
        return _result_from_fn_output(self.consumer_type, output)


# ── 2. CRM alerting ────────────────────────────────────────────

class CRMAlertingConsumer(DossierConsumer):
    """Join dossier entities with client segments, insert CRM alerts.

    The injected ``crm_alert_fn`` runs the platform-specific SQL (CRM lives
    outside backend-rag; fn bridges the gap).
    """

    consumer_type = ConsumerType.CRM
    require_public_safe = False

    def __init__(self, crm_alert_fn: CRMAlertFn) -> None:
        self.crm_alert_fn = crm_alert_fn

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        output = await self.crm_alert_fn(dossier)
        return _result_from_fn_output(self.consumer_type, output)


# ── 3. NotebookLM feeder ───────────────────────────────────────

class NLMFeederConsumer(DossierConsumer):
    """Upload dossier content as a new source into the correct NB-N.

    Routing NB-2..8 happens inside the injected ``nlm_upload_fn`` based on
    ``dossier.topic_category`` (same mapping as War Room v1 fact-check).
    NLM requires public-safe to avoid accidental leak into team-wide
    notebooks.
    """

    consumer_type = ConsumerType.NLM
    require_public_safe = True

    def __init__(self, nlm_upload_fn: NLMUploadFn) -> None:
        self.nlm_upload_fn = nlm_upload_fn

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        output = await self.nlm_upload_fn(dossier)
        return _result_from_fn_output(self.consumer_type, output)


# ── 4. KG Curiosity Loop ───────────────────────────────────────

class CuriosityConsumer(DossierConsumer):
    """Close open curiosity gaps that this dossier covers.

    The Curiosity Loop (already live) maintains open gap topics.
    ``curiosity_close_fn`` takes the dossier and marks any matching gap as
    closed, recording the dossier_id as resolution evidence.
    """

    consumer_type = ConsumerType.CURIOSITY
    require_public_safe = False

    def __init__(self, curiosity_close_fn: CuriosityCloseFn) -> None:
        self.curiosity_close_fn = curiosity_close_fn

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        output = await self.curiosity_close_fn(dossier)
        return _result_from_fn_output(self.consumer_type, output)


# ── 5. War Room Director notifier ──────────────────────────────

class WarRoomDirectorConsumer(DossierConsumer):
    """Notify the War Room Director that a fresh dossier is available.

    Typically the fn publishes on the EventBus in-process channel so M4
    Director knows there's new context to consider. Doesn't produce the
    carousel itself — that's still Zero-gated via the Intake step.
    """

    consumer_type = ConsumerType.WARROOM
    require_public_safe = False

    def __init__(self, warroom_notify_fn: WarRoomNotifyFn) -> None:
        self.warroom_notify_fn = warroom_notify_fn

    async def consume(self, dossier: ResearchDossier) -> ConsumeResult:
        output = await self.warroom_notify_fn(dossier)
        return _result_from_fn_output(self.consumer_type, output)
