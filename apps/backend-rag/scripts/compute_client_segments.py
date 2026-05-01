#!/usr/bin/env python3
"""Compute client_segments rows: LTV per client + tier assignment.

Run once post-deploy of migration 149. Idempotent: re-running updates rows.
From Sprint 4 onward, Cell skill `measure_conversion` will trigger weekly
re-computation; this script is the bootstrap.

Schema reality (verified 2026-05-01):
    practices.total_invoiced_idr NUMERIC  — pre-aggregated IDR amount
    practices.completed_at TIMESTAMPTZ    — completion timestamp
    practices.status TEXT                 — 'completed' | etc.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §4 Sprint 0.2

Usage:
    DATABASE_URL=postgres://... python scripts/compute_client_segments.py
    python scripts/compute_client_segments.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg

logger = logging.getLogger("compute_client_segments")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Static USD conversion. Refresh rate quarterly; design choice: simplicity > FX accuracy.
IDR_PER_USD: float = 15_500.0


def compute_ltv_usd(practices: list[dict[str, Any]]) -> float:
    """Sum completed practice IDR amounts converted to USD.

    Args:
        practices: list of dicts with keys total_invoiced_idr (numeric|None), status (str).

    Returns:
        Total LTV in USD; 0.0 if no completed practices or all amounts null/zero.
    """
    total_idr: float = 0.0
    for p in practices:
        if p.get("status") != "completed":
            continue
        amount = p.get("total_invoiced_idr")
        if amount is None:
            continue
        total_idr += float(amount)
    return total_idr / IDR_PER_USD if total_idr else 0.0


def assign_tier(ltv_usd: float) -> int:
    """Map LTV to tier 1/2/3.

    Tier 1: >= $5000 (high-value)
    Tier 2: $2000-4999 (medium)
    Tier 3: <$2000 (low) — also default for new/unknown clients.
    """
    if ltv_usd >= 5000:
        return 1
    if ltv_usd >= 2000:
        return 2
    return 3


async def verify_schema(conn: asyncpg.Connection) -> None:
    """Defensive check: required columns must exist before running queries.

    Aborts with clear error if schema drift renamed/removed required columns.
    """
    required = [
        ("practices", "total_invoiced_idr"),
        ("practices", "completed_at"),
        ("practices", "status"),
        ("practices", "client_id"),
        ("clients", "id"),
        ("clients", "deleted_at"),
        ("client_segments", "client_id"),  # Migration 149 must be applied first
    ]
    missing: list[str] = []
    for table, column in required:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = $1 AND column_name = $2
            )
            """,
            table,
            column,
        )
        if not exists:
            missing.append(f"{table}.{column}")
    if missing:
        raise RuntimeError(
            f"Schema verification failed. Missing columns: {missing}. "
            "Migration 149 may not be applied, or schema drift occurred. "
            "Aborting to avoid wrong data."
        )


async def compute_for_all_clients(
    conn: asyncpg.Connection,
    dry_run: bool = False,
) -> dict[str, int]:
    """Compute and upsert client_segments for every client. Returns counts per tier."""
    rows = await conn.fetch(
        """
        SELECT
            c.id AS client_id,
            COALESCE(json_agg(json_build_object(
                'total_invoiced_idr', p.total_invoiced_idr,
                'status', p.status
            )) FILTER (WHERE p.id IS NOT NULL), '[]'::json) AS practices_json
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id
        """,
    )

    counts: dict[str, int] = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "total": 0}
    for row in rows:
        practices = list(row["practices_json"])
        ltv = compute_ltv_usd(practices)
        tier = assign_tier(ltv)
        counts[f"tier_{tier}"] += 1
        counts["total"] += 1

        if dry_run:
            continue

        await conn.execute(
            """
            INSERT INTO client_segments (client_id, tier, lifetime_value_usd, computed_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (client_id) DO UPDATE
                SET tier = EXCLUDED.tier,
                    lifetime_value_usd = EXCLUDED.lifetime_value_usd,
                    computed_at = EXCLUDED.computed_at
            """,
            row["client_id"],
            tier,
            ltv,
        )

    return counts


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        await verify_schema(conn)
        counts = await compute_for_all_clients(conn, dry_run=args.dry_run)
        mode = "DRY-RUN" if args.dry_run else "WRITE"
        logger.info(
            f"[{mode}] processed {counts['total']} clients: "
            f"tier_1={counts['tier_1']}, tier_2={counts['tier_2']}, tier_3={counts['tier_3']}",
        )
        return 0
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
