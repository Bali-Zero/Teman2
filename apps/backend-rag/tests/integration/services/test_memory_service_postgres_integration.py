"""
Integration Tests for MemoryServicePostgres
Tests PostgreSQL-based memory management
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMemoryServicePostgresIntegration:
    """Comprehensive integration tests for MemoryServicePostgres"""

    @pytest_asyncio.fixture
    async def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_pool

    @pytest_asyncio.fixture
    async def service(self, mock_db_pool):
        """Create MemoryServicePostgres instance"""
        with patch(
            "services.memory_service_postgres.asyncpg.create_pool", return_value=mock_db_pool
        ):
            from services.memory_service_postgres import MemoryServicePostgres

            service = MemoryServicePostgres()
            service.pool = mock_db_pool
            service.use_postgres = True
            return service

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.MAX_FACTS > 0
        assert service.MAX_SUMMARY_LENGTH > 0

    @pytest.mark.asyncio
    async def test_connect(self, service, mock_db_pool):
        """Test connecting to PostgreSQL"""
        with patch(
            "services.memory_service_postgres.asyncpg.create_pool", return_value=mock_db_pool
        ):
            await service.connect()

            assert service.pool is not None

    @pytest.mark.asyncio
    async def test_get_memory_from_cache(self, service):
        """Test getting memory from cache"""
        from datetime import datetime

        from services.memory_service_postgres import UserMemory

        memory = UserMemory(
            user_id="test-user",
            profile_facts=["Fact 1"],
            summary="Test summary",
            counters={"conversations": 1},
            updated_at=datetime.now(),
        )

        service.memory_cache["test-user"] = memory

        result = await service.get_memory("test-user")

        assert result is not None
        assert result.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_get_memory_from_database(self, service, mock_db_pool):
        """Test getting memory from database"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "content": "Fact 1",
                    "confidence": 0.9,
                    "source": "user",
                    "metadata": {},
                    "created_at": "2025-01-01",
                }
            ]
        )
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "conversations_count": 5,
                "searches_count": 10,
                "summary": "Test summary",
                "updated_at": "2025-01-01",
            }
        )

        result = await service.get_memory("test-user")

        assert result is not None
        assert result.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_save_fact(self, service, mock_db_pool):
        """Test saving a fact"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await service.save_fact(
            user_id="test-user",
            fact="User prefers English",
            confidence=0.9,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_summary(self, service, mock_db_pool):
        """Test updating summary"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await service.update_summary("test-user", "New summary")

        assert result is True

    @pytest.mark.asyncio
    async def test_increment_counter(self, service, mock_db_pool):
        """Test incrementing counter"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await service.increment_counter("test-user", "conversations")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_memory_in_memory_fallback(self):
        """Test getting memory with in-memory fallback"""
        from services.memory_service_postgres import MemoryServicePostgres

        service = MemoryServicePostgres(database_url=None)
        service.use_postgres = False

        result = await service.get_memory("test-user")

        assert result is not None
        assert result.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_close(self, service, mock_db_pool):
        """Test closing connection pool"""
        await service.close()

        # Should not raise exception
        assert True
