"""The seam between L7 and the not-yet-merged order/practice journal.

`EventEnvelope` mirrors `products/garuda-voa/contracts/events.yaml` field for
field so a future concrete `JournalReader` only has to map rows onto this
shape, never invent one.

**Corrected after cross-family refuter review (Kimi K3, 2026-08-25) against
the frozen contract — two real gaps, fixed here:**

1. The first version of this file omitted `idempotency_identity`, which
   `events.yaml` marks **required** on every `EventEnvelope`. That omission
   was load-bearing: STATE-MACHINE.md names PR-01's retry-idempotency key
   as "the paid journal event ID", and `events.yaml`'s own
   `x-idempotency-source` for `PracticeReceived` is "committed payment.paid
   journal event identity" — NOT the `practice.received` event's own
   `event_id`. Deduping on the wrong key (which the first version of
   `crm_handoff.py` did) only catches an outbox redelivery of one already-
   committed event; it does not catch a journal-level PR-01 retry (a worker
   crash after journal append, before ack) that would mint a *second*
   `practice.received` event, with a fresh `event_id`, for the same order.
   `IdempotencyIdentity` below is added so `crm_handoff.py` can dedup on the
   contract-correct key.
2. `OrderSnapshotProvider` was documented as keyed by an *order* aggregate
   id, but the only id `crm_handoff.py` ever has is the PR-01 event's own
   `aggregate_id` — which STATE-MACHINE.md says is the **practice**
   aggregate (`aggregate_type: practice`), not the order. `events.yaml`'s
   `EventEnvelope` carries no practice->order correlation field, so a
   concrete reader built to the OLD "order id in, snapshot out" contract
   would return `None` for every real event — a permanent, silent handoff
   failure with no page. The Protocol below now says explicitly what the
   caller actually has and what a real adapter must do with it: resolve the
   practice id to its order by querying the practice row (once L3/L4 exist
   and that row exists), not just look one up.

The `Protocol`s below are the ONLY things L7 code is allowed to depend on
for order/practice data. Nothing in this package imports asyncpg or a table
name directly — that keeps every module here testable with a plain fake and
safe to write before L1/L3/L4 exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

TransitionId = str  # e.g. "PR-01", "OP-02" — kept as str, not an enum, so a
# new transition admitted to events.yaml (as OP-F04/OP-F05 were, per that
# file's own comment) never requires an edit here.

AggregateType = Literal["order", "practice"]

IdempotencyKind = str  # events.yaml IdempotencyIdentity.kind enum, kept as
# str for the same open-set reason as TransitionId.


@dataclass(frozen=True, slots=True)
class IdempotencyIdentity:
    """Mirrors `events.yaml`'s `IdempotencyIdentity` exactly: SHA-256 digests
    of the scoped idempotency key and the canonical payload, never the raw
    key (events.yaml's own field descriptions)."""

    kind: IdempotencyKind
    key_digest: str  # ^[a-f0-9]{64}$ per events.yaml
    canonical_payload_digest: str  # ^[a-f0-9]{64}$ per events.yaml


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """One row of the append-only journal, exactly as events.yaml defines it."""

    schema_version: str
    event_id: str
    event_name: str
    occurred_at: datetime
    aggregate_type: AggregateType
    aggregate_id: str
    transition_id: TransitionId
    customer_visible: bool
    idempotency_identity: IdempotencyIdentity
    # Not part of the wire event (events.yaml `unevaluatedProperties: false`
    # forbids it there) — attached by the reader from the order/practice
    # record's own metadata, per SLO.md M-04 ("labeled only by environment
    # and test class"). Defaults to False so a reader that forgets to set it
    # fails safe toward "counts as production", which BI-01/BI-02 treat as
    # the stricter case (synthetic traffic must be excluded, never assumed).
    is_synthetic: bool = False


@dataclass(frozen=True, slots=True)
class UploadSample:
    """One SLO-O01 observation: an accepted document upload and, if it has
    resolved, its terminal OCR feedback."""

    upload_committed_at: datetime
    ocr_feedback_committed_at: datetime | None
    is_synthetic: bool = False


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    """Everything the CRM handoff needs to create a practice with zero
    re-typing, once L3 (order) and L5 (documents/intake) exist. Field names
    intentionally mirror `garuda_flow.eligibility`/`garuda_flow.intake` and
    `garuda_flow.pricing` so a future adapter is a straight field copy."""

    order_aggregate_id: str
    customer_email: str
    case_type: str  # garuda_flow.intake.CaseType value
    purpose: str  # garuda_flow.intake.Purpose value
    nationality: str
    entry_date: date
    price_idr: int
    submit_by_date: date | None  # garuda_flow.operating_calendar commitment
    assigned_to: str | None = None  # team member email, if pre-assigned
    # Added when the first CONCRETE `CrmWriter` was built: `clients.full_name`
    # is NOT NULL, and this snapshot carried no name at all. The alternatives
    # were both worse than one additive optional field — deriving a name from
    # the email local-part would write invented data into the CRM, and having
    # the writer re-read `garuda_orders` itself would give the CRM-side adapter
    # a second, undeclared dependency on GARUDA's own tables. Optional with a
    # default so every existing fake and caller keeps working unchanged; a
    # writer that receives None must refuse rather than substitute a placeholder.
    customer_full_name: str | None = None


@dataclass(frozen=True, slots=True)
class PracticeSnapshot:
    """Current authoritative practice state, for the SLA timer."""

    practice_aggregate_id: str
    state: str  # "Received" | "In_review" | "Blocked" | "Submitted" | ...
    state_entered_at: datetime
    filing_deadline: date | None  # the published D-7 checkpoint for this case


class JournalReader(Protocol):
    """Read-only view over the append-only order/practice journal."""

    async def events_since(
        self,
        *,
        aggregate_type: AggregateType,
        event_names: tuple[str, ...],
        since: datetime,
        until: datetime,
    ) -> list[EventEnvelope]: ...

    async def upload_samples_since(
        self, *, since: datetime, until: datetime
    ) -> list[UploadSample]: ...


class OrderSnapshotProvider(Protocol):
    """Resolves a PR-01 event's **practice** aggregate id — the only id
    `crm_handoff.py` ever has, since PR-01's `aggregate_type` is `practice`
    — to the prefill data a CRM practice needs. `events.yaml`'s
    `EventEnvelope` carries no practice->order correlation field, so a
    concrete adapter must look up the practice row (once L3/L4 exist) to
    find its originating order, then load that order's snapshot. This is
    NOT a bare order-id lookup — the parameter name says what the caller
    actually has, so a future adapter cannot be built to the wrong contract
    the way an "order_aggregate_id" name invited.
    """

    async def get(self, practice_aggregate_id: str) -> OrderSnapshot | None: ...


class CrmWriter(Protocol):
    """The one write path L7 is allowed: creating the CRM-side practice.

    **Concurrency contract a concrete adapter MUST honour, not just the
    in-memory fake the tests use**: `CrmHandoffService` calls
    `find_practice_by_source_idempotency_key` then `create_client_and_practice`
    as two separate awaits — this is check-then-act, not atomic. Two
    concurrent deliveries racing the same idempotency key (a legitimate
    outbox retry racing a redelivery, or a journal-level PR-01 retry) can
    both observe `None` before either write commits. A real Postgres
    implementation MUST enforce this at the database, e.g. a UNIQUE
    constraint on the idempotency key digest plus `INSERT ... ON CONFLICT
    (source_idempotency_key) DO NOTHING RETURNING id` (falling back to the
    SELECT on conflict), so the DB — not this two-step dance — is the
    single idempotency authority. This mirrors SM-G07: an accepted
    transition and its journal append happen in the same transaction; the
    CRM write must have the equivalent guarantee, not merely look
    idempotent under a single-threaded fake. See
    `apps/backend-rag/backend/tests/services/garuda_ops/test_crm_handoff.py`
    for a fake that reproduces the race and one that closes it.

    The idempotency key passed by `CrmHandoffService` is
    `event.idempotency_identity.key_digest` — the contract-named "committed
    payment.paid journal event identity" (`events.yaml`'s
    `x-idempotency-source` for `PracticeReceived`), never the
    `practice.received` event's own `event_id` (see this module's
    docstring, gap 1).
    """

    async def find_practice_by_source_idempotency_key(
        self, source_idempotency_key: str
    ) -> int | None: ...

    async def create_client_and_practice(
        self, snapshot: OrderSnapshot, *, source_idempotency_key: str, practice_type_code: str
    ) -> int: ...
