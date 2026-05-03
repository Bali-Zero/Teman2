"""Unit tests for Visa Clock timeline builder."""

from __future__ import annotations

from datetime import date, timedelta

from backend.services.visa_check.catalogue import VisaType
from backend.services.visa_check.clock import clock_timeline


class TestTimeline:
    def test_produces_5_checkpoints(self):
        tl = clock_timeline(visa_type=VisaType.C1, entry_date=date(2026, 1, 1))
        assert len(tl.checkpoints) == 5
        assert [c.label for c in tl.checkpoints] == ["D-60", "D-30", "D-14", "D-7", "D-1"]

    def test_c1_expiry_is_60_days_after_entry(self):
        entry = date(2026, 1, 1)
        tl = clock_timeline(visa_type=VisaType.C1, entry_date=entry)
        assert tl.expiry_date == entry + timedelta(days=60)

    def test_e33g_expiry_is_one_year_after_entry(self):
        entry = date(2026, 1, 1)
        tl = clock_timeline(visa_type=VisaType.E33G, entry_date=entry)
        assert tl.expiry_date == entry + timedelta(days=365)

    def test_checkpoint_dates_descend_to_expiry(self):
        tl = clock_timeline(visa_type=VisaType.E28A, entry_date=date(2026, 1, 1))
        # D-60 is 60 days before expiry; D-1 is 1 day before; expiry not included.
        assert tl.checkpoints[0].at == tl.expiry_date - timedelta(days=60)
        assert tl.checkpoints[-1].at == tl.expiry_date - timedelta(days=1)

    def test_c7a_is_not_extendable(self):
        tl = clock_timeline(visa_type=VisaType.C7A, entry_date=date(2026, 1, 1))
        assert tl.extensions_possible == 0
        assert tl.extension_days == 0

    def test_c1_extensions_match_reference(self):
        """Visa C-series reference memory: C1 = 60 + 2×60 = 180 days max."""
        tl = clock_timeline(visa_type=VisaType.C1, entry_date=date(2026, 1, 1))
        assert tl.extensions_possible == 2
        assert tl.extension_days == 60
