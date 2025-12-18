"""
Unit tests for Dynamic Pricing Service
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.dynamic_pricing_service import (
    CostItem,
    DynamicPricingService,
    PricingResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_synthesis_service():
    """Mock CrossOracleSynthesisService"""
    mock = MagicMock()
    mock.synthesize = AsyncMock()
    return mock


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    mock = MagicMock()
    mock.search = AsyncMock()
    return mock


@pytest.fixture
def pricing_service(mock_synthesis_service, mock_search_service):
    """Create DynamicPricingService instance"""
    return DynamicPricingService(mock_synthesis_service, mock_search_service)


# ============================================================================
# Tests for CostItem and PricingResult
# ============================================================================


def test_cost_item_creation():
    """Test CostItem dataclass creation"""
    cost = CostItem(
        category="Legal",
        description="Notary fee",
        amount=5000000.0,
        currency="IDR",
        source_oracle="legal_architect",
        is_recurring=False,
    )
    assert cost.category == "Legal"
    assert cost.amount == 5000000.0
    assert cost.currency == "IDR"
    assert cost.is_recurring is False


def test_pricing_result_creation():
    """Test PricingResult dataclass creation"""
    cost_items = [
        CostItem(category="Legal", description="Test", amount=1000000.0),
    ]
    result = PricingResult(
        scenario="Test scenario",
        total_setup_cost=1000000.0,
        total_recurring_cost=0.0,
        currency="IDR",
        cost_items=cost_items,
        timeline_estimate="1-2 months",
        breakdown_by_category={"Legal": 1000000.0},
        key_assumptions=["Test assumption"],
        confidence=0.8,
    )
    assert result.scenario == "Test scenario"
    assert result.total_setup_cost == 1000000.0
    assert len(result.cost_items) == 1


# ============================================================================
# Tests for DynamicPricingService.__init__
# ============================================================================


def test_init(pricing_service, mock_synthesis_service, mock_search_service):
    """Test DynamicPricingService initialization"""
    assert pricing_service.synthesis is mock_synthesis_service
    assert pricing_service.search is mock_search_service
    assert pricing_service.pricing_stats["total_calculations"] == 0
    assert pricing_service.pricing_stats["avg_total_cost"] == 0.0


# ============================================================================
# Tests for extract_costs_from_text
# ============================================================================


def test_extract_costs_from_text_idr_juta(pricing_service):
    """Test extracting costs in IDR juta format"""
    text = "Notary fee is Rp 5 juta for PT PMA setup"
    costs = pricing_service.extract_costs_from_text(text, "legal_architect")

    assert len(costs) > 0
    assert any(c.amount == 5000000.0 for c in costs)


def test_extract_costs_from_text_idr_ribu(pricing_service):
    """Test extracting costs in IDR ribu format"""
    text = "Service fee is Rp 500 ribu per month"
    costs = pricing_service.extract_costs_from_text(text, "bali_zero_pricing")

    assert len(costs) > 0
    assert any(c.amount == 500000.0 for c in costs)


def test_extract_costs_from_text_usd(pricing_service):
    """Test extracting costs in USD format"""
    text = "Visa cost is $500 USD per person"
    costs = pricing_service.extract_costs_from_text(text, "visa_oracle")

    assert len(costs) > 0
    # Should be converted to IDR (500 * 15000)
    assert any(c.amount == 7500000.0 for c in costs)


def test_extract_costs_from_text_recurring(pricing_service):
    """Test extracting recurring costs"""
    text = "Annual tax registration fee is Rp 1 juta per year"
    costs = pricing_service.extract_costs_from_text(text, "tax_genius")

    assert len(costs) > 0
    recurring_costs = [c for c in costs if c.is_recurring]
    assert len(recurring_costs) > 0


def test_extract_costs_from_text_no_costs(pricing_service):
    """Test extracting costs from text with no cost information"""
    text = "This is just general information about the process"
    costs = pricing_service.extract_costs_from_text(text, "test_oracle")

    assert len(costs) == 0


def test_extract_costs_from_text_multiple_costs(pricing_service):
    """Test extracting multiple costs from text"""
    text = "Notary fee: Rp 5 juta. NIB fee: Rp 2 juta. Tax registration: Rp 1 juta"
    costs = pricing_service.extract_costs_from_text(text, "test_oracle")

    assert len(costs) >= 3


# ============================================================================
# Tests for _categorize_cost
# ============================================================================


def test_categorize_cost_legal(pricing_service):
    """Test categorizing legal costs"""
    category = pricing_service._categorize_cost("Notary deed preparation for PT PMA")
    assert category == "Legal"


def test_categorize_cost_licensing(pricing_service):
    """Test categorizing licensing costs"""
    category = pricing_service._categorize_cost("NIB application fee")
    assert category == "Licensing"


def test_categorize_cost_tax(pricing_service):
    """Test categorizing tax costs"""
    category = pricing_service._categorize_cost("NPWP registration cost")
    assert category == "Tax"


def test_categorize_cost_visa(pricing_service):
    """Test categorizing visa costs"""
    category = pricing_service._categorize_cost("KITAS application fee")
    assert category == "Visa"


def test_categorize_cost_property(pricing_service):
    """Test categorizing property costs"""
    category = pricing_service._categorize_cost("Office rent in Seminyak")
    assert category == "Property"


def test_categorize_cost_service_fees(pricing_service):
    """Test categorizing service fees"""
    category = pricing_service._categorize_cost("Bali Zero consultation fee")
    assert category == "Service_Fees"


def test_categorize_cost_other(pricing_service):
    """Test categorizing unknown costs"""
    category = pricing_service._categorize_cost("Miscellaneous expenses")
    assert category == "Other"


# ============================================================================
# Tests for calculate_pricing
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_pricing_success(
    pricing_service, mock_synthesis_service, mock_search_service
):
    """Test successful pricing calculation"""
    # Mock synthesis result
    mock_synthesis_result = MagicMock()
    mock_synthesis_result.sources = {
        "legal_architect": {
            "success": True,
            "results": [{"text": "Notary fee is Rp 5 juta for PT PMA"}],
        }
    }
    mock_synthesis_result.timeline = "4-6 months"
    mock_synthesis_result.oracles_consulted = ["legal_architect"]
    mock_synthesis_result.confidence = 0.8
    mock_synthesis_result.scenario_type = "company_setup"
    mock_synthesis_result.risks = []

    mock_synthesis_service.synthesize.return_value = mock_synthesis_result

    # Mock search result
    mock_search_service.search.return_value = {"results": [{"text": "Service fee is Rp 2 juta"}]}

    result = await pricing_service.calculate_pricing("PT PMA Restaurant setup", user_level=3)

    assert isinstance(result, PricingResult)
    assert result.scenario == "PT PMA Restaurant setup"
    assert result.total_setup_cost > 0
    assert result.currency == "IDR"
    assert len(result.cost_items) > 0
    assert result.timeline_estimate == "4-6 months"
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_calculate_pricing_no_results(
    pricing_service, mock_synthesis_service, mock_search_service
):
    """Test pricing calculation with no cost results"""
    mock_synthesis_result = MagicMock()
    mock_synthesis_result.sources = {}
    mock_synthesis_result.timeline = "Unknown"
    mock_synthesis_result.oracles_consulted = []
    mock_synthesis_result.confidence = 0.5
    mock_synthesis_result.scenario_type = "unknown"
    mock_synthesis_result.risks = []

    mock_synthesis_service.synthesize.return_value = mock_synthesis_result
    mock_search_service.search.return_value = {"results": []}

    result = await pricing_service.calculate_pricing("Unknown scenario", user_level=3)

    assert result.total_setup_cost == 0.0
    assert len(result.cost_items) == 0


@pytest.mark.asyncio
async def test_calculate_pricing_with_recurring_costs(
    pricing_service, mock_synthesis_service, mock_search_service
):
    """Test pricing calculation with recurring costs"""
    mock_synthesis_result = MagicMock()
    mock_synthesis_result.sources = {
        "tax_genius": {
            "success": True,
            "results": [{"text": "Annual tax fee is Rp 1 juta per year"}],
        }
    }
    mock_synthesis_result.timeline = "1 month"
    mock_synthesis_result.oracles_consulted = ["tax_genius"]
    mock_synthesis_result.confidence = 0.7
    mock_synthesis_result.scenario_type = "tax_registration"
    mock_synthesis_result.risks = []

    mock_synthesis_service.synthesize.return_value = mock_synthesis_result
    mock_search_service.search.return_value = {"results": []}

    result = await pricing_service.calculate_pricing("Tax registration", user_level=3)

    assert result.total_recurring_cost > 0
    recurring_items = [c for c in result.cost_items if c.is_recurring]
    assert len(recurring_items) > 0


@pytest.mark.asyncio
async def test_calculate_pricing_updates_stats(
    pricing_service, mock_synthesis_service, mock_search_service
):
    """Test that calculate_pricing updates statistics"""
    initial_calculations = pricing_service.pricing_stats["total_calculations"]

    mock_synthesis_result = MagicMock()
    mock_synthesis_result.sources = {
        "test_oracle": {"success": True, "results": [{"text": "Cost is Rp 1 juta"}]}
    }
    mock_synthesis_result.timeline = "1 month"
    mock_synthesis_result.oracles_consulted = ["test_oracle"]
    mock_synthesis_result.confidence = 0.8
    mock_synthesis_result.scenario_type = "test"
    mock_synthesis_result.risks = []

    mock_synthesis_service.synthesize.return_value = mock_synthesis_result
    mock_search_service.search.return_value = {"results": []}

    await pricing_service.calculate_pricing("Test scenario", user_level=3)

    assert pricing_service.pricing_stats["total_calculations"] == initial_calculations + 1
    assert pricing_service.pricing_stats["avg_total_cost"] > 0


# ============================================================================
# Tests for format_pricing_report
# ============================================================================


def test_format_pricing_report_text(pricing_service):
    """Test formatting pricing report as text"""
    cost_items = [
        CostItem(category="Legal", description="Notary fee", amount=5000000.0),
        CostItem(category="Tax", description="NPWP registration", amount=1000000.0),
    ]
    result = PricingResult(
        scenario="PT PMA Setup",
        total_setup_cost=6000000.0,
        total_recurring_cost=0.0,
        currency="IDR",
        cost_items=cost_items,
        timeline_estimate="2-3 months",
        breakdown_by_category={"Legal": 5000000.0, "Tax": 1000000.0},
        key_assumptions=["Test assumption"],
        confidence=0.8,
    )

    report = pricing_service.format_pricing_report(result, format="text")

    assert "DYNAMIC PRICING REPORT" in report
    assert "PT PMA Setup" in report
    assert "Rp 6,000,000" in report
    assert "Legal" in report
    assert "Tax" in report


def test_format_pricing_report_markdown(pricing_service):
    """Test formatting pricing report as markdown"""
    cost_items = [
        CostItem(category="Legal", description="Notary fee", amount=5000000.0),
    ]
    result = PricingResult(
        scenario="Test",
        total_setup_cost=5000000.0,
        total_recurring_cost=0.0,
        currency="IDR",
        cost_items=cost_items,
        timeline_estimate="1 month",
        breakdown_by_category={"Legal": 5000000.0},
        key_assumptions=[],
        confidence=0.8,
    )

    report = pricing_service.format_pricing_report(result, format="markdown")

    assert isinstance(report, str)
    assert len(report) > 0


# ============================================================================
# Tests for get_pricing_stats
# ============================================================================


def test_get_pricing_stats(pricing_service):
    """Test getting pricing statistics"""
    stats = pricing_service.get_pricing_stats()

    assert "total_calculations" in stats
    assert "avg_total_cost" in stats
    assert "scenarios_priced" in stats
    assert "avg_total_cost_formatted" in stats
    assert "Rp" in stats["avg_total_cost_formatted"]
