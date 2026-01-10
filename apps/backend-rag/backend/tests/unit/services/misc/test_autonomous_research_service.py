"""
Unit tests for AutonomousResearchService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.misc.autonomous_research_service import AutonomousResearchService, ResearchResult


@pytest.fixture
def mock_search_service():
    """Mock search service"""
    service = MagicMock()
    service.search = AsyncMock(
        return_value={
            "documents": ["Test document"],
            "metadatas": [{"source": "test"}],
            "ids": ["doc1"],
        }
    )
    return service


@pytest.fixture
def mock_query_router():
    """Mock query router"""
    router = MagicMock()
    router.select_collections = MagicMock(return_value=["collection1"])
    return router


@pytest.fixture
def mock_zantara_ai():
    """Mock ZANTARA AI service"""
    service = MagicMock()
    service.generate_content = AsyncMock(
        return_value={"text": "Synthesized answer", "model": "test_model"}
    )
    return service


@pytest.fixture
def autonomous_research_service(mock_search_service, mock_query_router, mock_zantara_ai):
    """Create AutonomousResearchService instance"""
    return AutonomousResearchService(
        search_service=mock_search_service,
        query_router=mock_query_router,
        zantara_ai_service=mock_zantara_ai,
    )


class TestAutonomousResearchService:
    """Tests for AutonomousResearchService"""

    def test_init(self, autonomous_research_service):
        """Test initialization"""
        assert autonomous_research_service.MAX_ITERATIONS == 5
        assert autonomous_research_service.CONFIDENCE_THRESHOLD == 0.7
        assert autonomous_research_service.MIN_RESULTS_THRESHOLD == 3

    @pytest.mark.asyncio
    async def test_analyze_gaps(self, autonomous_research_service):
        """Test analyzing gaps in results"""
        results = [{"text": "Test document", "score": 0.5}]
        has_gaps, suggested_queries, rationale = await autonomous_research_service.analyze_gaps(
            "test query", results, collections_searched=["collection1"]
        )
        assert isinstance(has_gaps, bool)
        assert isinstance(suggested_queries, list)
        assert isinstance(rationale, str)

    @pytest.mark.asyncio
    async def test_expand_query(self, autonomous_research_service):
        """Test expanding query based on gaps"""
        findings = ["PT PMA", "KBLI code"]
        expanded = await autonomous_research_service.expand_query("original query", findings)
        assert isinstance(expanded, list)
        assert len(expanded) > 0

    @pytest.mark.asyncio
    async def test_research_simple_query(
        self, autonomous_research_service, mock_search_service, mock_query_router
    ):
        """Test researching a simple query"""
        mock_search_service.search.return_value = {
            "results": [{"text": "Test document", "score": 0.8}] * 5
        }
        mock_query_router.route_with_confidence = MagicMock(
            return_value=("collection1", 0.9, ["collection1", "collection2"])
        )
        result = await autonomous_research_service.research("test query")
        assert isinstance(result, ResearchResult)
        assert result.original_query == "test query"

    @pytest.mark.asyncio
    async def test_research_max_iterations(
        self, autonomous_research_service, mock_search_service, mock_query_router
    ):
        """Test research hitting max iterations"""
        mock_search_service.search.return_value = {
            "results": [{"text": "Test document", "score": 0.3}]
        }
        mock_query_router.route_with_confidence = MagicMock(
            return_value=("collection1", 0.3, ["collection1", "collection2"])
        )
        result = await autonomous_research_service.research("test query")
        assert result.total_steps <= autonomous_research_service.MAX_ITERATIONS
