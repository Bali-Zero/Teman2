"""GARUDA VOA pilot — Safe Clock date engine (pure, no I/O).

Turns "a human reads the SOP and computes D-14 / D-7 / D-10 by hand" (exactly
what the Gate-1 role-play tested manually) into deterministic product logic.

Reuses ``visa_check.catalogue`` for the VOA facts (VisaType.B1: 30 days,
1×30 extension = 60 max) — no hardcoded durations. Anchors the Safe Clock
checkpoints to the CURRENT status expiry.

The printed expiry on the document is authoritative (SOP §2: "verify on
document, never compute-only"). ``compute_stay`` therefore accepts an optional
``printed_expiry`` override and flags whether the returned expiry is an
estimate — a caller acting on an estimated expiry for a real client is a bug
this type makes visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from backend.services.garuda_flow.constants import (
    EXTENSION_WINDOW_OPENS_DAYS,
    FINAL_CHECK_DAYS,
    INTERNAL_ESCALATION_DAYS,
    PILOT_INTAKE_THRESHOLD_DAYS,
    PUBLISHED_FILING_DEADLINE_DAYS,
)
from backend.services.visa_check.catalogue import VISA_META, VisaType


@dataclass(frozen=True)
class SafeCheckpoint:
    """One Safe-Clock checkpoint anchored to an absolute calendar date."""

    label: str  # "D-14"
    at: date  # absolute date = expiry - offset
    kind: str  # "window_opens" | "published_deadline" | "internal"
    client_facing: bool  # only the published deadline may be quoted to a client
    note: str


@dataclass(frozen=True)
class StayWindow:
    """The computed stay window + Safe Clock for one VOA/extension case."""

    visa_type: VisaType
    entry_date: date
    expiry_date: date  # printed expiry = last legal day in Indonesia
    last_legal_day: date  # == expiry_date; overstay begins the day AFTER
    expiry_is_estimated: bool  # True unless a printed_expiry was supplied
    max_total_days: int  # 60 for B1 (30 + 1×30)
    extension_window_opens: date  # D-14
    published_filing_deadline: date  # D-7 (client-facing)
    checkpoints: list[SafeCheckpoint]


def compute_stay(
    *,
    entry_date: date,
    visa_type: VisaType = VisaType.B1,
    printed_expiry: date | None = None,
) -> StayWindow:
    """Compute the stay window and Safe Clock for a VOA/extension case.

    If ``printed_expiry`` is given it is authoritative (SOP §2); otherwise the
    expiry is ESTIMATED as ``entry_date + duration_days`` and flagged via
    ``expiry_is_estimated=True``.

    ⚠️ The estimate is NOMINAL and may be up to one day OPTIMISTIC: it does not
    resolve whether Indonesian immigration counts the arrival day as day 1
    (which would make the last legal day ``entry + duration_days - 1``). The
    primary source deliberately gives no formula — the last legal day is read
    off the printed document (VOA/B1 CHATKB Q6). Because the error direction is
    unsafe (it could imply one extra legal day → overstay risk), an estimated
    expiry MUST NOT gate a real client's last legal day: pass ``printed_expiry``
    for any real case. This estimate is for planning/display only.
    """
    meta = VISA_META[visa_type]
    ext_count, ext_days = meta.extensions

    if printed_expiry is not None:
        expiry = printed_expiry
        estimated = False
    else:
        expiry = entry_date + timedelta(days=meta.duration_days)
        estimated = True

    max_total_days = meta.duration_days + ext_count * ext_days

    window_opens = expiry - timedelta(days=EXTENSION_WINDOW_OPENS_DAYS)
    published_deadline = expiry - timedelta(days=PUBLISHED_FILING_DEADLINE_DAYS)

    checkpoints = [
        SafeCheckpoint(
            label=f"D-{EXTENSION_WINDOW_OPENS_DAYS}",
            at=window_opens,
            kind="window_opens",
            client_facing=False,
            note="Extension window opens — earliest an extension can be filed.",
        ),
        SafeCheckpoint(
            label=f"D-{PILOT_INTAKE_THRESHOLD_DAYS}",
            at=expiry - timedelta(days=PILOT_INTAKE_THRESHOLD_DAYS),
            kind="internal",
            client_facing=False,
            note="Pilot intake threshold + internal escalation (SOP §1/§6). "
            "Below this the pilot declines. Never quote to a client.",
        ),
        SafeCheckpoint(
            label=f"D-{PUBLISHED_FILING_DEADLINE_DAYS}",
            at=published_deadline,
            kind="published_deadline",
            client_facing=True,
            note="Published filing deadline (Ngurah Rai — verify per office).",
        ),
        SafeCheckpoint(
            label=f"D-{INTERNAL_ESCALATION_DAYS}",
            at=expiry - timedelta(days=INTERNAL_ESCALATION_DAYS),
            kind="internal",
            client_facing=False,
            note="Internal: not approved yet → escalate to Zero (SOP §6).",
        ),
        SafeCheckpoint(
            label=f"D-{FINAL_CHECK_DAYS}",
            at=expiry - timedelta(days=FINAL_CHECK_DAYS),
            kind="internal",
            client_facing=False,
            note="Internal: emergency protocol — advise legal exit options (SOP §6).",
        ),
    ]

    return StayWindow(
        visa_type=visa_type,
        entry_date=entry_date,
        expiry_date=expiry,
        last_legal_day=expiry,
        expiry_is_estimated=estimated,
        max_total_days=max_total_days,
        extension_window_opens=window_opens,
        published_filing_deadline=published_deadline,
        checkpoints=checkpoints,
    )


def days_until_expiry(*, expiry_date: date, today: date) -> int:
    """Whole days from ``today`` to the printed expiry.

    ``today == expiry_date`` → 0 (the expiry date is still the last legal day).
    A negative result means the client is already overstaying.
    """
    return (expiry_date - today).days


def is_overstay(*, expiry_date: date, today: date) -> bool:
    """True if ``today`` is past the printed expiry.

    Overstay begins the day AFTER the printed expiry (VOA/B1 CHATKB Q6, verified
    2026-07-18), so departure ON the expiry date itself is NOT overstay.
    """
    return today > expiry_date


__all__ = [
    "SafeCheckpoint",
    "StayWindow",
    "compute_stay",
    "days_until_expiry",
    "is_overstay",
]
