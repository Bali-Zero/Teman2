"""Migration 124: Autonomous Lab runtime queue and events outbox.

Purpose:
- Create ``autonomous_lab_runs`` for idempotent, resumable Lab work.
- Create ``autonomous_lab_events_outbox`` for ack-after-success Lab events.

This is the v1 control-plane foundation only. Workers remain feature-gated and
must run on Pro/Mini according to the machine-placement policy.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 124."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS autonomous_lab_runs (
            run_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,

            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending',
                    'running',
                    'paused',
                    'succeeded',
                    'failed',
                    'cancelled'
                )),
            priority INTEGER NOT NULL DEFAULT 0,

            -- Machine placement and worker ownership.
            machine_role TEXT
                CHECK (
                    machine_role IS NULL
                    OR machine_role IN (
                        'air_m5_cockpit',
                        'pro_runtime',
                        'mini_scheduler',
                        'unknown'
                    )
                ),
            worker_id TEXT,

            -- Receipt-safe control-plane payloads only.
            objective TEXT NOT NULL,
            receipt JSONB NOT NULL,
            target_paths TEXT[] NOT NULL DEFAULT '{}',
            metadata JSONB NOT NULL DEFAULT '{}',

            -- Retry and lease state.
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            claimed_at TIMESTAMPTZ,
            heartbeat_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            last_error TEXT,

            -- Audit.
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_claimable
            ON autonomous_lab_runs (priority DESC, created_at ASC)
            WHERE status = 'pending';
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_status_updated
            ON autonomous_lab_runs (status, updated_at);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_worker
            ON autonomous_lab_runs (worker_id)
            WHERE worker_id IS NOT NULL;
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS autonomous_lab_events_outbox (
            event_id BIGSERIAL PRIMARY KEY,
            run_id TEXT NOT NULL
                REFERENCES autonomous_lab_runs(run_id)
                ON DELETE CASCADE,
            event_type TEXT NOT NULL
                CHECK (event_type IN (
                    'run_enqueued',
                    'run_claimed',
                    'run_checkpointed',
                    'run_paused',
                    'run_succeeded',
                    'run_failed',
                    'run_cancelled',
                    'material_ingested',
                    'run_drafted',
                    'experiment_ready',
                    'verification_failed',
                    'candidate_ready',
                    'evaluation_recorded',
                    'curator_decision_recorded',
                    'shadow_run_completed'
                )),
            payload JSONB NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending',
                    'in_progress',
                    'consumed',
                    'failed_dlq'
                )),
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            claimed_by TEXT,
            claimed_at TIMESTAMPTZ,
            consumed_at TIMESTAMPTZ,
            last_error TEXT,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_claimable
            ON autonomous_lab_events_outbox (created_at ASC)
            WHERE status = 'pending';
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_run_id
            ON autonomous_lab_events_outbox (run_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_status_updated
            ON autonomous_lab_events_outbox (status, updated_at);
    """)

    logger.info("Migration 124: autonomous_lab_runs + autonomous_lab_events_outbox applied")


async def rollback(conn: Any) -> None:
    """Rollback migration 124."""
    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_outbox_status_updated;")
    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_outbox_run_id;")
    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_outbox_claimable;")
    await conn.execute("DROP TABLE IF EXISTS autonomous_lab_events_outbox;")

    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_runs_worker;")
    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_runs_status_updated;")
    await conn.execute("DROP INDEX IF EXISTS idx_autonomous_lab_runs_claimable;")
    await conn.execute("DROP TABLE IF EXISTS autonomous_lab_runs;")

    logger.info("Migration 124 rollback: autonomous_lab runtime tables dropped")
