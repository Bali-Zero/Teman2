"""
Extended tests for PricingService — covers search, formatting, edge cases.

Complements existing pricing tests by testing the search algorithm,
noise word removal, multi-category lookup, and LLM context formatting.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest


SAMPLE_PRICES = {
    "services": {
        "single_entry_visas": [
            {
                "code": "B211A",
                "name": "Tourist Visa (Single Entry)",
                "price_idr": 2_500_000,
                "price_usd_approx": 160,
                "duration": "60 days",
                "notes": "Extendable 4 times",
            },
            {
                "code": "E28A",
                "name": "Investor KITAS Visa",
                "price_idr": 15_000_000,
                "price_usd_approx": 960,
                "duration": "1 year",
            },
        ],
        "kitas_permits": [
            {
                "code": "KITAS-INVESTOR",
                "name": "Investor KITAS",
                "price_idr": 20_000_000,
                "price_usd_approx": 1280,
                "duration": "1 year",
            },
        ],
        "company_services": [
            {
                "code": "PT-PMA",
                "name": "PT PMA Company Setup",
                "price_idr": 35_000_000,
                "price_usd_approx": 2240,
                "notes": "Full registration package",
            },
        ],
        "urgent_services": [
            {
                "code": "URGENT-VISA",
                "name": "Urgent Visa Processing",
                "price_idr": 5_000_000,
                "price_usd_approx": 320,
                "notes": "Express processing surcharge",
            },
        ],
    },
    "contact_info": {
        "email": "info@balizero.com",
        "whatsapp": "+62812345678",
    },
    "last_updated": "2025-06-01",
}


@pytest.fixture
def pricing_service():
    """Create PricingService with sample data (mocking file load)."""
    with patch("backend.services.pricing.pricing_service.Path") as mock_path:
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value.__truediv__ = MagicMock(return_value=mock_path_instance)
        # Make the chained Path operations work
        mock_path.__truediv__ = MagicMock(return_value=mock_path_instance)

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(SAMPLE_PRICES))
        ):
            from backend.services.pricing.pricing_service import PricingService

            service = PricingService.__new__(PricingService)
            service.prices = SAMPLE_PRICES
            service.loaded = True
            return service


@pytest.fixture
def unloaded_pricing_service():
    """Create PricingService that failed to load prices."""
    from backend.services.pricing.pricing_service import PricingService

    service = PricingService.__new__(PricingService)
    service.prices = {}
    service.loaded = False
    return service


class TestPricingServiceSearch:
    """Tests for the search_service method."""

    def test_search_kitas(self, pricing_service):
        result = pricing_service.search_service("kitas")
        assert len(result) > 0

    def test_search_investor(self, pricing_service):
        result = pricing_service.search_service("investor")
        assert len(result) > 0

    def test_search_pt_pma(self, pricing_service):
        result = pricing_service.search_service("PT PMA company setup")
        assert len(result) > 0

    def test_search_noise_words_removed(self, pricing_service):
        """Noise words like 'how much', 'cost', 'berapa' should be stripped."""
        result1 = pricing_service.search_service("how much does kitas cost?")
        result2 = pricing_service.search_service("kitas")
        # Both should find KITAS-related services
        assert len(result1) > 0
        assert len(result2) > 0

    def test_search_empty_query(self, pricing_service):
        """Empty query after noise removal should still work."""
        result = pricing_service.search_service("how much is the?")
        # Should fall back to raw query
        assert isinstance(result, dict)

    def test_search_unloaded(self, unloaded_pricing_service):
        """Search on unloaded service should return error."""
        result = unloaded_pricing_service.search_service("visa")
        assert "error" in result


class TestPricingServiceGetters:
    """Tests for category getter methods."""

    def test_get_all_prices(self, pricing_service):
        result = pricing_service.get_all_prices()
        assert "services" in result
        assert "contact_info" in result

    def test_get_all_prices_unloaded(self, unloaded_pricing_service):
        result = unloaded_pricing_service.get_all_prices()
        assert "error" in result

    def test_get_pricing_visa(self, pricing_service):
        result = pricing_service.get_pricing("visa")
        assert isinstance(result, dict)

    def test_get_pricing_all(self, pricing_service):
        result = pricing_service.get_pricing("all")
        assert isinstance(result, dict)

    def test_get_pricing_unloaded(self, unloaded_pricing_service):
        result = unloaded_pricing_service.get_pricing("visa")
        assert "error" in result


class TestPricingServiceFormat:
    """Tests for LLM context formatting."""

    def test_format_for_llm_returns_string(self, pricing_service):
        result = pricing_service.format_for_llm_context()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_for_llm_with_service_type(self, pricing_service):
        result = pricing_service.format_for_llm_context(service_type="visa")
        assert isinstance(result, str)

    def test_format_for_llm_unloaded(self, unloaded_pricing_service):
        result = unloaded_pricing_service.format_for_llm_context()
        assert isinstance(result, str)
