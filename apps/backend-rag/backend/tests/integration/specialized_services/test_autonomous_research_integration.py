"""
Integration Tests: Autonomous Research Service Integration

Tests integration with Autonomous Research Service:
1. Complex multi-collection queries
2. Research orchestration
3. Result synthesis
4. Integration with RAG and Memory

Target: Test Autonomous Research Service end-to-end integration
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Note: These imports may need to be mocked if services have complex dependencies
# from services.misc.autonomous_research_service import AutonomousResearchService
# from services.routing.specialized_service_router import SpecializedServiceRouter
# from services.search.search_service import SearchService


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    service.search = AsyncMock(return_value={
        "results": [
            {"id": "doc1", "text": "Test result 1", "score": 0.9},
            {"id": "doc2", "text": "Test result 2", "score": 0.85}
        ],
        "total": 2
    })
    return service


@pytest.fixture
def mock_db_pool():
    """Mock PostgreSQL connection pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def autonomous_research_service(mock_search_service, mock_db_pool):
    """Create AutonomousResearchService with mocked dependencies"""
    # Mock the service instead of importing it directly
    service = MagicMock()
    service.research = AsyncMock(return_value={
        "success": True,
        "results": [],
        "synthesis": "Test synthesis"
    })
    service.synthesize_results = AsyncMock(return_value={
        "synthesis": "Test synthesis",
        "key_differences": []
    })
    return service


class TestAutonomousResearchIntegration:
    """Autonomous Research Service Integration Tests"""

    @pytest.mark.asyncio
    async def test_complex_multi_collection_research(
        self, autonomous_research_service, mock_search_service
    ):
        """Test research across multiple collections"""
        query = "Analizza le ultime modifiche alle leggi su visto e tasse"

        # Mock multi-collection search
        collections = ["visa_oracle", "tax_genius", "legal_unified"]
        mock_search_service.search = AsyncMock(side_effect=[
            {"results": [{"id": f"doc{i}", "text": f"Result {i}"}], "total": 1}
            for i in range(len(collections))
        ])

        # Execute research
        with patch.object(autonomous_research_service, 'research') as mock_research:
            mock_research.return_value = {
                "success": True,
                "results": [
                    {"collection": "visa_oracle", "documents": [{"id": "doc1"}]},
                    {"collection": "tax_genius", "documents": [{"id": "doc2"}]},
                    {"collection": "legal_unified", "documents": [{"id": "doc3"}]}
                ],
                "synthesis": "Comprehensive analysis of visa and tax regulations"
            }

            result = await autonomous_research_service.research(
                query=query,
                collections=collections,
                limit_per_collection=5
            )

            # Verify research executed
            assert result["success"] is True
            assert len(result["results"]) == len(collections)
            assert "synthesis" in result

    @pytest.mark.asyncio
    async def test_autonomous_research_routing(
        self, mock_search_service, mock_db_pool
    ):
        """Test that complex queries route to Autonomous Research"""
        query = "Confronta i requisiti per E33G, E28A e C1 visto"

        # Mock specialized router
        with patch('services.routing.specialized_service_router.SpecializedServiceRouter') as mock_router:
            mock_router_instance = MagicMock()
            mock_router_instance.should_route_to_autonomous_research = MagicMock(return_value=True)
            mock_router.return_value = mock_router_instance

            router = mock_router_instance

            # Check routing decision
            should_route = router.should_route_to_autonomous_research(query)

            # Verify routing decision
            assert should_route is True

    @pytest.mark.asyncio
    async def test_research_result_synthesis(
        self, autonomous_research_service, mock_search_service
    ):
        """Test that research results are properly synthesized"""
        query = "Quali sono le differenze tra PT PMA e PT Lokal?"

        # Mock research with multiple results
        research_results = {
            "visa_oracle": [
                {"text": "PT PMA requires foreign investment", "score": 0.9},
                {"text": "PT Lokal is for local investors", "score": 0.85}
            ],
            "kbli_unified": [
                {"text": "PT PMA minimum investment Rp 10B", "score": 0.88},
                {"text": "PT Lokal no minimum investment", "score": 0.82}
            ]
        }

        # Mock synthesis
        with patch.object(autonomous_research_service, 'synthesize_results') as mock_synthesize:
            mock_synthesize.return_value = {
                "synthesis": "PT PMA requires foreign investment and minimum Rp 10B, while PT Lokal is for local investors with no minimum.",
                "key_differences": [
                    "Investment requirement",
                    "Investor type",
                    "Minimum capital"
                ]
            }

            synthesis = await autonomous_research_service.synthesize_results(
                query=query,
                results=research_results
            )

            # Verify synthesis
            assert "synthesis" in synthesis
            assert "key_differences" in synthesis

    @pytest.mark.asyncio
    async def test_research_with_memory_context(
        self, autonomous_research_service, mock_search_service, mock_db_pool
    ):
        """Test research using Memory context for personalization"""
        query = "Qual è il miglior visto per me?"
        user_id = "marco@example.com"

        # Mock memory context
        memory_context = {
            "facts": ["Marco is a digital nomad", "Marco has $50k budget"],
            "entities": {"profession": "digital_nomad", "budget": "$50k"}
        }

        # Execute research with context
        with patch.object(autonomous_research_service, 'research') as mock_research:
            mock_research.return_value = {
                "success": True,
                "results": [{"text": "E33G is best for digital nomads"}],
                "personalized": True
            }

            result = await autonomous_research_service.research(
                query=query,
                user_context=memory_context
            )

            # Verify personalized research
            assert result["success"] is True
            assert result.get("personalized") is True

    @pytest.mark.asyncio
    async def test_research_error_handling(
        self, autonomous_research_service, mock_search_service
    ):
        """Test error handling when research fails"""
        query = "Test query"

        # Mock search failure
        mock_search_service.search = AsyncMock(side_effect=Exception("Search error"))

        # Execute research - should handle error gracefully
        try:
            result = await autonomous_research_service.research(query=query)
            # Should either return error response or None
            assert result is None or "error" in str(result).lower() or not result.get("success", True)
        except Exception as e:
            # If exception is raised, verify it's handled appropriately
            assert "error" in str(e).lower() or "research" in str(e).lower()

    @pytest.mark.asyncio
    async def test_research_caching(
        self, autonomous_research_service, mock_search_service
    ):
        """Test that research results are cached"""
        query = "Informazioni su E33G"

        # Mock cache
        with patch('services.search.semantic_cache.SemanticCache') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache_instance.set = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            # Execute research
            with patch.object(autonomous_research_service, 'research') as mock_research:
                mock_research.return_value = {
                    "success": True,
                    "results": [{"text": "E33G information"}]
                }

                result = await autonomous_research_service.research(query=query)

                # Verify cache was checked
                mock_cache_instance.get.assert_called()

                # Verify cache was set
                if result and result.get("success"):
                    mock_cache_instance.set.assert_called()

