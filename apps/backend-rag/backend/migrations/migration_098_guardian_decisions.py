"""
Migration 098: Guardian V4 decision logging and risk score tracking.

Adds:
- guardian_decisions table (audit trail for every CG action)
- guardian_risk_scores table (unified risk score snapshots for trend tracking)
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "098_guardian_decisions"
DESCRIPTION = "Guardian V4: decision logging + risk score tracking tables"


async def check_if_applied(conn) -> bool:
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'guardian_decisions')"
    )
    return result


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    # 1. Decision log — every CG action is a row
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS guardian_decisions (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            component TEXT NOT NULL,
            check_type TEXT NOT NULL,
            finding TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            action_taken TEXT NOT NULL,
            rationale TEXT,
            rollback_plan TEXT,
            risk_score INTEGER,
            metadata JSONB DEFAULT '{}'
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gd_timestamp ON guardian_decisions (timestamp DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gd_component ON guardian_decisions (component)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gd_severity ON guardian_decisions (severity)"
    )

    # 2. Risk score snapshots — one row per watchdog run
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS guardian_risk_scores (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            overall_score INTEGER NOT NULL,
            rbac_score INTEGER NOT NULL DEFAULT 0,
            api_contract_score INTEGER NOT NULL DEFAULT 0,
            cache_score INTEGER NOT NULL DEFAULT 0,
            dead_code_score INTEGER NOT NULL DEFAULT 0,
            red_team_survival FLOAT,
            seo_health FLOAT,
            ragas_quality FLOAT,
            metadata JSONB DEFAULT '{}'
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grs_timestamp ON guardian_risk_scores (timestamp DESC)"
    )

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS guardian_risk_scores CASCADE")
    await conn.execute("DROP TABLE IF EXISTS guardian_decisions CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"Migration {MIGRATION_ID} rolled back")
