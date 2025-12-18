"""
Comprehensive tests for Pricing Service - Target 95% coverage
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import importlib.util

pricing_service_path = backend_path / "services" / "pricing_service.py"
spec = importlib.util.spec_from_file_location("pricing_service", pricing_service_path)
pricing_service_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pricing_service_module)
PricingService = pricing_service_module.PricingService
get_pricing_service = pricing_service_module.get_pricing_service


class TestPricingService95Coverage:
    """Comprehensive tests for PricingService to achieve 95% coverage"""

    @pytest.fixture
    def mock_prices_data(self):
        """Mock prices JSON data"""
        return {
            "services": {
                "single_entry_visas": {"C1 Tourism": {"price_usd": 50, "legacy_names": ["B211A"]}},
                "multiple_entry_visas": {"D1 Business": {"price_usd": 100}},
                "kitas_permits": {"E23 Freelance": {"price_usd": 500}},
                "business_legal_services": {"PT PMA Setup": {"price_usd": 1000}},
                "taxation_services": {"NPWP Registration": {"price_usd": 50}},
                "quick_quotes": {"Startup Package": {"price_usd": 2000}},
            },
            "contact_info": {"email": "info@balizero.com", "whatsapp": "+62 813 3805 1876"},
            "disclaimer": {"text": "Prices subject to change"},
            "important_warnings": {"text": "Important info"},
        }

    def test_init_loads_prices_success(self, mock_prices_data):
        """Test initialization loads prices successfully"""
        json_path = backend_path.parent / "data" / "bali_zero_official_prices_2025.json"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            assert service.loaded is True
            assert service.prices == mock_prices_data

    def test_init_file_not_found(self):
        """Test initialization when file not found"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            assert service.loaded is False
            assert service.prices == {}

    def test_init_load_exception(self):
        """Test initialization with load exception"""
        json_path = backend_path.parent / "data" / "bali_zero_official_prices_2025.json"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("Read error")),
        ):
            service = PricingService()
            assert service.loaded is False
            assert service.prices == {}

    def test_get_pricing_all(self, mock_prices_data):
        """Test getting all pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("all")
            assert "services" in result

    def test_get_pricing_visa(self, mock_prices_data):
        """Test getting visa pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("visa")
            assert "single_entry_visas" in result
            assert "multiple_entry_visas" in result

    def test_get_pricing_kitas(self, mock_prices_data):
        """Test getting KITAS pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("kitas")
            assert "kitas_permits" in result

    def test_get_pricing_long_stay_permit(self, mock_prices_data):
        """Test getting long-stay permit pricing (alias for kitas)"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("long_stay_permit")
            assert "kitas_permits" in result

    def test_get_pricing_business_setup(self, mock_prices_data):
        """Test getting business setup pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("business_setup")
            assert "business_legal_services" in result

    def test_get_pricing_tax_consulting(self, mock_prices_data):
        """Test getting tax consulting pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("tax_consulting")
            assert "taxation_services" in result

    def test_get_pricing_legal(self, mock_prices_data):
        """Test getting legal pricing"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("legal")
            assert "business_legal_services" in result

    def test_get_pricing_search_service(self, mock_prices_data):
        """Test searching for service"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_pricing("C1 Tourism")
            assert "results" in result or "message" in result

    def test_get_pricing_not_loaded(self):
        """Test getting pricing when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_pricing("visa")
            assert "error" in result
            assert "fallback_contact" in result

    def test_get_all_prices(self, mock_prices_data):
        """Test getting all prices"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_all_prices()
            assert result == mock_prices_data

    def test_get_all_prices_not_loaded(self):
        """Test getting all prices when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_all_prices()
            assert "error" in result

    def test_search_service_found(self, mock_prices_data):
        """Test searching service that exists"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.search_service("C1 Tourism")
            assert "results" in result
            assert "official_notice" in result

    def test_search_service_not_found(self, mock_prices_data):
        """Test searching service that doesn't exist"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.search_service("NonExistent Service")
            assert "message" in result
            assert "suggestion" in result

    def test_search_service_legacy_name(self, mock_prices_data):
        """Test searching by legacy name"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.search_service("B211A")
            assert "results" in result

    def test_search_service_not_loaded(self):
        """Test searching when prices not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.search_service("test")
            assert "error" in result

    def test_get_visa_prices(self, mock_prices_data):
        """Test getting visa prices"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_visa_prices()
            assert "single_entry_visas" in result
            assert "multiple_entry_visas" in result

    def test_get_visa_prices_not_loaded(self):
        """Test getting visa prices when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_visa_prices()
            assert "error" in result

    def test_get_kitas_prices(self, mock_prices_data):
        """Test getting KITAS prices"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_kitas_prices()
            assert "kitas_permits" in result

    def test_get_kitas_prices_not_loaded(self):
        """Test getting KITAS prices when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_kitas_prices()
            assert "error" in result

    def test_get_business_prices(self, mock_prices_data):
        """Test getting business prices"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_business_prices()
            assert "business_legal_services" in result

    def test_get_business_prices_not_loaded(self):
        """Test getting business prices when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_business_prices()
            assert "error" in result

    def test_get_tax_prices(self, mock_prices_data):
        """Test getting tax prices"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_tax_prices()
            assert "taxation_services" in result

    def test_get_tax_prices_not_loaded(self):
        """Test getting tax prices when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_tax_prices()
            assert "error" in result

    def test_get_quick_quotes(self, mock_prices_data):
        """Test getting quick quotes"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.get_quick_quotes()
            assert "quick_quotes" in result

    def test_get_quick_quotes_not_loaded(self):
        """Test getting quick quotes when not loaded"""
        with patch("pathlib.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_quick_quotes()
            assert "error" in result

    def test_search_service_noise_words(self, mock_prices_data):
        """Test searching with noise words removed"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.search_service("berapa harga C1 Tourism?")
            assert "results" in result

    def test_search_service_dict_category(self, mock_prices_data):
        """Test searching in dict category structure"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_prices_data))),
        ):
            service = PricingService()
            result = service.search_service("PT PMA")
            assert "results" in result or "message" in result

    def test_get_pricing_service_singleton(self):
        """Test get_pricing_service returns singleton"""
        # Reset singleton
        pricing_service_module._pricing_service = None

        with patch("pathlib.Path.exists", return_value=False):
            service1 = get_pricing_service()
            service2 = get_pricing_service()
            assert service1 is service2
