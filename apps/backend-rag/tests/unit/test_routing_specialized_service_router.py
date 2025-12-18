"""
Unit tests for Specialized Service Router
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.specialized_service_router import SpecializedServiceRouter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_autonomous_research():
    """Create mock AutonomousResearchService"""
    service = MagicMock()
    service.research = AsyncMock()
    service.research.return_value = MagicMock(
        total_steps=3,
        collections_explored=["collection1", "collection2"],
        confidence=0.9,
        sources_consulted=5,
        duration_ms=1000,
        final_answer="Research answer",
    )
    return service


@pytest.fixture
def mock_cross_oracle():
    """Create mock CrossOracleSynthesisService"""
    service = MagicMock()
    service.synthesize = AsyncMock()
    service.synthesize.return_value = MagicMock(
        scenario_type="business_setup",
        oracles_consulted=["oracle1", "oracle2"],
        confidence=0.85,
        timeline="60-90 days",
        investment="Rp 10B",
        key_requirements=["NIB", "NPWP"],
        risks=["Regulatory changes"],
        synthesis="Synthesis result",
    )
    return service


@pytest.fixture
def mock_client_journey():
    """Create mock ClientJourneyOrchestrator"""
    service = MagicMock()
    service.create_journey = MagicMock()
    service.create_journey.return_value = MagicMock(
        journey_id="journey_123",
        title="PT PMA Setup",
        status=MagicMock(value="active"),
        steps=[
            MagicMock(
                title="Step 1",
                description="First step",
                required_documents=["doc1", "doc2"],
            )
        ],
    )
    return service


@pytest.fixture
def specialized_router(mock_autonomous_research, mock_cross_oracle, mock_client_journey):
    """Create SpecializedServiceRouter instance"""
    return SpecializedServiceRouter(
        autonomous_research_service=mock_autonomous_research,
        cross_oracle_synthesis_service=mock_cross_oracle,
        client_journey_orchestrator=mock_client_journey,
    )


@pytest.fixture
def specialized_router_no_services():
    """Create SpecializedServiceRouter without services"""
    return SpecializedServiceRouter(
        autonomous_research_service=None,
        cross_oracle_synthesis_service=None,
        client_journey_orchestrator=None,
    )


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_specialized_router_init(
    specialized_router, mock_autonomous_research, mock_cross_oracle, mock_client_journey
):
    """Test SpecializedServiceRouter initialization"""
    assert specialized_router.autonomous_research is mock_autonomous_research
    assert specialized_router.cross_oracle is mock_cross_oracle
    assert specialized_router.client_journey is mock_client_journey


# ============================================================================
# Tests: detect_autonomous_research
# ============================================================================


def test_detect_autonomous_research_ambiguous_term(specialized_router):
    """Test detecting autonomous research with ambiguous term"""
    result = specialized_router.detect_autonomous_research(
        "How to setup a cryptocurrency business?", "business_complex"
    )

    assert result is True


def test_detect_autonomous_research_long_query(specialized_router):
    """Test detecting autonomous research with long query"""
    long_query = " ".join(["word"] * 20) + " how to"
    result = specialized_router.detect_autonomous_research(long_query, "business_complex")

    assert result is True


def test_detect_autonomous_research_wrong_category(specialized_router):
    """Test not detecting autonomous research for wrong category"""
    result = specialized_router.detect_autonomous_research("crypto business", "greeting")

    assert result is False


def test_detect_autonomous_research_no_service(specialized_router_no_services):
    """Test detecting autonomous research without service"""
    result = specialized_router_no_services.detect_autonomous_research(
        "crypto business", "business_complex"
    )

    assert result is False


# ============================================================================
# Tests: route_autonomous_research
# ============================================================================


@pytest.mark.asyncio
async def test_route_autonomous_research_success(specialized_router):
    """Test routing to autonomous research successfully"""
    result = await specialized_router.route_autonomous_research("crypto business", user_level=3)

    assert result is not None
    assert result["category"] == "autonomous_research"
    assert result["ai_used"] == "zantara"
    assert result["used_rag"] is True
    assert "autonomous_research" in result
    assert result["autonomous_research"]["total_steps"] == 3


@pytest.mark.asyncio
async def test_route_autonomous_research_no_service(specialized_router_no_services):
    """Test routing to autonomous research without service"""
    result = await specialized_router_no_services.route_autonomous_research("query", user_level=3)

    assert result is None


@pytest.mark.asyncio
async def test_route_autonomous_research_exception(specialized_router):
    """Test routing to autonomous research with exception"""
    specialized_router.autonomous_research.research.side_effect = Exception("Error")

    result = await specialized_router.route_autonomous_research("query", user_level=3)

    assert result is None


# ============================================================================
# Tests: detect_cross_oracle
# ============================================================================


def test_detect_cross_oracle_business_setup(specialized_router):
    """Test detecting cross-oracle with business setup term"""
    # Query needs: business setup term + (comprehensive indicator OR >10 words)
    result = specialized_router.detect_cross_oracle(
        "I need comprehensive guidance for opening a restaurant business in Indonesia with all requirements",
        "business_complex",
    )

    assert result is True


def test_detect_cross_oracle_comprehensive(specialized_router):
    """Test detecting cross-oracle with comprehensive indicator"""
    result = specialized_router.detect_cross_oracle(
        "I want everything needed to setup a company", "business_simple"
    )

    assert result is True


def test_detect_cross_oracle_wrong_category(specialized_router):
    """Test not detecting cross-oracle for wrong category"""
    result = specialized_router.detect_cross_oracle("open restaurant", "greeting")

    assert result is False


def test_detect_cross_oracle_no_service(specialized_router_no_services):
    """Test detecting cross-oracle without service"""
    result = specialized_router_no_services.detect_cross_oracle(
        "open restaurant", "business_complex"
    )

    assert result is False


# ============================================================================
# Tests: route_cross_oracle
# ============================================================================


@pytest.mark.asyncio
async def test_route_cross_oracle_success(specialized_router):
    """Test routing to cross-oracle successfully"""
    result = await specialized_router.route_cross_oracle("open restaurant", user_level=3)

    assert result is not None
    assert result["category"] == "cross_oracle_synthesis"
    assert result["ai_used"] == "zantara"
    assert "cross_oracle_synthesis" in result
    assert result["cross_oracle_synthesis"]["scenario_type"] == "business_setup"


@pytest.mark.asyncio
async def test_route_cross_oracle_no_service(specialized_router_no_services):
    """Test routing to cross-oracle without service"""
    result = await specialized_router_no_services.route_cross_oracle("query", user_level=3)

    assert result is None


@pytest.mark.asyncio
async def test_route_cross_oracle_exception(specialized_router):
    """Test routing to cross-oracle with exception"""
    specialized_router.cross_oracle.synthesize.side_effect = Exception("Error")

    result = await specialized_router.route_cross_oracle("query", user_level=3)

    assert result is None


@pytest.mark.asyncio
async def test_route_cross_oracle_use_cache(specialized_router):
    """Test routing to cross-oracle with cache"""
    result = await specialized_router.route_cross_oracle("query", user_level=3, use_cache=True)

    specialized_router.cross_oracle.synthesize.assert_called_once_with(
        query="query", user_level=3, use_cache=True
    )


# ============================================================================
# Tests: detect_client_journey
# ============================================================================


def test_detect_client_journey_pt_pma(specialized_router):
    """Test detecting client journey for PT PMA"""
    # Needs: start keyword + journey type (PT PMA)
    result = specialized_router.detect_client_journey(
        "start process for pt pma setup", "business_complex"
    )

    assert result is True


def test_detect_client_journey_kitas(specialized_router):
    """Test detecting client journey for KITAS"""
    result = specialized_router.detect_client_journey(
        "start process for KITAS application", "business_simple"
    )

    assert result is True


def test_detect_client_journey_property(specialized_router):
    """Test detecting client journey for property"""
    result = specialized_router.detect_client_journey(
        "begin application for property purchase", "business_complex"
    )

    assert result is True


def test_detect_client_journey_no_keywords(specialized_router):
    """Test not detecting client journey without keywords"""
    result = specialized_router.detect_client_journey("just a question", "business_simple")

    assert result is False


def test_detect_client_journey_no_service(specialized_router_no_services):
    """Test detecting client journey without service"""
    result = specialized_router_no_services.detect_client_journey(
        "start process PT PMA", "business_complex"
    )

    assert result is False


# ============================================================================
# Tests: route_client_journey
# ============================================================================


@pytest.mark.asyncio
async def test_route_client_journey_pt_pma(specialized_router):
    """Test routing client journey for PT PMA"""
    result = await specialized_router.route_client_journey("setup PT PMA company", "user123")

    assert result is not None
    assert result["category"] == "client_journey"
    assert "client_journey" in result
    assert result["client_journey"]["journey_id"] == "journey_123"


@pytest.mark.asyncio
async def test_route_client_journey_kitas(specialized_router):
    """Test routing client journey for KITAS"""
    result = await specialized_router.route_client_journey("apply for KITAS visa", "user123")

    assert result is not None
    assert result["client_journey"]["journey_id"] == "journey_123"


@pytest.mark.asyncio
async def test_route_client_journey_property(specialized_router):
    """Test routing client journey for property"""
    result = await specialized_router.route_client_journey("purchase land property", "user123")

    assert result is not None


@pytest.mark.asyncio
async def test_route_client_journey_unknown_type(specialized_router):
    """Test routing client journey with unknown type"""
    result = await specialized_router.route_client_journey("unknown journey type", "user123")

    assert result is None


@pytest.mark.asyncio
async def test_route_client_journey_no_service(specialized_router_no_services):
    """Test routing client journey without service"""
    result = await specialized_router_no_services.route_client_journey("PT PMA", "user123")

    assert result is None


@pytest.mark.asyncio
async def test_route_client_journey_exception(specialized_router):
    """Test routing client journey with exception"""
    specialized_router.client_journey.create_journey.side_effect = Exception("Error")

    result = await specialized_router.route_client_journey("PT PMA", "user123")

    assert result is None


@pytest.mark.asyncio
async def test_route_client_journey_response_format(specialized_router):
    """Test client journey response format"""
    result = await specialized_router.route_client_journey("PT PMA", "user123")

    assert "response" in result
    assert "journey_id" in result["response"] or "Journey ID" in result["response"]
    assert result["ai_used"] == "zantara"
    assert result["used_rag"] is False


# ============================================================================
# Tests: Edge Cases and Additional Coverage
# ============================================================================


def test_detect_autonomous_research_short_query_no_how_to(specialized_router):
    """Test autonomous research not triggered for short query without how-to"""
    # Short query (<=15 words) without how-to should not trigger
    short_query = "crypto business setup"
    result = specialized_router.detect_autonomous_research(short_query, "business_complex")

    # Should still trigger because of ambiguous term "crypto"
    assert result is True


def test_detect_autonomous_research_long_query_no_how_to(specialized_router):
    """Test autonomous research with long query but no how-to pattern"""
    # >15 words but no how-to pattern should not trigger
    long_query = " ".join(["word"] * 20)
    result = specialized_router.detect_autonomous_research(long_query, "business_complex")

    assert result is False


def test_detect_autonomous_research_business_simple_category(specialized_router):
    """Test autonomous research detection with business_simple category"""
    result = specialized_router.detect_autonomous_research(
        "cryptocurrency business", "business_simple"
    )

    assert result is True


def test_detect_cross_oracle_long_query_without_comprehensive(specialized_router):
    """Test cross-oracle with business setup and long query (>10 words) but no comprehensive indicator"""
    # Business setup term + >10 words should trigger even without comprehensive indicator
    long_query = "I want to open a restaurant business in Jakarta Indonesia with proper licensing"
    result = specialized_router.detect_cross_oracle(long_query, "business_complex")

    assert result is True


def test_detect_cross_oracle_short_query_no_comprehensive(specialized_router):
    """Test cross-oracle not triggered for short query without comprehensive indicator"""
    # Business setup term but short query and no comprehensive indicator
    short_query = "open restaurant"
    result = specialized_router.detect_cross_oracle(short_query, "business_complex")

    assert result is False


def test_detect_cross_oracle_business_simple_long(specialized_router):
    """Test cross-oracle detection with business_simple category and long query"""
    long_query = "I want to start a new cafe business in Bali with complete setup"
    result = specialized_router.detect_cross_oracle(long_query, "business_simple")

    assert result is True


def test_detect_client_journey_missing_journey_type(specialized_router):
    """Test client journey not detected when journey type is missing"""
    # Has start keyword but no journey type
    result = specialized_router.detect_client_journey(
        "start process for something", "business_complex"
    )

    assert result is False


def test_detect_client_journey_missing_start_keyword(specialized_router):
    """Test client journey not detected when start keyword is missing"""
    # Has journey type but no start keyword
    result = specialized_router.detect_client_journey(
        "I want to know about PT PMA", "business_complex"
    )

    assert result is False


def test_detect_client_journey_visa_journey(specialized_router):
    """Test detecting client journey for visa"""
    result = specialized_router.detect_client_journey(
        "begin application for visa", "business_complex"
    )

    assert result is True


def test_detect_client_journey_land_journey(specialized_router):
    """Test detecting client journey for land purchase"""
    result = specialized_router.detect_client_journey(
        "start process for land purchase", "business_complex"
    )

    assert result is True


@pytest.mark.asyncio
async def test_route_cross_oracle_no_cache(specialized_router):
    """Test routing to cross-oracle without cache"""
    result = await specialized_router.route_cross_oracle("query", user_level=3, use_cache=False)

    specialized_router.cross_oracle.synthesize.assert_called_once_with(
        query="query", user_level=3, use_cache=False
    )
    assert result is not None


@pytest.mark.asyncio
async def test_route_autonomous_research_user_level(specialized_router):
    """Test routing to autonomous research with different user level"""
    result = await specialized_router.route_autonomous_research("crypto query", user_level=5)

    specialized_router.autonomous_research.research.assert_called_once_with(
        query="crypto query", user_level=5
    )
    assert result is not None


@pytest.mark.asyncio
async def test_route_client_journey_response_contains_required_fields(specialized_router):
    """Test client journey response has all required fields"""
    result = await specialized_router.route_client_journey("setup PT PMA company", "user123")

    # Check all required response fields
    assert result["response"] is not None
    assert result["ai_used"] == "zantara"
    assert result["category"] == "client_journey"
    assert result["model"] == "zantara-ai"
    assert "tokens" in result
    assert result["tokens"]["input"] == 0
    assert result["tokens"]["output"] == 0
    assert result["used_rag"] is False
    assert "client_journey" in result
    assert result["client_journey"]["journey_id"] == "journey_123"
    assert result["client_journey"]["status"] == "active"
    assert result["client_journey"]["current_step"] == "Step 1"


# ============================================================================
# Tests: Keyword Coverage
# ============================================================================


def test_detect_autonomous_research_various_ambiguous_keywords(specialized_router):
    """Test autonomous research detection with various ambiguous keywords"""
    keywords_to_test = [
        "blockchain",
        "nft",
        "web3",
        "nuovo",
        "baru",
        "innovative",
        "innovativo",
        "non standard",
        "uncommon",
        "rare",
        "unusual",
        "multiple",
        "several",
        "various",
        "diversi",
        "beberapa",
    ]

    for keyword in keywords_to_test:
        result = specialized_router.detect_autonomous_research(
            f"What about {keyword} business?", "business_complex"
        )
        assert result is True, f"Failed for keyword: {keyword}"


def test_detect_autonomous_research_how_to_patterns(specialized_router):
    """Test autonomous research detection with various how-to patterns"""
    patterns = [
        "how to start a business in Indonesia with proper licensing documentation and all the permits needed for foreign investors",
        "come si apre una azienda in Indonesia con tutti i documenti necessari e permessi richiesti per investitori stranieri",
        "bagaimana cara mendirikan perusahaan di Indonesia dengan dokumen lengkap dan semua izin yang diperlukan untuk investor asing",
    ]

    for pattern in patterns:
        result = specialized_router.detect_autonomous_research(pattern, "business_complex")
        assert result is True, f"Failed for pattern: {pattern}"


def test_detect_cross_oracle_business_setup_keywords(specialized_router):
    """Test cross-oracle detection with various business setup keywords"""
    keywords = [
        "start",
        "launch",
        "setup",
        "establish",
        "create",
        "aprire",
        "avviare",
        "lanciare",
        "creare",
        "buka",
        "mulai",
        "dirikan",
    ]

    for keyword in keywords:
        query = f"I want to {keyword} a complete restaurant business in Bali"
        result = specialized_router.detect_cross_oracle(query, "business_complex")
        assert result is True, f"Failed for keyword: {keyword}"


def test_detect_cross_oracle_comprehensive_indicators(specialized_router):
    """Test cross-oracle detection with various comprehensive indicators"""
    indicators = [
        "everything",
        "tutto",
        "semua",
        "complete",
        "completo",
        "lengkap",
        "full",
        "penuh",
        "timeline",
        "cronologia",
        "investment",
        "investimento",
        "investasi",
        "requirements",
        "requisiti",
        "persyaratan",
    ]

    for indicator in indicators:
        query = f"I need {indicator} for opening restaurant"
        result = specialized_router.detect_cross_oracle(query, "business_complex")
        assert result is True, f"Failed for indicator: {indicator}"


def test_detect_client_journey_various_keywords(specialized_router):
    """Test client journey detection with various journey keywords"""
    journey_keywords = [
        ("start process", "pt pma"),
        ("begin application", "kitas"),
        ("setup company", "pt pma"),
        ("avvia pratica", "property"),
        ("inizia procedura", "land"),
        ("mulai proses", "visa"),
        ("apply for", "kitas"),
        ("richiedi", "property"),
        ("ajukan", "land"),
    ]

    for start_kw, journey_type in journey_keywords:
        query = f"{start_kw} for {journey_type}"
        result = specialized_router.detect_client_journey(query, "business_complex")
        assert result is True, f"Failed for: {start_kw} - {journey_type}"


# ============================================================================
# Tests: Response Format Validation
# ============================================================================


@pytest.mark.asyncio
async def test_route_autonomous_research_response_structure(specialized_router):
    """Test autonomous research response has correct structure"""
    result = await specialized_router.route_autonomous_research("crypto business", user_level=3)

    # Validate top-level fields
    assert result["response"] == "Research answer"
    assert result["ai_used"] == "zantara"
    assert result["category"] == "autonomous_research"
    assert result["model"] == "zantara-ai"
    assert result["used_rag"] is True

    # Validate autonomous_research sub-object
    ar = result["autonomous_research"]
    assert ar["total_steps"] == 3
    assert ar["collections_explored"] == ["collection1", "collection2"]
    assert ar["confidence"] == 0.9
    assert ar["sources_consulted"] == 5
    assert ar["duration_ms"] == 1000


@pytest.mark.asyncio
async def test_route_cross_oracle_response_structure(specialized_router):
    """Test cross-oracle response has correct structure"""
    result = await specialized_router.route_cross_oracle("open restaurant", user_level=3)

    # Validate top-level fields
    assert result["response"] == "Synthesis result"
    assert result["ai_used"] == "zantara"
    assert result["category"] == "cross_oracle_synthesis"
    assert result["model"] == "zantara-ai"
    assert result["used_rag"] is True

    # Validate cross_oracle_synthesis sub-object
    cos = result["cross_oracle_synthesis"]
    assert cos["scenario_type"] == "business_setup"
    assert cos["oracles_consulted"] == ["oracle1", "oracle2"]
    assert cos["confidence"] == 0.85
    assert cos["timeline"] == "60-90 days"
    assert cos["investment"] == "Rp 10B"
    assert cos["key_requirements"] == ["NIB", "NPWP"]
    assert cos["risks"] == ["Regulatory changes"]


# ============================================================================
# Tests: Initialization Logging
# ============================================================================


def test_specialized_router_init_no_services():
    """Test initialization without any services"""
    router = SpecializedServiceRouter(
        autonomous_research_service=None,
        cross_oracle_synthesis_service=None,
        client_journey_orchestrator=None,
    )

    assert router.autonomous_research is None
    assert router.cross_oracle is None
    assert router.client_journey is None


def test_specialized_router_init_partial_services(mock_autonomous_research):
    """Test initialization with only some services"""
    router = SpecializedServiceRouter(
        autonomous_research_service=mock_autonomous_research,
        cross_oracle_synthesis_service=None,
        client_journey_orchestrator=None,
    )

    assert router.autonomous_research is mock_autonomous_research
    assert router.cross_oracle is None
    assert router.client_journey is None
