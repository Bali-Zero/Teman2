"""
Unit tests for Cross-Oracle Synthesis Service
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.cross_oracle_synthesis_service import (
    CrossOracleSynthesisService,
    OracleQuery,
    SynthesisResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = AsyncMock()
    service.search = AsyncMock(return_value={"results": []})
    return service


@pytest.fixture
def mock_zantara_client():
    """Mock ZantaraAIClient"""
    client = AsyncMock()
    client.generate_text = AsyncMock(return_value={"text": "Synthesized answer"})
    return client


@pytest.fixture
def cross_oracle_service(mock_search_service, mock_zantara_client):
    """Create CrossOracleSynthesisService instance"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara_client):
        return (
            CrossOracleSynthesisService(mock_search_service, mock_zantara_client),
            mock_search_service,
            mock_zantara_client,
        )


@pytest.fixture
def cross_oracle_service_no_ai(mock_search_service):
    """Create CrossOracleSynthesisService without AI client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=MagicMock()):
        return CrossOracleSynthesisService(mock_search_service), mock_search_service


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_ai(mock_search_service, mock_zantara_client):
    """Test initialization with AI client"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara_client):
        service = CrossOracleSynthesisService(mock_search_service, mock_zantara_client)

        assert service.search == mock_search_service
        assert service.zantara == mock_zantara_client
        assert service.golden_answers is None


def test_init_without_ai(mock_search_service):
    """Test initialization without AI client"""
    mock_zantara = MagicMock()
    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara):
        service = CrossOracleSynthesisService(mock_search_service)

        assert service.search == mock_search_service
        assert service.zantara == mock_zantara


def test_init_with_golden_answers(mock_search_service, mock_zantara_client):
    """Test initialization with golden answer service"""
    mock_golden = MagicMock()

    with patch("llm.zantara_ai_client.ZantaraAIClient", return_value=mock_zantara_client):
        service = CrossOracleSynthesisService(mock_search_service, mock_zantara_client, mock_golden)

        assert service.golden_answers == mock_golden


# ============================================================================
# Tests for classify_scenario
# ============================================================================


def test_classify_scenario_business_setup(cross_oracle_service):
    """Test classify_scenario detects business_setup"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("I want to open a restaurant in Canggu")

    assert scenario == "business_setup"
    assert confidence > 0.0


def test_classify_scenario_visa_application(cross_oracle_service):
    """Test classify_scenario detects visa_application"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("How to get KITAS visa?")

    assert scenario == "visa_application"
    assert confidence > 0.0


def test_classify_scenario_property_investment(cross_oracle_service):
    """Test classify_scenario detects property_investment"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("I want to buy property in Bali")

    assert scenario == "property_investment"
    assert confidence > 0.0


def test_classify_scenario_tax_optimization(cross_oracle_service):
    """Test classify_scenario detects tax_optimization"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("What are the tax obligations?")

    assert scenario == "tax_optimization"
    assert confidence > 0.0


def test_classify_scenario_compliance_check(cross_oracle_service):
    """Test classify_scenario detects compliance_check"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("What are the compliance requirements?")

    assert scenario == "compliance_check"
    assert confidence > 0.0


def test_classify_scenario_general(cross_oracle_service):
    """Test classify_scenario defaults to general"""
    service, mock_search, mock_zantara = cross_oracle_service

    scenario, confidence = service.classify_scenario("Random query")

    assert scenario == "general"
    assert confidence == 0.0


# ============================================================================
# Tests for determine_oracles
# ============================================================================


def test_determine_oracles_business_setup(cross_oracle_service):
    """Test determine_oracles for business_setup"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_queries = service.determine_oracles("Open restaurant", "business_setup")

    assert len(oracle_queries) > 0
    assert all(isinstance(oq, OracleQuery) for oq in oracle_queries)
    # Check required oracles are included
    oracle_names = [oq.collection for oq in oracle_queries]
    assert "kbli_eye" in oracle_names
    assert "legal_architect" in oracle_names


def test_determine_oracles_visa_application(cross_oracle_service):
    """Test determine_oracles for visa_application"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_queries = service.determine_oracles("Get visa", "visa_application")

    assert len(oracle_queries) > 0
    oracle_names = [oq.collection for oq in oracle_queries]
    assert "visa_oracle" in oracle_names


def test_determine_oracles_property_investment(cross_oracle_service):
    """Test determine_oracles for property_investment"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_queries = service.determine_oracles("Buy property", "property_investment")

    assert len(oracle_queries) > 0
    oracle_names = [oq.collection for oq in oracle_queries]
    assert "property_knowledge" in oracle_names
    assert "legal_architect" in oracle_names


def test_determine_oracles_general(cross_oracle_service):
    """Test determine_oracles for general scenario"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_queries = service.determine_oracles("Test query", "general")

    assert len(oracle_queries) == 1
    assert oracle_queries[0].collection == "visa_oracle"
    assert oracle_queries[0].priority == 1


# ============================================================================
# Tests for query_oracle
# ============================================================================


@pytest.mark.asyncio
async def test_query_oracle_success(cross_oracle_service):
    """Test query_oracle successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.return_value = {
        "results": [
            {"text": "Result 1", "score": 0.9},
            {"text": "Result 2", "score": 0.8},
        ]
    }

    oracle_query = OracleQuery(
        collection="visa_oracle",
        query="How to get visa?",
        priority=1,
        rationale="Test",
    )

    result = await service.query_oracle(oracle_query)

    assert result["success"] is True
    assert result["collection"] == "visa_oracle"
    assert result["result_count"] == 2
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_query_oracle_no_results(cross_oracle_service):
    """Test query_oracle with no results"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.return_value = {"results": []}

    oracle_query = OracleQuery(
        collection="visa_oracle",
        query="Test",
        priority=1,
    )

    result = await service.query_oracle(oracle_query)

    assert result["success"] is False
    assert result["result_count"] == 0


@pytest.mark.asyncio
async def test_query_oracle_exception(cross_oracle_service):
    """Test query_oracle handles exception"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.side_effect = Exception("Search error")

    oracle_query = OracleQuery(
        collection="visa_oracle",
        query="Test",
        priority=1,
    )

    result = await service.query_oracle(oracle_query)

    assert result["success"] is False
    assert "error" in result


# ============================================================================
# Tests for query_all_oracles
# ============================================================================


@pytest.mark.asyncio
async def test_query_all_oracles_success(cross_oracle_service):
    """Test query_all_oracles successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.9}]}

    oracle_queries = [
        OracleQuery(collection="visa_oracle", query="Test", priority=1),
        OracleQuery(collection="tax_genius", query="Test", priority=2),
    ]

    results = await service.query_all_oracles(oracle_queries)

    assert isinstance(results, dict)
    assert "visa_oracle" in results
    assert "tax_genius" in results
    assert len(results) == 2


@pytest.mark.asyncio
async def test_query_all_oracles_mixed_results(cross_oracle_service):
    """Test query_all_oracles with mixed success/failure"""
    service, mock_search, mock_zantara = cross_oracle_service

    call_count = 0

    def mock_search_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"results": [{"text": "Result", "score": 0.9}]}
        else:
            return {"results": []}

    mock_search.search.side_effect = mock_search_side_effect

    oracle_queries = [
        OracleQuery(collection="visa_oracle", query="Test", priority=1),
        OracleQuery(collection="tax_genius", query="Test", priority=2),
    ]

    results = await service.query_all_oracles(oracle_queries)

    assert results["visa_oracle"]["success"] is True
    assert results["tax_genius"]["success"] is False


# ============================================================================
# Tests for synthesize_with_zantara
# ============================================================================


@pytest.mark.asyncio
async def test_synthesize_with_zantara_success(cross_oracle_service):
    """Test synthesize_with_zantara successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_zantara.generate_text.return_value = {"text": "Synthesized answer"}

    oracle_results = {
        "visa_oracle": {
            "success": True,
            "results": [{"text": "Visa info", "score": 0.9}],
        }
    }

    result = await service.synthesize_with_zantara(
        "How to get visa?", "visa_application", oracle_results
    )

    assert result == "Synthesized answer"
    mock_zantara.generate_text.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_with_zantara_exception(cross_oracle_service):
    """Test synthesize_with_zantara handles exception"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_zantara.generate_text.side_effect = Exception("AI error")

    oracle_results = {
        "visa_oracle": {
            "success": True,
            "results": [{"text": "Visa info"}],
        }
    }

    result = await service.synthesize_with_zantara(
        "How to get visa?", "visa_application", oracle_results
    )

    # Should fallback to simple synthesis
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_synthesize_with_zantara_no_results(cross_oracle_service):
    """Test synthesize_with_zantara with no successful results"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_results = {
        "visa_oracle": {
            "success": False,
            "results": [],
        }
    }

    result = await service.synthesize_with_zantara(
        "How to get visa?", "visa_application", oracle_results
    )

    # Should still synthesize with empty context
    assert isinstance(result, str)


# ============================================================================
# Tests for _simple_synthesis
# ============================================================================


def test_simple_synthesis_success(cross_oracle_service):
    """Test _simple_synthesis successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_results = {
        "visa_oracle": {
            "success": True,
            "results": [{"text": "Visa info here", "score": 0.9}],
        },
        "tax_genius": {
            "success": True,
            "results": [{"text": "Tax info here", "score": 0.8}],
        },
    }

    result = service._simple_synthesis("How to get visa?", oracle_results)

    assert isinstance(result, str)
    assert "Visa info" in result
    assert "Tax info" in result


def test_simple_synthesis_no_results(cross_oracle_service):
    """Test _simple_synthesis with no results"""
    service, mock_search, mock_zantara = cross_oracle_service

    oracle_results = {
        "visa_oracle": {
            "success": False,
            "results": [],
        }
    }

    result = service._simple_synthesis("Test query", oracle_results)

    assert isinstance(result, str)
    assert "Test query" in result


# ============================================================================
# Tests for _parse_synthesis
# ============================================================================


def test_parse_synthesis_success(cross_oracle_service):
    """Test _parse_synthesis successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    synthesis_text = """
## Integrated Recommendation
This is the recommendation.

## Timeline
2-3 months

## Investment Required
$10,000 - $15,000

## Key Requirements
- Requirement 1
- Requirement 2

## Potential Risks
- Risk 1
- Risk 2
"""

    result = service._parse_synthesis(synthesis_text)

    assert result["timeline"] == "2-3 months"
    assert result["investment"] == "$10,000 - $15,000"
    assert len(result["key_requirements"]) == 2
    assert len(result["risks"]) == 2


def test_parse_synthesis_partial(cross_oracle_service):
    """Test _parse_synthesis with partial data"""
    service, mock_search, mock_zantara = cross_oracle_service

    synthesis_text = """
## Integrated Recommendation
This is the recommendation.

## Timeline
2-3 months
"""

    result = service._parse_synthesis(synthesis_text)

    assert result["timeline"] == "2-3 months"
    assert result["investment"] is None
    assert len(result["key_requirements"]) == 0


def test_parse_synthesis_empty(cross_oracle_service):
    """Test _parse_synthesis with empty text"""
    service, mock_search, mock_zantara = cross_oracle_service

    result = service._parse_synthesis("")

    assert result["timeline"] is None
    assert result["investment"] is None
    assert len(result["key_requirements"]) == 0
    assert len(result["risks"]) == 0


# ============================================================================
# Tests for synthesize
# ============================================================================


@pytest.mark.asyncio
async def test_synthesize_success(cross_oracle_service):
    """Test synthesize successful"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.9}]}
    mock_zantara.generate_text.return_value = {
        "text": "## Integrated Recommendation\nAnswer\n## Timeline\n2 months"
    }

    result = await service.synthesize("How to open restaurant?", user_level=3)

    assert isinstance(result, SynthesisResult)
    assert result.query == "How to open restaurant?"
    assert result.scenario_type == "business_setup"
    assert len(result.oracles_consulted) > 0
    assert len(result.synthesis) > 0


@pytest.mark.asyncio
async def test_synthesize_updates_stats(cross_oracle_service):
    """Test synthesize updates statistics"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.9}]}
    mock_zantara.generate_text.return_value = {"text": "Answer"}

    initial_count = service.synthesis_stats["total_syntheses"]

    await service.synthesize("Test query", user_level=3)

    assert service.synthesis_stats["total_syntheses"] == initial_count + 1


@pytest.mark.asyncio
async def test_synthesize_with_cache(cross_oracle_service):
    """Test synthesize with cache enabled"""
    service, mock_search, mock_zantara = cross_oracle_service

    mock_golden = MagicMock()
    service.golden_answers = mock_golden

    mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.9}]}
    mock_zantara.generate_text.return_value = {"text": "Answer"}

    result = await service.synthesize("Test query", user_level=3, use_cache=True)

    assert isinstance(result, SynthesisResult)


# ============================================================================
# Tests for get_synthesis_stats
# ============================================================================


def test_get_synthesis_stats(cross_oracle_service):
    """Test get_synthesis_stats"""
    service, mock_search, mock_zantara = cross_oracle_service

    stats = service.get_synthesis_stats()

    assert "total_syntheses" in stats
    assert "cache_hits" in stats
    assert "avg_oracles_consulted" in stats
    assert "scenario_distribution" in stats
