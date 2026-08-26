"""Practice -> CRM handoff, zero re-typing.

Consumes exactly one transition: PR-01 (`practice.received`, STATE-MACHINE.md
line 84) — "OP-02 committed and its outbox event is consumed". Everything the
CRM practice row needs (client email, nationality, case type, price, filing
commitment) comes from `OrderSnapshotProvider` (`ports.py`), never re-typed
by staff.

**Corrected after cross-family refuter review (Kimi K3, 2026-08-25):**
idempotency dedups on `event.idempotency_identity.key_digest` — the
contract-named "committed payment.paid journal event identity"
(`events.yaml`'s `x-idempotency-source` for `PracticeReceived`) — never the
`practice.received` event's own `event_id`, which only catches an outbox
redelivery of one committed event and not a journal-level PR-01 retry that
mints a fresh `event_id` for the same order. See `ports.py`'s module
docstring for the full gap this closes.

No PII crosses into logs here, and — per SLO.md M-05 and STATE-MACHINE.md
SM-G03, which ban "order identifier"/"account identifier" as a log field
regardless of PII status — no order/practice/account identifier either:
`logger` calls below carry only the idempotency key digest (an opaque
SHA-256, not an identifier the contract names) and the outcome. A previous
version of this module logged `practice_aggregate_id` and
`crm_practice_id`; both are removed.
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

        idempotency_key = event.idempotency_identity.key_digest

        existing_id = await self._crm_writer.find_practice_by_source_idempotency_key(
            idempotency_key
        )
        if existing_id is not None:
            logger.info(
                "garuda_ops.crm_handoff.already_handled",
                extra={"idempotency_key_digest": idempotency_key},
            )
            return HandoffResult(HandoffOutcome.ALREADY_HANDLED, existing_id)

        # `event.aggregate_id` is the freshly-minted PRACTICE id (STATE-
        # MACHINE.md: PR-01's aggregate_type is `practice`) — NOT an order
        # id. `OrderSnapshotProvider.get` is documented to accept exactly
        # this and resolve practice->order internally (ports.py docstring,
        # gap 2); passing it straight through here is correct, not a stopgap.
        snapshot = await self._order_snapshots.get(event.aggregate_id)
        if snapshot is None:
            logger.error(
                "garuda_ops.crm_handoff.order_snapshot_missing",
                extra={"idempotency_key_digest": idempotency_key},
            )
            return HandoffResult(HandoffOutcome.ORDER_SNAPSHOT_MISSING, None)

        crm_practice_id = await self._crm_writer.create_client_and_practice(
            snapshot,
            source_idempotency_key=idempotency_key,
            practice_type_code=self._practice_type_code,
        )
        logger.info(
            "garuda_ops.crm_handoff.created",
            extra={"idempotency_key_digest": idempotency_key},
        )
        return HandoffResult(HandoffOutcome.CREATED, crm_practice_id)
