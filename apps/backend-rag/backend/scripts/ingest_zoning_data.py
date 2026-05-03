#!/usr/bin/env python3
"""
Nuzantara Prime - Geospatial Data Ingestion
Loads GeoJSON polygon data into the PostGIS database.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ingest_zoning")

# Add the parent directory to sys.path to allow imports from backend
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncpg  # noqa: E402

from backend.app.core.config import settings  # noqa: E402


async def ingest_geojson(file_path: Path):
    """Parses a GeoJSON file and inserts it into PostGIS."""
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return

    logger.info(f"Loading GeoJSON data from {file_path}...")
    with open(file_path, encoding="utf-8") as f:
        geojson_data = json.load(f)

    if geojson_data.get("type") != "FeatureCollection":
        logger.error("Expected a GeoJSON FeatureCollection.")
        return

    features = geojson_data.get("features", [])
    if not features:
        logger.warning("No features found in GeoJSON.")
        return

    # Initialize DB connection
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(settings.database_url)

    inserted_count = 0

    async with pool.acquire() as conn:
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry")

            if not geom or geom.get("type") not in ["Polygon", "MultiPolygon"]:
                logger.warning(
                    f"Skipping feature without valid Polygon geometry: {props.get('name', 'Unknown')}",
                )
                continue

            district = props.get("district", "Unknown")
            subdistrict = props.get("subdistrict", "Unknown")
            zoning_type = props.get("zoning_type", "Unclassified")
            allowed_kbli = json.dumps(props.get("allowed_kbli", []))
            avg_price = props.get("avg_price_per_are", 0.0)
            risk_score = props.get("risk_score", 0.5)

            # PostGIS uses ST_GeomFromGeoJSON for ingestion
            geom_json = json.dumps(geom)

            query = """
                INSERT INTO bali_zoning_layers (
                    district_name, subdistrict_name, zoning_type,
                    allowed_kbli, boundary, avg_price_per_are, risk_score
                ) VALUES (
                    $1, $2, $3, $4::jsonb,
                    ST_SetSRID(ST_GeomFromGeoJSON($5), 4326),
                    $6, $7
                )
            """
            try:
                await conn.execute(
                    query,
                    district,
                    subdistrict,
                    zoning_type,
                    allowed_kbli,
                    geom_json,
                    avg_price,
                    risk_score,
                )
                inserted_count += 1
            except Exception as e:
                logger.error(f"Failed to insert feature {district} - {subdistrict}: {e}")

    logger.info(f"✅ Ingestion complete. Inserted {inserted_count} zoning polygons.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_zoning_data.py <path_to_geojson>")
        sys.exit(1)

    target_file = Path(sys.argv[1])
    asyncio.run(ingest_geojson(target_file))
