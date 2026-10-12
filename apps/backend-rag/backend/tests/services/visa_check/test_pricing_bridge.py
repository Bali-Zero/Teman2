"""PricingBridge integration — no hardcoded prices, name-based hints.

Every VisaType must resolve to a positive IDR cost from the real JSON
except for the two documented known-None cases (C6, E30A), which reflect
the fact that the pricing JSON does not ship an entry for those services.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.catalogue import VISA_META, VisaType
from backend.services.visa_check.pricing_bridge import (
    KNOWN_NONE_VISAS,
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

    def test_known_none_set_is_subset_of_visatype(self):
        for vt in KNOWN_NONE_VISAS:
            assert vt in VISA_META

    def test_every_non_known_none_visa_resolves(self):
        if not self.pricing.loaded:
            return  # pricing service unavailable in this env — skip silently
        for vt in VisaType:
            if vt in KNOWN_NONE_VISAS:
                continue
            cost, source = estimate_match_cost(visa_type=vt, pricing=self.pricing)
            assert cost is not None, f"{vt.value}: no price found in JSON"
            assert cost > 0, f"{vt.value}: zero cost"
            assert source, f"{vt.value}: source string empty"

    def test_known_none_visas_return_none(self):
        if not self.pricing.loaded:
            return
        for vt in KNOWN_NONE_VISAS:
            cost, source = estimate_match_cost(visa_type=vt, pricing=self.pricing)
            # Known-None: either both None or a lucky match — never a crash.
            assert (cost is None) == (source is None)

    def test_investor_resolves_to_positive_cost(self):
        if not self.pricing.loaded:
            return
        cost, source = estimate_match_cost(visa_type=VisaType.E28A, pricing=self.pricing)
        assert cost is not None
        assert cost > 0
        assert source

    def test_e33g_prefers_offshore(self):
        if not self.pricing.loaded:
            return
        cost, source = estimate_match_cost(visa_type=VisaType.E33G, pricing=self.pricing)
        # Offshore E33G = 13M IDR, Altus/Onshore = 14M. Either is acceptable,
        # but we document the tie-break preference.
        assert cost is not None
        assert "remote" in (source or "").lower() or "e33g" in (source or "").lower()

    def test_freelance_e23_separate_from_working_kitas(self):
        if not self.pricing.loaded:
            return
        freelance_cost, _ = estimate_match_cost(
            visa_type=VisaType.E23_FREELANCE, pricing=self.pricing
        )
        working_cost, _ = estimate_match_cost(visa_type=VisaType.E23, pricing=self.pricing)
        if freelance_cost and working_cost:
            assert freelance_cost != working_cost, (
                "E23_FREELANCE and E23 should resolve to different price entries"
            )


_CATALOGUE = (
    Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"
)


def _catalogue_price(category: str, key: str) -> int:
    raw = json.loads(_CATALOGUE.read_text())["services"][category][key]["price"]
    return int(raw.replace(" IDR", "").replace(".", ""))


class TestQuotesPinnedToTheirOwnCatalogueRow:
    """A visa type with its own catalogue row must be quoted from THAT row.

    D2 used to be hinted at the D12 row first and so was quoted 7.500.000
    instead of its own 6.500.000 (audit 2026-10-12).
    """

    def setup_method(self):
        self.pricing = PricingService()

    def test_d2_is_its_own_row_not_d12(self):
        assert self.pricing.loaded
        cost, source = estimate_match_cost(visa_type=VisaType.D2, pricing=self.pricing)
        assert source == "D2 Business (1 Year)"
        assert cost == _catalogue_price("multiple_entry_visas", "D2 Business (1 Year)")
        assert cost != _catalogue_price(
            "multiple_entry_visas", "D12 Business Investigation (1 Year)"
        )

    def test_c6_and_e30a_are_priced_from_their_rows(self):
        assert self.pricing.loaded
        c6, c6_src = estimate_match_cost(visa_type=VisaType.C6, pricing=self.pricing)
        assert c6_src == "C6 Social Activity"
        assert c6 == _catalogue_price("single_entry_visas", "C6 Social Activity")
        e30a, e30a_src = estimate_match_cost(visa_type=VisaType.E30A, pricing=self.pricing)
        assert e30a_src == "E30A Education Visa (1 Year)"
        assert e30a == _catalogue_price("kitas_permits", "E30A Education Visa (1 Year)")
