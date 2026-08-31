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
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_ops.ports import (
    CrmWriter,
    EventEnvelope,
    OrderSnapshotProvider,
)

logger = get_logger(__name__)

# RULED by Zero, 2026-08-26: a paid GARUDA order enters the CRM as one of the
# two B1-VOA services the catalogue ALREADY holds — never a new `garuda_voa`
# type. Both rows are seeded by
# `db/migrations_v2/221_practice_types_b1_voa.sql`, so no migration and no new
# catalogue entry belong to this lane.
#
# This replaces a single hardcoded `GARUDA_VOA_PRACTICE_TYPE_CODE =
# "garuda_voa"`, whose own comment conceded the row was "not yet seeded in
# `practice_types`". That constant was not merely unseeded, it was WRONG:
# issuance and extension are different products at different prices
# (Rp 790,000 vs Rp 850,000 -- 221 seeded issuance at 750,000 and migration
# 302 corrected it to the owner's 2026-08-31 ruling), and one shared code would have
# priced, reported and routed them as one service.
#
# Derived per ORDER, never per SERVICE INSTANCE: there is deliberately no
# constructor override any more. An override is exactly how one code silently
# reclaims both case types again — the bug this constant already was.
PRACTICE_TYPE_CODE_BY_CASE_TYPE: dict[str, str] = {
    CaseType.ISSUANCE.value: "visa_b1_voa",
    CaseType.EXTENSION.value: "ext_b1_voa",
}


class UnmappedCaseType(ValueError):
    """`OrderSnapshot.case_type` names a case with no CRM service behind it.

    Raised, not returned as a `HandoffOutcome`, and the distinction is
    load-bearing. A `HandoffOutcome` is a resolved state the consumer marks
    dispatched; this is a code/data defect that no retry can fix and that
    must stay VISIBLE — a paid order with no CRM practice is a customer who
    paid and whom nobody is working for. Raising lets the outbox record the
    failed attempt and surface the job instead of retiring it green.
    """


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
    ) -> None:
        self._order_snapshots = order_snapshots
        self._crm_writer = crm_writer

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

        practice_type_code = PRACTICE_TYPE_CODE_BY_CASE_TYPE.get(snapshot.case_type)
        if practice_type_code is None:
            # Neither the case_type value nor any order identifier goes into
            # this message: SM-G03 bans order/account identifiers as log
            # fields, and this string reaches a log through the raise.
            msg = (
                "GARUDA order snapshot carries a case_type with no CRM practice "
                "type mapped to it; see PRACTICE_TYPE_CODE_BY_CASE_TYPE"
            )
            raise UnmappedCaseType(msg)

        crm_practice_id = await self._crm_writer.create_client_and_practice(
            snapshot,
            source_idempotency_key=idempotency_key,
            practice_type_code=practice_type_code,
        )
        logger.info(
            "garuda_ops.crm_handoff.created",
            extra={"idempotency_key_digest": idempotency_key},
        )
        return HandoffResult(HandoffOutcome.CREATED, crm_practice_id)
