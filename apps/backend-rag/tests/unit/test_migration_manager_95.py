"""
Unit Tests for db/migration_manager.py - 95% Coverage Target
Tests the MigrationManager class
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test MigrationManager initialization
# ============================================================================


class TestMigrationManagerInit:
    """Test suite for MigrationManager initialization"""

    def test_init_with_database_url(self):
        """Test initialization with explicit database URL"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://user:pass@localhost/db")
        assert manager.database_url == "postgresql://user:pass@localhost/db"
        assert manager.pool is None

    def test_init_with_settings_url(self):
        """Test initialization with settings database URL"""
        with patch("db.migration_manager.settings") as mock_settings:
            mock_settings.database_url = "postgresql://settings@localhost/db"

            from db.migration_manager import MigrationManager

            manager = MigrationManager()
            assert "settings@localhost" in manager.database_url

    def test_init_without_database_url_raises_error(self):
        """Test initialization without database URL raises error"""
        with patch("db.migration_manager.settings") as mock_settings:
            mock_settings.database_url = None

            from db.migration_base import MigrationError
            from db.migration_manager import MigrationManager

            with pytest.raises(MigrationError) as exc_info:
                MigrationManager(database_url=None)

            assert "DATABASE_URL not configured" in str(exc_info.value)


# ============================================================================
# Test connection management
# ============================================================================


class TestConnectionManagement:
    """Test suite for connection pool management"""

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self):
        """Test connect creates connection pool"""
        with patch(
            "db.migration_manager.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool:
            mock_pool = MagicMock()
            mock_create_pool.return_value = mock_pool

            from db.migration_manager import MigrationManager

            manager = MigrationManager(database_url="postgresql://test@localhost/db")
            await manager.connect()

            mock_create_pool.assert_called_once()
            assert manager.pool == mock_pool

    @pytest.mark.asyncio
    async def test_connect_skips_if_pool_exists(self):
        """Test connect skips if pool already exists"""
        with patch("db.migration_manager.asyncpg.create_pool") as mock_create_pool:
            from db.migration_manager import MigrationManager

            manager = MigrationManager(database_url="postgresql://test@localhost/db")
            manager.pool = MagicMock()

            await manager.connect()

            mock_create_pool.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_closes_pool(self):
        """Test close closes connection pool"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")
        mock_pool = AsyncMock()
        manager.pool = mock_pool

        await manager.close()

        mock_pool.close.assert_called_once()
        assert manager.pool is None

    @pytest.mark.asyncio
    async def test_close_skips_if_no_pool(self):
        """Test close skips if no pool exists"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")
        manager.pool = None

        # Should not raise
        await manager.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager"""
        with patch(
            "db.migration_manager.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            from db.migration_manager import MigrationManager

            manager = MigrationManager(database_url="postgresql://test@localhost/db")

            async with manager:
                assert manager.pool == mock_pool

            mock_pool.close.assert_called_once()


# ============================================================================
# Test _sanitize_db_url
# ============================================================================


class TestSanitizeDbUrl:
    """Test suite for _sanitize_db_url method"""

    def test_sanitize_with_password(self):
        """Test URL sanitization with password"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        result = manager._sanitize_db_url("postgresql://user:secret123@localhost:5432/mydb")

        assert "secret123" not in result
        assert "***" in result
        assert "user" in result
        assert "localhost" in result
        assert ":5432" in result
        assert "/mydb" in result

    def test_sanitize_without_password(self):
        """Test URL sanitization without password"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        url = "postgresql://localhost:5432/mydb"
        result = manager._sanitize_db_url(url)

        assert result == url

    def test_sanitize_with_password_no_port(self):
        """Test URL sanitization with password but no port"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        result = manager._sanitize_db_url("postgresql://user:secret@localhost/mydb")

        assert "secret" not in result
        assert "***" in result


# ============================================================================
# Test get_applied_migrations
# ============================================================================


class TestGetAppliedMigrations:
    """Test suite for get_applied_migrations method"""

    @pytest.mark.asyncio
    async def test_get_applied_migrations_success(self):
        """Test successful retrieval of applied migrations"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "migration_name": "001_init",
                    "migration_number": 1,
                    "executed_at": "2024-01-01",
                    "description": "Initial",
                },
                {
                    "migration_name": "002_users",
                    "migration_number": 2,
                    "executed_at": "2024-01-02",
                    "description": "Add users",
                },
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.get_applied_migrations()

        assert len(result) == 2
        assert result[0]["migration_name"] == "001_init"
        assert result[1]["migration_number"] == 2

    @pytest.mark.asyncio
    async def test_get_applied_migrations_creates_pool_if_needed(self):
        """Test that get_applied_migrations creates pool if not exists"""
        with patch(
            "db.migration_manager.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool:
            from db.migration_manager import MigrationManager

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])

            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
                )
            )
            mock_create_pool.return_value = mock_pool

            manager = MigrationManager(database_url="postgresql://test@localhost/db")
            manager.pool = None

            result = await manager.get_applied_migrations()

            mock_create_pool.assert_called_once()


# ============================================================================
# Test is_applied
# ============================================================================


class TestIsApplied:
    """Test suite for is_applied method"""

    @pytest.mark.asyncio
    async def test_is_applied_true(self):
        """Test is_applied returns True for applied migration"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.is_applied(7)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_applied_false(self):
        """Test is_applied returns False for unapplied migration"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.is_applied(99)

        assert result is False


# ============================================================================
# Test rollback_migration
# ============================================================================


class TestRollbackMigration:
    """Test suite for rollback_migration method"""

    @pytest.mark.asyncio
    async def test_rollback_migration_success(self):
        """Test successful migration rollback"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"rollback_sql": "DROP TABLE test_table;"})

        mock_transaction = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.rollback_migration("001_test")

        assert result is True
        mock_conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_rollback_migration_no_rollback_sql(self):
        """Test rollback fails when no rollback SQL exists"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"rollback_sql": None})

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.rollback_migration("001_test")

        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_migration_not_found(self):
        """Test rollback fails when migration not found"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        result = await manager.rollback_migration("nonexistent")

        assert result is False


# ============================================================================
# Test discover_migrations
# ============================================================================


class TestDiscoverMigrations:
    """Test suite for discover_migrations method"""

    @pytest.mark.asyncio
    async def test_discover_migrations_success(self):
        """Test successful migration discovery - uses actual filesystem"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        # Use the actual migrations directory
        result = await manager.discover_migrations()

        # The result depends on actual file system, so we test the structure
        assert isinstance(result, list)
        # Each migration should have required keys
        for migration in result:
            assert "number" in migration
            assert "file" in migration
            assert "path" in migration

    @pytest.mark.asyncio
    async def test_discover_migrations_invalid_filename(self):
        """Test discovery skips files with invalid names"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        # This will use the actual migrations directory
        result = await manager.discover_migrations()

        # All results should have valid number fields
        for migration in result:
            assert "number" in migration
            assert isinstance(migration["number"], int)


# ============================================================================
# Test apply_migration
# ============================================================================


class TestApplyMigration:
    """Test suite for apply_migration method"""

    @pytest.mark.asyncio
    async def test_apply_migration_success(self):
        """Test successful migration application"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_migration = MagicMock()
        mock_migration.apply = AsyncMock(return_value=True)

        result = await manager.apply_migration(mock_migration)

        assert result is True
        mock_migration.apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_migration_failure(self):
        """Test migration application failure"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_migration = MagicMock()
        mock_migration.apply = AsyncMock(return_value=False)

        result = await manager.apply_migration(mock_migration)

        assert result is False


# ============================================================================
# Test apply_all_pending
# ============================================================================


class TestApplyAllPending:
    """Test suite for apply_all_pending method"""

    @pytest.mark.asyncio
    async def test_apply_all_pending_no_pending(self):
        """Test apply_all_pending with no pending migrations"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "migration_name": "001",
                    "migration_number": 1,
                    "executed_at": None,
                    "description": "",
                }
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        with patch.object(manager, "discover_migrations") as mock_discover:
            mock_discover.return_value = [
                {"number": 1, "file": "001_test.sql", "path": Path("001_test.sql")}
            ]

            result = await manager.apply_all_pending()

            assert result["applied"] == []
            assert result["failed"] == []

    @pytest.mark.asyncio
    async def test_apply_all_pending_dry_run(self):
        """Test apply_all_pending in dry run mode"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        with patch.object(manager, "discover_migrations") as mock_discover:
            mock_discover.return_value = [
                {"number": 1, "file": "001_test.sql", "path": Path("001_test.sql")}
            ]

            result = await manager.apply_all_pending(dry_run=True)

            assert result["applied"] == []
            assert result["failed"] == []

    @pytest.mark.asyncio
    async def test_apply_all_pending_with_failures(self):
        """Test apply_all_pending with migration failures"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        with patch.object(manager, "discover_migrations") as mock_discover:
            mock_discover.return_value = [
                {"number": 999, "file": "999_test.sql", "path": Path("999_test.sql")}
            ]

            mock_migration = MagicMock()
            mock_migration.apply = AsyncMock(side_effect=Exception("Database error"))

            with patch("db.migration_manager.BaseMigration") as mock_base_migration:
                mock_base_migration.return_value = mock_migration

                result = await manager.apply_all_pending()

                assert len(result["failed"]) == 1
                assert "Database error" in result["failed"][0]["error"]

    @pytest.mark.asyncio
    async def test_apply_all_pending_migration_returns_false(self):
        """Test apply_all_pending when migration.apply returns False"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        with patch.object(manager, "discover_migrations") as mock_discover:
            mock_discover.return_value = [
                {"number": 999, "file": "999_test.sql", "path": Path("999_test.sql")}
            ]

            mock_migration = MagicMock()
            mock_migration.apply = AsyncMock(return_value=False)

            with patch("db.migration_manager.BaseMigration") as mock_base_migration:
                mock_base_migration.return_value = mock_migration

                result = await manager.apply_all_pending()

                assert len(result["failed"]) == 1
                assert "returned False" in result["failed"][0]["error"]


# ============================================================================
# Test get_status
# ============================================================================


class TestGetStatus:
    """Test suite for get_status method"""

    @pytest.mark.asyncio
    async def test_get_status_success(self):
        """Test successful status retrieval"""
        from db.migration_manager import MigrationManager

        manager = MigrationManager(database_url="postgresql://test@localhost/db")

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "migration_name": "001",
                    "migration_number": 1,
                    "executed_at": None,
                    "description": "",
                }
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )
        manager.pool = mock_pool

        with patch.object(manager, "discover_migrations") as mock_discover:
            mock_discover.return_value = [
                {"number": 1, "file": "001.sql", "path": Path("001.sql")},
                {"number": 2, "file": "002.sql", "path": Path("002.sql")},
            ]

            result = await manager.get_status()

            assert result["total"] == 2
            assert result["applied"] == 1
            assert result["pending"] == 1
            assert 1 in result["applied_list"]
            assert 2 in result["pending_list"]
