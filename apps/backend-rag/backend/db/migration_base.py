"""
NUZANTARA PRIME - Base Migration Framework
Provides base classes and utilities for database migrations
"""

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Base exception for migration errors"""

    pass


class BaseMigration:
    """
    Base class for all database migrations.

    Provides:
    - Transaction management with automatic rollback
    - Migration tracking (prevents duplicate execution)
    - SQL validation
    - Verification hooks
    - Consistent error handling
    """

    MIGRATIONS_DIR = Path(__file__).parent / "migrations"

    # Dangerous SQL patterns that should not be in migrations
    DANGEROUS_PATTERNS = [
        "DROP DATABASE",
        "DROP SCHEMA",
        "TRUNCATE",  # Unless explicitly needed
    ]

    def __init__(
        self,
        migration_number: int,
        sql_file: str,
        description: str,
        dependencies: list[int] | None = None,
        rollback_sql: str | None = None,
    ):
        """
        Initialize migration.

        Args:
            migration_number: Sequential migration number (e.g., 7, 10, 12)
            sql_file: Name of SQL file in db/migrations/ directory
            description: Human-readable description of migration
            dependencies: List of migration numbers that must be applied first
        """
        self.migration_number = migration_number
        self.sql_file = self.MIGRATIONS_DIR / sql_file
        self.description = description
        self.dependencies = dependencies or []
        self.rollback_sql = rollback_sql
        # Extract base name from SQL file (remove .sql extension)
        sql_base_name = sql_file.replace(".sql", "")
        # Remove any migration number prefix if it exists (e.g., "001_fix_missing_tables" -> "fix_missing_tables")
        # Check for 3-digit prefix pattern (001_, 007_, etc.)
        sql_base_name = re.sub(r"^\d{3}_", "", sql_base_name)
        self.migration_name = f"{migration_number:03d}_{sql_base_name}"

        if not self.sql_file.exists():
            raise MigrationError(f"SQL file not found: {self.sql_file}")

    def _sanitize_db_url(self, url: str) -> str:
        """Sanitize database URL for logging (hide credentials)"""
        parsed = urlparse(url)
        if parsed.password:
            # Replace password with ***
            safe_url = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                safe_url += f":{parsed.port}"
            safe_url += parsed.path
            return safe_url
        return url

    def _validate_sql(self, sql: str) -> None:
        """
        Validate SQL file is safe to execute.

        Raises:
            MigrationError: If SQL contains dangerous patterns
        """
        sql_upper = sql.upper()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in sql_upper:
                # Allow TRUNCATE if it's in a comment or part of a safe operation
                if pattern == "TRUNCATE":
                    # Check if it's in a comment
                    lines = sql.split("\n")
                    for line in lines:
                        if "TRUNCATE" in line.upper() and not line.strip().startswith("--"):
                            raise MigrationError(
                                f"SQL contains potentially dangerous pattern: {pattern}. "
                                "If this is intentional, add a comment explaining why."
                            )
                else:
                    raise MigrationError(f"SQL contains dangerous pattern: {pattern}")

    def _calculate_checksum(self, sql: str) -> str:
        """Calculate SHA256 checksum of SQL content"""
        return hashlib.sha256(sql.encode("utf-8")).hexdigest()

    async def _ensure_migration_log(self, conn: asyncpg.Connection) -> None:
        """Ensure schema_migrations table exists"""
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                migration_number INTEGER NOT NULL,
                executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                checksum VARCHAR(64) NOT NULL,
                description TEXT,
                execution_time_ms INTEGER
            )
        """
        )

        # Create index for faster lookups
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schema_migrations_name
            ON schema_migrations(migration_name)
        """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schema_migrations_number
            ON schema_migrations(migration_number)
        """
        )

    async def _is_applied(self, conn: asyncpg.Connection) -> bool:
        """Check if migration already applied"""
        await self._ensure_migration_log(conn)
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE migration_name = $1)",
            self.migration_name,
        )
        return bool(result)

    async def _check_dependencies(self, conn: asyncpg.Connection) -> None:
        """Check that all dependency migrations have been applied"""
        if not self.dependencies:
            return

        await self._ensure_migration_log(conn)

        for dep_number in self.dependencies:
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM schema_migrations
                    WHERE migration_number = $1
                )
            """,
                dep_number,
            )

            if not result:
                raise MigrationError(
                    f"Migration {self.migration_number} depends on migration {dep_number}, "
                    f"but {dep_number} has not been applied yet"
                )

    async def _log_migration(
        self,
        conn: asyncpg.Connection,
        sql: str,
        execution_time_ms: int,
        rollback_sql: str | None = None,
    ) -> None:
        """Log migration to schema_migrations table"""
        checksum = self._calculate_checksum(sql)
        await conn.execute(
            """
            INSERT INTO schema_migrations
            (migration_name, migration_number, checksum, description, execution_time_ms, rollback_sql)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (migration_name) DO NOTHING
        """,
            self.migration_name,
            self.migration_number,
            checksum,
            self.description,
            execution_time_ms,
            rollback_sql,
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """
        Verify migration was applied correctly.

        Override this method in subclasses to add custom verification logic.

        Returns:
            True if verification passes, False otherwise
        """
        return True

    async def apply(self) -> bool:
        """
        Apply migration with transaction and automatic rollback.

        Returns:
            True if migration applied successfully, False otherwise

        Raises:
            MigrationError: If migration fails or validation fails
        """
        if not settings.database_url:
            raise MigrationError("DATABASE_URL not configured")

        # Read SQL file
        try:
            sql = self.sql_file.read_text(encoding="utf-8")
        except Exception as e:
            raise MigrationError(f"Failed to read SQL file {self.sql_file}: {e}") from e

        # Validate SQL
        try:
            self._validate_sql(sql)
        except MigrationError as e:
            logger.error(f"SQL validation failed for {self.migration_name}: {e}")
            raise

        # Sanitize URL for logging
        safe_url = self._sanitize_db_url(settings.database_url)
        logger.info(f"Applying migration {self.migration_name} to {safe_url}")

        # Connect to database
        try:
            conn = await asyncpg.connect(settings.database_url)
        except Exception as e:
            raise MigrationError(f"Cannot connect to database: {e}") from e

        import time

        start_time = time.time()

        try:
            # Use transaction for atomicity
            async with conn.transaction():
                # Check dependencies
                await self._check_dependencies(conn)

                # Check if already applied
                if await self._is_applied(conn):
                    logger.info(f"Migration {self.migration_name} already applied, skipping")
                    return True

                # Execute SQL
                try:
                    await conn.execute(sql)
                except asyncpg.PostgresError as e:
                    raise MigrationError(f"SQL execution failed: {e}") from e

                # Verify migration
                if not await self.verify(conn):
                    raise MigrationError(f"Verification failed for {self.migration_name}")

                # Log migration
                execution_time_ms = int((time.time() - start_time) * 1000)
                await self._log_migration(conn, sql, execution_time_ms, self.rollback_sql)

                logger.info(
                    f"✅ Migration {self.migration_name} applied successfully "
                    f"in {execution_time_ms}ms"
                )
                return True

        except MigrationError:
            # Re-raise migration errors
            raise
        except Exception as e:
            logger.error(f"Migration {self.migration_name} failed: {e}", exc_info=True)
            raise MigrationError(f"Migration failed: {e}") from e
        finally:
            await conn.close()

    async def rollback(self, manager) -> bool:
        """
        Rollback migration using MigrationManager.

        Args:
            manager: MigrationManager instance

        Returns:
            True if rollback successful, False otherwise
        """
        return await manager.rollback_migration(self.migration_name)

    def __repr__(self) -> str:
        return f"<Migration {self.migration_number}: {self.description}>"
