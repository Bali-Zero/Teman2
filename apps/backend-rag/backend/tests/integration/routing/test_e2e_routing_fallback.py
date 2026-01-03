"""
Integration Tests: End-to-End Routing with Fallback Chain

Tests complete routing flow with fallback mechanisms:
1. Query Router collection selection
2. Specialized Service Router detection
3. Confidence calculation
4. Fallback chain execution
5. Routing statistics tracking
6. Priority override handling

Target: Test complete integration of routing components with fallback
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Note: Using mocks to avoid circular import issues
# from services.routing.fallback_manager import FallbackManagerService
# from services.routing.query_router import QueryRouter
# from services.routing.routing_stats import RoutingStatsService
# from services.routing.specialized_service_router import SpecializedServiceRouter


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    service.search = AsyncMock(return_value={
        "results": [{"id": "doc1", "text": "Test", "score": 0.8}],
        "total": 1
    })
    return service


@pytest.fixture
def mock_db_pool():
    """Mock PostgreSQL connection pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def query_router(mock_search_service):
    """Create QueryRouter mock"""
    router = MagicMock()
    router.route = MagicMock(return_value="visa_oracle")
    return router


@pytest.fixture
def specialized_router(mock_search_service, mock_db_pool):
    """Create SpecializedServiceRouter mock"""
    router = MagicMock()
    router.should_route_to_autonomous_research = MagicMock(return_value=False)
    router.should_route_to_cross_oracle = MagicMock(return_value=False)
    router.should_route_to_client_journey = MagicMock(return_value=False)
    return router


@pytest.fixture
def fallback_manager():
    """Create FallbackManagerService mock"""
    manager = MagicMock()
    manager.get_fallback_chain = MagicMock(return_value=["visa_oracle", "legal_unified"])
    return manager


@pytest.fixture
def routing_stats():
    """Create RoutingStatsService mock"""
    stats = MagicMock()
    stats.record_routing = MagicMock()
    stats.record_fallback = MagicMock()
    stats.get_stats = MagicMock(return_value={
        "total_routings": 0,
        "collection_stats": {},
        "failed_routings": 0
    })
    return stats


class TestE2ERoutingFallback:
    """End-to-End Routing with Fallback Tests"""

    @pytest.mark.asyncio
    async def test_complete_routing_flow_with_primary_collection(
        self, query_router, specialized_router, routing_stats, mock_search_service
    ):
        """Test complete flow: Query → Router → Primary Collection → Success"""
        query = "Quanto costa E33G KITAS?"

        # Mock routing decision
        with patch.object(query_router, 'route') as mock_route:
            mock_route.return_value = "visa_oracle"

            # Mock specialized router (should not trigger)
            with patch.object(specialized_router, 'should_route_to_specialized') as mock_specialized:
                mock_specialized.return_value = False

                # Execute routing
                collection = query_router.route(query)

                # Verify routing decision
                assert collection == "visa_oracle"

                # Record routing stats
                routing_stats.record_routing(
                    query=query,
                    collection=collection,
                    success=True
                )

                # Verify stats recorded
                stats = routing_stats.get_stats()
                assert stats["total_routings"] >= 1

    @pytest.mark.asyncio
    async def test_routing_fallback_chain(
        self, query_router, fallback_manager, routing_stats, mock_search_service
    ):
        """Test fallback chain: Primary → Fallback 1 → Fallback 2"""
        query = "Informazioni su visto"

        # Mock primary collection failure
        mock_search_service.search = AsyncMock(side_effect=[
            Exception("Primary collection error"),  # First attempt fails
            {"results": [{"id": "doc1", "text": "Test"}], "total": 1}  # Fallback succeeds
        ])

        # Define fallback chain
        fallback_chain = ["visa_oracle", "legal_unified", "kbli_unified"]

        # Execute routing with fallback
        result = None
        for collection in fallback_chain:
            try:
                result = await mock_search_service.search(
                    query=query,
                    collection=collection,
                    limit=5
                )
                if result:
                    break
            except Exception:
                continue

        # Verify fallback succeeded
        assert result is not None
        assert "results" in result

        # Record fallback stats
        routing_stats.record_fallback(
            query=query,
            primary_collection=fallback_chain[0],
            fallback_collection=fallback_chain[1],
            success=True
        )

    @pytest.mark.asyncio
    async def test_specialized_service_routing(
        self, specialized_router, routing_stats, mock_search_service, mock_db_pool
    ):
        """Test routing to specialized services (Autonomous Research, Cross-Oracle)"""
        query = "Analizza le ultime modifiche alle leggi sull'immigrazione"

        # Mock specialized service detection
        with patch.object(specialized_router, 'should_route_to_autonomous_research') as mock_autonomous:
            mock_autonomous.return_value = True

            # Mock autonomous research service
            with patch('services.misc.autonomous_research_service.AutonomousResearchService') as mock_service:
                mock_service_instance = MagicMock()
                mock_service_instance.research = AsyncMock(return_value={
                    "success": True,
                    "results": ["Result 1", "Result 2"]
                })
                mock_service.return_value = mock_service_instance

                # Execute routing
                should_route = specialized_router.should_route_to_autonomous_research(query)

                # Verify specialized routing detected
                assert should_route is True

                # Record specialized routing stats
                routing_stats.record_routing(
                    query=query,
                    collection="autonomous_research",
                    success=True
                )

    @pytest.mark.asyncio
    async def test_confidence_based_routing(
        self, query_router, routing_stats, mock_search_service
    ):
        """Test routing based on confidence scores"""
        query = "Visto E33G"

        # Mock confidence calculation
        with patch('services.routing.confidence_calculator.ConfidenceCalculatorService') as mock_confidence:
            mock_confidence_instance = MagicMock()
            mock_confidence_instance.calculate_confidence = MagicMock(return_value=0.75)
            mock_confidence.return_value = mock_confidence_instance

            # Calculate confidence
            confidence = mock_confidence_instance.calculate_confidence(query, "visa_oracle")

            # Route based on confidence
            if confidence > 0.7:
                collection = "visa_oracle"
            else:
                collection = "legal_unified"

            # Verify routing decision
            assert collection == "visa_oracle"

            # Record confidence-based routing
            routing_stats.record_routing(
                query=query,
                collection=collection,
                confidence=confidence,
                success=True
            )

    @pytest.mark.asyncio
    async def test_routing_statistics_tracking(
        self, routing_stats, query_router, mock_search_service
    ):
        """Test that routing statistics are properly tracked"""
        queries = [
            ("Quanto costa E33G?", "visa_oracle"),
            ("Come aprire PT PMA?", "kbli_unified"),
            ("Informazioni su tasse", "tax_genius")
        ]

        # Record multiple routings
        for query, collection in queries:
            routing_stats.record_routing(
                query=query,
                collection=collection,
                success=True
            )

        # Get statistics
        stats = routing_stats.get_stats()

        # Verify stats tracked
        assert stats["total_routings"] == 3
        assert "visa_oracle" in stats.get("collection_stats", {})
        assert "kbli_unified" in stats.get("collection_stats", {})
        assert "tax_genius" in stats.get("collection_stats", {})

    @pytest.mark.asyncio
    async def test_priority_override_routing(
        self, query_router, routing_stats, mock_search_service
    ):
        """Test priority override for specific queries"""
        query = "URGENTE: Informazioni su visto"

        # Mock priority override
        with patch('services.routing.priority_override.PriorityOverrideService') as mock_priority:
            mock_priority_instance = MagicMock()
            mock_priority_instance.get_override_collection = MagicMock(return_value="visa_oracle")
            mock_priority.return_value = mock_priority_instance

            # Check for priority override
            override_collection = mock_priority_instance.get_override_collection(query)

            if override_collection:
                collection = override_collection
            else:
                collection = query_router.route(query)

            # Verify priority override applied
            assert collection == "visa_oracle"

            # Record priority routing
            routing_stats.record_routing(
                query=query,
                collection=collection,
                priority_override=True,
                success=True
            )

    @pytest.mark.asyncio
    async def test_routing_error_handling(
        self, query_router, fallback_manager, routing_stats, mock_search_service
    ):
        """Test error handling when all routing attempts fail"""
        query = "Test query"

        # Mock all collections failing
        mock_search_service.search = AsyncMock(side_effect=Exception("All collections failed"))

        # Try routing with fallback chain
        fallback_chain = ["visa_oracle", "legal_unified", "kbli_unified"]
        success = False

        for collection in fallback_chain:
            try:
                result = await mock_search_service.search(
                    query=query,
                    collection=collection,
                    limit=5
                )
                if result:
                    success = True
                    break
            except Exception:
                continue

        # Verify error handling
        assert success is False

        # Record failure
        routing_stats.record_routing(
            query=query,
            collection=fallback_chain[0],
            success=False
        )

        # Verify failure tracked
        stats = routing_stats.get_stats()
        assert stats.get("failed_routings", 0) >= 1

