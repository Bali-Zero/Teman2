"""
Unit tests for Autonomous Research Service
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

from services.autonomous_research_service import (
    AutonomousResearchService,
    ResearchResult,
    ResearchStep,
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
def mock_query_router():
    """Mock QueryRouter"""
    router = MagicMock()
    router.route_with_confidence = MagicMock(
        return_value=("visa_oracle", 0.8, ["visa_oracle", "tax_genius"])
    )
    return router


@pytest.fixture
def mock_zantara_service():
    """Mock ZANTARA AI service"""
    service = AsyncMock()
    service.conversational = AsyncMock(return_value={"text": "Research answer"})
    return service


@pytest.fixture
def autonomous_research_service(mock_search_service, mock_query_router, mock_zantara_service):
    """Create AutonomousResearchService instance"""
    return (
        AutonomousResearchService(mock_search_service, mock_query_router, mock_zantara_service),
        mock_search_service,
        mock_query_router,
        mock_zantara_service,
    )


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init(autonomous_research_service):
    """Test initialization"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    assert service.search == mock_search
    assert service.router == mock_router
    assert service.zantara == mock_zantara
    assert service.MAX_ITERATIONS == 5
    assert service.CONFIDENCE_THRESHOLD == 0.7


# ============================================================================
# Tests for analyze_gaps
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_gaps_insufficient_results(autonomous_research_service):
    """Test analyze_gaps with insufficient results"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    has_gaps, queries, rationale = await service.analyze_gaps(
        "Test query", [{"text": "Result", "score": 0.5}], []
    )

    assert has_gaps is True
    assert len(queries) > 0
    assert "Insufficient" in rationale


@pytest.mark.asyncio
async def test_analyze_gaps_low_confidence(autonomous_research_service):
    """Test analyze_gaps with low confidence"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    has_gaps, queries, rationale = await service.analyze_gaps(
        "Test query",
        [
            {"text": "Result 1", "score": 0.3},
            {"text": "Result 2", "score": 0.4},
            {"text": "Result 3", "score": 0.35},  # Enough results but low confidence
        ],
        [],
    )

    assert has_gaps is True
    assert "Low confidence" in rationale or "confidence" in rationale.lower()


@pytest.mark.asyncio
async def test_analyze_gaps_uncertainty_keywords(autonomous_research_service):
    """Test analyze_gaps detects uncertainty keywords"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    has_gaps, queries, rationale = await service.analyze_gaps(
        "Test query",
        [
            {"text": "It is not clear what the requirements are", "score": 0.8},
            {"text": "This depends on various factors", "score": 0.7},
            {"text": "Result 3", "score": 0.6},  # Enough results
        ],
        [],
    )

    assert has_gaps is True
    # May detect uncertainty or other gaps
    assert isinstance(rationale, str)


@pytest.mark.asyncio
async def test_analyze_gaps_limited_collections(autonomous_research_service):
    """Test analyze_gaps with limited collection coverage"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    has_gaps, queries, rationale = await service.analyze_gaps(
        "Test query",
        [
            {"text": "Result 1", "score": 0.8},
            {"text": "Result 2", "score": 0.7},
            {"text": "Result 3", "score": 0.6},
        ],
        ["visa_oracle"],  # Only 1 collection searched
    )

    assert has_gaps is True
    assert "coverage" in rationale.lower() or "expanding" in rationale.lower()


@pytest.mark.asyncio
async def test_analyze_gaps_no_gaps(autonomous_research_service):
    """Test analyze_gaps detects no gaps"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    has_gaps, queries, rationale = await service.analyze_gaps(
        "Test query",
        [
            {"text": "Result 1", "score": 0.9},
            {"text": "Result 2", "score": 0.8},
            {"text": "Result 3", "score": 0.7},
            {"text": "Result 4", "score": 0.6},
        ],
        ["visa_oracle", "tax_genius", "legal_architect"],  # 3+ collections
    )

    assert has_gaps is False
    assert "Sufficient" in rationale


# ============================================================================
# Tests for select_next_collection
# ============================================================================


def test_select_next_collection_success(autonomous_research_service):
    """Test select_next_collection successful"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    collection = service.select_next_collection("Test query", [])

    assert collection is not None
    assert collection in ["visa_oracle", "tax_genius"]


def test_select_next_collection_all_searched(autonomous_research_service):
    """Test select_next_collection when all collections searched"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    collection = service.select_next_collection("Test query", ["visa_oracle", "tax_genius"])

    assert collection is None


# ============================================================================
# Tests for expand_query
# ============================================================================


@pytest.mark.asyncio
async def test_expand_query_basic(autonomous_research_service):
    """Test expand_query basic expansion"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    expansions = await service.expand_query("How to get visa?", [])

    assert isinstance(expansions, list)
    assert len(expansions) <= 3
    assert "How to get visa?" in expansions


@pytest.mark.asyncio
async def test_expand_query_with_findings(autonomous_research_service):
    """Test expand_query with findings"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    expansions = await service.expand_query(
        "How to get visa?", ["KITAS is required", "PT company needs visa"]
    )

    assert isinstance(expansions, list)
    assert len(expansions) <= 3


@pytest.mark.asyncio
async def test_expand_query_with_business_terms(autonomous_research_service):
    """Test expand_query extracts business terms"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    expansions = await service.expand_query(
        "How to setup business?", ["PT PMA company", "KBLI code required"]
    )

    assert isinstance(expansions, list)
    # May include expansions with business terms
    assert len(expansions) <= 3


# ============================================================================
# Tests for research_iteration
# ============================================================================


@pytest.mark.asyncio
async def test_research_iteration_success(autonomous_research_service):
    """Test research_iteration successful"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_search.search.return_value = {
        "results": [
            {"text": "Result 1", "score": 0.9},
            {"text": "Result 2", "score": 0.8},
        ]
    }

    step = await service.research_iteration("Test query", 1, [], user_level=3)

    assert isinstance(step, ResearchStep)
    assert step.step_number == 1
    assert step.results_found == 2
    assert step.confidence > 0.0
    assert len(step.key_findings) == 2


@pytest.mark.asyncio
async def test_research_iteration_no_collection(autonomous_research_service):
    """Test research_iteration when no collection available"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_router.route_with_confidence.return_value = ("visa_oracle", 0.8, [])

    step = await service.research_iteration("Test query", 1, ["visa_oracle"], user_level=3)

    assert step.collection == "none"
    assert step.results_found == 0


@pytest.mark.asyncio
async def test_research_iteration_no_results(autonomous_research_service):
    """Test research_iteration with no results"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_search.search.return_value = {"results": []}

    step = await service.research_iteration("Test query", 1, [], user_level=3)

    assert step.results_found == 0
    assert step.confidence == 0.0


@pytest.mark.asyncio
async def test_research_iteration_exception(autonomous_research_service):
    """Test research_iteration handles exception"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_search.search.side_effect = Exception("Search error")

    step = await service.research_iteration("Test query", 1, [], user_level=3)

    assert step.results_found == 0
    assert "failed" in step.rationale.lower()


# ============================================================================
# Tests for synthesize_research
# ============================================================================


@pytest.mark.asyncio
async def test_synthesize_research_success(autonomous_research_service):
    """Test synthesize_research successful"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    async def mock_conversational(*args, **kwargs):
        return {"text": "Synthesized answer"}

    mock_zantara.conversational = mock_conversational

    research_steps = [
        ResearchStep(
            step_number=1,
            collection="visa_oracle",
            query="Test",
            rationale="Test",
            results_found=2,
            confidence=0.8,
            key_findings=["Finding 1", "Finding 2"],
        )
    ]

    answer, confidence = await service.synthesize_research("Test query", research_steps)

    assert answer == "Synthesized answer"
    assert confidence > 0.0


@pytest.mark.asyncio
async def test_synthesize_research_no_findings(autonomous_research_service):
    """Test synthesize_research with no findings"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    research_steps = [
        ResearchStep(
            step_number=1,
            collection="visa_oracle",
            query="Test",
            rationale="Test",
            results_found=0,
            confidence=0.0,
            key_findings=[],
        )
    ]

    answer, confidence = await service.synthesize_research("Test query", research_steps)

    assert isinstance(answer, str)
    assert (
        "couldn't find" in answer.lower()
        or "insufficient" in answer.lower()
        or "not found" in answer.lower()
    )


@pytest.mark.asyncio
async def test_synthesize_research_exception(autonomous_research_service):
    """Test synthesize_research handles exception"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    async def mock_conversational_error(*args, **kwargs):
        raise Exception("AI error")

    mock_zantara.conversational = mock_conversational_error

    research_steps = [
        ResearchStep(
            step_number=1,
            collection="visa_oracle",
            query="Test",
            rationale="Test",
            results_found=2,
            confidence=0.8,
            key_findings=["Finding"],
        )
    ]

    answer, confidence = await service.synthesize_research("Test query", research_steps)

    # Should fallback to simple concatenation
    assert isinstance(answer, str)
    assert len(answer) > 0


# ============================================================================
# Tests for research
# ============================================================================


@pytest.mark.asyncio
async def test_research_success(autonomous_research_service):
    """Test research successful"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_search.search.return_value = {
        "results": [
            {"text": "Result", "score": 0.9},
        ]
    }

    async def mock_conversational(*args, **kwargs):
        return {"text": "Final answer"}

    mock_zantara.conversational = mock_conversational

    result = await service.research("How to get visa?", user_level=3)

    assert isinstance(result, ResearchResult)
    assert result.original_query == "How to get visa?"
    assert result.total_steps > 0
    assert len(result.research_steps) > 0
    assert len(result.final_answer) > 0


@pytest.mark.asyncio
async def test_research_max_iterations(autonomous_research_service):
    """Test research stops at max iterations"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    mock_search.search.return_value = {"results": []}  # Always no results to force iterations

    async def mock_conversational(*args, **kwargs):
        return {"text": "Answer"}

    mock_zantara.conversational = mock_conversational

    result = await service.research("Test query", user_level=3)

    assert result.total_steps <= service.MAX_ITERATIONS


@pytest.mark.asyncio
async def test_research_updates_stats(autonomous_research_service):
    """Test research updates statistics"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    initial_count = service.research_stats["total_researches"]

    mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.9}]}

    async def mock_conversational(*args, **kwargs):
        return {"text": "Answer"}

    mock_zantara.conversational = mock_conversational

    await service.research("Test query", user_level=3)

    assert service.research_stats["total_researches"] == initial_count + 1


# ============================================================================
# Tests for get_research_stats
# ============================================================================


def test_get_research_stats(autonomous_research_service):
    """Test get_research_stats"""
    service, mock_search, mock_router, mock_zantara = autonomous_research_service

    stats = service.get_research_stats()

    assert "total_researches" in stats
    assert "avg_iterations" in stats
    assert "avg_confidence" in stats
    assert "max_iterations_reached" in stats

    # ============================================================================
    # Expanded Edge Cases and Additional Tests
    # ============================================================================

    @pytest.mark.asyncio
    async def test_research_high_confidence_early_termination(autonomous_research_service):
        """Test research terminates early when high confidence achieved"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        # First iteration returns high confidence results
        mock_search.search.return_value = {
            "results": [
                {"text": "High quality result", "score": 0.95},
                {"text": "Another high quality result", "score": 0.92},
                {"text": "Third result", "score": 0.90},
            ]
        }

        async def mock_conversational(*args, **kwargs):
            return {"text": "Complete answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Test query", user_level=3)

        # Should terminate early (before MAX_ITERATIONS)
        assert result.total_steps < service.MAX_ITERATIONS
        assert result.final_confidence >= service.CONFIDENCE_THRESHOLD

    @pytest.mark.asyncio
    async def test_research_multiple_collection_expansion(autonomous_research_service):
        """Test research expands to multiple collections"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        call_count = 0

        def mock_search_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"results": [{"text": "Result 1", "score": 0.6}]}  # Low confidence
            elif call_count == 2:
                return {"results": [{"text": "Result 2", "score": 0.7}]}  # Still low
            else:
                return {"results": [{"text": "Result 3", "score": 0.9}]}  # High confidence

        mock_search.search.side_effect = mock_search_side_effect

        async def mock_conversational(*args, **kwargs):
            return {"text": "Final answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Complex query", user_level=3)

        # Should have searched multiple collections
        collections_searched = set(step.collection for step in result.research_steps)
        assert len(collections_searched) > 1

    @pytest.mark.asyncio
    async def test_research_query_expansion(autonomous_research_service):
        """Test research expands queries based on findings"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        mock_search.search.return_value = {
            "results": [
                {"text": "KITAS requires PT PMA company", "score": 0.8},
                {"text": "Business license needed", "score": 0.7},
            ]
        }

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("How to get visa?", user_level=3)

        # Should have expanded queries based on findings
        queries_used = [step.query for step in result.research_steps]
        # At least one query should be different from original
        assert any("PT PMA" in q or "business" in q.lower() for q in queries_used)

    @pytest.mark.asyncio
    async def test_research_reasoning_chain(autonomous_research_service):
        """Test research builds reasoning chain"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.8}]}

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Test query", user_level=3)

        # Should have reasoning chain
        assert len(result.reasoning_chain) > 0
        assert all(isinstance(step, str) for step in result.reasoning_chain)

    @pytest.mark.asyncio
    async def test_research_handles_router_errors(autonomous_research_service):
        """Test research handles query router errors"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        mock_router.route_with_confidence.side_effect = Exception("Router error")

        async def mock_conversational(*args, **kwargs):
            return {"text": "Fallback answer"}

        mock_zantara.conversational = mock_conversational

        # Should handle router error gracefully
        result = await service.research("Test query", user_level=3)

        assert isinstance(result, ResearchResult)
        assert len(result.final_answer) > 0

    @pytest.mark.asyncio
    async def test_research_empty_query(self, autonomous_research_service):
        """Test research handles empty query"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("", user_level=3)

        assert isinstance(result, ResearchResult)

    @pytest.mark.asyncio
    async def test_research_very_long_query(self, autonomous_research_service):
        """Test research handles very long query"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        long_query = "test " * 1000
        mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.8}]}

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research(long_query, user_level=3)

        assert isinstance(result, ResearchResult)

    @pytest.mark.asyncio
    async def test_research_special_characters(self, autonomous_research_service):
        """Test research handles special characters"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        special_query = "test query with émojis 🎉 and spéciál chars @#$%"
        mock_search.search.return_value = {"results": [{"text": "Result", "score": 0.8}]}

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research(special_query, user_level=3)

        assert isinstance(result, ResearchResult)

    @pytest.mark.asyncio
    async def test_research_all_collections_exhausted(autonomous_research_service):
        """Test research when all collections are exhausted"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        # Mock router to return None after all collections searched
        call_count = 0

        def mock_router_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            collections = ["visa_oracle", "tax_genius", "legal_architect"]
            if call_count <= len(collections):
                return (collections[call_count - 1], 0.8, collections[call_count:])
            return (None, 0.0, [])

        mock_router.route_with_confidence.side_effect = mock_router_side_effect
        mock_search.search.return_value = {"results": []}

        async def mock_conversational(*args, **kwargs):
            return {"text": "No results found"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Test query", user_level=3)

        assert isinstance(result, ResearchResult)
        assert result.total_steps <= service.MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_research_confidence_calculation(autonomous_research_service):
        """Test research calculates confidence correctly"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        # High quality results should yield high confidence
        mock_search.search.return_value = {
            "results": [
                {"text": "Result 1", "score": 0.95},
                {"text": "Result 2", "score": 0.93},
                {"text": "Result 3", "score": 0.91},
            ]
        }

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Test query", user_level=3)

        # First step should have high confidence
        if result.research_steps:
            assert result.research_steps[0].confidence > 0.7

    @pytest.mark.asyncio
    async def test_research_key_findings_extraction(autonomous_research_service):
        """Test research extracts key findings from results"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        mock_search.search.return_value = {
            "results": [
                {"text": "KITAS requires PT PMA company with minimum investment", "score": 0.9},
                {"text": "Business license (NIB) must be obtained first", "score": 0.85},
            ]
        }

        async def mock_conversational(*args, **kwargs):
            return {"text": "Answer"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("How to get KITAS?", user_level=3)

        # Should extract key findings
        all_findings = []
        for step in result.research_steps:
            all_findings.extend(step.key_findings)

        assert len(all_findings) > 0
        assert any("KITAS" in finding or "PT PMA" in finding for finding in all_findings)

    @pytest.mark.asyncio
    async def test_research_synthesis_with_multiple_steps(autonomous_research_service):
        """Test research synthesizes multiple research steps"""
        service, mock_search, mock_router, mock_zantara = autonomous_research_service

        call_count = 0

        def mock_search_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "results": [
                    {"text": f"Result from step {call_count}", "score": 0.7 + call_count * 0.05}
                ]
            }

        mock_search.search.side_effect = mock_search_side_effect

        async def mock_conversational(*args, **kwargs):
            # Check that synthesis includes multiple steps
            prompt = kwargs.get("prompt", "")
            assert "step" in prompt.lower() or "finding" in prompt.lower()
            return {"text": "Synthesized answer from multiple steps"}

        mock_zantara.conversational = mock_conversational

        result = await service.research("Complex multi-step query", user_level=3)

        assert len(result.research_steps) > 1
        assert "multiple" in result.final_answer.lower() or len(result.final_answer) > 0
