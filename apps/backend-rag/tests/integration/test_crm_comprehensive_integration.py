"""
Comprehensive Integration Tests for CRM System
Tests complete CRM workflows with real PostgreSQL database

Covers:
- Client CRUD operations
- Practice management
- Interaction tracking
- Shared memory
- Analytics and reporting
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestCRMComprehensiveIntegration:
    """Comprehensive integration tests for CRM system with real PostgreSQL"""

    @pytest.mark.asyncio
    async def test_client_lifecycle(self, db_pool):
        """Test complete client lifecycle: create, read, update, delete"""
        async with db_pool.acquire() as conn:
            # Create test client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, phone, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "Test Client Integration",
                "test.client@example.com",
                "+6281234567890",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert client_id is not None

            # Read client
            client = await conn.fetchrow(
                "SELECT id, full_name, email, status FROM clients WHERE id = $1", client_id
            )
            assert client is not None
            assert client["full_name"] == "Test Client Integration"
            assert client["status"] == "active"

            # Update client
            await conn.execute(
                """
                UPDATE clients
                SET full_name = $1, status = $2, updated_at = $3
                WHERE id = $4
                """,
                "Updated Client Name",
                "inactive",
                datetime.now(),
                client_id,
            )

            # Verify update
            updated_client = await conn.fetchrow(
                "SELECT full_name, status FROM clients WHERE id = $1", client_id
            )
            assert updated_client["full_name"] == "Updated Client Name"
            assert updated_client["status"] == "inactive"

            # Delete client
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

            # Verify deletion
            deleted_client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
            assert deleted_client is None

    @pytest.mark.asyncio
    async def test_practice_workflow(self, db_pool):
        """Test practice creation and management workflow"""
        async with db_pool.acquire() as conn:
            # Create client first
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Practice Test Client",
                "practice.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (client_id, practice_type, status, priority, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                "high",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert practice_id is not None

            # Link practice to client
            practice = await conn.fetchrow(
                """
                SELECT p.id, p.practice_type, p.status, c.full_name
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                WHERE p.id = $1
                """,
                practice_id,
            )

            assert practice is not None
            assert practice["practice_type"] == "KITAS"
            assert practice["full_name"] == "Practice Test Client"

            # Update practice status
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

            # Verify status update
            updated_practice = await conn.fetchrow(
                "SELECT status FROM practices WHERE id = $1", practice_id
            )
            assert updated_practice["status"] == "completed"

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_interaction_tracking(self, db_pool):
        """Test interaction logging and retrieval"""
        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Interaction Test Client",
                "interaction.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create multiple interactions
            interaction_ids = []
            for i, interaction_type in enumerate(["chat", "email", "call"]):
                interaction_id = await conn.fetchval(
                    """
                    INSERT INTO interactions (
                        client_id, interaction_type, summary, sentiment,
                        created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    client_id,
                    interaction_type,
                    f"Test interaction {i + 1}",
                    "positive",
                    "test@team.com",
                    datetime.now() - timedelta(days=i),
                )
                interaction_ids.append(interaction_id)

            # Retrieve interactions for client
            interactions = await conn.fetch(
                """
                SELECT id, interaction_type, summary, sentiment
                FROM interactions
                WHERE client_id = $1
                ORDER BY created_at DESC
                """,
                client_id,
            )

            assert len(interactions) == 3
            assert interactions[0]["interaction_type"] == "chat"
            assert interactions[1]["interaction_type"] == "email"
            assert interactions[2]["interaction_type"] == "call"

            # Test filtering by type
            chat_interactions = await conn.fetch(
                """
                SELECT id FROM interactions
                WHERE client_id = $1 AND interaction_type = $2
                """,
                client_id,
                "chat",
            )
            assert len(chat_interactions) == 1

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_shared_memory_operations(self, db_pool):
        """Test shared memory CRUD operations"""
        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Memory Test Client",
                "memory.test@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Create shared memory entry
            memory_id = await conn.fetchval(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags,
                    created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "preference",
                "Client prefers email communication",
                ["communication", "preference"],
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert memory_id is not None

            # Retrieve memory
            memory = await conn.fetchrow(
                """
                SELECT id, memory_type, content, tags
                FROM shared_memory
                WHERE id = $1
                """,
                memory_id,
            )

            assert memory is not None
            assert memory["memory_type"] == "preference"
            assert "email" in memory["content"].lower()

            # Update memory
            await conn.execute(
                """
                UPDATE shared_memory
                SET content = $1, updated_at = $2
                WHERE id = $3
                """,
                "Client prefers WhatsApp communication",
                datetime.now(),
                memory_id,
            )

            # Verify update
            updated_memory = await conn.fetchrow(
                "SELECT content FROM shared_memory WHERE id = $1", memory_id
            )
            assert "WhatsApp" in updated_memory["content"]

            # Test memory search by tags
            tagged_memories = await conn.fetch(
                """
                SELECT id FROM shared_memory
                WHERE client_id = $1 AND $2 = ANY(tags)
                """,
                client_id,
                "communication",
            )
            assert len(tagged_memories) == 1

            # Cleanup
            await conn.execute("DELETE FROM shared_memory WHERE id = $1", memory_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_crm_analytics_queries(self, db_pool):
        """Test CRM analytics and reporting queries"""
        async with db_pool.acquire() as conn:
            # Create test data
            client_ids = []
            for i in range(3):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    f"Analytics Client {i + 1}",
                    f"analytics{i + 1}@example.com",
                    "active",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

                # Add practices
                await conn.execute(
                    """
                    INSERT INTO practices (client_id, practice_type, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    client_id,
                    "KITAS" if i % 2 == 0 else "PT",
                    "in_progress",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )

                # Add interactions
                await conn.execute(
                    """
                    INSERT INTO interactions (client_id, interaction_type, summary, created_by, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    client_id,
                    "chat",
                    f"Interaction {i + 1}",
                    "test@team.com",
                    datetime.now(),
                )

            # Test client count by status
            active_clients = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE status = $1", "active"
            )
            assert active_clients == 3

            # Test practice count by type
            kitas_count = await conn.fetchval(
                "SELECT COUNT(*) FROM practices WHERE practice_type = $1", "KITAS"
            )
            assert kitas_count == 2

            # Test interaction count
            interaction_count = await conn.fetchval(
                "SELECT COUNT(*) FROM interactions WHERE interaction_type = $1", "chat"
            )
            assert interaction_count == 3

            # Test client with most interactions
            top_client = await conn.fetchrow(
                """
                SELECT c.id, c.full_name, COUNT(i.id) as interaction_count
                FROM clients c
                LEFT JOIN interactions i ON c.id = i.client_id
                GROUP BY c.id, c.full_name
                ORDER BY interaction_count DESC
                LIMIT 1
                """
            )
            assert top_client is not None
            assert top_client["interaction_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE client_id = ANY($1)", client_ids)
            await conn.execute("DELETE FROM practices WHERE client_id = ANY($1)", client_ids)
            await conn.execute("DELETE FROM clients WHERE id = ANY($1)", client_ids)

    @pytest.mark.asyncio
    async def test_crm_transaction_rollback(self, db_pool):
        """Test transaction rollback on error"""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create client
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    "Transaction Test Client",
                    "transaction.test@example.com",
                    "active",
                    "test@team.com",
                    datetime.now(),
                    datetime.now(),
                )

                # Try to create practice with invalid client_id (should fail)
                try:
                    await conn.execute(
                        """
                        INSERT INTO practices (client_id, practice_type, status, created_by, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        99999,  # Invalid client_id
                        "KITAS",
                        "in_progress",
                        "test@team.com",
                        datetime.now(),
                        datetime.now(),
                    )
                    # If foreign key constraint doesn't exist, manually rollback
                    raise Exception("Transaction should fail")
                except Exception:
                    # Transaction should rollback automatically
                    pass

            # Verify client was not created (transaction rolled back)
            client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
            assert client is None
