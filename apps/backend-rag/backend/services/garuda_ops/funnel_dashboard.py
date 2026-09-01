"""Funnel dashboard aggregation, per `product.yaml` primary/secondary metrics
and MANDATE.md §2: "paid orders/week; secondary: check->purchase conversion,
decline->WhatsApp conversion, % VOA buyers purchasing a second service
within 12 months".

This module answers "no purchases because nothing is wrong" vs "no
purchases because the funnel is dead" (the WhatsApp-bot 24-day silent
failure this lane was explicitly warned about, `MEMORY.md`
"discovery_the_whatsapp_bot_answered_nobody..."): every ratio below is
reported with its own denominator, and a zero denominator is `unknown`,
never rendered as `0%` conversion, which would look identical to "the
funnel is dead" and identical to "nobody arrived yet this week" — the same
failure mode the dead-man switch exists to catch on the input side, mirrored
here on the reporting side.

Reads verdict events (`checks_started`/`checks_declined`) and order/practice
journal events through `JournalReader` (`ports.py`); no concrete adapter
exists yet for the same reason documented in `garuda_ops/__init__.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.services.garuda_ops.ports import EventEnvelope


@dataclass(frozen=True, slots=True)
class ConversionRatio:
    numerator: int
    denominator: int
    ratio: float | None  # None when denominator == 0 — "unknown", not 0.0


def _ratio(numerator: int, denominator: int) -> ConversionRatio:
    return ConversionRatio(
        numerator=numerator,
        denominator=denominator,
        ratio=(numerator / denominator) if denominator > 0 else None,
    )


@dataclass(frozen=True, slots=True)
class FunnelSnapshot:
    window_start: datetime
    window_end: datetime
    paid_orders: int
    check_to_purchase: ConversionRatio
    decline_to_whatsapp: ConversionRatio


def build_funnel_snapshot(
    *,
    checks_started: int,
    checks_declined: int,
    declined_whatsapp_handoffs: int,
    order_events: list[EventEnvelope],
    window_start: datetime,
    window_end: datetime,
) -> FunnelSnapshot:
    """`checks_started`/`checks_declined`/`declined_whatsapp_handoffs` come
    from the L2 verdict path (not yet emitting business events at the time
    this lane was built — L2's router is unregistered, see
    `garuda_voa_public.py`'s own module docstring); callers pass 0 for both
    until that wiring lands, which correctly renders every ratio here as
    `unknown` rather than a fabricated 0%.

    Known judgment call (refuter review, 2026-08-25): `checks_started`/
    `checks_declined` are caller-supplied ints with no window attached,
    while `paid_orders` is computed strictly within
    `[window_start, window_end)`. Nothing in this function can detect if
    the caller passed a denominator from a different window than the
    numerator — that binding has to be enforced by whoever wires a
    concrete `JournalReader`/verdict-event source, not guessed here.
    """
    seen_event_ids: set[str] = set()
    seen_order_ids: set[str] = set()  # M-02's unit is the order, not the event
    paid_orders = 0
    for ev in order_events:
        if ev.event_name != "payment.paid" or ev.is_synthetic:
            continue
        if not (window_start < ev.occurred_at <= window_end):
            continue
        if ev.event_id in seen_event_ids:
            continue
        seen_event_ids.add(ev.event_id)
        if ev.aggregate_id in seen_order_ids:
            continue
        seen_order_ids.add(ev.aggregate_id)
        paid_orders += 1

    return FunnelSnapshot(
        window_start=window_start,
        window_end=window_end,
        paid_orders=paid_orders,
        check_to_purchase=_ratio(paid_orders, checks_started),
        decline_to_whatsapp=_ratio(declined_whatsapp_handoffs, checks_declined),
    )
