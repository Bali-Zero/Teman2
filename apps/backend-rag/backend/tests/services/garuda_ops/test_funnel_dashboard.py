"""Bite-proof for `garuda_ops.funnel_dashboard`.

Core property under test: a zero denominator must render as `unknown`
(ratio=None), never `0.0` — a `0.0` conversion rate is visually
indistinguishable from a dead funnel, which is precisely the WhatsApp-bot
24-day silent-failure shape this lane was warned about.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from backend.services.garuda_ops.funnel_dashboard import build_funnel_snapshot
from backend.services.garuda_ops.ports import EventEnvelope, IdempotencyIdentity

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
_WINDOW_START = _NOW - timedelta(days=7)


def _idempotency(seed: str) -> IdempotencyIdentity:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return IdempotencyIdentity(
        kind="PROVIDER_EVENT", key_digest=digest, canonical_payload_digest=digest
    )


def _paid_event(
    event_id: str,
    occurred_at: datetime,
    *,
    is_synthetic: bool = False,
    aggregate_id: str = "order-x",
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


def test_zero_checks_started_renders_conversion_as_unknown_not_zero() -> None:
    """RED-if-wrong: a naive `numerator/denominator` would raise or silently
    report 0.0 here — both are wrong; 'nobody visited yet' must read as
    unknown, not as 'the funnel converts nobody'."""
    snapshot = build_funnel_snapshot(
        checks_started=0,
        checks_declined=0,
        declined_whatsapp_handoffs=0,
        order_events=[],
        window_start=_WINDOW_START,
        window_end=_NOW,
    )
    assert snapshot.check_to_purchase.ratio is None
    assert snapshot.decline_to_whatsapp.ratio is None
    assert snapshot.paid_orders == 0


def test_real_traffic_computes_a_real_ratio() -> None:
    snapshot = build_funnel_snapshot(
        checks_started=10,
        checks_declined=4,
        declined_whatsapp_handoffs=2,
        order_events=[_paid_event("evt-1", _NOW - timedelta(hours=1))],
        window_start=_WINDOW_START,
        window_end=_NOW,
    )
    assert snapshot.paid_orders == 1
    assert snapshot.check_to_purchase.ratio == 0.1
    assert snapshot.decline_to_whatsapp.ratio == 0.5


def test_synthetic_paid_events_never_count_toward_paid_orders() -> None:
    snapshot = build_funnel_snapshot(
        checks_started=10,
        checks_declined=0,
        declined_whatsapp_handoffs=0,
        order_events=[_paid_event("evt-syn", _NOW - timedelta(hours=1), is_synthetic=True)],
        window_start=_WINDOW_START,
        window_end=_NOW,
    )
    assert snapshot.paid_orders == 0
    assert snapshot.check_to_purchase.ratio == 0.0  # denominator is real (10), numerator genuinely 0


def test_duplicate_paid_event_id_counts_once() -> None:
    dup = _paid_event("evt-dup", _NOW - timedelta(hours=1))
    snapshot = build_funnel_snapshot(
        checks_started=5,
        checks_declined=0,
        declined_whatsapp_handoffs=0,
        order_events=[dup, dup],
        window_start=_WINDOW_START,
        window_end=_NOW,
    )
    assert snapshot.paid_orders == 1


def test_two_distinct_event_ids_for_the_same_order_count_once() -> None:
    """Refuter finding 6 companion: M-02's unit is the order, not the event."""
    snapshot = build_funnel_snapshot(
        checks_started=5,
        checks_declined=0,
        declined_whatsapp_handoffs=0,
        order_events=[
            _paid_event("evt-a", _NOW - timedelta(hours=2), aggregate_id="order-shared"),
            _paid_event("evt-b", _NOW - timedelta(hours=1), aggregate_id="order-shared"),
        ],
        window_start=_WINDOW_START,
        window_end=_NOW,
    )
    assert snapshot.paid_orders == 1
