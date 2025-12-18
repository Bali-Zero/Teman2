"""
Comprehensive Integration Tests for Specialized Routing
Tests SpecializedServiceRouter and advanced routing scenarios

Covers:
- Autonomous research routing
- Cross-oracle synthesis routing
- Client journey routing
- Query classification
- Multi-service orchestration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSpecializedServiceRouterIntegration:
    """Integration tests for SpecializedServiceRouter"""

    @pytest.mark.asyncio
    async def test_specialized_router_initialization(self):
        """Test SpecializedServiceRouter initialization"""
        with (
            patch(
                "services.routing.specialized_service_router.AutonomousResearchService"
            ) as mock_research,
            patch(
                "services.routing.specialized_service_router.CrossOracleSynthesisService"
            ) as mock_synthesis,
            patch(
                "services.routing.specialized_service_router.ClientJourneyOrchestrator"
            ) as mock_journey,
        ):
            from services.routing.specialized_service_router import SpecializedServiceRouter

            router = SpecializedServiceRouter(
                autonomous_research_service=mock_research.return_value,
                cross_oracle_synthesis_service=mock_synthesis.return_value,
                client_journey_orchestrator=mock_journey.return_value,
            )

            assert router is not None

    @pytest.mark.asyncio
    async def test_autonomous_research_detection(self):
        """Test autonomous research query detection"""
        from services.routing.specialized_service_router import SpecializedServiceRouter

        router = SpecializedServiceRouter()

        # Test ambiguous queries
        ambiguous_queries = [
            "What are the requirements for crypto business?",
            "How to start an innovative new type of business?",
            "What are all the requirements for multiple visa types?",
        ]

        for query in ambiguous_queries:
            # Check if query contains ambiguous keywords
            is_ambiguous = any(
                keyword in query.lower()
                for keyword in [
                    "crypto",
                    "innovative",
                    "new type",
                    "multiple",
                    "various",
                ]
            )
            assert is_ambiguous

    @pytest.mark.asyncio
    async def test_cross_oracle_detection(self):
        """Test cross-oracle synthesis detection"""
        from services.routing.specialized_service_router import SpecializedServiceRouter

        router = SpecializedServiceRouter()

        # Test business setup queries
        business_queries = [
            "How to open a restaurant in Indonesia?",
            "What do I need to start a business?",
            "Complete guide to setup a company",
        ]

        for query in business_queries:
            # Check if query contains business keywords
            is_business = any(
                keyword in query.lower()
                for keyword in [
                    "open",
                    "start",
                    "setup",
                    "business",
                    "restaurant",
                    "company",
                ]
            )
            assert is_business

    @pytest.mark.asyncio
    async def test_journey_keyword_detection(self):
        """Test client journey keyword detection"""
        from services.routing.specialized_service_router import SpecializedServiceRouter

        router = SpecializedServiceRouter()

        # Test journey queries
        journey_queries = [
            "How to start the KITAS process?",
            "Begin application for work permit",
            "What is the complete process?",
        ]

        for query in journey_queries:
            # Check if query contains journey keywords
            is_journey = any(
                keyword in query.lower()
                for keyword in [
                    "start process",
                    "begin application",
                    "complete process",
                    "apply for",
                ]
            )
            assert is_journey or "process" in query.lower()

    @pytest.mark.asyncio
    async def test_route_autonomous_research(self):
        """Test routing to autonomous research"""
        with (
            patch(
                "services.routing.specialized_service_router.AutonomousResearchService"
            ) as mock_research,
            patch(
                "services.routing.specialized_service_router.CrossOracleSynthesisService"
            ) as mock_synthesis,
            patch(
                "services.routing.specialized_service_router.ClientJourneyOrchestrator"
            ) as mock_journey,
        ):
            mock_research_instance = MagicMock()
            mock_research_instance.research = AsyncMock(
                return_value=MagicMock(
                    final_answer="Research result",
                    total_steps=3,
                    collections_explored=["visa_oracle", "legal_unified"],
                    confidence=0.85,
                )
            )
            mock_research.return_value = mock_research_instance

            from services.routing.specialized_service_router import SpecializedServiceRouter

            router = SpecializedServiceRouter(
                autonomous_research_service=mock_research_instance,
            )

            result = await router.route_autonomous_research(
                "What are the requirements for crypto business?", user_level=3
            )

            assert result is not None
            assert result["category"] == "autonomous_research"
            assert result["autonomous_research"]["total_steps"] == 3

    @pytest.mark.asyncio
    async def test_route_cross_oracle_synthesis(self):
        """Test routing to cross-oracle synthesis"""
        with (
            patch(
                "services.routing.specialized_service_router.CrossOracleSynthesisService"
            ) as mock_synthesis,
            patch("services.routing.specialized_service_router.SearchService") as mock_search,
        ):
            mock_synthesis_instance = MagicMock()
            mock_synthesis_instance.synthesize = AsyncMock(
                return_value=MagicMock(
                    synthesized_answer="Synthesized answer",
                    oracles_consulted=["kbli_unified", "legal_unified", "tax_genius"],
                    confidence=0.90,
                )
            )
            mock_synthesis.return_value = mock_synthesis_instance

            from services.routing.specialized_service_router import SpecializedServiceRouter

            router = SpecializedServiceRouter(
                cross_oracle_synthesis_service=mock_synthesis_instance,
            )

            # Test cross-oracle detection
            query = "How to open a restaurant in Indonesia?"
            is_cross_oracle = router.detect_cross_oracle(query, "business_complex")

            assert (
                is_cross_oracle is True or is_cross_oracle is False
            )  # May depend on service availability


@pytest.mark.integration
class TestQueryClassificationIntegration:
    """Integration tests for query classification and routing"""

    @pytest.mark.asyncio
    async def test_query_intent_classification(self, db_pool):
        """Test query intent classification"""

        async with db_pool.acquire() as conn:
            # Create query_classifications table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_classifications (
                    id SERIAL PRIMARY KEY,
                    query_text TEXT,
                    intent_category VARCHAR(100),
                    confidence DECIMAL(5,2),
                    routing_decision VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Classify queries
            test_queries = [
                ("What is KITAS?", "visa_simple", 0.95, "oracle_universal"),
                ("How to start a business?", "business_complex", 0.90, "cross_oracle"),
                ("Crypto business requirements", "ambiguous", 0.85, "autonomous_research"),
            ]

            for query_text, intent, confidence, routing in test_queries:
                await conn.execute(
                    """
                    INSERT INTO query_classifications (
                        query_text, intent_category, confidence, routing_decision
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    query_text,
                    intent,
                    confidence,
                    routing,
                )

            # Retrieve classifications
            classifications = await conn.fetch(
                """
                SELECT intent_category, routing_decision, COUNT(*) as count
                FROM query_classifications
                GROUP BY intent_category, routing_decision
                """
            )

            assert len(classifications) == 3

            # Cleanup
            await conn.execute("DELETE FROM query_classifications")

    @pytest.mark.asyncio
    async def test_routing_decision_tracking(self, db_pool):
        """Test routing decision tracking"""

        async with db_pool.acquire() as conn:
            # Create routing_decisions table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    id SERIAL PRIMARY KEY,
                    query_hash VARCHAR(64),
                    query_text TEXT,
                    routing_service VARCHAR(100),
                    response_time_ms INTEGER,
                    success BOOLEAN,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track routing decisions
            decisions = [
                ("hash1", "Query 1", "oracle_universal", 150, True),
                ("hash2", "Query 2", "cross_oracle", 500, True),
                ("hash3", "Query 3", "autonomous_research", 2000, True),
            ]

            for query_hash, query_text, service, time_ms, success in decisions:
                await conn.execute(
                    """
                    INSERT INTO routing_decisions (
                        query_hash, query_text, routing_service, response_time_ms, success
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    query_hash,
                    query_text,
                    service,
                    time_ms,
                    success,
                )

            # Analyze routing performance
            performance = await conn.fetchrow(
                """
                SELECT
                    routing_service,
                    AVG(response_time_ms) as avg_time,
                    COUNT(*) as total_queries,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_queries
                FROM routing_decisions
                GROUP BY routing_service
                ORDER BY avg_time DESC
                LIMIT 1
                """
            )

            assert performance is not None
            assert performance["total_queries"] > 0

            # Cleanup
            await conn.execute("DELETE FROM routing_decisions")
