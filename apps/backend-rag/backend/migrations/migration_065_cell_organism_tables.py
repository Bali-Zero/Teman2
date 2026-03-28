"""
Migration 065: CELL Organism Dashboard Tables

Purpose:
- Create `cell_pulse_log` table for CELL heartbeat history (if not exists)
- Create `cell_alerts` table for silent/human/logs alert history

Tables:
- cell_pulse_log: one row per 60s pulse (health, response time, action taken)
- cell_alerts: alert history from alert_silent, alert_human, read_logs actions

Author: Claude Sonnet 4.6
Date: 2026-03-27
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def upgrade(conn: Any) -> None:
    """Create CELL organism tables."""

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cell_pulse_log (
            id                  SERIAL PRIMARY KEY,
            pulse_number        INTEGER NOT NULL,
            health_status       VARCHAR(16) NOT NULL,
            response_time_ms    INTEGER NOT NULL DEFAULT 0,
            dna_intact          BOOLEAN NOT NULL DEFAULT TRUE,
            budget_spent        NUMERIC(10, 6) NOT NULL DEFAULT 0,
            budget_limit        NUMERIC(10, 6) NOT NULL DEFAULT 1,
            memory_stm_count    INTEGER NOT NULL DEFAULT 0,
            memory_ltm_count    INTEGER NOT NULL DEFAULT 0,
            procedures_count    INTEGER NOT NULL DEFAULT 0,
            cells_active        INTEGER NOT NULL DEFAULT 1,
            cells_total         INTEGER NOT NULL DEFAULT 1,
            action_taken        VARCHAR(64),
            error_message       TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cell_pulse_log_created_at
            ON cell_pulse_log (created_at DESC)
        """,
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cell_alerts (
            id              SERIAL PRIMARY KEY,
            level           VARCHAR(16) NOT NULL DEFAULT 'info',
            action          VARCHAR(64) NOT NULL,
            message         TEXT NOT NULL,
            health_status   VARCHAR(16) NOT NULL DEFAULT '',
            pulse_number    INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cell_alerts_created_at
            ON cell_alerts (created_at DESC)
        """,
    )

    logger.info("Migration 065: cell_pulse_log and cell_alerts tables created")


async def downgrade(conn: Any) -> None:
    """Drop CELL organism tables."""
    await conn.execute("DROP TABLE IF EXISTS cell_alerts")
    await conn.execute("DROP TABLE IF EXISTS cell_pulse_log")
    logger.info("Migration 065: cell_pulse_log and cell_alerts tables dropped")
