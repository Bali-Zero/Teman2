#!/usr/bin/env python3
"""
Import Bali coastline from OpenStreetMap and backfill sea_distance_m.

Downloads the pre-extracted OSM coastline (land polygons), clips to Bali,
extracts boundary as MULTILINESTRING, inserts into bali_coastline table,
then backfills sea_distance_m on all bali_zoning_layers rows.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate  # or venv on Air
    PYTHONPATH=. python scripts/import_bali_coastline.py [--db-url postgresql://...]

Requires: shapely, asyncpg (already in venv)
Optional: fiona (for shapefile reading) — falls back to OGR subprocess
"""

import argparse
import asyncio
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Bali bounding box (generous)
BALI_BBOX = {
    "min_lat": -8.86,
    "max_lat": -8.05,
    "min_lng": 114.42,
    "max_lng": 115.72,
}

# OSM coastline data URL (land polygons, WGS84, ~600MB full, we clip to Bali)
COASTLINE_URL = "https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip"

# Alternative: use Overpass for just Bali coastline (much smaller download)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:120];
(
  way["natural"="coastline"]({min_lat},{min_lng},{max_lat},{max_lng});
);
out body;
>;
out skel qt;
""".format(**BALI_BBOX)


async def get_db_connection(db_url: str) -> asyncpg.Connection:
    """Create a database connection."""
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return await asyncpg.connect(db_url)


def fetch_coastline_overpass() -> list[list[tuple[float, float]]]:
    """Fetch Bali coastline via Overpass API (small download, ~100KB)."""
    import httpx

    logger.info("Fetching Bali coastline from Overpass API...")
    resp = httpx.post(OVERPASS_URL, data={"data": OVERPASS_QUERY}, timeout=180.0)
    resp.raise_for_status()
    data = resp.json()

    # Build node lookup
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[list[int]] = []
    for elem in data.get("elements", []):
        if elem["type"] == "node":
            nodes[elem["id"]] = (elem["lon"], elem["lat"])
        elif elem["type"] == "way":
            ways.append(elem.get("nodes", []))

    # Convert ways to coordinate lists
    lines: list[list[tuple[float, float]]] = []
    for way_nodes in ways:
        coords = [nodes[nid] for nid in way_nodes if nid in nodes]
        if len(coords) >= 2:
            lines.append(coords)

    logger.info("Fetched %d coastline segments from Overpass", len(lines))
    return lines


def try_shapefile_approach(tmpdir: str) -> list[list[tuple[float, float]]] | None:
    """Try to extract coastline from local shapefile if ogr2ogr is available."""
    try:
        # Check if ogr2ogr is available
        subprocess.run(["ogr2ogr", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    # Check for local land polygons file
    local_files = [
        Path.home() / "data" / "land-polygons-split-4326" / "land_polygons.shp",
        Path("/tmp/land-polygons-split-4326/land_polygons.shp"),
    ]
    shp_path = next((p for p in local_files if p.exists()), None)
    if not shp_path:
        return None

    logger.info("Using local shapefile: %s", shp_path)
    out_geojson = os.path.join(tmpdir, "bali_coast.geojson")
    bbox = f"{BALI_BBOX['min_lng']},{BALI_BBOX['min_lat']},{BALI_BBOX['max_lng']},{BALI_BBOX['max_lat']}"

    subprocess.run([
        "ogr2ogr", "-f", "GeoJSON", out_geojson, str(shp_path),
        "-clipsrc", *bbox.split(","),
        "-nlt", "MULTILINESTRING",
    ], check=True)

    with open(out_geojson) as f:
        geojson = json.load(f)

    lines: list[list[tuple[float, float]]] = []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom["type"] == "MultiLineString":
            for ring in geom["coordinates"]:
                lines.append([(c[0], c[1]) for c in ring])
        elif geom["type"] == "LineString":
            lines.append([(c[0], c[1]) for c in geom["coordinates"]])
        elif geom["type"] == "Polygon":
            # Extract exterior ring as linestring
            lines.append([(c[0], c[1]) for c in geom["coordinates"][0]])
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                lines.append([(c[0], c[1]) for c in poly[0]])

    return lines if lines else None


def lines_to_wkt_multilinestring(lines: list[list[tuple[float, float]]]) -> str:
    """Convert list of coordinate lists to WKT MULTILINESTRING."""
    parts: list[str] = []
    for line in lines:
        if len(line) < 2:
            continue
        coords_str = ", ".join(f"{lng} {lat}" for lng, lat in line)
        parts.append(f"({coords_str})")
    return f"MULTILINESTRING({', '.join(parts)})"


async def import_coastline(conn: asyncpg.Connection, lines: list[list[tuple[float, float]]]) -> None:
    """Insert coastline into bali_coastline table."""
    # Clear existing
    await conn.execute("DELETE FROM bali_coastline")

    wkt = lines_to_wkt_multilinestring(lines)
    total_points = sum(len(line) for line in lines)
    logger.info("Inserting coastline: %d segments, %d total points", len(lines), total_points)

    await conn.execute("""
        INSERT INTO bali_coastline (name, geom, source)
        VALUES ('bali_main', ST_MakeValid(ST_GeomFromText($1, 4326)), 'openstreetmap')
    """, wkt)

    # Verify
    row = await conn.fetchrow("""
        SELECT ST_NPoints(geom) as npoints,
               ST_Length(geom::geography) / 1000.0 as length_km
        FROM bali_coastline
        WHERE name = 'bali_main'
    """)
    if row:
        logger.info(
            "✅ Coastline inserted: %d points, %.1f km total length",
            row["npoints"], row["length_km"],
        )


async def backfill_sea_distance(conn: asyncpg.Connection) -> None:
    """Backfill sea_distance_m on all bali_zoning_layers rows."""
    # Check coastline exists
    count = await conn.fetchval("SELECT COUNT(*) FROM bali_coastline")
    if count == 0:
        logger.error("No coastline data found — run import first")
        return

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM bali_zoning_layers WHERE boundary IS NOT NULL"
    )
    logger.info("Backfilling sea_distance_m for %d zones...", total)

    # Batch update using PostGIS geography distance (accurate meters)
    updated = await conn.execute("""
        UPDATE bali_zoning_layers z
        SET sea_distance_m = sub.dist_m
        FROM (
            SELECT z2.id,
                   ST_Distance(
                       ST_Centroid(z2.boundary)::geography,
                       c.geom::geography
                   ) AS dist_m
            FROM bali_zoning_layers z2
            CROSS JOIN bali_coastline c
            WHERE z2.boundary IS NOT NULL
              AND c.name = 'bali_main'
        ) sub
        WHERE z.id = sub.id
    """)

    # Stats
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE sea_distance_m IS NOT NULL) AS filled,
            ROUND(AVG(sea_distance_m)::numeric, 0) AS avg_m,
            ROUND(MIN(sea_distance_m)::numeric, 0) AS min_m,
            ROUND(MAX(sea_distance_m)::numeric, 0) AS max_m,
            COUNT(*) FILTER (WHERE sea_distance_m < 500) AS near_coast,
            COUNT(*) FILTER (WHERE sea_distance_m BETWEEN 500 AND 2000) AS mid_coast,
            COUNT(*) FILTER (WHERE sea_distance_m > 2000) AS inland
        FROM bali_zoning_layers
    """)

    logger.info(
        "✅ Backfill complete: %d zones filled. "
        "AVG=%sm, MIN=%sm, MAX=%sm | Near coast(<500m)=%d, Mid(500-2km)=%d, Inland(>2km)=%d",
        stats["filled"], stats["avg_m"], stats["min_m"], stats["max_m"],
        stats["near_coast"], stats["mid_coast"], stats["inland"],
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import Bali coastline from OSM")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--skip-import", action="store_true", help="Skip coastline import, only backfill")
    parser.add_argument("--skip-backfill", action="store_true", help="Skip sea_distance backfill")
    parser.add_argument("--method", choices=["overpass", "shapefile", "auto"], default="auto")
    args = parser.parse_args()

    if not args.db_url:
        logger.error("DATABASE_URL not set. Use --db-url or set env var.")
        sys.exit(1)

    conn = await get_db_connection(args.db_url)
    logger.info("Connected to database")

    try:
        if not args.skip_import:
            lines: list[list[tuple[float, float]]] | None = None

            if args.method in ("shapefile", "auto"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    lines = try_shapefile_approach(tmpdir)

            if lines is None and args.method in ("overpass", "auto"):
                lines = fetch_coastline_overpass()

            if not lines:
                logger.error("Failed to obtain coastline data")
                sys.exit(1)

            await import_coastline(conn, lines)

        if not args.skip_backfill:
            await backfill_sea_distance(conn)

    finally:
        await conn.close()

    logger.info("🏖️ Done!")


if __name__ == "__main__":
    asyncio.run(main())
