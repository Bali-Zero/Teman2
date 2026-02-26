"""
Migration 054: Autonomous Execution Engine

Creates persistent tables for the execution engine:
1. execution_plans - Plan metadata and overall status
2. execution_steps - Individual steps with retry tracking
3. execution_approvals - Human approval decisions audit trail

Replaces in-memory POC storage with durable PostgreSQL state.

Author: Nuzantara Team
Date: 2026-02-26
"""

import logging

import asyncpg

from backend.db.migration_base import BaseMigration

logger = logging.getLogger(__name__)


class Migration054(BaseMigration):
    """Autonomous Execution Engine tables."""

    def __init__(self) -> None:
        super().__init__(
            migration_number=54,
            description="Create Autonomous Execution Engine tables (plans, steps, approvals)",
        )

    async def up(self, conn: asyncpg.Connection) -> None:
        await _apply_migration(conn)

    async def down(self, conn: asyncpg.Connection) -> None:
        await conn.execute("DROP TABLE IF EXISTS execution_approvals CASCADE")
        await conn.execute("DROP TABLE IF EXISTS execution_steps CASCADE")
        await conn.execute("DROP TABLE IF EXISTS execution_plans CASCADE")
        await conn.execute("DROP TYPE IF EXISTS execution_status CASCADE")
        await conn.execute("DROP TYPE IF EXISTS step_safety CASCADE")
        logger.info("Migration 054 rolled back")


async def _apply_migration(conn: asyncpg.Connection) -> None:
    """Apply the migration."""

    # Enum types
    await conn.execute("""
        DO $$ BEGIN
            CREATE TYPE execution_status AS ENUM (
                'pending', 'queued', 'in_progress', 'waiting_approval',
                'approved', 'completed', 'failed', 'rolled_back', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    await conn.execute("""
        DO $$ BEGIN
            CREATE TYPE step_safety AS ENUM ('safe', 'critical', 'irreversible');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Plans table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS execution_plans (
            plan_id         TEXT PRIMARY KEY,
            user_query      TEXT NOT NULL,
            user_email      TEXT NOT NULL,
            task_type       TEXT NOT NULL,
            priority        INTEGER NOT NULL DEFAULT 0,
            overall_status  execution_status NOT NULL DEFAULT 'pending',
            current_step    INTEGER NOT NULL DEFAULT 0,
            total_steps     INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT,
            metadata        JSONB DEFAULT '{}',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Steps table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS execution_steps (
            id              SERIAL PRIMARY KEY,
            plan_id         TEXT NOT NULL REFERENCES execution_plans(plan_id) ON DELETE CASCADE,
            step_index      INTEGER NOT NULL,
            step_id         TEXT NOT NULL,
            action          TEXT NOT NULL,
            description     TEXT NOT NULL,
            safety_level    step_safety NOT NULL DEFAULT 'safe',
            status          execution_status NOT NULL DEFAULT 'pending',
            rollback_action TEXT,
            retry_count     INTEGER NOT NULL DEFAULT 0,
            max_retries     INTEGER NOT NULL DEFAULT 3,
            last_error      TEXT,
            result          JSONB,
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            next_retry_at   TIMESTAMPTZ,
            UNIQUE (plan_id, step_id)
        )
    """)

    # Approvals audit trail
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS execution_approvals (
            id              SERIAL PRIMARY KEY,
            plan_id         TEXT NOT NULL REFERENCES execution_plans(plan_id) ON DELETE CASCADE,
            step_id         TEXT NOT NULL,
            approved        BOOLEAN NOT NULL,
            approver_email  TEXT,
            reason          TEXT,
            decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Indexes for common queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_plans_status
            ON execution_plans(overall_status)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_plans_user
            ON execution_plans(user_email)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_plans_queue
            ON execution_plans(priority DESC, created_at ASC)
            WHERE overall_status IN ('pending', 'queued')
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_steps_plan
            ON execution_steps(plan_id, step_index)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_steps_retry
            ON execution_steps(next_retry_at)
            WHERE status = 'failed' AND retry_count < max_retries
    """)

    logger.info("Migration 054 applied: Autonomous Execution Engine tables created")
