"""
NUZANTARA PRIME - Migration Manager
Centralized migration management system
"""

import logging
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from backend.app.core.config import settings
from backend.db.migration_base import (
    ROLLBACK_MARKER_RE,
    BaseMigration,
    MigrationError,
    split_migration_sql,
)

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility with existing tests/callers.
# `__all__` advertises the re-export so static analyzers don't flag it
# as dead code (CodeQL: py/unused-global-variable).
_ROLLBACK_MARKER_RE = ROLLBACK_MARKER_RE
__all__ = [
    "MigrationManager",
    "_ROLLBACK_MARKER_RE",
    "_assert_unique_migration_numbers",
    "_extract_rollback_sql",
]


def _assert_unique_migration_numbers(sql_files: list[Path]) -> None:
    """Raise MigrationError if any two paths in `sql_files` share a numeric
    prefix (e.g. `129_a.sql` + `129_b.sql`).

    Pulled out of `MigrationManager.discover_migrations` so unit tests can
    exercise the rule without instantiating the manager (which requires
    DATABASE_URL). Files that don't start with `NNN_` are ignored — the
    parser falls back to logging a warning later.
    """
    seen: dict[int, str] = {}
    duplicates: dict[int, list[str]] = {}
    for sql_file in sql_files:
        try:
            num = int(sql_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if num in seen:
            duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
        else:
            seen[num] = sql_file.name
    if duplicates:
        details = ", ".join(
            f"{num}: [{', '.join(files)}]" for num, files in sorted(duplicates.items())
        )
        raise MigrationError(
            "Duplicate migration numbers in migrations_v2/: "
            f"{details}. Two files cannot share a prefix — the runner "
            "applies one and silently skips the other. Resolution: "
            "rename the not-yet-applied file to the next free number. "
            "See cicatrix STRUCTURAL 2026-04-29 P0-7."
        )


def _extract_rollback_sql(sql_text: str) -> str | None:
    """Extract the rollback SQL block from a migration file.

    Thin wrapper over `migration_base.split_migration_sql` that returns only
    the rollback portion (None if the marker is absent).
    """
    _, rollback = split_migration_sql(sql_text)
    return rollback


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

    def __init__(self, database_url: str | None = None) -> None:
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
                self.database_url, min_size=1, max_size=5, command_timeout=60,
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
        """Ensure _schema_versions table exists"""
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _schema_versions (
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
        """,
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
                FROM _schema_versions
                ORDER BY migration_number
            """,
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

    async def is_applied(self, migration_name: str) -> bool:
        """
        Check if a migration has been applied.

        Args:
            migration_name: Migration filename (without .py) to check

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
                    SELECT 1 FROM _schema_versions
                    WHERE migration_name = $1
                )
            """,
                migration_name,
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
                FROM _schema_versions
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
                    DELETE FROM _schema_versions
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
        # SWITCH TO V2 DIRECTORY
        migrations_dir = Path(__file__).parent / "migrations_v2"
        # Create directory if it doesn't exist (first run)
        migrations_dir.mkdir(exist_ok=True)

        sql_files = sorted(migrations_dir.glob("*.sql"))

        # P0-7 (zero-crash audit 2026-04-29): reject duplicate migration
        # numbers. Two files sharing the same prefix make
        # `discover_migrations` order undefined — the runner applies one
        # alphabetically and silently skips the other on the next deploy.
        # See cicatrix STRUCTURAL 2026-04-29 P0-7 (PRs #254 + #258).
        _assert_unique_migration_numbers(sql_files)

        migrations = []
        for sql_file in sql_files:
            # Extract migration number from filename (e.g., "001_baseline_v2.sql" -> 1)
            try:
                migration_number = int(sql_file.stem.split("_")[0])
            except (ValueError, IndexError):
                logger.warning(f"Could not parse migration number from {sql_file.name}, skipping")
                continue

            try:
                sql_text = sql_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                logger.error(f"Cannot read migration {sql_file.name}: {exc}")
                continue

            migrations.append({
                "number": migration_number,
                "file": sql_file.name,
                "path": sql_file,
                "rollback_sql": _extract_rollback_sql(sql_text),
            })

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

    # Process-wide advisory lock id used to serialise concurrent migration
    # runs. `pg_advisory_lock` / `pg_advisory_unlock` are *session-scoped* —
    # a lock acquired on connection A must be released on the same
    # connection A. Releasing on a different connection silently no-ops
    # (the function returns false / NULL) and the original session keeps
    # the lock until it terminates.
    _APPLY_ALL_LOCK_ID = 73491

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
        if not self.pool:
            await self.connect()

        # Hold a single dedicated connection for the entire run so the
        # session-scoped `pg_advisory_lock` is acquired and released on the
        # *same* session. Anything else (including individual migration
        # `apply()` calls) keeps using fresh connections from the pool —
        # they don't need to share this session because the lock only
        # serialises the orchestrator, not the SQL it dispatches.
        #
        # We deliberately do NOT use `pg_advisory_xact_lock`: that variant
        # auto-releases on transaction commit, but `apply_all_pending`
        # spans many independent migrations (each with its own commit), so
        # an xact-scoped lock would be released after the first migration
        # and concurrent runners could interleave from migration #2 onward.
        async with self.pool.acquire() as lock_conn:
            try:
                locked = await lock_conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)", self._APPLY_ALL_LOCK_ID,
                )
            except Exception as exc:
                logger.error("Failed to acquire migration advisory lock: %s", exc)
                raise

            if not locked:
                logger.warning("Another migration process is running, skipping")
                return {"applied": [], "skipped": [], "failed": []}

            try:
                return await self._apply_all_pending_locked(dry_run)
            finally:
                # Same session — guaranteed to actually release. We swallow
                # release errors because the connection is about to be
                # returned to the pool either way; the lock dies with the
                # session even if the explicit release fails.
                try:
                    await lock_conn.execute(
                        "SELECT pg_advisory_unlock($1)", self._APPLY_ALL_LOCK_ID,
                    )
                except Exception as exc:
                    logger.warning(
                        "Advisory lock release raised %s — relying on session "
                        "termination to free the lock", exc,
                    )

    async def _apply_all_pending_locked(self, dry_run: bool = False) -> dict:
        """Internal: apply pending migrations while holding advisory lock."""
        discovered = await self.discover_migrations()
        applied_migrations = await self.get_applied_migrations()
        applied_numbers = {m["migration_number"] for m in applied_migrations}

        # Orphan tolerance: log applied migrations that no longer have files
        discovered_numbers = {m["number"] for m in discovered}
        orphan_numbers = applied_numbers - discovered_numbers
        if orphan_numbers:
            logger.warning(
                f"Orphan migrations in _schema_versions (files removed): {sorted(orphan_numbers)}. "
                "These are already applied and will be ignored."
            )

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

        # CHECK FOR LEGACY DB STATE (FAKE APPLY STRATEGY)
        # If we have pending migration 001 AND the DB already has tables (e.g. users)
        # We skip the SQL execution of 001 but mark it as applied.
        is_migration_001_pending = any(m["number"] == 1 for m in pending)
        is_schema_empty = len(applied_numbers) == 0  # Based on _schema_versions table

        if is_migration_001_pending and is_schema_empty:
            # Check if real user tables exist (to distinguish from fresh DB)
            async with self.pool.acquire() as conn:
                tables_exist = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'clients'
                    );
                """,
                )

                if tables_exist:
                    logger.warning("🚀 DETECTED LEGACY DATABASE! FAKE-APPLYING BASELINE (001)...")

                    # Manually insert into _schema_versions
                    await conn.execute(
                        """
                        INSERT INTO _schema_versions (migration_name, migration_number, description, applied_by, checksum)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        "001_baseline_v2.sql",
                        1,
                        "Baseline V2 (Fake Applied on Legacy DB)",
                        "system-auto",
                        "legacy_fake_checksum",
                    )

                    logger.info("✅ Baseline V2 marked as applied (SQL execution skipped).")

                    # Add to results and remove from pending list to execute
                    applied.append(1)
                    pending = [m for m in pending if m["number"] != 1]

        for migration_info in sorted(pending, key=lambda x: x["number"]):
            migration_number = migration_info["number"]
            sql_file = migration_info["file"]

            # Create migration instance (will be subclassed in actual migrations)
            # For now, we'll use BaseMigration directly
            migration = BaseMigration(
                migration_number=migration_number,
                sql_file=sql_file,
                description=f"Migration {migration_number}",
                rollback_sql=migration_info.get("rollback_sql"),
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
