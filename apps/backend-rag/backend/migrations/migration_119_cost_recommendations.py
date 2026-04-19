"""
Migration 119: llm_cost_recommendations — CostAdvisor output table.

One row per (endpoint, current_model, proposed_model) triple produced by
the weekly CostAdvisor agent. Status flow: pending → reviewed →
applied | rejected. 7-day dedup window prevents the weekly re-run from
inserting the same suggestion repeatedly.

Author: Claude Opus 4.7
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_cost_recommendations (
            id                           BIGSERIAL PRIMARY KEY,
            ts_utc                       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            endpoint                     VARCHAR(128) NOT NULL,
            current_model                VARCHAR(128) NOT NULL,
            proposed_model               VARCHAR(128) NOT NULL,
            estimated_monthly_saving_usd NUMERIC(12, 6) NOT NULL,
            quality_tradeoff             TEXT NOT NULL,
            confidence                   VARCHAR(16) NOT NULL
                CHECK (confidence IN ('low','medium','high')),
            spike_flag                   BOOLEAN NOT NULL DEFAULT FALSE,
            status                       VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','reviewed','applied','rejected')),
            reviewed_at                  TIMESTAMP WITH TIME ZONE,
            reviewed_by                  VARCHAR(128),
            notes                        TEXT
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_status_ts
        ON llm_cost_recommendations (status, ts_utc DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_endpoint
        ON llm_cost_recommendations (endpoint, ts_utc DESC);
    """)
    logger.info("✅ Migration 119: llm_cost_recommendations + 2 indexes created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS llm_cost_recommendations CASCADE;")
    logger.info("Migration 119 rollback: llm_cost_recommendations dropped")
