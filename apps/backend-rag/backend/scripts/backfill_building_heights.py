"""
Backfill max_height_meters in master_building_codes from JSON TB strings.

Usage:
    PYTHONPATH=. python backend/scripts/backfill_building_heights.py --dry-run
    PYTHONPATH=. python backend/scripts/backfill_building_heights.py
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

import asyncpg

from backend.services.prime.prime_nexus_service import parse_tb_to_meters

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

JSON_PATH = Path(__file__).parent.parent / "data" / "master_building_codes_complete.json"


async def backfill(dry_run: bool = True) -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return

    with open(JSON_PATH, encoding="utf-8") as f:
        codes: dict[str, dict[str, str]] = json.load(f)

    updates: list[tuple[str, float]] = []
    for zone_code, data in codes.items():
        meters = parse_tb_to_meters(data.get("TB"))
        if meters is not None:
            updates.append((zone_code, meters))

    logger.info("Parsed %d zone heights from JSON (%d total zones)", len(updates), len(codes))

    if dry_run:
        for zone_code, meters in updates:
            logger.info("  [DRY] %s → %.1f m", zone_code, meters)
        return

    conn = await asyncpg.connect(db_url)
    try:
        updated = 0
        for zone_code, meters in updates:
            result = await conn.execute(
                """
                UPDATE master_building_codes
                SET max_height_meters = $1
                WHERE kodszn = $2 AND (max_height_meters IS NULL OR max_height_meters != $1)
                """,
                meters,
                zone_code,
            )
            count = int(result.split()[-1])
            if count > 0:
                updated += count
                logger.info("  Updated %s → %.1f m (%d rows)", zone_code, meters, count)
        logger.info("Done. Updated %d rows total.", updated)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill building height data")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))
