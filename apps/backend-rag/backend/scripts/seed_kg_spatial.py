"""
Seed KG with spatial nodes (zone + area) from bali_zoning_layers.

Creates:
- 'zone' entity nodes from distinct (kodszn, zoning_type) in bali_zoning_layers
- 'area' entity nodes from distinct (district_name, subdistrict_name)
- LOCATED_IN edges from geocoded companies to their rdtr_zone_code

Does NOT create ALLOWS/RESTRICTS edges (compatibility stays in Python dict).

Usage:
    cd apps/backend-rag
    PYTHONPATH=. DATABASE_URL=... python backend/scripts/seed_kg_spatial.py
"""

import asyncio
import json
import logging
import os
import uuid

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_zone_nodes(conn: asyncpg.Connection) -> int:
    """Create KG nodes for distinct zones in bali_zoning_layers."""
    rows = await conn.fetch("""
        SELECT DISTINCT kodszn, zoning_type, district_name
        FROM bali_zoning_layers
        WHERE kodszn IS NOT NULL
        ORDER BY kodszn
    """)

    count = 0
    for row in rows:
        zone_code = row["kodszn"]
        zone_type = row["zoning_type"] or ""
        zone_name = zone_type.split(":", 1)[1].strip() if ":" in zone_type else zone_type

        entity_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"zone:{zone_code}")
        payload = {
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "district": row["district_name"] or "",
        }

        await conn.execute("""
            INSERT INTO kg_nodes (entity_id, entity_name, entity_type, source_collection, payload, confidence, created_at)
            VALUES ($1, $2, 'zone', 'bali_zoning_layers', $3, 0.95, NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                confidence = EXCLUDED.confidence
        """, entity_id, f"Zone {zone_code}: {zone_name}", json.dumps(payload))
        count += 1

    logger.info("✅ Seeded %d zone nodes", count)
    return count


async def seed_area_nodes(conn: asyncpg.Connection) -> int:
    """Create KG nodes for distinct areas (district + subdistrict)."""
    rows = await conn.fetch("""
        SELECT DISTINCT district_name, subdistrict_name
        FROM bali_zoning_layers
        WHERE district_name IS NOT NULL AND subdistrict_name IS NOT NULL
        ORDER BY district_name, subdistrict_name
    """)

    count = 0
    for row in rows:
        district = row["district_name"]
        subdistrict = row["subdistrict_name"]
        area_name = f"{subdistrict}, {district}"

        entity_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"area:{district}:{subdistrict}")
        payload = {
            "area_name": area_name,
            "district": district,
            "subdistrict": subdistrict,
        }

        await conn.execute("""
            INSERT INTO kg_nodes (entity_id, entity_name, entity_type, source_collection, payload, confidence, created_at)
            VALUES ($1, $2, 'area', 'bali_zoning_layers', $3, 0.95, NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                confidence = EXCLUDED.confidence
        """, entity_id, area_name, json.dumps(payload))
        count += 1

    logger.info("✅ Seeded %d area nodes", count)
    return count


async def seed_located_in_edges(conn: asyncpg.Connection) -> int:
    """Create LOCATED_IN edges from geocoded companies to their zone nodes."""
    rows = await conn.fetch("""
        SELECT c.id, c.company_name, c.rdtr_zone_code
        FROM companies c
        WHERE c.rdtr_zone_code IS NOT NULL
          AND c.geo_point IS NOT NULL
    """)

    count = 0
    for row in rows:
        zone_code = row["rdtr_zone_code"]
        company_name = row["company_name"]

        # Find company entity in KG (if exists)
        company_node = await conn.fetchrow("""
            SELECT entity_id FROM kg_nodes
            WHERE entity_type = 'pt_pma' AND entity_name ILIKE $1
            LIMIT 1
        """, f"%{company_name}%")

        if not company_node:
            continue

        zone_entity_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"zone:{zone_code}")

        # Check zone node exists
        zone_exists = await conn.fetchval(
            "SELECT 1 FROM kg_nodes WHERE entity_id = $1", zone_entity_id,
        )
        if not zone_exists:
            continue

        await conn.execute("""
            INSERT INTO kg_edges (source_entity_id, target_entity_id, relation_type, confidence)
            VALUES ($1, $2, 'LOCATED_IN', 0.9)
            ON CONFLICT (source_entity_id, target_entity_id, relation_type) DO NOTHING
        """, company_node["entity_id"], zone_entity_id)
        count += 1

    logger.info("✅ Created %d LOCATED_IN edges (company → zone)", count)
    return count


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        logger.error("DATABASE_URL not set")
        return
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    conn = await asyncpg.connect(url)
    try:
        zones = await seed_zone_nodes(conn)
        areas = await seed_area_nodes(conn)
        edges = await seed_located_in_edges(conn)
        logger.info(
            "✅ KG spatial seed complete: %d zones, %d areas, %d LOCATED_IN edges",
            zones, areas, edges,
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
