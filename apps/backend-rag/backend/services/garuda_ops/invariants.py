"""BI-01 and BI-02, per `products/garuda-voa/journeys/SLO.md`.

Pure functions over already-fetched samples — no I/O — so each can be
bite-proven directly: feed it a fabricated event/sample list, assert the
verdict, mutate one field, assert the verdict flips. The measurement
contract (M-01..M-06 in SLO.md) is encoded here, not left to callers:

- M-02: dedup by event_id, THEN by order aggregate_id (BI-01) before
  counting — M-02's unit is explicitly "one logical ... order ...
  contributes at most one sample"; event_id dedup alone only guards a
  retry/redelivery of the SAME journal event, not two distinct
  `payment.paid` event ids minted for the same order (a journal-level
  retry — the same fault class `crm_handoff.py`'s idempotency-identity fix
  addresses). Fixed after cross-family refuter review (Kimi K3, 2026-08-25,
  finding 6).
- M-03/M-06: an empty population is `UNKNOWN`, never `HEALTHY` — a stream
  that silently stopped reporting must not read as "zero incidents".
- M-03 (BI-02): an unresolved upload contributes its current age as a
  censored duration, so a queue that never finishes cannot make the median
  look artificially fast by simply not being counted. Durations and ages
  must be non-negative — M-01 allows timestamps from different
  authoritative commit records, so cross-writer clock skew (or a future
  `upload_committed_at`) could otherwise produce a negative sample that
  LOWERS the median, hiding exactly the violation M-03 exists to surface.
  `deadman.py`/`sla_timer.py` already reject a future timestamp; this
  module now does too (refuter finding 5).
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

    Known judgment call (refuter review, 2026-08-25): SLO.md says
    "provided the public funnel has *remained* enabled", a continuous
    condition; `funnel_currently_enabled` only reads the instant-of-
    evaluation flag. A funnel toggled off then back on within the 24h
    activation window can false-PAGE once re-enabled. The caller could
    track continuous-enabled-since instead, but that state doesn't exist
    anywhere yet either — left as the caller's problem, not silently
    "fixed" by pretending the instantaneous flag means something it doesn't.
    """
    window_start, window_end = now - _BI01_WINDOW, now

    if launch_activated_at is None or not funnel_currently_enabled:
        return Bi01Verdict(InvariantStatus.UNKNOWN, 0, window_start, window_end)
    if now - launch_activated_at < _BI01_WINDOW:
        return Bi01Verdict(InvariantStatus.UNKNOWN, 0, window_start, window_end)

    seen_event_ids: set[str] = set()
    seen_order_ids: set[str] = set()  # M-02's actual unit: one sample per order
    qualifying = 0
    for ev in paid_events:
        if ev.event_name != "payment.paid" or ev.aggregate_type != "order":
            continue
        if ev.is_synthetic:
            continue
        if not (window_start < ev.occurred_at <= window_end):
            continue
        if ev.event_id in seen_event_ids:  # retry/redelivery of one event
            continue
        seen_event_ids.add(ev.event_id)
        if ev.aggregate_id in seen_order_ids:  # a second event id, same order
            continue
        seen_order_ids.add(ev.aggregate_id)
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
        if s.upload_committed_at > now:
            msg = "upload_committed_at is in the future"
            raise ValueError(msg)
        if s.ocr_feedback_committed_at is not None:
            if s.ocr_feedback_committed_at < s.upload_committed_at:
                # A negative duration can only LOWER the median — the exact
                # fail-open direction M-03's censoring rule exists to
                # prevent. Cross-writer clock skew is real (M-01), so this
                # must be rejected, not silently absorbed.
                msg = "ocr_feedback_committed_at precedes upload_committed_at"
                raise ValueError(msg)
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
