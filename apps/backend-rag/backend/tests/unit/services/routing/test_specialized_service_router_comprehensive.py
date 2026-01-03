"""
Comprehensive tests for SpecializedServiceRouter
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.specialized_service_router import (  # noqa: E402
    SpecializedServiceRouter,
)


@pytest.fixture
def mock_autonomous_research():
    """Mock autonomous research service"""
    service = MagicMock()
    service.research = AsyncMock(return_value=MagicMock(
        final_answer="Research result",
        total_steps=3,
        collections_explored=["visa_oracle", "legal_architect"],
        confidence=0.85,
        sources_consulted=5,
        duration_ms=1500
    ))
    return service


@pytest.fixture
def mock_cross_oracle():
    """Mock cross-oracle synthesis service"""
    service = MagicMock()
    service.synthesize = AsyncMock(return_value=MagicMock(
        synthesis="Synthesis result",
        scenario_type="pt_pma_setup",
        oracles_consulted=["visa_oracle", "tax_genius", "legal_architect"],
        confidence=0.9,
        timeline="3-6 months",
        investment="100M IDR",
        key_requirements=["Passport", "Investment plan"],
        risks=["Regulatory changes"]
    ))
    return service


@pytest.fixture
def mock_client_journey():
    """Mock client journey orchestrator"""
    service = MagicMock()
    journey = MagicMock()
    journey.journey_id = "journey-123"
    journey.title = "PT PMA Setup"
    journey.status = MagicMock(value="in_progress")
    journey.steps = [MagicMock(
        title="Step 1",
        description="First step",
        required_documents=["Passport", "Investment plan"]
    )]
    service.create_journey = MagicMock(return_value=journey)
    return service


@pytest.fixture
def specialized_router(mock_autonomous_research, mock_cross_oracle, mock_client_journey):
    """Create SpecializedServiceRouter instance"""
    return SpecializedServiceRouter(
        autonomous_research_service=mock_autonomous_research,
        cross_oracle_synthesis_service=mock_cross_oracle,
        client_journey_orchestrator=mock_client_journey
    )


@pytest.fixture
def empty_router():
    """Create SpecializedServiceRouter without services"""
    return SpecializedServiceRouter()


class TestSpecializedServiceRouter:
    """Tests for SpecializedServiceRouter"""

    def test_init_with_all_services(self, mock_autonomous_research, mock_cross_oracle, mock_client_journey):
        """Test initialization with all services"""
        router = SpecializedServiceRouter(
            autonomous_research_service=mock_autonomous_research,
            cross_oracle_synthesis_service=mock_cross_oracle,
            client_journey_orchestrator=mock_client_journey
        )
        assert router.autonomous_research == mock_autonomous_research
        assert router.cross_oracle == mock_cross_oracle
        assert router.client_journey == mock_client_journey

    def test_init_without_services(self):
        """Test initialization without services"""
        router = SpecializedServiceRouter()
        assert router.autonomous_research is None
        assert router.cross_oracle is None
        assert router.client_journey is None

    def test_detect_autonomous_research_with_ambiguous_keyword(self, specialized_router):
        """Test detecting autonomous research with ambiguous keyword"""
        result = specialized_router.detect_autonomous_research(
            message="I want to open a crypto business",
            category="business_complex"
        )
        assert result is True

    def test_detect_autonomous_research_with_long_query(self, specialized_router):
        """Test detecting autonomous research with long query"""
        long_query = "how to " + "word " * 20
        result = specialized_router.detect_autonomous_research(
            message=long_query,
            category="business_complex"
        )
        assert result is True

    def test_detect_autonomous_research_without_service(self, empty_router):
        """Test detecting autonomous research without service"""
        result = empty_router.detect_autonomous_research(
            message="crypto business",
            category="business_complex"
        )
        assert result is False

    def test_detect_autonomous_research_wrong_category(self, specialized_router):
        """Test detecting autonomous research with wrong category"""
        result = specialized_router.detect_autonomous_research(
            message="crypto business",
            category="visa"
        )
        assert result is False

    def test_detect_autonomous_research_no_match(self, specialized_router):
        """Test detecting autonomous research with no match"""
        result = specialized_router.detect_autonomous_research(
            message="simple visa question",
            category="business_complex"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_route_autonomous_research_success(self, specialized_router):
        """Test routing to autonomous research successfully"""
        result = await specialized_router.route_autonomous_research(
            query="How to open a crypto business",
            user_level=3
        )
        assert result is not None
        assert result["category"] == "autonomous_research"
        assert result["ai_used"] == "zantara"
        assert "autonomous_research" in result
        assert result["autonomous_research"]["total_steps"] == 3

    @pytest.mark.asyncio
    async def test_route_autonomous_research_without_service(self, empty_router):
        """Test routing to autonomous research without service"""
        result = await empty_router.route_autonomous_research(
            query="crypto business",
            user_level=3
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_route_autonomous_research_error(self, specialized_router, mock_autonomous_research):
        """Test routing to autonomous research with error"""
        mock_autonomous_research.research = AsyncMock(side_effect=Exception("Error"))
        result = await specialized_router.route_autonomous_research(
            query="crypto business",
            user_level=3
        )
        assert result is None

    def test_detect_cross_oracle_with_business_setup(self, specialized_router):
        """Test detecting cross-oracle with business setup keywords"""
        result = specialized_router.detect_cross_oracle(
            message="I want to open a restaurant with complete requirements",
            category="business_complex"
        )
        assert result is True

    def test_detect_cross_oracle_with_comprehensive_indicator(self, specialized_router):
        """Test detecting cross-oracle with comprehensive indicator"""
        result = specialized_router.detect_cross_oracle(
            message="I want to setup a company with everything needed",
            category="business_complex"
        )
        assert result is True

    def test_detect_cross_oracle_with_long_query(self, specialized_router):
        """Test detecting cross-oracle with long query"""
        long_query = "I want to open a restaurant " + "word " * 15
        result = specialized_router.detect_cross_oracle(
            message=long_query,
            category="business_complex"
        )
        assert result is True

    def test_detect_cross_oracle_without_service(self, empty_router):
        """Test detecting cross-oracle without service"""
        result = empty_router.detect_cross_oracle(
            message="open restaurant",
            category="business_complex"
        )
        assert result is False

    def test_detect_cross_oracle_wrong_category(self, specialized_router):
        """Test detecting cross-oracle with wrong category"""
        result = specialized_router.detect_cross_oracle(
            message="open restaurant",
            category="visa"
        )
        assert result is False

    def test_detect_cross_oracle_no_match(self, specialized_router):
        """Test detecting cross-oracle with no match"""
        result = specialized_router.detect_cross_oracle(
            message="simple question",
            category="business_complex"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_route_cross_oracle_success(self, specialized_router):
        """Test routing to cross-oracle successfully"""
        result = await specialized_router.route_cross_oracle(
            query="I want to open a restaurant with complete requirements",
            user_level=3,
            use_cache=True
        )
        assert result is not None
        assert result["category"] == "cross_oracle_synthesis"
        assert result["ai_used"] == "zantara"
        assert "cross_oracle_synthesis" in result
        assert result["cross_oracle_synthesis"]["scenario_type"] == "pt_pma_setup"

    @pytest.mark.asyncio
    async def test_route_cross_oracle_without_service(self, empty_router):
        """Test routing to cross-oracle without service"""
        result = await empty_router.route_cross_oracle(
            query="open restaurant",
            user_level=3
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_route_cross_oracle_error(self, specialized_router, mock_cross_oracle):
        """Test routing to cross-oracle with error"""
        mock_cross_oracle.synthesize = AsyncMock(side_effect=Exception("Error"))
        result = await specialized_router.route_cross_oracle(
            query="open restaurant",
            user_level=3
        )
        assert result is None

    def test_detect_client_journey_with_keywords(self, specialized_router):
        """Test detecting client journey with keywords"""
        result = specialized_router.detect_client_journey(
            message="I want to start process for PT PMA",
            category="business_complex"
        )
        assert result is True

    def test_detect_client_journey_with_kitas(self, specialized_router):
        """Test detecting client journey with KITAS"""
        result = specialized_router.detect_client_journey(
            message="I want to begin application for KITAS",
            category="business_complex"
        )
        assert result is True

    def test_detect_client_journey_without_service(self, empty_router):
        """Test detecting client journey without service"""
        result = empty_router.detect_client_journey(
            message="start process PT PMA",
            category="business_complex"
        )
        assert result is False

    def test_detect_client_journey_no_match(self, specialized_router):
        """Test detecting client journey with no match"""
        result = specialized_router.detect_client_journey(
            message="simple question",
            category="business_complex"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_route_client_journey_pt_pma(self, specialized_router):
        """Test routing to client journey for PT PMA"""
        result = await specialized_router.route_client_journey(
            query="I want to start process for PT PMA",
            user_id="user-123"
        )
        assert result is not None
        assert result["category"] == "client_journey"
        assert result["ai_used"] == "zantara"
        assert "client_journey" in result
        assert result["client_journey"]["journey_id"] == "journey-123"

    @pytest.mark.asyncio
    async def test_route_client_journey_kitas(self, specialized_router):
        """Test routing to client journey for KITAS"""
        result = await specialized_router.route_client_journey(
            query="I want to apply for KITAS",
            user_id="user-123"
        )
        assert result is not None
        assert result["category"] == "client_journey"

    @pytest.mark.asyncio
    async def test_route_client_journey_property(self, specialized_router):
        """Test routing to client journey for property"""
        result = await specialized_router.route_client_journey(
            query="I want to start process for property purchase",
            user_id="user-123"
        )
        assert result is not None
        assert result["category"] == "client_journey"

    @pytest.mark.asyncio
    async def test_route_client_journey_without_service(self, empty_router):
        """Test routing to client journey without service"""
        result = await empty_router.route_client_journey(
            query="start process PT PMA",
            user_id="user-123"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_route_client_journey_unknown_type(self, specialized_router):
        """Test routing to client journey with unknown type"""
        result = await specialized_router.route_client_journey(
            query="I want to start something",
            user_id="user-123"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_route_client_journey_error(self, specialized_router, mock_client_journey):
        """Test routing to client journey with error"""
        mock_client_journey.create_journey = MagicMock(side_effect=Exception("Error"))
        result = await specialized_router.route_client_journey(
            query="start process PT PMA",
            user_id="user-123"
        )
        assert result is None




