"""
Unit tests for DynamicPricingService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.pricing.dynamic_pricing_service import DynamicPricingService, PricingResult


@pytest.fixture
def mock_synthesis_service():
    """Mock cross oracle synthesis service"""
    service = MagicMock()
    service.synthesize = AsyncMock(return_value={"content": "Test synthesis"})
    return service


@pytest.fixture
def mock_search_service():
    """Mock search service"""
    service = MagicMock()
    service.search = AsyncMock(return_value={"results": []})
    return service


@pytest.fixture
def dynamic_pricing_service(mock_synthesis_service, mock_search_service):
    """Create DynamicPricingService instance"""
    return DynamicPricingService(
        cross_oracle_synthesis_service=mock_synthesis_service,
        search_service=mock_search_service
    )


class TestDynamicPricingService:
    """Tests for DynamicPricingService"""

    def test_init(self, dynamic_pricing_service):
        """Test initialization"""
        assert dynamic_pricing_service.synthesis is not None
        assert dynamic_pricing_service.search is not None
        assert dynamic_pricing_service.pricing_stats["total_calculations"] == 0

    def test_extract_costs_from_text(self, dynamic_pricing_service):
        """Test extracting costs from text"""
        text = "The cost is Rp 10 juta for setup and $500 monthly"
        costs = dynamic_pricing_service.extract_costs_from_text(text)
        assert isinstance(costs, list)
        assert len(costs) > 0

    def test_categorize_cost(self, dynamic_pricing_service):
        """Test categorizing cost"""
        text = "notary deed preparation"
        category = dynamic_pricing_service._categorize_cost(text)
        assert category == "Legal"

    def test_categorize_cost_unknown(self, dynamic_pricing_service):
        """Test categorizing unknown cost"""
        text = "random expense item"
        category = dynamic_pricing_service._categorize_cost(text)
        assert category == "Other"

    @pytest.mark.asyncio
    async def test_calculate_pricing(self, dynamic_pricing_service, mock_synthesis_service, mock_search_service):
        """Test calculating pricing"""
        mock_synthesis_result = MagicMock()
        mock_synthesis_result.sources = {"oracle1": {"success": True, "results": [{"text": "Setup cost: Rp 50 juta"}]}}
        mock_synthesis_result.timeline = "4-6 months"
        mock_synthesis_result.oracles_consulted = ["oracle1"]
        mock_synthesis_result.confidence = 0.8
        mock_synthesis_result.scenario_type = "company_setup"
        mock_synthesis_result.risks = []
        mock_synthesis_service.synthesize.return_value = mock_synthesis_result
        mock_search_service.search.return_value = {"results": []}
        result = await dynamic_pricing_service.calculate_pricing("PT PMA setup")
        assert isinstance(result, PricingResult)
        assert result.scenario == "PT PMA setup"

