from unittest.mock import patch

import pytest

from backend.services.pricing.pricing_service import PricingService

# Test Suite for PricingService
# Corrected manually by Overlord to serve as a Gold Standard


@pytest.fixture
def mock_prices():
    # 2026 schema fixture — visa_extensions dropped, urgent_services renamed
    # to urgent_processing, tax_accounting + consultant_services added.
    return {
        "services": {
            "single_entry_visas": {"Tourist": {"price": "1.500.000"}},
            "multiple_entry_visas": {},
            "kitas_permits": {},
            "kitap_permits": {},
            "tax_accounting": {},
            "company_services": {},
            "consultant_services": {},
            "other_process": {},
            "urgent_processing": {},
        },
    }


def test_pricing_service_init():
    """Test that the service initializes even if JSON is missing."""
    service = PricingService()
    # It should not crash, just set loaded to False if file missing
    assert isinstance(service.prices, dict)


def test_get_all_prices_not_loaded():
    """Test behavior when prices are not loaded."""
    service = PricingService()
    service.loaded = False
    res = service.get_all_prices()
    assert "error" in res


@patch("backend.services.pricing.pricing_service.PricingService._load_prices")
def test_get_visa_prices(mock_load, mock_prices):
    """Test visa pricing retrieval with mocked data."""
    service = PricingService()
    service.prices = mock_prices
    service.loaded = True

    res = service.get_visa_prices()
    assert "single_entry_visas" in res
    assert "Tourist" in res["single_entry_visas"]


def test_search_service():
    """Test the search functionality."""
    service = PricingService()
    service.prices = {"services": {"single_entry_visas": {"B211A": {"price": "2.000.000"}}}}
    service.loaded = True

    res = service.search_service("B211A")
    assert "results" in res
    assert "single_entry_visas" in res["results"]
