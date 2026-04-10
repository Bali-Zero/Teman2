#!/usr/bin/env python3
"""
Backfill differentiated risk_score on bali_zoning_layers.

Replaces the flat 0.5 with a computed 4-component score:
  - tsunami (35%): based on sea_distance_m
  - flood (25%): based on KRB_03 overlay or heuristic
  - saturation (20%): based on company density per zone
  - erosion (20%): based on SEMPDN / coastal proximity

Requires: sea_distance_m already backfilled (run import_bali_coastline.py first).

Usage:
    cd apps/backend-rag
    source .venv/bin/activate  # or venv on Air
    PYTHONPATH=. python scripts/backfill_risk_scores.py [--db-url postgresql://...]
"""

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Saturation threshold: max companies per zone before market is "full"
SATURATION_THRESHOLD = 50


def compute_tsunami_component(sea_distance_m: float | None) -> float:
    """0.0 (safe) to 1.0 (high risk) based on distance to coast."""
    if sea_distance_m is None:
        return 0.1  # unknown, slight risk
    if sea_distance_m < 500:
        return 1.0
    if sea_distance_m < 1000:
        return 0.7
    if sea_distance_m < 2000:
        return 0.4
    if sea_distance_m < 5000:
        return 0.15
    return 0.0


def compute_erosion_component(sea_distance_m: float | None) -> float:
    """Coastal erosion risk based on proximity (SEMPDN proxy)."""
    if sea_distance_m is None:
        return 0.0
    if sea_distance_m < 100:
        return 0.8
    if sea_distance_m < 300:
        return 0.4
    if sea_distance_m < 500:
        return 0.15
    return 0.0


def compute_flood_component(overlays_json: dict | None, sea_distance_m: float | None) -> float:
    """Flood risk: KRB_03 overlay if available, else heuristic."""
    if overlays_json:
        # Check for KRB_03 (disaster risk zone) in overlays
        krb = overlays_json.get("KRB_03") or overlays_json.get("krb_03")
        if krb and str(krb).lower() not in ("", "tidak ada", "none", "null"):
            return 1.0
        # SEMPDN = coastal buffer
        sempdn = overlays_json.get("SEMPDN") or overlays_json.get("sempdn")
        if sempdn and str(sempdn).lower() not in ("", "tidak ada", "none", "null"):
            return 0.6
    # Heuristic: low-elevation coastal areas have moderate flood risk
    if sea_distance_m is not None and sea_distance_m < 500:
        return 0.4
    return 0.2  # default moderate


def compute_saturation_component(company_count: int) -> float:
    """Market saturation: 0.0 (empty) to 1.0 (saturated)."""
    if company_count <= 0:
        return 0.0
    return min(1.0, company_count / SATURATION_THRESHOLD)


def compute_risk_score(
    sea_distance_m: float | None,
    company_count: int,
    overlays_json: dict | None,
) -> float:
    """Compute composite risk score (0.0 = safest, 1.0 = highest risk)."""
    tsunami = compute_tsunami_component(sea_distance_m) * 0.35
    flood = compute_flood_component(overlays_json, sea_distance_m) * 0.25
    saturation = compute_saturation_component(company_count) * 0.20
    erosion = compute_erosion_component(sea_distance_m) * 0.20

    return round(max(0.0, min(1.0, tsunami + flood + saturation + erosion)), 3)


async def backfill(db_url: str, batch_size: int = 500) -> None:
    """Backfill risk_score on all bali_zoning_layers rows."""
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = await asyncpg.connect(db_url)
    logger.info("Connected to database")

    try:
        # Count zones
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM bali_zoning_layers WHERE boundary IS NOT NULL"
        )
        logger.info("Processing %d zones...", total)

        # Check if sea_distance_m is populated
        sea_dist_count = await conn.fetchval(
            "SELECT COUNT(*) FROM bali_zoning_layers WHERE sea_distance_m IS NOT NULL"
        )
        if sea_dist_count == 0:
            logger.warning(
                "⚠️ sea_distance_m not populated — run import_bali_coastline.py first. "
                "Proceeding with heuristic-only risk scores."
            )

        # Fetch all zone data with company counts
        rows = await conn.fetch("""
            SELECT
                z.id,
                z.sea_distance_m,
                z.overlays,
                z.kodszn,
                COALESCE(comp.cnt, 0) AS company_count
            FROM bali_zoning_layers z
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS cnt
                FROM companies c
                WHERE c.latitude IS NOT NULL
                  AND c.longitude IS NOT NULL
                  AND ST_Contains(
                      z.boundary,
                      ST_SetSRID(ST_MakePoint(c.longitude, c.latitude), 4326)
                  )
            ) comp ON true
            WHERE z.boundary IS NOT NULL
        """)

        logger.info("Fetched %d zones with company counts", len(rows))

        # Compute and update in batches
        updates: list[tuple[float, str]] = []
        for row in rows:
            overlays = row["overlays"] if isinstance(row["overlays"], dict) else None
            risk = compute_risk_score(
                sea_distance_m=row["sea_distance_m"],
                company_count=row["company_count"],
                overlays_json=overlays,
            )
            updates.append((risk, str(row["id"])))

        # Batch UPDATE
        updated = 0
        for i in range(0, len(updates), batch_size):
            batch = updates[i : i + batch_size]
            await conn.executemany(
                "UPDATE bali_zoning_layers SET risk_score = $1 WHERE id = $2::uuid",
                batch,
            )
            updated += len(batch)
            if updated % 5000 == 0 or updated == len(updates):
                logger.info("  Updated %d / %d zones", updated, len(updates))

        # Stats
        stats = await conn.fetchrow("""
            SELECT
                ROUND(AVG(risk_score)::numeric, 3) AS avg_risk,
                ROUND(STDDEV(risk_score)::numeric, 3) AS stddev_risk,
                ROUND(MIN(risk_score)::numeric, 3) AS min_risk,
                ROUND(MAX(risk_score)::numeric, 3) AS max_risk,
                COUNT(*) FILTER (WHERE risk_score < 0.2) AS low_risk,
                COUNT(*) FILTER (WHERE risk_score BETWEEN 0.2 AND 0.5) AS mid_risk,
                COUNT(*) FILTER (WHERE risk_score > 0.5) AS high_risk
            FROM bali_zoning_layers
        """)

        logger.info(
            "✅ Backfill complete: %d zones updated. "
            "AVG=%.3f, STDDEV=%.3f, MIN=%.3f, MAX=%.3f | "
            "Low(<0.2)=%d, Mid(0.2-0.5)=%d, High(>0.5)=%d",
            updated,
            float(stats["avg_risk"]), float(stats["stddev_risk"]),
            float(stats["min_risk"]), float(stats["max_risk"]),
            stats["low_risk"], stats["mid_risk"], stats["high_risk"],
        )

    finally:
        await conn.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill differentiated risk_score")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    if not args.db_url:
        logger.error("DATABASE_URL not set. Use --db-url or set env var.")
        sys.exit(1)

    await backfill(args.db_url, args.batch_size)
    logger.info("🎯 Done!")


if __name__ == "__main__":
    asyncio.run(main())
