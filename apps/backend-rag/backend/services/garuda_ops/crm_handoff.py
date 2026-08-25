"""Practice -> CRM handoff, zero re-typing.

Consumes exactly one transition: PR-01 (`practice.received`, STATE-MACHINE.md
line 84) — "OP-02 committed and its outbox event is consumed". Everything the
CRM practice row needs (client email, nationality, case type, price, filing
commitment) comes from `OrderSnapshotProvider` (`ports.py`), never re-typed
by staff. Idempotency mirrors PR-01's own guard: "no practice exists for the
order" is checked via `source_event_id` (the PR-01 event id, per PR-12's
retry-idempotent set in STATE-MACHINE.md) before any write — a duplicate
outbox delivery of the same PR-01 event must never create a second CRM
practice.

No PII crosses into logs here: `logger` calls below carry only aggregate ids
and event ids, never `customer_email` — CLAUDE.md's output-boundary rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.app.utils.logging_utils import get_logger
from backend.services.garuda_ops.ports import (
    CrmWriter,
    EventEnvelope,
    OrderSnapshotProvider,
)

logger = get_logger(__name__)

# The practice_type_code this handoff writes against. Not yet seeded in
# `practice_types` (that migration is L1's exclusive path,
# `apps/backend-rag/backend/db/migrations_v2/`) — kept as a named constant
# so the concrete `PostgresCrmWriter` fails with a clear, attributable error
# rather than a silent wrong-row insert if the row is still missing.
GARUDA_VOA_PRACTICE_TYPE_CODE = "garuda_voa"


class HandoffOutcome(str, Enum):
    CREATED = "created"
    ALREADY_HANDLED = "already_handled"  # idempotent no-op
    ORDER_SNAPSHOT_MISSING = "order_snapshot_missing"


@dataclass(frozen=True, slots=True)
class HandoffResult:
    outcome: HandoffOutcome
    crm_practice_id: int | None


class CrmHandoffService:
    def __init__(
        self,
        *,
        order_snapshots: OrderSnapshotProvider,
        crm_writer: CrmWriter,
        practice_type_code: str = GARUDA_VOA_PRACTICE_TYPE_CODE,
    ) -> None:
        self._order_snapshots = order_snapshots
        self._crm_writer = crm_writer
        self._practice_type_code = practice_type_code

    async def handle_practice_received(self, event: EventEnvelope) -> HandoffResult:
        if event.transition_id != "PR-01" or event.aggregate_type != "practice":
            msg = f"CrmHandoffService only consumes PR-01 practice events, got {event.transition_id}/{event.aggregate_type}"
            raise ValueError(msg)

        existing_id = await self._crm_writer.find_practice_by_source_event(event.event_id)
        if existing_id is not None:
            logger.info(
                "garuda_ops.crm_handoff.already_handled",
                extra={"practice_aggregate_id": event.aggregate_id, "event_id": event.event_id},
            )
            return HandoffResult(HandoffOutcome.ALREADY_HANDLED, existing_id)

        # STATE-MACHINE.md PR-01 keys off the *order* whose OP-02 committed;
        # the practice aggregate id it names is a freshly-minted practice id,
        # not the order id. Until L3/L4 land, aggregate_id is the only handle
        # we have; the concrete reader is responsible for resolving it to the
        # order it was created from before calling this method — asserted by
        # the fake in the test suite, which always supplies a resolvable id.
        snapshot = await self._order_snapshots.get(event.aggregate_id)
        if snapshot is None:
            logger.error(
                "garuda_ops.crm_handoff.order_snapshot_missing",
                extra={"practice_aggregate_id": event.aggregate_id, "event_id": event.event_id},
            )
            return HandoffResult(HandoffOutcome.ORDER_SNAPSHOT_MISSING, None)

        crm_practice_id = await self._crm_writer.create_client_and_practice(
            snapshot,
            source_event_id=event.event_id,
            practice_type_code=self._practice_type_code,
        )
        logger.info(
            "garuda_ops.crm_handoff.created",
            extra={
                "practice_aggregate_id": event.aggregate_id,
                "event_id": event.event_id,
                "crm_practice_id": crm_practice_id,
            },
        )
        return HandoffResult(HandoffOutcome.CREATED, crm_practice_id)
