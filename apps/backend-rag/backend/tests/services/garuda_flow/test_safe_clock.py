"""Tests for the GARUDA VOA Safe Clock date engine.

Fixtures use synthetic dates only — no client PII (SOP §0 guardrail).
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.services.garuda_flow.safe_clock import (
    compute_stay,
    days_until_expiry,
    filing_window_opens_for,
    is_overstay,
)
from backend.services.visa_check.catalogue import VisaType


class TestComputeStay:
    def test_b1_estimated_expiry_is_entry_plus_30(self) -> None:
        w = compute_stay(entry_date=date(2026, 7, 13))
        assert w.visa_type is VisaType.B1
        assert w.expiry_date == date(2026, 8, 12)  # 13 Jul + 30 days
        assert w.expiry_is_estimated is True
        assert w.max_total_days == 60  # 30 + 1×30

    def test_last_legal_day_equals_expiry(self) -> None:
        # Overstay begins the day AFTER expiry — last legal day IS the expiry.
        w = compute_stay(entry_date=date(2026, 7, 13))
        assert w.last_legal_day == w.expiry_date

    def test_printed_expiry_is_authoritative_and_not_estimated(self) -> None:
        # SOP §2: the printed document wins over the computed estimate.
        w = compute_stay(
            entry_date=date(2026, 7, 13),
            printed_expiry=date(2026, 8, 11),  # e.g. immigration printed 11th, not 12th
        )
        assert w.expiry_date == date(2026, 8, 11)
        assert w.expiry_is_estimated is False

    def test_estimate_is_nominal_and_flagged_not_authoritative(self) -> None:
        # The estimate may be up to +1 day optimistic (arrival-day counting is
        # unresolved); it must always be flagged so a caller never mistakes it
        # for the printed last-legal-day. Grader finding 2026-07-25 (Kimi K3).
        est = compute_stay(entry_date=date(2026, 7, 13))
        assert est.expiry_is_estimated is True
        printed = compute_stay(
            entry_date=date(2026, 7, 13), printed_expiry=date(2026, 8, 11)
        )
        # A printed date one day earlier than the nominal estimate is exactly
        # the unsafe case the flag exists to surface — and it overrides cleanly.
        assert printed.expiry_date < est.expiry_date
        assert printed.expiry_is_estimated is False

    def test_safe_clock_anchored_to_expiry(self) -> None:
        w = compute_stay(entry_date=date(2026, 7, 13))  # expiry 12 Aug
        assert w.extension_window_opens == date(2026, 7, 29)  # D-14
        assert w.published_filing_deadline == date(2026, 8, 5)  # D-7

    def test_only_the_published_deadline_is_client_facing(self) -> None:
        w = compute_stay(entry_date=date(2026, 7, 13))
        client_facing = [c for c in w.checkpoints if c.client_facing]
        assert len(client_facing) == 1
        assert client_facing[0].label == "D-7"
        assert client_facing[0].kind == "published_deadline"

    def test_d10_checkpoint_is_internal_never_client_facing(self) -> None:
        # The D-10 pilot threshold must never be quoted to a client (SOP §1).
        w = compute_stay(entry_date=date(2026, 7, 13))
        d10 = next(c for c in w.checkpoints if c.label == "D-10")
        assert d10.client_facing is False
        assert d10.kind == "internal"

    def test_checkpoints_cover_the_five_safe_clock_marks(self) -> None:
        w = compute_stay(entry_date=date(2026, 7, 13))
        labels = {c.label for c in w.checkpoints}
        assert labels == {"D-14", "D-10", "D-7", "D-3", "D-1"}


class TestFilingWindowOpensFor:
    """D-14 as a standalone, client-facing accessor (defect-fix pin: the
    frontend result page consumes this field directly and must never
    recompute the 14-day offset itself)."""

    def test_pins_the_14_day_offset(self) -> None:
        assert filing_window_opens_for(date(2026, 8, 12)) == date(2026, 7, 29)

    def test_matches_compute_stay_own_derivation(self) -> None:
        # Single source of truth: the standalone accessor and compute_stay()'s
        # internal StayWindow.extension_window_opens must never diverge.
        w = compute_stay(entry_date=date(2026, 7, 13))
        assert filing_window_opens_for(w.expiry_date) == w.extension_window_opens

    def test_derives_from_printed_expiry_not_estimated_one(self) -> None:
        printed = compute_stay(
            entry_date=date(2026, 7, 13), printed_expiry=date(2026, 8, 11)
        )
        assert filing_window_opens_for(printed.expiry_date) == date(2026, 7, 28)


class TestDaysUntilExpiry:
    def test_today_is_expiry_returns_zero(self) -> None:
        assert days_until_expiry(expiry_date=date(2026, 8, 12), today=date(2026, 8, 12)) == 0

    def test_ten_days_before(self) -> None:
        assert days_until_expiry(expiry_date=date(2026, 8, 12), today=date(2026, 8, 2)) == 10

    def test_already_overstaying_is_negative(self) -> None:
        assert days_until_expiry(expiry_date=date(2026, 8, 12), today=date(2026, 8, 15)) == -3


class TestIsOverstay:
    def test_on_expiry_date_is_not_overstay(self) -> None:
        # Departure ON the expiry date is legal; overstay begins the day after.
        assert is_overstay(expiry_date=date(2026, 8, 12), today=date(2026, 8, 12)) is False

    def test_day_after_expiry_is_overstay(self) -> None:
        assert is_overstay(expiry_date=date(2026, 8, 12), today=date(2026, 8, 13)) is True

    def test_before_expiry_is_not_overstay(self) -> None:
        assert is_overstay(expiry_date=date(2026, 8, 12), today=date(2026, 8, 1)) is False


@pytest.mark.parametrize("vt", [VisaType.B1])
def test_reuses_catalogue_facts_not_hardcoded(vt: VisaType) -> None:
    # Guard against a future catalogue change silently diverging from the engine.
    from backend.services.visa_check.catalogue import VISA_META

    w = compute_stay(entry_date=date(2026, 1, 1), visa_type=vt)
    meta = VISA_META[vt]
    ext_count, ext_days = meta.extensions
    assert w.max_total_days == meta.duration_days + ext_count * ext_days
