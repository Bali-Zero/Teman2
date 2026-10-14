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


@pytest.mark.parametrize(
    "query",
    ["retirement", "retire", "pension", "pensiun", "pensiunan", "senior"],
)
def test_search_service_returns_e33f_and_skips_internal_rows(query: str) -> None:
    """Guilt: retirement/pension/senior queries return E33F rows and omit internal rows."""
    service = PricingService()
    res = service.search_service(query)
    kitas = res.get("results", {}).get("kitas_permits", {})
    e33f_keys = {
        "E33F Second Home Senior (1 Year, Offshore)",
        "E33F Second Home Senior (1 Year, Altus/Onshore)",
        "E33F Second Home Senior (Extend)",
    }
    internal_keys = {
        "Retirement (Altus/Onshore)",
        "Retirement (Offshore)",
        "Retirement (Extend)",
    }
    assert e33f_keys.issubset(set(kitas.keys()))
    assert internal_keys.isdisjoint(set(kitas.keys()))
    assert kitas["E33F Second Home Senior (1 Year, Offshore)"]["price"] == "14.000.000 IDR"
    assert kitas["E33F Second Home Senior (1 Year, Altus/Onshore)"]["price"] == "16.000.000 IDR"
    assert kitas["E33F Second Home Senior (Extend)"]["price"] == "10.000.000 IDR"


def test_search_service_innocence_kitap_and_get_service_by_key() -> None:
    """Innocence: Retirement KITAP + MERP is searchable and get_service_by_key works."""
    service = PricingService()
    kitap_res = service.search_service("KITAP")
    assert "Retirement KITAP + MERP" in kitap_res.get("results", {}).get("kitap_permits", {})

    offshore = service.get_service_by_key("Retirement (Offshore)")
    assert offshore is not None
    assert offshore["price"] == "14.000.000 IDR"


def test_format_for_llm_context_omits_internal_rows_and_includes_e33f() -> None:
    """format_for_llm_context omits internal Retirement rows for every service_type."""
    service = PricingService()
    internal_names = (
        "Retirement (Altus/Onshore)",
        "Retirement (Offshore)",
        "Retirement (Extend)",
    )
    for st in (None, "all", "visa", "kitas", "business", "tax", "other", "urgent"):
        ctx = service.format_for_llm_context(st)
        for internal_name in internal_names:
            assert internal_name not in ctx
    kitas_ctx = service.format_for_llm_context("kitas")
    assert "E33F Second Home Senior (1 Year, Offshore)" in kitas_ctx
    assert "Retirement KITAP + MERP" in kitas_ctx
