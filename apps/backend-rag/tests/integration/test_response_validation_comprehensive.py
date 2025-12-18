"""
Comprehensive Response Validation Tests
Tests that successful API responses contain all expected fields and correct data types

Covers:
- Response structure validation
- Field presence and type checking
- Data integrity validation
- Response completeness verification
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
class TestResponseStructureValidation:
    """Test response structure and field validation"""

    @pytest.mark.asyncio
    async def test_client_response_structure(self, db_pool):
        """Validate client response structure"""
        async with db_pool.acquire() as conn:
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, client_type, priority,
                    created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                "Validation Client",
                "validation@example.com",
                "+6281234567890",
                "active",
                "individual",
                "medium",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            client = await conn.fetchrow(
                """
                SELECT * FROM clients WHERE id = $1
                """,
                client_id,
            )

            # Validate all expected fields exist
            required_fields = [
                "id",
                "full_name",
                "email",
                "status",
                "created_by",
                "created_at",
                "updated_at",
            ]

            for field in required_fields:
                assert field in client, f"Missing required field: {field}"

            # Validate field types
            assert isinstance(client["id"], int)
            assert isinstance(client["full_name"], str)
            assert isinstance(client["email"], str)
            assert isinstance(client["status"], str)
            assert isinstance(client["created_at"], datetime)
            assert isinstance(client["updated_at"], datetime)

            # Validate field values
            assert client["id"] > 0
            assert len(client["full_name"]) > 0
            assert "@" in client["email"]
            assert client["status"] in ["active", "inactive", "archived"]

    @pytest.mark.asyncio
    async def test_practice_response_structure(self, db_pool):
        """Validate practice response structure"""
        async with db_pool.acquire() as conn:
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Practice Validation Client",
                "practice.validation@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "PT PMA",
                "in_progress",
                "high",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            practice = await conn.fetchrow(
                """
                SELECT * FROM practices WHERE id = $1
                """,
                practice_id,
            )

            # Validate required fields
            required_fields = [
                "id",
                "client_id",
                "practice_type",
                "status",
                "created_by",
                "created_at",
                "updated_at",
            ]

            for field in required_fields:
                assert field in practice, f"Missing required field: {field}"

            # Validate relationships
            assert practice["client_id"] == client_id

            # Validate status values
            assert practice["status"] in [
                "pending",
                "in_progress",
                "pending_review",
                "completed",
                "cancelled",
            ]

    @pytest.mark.asyncio
    async def test_interaction_response_structure(self, db_pool):
        """Validate interaction response structure"""
        async with db_pool.acquire() as conn:
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Interaction Validation Client",
                "interaction.validation@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "email",
                "Test interaction",
                "team@example.com",
                datetime.now(),
            )

            interaction = await conn.fetchrow(
                """
                SELECT * FROM interactions WHERE id = $1
                """,
                interaction_id,
            )

            # Validate required fields
            required_fields = [
                "id",
                "client_id",
                "interaction_type",
                "created_by",
                "created_at",
            ]

            for field in required_fields:
                assert field in interaction, f"Missing required field: {field}"

            # Validate interaction type
            assert interaction["interaction_type"] in [
                "email",
                "call",
                "meeting",
                "chat",
                "document",
            ]


@pytest.mark.integration
class TestDataIntegrityValidation:
    """Test data integrity in responses"""

    @pytest.mark.asyncio
    async def test_client_data_integrity(self, db_pool):
        """Test client data integrity across operations"""
        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, phone, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "Integrity Client",
                "integrity@example.com",
                "+6281234567890",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Update client
            await conn.execute(
                """
                UPDATE clients
                SET full_name = $1, status = $2, updated_at = $3
                WHERE id = $4
                """,
                "Updated Integrity Client",
                "inactive",
                datetime.now(),
                client_id,
            )

            # Verify data integrity
            client = await conn.fetchrow(
                """
                SELECT id, full_name, email, status, created_at, updated_at
                FROM clients
                WHERE id = $1
                """,
                client_id,
            )

            assert client["id"] == client_id
            assert client["full_name"] == "Updated Integrity Client"
            assert client["email"] == "integrity@example.com"  # Should not change
            assert client["status"] == "inactive"
            assert client["updated_at"] > client["created_at"]

    @pytest.mark.asyncio
    async def test_relationship_integrity(self, db_pool):
        """Test relationship integrity between entities"""
        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Relationship Client",
                "relationship@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice
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
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create interaction
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, practice_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                practice_id,
                "email",
                "Test",
                "team@example.com",
                datetime.now(),
            )

            # Verify relationships
            relationship_check = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    p.id as practice_id,
                    p.client_id as practice_client_id,
                    i.id as interaction_id,
                    i.client_id as interaction_client_id,
                    i.practice_id as interaction_practice_id
                FROM clients c
                JOIN practices p ON c.id = p.client_id
                JOIN interactions i ON c.id = i.client_id AND p.id = i.practice_id
                WHERE c.id = $1
                """,
                client_id,
            )

            assert relationship_check is not None
            assert relationship_check["client_id"] == client_id
            assert relationship_check["practice_id"] == practice_id
            assert relationship_check["practice_client_id"] == client_id
            assert relationship_check["interaction_id"] == interaction_id
            assert relationship_check["interaction_client_id"] == client_id
            assert relationship_check["interaction_practice_id"] == practice_id


@pytest.mark.integration
class TestResponseCompleteness:
    """Test response completeness"""

    @pytest.mark.asyncio
    async def test_list_response_completeness(self, db_pool):
        """Test that list responses contain all expected items"""
        async with db_pool.acquire() as conn:
            # Create multiple clients
            client_ids = []
            for i in range(5):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                        full_name, email, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    f"List Client {i}",
                    f"list.client{i}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

            # Retrieve list
            clients = await conn.fetch(
                """
                SELECT id, full_name, email, status
                FROM clients
                WHERE id = ANY($1)
                ORDER BY id
                """,
                client_ids,
            )

            assert len(clients) == 5
            assert all(client["id"] in client_ids for client in clients)
            assert all(client["full_name"] is not None for client in clients)
            assert all(client["email"] is not None for client in clients)
            assert all(client["status"] is not None for client in clients)

    @pytest.mark.asyncio
    async def test_statistics_response_completeness(self, db_pool):
        """Test that statistics responses contain all expected metrics"""
        async with db_pool.acquire() as conn:
            # Create test data
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Stats Client",
                "stats@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practices
            for i in range(3):
                await conn.execute(
                    """
                    INSERT INTO practices (
                        client_id, practice_type, status, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    client_id,
                    f"Practice_{i}",
                    "in_progress",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )

            # Create interactions
            for i in range(5):
                await conn.execute(
                    """
                    INSERT INTO interactions (
                        client_id, interaction_type, summary, created_by, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    client_id,
                    "email",
                    f"Interaction {i}",
                    "team@example.com",
                    datetime.now(),
                )

            # Get statistics
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT c.id) as total_clients,
                    COUNT(DISTINCT p.id) as total_practices,
                    COUNT(DISTINCT i.id) as total_interactions
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                WHERE c.id = $1
                GROUP BY c.id
                """,
                client_id,
            )

            assert stats is not None
            assert stats["total_clients"] == 1
            assert stats["total_practices"] == 3
            assert stats["total_interactions"] == 5
            assert all(isinstance(v, int) for v in stats.values())
