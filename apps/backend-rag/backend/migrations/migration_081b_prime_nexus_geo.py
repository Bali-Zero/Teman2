"""
Migration 081: Prime Nexus geospatial columns + geocoding job queue.

Adds PostGIS POINT geometry columns to companies and clients tables for
geocoded locations, plus a geocoding_jobs queue table for batch processing.

Part of PRIME NEXUS Sprint 1 — Foundation.
"""

import asyncio
import os

import asyncpg


async def apply(conn: asyncpg.Connection) -> None:
    """Add geo columns to companies/clients and create geocoding_jobs table."""

    # Ensure PostGIS extension exists
    await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── Companies: geo columns ───────────────────────────────────
    await conn.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS geo_point GEOMETRY(Point, 4326)
    """)
    await conn.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS rdtr_zone_code TEXT
    """)
    await conn.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMPTZ
    """)
    await conn.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS geocode_source TEXT
    """)

    # GIST index for spatial queries (ST_Contains, ST_DWithin)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_geo_point
        ON companies USING GIST(geo_point)
    """)

    # Partial index on rdtr_zone_code for zone-based queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_companies_rdtr_zone
        ON companies(rdtr_zone_code)
        WHERE rdtr_zone_code IS NOT NULL
    """)

    # ── Clients: geo columns (optional enrichment) ───────────────
    await conn.execute("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS geo_point GEOMETRY(Point, 4326)
    """)
    await conn.execute("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS rdtr_zone_code TEXT
    """)
    await conn.execute("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMPTZ
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clients_geo_point
        ON clients USING GIST(geo_point)
    """)

    # ── Geocoding job queue ──────────────────────────────────────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS geocoding_jobs (
            id SERIAL PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            address_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result_lat DOUBLE PRECISION,
            result_lng DOUBLE PRECISION,
            result_source TEXT,
            error_message TEXT,
            attempts INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            processed_at TIMESTAMPTZ,
            UNIQUE(entity_type, entity_id)
        )
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_geocoding_jobs_pending
        ON geocoding_jobs(status)
        WHERE status = 'pending'
    """)


async def downgrade(conn: asyncpg.Connection) -> None:
    """Remove geo columns and geocoding_jobs table."""
    await conn.execute("DROP TABLE IF EXISTS geocoding_jobs")

    await conn.execute("DROP INDEX IF EXISTS idx_clients_geo_point")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS geocoded_at")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS rdtr_zone_code")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS geo_point")

    await conn.execute("DROP INDEX IF EXISTS idx_companies_rdtr_zone")
    await conn.execute("DROP INDEX IF EXISTS idx_companies_geo_point")
    await conn.execute("ALTER TABLE companies DROP COLUMN IF EXISTS geocode_source")
    await conn.execute("ALTER TABLE companies DROP COLUMN IF EXISTS geocoded_at")
    await conn.execute("ALTER TABLE companies DROP COLUMN IF EXISTS rdtr_zone_code")
    await conn.execute("ALTER TABLE companies DROP COLUMN IF EXISTS geo_point")


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL not set")
        return
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = await asyncpg.connect(url)
    try:
        await apply(conn)
        print("✅ Migration 081 applied: Prime Nexus geo columns + geocoding_jobs")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
