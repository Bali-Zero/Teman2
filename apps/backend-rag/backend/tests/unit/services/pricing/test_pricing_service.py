"""
Unit tests for PricingService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("all")
            assert isinstance(result, dict)

    def test_get_pricing_visa(self):
        """Test getting visa pricing"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("visa")
            assert isinstance(result, dict)

    def test_get_pricing_kitas(self):
        """Test getting KITAS pricing"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
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
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.search_service("test")
            assert isinstance(result, dict)

    def test_get_visa_prices(self):
        """Test getting visa prices"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"single_entry_visas": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_visa_prices()
            assert isinstance(result, dict)

    def test_get_kitas_prices(self):
        """Test getting KITAS prices"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"kitas_permits": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_kitas_prices()
            assert isinstance(result, dict)

    def test_get_business_prices(self):
        """Test getting business prices"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"company_services": []}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_business_prices()
            assert isinstance(result, dict)

    def test_get_tax_prices(self):
        """Test getting tax prices"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_tax_prices()
            assert isinstance(result, dict)

    def test_get_quick_quotes(self):
        """Test getting quick quotes"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_quick_quotes()
            assert isinstance(result, dict)

    def test_get_warnings(self):
        """Test getting warnings"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_warnings()
            assert isinstance(result, dict)

    def test_format_for_llm_context(self):
        """Test formatting for LLM context"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.format_for_llm_context("visa")
            assert isinstance(result, str)

    def test_load_prices_exception(self):
        """Test _load_prices handles exception"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", side_effect=Exception("Read error")),
        ):
            service = PricingService()
            assert service.loaded is False
            assert service.prices == {}

    def test_get_pricing_business_setup(self):
        """Test getting business_setup pricing"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"company_services": {}}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("business_setup")
            assert "official_notice" in result

    def test_get_pricing_tax_consulting(self):
        """Test getting tax_consulting pricing"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"urgent_services": {}}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("tax_consulting")
            assert "official_notice" in result

    def test_get_pricing_legal(self):
        """Test getting legal pricing (maps to business)"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"company_services": {}}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("legal")
            assert "official_notice" in result

    def test_get_pricing_unknown_type(self):
        """Test getting unknown service type falls through to search"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("unknown_type")
            # Falls through to search_service
            assert "message" in result or "results" in result

    def test_get_pricing_long_stay_permit(self):
        """Test getting long_stay_permit pricing (alias for kitas)"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {"services": {"kitas_permits": {}}}
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.get_pricing("long_stay_permit")
            assert "official_notice" in result

    def test_get_all_prices_not_loaded(self):
        """Test get_all_prices when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_all_prices()
            assert "error" in result

    def test_search_service_not_loaded(self):
        """Test search_service when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.search_service("test")
            assert "error" in result

    def test_search_service_with_results(self):
        """Test search_service with matching results"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {
                    "test_category": {
                        "TestService": {"price": "XXX", "description": "Test description"}
                    }
                },
                "contact_info": {"email": "test@example.com"},
                "disclaimer": {"text": "Test disclaimer"},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.search_service("TestService")
            assert "results" in result
            assert "test_category" in result["results"]

    def test_search_service_with_legacy_names(self):
        """Test search_service with legacy names"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {
                    "test_category": {
                        "NewServiceName": {
                            "price": "XXX",
                            "legacy_names": ["OldCode-123", "Legacy Name"],
                        }
                    }
                },
                "contact_info": {},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.search_service("OldCode-123")
            assert "results" in result

    def test_get_visa_prices_not_loaded(self):
        """Test get_visa_prices when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_visa_prices()
            assert "error" in result

    def test_get_kitas_prices_not_loaded(self):
        """Test get_kitas_prices when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_kitas_prices()
            assert "error" in result

    def test_get_business_prices_not_loaded(self):
        """Test get_business_prices when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_business_prices()
            assert "error" in result

    def test_get_tax_prices_not_loaded(self):
        """Test get_tax_prices when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_tax_prices()
            assert "error" in result

    def test_get_quick_quotes_not_loaded(self):
        """Test get_quick_quotes when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_quick_quotes()
            assert "error" in result

    def test_get_warnings_not_loaded(self):
        """Test get_warnings when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.get_warnings()
            assert "error" in result

    def test_format_for_llm_context_not_loaded(self):
        """Test format_for_llm_context when not loaded"""
        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            service = PricingService()
            result = service.format_for_llm_context()
            assert "not available" in result.lower()

    def test_format_for_llm_context_all(self):
        """Test format_for_llm_context with all services"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {
                    "single_entry_visas": {"TestSEV": {"price": "XXX"}},
                    "multiple_entry_visas": {"TestMEV": {"price": "XXX", "validity": "XX days"}},
                    "kitas_permits": {"TestKITAS": {"price": "XXX"}},
                    "kitap_permits": {"TestKITAP": {"price": "XXX"}},
                    "company_services": {"TestCompany": {"price": "XXX"}},
                    "other_process": {"TestOther": {"price": "XXX"}},
                },
                "important_warnings": {"warning1": "Test warning 1", "warning2": "Test warning 2"},
                "contact_info": {"email": "test@example.com", "whatsapp": "+000"},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.format_for_llm_context()
            assert "VISA PRICES" in result
            assert "KITAS" in result
            assert "COMPANY" in result
            assert "OTHER" in result
            assert "WARNING" in result

    def test_format_for_llm_context_kitas_only(self):
        """Test format_for_llm_context with kitas only"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {"kitas_permits": {"TestKITAS": {"price": "XXX"}}},
                "contact_info": {"email": "test@example.com"},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.format_for_llm_context("kitas")
            assert "KITAS" in result

    def test_format_for_llm_context_business_only(self):
        """Test format_for_llm_context with business only"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {"company_services": {"TestCompany": {"price": "XXX"}}},
                "contact_info": {},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.format_for_llm_context("business")
            assert "COMPANY" in result

    def test_format_for_llm_context_other_only(self):
        """Test format_for_llm_context with other only"""
        with (
            patch("services.pricing.pricing_service.Path.exists", return_value=True),
            patch("builtins.open", create=True) as mock_open,
            patch("json.load") as mock_json_load,
        ):
            mock_json_load.return_value = {
                "services": {"other_process": {"TestOther": {"price": "XXX"}}},
                "contact_info": {},
            }
            mock_open.return_value.__enter__.return_value = MagicMock()

            service = PricingService()
            result = service.format_for_llm_context("other")
            assert "OTHER" in result


class TestPricingServiceConvenienceFunctions:
    """Tests for convenience functions"""

    def test_get_all_prices_func(self):
        """Test get_all_prices function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_all_prices

        # Reset singleton
        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_all_prices()
            assert "error" in result

    def test_search_service_func(self):
        """Test search_service function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import search_service

        # Reset singleton
        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = search_service("test")
            assert "error" in result

    def test_get_visa_prices_func(self):
        """Test get_visa_prices function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_visa_prices

        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_visa_prices()
            assert "error" in result

    def test_get_kitas_prices_func(self):
        """Test get_kitas_prices function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_kitas_prices

        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_kitas_prices()
            assert "error" in result

    def test_get_business_prices_func(self):
        """Test get_business_prices function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_business_prices

        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_business_prices()
            assert "error" in result

    def test_get_tax_prices_func(self):
        """Test get_tax_prices function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_tax_prices

        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_tax_prices()
            assert "error" in result

    def test_get_pricing_context_for_llm_func(self):
        """Test get_pricing_context_for_llm function"""
        import services.pricing.pricing_service as ps
        from services.pricing.pricing_service import get_pricing_context_for_llm

        ps._pricing_service = None

        with patch("services.pricing.pricing_service.Path.exists", return_value=False):
            result = get_pricing_context_for_llm()
            assert "not available" in result.lower()
