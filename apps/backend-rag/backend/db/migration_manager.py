"""
NUZANTARA PRIME - Migration Manager
Centralized migration management system
"""

import logging
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
from db.migration_base import BaseMigration, MigrationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Centralized migration manager.

    Provides:
    - List all migrations (applied and pending)
    - Apply migrations in order
    - Check migration status
    - Rollback migrations
    - Connection pooling for performance
    """

    def __init__(self, database_url: str | None = None):
        """
        Initialize migration manager.

        Args:
            database_url: Database URL (defaults to settings.database_url)
        """
        self.database_url = database_url or settings.database_url
        if not self.database_url:
            raise MigrationError("DATABASE_URL not configured")
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """
        Create connection pool.

        Should be called before using the manager.
        """
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url, min_size=1, max_size=5, command_timeout=60
            )
            logger.info("Migration manager connection pool created")

    async def close(self) -> None:
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Migration manager connection pool closed")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    def _sanitize_db_url(self, url: str) -> str:
        """Sanitize database URL for logging"""
        parsed = urlparse(url)
        if parsed.password:
            safe_url = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                safe_url += f":{parsed.port}"
            safe_url += parsed.path
            return safe_url
        return url

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
                execution_time_ms INTEGER,
                rollback_sql TEXT,
                applied_by VARCHAR(255) DEFAULT 'system'
            );
            -- Fix for legacy schema: Ensure ALL columns exist
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS migration_number INTEGER DEFAULT 0;
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS description TEXT;
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS rollback_sql TEXT;
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS checksum VARCHAR(64) DEFAULT '';
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER DEFAULT 0;
            ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS applied_by VARCHAR(255) DEFAULT 'system';
        """
        )

    async def get_applied_migrations(self) -> list[dict]:
        """
        Get list of all applied migrations.

        Returns:
            List of migration dictionaries with keys:
            - migration_name
            - migration_number
            - executed_at
            - description
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            await self._ensure_migration_log(conn)
            rows = await conn.fetch(
                """
                SELECT migration_name, migration_number, executed_at, description
                FROM schema_migrations
                ORDER BY migration_number
            """
            )
            return [
                {
                    "migration_name": row["migration_name"],
                    "migration_number": row["migration_number"],
                    "executed_at": row["executed_at"],
                    "description": row["description"],
                }
                for row in rows
            ]

    async def is_applied(self, migration_number: int) -> bool:
        """
        Check if a migration has been applied.

        Args:
            migration_number: Migration number to check

        Returns:
            True if migration is applied, False otherwise
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            await self._ensure_migration_log(conn)
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM schema_migrations
                    WHERE migration_number = $1
                )
            """,
                migration_number,
            )
            return bool(result)

    async def rollback_migration(self, migration_name: str) -> bool:
        """
        Rollback a specific migration.

        Args:
            migration_name: Name of migration to rollback

        Returns:
            True if rollback successful, False otherwise
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            await self._ensure_migration_log(conn)

            # Get rollback SQL
            row = await conn.fetchrow(
                """
                SELECT rollback_sql
                FROM schema_migrations
                WHERE migration_name = $1
            """,
                migration_name,
            )

            if not row or not row["rollback_sql"]:
                logger.warning(f"No rollback SQL for {migration_name}")
                return False

            async with conn.transaction():
                # Execute rollback
                await conn.execute(row["rollback_sql"])

                # Remove from log
                await conn.execute(
                    """
                    DELETE FROM schema_migrations
                    WHERE migration_name = $1
                """,
                    migration_name,
                )

        logger.info(f"✅ Rolled back migration: {migration_name}")
        return True

    async def discover_migrations(self) -> list[BaseMigration]:
        """
        Discover all migration files in migrations directory.

        Returns:
            List of BaseMigration instances (not yet initialized with SQL files)
        """
        migrations_dir = Path(__file__).parent / "migrations"
        sql_files = sorted(migrations_dir.glob("*.sql"))

        migrations = []
        for sql_file in sql_files:
            # Extract migration number from filename (e.g., "007_crm_system_schema.sql" -> 7)
            try:
                migration_number = int(sql_file.stem.split("_")[0])
                migrations.append(
                    {"number": migration_number, "file": sql_file.name, "path": sql_file}
                )
            except (ValueError, IndexError):
                logger.warning(f"Could not parse migration number from {sql_file.name}, skipping")
                continue

        return migrations

    async def apply_migration(self, migration: BaseMigration) -> bool:
        """
        Apply a single migration.

        Args:
            migration: BaseMigration instance to apply

        Returns:
            True if successful, False otherwise

        Raises:
            MigrationError: If migration fails
        """
        return await migration.apply()

    async def apply_all_pending(self, dry_run: bool = False) -> dict:
        """
        Apply all pending migrations in order.

        Args:
            dry_run: If True, only show what would be applied without executing

        Returns:
            Dictionary with:
            - applied: List of applied migration numbers
            - skipped: List of skipped migration numbers
            - failed: List of failed migration numbers with errors
        """
        discovered = await self.discover_migrations()
        applied_migrations = await self.get_applied_migrations()
        applied_numbers = {m["migration_number"] for m in applied_migrations}

        pending = [m for m in discovered if m["number"] not in applied_numbers]

        if not pending:
            logger.info("No pending migrations")
            return {"applied": [], "skipped": [], "failed": []}

        logger.info(f"Found {len(pending)} pending migrations")

        if dry_run:
            logger.info("DRY RUN - Would apply:")
            for m in pending:
                logger.info(f"  - {m['number']:03d}: {m['file']}")
            return {"applied": [], "skipped": [], "failed": []}

        applied = []
        failed = []

        for migration_info in sorted(pending, key=lambda x: x["number"]):
            migration_number = migration_info["number"]
            sql_file = migration_info["file"]

            # Create migration instance (will be subclassed in actual migrations)
            # For now, we'll use BaseMigration directly
            migration = BaseMigration(
                migration_number=migration_number,
                sql_file=sql_file,
                description=f"Migration {migration_number}",
            )

            try:
                success = await self.apply_migration(migration)
                if success:
                    applied.append(migration_number)
                else:
                    failed.append({"number": migration_number, "error": "Migration returned False"})
            except Exception as e:
                logger.error(f"Failed to apply migration {migration_number}: {e}")
                failed.append({"number": migration_number, "error": str(e)})

        return {"applied": applied, "skipped": [], "failed": failed}

    async def get_status(self) -> dict:
        """
        Get migration status summary.

        Returns:
            Dictionary with:
            - total: Total number of migrations discovered
            - applied: Number of applied migrations
            - pending: Number of pending migrations
            - applied_list: List of applied migration numbers
            - pending_list: List of pending migration numbers
        """
        discovered = await self.discover_migrations()
        applied_migrations = await self.get_applied_migrations()
        applied_numbers = {m["migration_number"] for m in applied_migrations}

        total = len(discovered)
        applied = len(applied_numbers)
        pending = total - applied

        discovered_numbers = {m["number"] for m in discovered}
        pending_numbers = sorted(discovered_numbers - applied_numbers)

        return {
            "total": total,
            "applied": applied,
            "pending": pending,
            "applied_list": sorted(applied_numbers),
            "pending_list": pending_numbers,
        }
