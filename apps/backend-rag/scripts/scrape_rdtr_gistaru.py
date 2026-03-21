#!/usr/bin/env python3
"""
RDTR Scraper from gistaru.atrbpn.go.id
Downloads official zoning polygons for Tabanan and Denpasar and imports into DB.

Usage:
    source .venv/bin/activate
    PYTHONPATH=. python scripts/scrape_rdtr_gistaru.py [--dry-run] [--district tabanan|denpasar|all]
"""

import argparse
import asyncio
import json
import logging
import urllib.parse

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROXY = "https://gistaru.atrbpn.go.id/proxy_mobile/run.ashx"
BASE = "https://gistaru.atrbpn.go.id/arcgis/rest/services/060_RDTR_PROVINSI_BALI"
PAGE_SIZE = 500

# Official RDTR layers per district
LAYERS = {
    "bangli": [
        {
            "service": "_RDTR_51C3_WP_GEOPARK_BATUR",
            "district": "Bangli",
            "subdistrict": "Kintamani (Geopark Batur)",
            "perda": "2023",
        }
    ],
    "buleleng": [
        {
            "service": "_RDTR__51A2_KAWASAN_PERKOTAAN_SINGARAJA_2023",
            "district": "Buleleng",
            "subdistrict": "Singaraja",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C9_KAWASAN_PERKOTAAN_GEROKGAK",
            "district": "Buleleng",
            "subdistrict": "Gerokgak",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51B8_KAWASAN_TERPADU_BATUAMPAR",
            "district": "Buleleng",
            "subdistrict": "Batuampar",
            "perda": "2023",
        },
    ],
    "karangasem": [
        {
            "service": "_RDTR_51B5_KAWASAN_PERKOTAAN_AMLAPURA",
            "district": "Karangasem",
            "subdistrict": "Amlapura",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C5_WILAYAH_PERENCANAAN_KARANGASEM",
            "district": "Karangasem",
            "subdistrict": "WP Karangasem",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D4_KECAMATAN_SIDEMEN",
            "district": "Karangasem",
            "subdistrict": "Sidemen",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D5_WP_KECAMATAN_ABANG",
            "district": "Karangasem",
            "subdistrict": "Abang",
            "perda": "2023",
        },
    ],
    "jembrana": [
        {
            "service": "_RDTR_51A7_KAWASAN_PERKOTAAN_NEGARA",
            "district": "Jembrana",
            "subdistrict": "Negara",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C4_KAWASAN_PERKOTAAN_MELAYA",
            "district": "Jembrana",
            "subdistrict": "Melaya",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D2_KAWASAN_PERKOTAAN_PEKUTATAN",
            "district": "Jembrana",
            "subdistrict": "Pekutatan",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D3_KAWASAN_PERKOTAAN_PENGAMBENGAN",
            "district": "Jembrana",
            "subdistrict": "Pengambengan",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D7_KAWASAN_EFEKTIF_PARIWISATA_PERANCAK",
            "district": "Jembrana",
            "subdistrict": "Perancak",
            "perda": "2023",
        },
    ],
    "badung": [
        {
            "service": "_RDTR_51A1_KECAMATAN_KUTA_SELATAN_2023",
            "district": "Badung",
            "subdistrict": "Kuta Selatan",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51A3_KECAMATAN_KUTA_2023",
            "district": "Badung",
            "subdistrict": "Kuta",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51A4_KECAMATAN_KUTA_UTARA",
            "district": "Badung",
            "subdistrict": "Kuta Utara",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51A6_WILAYAH_PERENCANAAN_MENGWI_2023",
            "district": "Badung",
            "subdistrict": "Mengwi",
            "perda": "2023",
        },
    ],
    "gianyar": [
        {
            "service": "_RDTR_51B1_KECAMATAN_UBUD",
            "district": "Gianyar",
            "subdistrict": "Ubud",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51B6_KECAMATAN_PAYANGAN",
            "district": "Gianyar",
            "subdistrict": "Payangan",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51B7_KECAMATAN_SUKAWATI",
            "district": "Gianyar",
            "subdistrict": "Sukawati",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C2_KECAMATAN_TEGALLALANG",
            "district": "Gianyar",
            "subdistrict": "Tegallalang",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C7_KECAMATAN_GIANYAR",
            "district": "Gianyar",
            "subdistrict": "Gianyar",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51C8_KECAMATAN_BLAHBATUH",
            "district": "Gianyar",
            "subdistrict": "Blahbatuh",
            "perda": "2023",
        },
        {
            "service": "_RDTR_51D1_KECAMATAN_TAMPAKSIRING",
            "district": "Gianyar",
            "subdistrict": "Tampaksiring",
            "perda": "2023",
        },
    ],
    "tabanan": [
        {
            "service": "_RDTR_51B9_KAWASAN_PERKOTAAN_TABANAN",
            "district": "Tabanan",
            "subdistrict": "Kawasan Perkotaan Tabanan",
            "perda": "Perbup No. 101/2023",
        },
        {
            "service": "_RDTR_51C6_KECAMATAN_SELEMADEG_BARAT",
            "district": "Tabanan",
            "subdistrict": "Selemadeg Barat",
            "perda": "Perbup No. 20/2024",
        },
        {
            "service": "_RDTR_51D6_KAWASAN_TANAH_LOT_DSK",
            "district": "Tabanan",
            "subdistrict": "Kawasan Tanah Lot",
            "perda": "In process",
        },
    ],
    "denpasar": [
        {
            "service": "_RDTR_51A9_WP_BARAT",
            "district": "Denpasar",
            "subdistrict": "Denpasar Barat",
            "perda": "Perwal No. 59/2022",
        },
        {
            "service": "_RDTR_51A8_WP_TENGAH",
            "district": "Denpasar",
            "subdistrict": "Denpasar Tengah",
            "perda": "Perwal No. 58/2022",
        },
        {
            "service": "_RDTR_51B2_WP_SELATAN",
            "district": "Denpasar",
            "subdistrict": "Denpasar Selatan",
            "perda": "Perwal No. 8/2023",
        },
        {
            "service": "_RDTR_51B3_WP_TIMUR",
            "district": "Denpasar",
            "subdistrict": "Denpasar Timur",
            "perda": "Perwal No. 7/2023",
        },
        {
            "service": "_RDTR_51A5_WILAYAH_PERENCANAAN_UTARA",
            "district": "Denpasar",
            "subdistrict": "Denpasar Utara",
            "perda": "Perwal No. 1/2022",
        },
    ],
}

# Map RDTR NAMZON → zone_type codes matching Badung convention
ZONE_CODE_MAP: dict[str, str] = {
    # Residential
    "Zona Perumahan": "R",
    "Perumahan Kepadatan Tinggi": "R-2",
    "Perumahan Kepadatan Sedang": "R-3",
    "Perumahan Kepadatan Rendah": "R-4",
    # Commercial
    "Zona Perdagangan dan Jasa": "K",
    "Perdagangan dan Jasa Skala Kota": "K-1",
    "Perdagangan dan Jasa Skala WP": "K-2",
    "Perdagangan dan Jasa Skala SWP": "K-3",
    # Tourism
    "Zona Pariwisata": "W",
    "Pariwisata": "W",
    # Industry
    "Zona Industri": "I",
    # Green/Open space
    "Ruang Terbuka Hijau": "RTH",
    "Taman Kota": "RTH-2",
    "Taman RW": "RTH-5",
    "Pemakaman": "RTH-7",
    "Jalur Hijau": "RTH-8",
    # Agriculture
    "Zona Tanaman Pangan": "P-1",
    "Tanaman Pangan": "P-1",
    "Zona Hortikultura": "P-2",
    "Zona Perkebunan": "P-3",
    # Public services
    "Sarana Pelayanan Umum": "SPU",
    "SPU Skala Kota": "SPU-1",
    "SPU Skala Kecamatan": "SPU-2",
    "SPU Skala Kelurahan": "SPU-3",
    "SPU Skala RW": "SPU-4",
    # Office
    "Zona Perkantoran": "KT",
    # Protected
    "Zona Perlindungan Setempat": "PS",
    "Perlindungan Setempat": "PS",
    # Water body
    "Badan Air": "BA",
    # Road
    "Badan Jalan": "BJ",
    # Other
    "Zona Campuran": "C",
}

ZONE_COLORS: dict[str, str] = {
    "K-1": "#E8472A",
    "K-2": "#E8472A",
    "K-3": "#E8472A",
    "K": "#E8472A",
    "W": "#D4845A",
    "R": "#93C5FD",
    "R-2": "#60A5FA",
    "R-3": "#93C5FD",
    "R-4": "#BFDBFE",
    "P-1": "#86EFAC",
    "P-2": "#4ADE80",
    "P-3": "#22C55E",
    "RTH": "#166534",
    "RTH-2": "#15803D",
    "RTH-5": "#16A34A",
    "RTH-7": "#14532D",
    "RTH-8": "#166534",
    "SPU": "#A78BFA",
    "SPU-1": "#8B5CF6",
    "SPU-2": "#A78BFA",
    "SPU-3": "#C4B5FD",
    "SPU-4": "#DDD6FE",
    "KT": "#FCD34D",
    "PS": "#94A3B8",
    "BA": "#7DD3FC",
    "BJ": "#6B7280",
    "C": "#F9A8D4",
}


def proxy_url(service: str, params: dict) -> str:
    inner = f"{BASE}/{service}/MapServer/0/query?" + urllib.parse.urlencode(params)
    return PROXY + "?" + urllib.parse.quote(inner, safe="")


def normalize_zone(props: dict) -> str:
    """Extract best zone_type code from RDTR feature properties."""
    # Try KODSZN (sub-zone code) first — most specific
    kodszn = (props.get("KODSZN") or "").strip()
    if kodszn:
        return kodszn

    # Try KODZON (zone code)
    kodzon = (props.get("KODZON") or "").strip()
    if kodzon:
        return kodzon

    # Map from NAMZON / NAMSZN text
    for field in ("NAMSZN", "NAMZON"):
        name = (props.get(field) or "").strip()
        if name:
            for key, code in ZONE_CODE_MAP.items():
                if key.lower() in name.lower():
                    return code
            return name  # fallback: raw name

    return "Unknown"


async def fetch_page(client: httpx.AsyncClient, service: str, offset: int) -> dict:
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson",
        "resultRecordCount": PAGE_SIZE,
        "resultOffset": offset,
    }
    url = proxy_url(service, params)
    r = await client.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


async def get_count(client: httpx.AsyncClient, service: str) -> int:
    params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    url = proxy_url(service, params)
    r = await client.get(url, timeout=30)
    r.raise_for_status()
    return r.json().get("count", 0)


async def scrape_layer(layer: dict, dry_run: bool, db_pool) -> int:
    service = layer["service"]
    district = layer["district"]
    subdistrict = layer["subdistrict"]

    logger.info(f"Scraping {district}/{subdistrict} ({service})")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        total = await get_count(client, service)
        logger.info(f"  Total features: {total}")

        if total == 0:
            logger.warning("  No features found, skipping")
            return 0

        all_features = []
        for offset in range(0, total, PAGE_SIZE):
            logger.info(f"  Fetching offset {offset}/{total}...")
            data = await fetch_page(client, service, offset)
            features = data.get("features", [])
            if not features:
                break
            all_features.extend(features)
            await asyncio.sleep(0.3)  # rate limit

    logger.info(f"  Fetched {len(all_features)} features")

    if dry_run:
        # Show sample
        if all_features:
            f = all_features[0]
            props = f.get("properties", {})
            logger.info(f"  DRY RUN - sample props: {dict(list(props.items())[:6])}")
            logger.info(f"  DRY RUN - zone_type would be: {normalize_zone(props)}")
        return len(all_features)

    # Insert into DB
    inserted = 0
    async with db_pool.acquire() as conn:
        # Delete existing rows for this subdistrict to allow re-runs
        deleted = await conn.fetchval(
            "SELECT COUNT(*) FROM bali_zoning_layers WHERE district_name=$1 AND subdistrict_name=$2",
            district,
            subdistrict,
        )
        await conn.execute(
            "DELETE FROM bali_zoning_layers WHERE district_name=$1 AND subdistrict_name=$2",
            district,
            subdistrict,
        )
        logger.info(f"  Deleted {deleted or 0} existing rows for {subdistrict}")

        for feat in all_features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue

            zone_type = normalize_zone(props)
            zone_full = props.get("NAMSZN") or props.get("NAMZON") or zone_type

            # Build full zone type string like Badung: "K-1: Perdagangan..."
            zoning_type = f"{zone_type}: {zone_full}" if zone_type != zone_full else zone_type

            geom_json = json.dumps(geom)
            try:
                await conn.execute(
                    """
                    INSERT INTO bali_zoning_layers
                        (district_name, subdistrict_name, zoning_type, boundary)
                    VALUES ($1, $2, $3, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326))
                    """,
                    district,
                    subdistrict,
                    zoning_type,
                    geom_json,
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"  Insert error: {e}")

    logger.info(f"  ✅ Inserted {inserted}/{len(all_features)} rows for {subdistrict}")
    return inserted


async def main(districts: list[str], dry_run: bool):
    db_url = "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"

    if dry_run:
        logger.info("DRY RUN mode — no DB writes")
        db_pool = None
    else:
        db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5)

    total_inserted = 0
    for dist in districts:
        for layer in LAYERS.get(dist, []):
            n = await scrape_layer(layer, dry_run, db_pool)
            total_inserted += n

    if db_pool:
        await db_pool.close()

    logger.info(f"\n🎉 Done. Total: {total_inserted} rows {'(dry run)' if dry_run else 'inserted'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't write to DB")
    parser.add_argument(
        "--district",
        default="all",
        choices=[
            "badung",
            "gianyar",
            "tabanan",
            "denpasar",
            "bangli",
            "buleleng",
            "karangasem",
            "jembrana",
            "all",
        ],
        help="Which district to scrape",
    )
    args = parser.parse_args()

    districts = list(LAYERS.keys()) if args.district == "all" else [args.district]
    asyncio.run(main(districts, args.dry_run))
