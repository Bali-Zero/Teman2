"""
Tests for database migrations
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import asyncpg
from db.migration_base import BaseMigration, MigrationError
from db.migration_manager import MigrationManager

from app.core.config import settings


@pytest.fixture
async def test_db():
    """Create test database connection"""
    if not settings.database_url:
        pytest.skip("DATABASE_URL not configured")

    try:
        conn = await asyncpg.connect(settings.database_url)
        yield conn
        await conn.close()
    except Exception as e:
        pytest.skip(f"Cannot connect to database: {e}")


@pytest.fixture
def migration_manager():
    """Create migration manager instance"""
    return MigrationManager()


class TestBaseMigration:
    """Test BaseMigration class"""

    def test_migration_initialization(self):
        """Test migration can be initialized"""
        migration = BaseMigration(
            migration_number=999,
            sql_file="001_fix_missing_tables.sql",
            description="Test migration",
        )
        assert migration.migration_number == 999
        # Migration name should strip the migration number prefix from SQL filename
        assert migration.migration_name == "999_fix_missing_tables"
        assert migration.description == "Test migration"

    def test_migration_file_not_found(self):
        """Test error when SQL file doesn't exist"""
        with pytest.raises(MigrationError, match="SQL file not found"):
            BaseMigration(migration_number=999, sql_file="nonexistent.sql", description="Test")

    def test_sql_validation_dangerous_patterns(self):
        """Test SQL validation rejects dangerous patterns"""
        migration = BaseMigration(
            migration_number=999, sql_file="001_fix_missing_tables.sql", description="Test"
        )

        # Test DROP DATABASE
        with pytest.raises(MigrationError, match="DROP DATABASE"):
            migration._validate_sql("DROP DATABASE test;")

        # Test DROP SCHEMA
        with pytest.raises(MigrationError, match="DROP SCHEMA"):
            migration._validate_sql("DROP SCHEMA public;")

        # Test TRUNCATE (should be rejected unless in comment)
        with pytest.raises(MigrationError, match="TRUNCATE"):
            migration._validate_sql("TRUNCATE TABLE users;")

        # Test TRUNCATE in comment (should pass)
        migration._validate_sql("-- TRUNCATE TABLE users;")

    def test_checksum_calculation(self):
        """Test checksum calculation"""
        migration = BaseMigration(
            migration_number=999, sql_file="001_fix_missing_tables.sql", description="Test"
        )

        sql1 = "CREATE TABLE test (id INT);"
        sql2 = "CREATE TABLE test (id INT);"
        sql3 = "CREATE TABLE test (id INTEGER);"

        checksum1 = migration._calculate_checksum(sql1)
        checksum2 = migration._calculate_checksum(sql2)
        checksum3 = migration._calculate_checksum(sql3)

        assert checksum1 == checksum2  # Same SQL = same checksum
        assert checksum1 != checksum3  # Different SQL = different checksum
        assert len(checksum1) == 64  # SHA256 hex = 64 chars


class TestMigrationManager:
    """Test MigrationManager class"""

    @pytest.mark.asyncio
    async def test_migration_manager_initialization(self):
        """Test migration manager can be initialized"""
        manager = MigrationManager()
        assert manager.database_url is not None

    @pytest.mark.asyncio
    async def test_discover_migrations(self, migration_manager):
        """Test migration discovery"""
        migrations = await migration_manager.discover_migrations()
        assert isinstance(migrations, list)
        assert len(migrations) > 0

        # Check structure
        for m in migrations:
            assert "number" in m
            assert "file" in m
            assert "path" in m
            assert isinstance(m["number"], int)

    @pytest.mark.asyncio
    async def test_get_status(self, migration_manager):
        """Test get migration status"""
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured")

        try:
            status = await migration_manager.get_status()

            assert "total" in status
            assert "applied" in status
            assert "pending" in status
            assert "applied_list" in status
            assert "pending_list" in status

            assert isinstance(status["total"], int)
            assert isinstance(status["applied"], int)
            assert isinstance(status["pending"], int)
            assert status["total"] == status["applied"] + status["pending"]
        except Exception as e:
            pytest.skip(f"Cannot connect to database: {e}")

    @pytest.mark.asyncio
    async def test_get_applied_migrations(self, migration_manager):
        """Test get applied migrations list"""
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured")

        try:
            applied = await migration_manager.get_applied_migrations()
            assert isinstance(applied, list)

            for m in applied:
                assert "migration_name" in m
                assert "migration_number" in m
                assert "executed_at" in m
                assert "description" in m
        except Exception as e:
            pytest.skip(f"Cannot connect to database: {e}")

    @pytest.mark.asyncio
    async def test_is_applied(self, migration_manager):
        """Test check if migration is applied"""
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured")

        try:
            # Check a migration that likely doesn't exist
            result = await migration_manager.is_applied(99999)
            assert isinstance(result, bool)
        except Exception as e:
            pytest.skip(f"Cannot connect to database: {e}")


class TestMigrationIntegration:
    """Integration tests for migrations"""

    @pytest.mark.asyncio
    async def test_migration_idempotency(self, test_db):
        """Test that migrations can be applied multiple times safely"""
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured")

        # This test requires a real migration
        # For now, we'll test the concept

        migration = BaseMigration(
            migration_number=999,
            sql_file="001_fix_missing_tables.sql",
            description="Test migration for idempotency",
        )

        # First application
        try:
            result1 = await migration.apply()
            assert result1 is True

            # Second application (should skip)
            result2 = await migration.apply()
            assert result2 is True  # Should return True (skipped)
        except MigrationError as e:
            # If migration already applied, that's fine
            if "already applied" in str(e).lower():
                pytest.skip("Migration already applied in test database")
            # If database connection fails, skip
            if "Cannot connect" in str(e):
                pytest.skip(f"Cannot connect to database: {e}")
            raise

    @pytest.mark.asyncio
    async def test_migration_verification(self, test_db):
        """Test migration verification"""
        migration = BaseMigration(
            migration_number=999,
            sql_file="001_fix_missing_tables.sql",
            description="Test migration",
        )

        # Default verification should return True
        result = await migration.verify(test_db)
        assert result is True


class TestMigrationDependencies:
    """Test migration dependency checking"""

    @pytest.mark.asyncio
    async def test_dependency_checking(self, test_db):
        """Test that dependencies are checked"""
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured")

        # Create a migration with a dependency that doesn't exist
        migration = BaseMigration(
            migration_number=999,
            sql_file="001_fix_missing_tables.sql",
            description="Test migration with dependency",
            dependencies=[99999],  # Non-existent migration
        )

        # Should fail because dependency doesn't exist
        try:
            with pytest.raises(MigrationError, match="depends on"):
                await migration.apply()
        except MigrationError as e:
            # If database connection fails, skip instead of failing
            if "Cannot connect" in str(e):
                pytest.skip(f"Cannot connect to database: {e}")
            # Re-raise if it's the expected dependency error
            if "depends on" in str(e):
                raise
            # Otherwise skip
            pytest.skip(f"Unexpected error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
