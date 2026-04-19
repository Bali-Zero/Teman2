"""
Migration 121: visa_checks — persistence for Visa Check app (Clock + Match).

Why
---
Visa Check is the first of 4 homepage apps that replaces the decorative
FunnelFeature sections. It has 2 branches:

- Clock: user already in Indonesia, knows visa_type + entry_date → gets
  countdown page `/visa/clock/[hash]` with 5-checkpoint timeline.
- Match: user planning, does 4-step wizard (nationality / purpose /
  duration / budget) → gets `/visa/match/[hash]` with recommended visa
  and PricingTool cost.

Both branches produce a shareable `/visa/<branch>/<hash>` URL that renders
from this table on every view. The table is append-only for result rows
(edits happen only to `view_count`, `share_count`).

Schema design decision
----------------------
Single table with nullable columns per branch (branch='clock' → match cols
NULL, and vice versa) instead of two tables. Rationale:

1. Common fields (hash, branch, client_fp, view_count, share_count,
   created_at) dominate; a JOIN on hash would be redundant.
2. Both branches reach the same result-page renderer that reads from one
   row by hash — a union view would require more code for no gain.
3. Index cost is bounded: partial indexes on branch-specific columns only
   include applicable rows.

Hash format: 16-char nanoid (URL-safe, 62^16 = 10^28 collision space).

Indexes
-------
- idx_visa_checks_branch_created: time-series rollup per branch for KPI
  dashboards and wizard-abandon analysis.
- idx_visa_checks_expiry_clock: partial index for the daily reminder cron
  that scans Clock rows expiring within 60 days.
- idx_visa_checks_fp_recent: partial index for 24h idempotent re-submission
  (same user clicking Submit twice should not create 2 rows).

Companion
---------
- backend/services/visa_check/ — branch logic, decision tree, repository
- backend/app/routers/visa_check.py — 5 endpoints
- backend/services/visa_check/match_tree.py — rule-based visa recommender
- apps/mouth/src/app/visa/ — 5 pages (entry, clock form, clock result,
  match wizard, match result)

Idempotent: safe to re-run.

Plan: docs/plans/2026-04-19-4apps/01-visa-check.md (migration 119 in plan, renumbered to 121)
Author: Claude Opus 4.7
Date: 2026-04-20
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS visa_checks (
            hash                    VARCHAR(20) PRIMARY KEY,
            branch                  VARCHAR(8)  NOT NULL
                                    CHECK (branch IN ('clock', 'match')),
            client_fp               VARCHAR(32),
            view_count              INT NOT NULL DEFAULT 0,
            share_count             INT NOT NULL DEFAULT 0,
            created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

            -- Clock branch (NULL when branch='match')
            visa_type               VARCHAR(16),
            entry_date              DATE,
            expiry_date             DATE,
            extensions_possible     INT,
            extension_days          INT,

            -- Match branch (NULL when branch='clock')
            nationality             VARCHAR(3),
            purpose                 VARCHAR(32),
            duration_months         INT,
            budget_band             VARCHAR(16),
            recommended_visa        VARCHAR(16),
            recommendation_reason   TEXT,
            pre_arrival_steps       JSONB,
            alternatives            JSONB,
            expected_arrival_date   DATE,
            estimated_cost_idr      BIGINT
        );
    """)

    await conn.execute("""
        COMMENT ON TABLE visa_checks IS
            'Visa Check app result store. One row per hash = one shareable /visa/<branch>/<hash> page. Clock and Match branches share the same table with nullable per-branch columns.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN visa_checks.branch IS
            'clock = user already in Indonesia with known visa; match = user planning, went through 4-step wizard.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN visa_checks.hash IS
            '16-char URL-safe nanoid. Used as public identifier in /visa/<branch>/<hash>.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN visa_checks.client_fp IS
            'Opaque browser fingerprint (not user-identifying). Used for 24h de-duplication.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN visa_checks.estimated_cost_idr IS
            'Match-only. Total cost (Bali Zero fee + gov fees) in IDR. SOURCE: PricingTool; never hardcoded.';
    """)

    # Branch analytics: time-series per branch for KPI dashboards.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_checks_branch_created
            ON visa_checks (branch, created_at DESC);
    """)

    # Clock reminder cron: rows expiring within 60 days.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_checks_expiry_clock
            ON visa_checks (expiry_date)
            WHERE branch = 'clock' AND expiry_date IS NOT NULL;
    """)

    # Idempotent re-submission guard (24h window).
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visa_checks_fp_recent
            ON visa_checks (client_fp, created_at DESC)
            WHERE client_fp IS NOT NULL;
    """)

    logger.info(
        "✅ Migration 121: visa_checks table + 3 indexes created (idempotent)"
    )


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_visa_checks_fp_recent;")
    await conn.execute("DROP INDEX IF EXISTS idx_visa_checks_expiry_clock;")
    await conn.execute("DROP INDEX IF EXISTS idx_visa_checks_branch_created;")
    await conn.execute("DROP TABLE IF EXISTS visa_checks;")
    logger.info("Migration 121 rollback: visa_checks table + 3 indexes dropped")
