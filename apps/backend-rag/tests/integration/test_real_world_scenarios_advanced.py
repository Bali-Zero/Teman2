"""
Real-World Advanced Scenarios Integration Tests
Tests extremely realistic real-world scenarios

Covers:
- Complete business setup scenario
- Multi-client portfolio management
- Complex legal research scenario
- Complete compliance monitoring scenario
- Multi-channel communication scenario
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
class TestRealWorldAdvancedScenarios:
    """Real-world advanced scenario integration tests"""

    @pytest.mark.asyncio
    async def test_complete_business_setup_scenario(self, db_pool):
        """Test complete business setup scenario"""

        async with db_pool.acquire() as conn:
            # Scenario: New client wants to start a restaurant business in Bali
            # Step 1: Initial inquiry
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "Restaurant Business Owner",
                "restaurant@example.com",
                "+6281234567890",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Create multiple practices
            practices = []
            practice_types = ["PT", "KITAS", "Tax Registration", "Business License", "Food License"]

            for practice_type in practice_types:
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
                {
                    "practices": practices,
                    "total_steps": 15,
                    "current_step": 1,
                    "estimated_completion": "2025-03-01",
                },
            )

            # Step 4: Multiple interactions
            interaction_types = ["consultation", "email", "call", "meeting", "note"]

            for i, interaction_type in enumerate(interaction_types):
                await conn.execute(
                    """
                    INSERT INTO interactions (
                        client_id, interaction_type, summary, sentiment, created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    client_id,
                    interaction_type,
                    f"{interaction_type.capitalize()} about {practice_types[i % len(practice_types)]}",
                    "positive" if i % 2 == 0 else "neutral",
                    "team@example.com",
                    datetime.now() - timedelta(days=i),
                )

            # Step 5: Store preferences and notes
            await conn.execute(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                client_id,
                "preference",
                "Client prefers WhatsApp for urgent matters and email for documentation",
                ["communication", "preference"],
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

            # Step 7: Generate complete scenario analytics
            scenario = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT sm.id) as memory_count,
                    COUNT(DISTINCT ca.id) as alert_count,
                    COUNT(DISTINCT cj.id) as journey_count,
                    cj.metadata->>'current_step' as current_step,
                    cj.metadata->>'total_steps' as total_steps
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                LEFT JOIN compliance_alerts ca ON c.id = ca.client_id
                LEFT JOIN client_journeys cj ON c.id = cj.client_id
                WHERE c.id = $1
                GROUP BY c.id, cj.id, cj.metadata
                """,
                client_id,
            )

            assert scenario is not None
            assert scenario["practice_count"] == len(practices)
            assert scenario["interaction_count"] == len(interaction_types)
            assert scenario["memory_count"] == 1
            assert scenario["alert_count"] == 1
            assert scenario["journey_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM compliance_alerts WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM shared_memory WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM client_journeys WHERE id = $1", journey_id)
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_multi_client_portfolio_management(self, db_pool):
        """Test multi-client portfolio management scenario"""

        async with db_pool.acquire() as conn:
            # Create portfolio of 10 clients
            client_ids = []
            for i in range(10):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    f"Portfolio Client {i + 1}",
                    f"portfolio{i + 1}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

                # Create 2-3 practices per client
                practice_count = 2 + (i % 2)
                for j in range(practice_count):
                    await conn.execute(
                        """
                        INSERT INTO practices (
                            client_id, practice_type, status, priority, created_by, created_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        client_id,
                        f"Practice {j + 1}",
                        "in_progress" if j % 2 == 0 else "pending",
                        "high" if i < 3 else "medium",
                        "team@example.com",
                        datetime.now(),
                        datetime.now(),
                    )

            # Portfolio analytics
            portfolio = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT c.id) as total_clients,
                    COUNT(DISTINCT p.id) as total_practices,
                    COUNT(DISTINCT CASE WHEN p.status = 'in_progress' THEN p.id END) as active_practices,
                    COUNT(DISTINCT CASE WHEN p.priority = 'high' THEN p.id END) as high_priority_practices,
                    AVG(practice_counts.count) as avg_practices_per_client
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN (
                    SELECT client_id, COUNT(*) as count
                    FROM practices
                    GROUP BY client_id
                ) practice_counts ON c.id = practice_counts.client_id
                WHERE c.id = ANY($1)
                GROUP BY c.id
                """,
                client_ids,
            )

            assert portfolio is not None
            assert portfolio["total_clients"] == 10
            assert portfolio["total_practices"] > 0

            # Cleanup
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
    async def test_complex_legal_research_scenario(self, qdrant_client, db_pool):
        """Test complex legal research scenario"""

        async with db_pool.acquire() as conn:
            # Scenario: Research multiple legal topics
            research_topics = [
                "KITAS requirements",
                "PT company setup",
                "Tax obligations",
                "Business licensing",
            ]

            # Create research session
            session_id = await conn.fetchval(
                """
                INSERT INTO research_sessions (
                    user_id, research_topic, status, created_at
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "legal_researcher",
                "Business Setup Legal Research",
                "in_progress",
                datetime.now(),
            )

            # Search across multiple collections
            collections = ["visa_oracle", "legal_unified", "kbli_unified", "tax_genius"]

            for i, topic in enumerate(research_topics):
                collection_name = collections[i % len(collections)]

                try:
                    await qdrant_client.create_collection(
                        collection_name=collection_name, vector_size=1536
                    )

                    test_embedding = [0.1 + (i * 0.1)] * 1536
                    await qdrant_client.upsert(
                        collection_name=collection_name,
                        points=[
                            {
                                "id": f"research_{topic}_{i}",
                                "vector": test_embedding,
                                "payload": {
                                    "text": f"Information about {topic}",
                                    "topic": topic,
                                    "collection": collection_name,
                                },
                            }
                        ],
                    )

                    # Store research result
                    await conn.execute(
                        """
                        INSERT INTO research_results (
                            session_id, topic, collection_name, result_count, created_at
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        session_id,
                        topic,
                        collection_name,
                        1,
                        datetime.now(),
                    )

                except Exception:
                    pass  # Collection might already exist

            # Research summary
            research_summary = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT topic) as topics_researched,
                    COUNT(DISTINCT collection_name) as collections_searched,
                    SUM(result_count) as total_results
                FROM research_results
                WHERE session_id = $1
                """,
                session_id,
            )

            assert research_summary is not None
            assert research_summary["topics_researched"] == len(research_topics)

            # Cleanup
            await conn.execute("DELETE FROM research_results WHERE session_id = $1", session_id)
            await conn.execute("DELETE FROM research_sessions WHERE id = $1", session_id)










