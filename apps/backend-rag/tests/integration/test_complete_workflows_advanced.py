"""
Complete Advanced Workflows Integration Tests
Tests extremely complex real-world workflows combining all services

Covers:
- Complete client onboarding workflow
- Complete practice lifecycle workflow
- Complete research workflow
- Complete compliance workflow
- Multi-service orchestration workflows
"""

import os
import sys
from datetime import datetime
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
class TestCompleteAdvancedWorkflows:
    """Complete advanced workflow integration tests"""

    @pytest.mark.asyncio
    async def test_complete_client_onboarding_workflow(self, db_pool):
        """Test complete client onboarding workflow"""

        async with db_pool.acquire() as conn:
            # Step 1: Initial inquiry via conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, metadata)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "onboarding_user",
                "Initial Inquiry",
                {"source": "website", "inquiry_type": "business_setup"},
            )

            # Step 2: Auto-CRM extracts client info
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "Onboarding Client",
                "onboarding@example.com",
                "+6281234567890",
                "active",
                "auto_crm",
                datetime.now(),
                datetime.now(),
            )

            # Step 3: Link conversation to client
            await conn.execute(
                """
                UPDATE conversations
                SET metadata = jsonb_set(metadata, '{client_id}', $1::text::jsonb)
                WHERE id = $2
                """,
                str(client_id),
                conversation_id,
            )

            # Step 4: Create client journey
            journey_id = await conn.fetchval(
                """
                INSERT INTO client_journeys (
                    client_id, journey_type, current_step, status, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "onboarding",
                "initial_consultation",
                "in_progress",
                {"steps_completed": 0, "total_steps": 5},
            )

            # Step 5: Create initial practices
            practices = []
            for practice_type in ["KITAS", "PT"]:
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

            # Step 6: Store preferences in shared memory
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

            # Step 7: Create welcome interaction
            await conn.execute(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, sentiment, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                client_id,
                "email",
                "Welcome email sent",
                "positive",
                "team@example.com",
                datetime.now(),
            )

            # Step 8: Generate onboarding analytics
            onboarding_complete = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    cj.id as journey_id,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT sm.id) as memory_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    cj.metadata->>'steps_completed' as steps_completed
                FROM clients c
                LEFT JOIN client_journeys cj ON c.id = cj.client_id
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                WHERE c.id = $1
                GROUP BY c.id, cj.id, cj.metadata
                """,
                client_id,
            )

            assert onboarding_complete is not None
            assert onboarding_complete["practice_count"] == len(practices)
            assert onboarding_complete["memory_count"] == 1
            assert onboarding_complete["interaction_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM shared_memory WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM client_journeys WHERE id = $1", journey_id)
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_complete_practice_lifecycle_workflow(self, db_pool):
        """Test complete practice lifecycle workflow"""

        async with db_pool.acquire() as conn:
            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
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

            # Step 2: Create practice
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
                "pending",
                "high",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 3: Document preparation phase
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "document_preparation",
                practice_id,
            )

            # Step 4: Track document collection
            await conn.execute(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                "email",
                "Documents requested",
                "team@example.com",
                datetime.now(),
            )

            # Step 5: Submission phase
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "submitted",
                practice_id,
            )

            # Step 6: Track submission
            await conn.execute(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                "note",
                "Application submitted",
                "team@example.com",
                datetime.now(),
            )

            # Step 7: Processing phase
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "in_progress",
                practice_id,
            )

            # Step 8: Completion phase
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "completed",
                practice_id,
            )

            # Step 9: Track completion
            await conn.execute(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, sentiment, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                client_id,
                "email",
                "Practice completed successfully",
                "positive",
                "team@example.com",
                datetime.now(),
            )

            # Verify complete lifecycle
            lifecycle = await conn.fetchrow(
                """
                SELECT
                    p.id,
                    p.status,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT CASE WHEN i.sentiment = 'positive' THEN i.id END) as positive_interactions
                FROM practices p
                LEFT JOIN interactions i ON p.client_id = i.client_id
                WHERE p.id = $1
                GROUP BY p.id, p.status
                """,
                practice_id,
            )

            assert lifecycle is not None
            assert lifecycle["status"] == "completed"
            assert lifecycle["interaction_count"] >= 3

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
