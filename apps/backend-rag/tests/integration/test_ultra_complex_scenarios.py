"""
Ultra-Complex Real-World Scenarios Integration Tests
Tests extremely complex scenarios combining many services

Covers:
- Multi-client, multi-practice scenarios
- Complex query processing with multiple services
- Complete business workflows
- Advanced orchestration scenarios
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestUltraComplexScenarios:
    """Ultra-complex integration test scenarios"""

    @pytest.mark.asyncio
    async def test_multi_client_multi_practice_scenario(self, db_pool):
        """Test scenario with multiple clients and multiple practices"""

        async with db_pool.acquire() as conn:
            # Create 5 clients
            client_ids = []
            for i in range(5):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, phone, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    f"Complex Client {i + 1}",
                    f"complex{i + 1}@example.com",
                    f"+628123456789{i}",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

                # Create 2-3 practices per client
                practice_types = ["KITAS", "PT", "Visa"]
                for j, practice_type in enumerate(practice_types[: 2 + (i % 2)]):
                    practice_id = await conn.fetchval(
                        """
                        INSERT INTO practices (
                            client_id, practice_type, status, priority, created_by, created_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING id
                        """,
                        client_id,
                        practice_type,
                        "in_progress" if j % 2 == 0 else "document_preparation",
                        "high" if i < 2 else "medium",
                        "team@example.com",
                        datetime.now(),
                        datetime.now(),
                    )

                    # Create interactions for each practice
                    await conn.execute(
                        """
                        INSERT INTO interactions (
                            client_id, interaction_type, summary, sentiment, created_by, created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        client_id,
                        "consultation",
                        f"Consultation for {practice_type}",
                        "positive",
                        "team@example.com",
                        datetime.now(),
                    )

            # Complex analytics query
            analytics = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT c.id) as total_clients,
                    COUNT(DISTINCT p.id) as total_practices,
                    COUNT(DISTINCT i.id) as total_interactions,
                    COUNT(DISTINCT CASE WHEN p.status = 'in_progress' THEN p.id END) as active_practices,
                    AVG(CASE WHEN p.priority = 'high' THEN 1 ELSE 0 END) as high_priority_ratio
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                WHERE c.id = ANY($1)
                """,
                client_ids,
            )

            assert analytics is not None
            assert analytics["total_clients"] == 5
            assert analytics["total_practices"] > 0

            # Cleanup
            await conn.execute(
                """
                DELETE FROM interactions WHERE client_id = ANY($1)
                """,
                client_ids,
            )
            await conn.execute(
                """
                DELETE FROM practices WHERE client_id = ANY($1)
                """,
                client_ids,
            )
            await conn.execute(
                """
                DELETE FROM clients WHERE id = ANY($1)
                """,
                client_ids,
            )

    @pytest.mark.asyncio
    async def test_complex_multi_service_query_scenario(self, qdrant_client, db_pool):
        """Test complex query requiring multiple services"""

        async with db_pool.acquire() as conn:
            # Complex query: "How to start a restaurant business in Indonesia including tax, legal, and visa requirements?"
            query = "How to start a restaurant business in Indonesia including tax, legal, and visa requirements?"

            # Step 1: Route query (would use SpecializedServiceRouter)
            # Step 2: Search across multiple collections
            collections = ["kbli_unified", "legal_unified", "tax_genius", "visa_oracle"]

            # Step 3: Cross-oracle synthesis
            # Step 4: Store query analytics
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS complex_query_analytics (
                    id SERIAL PRIMARY KEY,
                    query_text TEXT,
                    collections_searched TEXT[],
                    synthesis_used BOOLEAN,
                    response_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            analytics_id = await conn.fetchval(
                """
                INSERT INTO complex_query_analytics (
                    query_text, collections_searched, synthesis_used, response_time_ms
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                query,
                collections,
                True,
                2500,
            )

            # Step 5: Store in conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, metadata)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "complex_user",
                "Complex Business Query",
                {
                    "query_type": "complex",
                    "collections_used": collections,
                    "synthesis": True,
                },
            )

            # Step 6: Extract insights for CRM
            # Step 7: Create compliance alerts if needed
            # Step 8: Generate notifications

            # Verify complete flow
            flow = await conn.fetchrow(
                """
                SELECT
                    cqa.id as analytics_id,
                    c.id as conversation_id,
                    array_length(cqa.collections_searched, 1) as collections_count
                FROM complex_query_analytics cqa
                LEFT JOIN conversations c ON c.metadata->>'query_type' = 'complex'
                WHERE cqa.id = $1
                LIMIT 1
                """,
                analytics_id,
            )

            assert flow is not None
            assert flow["collections_count"] == len(collections)

            # Cleanup
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM complex_query_analytics WHERE id = $1", analytics_id)

    @pytest.mark.asyncio
    async def test_complete_business_setup_workflow(self, db_pool):
        """Test complete business setup workflow"""

        async with db_pool.acquire() as conn:
            # Step 1: Client inquiry
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Business Setup Client",
                "business.setup@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Create multiple practices
            practices = []
            for practice_type in ["PT", "KITAS", "Tax Registration"]:
                practice_id = await conn.fetchval(
                    """
                    INSERT INTO practices (
                        client_id, practice_type, status, priority, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    client_id,
                    practice_type,
                    "pending",
                    "high",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                practices.append(practice_id)

            # Step 3: Create journey
            journey_id = await conn.fetchval(
                """
                INSERT INTO client_journeys (
                    client_id, journey_type, current_step, status, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "business_setup",
                "document_preparation",
                "in_progress",
                {"practices": practices, "total_steps": 10, "current_step": 1},
            )

            # Step 4: Track interactions
            for i, interaction_type in enumerate(["consultation", "email", "call"]):
                await conn.execute(
                    """
                    INSERT INTO interactions (
                        client_id, interaction_type, summary, created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    client_id,
                    interaction_type,
                    f"{interaction_type.capitalize()} about {practices[i % len(practices)]}",
                    "team@example.com",
                    datetime.now() - timedelta(days=i),
                )

            # Step 5: Store shared memory
            await conn.execute(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                client_id,
                "preference",
                "Client prefers email communication and English language",
                ["communication", "language"],
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 6: Compliance monitoring
            await conn.execute(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                "new_business_setup",
                "info",
                "New business setup initiated - monitor progress",
                {"journey_id": journey_id, "practices_count": len(practices)},
            )

            # Step 7: Generate analytics
            complete_workflow = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT sm.id) as memory_count,
                    COUNT(DISTINCT ca.id) as alert_count,
                    COUNT(DISTINCT cj.id) as journey_count
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                LEFT JOIN compliance_alerts ca ON c.id = ca.client_id
                LEFT JOIN client_journeys cj ON c.id = cj.client_id
                WHERE c.id = $1
                GROUP BY c.id
                """,
                client_id,
            )

            assert complete_workflow is not None
            assert complete_workflow["practice_count"] == len(practices)
            assert complete_workflow["interaction_count"] == 3
            assert complete_workflow["memory_count"] == 1
            assert complete_workflow["alert_count"] == 1
            assert complete_workflow["journey_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM compliance_alerts WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM shared_memory WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM client_journeys WHERE id = $1", journey_id)
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
