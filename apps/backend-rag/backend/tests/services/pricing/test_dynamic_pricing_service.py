"""Tests for DynamicPricingService — cost extraction, categorization, and pricing stats."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.pricing.dynamic_pricing_service import (
    CostItem,
    DynamicPricingService,
    PricingResult,
)


@pytest.fixture
def service() -> DynamicPricingService:
    synthesis = AsyncMock()
    search = AsyncMock()
    return DynamicPricingService(
        cross_oracle_synthesis_service=synthesis,
        search_service=search,
    )


class TestExtractCostsFromText:
    def test_extracts_idr_rp_format(self, service: DynamicPricingService) -> None:
        text = "Notary fee: Rp 5.000.000 for incorporation"
        costs = service.extract_costs_from_text(text, "test_oracle")
        assert len(costs) >= 1
        assert any(c.amount == 5_000_000 for c in costs)

    def test_extracts_idr_suffix_format(self, service: DynamicPricingService) -> None:
        text = "Registration: 3.000.000 IDR"
        costs = service.extract_costs_from_text(text, "test")
        assert len(costs) >= 1
        assert any(c.amount == 3_000_000 for c in costs)

    def test_extracts_usd_converts_to_idr(self, service: DynamicPricingService) -> None:
        text = "Investor capital requirement: $1000"
        costs = service.extract_costs_from_text(text, "test")
        assert len(costs) >= 1
        # USD * 15_000
        assert any(c.amount == 1000 * 15_000 for c in costs)

    def test_extracts_juta_multiplier(self, service: DynamicPricingService) -> None:
        text = "Biaya: Rp 20 juta untuk PT PMA"
        costs = service.extract_costs_from_text(text, "test")
        assert len(costs) >= 1
        assert any(c.amount == 20_000_000 for c in costs)

    def test_empty_text_returns_empty(self, service: DynamicPricingService) -> None:
        costs = service.extract_costs_from_text("", "test")
        assert costs == []

    def test_no_costs_in_text(self, service: DynamicPricingService) -> None:
        costs = service.extract_costs_from_text("This is a description without any prices.", "test")
        assert costs == []

    def test_recurring_flag_detected(self, service: DynamicPricingService) -> None:
        text = "Annual tax filing fee: Rp 2.000.000 per year"
        costs = service.extract_costs_from_text(text, "test")
        recurring = [c for c in costs if c.is_recurring]
        assert len(recurring) >= 1

    def test_source_oracle_stored(self, service: DynamicPricingService) -> None:
        text = "Fee: Rp 1.000.000"
        costs = service.extract_costs_from_text(text, "visa_oracle")
        assert all(c.source_oracle == "visa_oracle" for c in costs)


class TestCategorizeCost:
    def test_categorizes_legal(self, service: DynamicPricingService) -> None:
        assert service._categorize_cost("notary deed akta incorporation") == "Legal"

    def test_categorizes_visa(self, service: DynamicPricingService) -> None:
        assert service._categorize_cost("KITAS work permit visa") == "Visa"

    def test_categorizes_tax(self, service: DynamicPricingService) -> None:
        assert service._categorize_cost("NPWP pajak tax registration") == "Tax"

    def test_categorizes_licensing(self, service: DynamicPricingService) -> None:
        assert service._categorize_cost("NIB OSS business license izin") == "Licensing"

    def test_categorizes_unknown_as_other(self, service: DynamicPricingService) -> None:
        assert service._categorize_cost("something unrecognized xyz") == "Other"


class TestCalculatePricing:
    @pytest.mark.asyncio
    async def test_returns_pricing_result(self, service: DynamicPricingService) -> None:
        synthesis_result = MagicMock()
        synthesis_result.sources = {
            "visa_oracle": {
                "success": True,
                "results": [{"text": "KITAS Investor fee: Rp 20.000.000"}],
            }
        }
        synthesis_result.timeline = "3-4 months"
        synthesis_result.risks = []
        synthesis_result.confidence = 0.8
        synthesis_result.oracles_consulted = ["visa_oracle"]
        synthesis_result.scenario_type = "visa"

        service.synthesis.synthesize = AsyncMock(return_value=synthesis_result)
        service.search.search = AsyncMock(return_value={"results": []})

        result = await service.calculate_pricing("KITAS investor Bali")

        assert isinstance(result, PricingResult)
        assert result.currency == "IDR"
        assert result.total_setup_cost >= 0
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_zero_costs_when_no_prices_in_text(self, service: DynamicPricingService) -> None:
        synthesis_result = MagicMock()
        synthesis_result.sources = {
            "legal": {
                "success": True,
                "results": [{"text": "Requirements: passport, photo, application form"}],
            }
        }
        synthesis_result.timeline = None
        synthesis_result.risks = []
        synthesis_result.confidence = 0.5
        synthesis_result.oracles_consulted = ["legal"]
        synthesis_result.scenario_type = "general"

        service.synthesis.synthesize = AsyncMock(return_value=synthesis_result)
        service.search.search = AsyncMock(return_value={"results": []})

        result = await service.calculate_pricing("what documents for KITAS?")

        assert result.total_setup_cost == 0.0
        assert result.total_recurring_cost == 0.0
        assert result.cost_items == []

    @pytest.mark.asyncio
    async def test_stats_updated_after_calculation(self, service: DynamicPricingService) -> None:
        synthesis_result = MagicMock()
        synthesis_result.sources = {}
        synthesis_result.timeline = None
        synthesis_result.risks = []
        synthesis_result.confidence = 0.5
        synthesis_result.oracles_consulted = []
        synthesis_result.scenario_type = "test"

        service.synthesis.synthesize = AsyncMock(return_value=synthesis_result)
        service.search.search = AsyncMock(return_value={"results": []})

        await service.calculate_pricing("test scenario")

        assert service.pricing_stats["total_calculations"] == 1


class TestFormatPricingReport:
    def test_text_format_contains_scenario(self, service: DynamicPricingService) -> None:
        result = PricingResult(
            scenario="PT PMA Restaurant",
            total_setup_cost=20_000_000,
            total_recurring_cost=5_000_000,
            currency="IDR",
            cost_items=[
                CostItem(
                    category="Legal",
                    description="Notary fee",
                    amount=20_000_000,
                    currency="IDR",
                )
            ],
            timeline_estimate="3-4 months",
            breakdown_by_category={"Legal": 20_000_000},
            key_assumptions=["Estimate only"],
            confidence=0.7,
        )
        report = service.format_pricing_report(result, format="text")
        assert "PT PMA Restaurant" in report
        assert "20,000,000" in report

    def test_empty_cost_items(self, service: DynamicPricingService) -> None:
        result = PricingResult(
            scenario="Empty scenario",
            total_setup_cost=0,
            total_recurring_cost=0,
            currency="IDR",
            cost_items=[],
            timeline_estimate="Unknown",
            breakdown_by_category={},
            key_assumptions=[],
            confidence=0.0,
        )
        report = service.format_pricing_report(result)
        assert isinstance(report, str)


class TestGetPricingStats:
    def test_initial_stats(self, service: DynamicPricingService) -> None:
        stats = service.get_pricing_stats()
        assert stats["total_calculations"] == 0
        assert stats["avg_total_cost"] == 0.0
        assert "avg_total_cost_formatted" in stats
