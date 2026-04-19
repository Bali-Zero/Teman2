"""Visa Clock branch: compute 5-checkpoint timeline.

Input: visa_type + entry_date.
Output: expiry_date + list of 5 checkpoints (D-60, D-30, D-14, D-7, D-1)
        with ISO dates and what the user should do on each.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from backend.services.visa_check.catalogue import (
    DEFAULT_DURATION_DAYS,
    EXTENSION_POLICY,
    VisaType,
)


@dataclass(frozen=True)
class Checkpoint:
    label: str            # "D-60"
    at: date              # absolute calendar date
    title: str            # "Start paperwork"
    body: str             # short human description


@dataclass(frozen=True)
class ClockTimeline:
    visa_type: VisaType
    entry_date: date
    expiry_date: date
    extensions_possible: int
    extension_days: int
    checkpoints: list[Checkpoint]


_CHECKPOINT_TEMPLATE: list[tuple[str, int, str, str]] = [
    # (label, days_before_expiry, title, body)
    (
        "D-60",
        60,
        "Start paperwork",
        "Begin collecting renewal / extension documents. Confirm your visa type and sponsor.",
    ),
    (
        "D-30",
        30,
        "Documents ready",
        "All docs translated and notarised where required. Book imigrasi appointment.",
    ),
    (
        "D-14",
        14,
        "Kantor Imigrasi visit",
        "Biometrics + passport hand-in. Plan to be unavailable to travel abroad.",
    ),
    (
        "D-7",
        7,
        "Pickup window",
        "Most offices release the new visa 5-10 days after intake. Keep the receipt handy.",
    ),
    (
        "D-1",
        1,
        "Final check",
        "Verify the stamp/KITAS in hand. If you have not picked up yet, go today.",
    ),
]


def clock_timeline(*, visa_type: VisaType, entry_date: date) -> ClockTimeline:
    duration_days = DEFAULT_DURATION_DAYS.get(visa_type, 60)
    ext_count, ext_days = EXTENSION_POLICY.get(visa_type, (0, 0))

    expiry = entry_date + timedelta(days=duration_days)

    checkpoints = [
        Checkpoint(label=label, at=expiry - timedelta(days=offset), title=title, body=body)
        for label, offset, title, body in _CHECKPOINT_TEMPLATE
    ]

    return ClockTimeline(
        visa_type=visa_type,
        entry_date=entry_date,
        expiry_date=expiry,
        extensions_possible=ext_count,
        extension_days=ext_days,
        checkpoints=checkpoints,
    )
