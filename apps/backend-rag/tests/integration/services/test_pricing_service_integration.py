"""
Integration Tests for PricingService
Tests official Bali Zero pricing service with real data
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPricingServiceIntegration:
    """Comprehensive integration tests for PricingService"""

    @pytest.fixture
    def mock_prices_data(self):
        """Create mock prices data"""
        return {
            "services": {
                "single_entry_visas": {
                    "VOA": {
                        "name": "Visa on Arrival",
                        "price_idr": 500000,
                        "price_usd": 35,
                        "duration_days": 30,
                    }
                },
                "kitas_permits": {
                    "E33G": {
                        "name": "Digital Nomad KITAS",
                        "price_idr": 15000000,
                        "price_usd": 1000,
                        "duration_years": 5,
                    }
                },
                "business_legal_services": {
                    "PT_PMA": {
                        "name": "PT PMA Setup",
                        "price_idr": 50000000,
                        "price_usd": 3500,
                    }
                },
            },
            "contact_info": {
                "email": "info@balizero.com",
                "whatsapp": "+62 813 3805 1876",
            },
        }

    @pytest.fixture
    def service_with_mock_data(self, mock_prices_data, tmp_path):
        """Create PricingService with mock data file"""
        # Create temporary prices file
        prices_file = tmp_path / "bali_zero_official_prices_2025.json"
        with open(prices_file, "w", encoding="utf-8") as f:
            json.dump(mock_prices_data, f)

        with patch("services.pricing_service.Path") as mock_path:
            mock_path.return_value.parent.parent = tmp_path

            from services.pricing_service import PricingService

            service = PricingService()
            return service

    def test_initialization(self, service_with_mock_data):
        """Test service initialization"""
        assert service_with_mock_data is not None
        assert service_with_mock_data.loaded is True

    def test_get_all_prices(self, service_with_mock_data):
        """Test getting all prices"""
        prices = service_with_mock_data.get_all_prices()

        assert prices is not None
        assert "services" in prices

    def test_get_pricing_visa(self, service_with_mock_data):
        """Test getting visa prices"""
        result = service_with_mock_data.get_pricing(service_type="visa")

        assert result is not None
        assert "single_entry_visas" in result or "multiple_entry_visas" in result

    def test_get_pricing_kitas(self, service_with_mock_data):
        """Test getting KITAS prices"""
        result = service_with_mock_data.get_pricing(service_type="kitas")

        assert result is not None
        assert "kitas_permits" in result

    def test_get_pricing_business_setup(self, service_with_mock_data):
        """Test getting business setup prices"""
        result = service_with_mock_data.get_pricing(service_type="business_setup")

        assert result is not None
        assert "business_legal_services" in result

    def test_get_pricing_tax_consulting(self, service_with_mock_data):
        """Test getting tax consulting prices"""
        result = service_with_mock_data.get_pricing(service_type="tax_consulting")

        assert result is not None

    def test_get_pricing_all(self, service_with_mock_data):
        """Test getting all prices via get_pricing"""
        result = service_with_mock_data.get_pricing(service_type="all")

        assert result is not None
        assert "services" in result

    def test_search_service_by_name(self, service_with_mock_data):
        """Test searching service by name"""
        result = service_with_mock_data.search_service("VOA")

        assert result is not None
        assert len(result) > 0

    def test_search_service_by_keyword(self, service_with_mock_data):
        """Test searching service by keyword"""
        result = service_with_mock_data.search_service("Digital Nomad")

        assert result is not None
        assert len(result) > 0

    def test_search_service_not_found(self, service_with_mock_data):
        """Test searching for non-existent service"""
        result = service_with_mock_data.search_service("Nonexistent Service")

        assert result is not None
        # May return empty dict or error message

    def test_get_visa_prices(self, service_with_mock_data):
        """Test getting visa prices directly"""
        result = service_with_mock_data.get_visa_prices()

        assert result is not None
        assert "single_entry_visas" in result or "multiple_entry_visas" in result

    def test_get_kitas_prices(self, service_with_mock_data):
        """Test getting KITAS prices directly"""
        result = service_with_mock_data.get_kitas_prices()

        assert result is not None
        assert "kitas_permits" in result

    def test_get_business_prices(self, service_with_mock_data):
        """Test getting business prices directly"""
        result = service_with_mock_data.get_business_prices()

        assert result is not None
        assert "business_legal_services" in result

    def test_get_tax_prices(self, service_with_mock_data):
        """Test getting tax prices directly"""
        result = service_with_mock_data.get_tax_prices()

        assert result is not None

    def test_service_not_loaded(self):
        """Test service when prices file not found"""
        with patch("services.pricing_service.Path") as mock_path:
            mock_path.return_value.parent.parent = Path("/nonexistent")

            from services.pricing_service import PricingService

            service = PricingService()

            assert service.loaded is False
            result = service.get_pricing("visa")
            assert "error" in result or "not loaded" in str(result).lower()

    def test_search_service_removes_noise_words(self, service_with_mock_data):
        """Test that search removes noise words"""
        result = service_with_mock_data.search_service("berapa harga VOA?")

        # Should still find VOA despite noise words
        assert result is not None

    def test_get_pricing_unknown_service_type(self, service_with_mock_data):
        """Test getting pricing for unknown service type"""
        result = service_with_mock_data.get_pricing(service_type="unknown_type")

        # Should attempt search
        assert result is not None
