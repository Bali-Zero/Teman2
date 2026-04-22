#!/usr/bin/env python3
"""One-shot backfill — mark NULL clients.lead_source as 'unknown-legacy'.

Discovery 2026-04-22: Bali Zero CRM schema uses `lead_source` (NOT
`utm_source`). Only 6 of 324 rows in last 90d had NULL lead_source
(98.1% coverage). This script marks them 'unknown-legacy' so post-
rollout coverage metrics can distinguish pre-fix vs post-fix state.

Idempotent: re-running only updates NULL rows (there won't be any after
the first run).

Usage:
    python scripts/sota_lead_source_backfill.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.backfill")


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL") or "postgresql://localhost:5432/nuzantara_dev"
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        # Count before
        before = await conn.fetchval(
            "SELECT COUNT(*) FROM clients "
            "WHERE lead_source IS NULL AND created_at > NOW() - INTERVAL '90 days'"
        )
        logger.info("NULL lead_source rows (90d) before: %d", before)

        if before == 0:
            logger.info("Nothing to backfill — all rows already attributed.")
            return 0

        updated = await conn.execute(
            "UPDATE clients SET lead_source = 'unknown-legacy' "
            "WHERE lead_source IS NULL AND created_at > NOW() - INTERVAL '90 days'"
        )
        logger.info("UPDATE result: %s", updated)

        after = await conn.fetchval(
            "SELECT COUNT(*) FROM clients "
            "WHERE lead_source IS NULL AND created_at > NOW() - INTERVAL '90 days'"
        )
        logger.info("NULL lead_source rows (90d) after: %d", after)

        coverage = await conn.fetchval(
            "SELECT AVG(CASE WHEN lead_source IS NOT NULL AND lead_source <> '' "
            "THEN 1.0 ELSE 0.0 END) FROM clients "
            "WHERE created_at > NOW() - INTERVAL '90 days'"
        )
        logger.info("Coverage now: %.2f%%", float(coverage or 0) * 100)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
