"""
Integration Tests for DynamicPricingService
Tests dynamic pricing calculation with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestDynamicPricingServiceIntegration:
    """Comprehensive integration tests for DynamicPricingService"""

    @pytest_asyncio.fixture
    async def mock_cross_oracle_synthesis(self):
        """Create mock CrossOracleSynthesisService"""
        mock_synthesis = MagicMock()

        # Mock synthesize method
        mock_synthesis.synthesize = AsyncMock(
            return_value=MagicMock(
                sources={
                    "legal_architect": {
                        "success": True,
                        "results": [
                            {
                                "text": "Notary deed costs Rp 5 juta. Incorporation fee is 10 million IDR."
                            }
                        ],
                    },
                    "tax_genius": {
                        "success": True,
                        "results": [
                            {
                                "text": "NPWP registration: Rp 2.5 juta. PKP registration costs $100 USD."
                            }
                        ],
                    },
                    "visa_oracle": {
                        "success": True,
                        "results": [
                            {
                                "text": "KITAS visa costs Rp 15 juta per person. Annual renewal is Rp 3 juta."
                            }
                        ],
                    },
                },
                oracles_consulted=["legal_architect", "tax_genius", "visa_oracle"],
                timeline="4-6 months",
                scenario_type="business_setup",
                confidence=0.85,
                risks=["Exchange rate fluctuations", "Regulatory changes"],
            )
        )

        return mock_synthesis

    @pytest_asyncio.fixture
    async def mock_search_service(self):
        """Create mock SearchService"""
        mock_search = MagicMock()

        # Mock search method
        mock_search.search = AsyncMock(
            return_value={
                "results": [
                    {
                        "text": "Bali Zero service fee: Rp 25 juta for full setup package. Annual consultation: Rp 5 juta."
                    }
                ]
            }
        )

        return mock_search

    @pytest_asyncio.fixture
    async def pricing_service(self, mock_cross_oracle_synthesis, mock_search_service):
        """Create DynamicPricingService instance"""
        from services.dynamic_pricing_service import DynamicPricingService

        service = DynamicPricingService(
            cross_oracle_synthesis_service=mock_cross_oracle_synthesis,
            search_service=mock_search_service,
        )
        return service

    @pytest.mark.asyncio
    async def test_initialization(self, pricing_service):
        """Test service initialization"""
        assert pricing_service is not None
        assert pricing_service.synthesis is not None
        assert pricing_service.search is not None
        assert pricing_service.pricing_stats["total_calculations"] == 0
        assert pricing_service.pricing_stats["avg_total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_costs_from_text_idr_juta(self, pricing_service):
        """Test extracting costs in IDR juta format"""
        text = "Notary deed costs Rp 5 juta. Legal fee is 10 juta IDR."
        costs = pricing_service.extract_costs_from_text(text, "legal_architect")

        assert len(costs) >= 2
        assert any(c.amount == 5_000_000 for c in costs)
        assert any(c.amount == 10_000_000 for c in costs)
        assert all(c.currency == "IDR" for c in costs)

    @pytest.mark.asyncio
    async def test_extract_costs_from_text_idr_ribu(self, pricing_service):
        """Test extracting costs in IDR ribu format"""
        text = "Small fee: Rp 500 ribu. Another cost is 250 ribu IDR."
        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        assert len(costs) >= 2
        assert any(c.amount == 500_000 for c in costs)
        assert any(c.amount == 250_000 for c in costs)

    @pytest.mark.asyncio
    async def test_extract_costs_from_text_usd(self, pricing_service):
        """Test extracting costs in USD format"""
        text = "Service fee: $100 USD. Another cost is $250."
        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        assert len(costs) >= 2
        # USD should be converted to IDR (100 * 15000 = 1,500,000)
        assert any(1_400_000 <= c.amount <= 1_600_000 for c in costs)
        assert any(3_500_000 <= c.amount <= 3_800_000 for c in costs)

    @pytest.mark.asyncio
    async def test_extract_costs_from_text_recurring(self, pricing_service):
        """Test extracting recurring costs"""
        text = "Annual renewal fee: Rp 3 juta per year. Monthly maintenance: Rp 500 ribu monthly."
        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        recurring_costs = [c for c in costs if c.is_recurring]
        assert len(recurring_costs) >= 1

    @pytest.mark.asyncio
    async def test_extract_costs_from_text_no_costs(self, pricing_service):
        """Test extracting costs from text with no cost information"""
        text = "This is just some text without any pricing information."
        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        assert len(costs) == 0

    @pytest.mark.asyncio
    async def test_categorize_cost_legal(self, pricing_service):
        """Test cost categorization for legal costs"""
        category = pricing_service._categorize_cost("Notary deed and incorporation")
        assert category == "Legal"

    @pytest.mark.asyncio
    async def test_categorize_cost_visa(self, pricing_service):
        """Test cost categorization for visa costs"""
        category = pricing_service._categorize_cost("KITAS visa and work permit")
        assert category == "Visa"

    @pytest.mark.asyncio
    async def test_categorize_cost_tax(self, pricing_service):
        """Test cost categorization for tax costs"""
        category = pricing_service._categorize_cost("NPWP and PKP registration")
        assert category == "Tax"

    @pytest.mark.asyncio
    async def test_categorize_cost_other(self, pricing_service):
        """Test cost categorization for unknown costs"""
        category = pricing_service._categorize_cost("Some random cost")
        assert category == "Other"

    @pytest.mark.asyncio
    async def test_calculate_pricing_success(self, pricing_service):
        """Test calculating pricing for a scenario"""
        scenario = "PT PMA Restaurant in Seminyak, 3 foreign directors"

        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        assert result is not None
        assert result.scenario == scenario
        assert result.total_setup_cost > 0
        assert result.currency == "IDR"
        assert len(result.cost_items) > 0
        assert len(result.breakdown_by_category) > 0
        assert result.timeline_estimate is not None
        assert len(result.key_assumptions) > 0
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_pricing_with_no_results(self, pricing_service):
        """Test calculating pricing when no Oracle results are available"""
        # Mock empty synthesis result
        pricing_service.synthesis.synthesize = AsyncMock(
            return_value=MagicMock(
                sources={},
                oracles_consulted=[],
                timeline="Unknown",
                scenario_type="unknown",
                confidence=0.0,
                risks=[],
            )
        )
        pricing_service.search.search = AsyncMock(return_value={"results": []})

        scenario = "Unknown scenario"
        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        assert result is not None
        assert result.total_setup_cost == 0
        assert result.total_recurring_cost == 0
        assert len(result.cost_items) == 0

    @pytest.mark.asyncio
    async def test_calculate_pricing_updates_stats(self, pricing_service):
        """Test that calculate_pricing updates statistics"""
        initial_calculations = pricing_service.pricing_stats["total_calculations"]

        scenario = "Test scenario"
        await pricing_service.calculate_pricing(scenario, user_level=3)

        assert pricing_service.pricing_stats["total_calculations"] == initial_calculations + 1
        assert pricing_service.pricing_stats["avg_total_cost"] > 0

    @pytest.mark.asyncio
    async def test_format_pricing_report_text(self, pricing_service):
        """Test formatting pricing report as text"""
        scenario = "Test scenario"
        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        report = pricing_service.format_pricing_report(result, format="text")

        assert report is not None
        assert "DYNAMIC PRICING REPORT" in report
        assert scenario in report
        assert "TOTAL INVESTMENT" in report
        assert "BREAKDOWN BY CATEGORY" in report

    @pytest.mark.asyncio
    async def test_format_pricing_report_markdown(self, pricing_service):
        """Test formatting pricing report as markdown"""
        scenario = "Test scenario"
        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        report = pricing_service.format_pricing_report(result, format="markdown")

        assert report is not None
        assert "DYNAMIC PRICING REPORT" in report

    @pytest.mark.asyncio
    async def test_format_pricing_report_default(self, pricing_service):
        """Test formatting pricing report with default format"""
        scenario = "Test scenario"
        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        report = pricing_service.format_pricing_report(result)

        assert report is not None
        assert "DYNAMIC PRICING REPORT" in report

    @pytest.mark.asyncio
    async def test_format_text_report_with_recurring_costs(self, pricing_service):
        """Test text report formatting with recurring costs"""
        # Create a result with recurring costs
        from services.dynamic_pricing_service import CostItem, PricingResult

        result = PricingResult(
            scenario="Test",
            total_setup_cost=10_000_000,
            total_recurring_cost=2_000_000,
            currency="IDR",
            cost_items=[
                CostItem(
                    category="Legal",
                    description="Annual renewal",
                    amount=2_000_000,
                    is_recurring=True,
                )
            ],
            timeline_estimate="1 year",
            breakdown_by_category={"Legal": 2_000_000},
            key_assumptions=["Test assumption"],
            confidence=0.8,
        )

        report = pricing_service._format_text_report(result)

        assert "Recurring Costs (Annual)" in report
        assert "[RECURRING]" in report

    @pytest.mark.asyncio
    async def test_format_text_report_with_zero_setup_cost(self, pricing_service):
        """Test text report formatting with zero setup cost"""
        from services.dynamic_pricing_service import PricingResult

        result = PricingResult(
            scenario="Test",
            total_setup_cost=0,
            total_recurring_cost=0,
            currency="IDR",
            cost_items=[],
            timeline_estimate="Unknown",
            breakdown_by_category={},
            key_assumptions=[],
            confidence=0.0,
        )

        report = pricing_service._format_text_report(result)

        assert "Rp 0" in report or "0" in report

    @pytest.mark.asyncio
    async def test_get_pricing_stats(self, pricing_service):
        """Test getting pricing statistics"""
        # Calculate some pricing first
        await pricing_service.calculate_pricing("Scenario 1", user_level=3)
        await pricing_service.calculate_pricing("Scenario 2", user_level=3)

        stats = pricing_service.get_pricing_stats()

        assert stats is not None
        assert stats["total_calculations"] == 2
        assert "avg_total_cost_formatted" in stats
        assert stats["avg_total_cost"] >= 0

    @pytest.mark.asyncio
    async def test_extract_costs_invalid_format(self, pricing_service):
        """Test extracting costs from invalid format (should handle gracefully)"""
        text = "Cost: invalid123format. Another: also invalid."
        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        # Should not crash, may return empty list or partial results
        assert isinstance(costs, list)

    @pytest.mark.asyncio
    async def test_calculate_pricing_with_failed_oracle(self, pricing_service):
        """Test calculating pricing when some Oracles fail"""
        # Mock synthesis with some failed Oracles
        pricing_service.synthesis.synthesize = AsyncMock(
            return_value=MagicMock(
                sources={
                    "legal_architect": {"success": False, "results": []},
                    "tax_genius": {
                        "success": True,
                        "results": [{"text": "NPWP costs Rp 2.5 juta."}],
                    },
                },
                oracles_consulted=["tax_genius"],
                timeline="2-3 months",
                scenario_type="tax_setup",
                confidence=0.7,
                risks=[],
            )
        )

        scenario = "Tax registration only"
        result = await pricing_service.calculate_pricing(scenario, user_level=3)

        assert result is not None
        assert result.total_setup_cost > 0
        # Should only have costs from successful Oracle
        assert len(result.cost_items) > 0

    @pytest.mark.asyncio
    async def test_extract_costs_multiple_formats(self, pricing_service):
        """Test extracting costs with multiple currency formats in same text"""
        text = """
        Setup costs: Rp 10 juta.
        Service fee: $500 USD.
        Monthly fee: Rp 1 juta per month.
        Annual renewal: 2 million IDR.
        """

        costs = pricing_service.extract_costs_from_text(text, "test_oracle")

        assert len(costs) >= 4
        # Check that different formats are extracted
        amounts = [c.amount for c in costs]
        assert any(amount >= 10_000_000 for amount in amounts)  # 10 juta
        assert any(amount >= 1_000_000 for amount in amounts)  # 1 juta or 2 million
