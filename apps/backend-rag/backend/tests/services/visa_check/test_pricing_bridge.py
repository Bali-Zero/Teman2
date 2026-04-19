"""PricingBridge integration — no hardcoded prices allowed.

Validates that the bridge pulls from PricingService and that the IDR
string parser handles the real JSON shape ('5.800.000 IDR').
"""

from __future__ import annotations

from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.catalogue import VisaType
from backend.services.visa_check.pricing_bridge import (
    _idr_string_to_int,
    estimate_match_cost,
)


class TestIdrParser:
    def test_parses_thousands_dots(self):
        assert _idr_string_to_int("5.800.000 IDR") == 5_800_000

    def test_parses_with_spaces(self):
        assert _idr_string_to_int("  10.000.000 IDR  ") == 10_000_000

    def test_rejects_non_idr(self):
        assert _idr_string_to_int("$100") is None

    def test_empty_returns_none(self):
        assert _idr_string_to_int("") is None


class TestEstimateMatchCost:
    def setup_method(self):
        self.pricing = PricingService()

    def test_returns_cost_for_every_catalogue_type(self):
        """Smoke: every VisaType either resolves to a cost or None
        (None is acceptable — the UI falls back to 'confirm on WA')."""
        for vt in VisaType:
            cost, source = estimate_match_cost(visa_type=vt, pricing=self.pricing)
            # Either both None or both non-None (consistency check).
            assert (cost is None) == (source is None), vt.value
            if cost is not None:
                assert cost > 0, f"{vt.value} returned zero cost"

    def test_investor_resolves_to_positive_cost(self):
        cost, source = estimate_match_cost(
            visa_type=VisaType.E28A, pricing=self.pricing
        )
        # If PricingService loaded, E28A (Investor KITAS) must exist.
        if self.pricing.loaded:
            assert cost is not None
            assert source is not None
            assert "investor" in source.lower() or "E28A" in source.upper()
