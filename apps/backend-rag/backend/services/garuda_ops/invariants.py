"""BI-01 and BI-02, per `products/garuda-voa/journeys/SLO.md`.

Pure functions over already-fetched samples — no I/O — so each can be
bite-proven directly: feed it a fabricated event/sample list, assert the
verdict, mutate one field, assert the verdict flips. The measurement
contract (M-01..M-06 in SLO.md) is encoded here, not left to callers:

- M-02: dedup by event_id (BI-01) before counting.
- M-03/M-06: an empty population is `UNKNOWN`, never `HEALTHY` — a stream
  that silently stopped reporting must not read as "zero incidents".
- M-03 (BI-02): an unresolved upload contributes its current age as a
  censored duration, so a queue that never finishes cannot make the median
  look artificially fast by simply not being counted.
- M-04: synthetic samples never enter a business/product-conversion count.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from backend.services.garuda_ops.ports import EventEnvelope, UploadSample

_BI01_WINDOW = timedelta(hours=24)
_BI02_OBJECTIVE_SECONDS = 60.0


class InvariantStatus(str, Enum):
    HEALTHY = "healthy"
    PAGE = "page"
    UNKNOWN = "unknown"  # M-06: a missing/unprovable stream, never HEALTHY


@dataclass(frozen=True, slots=True)
class Bi01Verdict:
    status: InvariantStatus
    qualifying_count: int
    window_start: datetime
    window_end: datetime


def paid_orders_24h(
    *,
    paid_events: list[EventEnvelope],
    now: datetime,
    launch_activated_at: datetime | None,
    funnel_currently_enabled: bool,
) -> Bi01Verdict:
    """BI-01: paid orders in the rolling 24h must be > 0, once activated.

    Activation per SLO.md: begin evaluation 24h after `launch_activated_at`,
    provided the funnel has stayed enabled. Before that, or while disabled,
    the invariant does not apply — reported UNKNOWN rather than PAGE so an
    absent alert cannot be misread as "0 orders is fine forever".
    """
    window_start, window_end = now - _BI01_WINDOW, now

    if launch_activated_at is None or not funnel_currently_enabled:
        return Bi01Verdict(InvariantStatus.UNKNOWN, 0, window_start, window_end)
    if now - launch_activated_at < _BI01_WINDOW:
        return Bi01Verdict(InvariantStatus.UNKNOWN, 0, window_start, window_end)

    seen_event_ids: set[str] = set()
    qualifying = 0
    for ev in paid_events:
        if ev.event_name != "payment.paid" or ev.aggregate_type != "order":
            continue
        if ev.is_synthetic:
            continue
        if not (window_start < ev.occurred_at <= window_end):
            continue
        if ev.event_id in seen_event_ids:  # M-02: retries/dupes contribute once
            continue
        seen_event_ids.add(ev.event_id)
        qualifying += 1

    status = InvariantStatus.HEALTHY if qualifying > 0 else InvariantStatus.PAGE
    return Bi01Verdict(status, qualifying, window_start, window_end)


@dataclass(frozen=True, slots=True)
class Bi02Verdict:
    status: InvariantStatus
    median_seconds: float | None
    sample_count: int
    unresolved_overdue_count: int


def median_upload_to_ocr(
    *, samples: list[UploadSample], now: datetime
) -> Bi02Verdict:
    """BI-02: median upload->OCR feedback must stay under 60s."""
    production = [s for s in samples if not s.is_synthetic]
    if not production:
        return Bi02Verdict(InvariantStatus.UNKNOWN, None, 0, 0)

    durations: list[float] = []
    unresolved_overdue = 0
    for s in production:
        if s.ocr_feedback_committed_at is not None:
            durations.append(
                (s.ocr_feedback_committed_at - s.upload_committed_at).total_seconds()
            )
            continue
        # M-03: unresolved stays in the population as a censored duration —
        # its current age — rather than being dropped.
        age = (now - s.upload_committed_at).total_seconds()
        durations.append(age)
        if age >= _BI02_OBJECTIVE_SECONDS:
            unresolved_overdue += 1

    median_seconds = statistics.median(durations)
    status = (
        InvariantStatus.HEALTHY
        if median_seconds < _BI02_OBJECTIVE_SECONDS
        else InvariantStatus.PAGE
    )
    return Bi02Verdict(status, median_seconds, len(durations), unresolved_overdue)
