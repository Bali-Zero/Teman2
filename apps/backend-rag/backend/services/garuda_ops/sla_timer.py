"""SLA timer over a practice's current state.

Two independent clocks, both pure functions over a `PracticeSnapshot`
(`ports.py`) — no I/O, bite-provable directly:

1. `time_in_state`: how long the practice has sat in its current state.
   Staff-facing — a practice sitting in `Blocked` or `In_review` for an
   unreasonable time is a work-item SLA breach independent of the filing
   deadline.
2. `time_to_filing_deadline`: days remaining to the customer-facing D-7
   checkpoint (`garuda_flow.constants.PUBLISHED_FILING_DEADLINE_DAYS`),
   which pages when a practice is not `Submitted`/`Approved`/`Delivered`
   and the deadline is imminent or passed — the one clock that must never
   leak an internal checkpoint name to the customer (STATE-MACHINE.md G06),
   which is why this module returns only a day-count and a boolean, never a
   named internal date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from backend.services.garuda_ops.ports import PracticeSnapshot

# Work-item SLA thresholds. Deliberately conservative and staff-facing only
# (never surfaced to the customer per G06/PR-F04) — a practice that sits in
# a working state this long needs a human to look, not a customer email.
_STATE_SLA = {
    "Received": timedelta(hours=4),
    "In_review": timedelta(hours=24),
    "Blocked": timedelta(hours=48),
    "Submitted": timedelta(days=5),  # D-7 filing deadline backstops this
}


class SlaState(str, Enum):
    OK = "ok"
    WARNING = "warning"
    OVERDUE = "overdue"


@dataclass(frozen=True, slots=True)
class WorkItemSlaVerdict:
    state: SlaState
    time_in_state: timedelta
    threshold: timedelta | None  # None for terminal/unmonitored states


def time_in_state(practice: PracticeSnapshot, *, now: datetime) -> WorkItemSlaVerdict:
    if practice.state_entered_at > now:
        msg = "state_entered_at is in the future"
        raise ValueError(msg)
    elapsed = now - practice.state_entered_at
    threshold = _STATE_SLA.get(practice.state)
    if threshold is None:
        return WorkItemSlaVerdict(SlaState.OK, elapsed, None)
    if elapsed >= threshold:
        return WorkItemSlaVerdict(SlaState.OVERDUE, elapsed, threshold)
    if elapsed >= threshold * 0.75:
        return WorkItemSlaVerdict(SlaState.WARNING, elapsed, threshold)
    return WorkItemSlaVerdict(SlaState.OK, elapsed, threshold)


# Practice states that no longer race the filing deadline.
_DEADLINE_CLEARED_STATES = frozenset({"Submitted", "Approved", "Delivered", "Rejected"})


@dataclass(frozen=True, slots=True)
class FilingDeadlineVerdict:
    days_remaining: int | None  # None if no deadline applies to this case/state
    should_page: bool


def time_to_filing_deadline(
    practice: PracticeSnapshot, *, today: date
) -> FilingDeadlineVerdict:
    if practice.filing_deadline is None or practice.state in _DEADLINE_CLEARED_STATES:
        return FilingDeadlineVerdict(days_remaining=None, should_page=False)
    days_remaining = (practice.filing_deadline - today).days
    # Page while there is still time to act (<=2 days) or once it has
    # already passed (negative) — a practice must never sail past D-7 while
    # sitting in Received/In_review/Blocked with nobody paged.
    should_page = days_remaining <= 2
    return FilingDeadlineVerdict(days_remaining=days_remaining, should_page=should_page)
