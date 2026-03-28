#!/usr/bin/env python3
"""
Nuzantara Prime - Bulk Geospatial Ingestion for Harvested Zones
Loads multiple GISTARU/BATARA JSON files into PostGIS.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bulk_ingest")

# Add the parent directory to sys.path to allow imports from backend
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from backend.app.core.config import settings


async def process_file(file_path: Path, pool: asyncpg.Pool):
    """Processes a single JSON file and inserts features into DB."""
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return 0

    features = []
    if isinstance(data, dict):
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
    elif isinstance(data, list):
        # Handle cases where the file is a direct list of features
        features = data
    else:
        logger.warning(f"Unsupported JSON structure in {file_path.name}")
        return 0

    if not features:
        return 0

    # Extract subdistrict from filename (e.g., Canggu_5103030005.json -> Canggu)
    file_stem = file_path.stem
    subdistrict_from_name = file_stem.split("_")[0]

    rows = []
    for feature in features:
        if not isinstance(feature, dict):
            continue

        geom = feature.get("geometry")
        # If it's the custom master_zoning format, it might be nested
        if not geom and "raw_data_sample" in feature:
            feature = feature["raw_data_sample"]
            geom = feature.get("geometry")

        if not geom or geom.get("type") not in ["Polygon", "MultiPolygon"]:
            continue

        props = feature.get("properties", {})
        attr = props.get("attribute", {})

        # Zone object may be at props["zone"] or attr["zone"]
        zone_obj = props.get("zone") or attr.get("zone") or {}
        zoning_type = zone_obj.get("name", "Unknown")
        zoning_code = zone_obj.get("code", "Unknown")

        district = attr.get("kabupaten") or "Badung"
        subdistrict = attr.get("kecamatan") or subdistrict_from_name

        allowed_kbli = json.dumps([zoning_code])
        geom_json = json.dumps(geom)

        rows.append(
            (
                district,
                subdistrict,
                f"{zoning_code}: {zoning_type}",
                allowed_kbli,
                geom_json,
                0.0,
                0.5,
            ),
        )

    if not rows:
        return 0

    query = """
        INSERT INTO bali_zoning_layers (
            district_name, subdistrict_name, zoning_type,
            allowed_kbli, boundary, avg_price_per_are, risk_score
        ) VALUES (
            $1, $2, $3, $4::jsonb,
            ST_SetSRID(ST_MakeValid(ST_GeomFromGeoJSON($5)), 4326),
            $6, $7
        )
    """
    inserted = 0
    async with pool.acquire() as conn:
        try:
            await conn.executemany(query, rows)
            inserted = len(rows)
        except Exception as e:
            logger.warning(
                f"Batch insert failed for {file_path.name}: {e} — falling back to row-by-row",
            )
            for row in rows:
                try:
                    await conn.execute(query, *row)
                    inserted += 1
                except Exception as row_err:
                    logger.debug(f"Row skip in {file_path.name}: {row_err}")

    return inserted


async def bulk_ingest(directories: list[str]):
    """Main loop for bulk ingestion."""
    logger.info("Connecting to database...")
    try:
        pool = await asyncpg.create_pool(settings.database_url)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return

    total_inserted = 0
    files_processed = 0

    for dir_path in directories:
        path = Path(dir_path)
        if not path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            continue

        logger.info(f"Scanning directory (recursively): {dir_path}")
        # Recursive glob to find everything
        json_files = list(path.rglob("*.json"))

        for file_path in json_files:
            # Skip non-zoning files
            if file_path.name in ["batara_endpoints.json", "package.json"]:
                continue

            count = await process_file(file_path, pool)
            total_inserted += count
            files_processed += 1
            if files_processed % 10 == 0:
                logger.info(
                    f"Processed {files_processed} files... ({total_inserted} polygons so far)",
                )

    await pool.close()
    logger.info("✅ BULK INGESTION COMPLETE!")
    logger.info(f"Total files: {files_processed}")
    logger.info(f"Total polygons inserted: {total_inserted}")


if __name__ == "__main__":
    dirs = sys.argv[1:]
    if not dirs:
        print("Usage: python bulk_ingest_harvested_zones.py <dir1> <dir2> ...")
        sys.exit(1)

    asyncio.run(bulk_ingest(dirs))
