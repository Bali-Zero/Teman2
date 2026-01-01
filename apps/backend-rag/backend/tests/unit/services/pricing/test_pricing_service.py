"""
Unit tests for PricingService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.pricing.pricing_service import PricingService


class TestPricingService:
    """Tests for PricingService"""

    def test_init(self):
        """Test initialization"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            assert service.loaded is False

    def test_get_pricing_all(self):
        """Test getting all pricing"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_pricing("all")
            assert isinstance(result, dict)

    def test_get_pricing_visa(self):
        """Test getting visa pricing"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_pricing("visa")
            assert isinstance(result, dict)

    def test_get_pricing_kitas(self):
        """Test getting KITAS pricing"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_pricing("kitas")
            assert isinstance(result, dict)

    def test_get_pricing_not_loaded(self):
        """Test getting pricing when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_pricing("visa")
            assert "error" in result

    def test_search_service(self):
        """Test searching for service"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.search_service("test")
            assert isinstance(result, dict)

    def test_get_visa_prices(self):
        """Test getting visa prices"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {"single_entry_visas": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_visa_prices()
            assert isinstance(result, dict)

    def test_get_kitas_prices(self):
        """Test getting KITAS prices"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {"kitas_permits": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_kitas_prices()
            assert isinstance(result, dict)

    def test_get_business_prices(self):
        """Test getting business prices"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {"company_services": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_business_prices()
            assert isinstance(result, dict)

    def test_get_tax_prices(self):
        """Test getting tax prices"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_tax_prices()
            assert isinstance(result, dict)

    def test_get_quick_quotes(self):
        """Test getting quick quotes"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_quick_quotes()
            assert isinstance(result, dict)

    def test_get_warnings(self):
        """Test getting warnings"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.get_warnings()
            assert isinstance(result, dict)

    def test_format_for_llm_context(self):
        """Test formatting for LLM context"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()
            
            service = PricingService()
            result = service.format_for_llm_context("visa")
            assert isinstance(result, str)
