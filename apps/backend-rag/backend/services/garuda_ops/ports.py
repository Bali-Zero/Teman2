"""The seam between L7 and the not-yet-merged order/practice journal.

`EventEnvelope` mirrors `products/garuda-voa/contracts/events.yaml` field for
field (schema_version/event_id/event_name/occurred_at/aggregate_type/
aggregate_id/transition_id/customer_visible) so a future concrete
`JournalReader` only has to map rows onto this shape, never invent one.

The two `Protocol`s below (`JournalReader`, `OrderSnapshotProvider`) are the
ONLY things L7 code is allowed to depend on for order/practice data. Nothing
in this package imports asyncpg or a table name directly — that keeps every
module here testable with a plain fake and safe to write before L1/L3/L4
exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

TransitionId = str  # e.g. "PR-01", "OP-02" — kept as str, not an enum, so a
# new transition admitted to events.yaml (as OP-F04/OP-F05 were, per that
# file's own comment) never requires an edit here.

AggregateType = Literal["order", "practice"]


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
    """Resolves an order aggregate id to the prefill data a practice needs."""

    async def get(self, order_aggregate_id: str) -> OrderSnapshot | None: ...


class CrmWriter(Protocol):
    """The one write path L7 is allowed: creating the CRM-side practice.

    Every method must be idempotent on ``source_event_id`` — see
    `crm_handoff.CrmHandoffService`, which is the only caller.
    """

    async def find_practice_by_source_event(self, source_event_id: str) -> int | None: ...

    async def create_client_and_practice(
        self, snapshot: OrderSnapshot, *, source_event_id: str, practice_type_code: str
    ) -> int: ...
