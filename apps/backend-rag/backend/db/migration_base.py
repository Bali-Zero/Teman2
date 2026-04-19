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

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Base exception for migration errors"""

    pass


# Marker convention for SQL migrations: everything after this marker line
# is the rollback SQL. The marker itself is a `--` comment, so PostgreSQL
# would happily execute the rollback DDL together with the forward DDL
# (and undo the migration in the same transaction) unless we strip it.
ROLLBACK_MARKER_RE = re.compile(
    r"^\s*--\s*===\s*ROLLBACK\s*===\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def split_migration_sql(sql_text: str) -> tuple[str, str | None]:
    """Split a SQL migration body at the `-- === ROLLBACK ===` marker.

    Returns:
        (forward_sql, rollback_sql) where rollback_sql is None if the marker
        is absent. forward_sql is right-stripped (no trailing whitespace).
        rollback_sql is left/right-stripped; it may be the empty string when
        the marker is present but no rollback DDL follows it.
    """
    match = ROLLBACK_MARKER_RE.search(sql_text)
    if not match:
        return sql_text, None
    forward = sql_text[: match.start()].rstrip()
    rollback = sql_text[match.end() :].strip()
    return forward, rollback


class MigrationIrreversibleError(MigrationError):
    """Raised when a migration explicitly has no safe rollback path.

    Use this in rollback_sql or a custom rollback hook when the operation
    (e.g., DROP COLUMN with data loss, denormalization) cannot be reversed.
    Raising this is preferable to silently ignoring rollback — it forces
    the caller to acknowledge the irreversibility.
    """

    pass


# All migration_*.py files that existed before 2026-04-18 are grandfathered:
# they were written before the rollback requirement was introduced and are
# applied manually (the automated loader only reads db/migrations_v2/*.sql).
# New migrations (migration_number > 111) MUST supply rollback_sql.
LEGACY_NO_ROLLBACK_WHITELIST: frozenset[str] = frozenset({
    "migration_001",
    "migration_007",
    "migration_010",
    "migration_012",
    "migration_013",
    "migration_014",
    "migration_015",
    "migration_016",
    "migration_018",
    "migration_019",
    "migration_020",
    "migration_021a_baseline",
    "migration_021b_add_bm25_sparse_vectors",
    "migration_022",
    "migration_025",
    "migration_026",
    "migration_027_team_memory_facts",
    "migration_028_knowledge_graph_schema",
    "migration_029_kg_source_chunks",
    "migration_030_zoho_email",
    "migration_031_client_portal",
    "migration_031b_hybrid_collections",
    "migration_032_drop_legacy_kg_tables",
    "migration_033_newsletter",
    "migration_034_google_drive_tokens",
    "migration_035_kbli_blueprints",
    "migration_036_team_departments",
    "migration_037_folder_access_rules",
    "migration_038_news_items",
    "migration_040_email_activity_log",
    "migration_041_clients_missing_columns",
    "migration_041b_team_activity_logging",
    "migration_042_passport_enrichment",
    "migration_043_fix_visa_types_from_qdrant",
    "migration_043b_knowledge_activity_log",
    "migration_044_seed_practice_types",
    "migration_050_client_memory_sync",
    "migration_051_client_messaging_link",
    "migration_052_openclaw_message_logs",
    "migration_054_practice_required_documents",
    "migration_055_kg_performance_indexes",
    "migration_060_x_monitored_tweets",
    "migration_061_documents_ocr_status",
    "migration_062_client_drive_subfolders",
    "migration_063_lkpm_reports",
    "migration_064_kg_reverse_traversal_index",
    "migration_065_cell_organism_tables",
    "migration_066_populate_practice_types_from_pricing",
    "migration_067_clients_soft_delete_indexes",
    "migration_068_hr_payroll",
    "migration_069_audit_logs",
    "migration_069b_hr_bonus_rates_alignment",
    "migration_070_conversation_history",
    "migration_070b_legal_ingest_jobs",
    "migration_071_notification_alerts",
    "migration_072_welcome_email_queue",
    "migration_073_visa_lifecycle",
    "migration_074_content_hash",
    "migration_075_practice_status_notify",
    "migration_076_event_bus_triggers",
    "migration_076b_hr_leave_balances_seed",
    "migration_077_kg_staging_tables",
    "migration_077b_post_publish_queue",
    "migration_078_ppq_step_tracking",
    "migration_079_naga_tables",
    "migration_080a_visa_oracle_sessions",
    "migration_080b_renewal_dedup",
    "migration_080c_hr_team_cleanup",
    "migration_081_naga_claim_quality",
    "migration_081b_prime_nexus_geo",
    "migration_084a_nlm_verification_log",
    "migration_084b_client_perf_indexes",
    "migration_085a_prime_proposals",
    "migration_085b_check_no_empty_strings",
    "migration_086_channel_dlq",
    "migration_087_normalize_practice_states",
    "migration_088_kg_gin_indexes",
    "migration_089_api_key_records",
    "migration_090_security_audit_log",
    "migration_091_client_consent_log",
    "migration_092a_attendance_late_incidents",
    "migration_092b_coastline_distance",
    "migration_093_lkpm_assigns_and_oss_creds",
    "migration_094_conversation_threads",
    "migration_095_backfill_threads",
    "migration_096_kg_communities",
    "migration_097_entity_mentions",
    "migration_098a_owner_weekly_cashout",
    "migration_098b_guardian_decisions",
    "migration_099_hr_bonus_historical",
    "migration_100a_lkpm_company_id",
    "migration_100b_widen_gender_column",
    "migration_100c_olympus_tables",
    "migration_101_critical_indexes",
    "migration_102_materialized_views",
    "migration_103_pg_tuning",
    "migration_104_olympus_v3_columns",
    "migration_105_covering_indexes",
    "migration_106_news_dedup_constraint",
    "migration_107_bridge_outbox",
    "migration_108_kg_proposals",
    "migration_109_funnel_sessions",
    "migration_110_notification_prefs",
    "migration_111_notification_log",
})


class BaseMigration:
    """
    Base class for all database migrations.

    Provides:
    - Transaction management with automatic rollback
    - Migration tracking (prevents duplicate execution)
    - SQL validation
    - Verification hooks (verify_apply, verify_rollback)
    - Consistent error handling
    - Rollback enforcement for post-2026-04-18 migrations
    """

    MIGRATIONS_DIR = Path(__file__).parent / "migrations_v2"

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
        _sql_dir: Path | None = None,
    ) -> None:
        """
        Initialize migration.

        Args:
            migration_number: Sequential migration number (e.g., 7, 10, 12)
            sql_file: Name of SQL file in db/migrations/ directory
            description: Human-readable description of migration
            dependencies: List of migration numbers that must be applied first
            rollback_sql: SQL to reverse this migration. Required for migration_number > 111.
                          Use MigrationIrreversibleError inside a rollback hook when truly
                          one-way (e.g., DROP COLUMN with data loss).
            _sql_dir: Override SQL directory (for testing only)
        """
        self.migration_number = migration_number
        sql_dir = _sql_dir if _sql_dir is not None else self.MIGRATIONS_DIR
        self.sql_file = sql_dir / sql_file
        self.description = description
        self.dependencies = dependencies or []
        self.rollback_sql = rollback_sql

        # Extract base name from SQL file (remove .sql extension)
        sql_base_name = sql_file.replace(".sql", "")
        # Remove any migration number prefix if it exists (e.g., "001_fix_missing_tables" -> "fix_missing_tables")
        sql_base_name = re.sub(r"^\d{3}_", "", sql_base_name)
        self.migration_name = f"{migration_number:03d}_{sql_base_name}"

        if not self.sql_file.exists():
            raise MigrationError(f"SQL file not found: {self.sql_file}")

        # Enforce rollback_sql for migrations created after the cutoff (> 111).
        # Legacy migrations are grandfathered via LEGACY_NO_ROLLBACK_WHITELIST.
        stem = self.sql_file.stem  # e.g., "200_new_feature"
        # Reconstruct what migration_name would look like as a stem key
        migration_stem = f"migration_{migration_number:03d}_{sql_base_name}".rstrip("_")
        is_legacy = (
            migration_number <= 111
            or migration_stem in LEGACY_NO_ROLLBACK_WHITELIST
        )
        if not is_legacy and rollback_sql is None:
            raise ValueError(
                f"Migration {migration_number} ({self.migration_name}) must supply "
                "`rollback_sql`. Post-2026-04-18 migrations require an explicit rollback. "
                "If the migration is truly irreversible, raise MigrationIrreversibleError "
                "inside the rollback SQL comment or supply a compensating migration reference."
            )

    def _sanitize_db_url(self, url: str) -> str:
        """Sanitize database URL for logging (hide credentials)"""
        parsed = urlparse(url)
        if parsed.password:
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
                                "If this is intentional, add a comment explaining why.",
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
                execution_time_ms INTEGER,
                rollback_sql TEXT
            )
        """,
        )

        # Create index for faster lookups
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schema_migrations_name
            ON schema_migrations(migration_name)
        """,
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_schema_migrations_number
            ON schema_migrations(migration_number)
        """,
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
                    f"but {dep_number} has not been applied yet",
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

    async def verify_apply(self, conn: asyncpg.Connection | None) -> bool:
        """
        Verify post-apply state. Override in subclasses for custom checks.

        Returns:
            True if post-apply verification passes.
        """
        return True

    async def verify_rollback(self, conn: asyncpg.Connection | None) -> bool:
        """
        Verify post-rollback state. Override in subclasses for custom checks.

        Returns:
            True if post-rollback verification passes.
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

        # The file may contain a `-- === ROLLBACK ===` marker followed by
        # rollback DDL. PostgreSQL treats the marker as a comment, so executing
        # the full file would CREATE then DROP the same objects in one
        # transaction. Apply the forward portion only; the rollback string is
        # stored separately on `self.rollback_sql` for `rollback_migration()`.
        sql_forward, _embedded_rollback = split_migration_sql(sql)

        # Validate SQL
        try:
            self._validate_sql(sql_forward)
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

                # Execute SQL (forward portion only; rollback portion is
                # stored on `self.rollback_sql` and will be re-run via
                # MigrationManager.rollback_migration if ever invoked).
                try:
                    await conn.execute(sql_forward)
                except asyncpg.PostgresError as e:
                    raise MigrationError(f"SQL execution failed: {e}") from e

                # Verify migration
                if not await self.verify(conn):
                    raise MigrationError(f"Verification failed for {self.migration_name}")

                if not await self.verify_apply(conn):
                    raise MigrationError(f"verify_apply failed for {self.migration_name}")

                # Log migration
                execution_time_ms = int((time.time() - start_time) * 1000)
                await self._log_migration(conn, sql, execution_time_ms, self.rollback_sql)

                logger.info(
                    f"✅ Migration {self.migration_name} applied successfully "
                    f"in {execution_time_ms}ms",
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
