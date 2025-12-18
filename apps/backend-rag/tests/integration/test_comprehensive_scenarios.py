"""
Comprehensive Real-World Scenarios Integration Tests
Tests complex real-world scenarios combining multiple services

Covers:
- Complete client onboarding flow
- Multi-step practice management
- Complex query processing with context
- Team collaboration scenarios
- Compliance monitoring workflows
- Knowledge graph building scenarios
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestClientOnboardingScenario:
    """Complete client onboarding scenario"""

    @pytest.mark.asyncio
    async def test_complete_client_onboarding(self, db_pool):
        """Test complete client onboarding flow"""

        async with db_pool.acquire() as conn:
            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "New Client Onboarding",
                "onboarding@example.com",
                "+6281234567890",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Create initial practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "document_preparation",
                "high",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 3: Log initial interaction
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, sentiment, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "consultation",
                "Initial consultation for KITAS application",
                "positive",
                "team@example.com",
                datetime.now(),
            )

            # Step 4: Store client preferences in shared memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "preference",
                "Client prefers email communication and English language",
                ["communication", "language", "preference"],
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 5: Create compliance monitoring entry
            alert_id = await conn.fetchval(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "new_client",
                "info",
                "New client onboarded - monitor practice progress",
                {"practice_id": practice_id, "onboarding_date": datetime.now().isoformat()},
            )

            # Verify complete onboarding
            client_data = await conn.fetchrow(
                """
                SELECT
                    c.id,
                    c.full_name,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT sm.id) as memory_count,
                    COUNT(DISTINCT ca.id) as alert_count
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                LEFT JOIN compliance_alerts ca ON c.id = ca.client_id
                WHERE c.id = $1
                GROUP BY c.id, c.full_name
                """,
                client_id,
            )

            assert client_data is not None
            assert client_data["practice_count"] == 1
            assert client_data["interaction_count"] == 1
            assert client_data["memory_count"] == 1
            assert client_data["alert_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM shared_memory WHERE id = $1", memory_id)
            await conn.execute("DELETE FROM interactions WHERE id = $1", interaction_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
@pytest.mark.slow
class TestMultiStepPracticeScenario:
    """Multi-step practice management scenario"""

    @pytest.mark.asyncio
    async def test_practice_lifecycle_management(self, db_pool):
        """Test complete practice lifecycle"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Practice Lifecycle Client",
                "practice.lifecycle@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 1: Create practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "PT",
                "document_preparation",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Update to document_review
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = $2
                WHERE id = $3
                """,
                "document_review",
                datetime.now(),
                practice_id,
            )

            # Step 3: Log review interaction
            await conn.execute(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                "review",
                "Documents reviewed and approved",
                "team@example.com",
                datetime.now(),
            )

            # Step 4: Update to submission
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = $2
                WHERE id = $3
                """,
                "submission",
                datetime.now(),
                practice_id,
            )

            # Step 5: Create compliance alert for submission deadline
            await conn.execute(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                "submission_deadline",
                "warning",
                "Practice submitted - monitor approval status",
                {"practice_id": practice_id, "submission_date": datetime.now().isoformat()},
            )

            # Step 6: Update to completed
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = $2
                WHERE id = $3
                """,
                "completed",
                datetime.now(),
                practice_id,
            )

            # Verify lifecycle
            practice = await conn.fetchrow(
                """
                SELECT status FROM practices WHERE id = $1
                """,
                practice_id,
            )

            assert practice["status"] == "completed"

            # Verify interactions
            interactions = await conn.fetch(
                """
                SELECT interaction_type FROM interactions WHERE client_id = $1
                """,
                client_id,
            )

            assert len(interactions) >= 1

            # Cleanup
            await conn.execute("DELETE FROM compliance_alerts WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
@pytest.mark.slow
class TestComplexQueryScenario:
    """Complex query processing scenario"""

    @pytest.mark.asyncio
    async def test_multi_collection_query_processing(self, qdrant_client, db_pool):
        """Test complex query across multiple collections"""
        from services.query_router import QueryRouter
        from services.search_service import SearchService

        # Mock dependencies
        with (
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
            patch(
                "services.cross_oracle_synthesis_service.CrossOracleSynthesisService"
            ) as mock_synthesis,
        ):
            embedder = MagicMock()
            embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
            embedder.provider = "openai"
            embedder.dimensions = 1536
            mock_embedder.return_value = embedder

            # Mock synthesis service
            mock_synthesis_instance = MagicMock()
            mock_synthesis_instance.synthesize = AsyncMock(
                return_value="Synthesized response from multiple sources..."
            )
            mock_synthesis.return_value = mock_synthesis_instance

            # Complex query requiring multiple collections
            query = "How to start a business in Indonesia including tax requirements and legal structure?"

            # Route query
            router = QueryRouter()
            routing_result = await router.route_query(query)

            assert routing_result is not None

            # Search across multiple collections
            collections = ["kbli_unified", "legal_unified", "tax_genius"]
            search_service = SearchService()

            all_results = []
            for collection in collections:
                result = await search_service.search(query, user_level=1, limit=5)
                if result and "results" in result:
                    all_results.extend(result["results"])

            # Synthesize results
            synthesized = await mock_synthesis_instance.synthesize(
                query=query, documents=all_results
            )

            assert synthesized is not None
            assert len(synthesized) > 0

            # Store query analytics

            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oracle_query_analytics (
                        id SERIAL PRIMARY KEY,
                        query_text TEXT,
                        collections_used TEXT[],
                        document_count INTEGER,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                await conn.execute(
                    """
                    INSERT INTO oracle_query_analytics (
                        query_text, collections_used, document_count
                    )
                    VALUES ($1, $2, $3)
                    """,
                    query,
                    collections,
                    len(all_results),
                )

                # Verify storage
                analytics = await conn.fetchrow(
                    """
                    SELECT collections_used, document_count
                    FROM oracle_query_analytics
                    WHERE query_text = $1
                    """,
                    query,
                )

                assert analytics is not None
                assert len(analytics["collections_used"]) == 3

                # Cleanup
                await conn.execute(
                    "DELETE FROM oracle_query_analytics WHERE query_text = $1", query
                )


@pytest.mark.integration
@pytest.mark.slow
class TestTeamCollaborationScenario:
    """Team collaboration scenario"""

    @pytest.mark.asyncio
    async def test_team_collaboration_workflow(self, db_pool):
        """Test team collaboration on client work"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Collaboration Client",
                "collab@example.com",
                "active",
                "team1@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Team member 1 creates practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                "team1@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Team member 2 adds shared memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "note",
                "Client mentioned preference for fast processing",
                "team2@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Team member 3 logs interaction
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "call",
                "Follow-up call with client - all documents ready",
                "team3@example.com",
                datetime.now(),
            )

            # Verify team collaboration
            team_activities = await conn.fetch(
                """
                SELECT
                    'practice' as activity_type,
                    created_by as team_member
                FROM practices WHERE client_id = $1
                UNION ALL
                SELECT
                    'memory' as activity_type,
                    created_by as team_member
                FROM shared_memory WHERE client_id = $1
                UNION ALL
                SELECT
                    'interaction' as activity_type,
                    created_by as team_member
                FROM interactions WHERE client_id = $1
                """,
                client_id,
            )

            assert len(team_activities) == 3
            team_members = {activity["team_member"] for activity in team_activities}
            assert len(team_members) == 3  # Three different team members

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE id = $1", interaction_id)
            await conn.execute("DELETE FROM shared_memory WHERE id = $1", memory_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
@pytest.mark.slow
class TestComplianceMonitoringScenario:
    """Compliance monitoring scenario"""

    @pytest.mark.asyncio
    async def test_compliance_monitoring_workflow(self, db_pool):
        """Test compliance monitoring workflow"""

        async with db_pool.acquire() as conn:
            # Create client with practice
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Compliance Client",
                "compliance@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, expiry_date, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "active",
                datetime.now().date() + timedelta(days=30),
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create compliance alerts for different scenarios
            alerts = []

            # Alert 1: Expiry warning
            alert1_id = await conn.fetchval(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "expiry_warning",
                "warning",
                "Practice expires in 30 days",
                {"practice_id": practice_id, "days_remaining": 30},
            )
            alerts.append(alert1_id)

            # Alert 2: Document missing
            alert2_id = await conn.fetchval(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "document_missing",
                "urgent",
                "Required document missing",
                {"practice_id": practice_id, "document_type": "passport"},
            )
            alerts.append(alert2_id)

            # Query alerts by severity
            critical_alerts = await conn.fetch(
                """
                SELECT id, alert_type, severity
                FROM compliance_alerts
                WHERE client_id = $1 AND severity = $2
                """,
                client_id,
                "urgent",
            )

            assert len(critical_alerts) == 1

            # Query alerts by type
            expiry_alerts = await conn.fetch(
                """
                SELECT id, alert_type
                FROM compliance_alerts
                WHERE client_id = $1 AND alert_type = $2
                """,
                client_id,
                "expiry_warning",
            )

            assert len(expiry_alerts) == 1

            # Cleanup
            for alert_id in alerts:
                await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
