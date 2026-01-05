"""
Unit tests for SpecializedServiceRouter
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.specialized_service_router import SpecializedServiceRouter


@pytest.fixture
def mock_autonomous_research():
    """Mock autonomous research service"""
    service = AsyncMock()
    service.research = AsyncMock(
        return_value=MagicMock(
            final_answer="Research result",
            total_steps=3,
            collections_explored=["collection1"],
            confidence=0.9,
            sources_consulted=5,
            duration_ms=1000,
        )
    )
    return service


@pytest.fixture
def mock_cross_oracle():
    """Mock cross-oracle synthesis service"""
    service = AsyncMock()
    service.synthesize = AsyncMock(
        return_value=MagicMock(
            synthesis="Synthesis result",
            scenario_type="business_setup",
            oracles_consulted=["oracle1"],
            confidence=0.9,
            timeline="6 months",
            investment="$10000",
            key_requirements=["req1"],
            risks=["risk1"],
        )
    )
    return service


@pytest.fixture
def mock_client_journey():
    """Mock client journey orchestrator"""
    service = MagicMock()
    journey = MagicMock()
    journey.journey_id = "journey-123"
    journey.title = "PT PMA Setup"
    journey.status = MagicMock(value="in_progress")
    step = MagicMock()
    step.title = "Step 1"
    step.description = "Description"
    step.required_documents = ["doc1", "doc2"]
    journey.steps = [step]
    service.create_journey = MagicMock(return_value=journey)
    return service


@pytest.fixture
def router(mock_autonomous_research, mock_cross_oracle, mock_client_journey):
    """Create router with mocked services"""
    return SpecializedServiceRouter(
        autonomous_research_service=mock_autonomous_research,
        cross_oracle_synthesis_service=mock_cross_oracle,
        client_journey_orchestrator=mock_client_journey,
    )


@pytest.fixture
def router_no_services():
    """Create router without services"""
    return SpecializedServiceRouter()


class TestSpecializedServiceRouter:
    """Tests for SpecializedServiceRouter"""

    def test_init(self):
        """Test initialization"""
        router = SpecializedServiceRouter()
        assert router.autonomous_research is None
        assert router.cross_oracle is None
        assert router.client_journey is None

    def test_init_with_services(self, router):
        """Test initialization with services"""
        assert router.autonomous_research is not None
        assert router.cross_oracle is not None
        assert router.client_journey is not None

    def test_detect_autonomous_research_no_service(self, router_no_services):
        """Test detecting autonomous research without service"""
        result = router_no_services.detect_autonomous_research("test", "business_complex")
        assert result is False

    def test_detect_autonomous_research_wrong_category(self, router):
        """Test detecting autonomous research with wrong category"""
        result = router.detect_autonomous_research("test", "greeting")
        assert result is False

    def test_detect_autonomous_research_with_ambiguous(self, router):
        """Test detecting autonomous research with ambiguous keywords"""
        result = router.detect_autonomous_research("crypto blockchain", "business_complex")
        assert result is True

    def test_detect_autonomous_research_long_query(self, router):
        """Test detecting autonomous research with long query"""
        long_query = "how to " + "word " * 20
        result = router.detect_autonomous_research(long_query, "business_complex")
        assert result is True

    def test_detect_autonomous_research_no_match(self, router):
        """Test detecting autonomous research with no match"""
        result = router.detect_autonomous_research("simple query", "business_complex")
        assert result is False

    @pytest.mark.asyncio
    async def test_route_autonomous_research_no_service(self, router_no_services):
        """Test routing autonomous research without service"""
        result = await router_no_services.route_autonomous_research("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_autonomous_research_success(self, router):
        """Test routing autonomous research successfully"""
        result = await router.route_autonomous_research("crypto query", user_level=3)
        assert result is not None
        assert result["category"] == "autonomous_research"
        assert result["response"] == "Research result"

    @pytest.mark.asyncio
    async def test_route_autonomous_research_error(self, router):
        """Test routing autonomous research with error"""
        router.autonomous_research.research.side_effect = Exception("Error")
        result = await router.route_autonomous_research("test")
        assert result is None

    def test_detect_cross_oracle_no_service(self, router_no_services):
        """Test detecting cross-oracle without service"""
        result = router_no_services.detect_cross_oracle("test", "business_complex")
        assert result is False

    def test_detect_cross_oracle_wrong_category(self, router):
        """Test detecting cross-oracle with wrong category"""
        result = router.detect_cross_oracle("test", "greeting")
        assert result is False

    def test_detect_cross_oracle_business_setup(self, router):
        """Test detecting cross-oracle with business setup keywords"""
        result = router.detect_cross_oracle("open restaurant complete", "business_complex")
        assert result is True

    def test_detect_cross_oracle_long_query(self, router):
        """Test detecting cross-oracle with long query"""
        long_query = "open business " + "word " * 10
        result = router.detect_cross_oracle(long_query, "business_complex")
        assert result is True

    def test_detect_cross_oracle_no_match(self, router):
        """Test detecting cross-oracle with no match"""
        result = router.detect_cross_oracle("simple query", "business_complex")
        assert result is False

    @pytest.mark.asyncio
    async def test_route_cross_oracle_no_service(self, router_no_services):
        """Test routing cross-oracle without service"""
        result = await router_no_services.route_cross_oracle("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_cross_oracle_success(self, router):
        """Test routing cross-oracle successfully"""
        result = await router.route_cross_oracle("open restaurant", user_level=3)
        assert result is not None
        assert result["category"] == "cross_oracle_synthesis"

    @pytest.mark.asyncio
    async def test_route_cross_oracle_error(self, router):
        """Test routing cross-oracle with error"""
        router.cross_oracle.synthesize.side_effect = Exception("Error")
        result = await router.route_cross_oracle("test")
        assert result is None

    def test_detect_client_journey_no_service(self, router_no_services):
        """Test detecting client journey without service"""
        result = router_no_services.detect_client_journey("test", "business_complex")
        assert result is False

    def test_detect_client_journey_with_keywords(self, router):
        """Test detecting client journey with keywords"""
        result = router.detect_client_journey("start process pt pma", "business_complex")
        assert result is True

    def test_detect_client_journey_no_match(self, router):
        """Test detecting client journey with no match"""
        result = router.detect_client_journey("simple query", "business_complex")
        assert result is False

    @pytest.mark.asyncio
    async def test_route_client_journey_no_service(self, router_no_services):
        """Test routing client journey without service"""
        result = await router_no_services.route_client_journey("test", "user123")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_client_journey_pt_pma(self, router):
        """Test routing client journey for PT PMA"""
        result = await router.route_client_journey("start process pt pma", "user123")
        assert result is not None
        assert result["category"] == "client_journey"

    @pytest.mark.asyncio
    async def test_route_client_journey_kitas(self, router):
        """Test routing client journey for KITAS"""
        result = await router.route_client_journey("start process kitas", "user123")
        assert result is not None

    @pytest.mark.asyncio
    async def test_route_client_journey_property(self, router):
        """Test routing client journey for property"""
        result = await router.route_client_journey("start process property", "user123")
        assert result is not None

    @pytest.mark.asyncio
    async def test_route_client_journey_unknown_type(self, router):
        """Test routing client journey with unknown type"""
        result = await router.route_client_journey("start process unknown", "user123")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_client_journey_error(self, router):
        """Test routing client journey with error"""
        router.client_journey.create_journey.side_effect = Exception("Error")
        result = await router.route_client_journey("start process pt pma", "user123")
        assert result is None

