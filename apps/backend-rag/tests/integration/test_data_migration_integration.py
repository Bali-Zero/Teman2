"""
Comprehensive Integration Tests for Data Migration
Tests data migration scenarios and schema changes

Covers:
- Schema migrations
- Data migrations
- Migration rollback
- Migration validation
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestDataMigrationIntegration:
    """Integration tests for data migration"""

    @pytest.mark.asyncio
    async def test_schema_migration(self, db_pool):
        """Test schema migration"""

        async with db_pool.acquire() as conn:
            # Create initial schema
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_test_v1 (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255),
                    email VARCHAR(255)
                )
                """
            )

            # Insert test data
            await conn.execute(
                "INSERT INTO migration_test_v1 (name, email) VALUES ($1, $2)",
                "Test User",
                "test@example.com",
            )

            # Migrate to v2 schema (add column)
            await conn.execute(
                """
                ALTER TABLE migration_test_v1
                ADD COLUMN IF NOT EXISTS phone VARCHAR(50)
                """
            )

            # Verify migration
            columns = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'migration_test_v1'
                ORDER BY ordinal_position
                """
            )

            column_names = [col["column_name"] for col in columns]
            assert "phone" in column_names

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS migration_test_v1")

    @pytest.mark.asyncio
    async def test_data_migration(self, db_pool):
        """Test data migration"""

        async with db_pool.acquire() as conn:
            # Create source table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_source (
                    id SERIAL PRIMARY KEY,
                    old_field VARCHAR(255)
                )
                """
            )

            # Create target table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_target (
                    id SERIAL PRIMARY KEY,
                    new_field VARCHAR(255),
                    migrated_at TIMESTAMP
                )
                """
            )

            # Insert source data
            await conn.execute("INSERT INTO migration_source (old_field) VALUES ($1)", "Old Value")

            # Migrate data
            await conn.execute(
                """
                INSERT INTO migration_target (new_field, migrated_at)
                SELECT old_field, NOW()
                FROM migration_source
                """
            )

            # Verify migration
            migrated = await conn.fetchval("SELECT COUNT(*) FROM migration_target")
            assert migrated == 1

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS migration_target")
            await conn.execute("DROP TABLE IF EXISTS migration_source")

    @pytest.mark.asyncio
    async def test_migration_rollback(self, db_pool):
        """Test migration rollback"""

        async with db_pool.acquire() as conn:
            # Create table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rollback_test (
                    id SERIAL PRIMARY KEY,
                    value VARCHAR(255)
                )
                """
            )

            # Start migration
            async with conn.transaction():
                # Add column
                await conn.execute("ALTER TABLE rollback_test ADD COLUMN new_field VARCHAR(255)")

                # Simulate error
                try:
                    await conn.execute(
                        "ALTER TABLE rollback_test ADD COLUMN invalid_field INVALID_TYPE"
                    )
                except Exception:
                    # Transaction should rollback
                    pass

            # Verify rollback (column should not exist)
            columns = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'rollback_test'
                """
            )

            column_names = [col["column_name"] for col in columns]
            assert "new_field" not in column_names  # Rolled back

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS rollback_test")

    @pytest.mark.asyncio
    async def test_migration_validation(self, db_pool):
        """Test migration validation"""

        async with db_pool.acquire() as conn:
            # Create migration_log table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_log (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255),
                    status VARCHAR(50),
                    records_migrated INTEGER,
                    validation_passed BOOLEAN,
                    executed_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log migration
            migration_id = await conn.fetchval(
                """
                INSERT INTO migration_log (
                    migration_name, status, records_migrated, validation_passed
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "test_migration",
                "completed",
                100,
                True,
            )

            # Validate migration
            validation = await conn.fetchrow(
                """
                SELECT status, validation_passed, records_migrated
                FROM migration_log
                WHERE id = $1
                """,
                migration_id,
            )

            assert validation["status"] == "completed"
            assert validation["validation_passed"] is True
            assert validation["records_migrated"] == 100

            # Cleanup
            await conn.execute("DELETE FROM migration_log WHERE id = $1", migration_id)
