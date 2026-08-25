"""ClientHandoffService — F10, "client-bot handoff is a first-class module".

MANDATE.md F10: "the bot may say 'l'ho passato al team' only AFTER the
handoff row is durably created; otherwise the copy says 'puoi richiedere'."
This module is where that ordering is enforced structurally: it is the
ONLY thing ``final_gate.py`` calls when a candidate's disposition is
``"handoff"``, and it always runs the durable-insert attempt BEFORE
returning — there is no code path in this package that can produce a
``HANDOFF`` ``FinalDecision`` without this having already tried.

``HandoffOutcome`` is what a B6b golden fixture's ``reason_detail`` pins
(``"client.handoff-insert-succeeds-and-fails"``, both variants) — the
model's own ``BrainCandidate.handoff_reason_code`` is NOT echoed into the
gate's reason (every explicit handoff normalizes to
``GateReason.MODEL_REQUESTED_HANDOFF`` — verified against both golden
fixtures, which use the same model-supplied handoff_reason_code
"OUT_OF_SCOPE_REGULATED_REQUEST" for both the succeeds- and fails-insert
cases and expect an IDENTICAL GateReason either way); what actually
distinguishes the two is this service's own insert outcome.

``HandoffRepository`` is injected and optional — no handoff table/migration
exists yet (out of scope for this lane; a future lane owns the durable
store). With no repository wired, every handoff attempt reports
``ROW_INSERT_FAILED`` — the SAFE default per F10's own text: the copy must
say "puoi richiedere", never falsely claim a handoff happened.

Context carry-over (F10: "the KPI that matters") is approximated here as
"the grounding bundle's history is non-empty" — a real measure of whether
the CONSULTANT-FACING record actually carries that history belongs to
whatever renders the handoff queue entry (out of scope here); this
service can only report whether the INPUT it had available to hand off
included prior context, which is the honest signal available at this
layer.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from backend.channels.profiles import HandoffQueue
from backend.services.client_bot.contracts import BrainCandidate, BrainRequest
from backend.services.client_bot.observability import (
    record_handoff_created,
    record_handoff_creation_failed,
)

logger = logging.getLogger("zantara.backend")

__all__ = [
    "ClientHandoffService",
    "HandoffOutcome",
    "HandoffRecord",
    "HandoffRepository",
]


class HandoffOutcome(StrEnum):
    """The two values a B6b golden fixture pins as ``reason_detail`` on a
    HANDOFF ``FinalDecision`` — see module docstring.
    """

    ROW_INSERTED = "handoff_row_inserted"
    ROW_INSERT_FAILED = "handoff_row_insert_failed"


@dataclass(frozen=True)
class HandoffRecord:
    """What gets durably stored — the shape a future ``HandoffRepository``
    implementation persists. Deliberately carries no PII beyond what
    ``CanonicalMessage``/``BrainRequest`` already scrubbed to opaque
    references (CLAUDE.md §14 PII boundary).
    """

    handoff_id: UUID
    request_id: UUID
    conversation_id: UUID
    surface: str
    queue: HandoffQueue
    handoff_reason_code: str | None
    context_carried: bool
    created_at: datetime


class HandoffRepository(Protocol):
    """Injected by a future lane once a durable store exists. Returning
    ``False`` (not raising) is the expected shape for an ordinary
    insert-failed outcome; an exception is still caught by the caller as a
    defense-in-depth measure — see ``ClientHandoffService.create_handoff``.
    """

    async def insert(self, record: HandoffRecord) -> bool: ...


class ClientHandoffService:
    def __init__(self, repository: HandoffRepository | None = None) -> None:
        self._repository = repository

    async def create_handoff(
        self, candidate: BrainCandidate, request: BrainRequest
    ) -> HandoffOutcome:
        """Attempt the durable insert NOW, synchronously, before the caller
        (``final_gate.py``) is allowed to return a HANDOFF ``FinalDecision``
        — this ordering is F10's whole point, not an optimization detail.
        """
        context_carried = len(request.grounding.history) > 0
        record = HandoffRecord(
            handoff_id=uuid.uuid4(),
            request_id=request.request_id,
            conversation_id=request.message.conversation_id,
            surface=request.message.surface.value,
            queue=request.profile.handoff_queue,
            handoff_reason_code=candidate.handoff_reason_code,
            context_carried=context_carried,
            created_at=datetime.now(timezone.utc),
        )

        if self._repository is None:
            logger.warning(
                "client-handoff: no HandoffRepository wired — reporting insert-failed "
                "(F10 safe default) for request %s",
                request.request_id,
            )
            record_handoff_creation_failed(request.message.surface.value)
            return HandoffOutcome.ROW_INSERT_FAILED

        try:
            inserted = await self._repository.insert(record)
        except Exception:
            logger.exception(
                "client-handoff: repository.insert raised for request %s", request.request_id
            )
            inserted = False

        if inserted:
            record_handoff_created(request.message.surface.value, context_carried=context_carried)
            return HandoffOutcome.ROW_INSERTED

        record_handoff_creation_failed(request.message.surface.value)
        return HandoffOutcome.ROW_INSERT_FAILED
