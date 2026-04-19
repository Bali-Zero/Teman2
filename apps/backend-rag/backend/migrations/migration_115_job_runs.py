"""
Migration 115: job_runs table for the unified jobs runner.

Purpose:
- Persist every job dispatch, retry, and completion for the in-process
  scheduler registered by backend/jobs/runner.py.
- Enforce idempotency: a completed row with a given idempotency_key
  tells the runner to skip duplicate dispatches.
- Provide run history for /api/jobs observability endpoints.

Reference: docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 115 — create job_runs table and indexes."""
    logger.info("Applying migration 115: job_runs table")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS job_runs (
            id              BIGSERIAL PRIMARY KEY,
            job_name        TEXT NOT NULL,
            scheduled_tick  TIMESTAMPTZ NOT NULL,
            idempotency_key TEXT NOT NULL,
            status          TEXT NOT NULL
                            CHECK (status IN (
                                'pending','running','completed',
                                'failed','skipped','cost_exceeded'
                            )),
            attempt         SMALLINT NOT NULL DEFAULT 1,
            started_at      TIMESTAMPTZ,
            finished_at     TIMESTAMPTZ,
            error           TEXT,
            cost_cents      INTEGER NOT NULL DEFAULT 0,
            meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    logger.info("Created table job_runs")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_name_tick
            ON job_runs (job_name, scheduled_tick DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_idempotency
            ON job_runs (idempotency_key)
            WHERE status IN ('completed','running');
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_status_name
            ON job_runs (status, job_name)
            WHERE status IN ('running','pending','failed');
    """)
    logger.info("Created indexes on job_runs")

    logger.info("Applied migration 115: job_runs table")


async def rollback(conn: Any) -> None:
    """Rollback migration 115 — drop job_runs table."""
    logger.info("Rolling back migration 115: job_runs table")

    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_status_name;")
    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_idempotency;")
    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_name_tick;")
    await conn.execute("DROP TABLE IF EXISTS job_runs;")

    logger.info("Rolled back migration 115: job_runs table")
