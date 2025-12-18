"""
Integration Tests for PricingPlugin
Tests Bali Zero pricing plugin with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPricingPluginIntegration:
    """Comprehensive integration tests for PricingPlugin"""

    @pytest_asyncio.fixture
    async def mock_pricing_service(self):
        """Create mock pricing service"""
        mock_service = MagicMock()
        mock_service.get_pricing = MagicMock(
            return_value={
                "visa": [{"name": "C1 Tourism", "price": 500000}],
                "kitas": [{"name": "E23 Freelance", "price": 15000000}],
            }
        )
        mock_service.search_service = MagicMock(
            return_value={"results": [{"name": "PT PMA Setup", "price": 25000000}]}
        )
        return mock_service

    @pytest_asyncio.fixture
    async def pricing_plugin(self, mock_pricing_service):
        """Create PricingPlugin instance"""
        from plugins.bali_zero.pricing_plugin import PricingPlugin

        plugin = PricingPlugin(pricing_service=mock_pricing_service)
        return plugin

    def test_initialization(self, pricing_plugin):
        """Test plugin initialization"""
        assert pricing_plugin is not None
        assert pricing_plugin.pricing_service is not None

    def test_metadata(self, pricing_plugin):
        """Test plugin metadata"""
        metadata = pricing_plugin.metadata

        assert metadata is not None
        assert metadata.name == "bali_zero.pricing"
        assert metadata.version == "1.0.0"
        assert "pricing" in metadata.tags
        assert metadata.category.value == "bali_zero"

    def test_input_schema(self, pricing_plugin):
        """Test input schema"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        assert pricing_plugin.input_schema == PricingQueryInput

    def test_output_schema(self, pricing_plugin):
        """Test output schema"""
        from plugins.bali_zero.pricing_plugin import PricingQueryOutput

        assert pricing_plugin.output_schema == PricingQueryOutput

    @pytest.mark.asyncio
    async def test_execute_all_services(self, pricing_plugin):
        """Test executing plugin with all services"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="all")
        result = await pricing_plugin.execute(input_data)

        assert result is not None
        assert hasattr(result, "prices") or hasattr(result, "data")

    @pytest.mark.asyncio
    async def test_execute_visa_service(self, pricing_plugin):
        """Test executing plugin for visa services"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="visa")
        result = await pricing_plugin.execute(input_data)

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_kitas_service(self, pricing_plugin):
        """Test executing plugin for KITAS services"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="kitas")
        result = await pricing_plugin.execute(input_data)

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_with_query(self, pricing_plugin):
        """Test executing plugin with search query"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="all", query="PT PMA setup")
        result = await pricing_plugin.execute(input_data)

        assert result is not None
        # Should use search_service when query provided
        pricing_plugin.pricing_service.search_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_business_setup(self, pricing_plugin):
        """Test executing plugin for business setup"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="business_setup")
        result = await pricing_plugin.execute(input_data)

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_tax_consulting(self, pricing_plugin):
        """Test executing plugin for tax consulting"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="tax_consulting")
        result = await pricing_plugin.execute(input_data)

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_legal_service(self, pricing_plugin):
        """Test executing plugin for legal services"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="legal")
        result = await pricing_plugin.execute(input_data)

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, pricing_plugin):
        """Test error handling in plugin execution"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        # Mock service to raise exception
        pricing_plugin.pricing_service.get_pricing = MagicMock(
            side_effect=Exception("Service error")
        )

        input_data = PricingQueryInput(service_type="all")
        result = await pricing_plugin.execute(input_data)

        # Should handle error gracefully
        assert result is not None

    def test_pricing_query_input_default(self):
        """Test PricingQueryInput with default values"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput()
        assert input_data.service_type == "all"
        assert input_data.query is None

    def test_pricing_query_input_custom(self):
        """Test PricingQueryInput with custom values"""
        from plugins.bali_zero.pricing_plugin import PricingQueryInput

        input_data = PricingQueryInput(service_type="visa", query="tourist visa")
        assert input_data.service_type == "visa"
        assert input_data.query == "tourist visa"
