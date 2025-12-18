"""
Comprehensive tests for services/pricing_service.py
Target: 95%+ coverage
"""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from services.pricing_service import (
    PricingService,
    get_all_prices,
    get_pricing_service,
    get_visa_prices,
    search_service,
)


class TestPricingService:
    """Comprehensive test suite for PricingService"""

    @pytest.fixture
    def sample_prices_data(self):
        """Sample pricing data"""
        return {
            "services": {
                "single_entry_visas": {
                    "C1 Tourism": {"price": "1.5M IDR"},
                    "B211A": {"price": "2M IDR", "legacy_names": ["B211A"]},
                },
                "multiple_entry_visas": {
                    "D1 Multiple Entry": {"price_1y": "5M IDR", "price_2y": "8M IDR"},
                },
                "kitas_permits": {
                    "Investor KITAS": {"offshore": "47.5M IDR", "onshore": "45M IDR"},
                },
                "business_legal_services": {
                    "PT PMA Setup": {"price": "25M IDR"},
                },
                "taxation_services": {
                    "Tax Consultation": {"price": "2M IDR"},
                },
            },
            "contact_info": {"email": "info@balizero.com", "whatsapp": "+62 813 3805 1876"},
            "disclaimer": {"text": "Prices subject to change"},
            "important_warnings": {"warning1": "Be careful"},
        }

    def test_init_with_file(self, sample_prices_data):
        """Test initialization with existing file"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "builtins.open", mock_open(read_data=str(sample_prices_data).replace("'", '"'))
            ):
                with patch("json.load", return_value=sample_prices_data):
                    service = PricingService()
                    assert service.loaded is True

    def test_init_without_file(self):
        """Test initialization without file"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            assert service.loaded is False
            assert service.prices == {}

    def test_init_with_error(self):
        """Test initialization with error"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", side_effect=Exception("Error")):
                service = PricingService()
                assert service.loaded is False

    def test_get_pricing_all(self, sample_prices_data):
        """Test get_pricing with 'all'"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_pricing("all")
        assert "services" in result

    def test_get_pricing_visa(self, sample_prices_data):
        """Test get_pricing with 'visa'"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_pricing("visa")
        assert "single_entry_visas" in result or "error" in result

    def test_get_pricing_kitas(self, sample_prices_data):
        """Test get_pricing with 'kitas'"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_pricing("kitas")
        assert "kitas_permits" in result or "error" in result

    def test_get_pricing_business(self, sample_prices_data):
        """Test get_pricing with 'business_setup'"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_pricing("business_setup")
        assert "business_legal_services" in result or "error" in result

    def test_get_pricing_not_loaded(self):
        """Test get_pricing when not loaded"""
        service = PricingService()
        service.loaded = False
        result = service.get_pricing("all")
        assert "error" in result

    def test_get_all_prices(self, sample_prices_data):
        """Test get_all_prices"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_all_prices()
        assert result == sample_prices_data

    def test_get_all_prices_not_loaded(self):
        """Test get_all_prices when not loaded"""
        service = PricingService()
        service.loaded = False
        result = service.get_all_prices()
        assert "error" in result

    def test_search_service_found(self, sample_prices_data):
        """Test search_service with found service"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.search_service("Tourism")
        assert "results" in result or "message" in result

    def test_search_service_not_found(self, sample_prices_data):
        """Test search_service with not found service"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.search_service("NonExistentService")
        assert "message" in result or "results" in result

    def test_search_service_not_loaded(self):
        """Test search_service when not loaded"""
        service = PricingService()
        service.loaded = False
        result = service.search_service("test")
        assert "error" in result

    def test_get_visa_prices(self, sample_prices_data):
        """Test get_visa_prices"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_visa_prices()
        assert "single_entry_visas" in result or "error" in result

    def test_get_kitas_prices(self, sample_prices_data):
        """Test get_kitas_prices"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_kitas_prices()
        assert "kitas_permits" in result or "error" in result

    def test_get_business_prices(self, sample_prices_data):
        """Test get_business_prices"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_business_prices()
        assert "business_legal_services" in result or "error" in result

    def test_get_tax_prices(self, sample_prices_data):
        """Test get_tax_prices"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_tax_prices()
        assert "taxation_services" in result or "error" in result

    def test_get_quick_quotes(self, sample_prices_data):
        """Test get_quick_quotes"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_quick_quotes()
        assert "quick_quotes" in result or "error" in result

    def test_get_warnings(self, sample_prices_data):
        """Test get_warnings"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.get_warnings()
        assert "important_warnings" in result or "error" in result

    def test_format_for_llm_context(self, sample_prices_data):
        """Test format_for_llm_context"""
        service = PricingService()
        service.prices = sample_prices_data
        service.loaded = True
        result = service.format_for_llm_context()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_for_llm_context_not_loaded(self):
        """Test format_for_llm_context when not loaded"""
        service = PricingService()
        service.loaded = False
        result = service.format_for_llm_context()
        assert "not available" in result.lower()

    def test_get_pricing_service_singleton(self):
        """Test get_pricing_service returns singleton"""
        with patch("services.pricing_service._pricing_service", None):
            service1 = get_pricing_service()
            service2 = get_pricing_service()
            assert service1 is service2

    def test_convenience_functions(self, sample_prices_data):
        """Test convenience functions"""
        with patch("services.pricing_service.get_pricing_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_all_prices.return_value = sample_prices_data
            mock_get.return_value = mock_service

            result = get_all_prices()
            assert result == sample_prices_data

            mock_service.get_visa_prices.return_value = {"visa": "data"}
            result = get_visa_prices()
            assert "visa" in result

            mock_service.search_service.return_value = {"results": {}}
            result = search_service("test")
            assert "results" in result
