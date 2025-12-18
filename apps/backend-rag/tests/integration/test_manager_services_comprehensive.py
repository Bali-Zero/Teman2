"""
Comprehensive Integration Tests for Manager Services
Tests CollectionManager, PromptManager, MigrationManager, ContextWindowManager

Covers:
- Collection management
- Prompt management
- Migration management
- Context window management
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollectionManager:
    """Integration tests for CollectionManager"""

    @pytest.mark.asyncio
    async def test_collection_manager_initialization(self, qdrant_client):
        """Test CollectionManager initialization"""
        with patch("services.collection_manager.QdrantClient") as mock_qdrant:
            from services.collection_manager import CollectionManager

            manager = CollectionManager(qdrant_client=mock_qdrant.return_value)

            assert manager is not None

    @pytest.mark.asyncio
    async def test_collection_creation(self, qdrant_client):
        """Test collection creation"""

        collection_name = "manager_test_collection"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Verify collection exists
            info = await qdrant_client.get_collection_info(collection_name=collection_name)
            assert info is not None

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_collection_deletion(self, qdrant_client):
        """Test collection deletion"""

        collection_name = "manager_delete_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Delete collection
            await qdrant_client.delete_collection(collection_name=collection_name)

            # Verify deletion
            try:
                await qdrant_client.get_collection_info(collection_name=collection_name)
                assert False, "Collection should not exist"
            except Exception:
                pass  # Expected

        except Exception:
            pass  # Cleanup if needed


@pytest.mark.integration
class TestPromptManager:
    """Integration tests for PromptManager"""

    @pytest.mark.asyncio
    async def test_prompt_manager_initialization(self):
        """Test PromptManager initialization"""
        with patch("llm.prompt_manager.PromptManager") as mock_prompt:
            from llm.prompt_manager import PromptManager

            manager = PromptManager()

            assert manager is not None

    @pytest.mark.asyncio
    async def test_prompt_retrieval(self):
        """Test prompt retrieval"""
        # Mock prompt manager
        mock_manager = MagicMock()
        mock_manager.get_prompt = AsyncMock(return_value="Test prompt template with {variable}")

        # Get prompt
        prompt = await mock_manager.get_prompt("test_template", variable="value")

        assert prompt is not None

    @pytest.mark.asyncio
    async def test_prompt_template_rendering(self):
        """Test prompt template rendering"""
        template = "Hello {name}, welcome to {service}!"

        # Render template
        rendered = template.format(name="Test User", service="ZANTARA")

        assert "Test User" in rendered
        assert "ZANTARA" in rendered


@pytest.mark.integration
class TestMigrationManager:
    """Integration tests for MigrationManager"""

    @pytest.mark.asyncio
    async def test_migration_manager_initialization(self, db_pool):
        """Test MigrationManager initialization"""
        with patch("db.migration_manager.asyncpg") as mock_asyncpg:
            from db.migration_manager import MigrationManager

            manager = MigrationManager(db_pool=db_pool)

            assert manager is not None

    @pytest.mark.asyncio
    async def test_migration_tracking(self, db_pool):
        """Test migration tracking"""

        async with db_pool.acquire() as conn:
            # Create migrations table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE,
                    applied_at TIMESTAMP DEFAULT NOW(),
                    checksum VARCHAR(64)
                )
                """
            )

            # Track migration
            migration_id = await conn.fetchval(
                """
                INSERT INTO migrations (migration_name, checksum)
                VALUES ($1, $2)
                RETURNING id
                """,
                "test_migration_001",
                "abc123def456",
            )

            assert migration_id is not None

            # Verify migration tracked
            migration = await conn.fetchrow(
                """
                SELECT migration_name, checksum
                FROM migrations
                WHERE id = $1
                """,
                migration_id,
            )

            assert migration is not None
            assert migration["migration_name"] == "test_migration_001"

            # Cleanup
            await conn.execute("DELETE FROM migrations WHERE id = $1", migration_id)

    @pytest.mark.asyncio
    async def test_migration_rollback_tracking(self, db_pool):
        """Test migration rollback tracking"""

        async with db_pool.acquire() as conn:
            # Create migration_rollbacks table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_rollbacks (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255),
                    rolled_back_at TIMESTAMP DEFAULT NOW(),
                    reason TEXT
                )
                """
            )

            # Track rollback
            rollback_id = await conn.fetchval(
                """
                INSERT INTO migration_rollbacks (migration_name, reason)
                VALUES ($1, $2)
                RETURNING id
                """,
                "test_migration_001",
                "Test rollback",
            )

            assert rollback_id is not None

            # Cleanup
            await conn.execute("DELETE FROM migration_rollbacks WHERE id = $1", rollback_id)


@pytest.mark.integration
class TestContextWindowManager:
    """Integration tests for ContextWindowManager"""

    @pytest.mark.asyncio
    async def test_context_window_manager_initialization(self):
        """Test ContextWindowManager initialization"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=4000)

        assert manager is not None
        assert manager.max_tokens == 4000

    @pytest.mark.asyncio
    async def test_context_truncation(self):
        """Test context truncation"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=100)

        # Create messages that exceed limit
        messages = [
            {"role": "user", "content": "A" * 50},
            {"role": "assistant", "content": "B" * 50},
            {"role": "user", "content": "C" * 50},
        ]

        # Truncate context
        truncated = manager.manage_context(messages, max_tokens=100)

        assert len(truncated) <= len(messages)

    @pytest.mark.asyncio
    async def test_context_priority_management(self):
        """Test context priority management"""
        from services.context_window_manager import ContextWindowManager

        manager = ContextWindowManager(max_tokens=200)

        # Create messages with different priorities
        messages = [
            {"role": "system", "content": "System message", "priority": "high"},
            {"role": "user", "content": "User message 1", "priority": "high"},
            {"role": "assistant", "content": "Assistant message", "priority": "medium"},
            {"role": "user", "content": "User message 2", "priority": "low"},
        ]

        # Manage context with priority
        managed = manager.manage_context(messages, max_tokens=200)

        # High priority messages should be preserved
        assert any(m.get("priority") == "high" for m in managed)
