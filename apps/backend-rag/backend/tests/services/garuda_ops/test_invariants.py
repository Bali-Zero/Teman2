"""Bite-proof for BI-01/BI-02 (`garuda_ops.invariants`).

For each invariant: what makes it go RED (PAGE)? What makes a green verdict
suspicious (UNKNOWN, not silently HEALTHY)?
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.garuda_ops.invariants import (
    InvariantStatus,
    median_upload_to_ocr,
    paid_orders_24h,
)
from backend.services.garuda_ops.ports import EventEnvelope, IdempotencyIdentity, UploadSample

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _idempotency(seed: str) -> IdempotencyIdentity:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return IdempotencyIdentity(
        kind="PROVIDER_EVENT", key_digest=digest, canonical_payload_digest=digest
    )


def _paid_event(
    *,
    event_id: str,
    occurred_at: datetime,
    is_synthetic: bool = False,
    aggregate_id: str = "order-1",
) -> EventEnvelope:
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_name="payment.paid",
        occurred_at=occurred_at,
        aggregate_type="order",
        aggregate_id=aggregate_id,
        transition_id="OP-02",
        customer_visible=True,
        idempotency_identity=_idempotency(event_id),
        is_synthetic=is_synthetic,
    )


# ---------------------------------------------------------------------------
# BI-01
# ---------------------------------------------------------------------------


def test_bi01_pages_when_zero_qualifying_orders_in_the_last_24h() -> None:
    """RED: activation criteria met, zero paid events in window -> PAGE."""
    verdict = paid_orders_24h(
        paid_events=[],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.status is InvariantStatus.PAGE
    assert verdict.qualifying_count == 0


def test_bi01_healthy_when_one_qualifying_order_lands() -> None:
    """GREEN: restoring exactly one real paid order clears the page."""
    verdict = paid_orders_24h(
        paid_events=[_paid_event(event_id="evt-1", occurred_at=_NOW - timedelta(hours=1))],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.status is InvariantStatus.HEALTHY
    assert verdict.qualifying_count == 1


def test_bi01_before_activation_window_is_unknown_not_healthy() -> None:
    """Launch happened 1h ago, not 24h — the invariant does not apply yet,
    and must not be silently reported as passing."""
    verdict = paid_orders_24h(
        paid_events=[],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=1),
        funnel_currently_enabled=True,
    )
    assert verdict.status is InvariantStatus.UNKNOWN


def test_bi01_funnel_disabled_is_unknown() -> None:
    verdict = paid_orders_24h(
        paid_events=[_paid_event(event_id="evt-1", occurred_at=_NOW - timedelta(hours=1))],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=False,
    )
    assert verdict.status is InvariantStatus.UNKNOWN


def test_bi01_synthetic_orders_never_count_toward_the_page_clear() -> None:
    """Adversarial case: 10 synthetic paid events must NOT clear a real
    page — only real production traffic may."""
    verdict = paid_orders_24h(
        paid_events=[
            _paid_event(event_id=f"synthetic-{i}", occurred_at=_NOW - timedelta(minutes=i), is_synthetic=True)
            for i in range(10)
        ],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.status is InvariantStatus.PAGE
    assert verdict.qualifying_count == 0


def test_bi01_deduplicates_retried_webhook_deliveries() -> None:
    """M-02: the same event_id delivered twice must contribute one sample,
    not two — proving a webhook retry storm cannot inflate the count."""
    dup_event = _paid_event(event_id="evt-dup", occurred_at=_NOW - timedelta(hours=1))
    verdict = paid_orders_24h(
        paid_events=[dup_event, dup_event, dup_event],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.qualifying_count == 1


def test_bi01_two_distinct_event_ids_for_the_same_order_count_once() -> None:
    """RED-if-wrong (refuter finding 6): M-02's unit is "one logical
    order", not "one event_id" — a journal-level retry can mint a SECOND
    payment.paid event_id for the same order (the same fault class the
    crm_handoff idempotency-identity fix addresses). Before the fix this
    inflated `qualifying_count` to 2."""
    verdict = paid_orders_24h(
        paid_events=[
            _paid_event(event_id="evt-a", occurred_at=_NOW - timedelta(hours=2), aggregate_id="order-x"),
            _paid_event(event_id="evt-b", occurred_at=_NOW - timedelta(hours=1), aggregate_id="order-x"),
        ],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.qualifying_count == 1


def test_bi01_two_distinct_orders_each_count() -> None:
    """Green counterpart: two REAL distinct orders must both count — the
    order-level dedup must not collapse genuinely different orders."""
    verdict = paid_orders_24h(
        paid_events=[
            _paid_event(event_id="evt-a", occurred_at=_NOW - timedelta(hours=2), aggregate_id="order-x"),
            _paid_event(event_id="evt-b", occurred_at=_NOW - timedelta(hours=1), aggregate_id="order-y"),
        ],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.qualifying_count == 2


def test_bi01_ignores_events_outside_the_rolling_window() -> None:
    verdict = paid_orders_24h(
        paid_events=[_paid_event(event_id="evt-old", occurred_at=_NOW - timedelta(hours=25))],
        now=_NOW,
        launch_activated_at=_NOW - timedelta(hours=48),
        funnel_currently_enabled=True,
    )
    assert verdict.status is InvariantStatus.PAGE
    assert verdict.qualifying_count == 0


# ---------------------------------------------------------------------------
# BI-02
# ---------------------------------------------------------------------------


def test_bi02_unknown_with_zero_samples_never_reads_as_healthy() -> None:
    """M-06: a missing stream is UNKNOWN, not a silent pass."""
    verdict = median_upload_to_ocr(samples=[], now=_NOW)
    assert verdict.status is InvariantStatus.UNKNOWN
    assert verdict.median_seconds is None


def test_bi02_healthy_when_all_resolved_under_60s() -> None:
    samples = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=40),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=10),
        ),
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=50),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=20),
        ),
    ]
    verdict = median_upload_to_ocr(samples=samples, now=_NOW)
    assert verdict.status is InvariantStatus.HEALTHY
    assert verdict.median_seconds == 30.0


def test_bi02_pages_when_median_exceeds_60s() -> None:
    """RED: break the healthy fixture by pushing both durations past 60s."""
    samples = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=200),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=100),
        ),
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=210),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=90),
        ),
    ]
    verdict = median_upload_to_ocr(samples=samples, now=_NOW)
    assert verdict.status is InvariantStatus.PAGE
    assert verdict.median_seconds == 110.0


def test_bi02_unresolved_upload_contributes_censored_age_not_dropped() -> None:
    """M-03: an upload still stuck in the queue after 90s must count as a
    90s-or-worse sample, never be excluded as 'not yet finished'."""
    samples = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=90),
            ocr_feedback_committed_at=None,
        )
    ]
    verdict = median_upload_to_ocr(samples=samples, now=_NOW)
    assert verdict.status is InvariantStatus.PAGE
    assert verdict.median_seconds == 90.0
    assert verdict.unresolved_overdue_count == 1


def test_bi02_a_stuck_upload_cannot_be_hidden_by_many_fast_resolved_ones() -> None:
    """Adversarial: 9 fast resolved uploads + 1 permanently-stuck one. A
    naive 'only count resolved' implementation would report a healthy
    median forever; M-03 requires the stuck one to keep contributing its
    growing age."""
    fast = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=30),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=25),
        )
        for _ in range(9)
    ]
    stuck = UploadSample(
        upload_committed_at=_NOW - timedelta(seconds=500), ocr_feedback_committed_at=None
    )
    verdict = median_upload_to_ocr(samples=[*fast, stuck], now=_NOW)
    assert verdict.sample_count == 10
    # median of nine 5s durations + one 500s duration is still 5s (index 4
    # of 10 sorted) — the point is it did NOT get dropped from sample_count,
    # not that a single outlier flips a 10-sample median by itself.
    assert verdict.unresolved_overdue_count == 1


def test_bi02_synthetic_samples_are_excluded() -> None:
    samples = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=500),
            ocr_feedback_committed_at=None,
            is_synthetic=True,
        )
    ]
    verdict = median_upload_to_ocr(samples=samples, now=_NOW)
    assert verdict.status is InvariantStatus.UNKNOWN


def test_bi02_rejects_a_future_upload_timestamp() -> None:
    """RED-if-wrong (refuter finding 5): before the fix, a future
    `upload_committed_at` (cross-writer clock skew) produced a NEGATIVE
    censored age, which can only lower the median — masking the exact
    violation M-03 exists to surface. `deadman`/`sla_timer` already reject
    a future timestamp; this must too."""
    samples = [
        UploadSample(
            upload_committed_at=_NOW + timedelta(seconds=10),
            ocr_feedback_committed_at=None,
        )
    ]
    with pytest.raises(ValueError, match="future"):
        median_upload_to_ocr(samples=samples, now=_NOW)


def test_bi02_rejects_ocr_feedback_that_precedes_its_own_upload() -> None:
    """RED-if-wrong: a resolved sample whose feedback timestamp precedes its
    upload timestamp (clock skew between two authoritative commit records,
    M-01) would otherwise compute a negative duration and lower the median."""
    samples = [
        UploadSample(
            upload_committed_at=_NOW - timedelta(seconds=10),
            ocr_feedback_committed_at=_NOW - timedelta(seconds=20),
        )
    ]
    with pytest.raises(ValueError, match="precedes"):
        median_upload_to_ocr(samples=samples, now=_NOW)
