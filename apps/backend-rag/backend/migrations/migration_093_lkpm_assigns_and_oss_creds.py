"""
Migration 093: LKPM assignment + OSS credentials (plaintext) + client tax_consultant.

Part of the LKPM Q1 2026 rollout for Bali Zero. Adds three orthogonal schema
changes needed by the tax team:

1. clients.tax_consultant — VARCHAR(64), enum of 5 tax consultants
   (veronika / kadek / dewaayu / angel / faisha @balizero.com). Populated
   manually from the CRM Tax tab (one consultant per client).

2. lkpm_reports.lkpm_assigned_to — VARCHAR(64), same enum. Separate from
   clients.assigned_to (the primary account owner). Lets the tax team assign
   an LKPM report without overriding the main client owner.

3. lkpm_client_config.oss_username / oss_password / oss_creds_updated_at /
   oss_creds_updated_by — OSS RBA credentials stored in PLAINTEXT, on explicit
   request. Accessible to the team in the workspace and to the client in the
   portal. Not audited at row level (no crypto helper).

Non-derivable from code, matters for future replays:
- CHECK constraints hard-code the 5 email addresses. Adding a new tax
  consultant requires a new migration to ALTER the constraint.
- The import of 59 Q1-2026 LKPM rows is NOT part of this migration. It runs
  as a separate one-off script after this migration is applied.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "093_lkpm_assigns_and_oss_creds"
DESCRIPTION = (
    "LKPM: clients.tax_consultant, lkpm_reports.lkpm_assigned_to, "
    "lkpm_client_config OSS credentials (plaintext)"
)

TAX_CONSULTANT_EMAILS = (
    "veronika.tax@balizero.com",
    "kadek.tax@balizero.com",
    "dewaayu.tax@balizero.com",
    "angel.tax@balizero.com",
    "faisha.tax@balizero.com",
)

_CHECK_EMAIL_LIST_SQL = ", ".join(f"'{email}'" for email in TAX_CONSULTANT_EMAILS)


async def check_if_applied(conn) -> bool:
    """Idempotency: consider applied when all four new columns exist."""
    result = await conn.fetchval(
        """
        SELECT
            EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'clients' AND column_name = 'tax_consultant'
            )
            AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'lkpm_reports' AND column_name = 'lkpm_assigned_to'
            )
            AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'lkpm_client_config' AND column_name = 'oss_username'
            )
            AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'lkpm_client_config' AND column_name = 'oss_password'
            )
        """,
    )
    return bool(result)


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    # -------------------------------------------------- clients.tax_consultant
    await conn.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS tax_consultant VARCHAR(64)",
    )
    await conn.execute(
        "ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_tax_consultant_check",
    )
    await conn.execute(
        f"""
        ALTER TABLE clients
        ADD CONSTRAINT clients_tax_consultant_check
        CHECK (tax_consultant IS NULL OR tax_consultant IN ({_CHECK_EMAIL_LIST_SQL}))
        """,
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_clients_tax_consultant
            ON clients (tax_consultant)
            WHERE tax_consultant IS NOT NULL
        """,
    )

    # ------------------------------------------ lkpm_reports.lkpm_assigned_to
    await conn.execute(
        "ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS lkpm_assigned_to VARCHAR(64)",
    )
    await conn.execute(
        "ALTER TABLE lkpm_reports DROP CONSTRAINT IF EXISTS lkpm_reports_assigned_to_check",
    )
    await conn.execute(
        f"""
        ALTER TABLE lkpm_reports
        ADD CONSTRAINT lkpm_reports_assigned_to_check
        CHECK (lkpm_assigned_to IS NULL OR lkpm_assigned_to IN ({_CHECK_EMAIL_LIST_SQL}))
        """,
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_assigned
            ON lkpm_reports (lkpm_assigned_to, status)
            WHERE lkpm_assigned_to IS NOT NULL
        """,
    )

    # ----------------------------- lkpm_client_config OSS credentials (plaintext)
    await conn.execute(
        "ALTER TABLE lkpm_client_config ADD COLUMN IF NOT EXISTS oss_username TEXT",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config ADD COLUMN IF NOT EXISTS oss_password TEXT",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config ADD COLUMN IF NOT EXISTS oss_creds_updated_at TIMESTAMPTZ",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config ADD COLUMN IF NOT EXISTS oss_creds_updated_by TEXT",
    )

    # Optional tracking row in migration_history (created by migration 092 if
    # the table exists; otherwise we silently skip — same pattern as 092).
    has_history = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migration_history')",
    )
    if has_history:
        await conn.execute(
            """
            INSERT INTO migration_history (migration_id, description, applied_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (migration_id) DO NOTHING
            """,
            MIGRATION_ID,
            DESCRIPTION,
        )

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")

    # Reverse order of creation.
    await conn.execute(
        "ALTER TABLE lkpm_client_config DROP COLUMN IF EXISTS oss_creds_updated_by",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config DROP COLUMN IF EXISTS oss_creds_updated_at",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config DROP COLUMN IF EXISTS oss_password",
    )
    await conn.execute(
        "ALTER TABLE lkpm_client_config DROP COLUMN IF EXISTS oss_username",
    )

    await conn.execute("DROP INDEX IF EXISTS idx_lkpm_reports_assigned")
    await conn.execute(
        "ALTER TABLE lkpm_reports DROP CONSTRAINT IF EXISTS lkpm_reports_assigned_to_check",
    )
    await conn.execute(
        "ALTER TABLE lkpm_reports DROP COLUMN IF EXISTS lkpm_assigned_to",
    )

    await conn.execute("DROP INDEX IF EXISTS idx_clients_tax_consultant")
    await conn.execute(
        "ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_tax_consultant_check",
    )
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS tax_consultant")

    has_history = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migration_history')",
    )
    if has_history:
        await conn.execute(
            "DELETE FROM migration_history WHERE migration_id = $1",
            MIGRATION_ID,
        )

    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
