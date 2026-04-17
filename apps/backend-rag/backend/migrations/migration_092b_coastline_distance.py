"""
Migration 092: Coastline distance infrastructure for Prime Nexus.

Adds:
- bali_coastline table (OSM coastline geometry for ST_Distance)
- sea_distance_m column on bali_zoning_layers (precomputed per-zone centroid)
- overlays JSONB column on bali_zoning_layers (for future overlay storage)
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "092_coastline_distance"
DESCRIPTION = "Prime Nexus: coastline table + sea_distance_m + overlays column"


async def check_if_applied(conn) -> bool:
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'bali_coastline')"
    )
    return result


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    # 1. Coastline table — stores OSM Bali coastline as MultiLineString
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bali_coastline (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'bali_main',
            geom GEOMETRY(MultiLineString, 4326) NOT NULL,
            source TEXT NOT NULL DEFAULT 'openstreetmap',
            imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bali_coastline_geom ON bali_coastline USING GIST(geom)"
    )

    # 2. Precomputed sea distance on zoning layers (meters from zone centroid to coast)
    col_exists = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'bali_zoning_layers' AND column_name = 'sea_distance_m'
        )
    """)
    if not col_exists:
        await conn.execute(
            "ALTER TABLE bali_zoning_layers ADD COLUMN sea_distance_m FLOAT"
        )

    # 3. Overlays JSONB for future per-zone overlay storage
    ov_exists = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'bali_zoning_layers' AND column_name = 'overlays'
        )
    """)
    if not ov_exists:
        await conn.execute(
            "ALTER TABLE bali_zoning_layers ADD COLUMN overlays JSONB DEFAULT '{}'"
        )

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute(
        "ALTER TABLE bali_zoning_layers DROP COLUMN IF EXISTS overlays"
    )
    await conn.execute(
        "ALTER TABLE bali_zoning_layers DROP COLUMN IF EXISTS sea_distance_m"
    )
    await conn.execute("DROP TABLE IF EXISTS bali_coastline CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
