"""
Batch geocoding for companies and clients using Google Geocoding API.

Cost: ~$10 one-time for 2000 companies (40k free/month tier).
Rate: Google API has no 1-req/s limit (unlike Nominatim).

Pipeline:
  1. Query companies with address but no geo_point
  2. Insert into geocoding_jobs (pending)
  3. Process pending jobs via Google Geocoding API
  4. Update companies.geo_point + rdtr_zone_code
  5. Optionally reverse-resolve zone via Prime Nexus Layer 1

Usage:
    cd apps/backend-rag
    PYTHONPATH=. DATABASE_URL=... GOOGLE_MAPS_API_KEY=... python backend/scripts/backfill_geocoding.py --limit 100

For weekly cron (new companies only):
    PYTHONPATH=. DATABASE_URL=... GOOGLE_MAPS_API_KEY=... python backend/scripts/backfill_geocoding.py --new-only
"""

import argparse
import asyncio
import logging
import os
import time

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def enqueue_pending(conn: asyncpg.Connection, limit: int, new_only: bool) -> int:
    """Insert companies with address but no geo_point into geocoding_jobs."""
    where_clause = """
        WHERE (c.registered_address IS NOT NULL AND c.registered_address != '')
          AND c.geo_point IS NULL
    """
    if new_only:
        where_clause += """
          AND NOT EXISTS (
              SELECT 1 FROM geocoding_jobs gj
              WHERE gj.entity_type = 'company' AND gj.entity_id = c.id
          )
        """

    query = f"""
        INSERT INTO geocoding_jobs (entity_type, entity_id, address_text)
        SELECT 'company', c.id, c.registered_address
        FROM companies c
        {where_clause}
        ORDER BY c.id
        LIMIT $1
        ON CONFLICT (entity_type, entity_id) DO NOTHING
    """
    result = await conn.execute(query, limit)
    count = int(result.split()[-1]) if result else 0
    logger.info("Enqueued %d companies for geocoding", count)
    return count


async def geocode_address(api_key: str, address: str) -> tuple[float, float, str] | None:
    """Geocode an address using Google Maps Geocoding API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(GOOGLE_GEOCODE_URL, params={
                "address": f"{address}, Bali, Indonesia",
                "key": api_key,
                "region": "id",
                "language": "en",
            })
            data = resp.json()

            if data.get("status") != "OK" or not data.get("results"):
                return None

            location = data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"], "google"
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", address[:50], exc)
        return None


async def process_jobs(conn: asyncpg.Connection, api_key: str, batch_size: int = 50) -> dict:
    """Process pending geocoding jobs."""
    jobs = await conn.fetch("""
        SELECT id, entity_type, entity_id, address_text, attempts
        FROM geocoding_jobs
        WHERE status = 'pending' AND attempts < 3
        ORDER BY id
        LIMIT $1
    """, batch_size)

    stats = {"processed": 0, "success": 0, "failed": 0, "skipped": 0}

    for job in jobs:
        stats["processed"] += 1
        job_id = job["id"]
        address = job["address_text"]

        result = await geocode_address(api_key, address)

        if result:
            lat, lng, source = result
            # Update job
            await conn.execute("""
                UPDATE geocoding_jobs
                SET status = 'completed', result_lat = $1, result_lng = $2,
                    result_source = $3, processed_at = NOW(), attempts = attempts + 1
                WHERE id = $4
            """, lat, lng, source, job_id)

            # Update company/client geo_point (whitelist table name — no SQL injection)
            entity_type = job["entity_type"]
            entity_id = job["entity_id"]
            _ALLOWED_TABLES = {"company": "companies", "client": "clients"}
            table = _ALLOWED_TABLES.get(entity_type)
            if not table:
                logger.warning("Unknown entity_type '%s' for job #%d", entity_type, job_id)
                continue
            await conn.execute(f"""
                UPDATE {table}
                SET geo_point = ST_SetSRID(ST_MakePoint($1, $2), 4326),
                    geocoded_at = NOW(),
                    geocode_source = $3
                WHERE id = $4
            """, lng, lat, source, entity_id)

            stats["success"] += 1
            logger.info(
                "✅ Geocoded %s #%d: %s → (%.6f, %.6f)",
                entity_type, entity_id, address[:40], lat, lng,
            )
        else:
            await conn.execute("""
                UPDATE geocoding_jobs
                SET attempts = attempts + 1,
                    error_message = 'Google API returned no results',
                    status = CASE WHEN attempts + 1 >= 3 THEN 'failed' ELSE 'pending' END
                WHERE id = $1
            """, job_id)
            stats["failed"] += 1
            logger.warning("❌ Failed to geocode %s #%d: %s", job["entity_type"], job["entity_id"], address[:40])

        # Small delay to be respectful (even though Google doesn't require it)
        await asyncio.sleep(0.1)

    return stats


async def reverse_resolve_zones(conn: asyncpg.Connection) -> int:
    """Update rdtr_zone_code for geocoded companies using PostGIS."""
    result = await conn.execute("""
        UPDATE companies c
        SET rdtr_zone_code = sub.zone_code
        FROM (
            SELECT c2.id,
                   SPLIT_PART(bz.zoning_type, ':', 1) AS zone_code
            FROM companies c2
            JOIN bali_zoning_layers bz
              ON ST_Contains(bz.boundary, c2.geo_point)
            WHERE c2.geo_point IS NOT NULL
              AND c2.rdtr_zone_code IS NULL
        ) sub
        WHERE c.id = sub.id
    """)
    count = int(result.split()[-1]) if result else 0
    logger.info("✅ Reverse-resolved zones for %d companies", count)
    return count


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch geocode companies")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process")
    parser.add_argument("--new-only", action="store_true", help="Only process new (never-attempted) companies")
    parser.add_argument("--batch-size", type=int, default=50, help="Jobs per batch")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    if not url:
        logger.error("DATABASE_URL not set")
        return
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY not set (get from Google Cloud Console)")
        return

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    conn = await asyncpg.connect(url)
    try:
        start = time.time()

        # Step 1: Enqueue
        enqueued = await enqueue_pending(conn, args.limit, args.new_only)
        if enqueued == 0:
            logger.info("No companies to geocode. All done!")
            return

        # Step 2: Process
        stats = await process_jobs(conn, api_key, args.batch_size)

        # Step 3: Reverse resolve zones
        zones_resolved = await reverse_resolve_zones(conn)

        elapsed = time.time() - start
        logger.info(
            "🏁 Geocoding complete in %.1fs: %d processed, %d success, %d failed, %d zones resolved",
            elapsed, stats["processed"], stats["success"], stats["failed"], zones_resolved,
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
