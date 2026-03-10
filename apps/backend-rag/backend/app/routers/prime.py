"""
Nuzantara Prime — Geospatial Zoning API

Exposes PostGIS spatial queries for the Prime 3D map intelligence layer.
Enriches zone data with KBLI business opportunities for non-specialist audiences.
"""

import logging
import os
from typing import Any

import asyncpg
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime", tags=["prime"])

_ZONING_QUERY = """
    SELECT
        district_name,
        subdistrict_name,
        zoning_type,
        allowed_kbli,
        avg_price_per_are,
        risk_score
    FROM bali_zoning_layers
    WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326))
    ORDER BY risk_score DESC
    LIMIT 1
"""

# =============================================================================
# ZONE → BUSINESS OPPORTUNITIES MAPPING
# Based on GISTARU Badung zoning regulations (RDTR 2022-2042)
# Each zone lists top KBLI codes relevant for foreign investors (PMA focus)
# Format: { zone_code: [ {code, title_en, title_id, pma_open, category_en} ] }
# =============================================================================
_ZONE_KBLI_MAP: dict[str, list[dict[str, Any]]] = {
    # K-1: Perdagangan dan Jasa Skala Kota (City-scale Commerce & Services)
    "K-1": [
        {"code": "47112", "title_en": "Supermarket / Convenience Store", "title_id": "Minimarket/Supermarket", "pma_open": True, "category_en": "Retail"},
        {"code": "56101", "title_en": "Restaurant / Café", "title_id": "Restoran & Kafe", "pma_open": True, "category_en": "F&B"},
        {"code": "56301", "title_en": "Bar / Lounge", "title_id": "Bar & Lounge", "pma_open": True, "category_en": "F&B"},
        {"code": "55110", "title_en": "Hotel (5-star / Boutique)", "title_id": "Hotel Berbintang", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "68111", "title_en": "Real Estate Development", "title_id": "Pengembangan Properti", "pma_open": True, "category_en": "Property"},
        {"code": "74120", "title_en": "Design & Creative Agency", "title_id": "Desain & Kreatif", "pma_open": True, "category_en": "Creative"},
        {"code": "85499", "title_en": "Private School / Training Center", "title_id": "Sekolah & Kursus", "pma_open": True, "category_en": "Education"},
    ],
    # K-2: Perdagangan dan Jasa Skala WP (District-scale Commerce)
    "K-2": [
        {"code": "56101", "title_en": "Restaurant / Café", "title_id": "Restoran & Kafe", "pma_open": True, "category_en": "F&B"},
        {"code": "56301", "title_en": "Bar / Lounge", "title_id": "Bar & Lounge", "pma_open": True, "category_en": "F&B"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55201", "title_en": "Homestay / Guesthouse", "title_id": "Homestay & Penginapan", "pma_open": True, "category_en": "Hospitality"},
        {"code": "47112", "title_en": "Retail Shop", "title_id": "Toko Ritel", "pma_open": True, "category_en": "Retail"},
        {"code": "93199", "title_en": "Yoga / Fitness Studio", "title_id": "Studio Yoga & Fitness", "pma_open": True, "category_en": "Wellness"},
        {"code": "74901", "title_en": "Consulting Agency", "title_id": "Konsultan Bisnis", "pma_open": True, "category_en": "Services"},
    ],
    # K-3: Perdagangan dan Jasa Skala SWP (Neighborhood Commerce)
    "K-3": [
        {"code": "56101", "title_en": "Restaurant / Café", "title_id": "Restoran & Kafe", "pma_open": True, "category_en": "F&B"},
        {"code": "56102", "title_en": "Food Court / Warung", "title_id": "Warung Makan", "pma_open": True, "category_en": "F&B"},
        {"code": "55201", "title_en": "Homestay / Guesthouse", "title_id": "Homestay & Penginapan", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "93199", "title_en": "Yoga / Wellness Studio", "title_id": "Studio Yoga & Wellness", "pma_open": True, "category_en": "Wellness"},
        {"code": "96021", "title_en": "Spa / Beauty Salon", "title_id": "Spa & Salon", "pma_open": True, "category_en": "Wellness"},
        {"code": "47112", "title_en": "Specialty Shop / Boutique", "title_id": "Toko Butik", "pma_open": True, "category_en": "Retail"},
    ],
    # C-1: Campuran Intensitas Tinggi (High-intensity Mixed Use)
    "C-1": [
        {"code": "55110", "title_en": "Hotel (Boutique / Business)", "title_id": "Hotel Butik & Bisnis", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "56101", "title_en": "Restaurant / Café", "title_id": "Restoran & Kafe", "pma_open": True, "category_en": "F&B"},
        {"code": "68111", "title_en": "Real Estate / Property Development", "title_id": "Pengembangan Properti", "pma_open": True, "category_en": "Property"},
        {"code": "41017", "title_en": "Hotel Construction & Development", "title_id": "Konstruksi Hotel", "pma_open": True, "category_en": "Construction"},
        {"code": "74120", "title_en": "Design Studio / Creative Office", "title_id": "Studio Desain", "pma_open": True, "category_en": "Creative"},
        {"code": "93199", "title_en": "Yoga / Fitness / Wellness", "title_id": "Wellness & Fitness", "pma_open": True, "category_en": "Wellness"},
        {"code": "85499", "title_en": "Co-working / Learning Center", "title_id": "Co-working & Pendidikan", "pma_open": True, "category_en": "Education"},
    ],
    # C-2: Campuran Intensitas Menengah (Medium Mixed Use)
    "C-2": [
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55201", "title_en": "Homestay / Boutique Stay", "title_id": "Homestay Butik", "pma_open": True, "category_en": "Hospitality"},
        {"code": "56101", "title_en": "Restaurant / Café", "title_id": "Restoran & Kafe", "pma_open": True, "category_en": "F&B"},
        {"code": "93199", "title_en": "Yoga / Wellness Studio", "title_id": "Studio Wellness", "pma_open": True, "category_en": "Wellness"},
        {"code": "96021", "title_en": "Spa / Beauty Center", "title_id": "Spa & Kecantikan", "pma_open": True, "category_en": "Wellness"},
        {"code": "68111", "title_en": "Property / Real Estate", "title_id": "Properti", "pma_open": True, "category_en": "Property"},
    ],
    # R-2: Perumahan Kepadatan Tinggi (High-density Residential)
    "R-2": [
        {"code": "55201", "title_en": "Homestay / Guesthouse", "title_id": "Homestay", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "68111", "title_en": "Property Investment / Leasing", "title_id": "Investasi Properti", "pma_open": True, "category_en": "Property"},
        {"code": "96021", "title_en": "Small Spa / Home Salon", "title_id": "Spa Rumahan", "pma_open": True, "category_en": "Wellness"},
    ],
    # R-3: Perumahan Kepadatan Sedang (Medium Residential)
    "R-3": [
        {"code": "55201", "title_en": "Homestay / Guesthouse", "title_id": "Homestay", "pma_open": True, "category_en": "Hospitality"},
        {"code": "55203", "title_en": "Villa Rental", "title_id": "Vila Sewa", "pma_open": True, "category_en": "Hospitality"},
        {"code": "68111", "title_en": "Property Investment / Leasing", "title_id": "Investasi Properti", "pma_open": True, "category_en": "Property"},
    ],
    # R-4: Perumahan Kepadatan Rendah (Low-density Residential)
    "R-4": [
        {"code": "55203", "title_en": "Luxury Villa Development", "title_id": "Vila Mewah", "pma_open": True, "category_en": "Hospitality"},
        {"code": "68111", "title_en": "Land / Property Investment", "title_id": "Investasi Lahan", "pma_open": True, "category_en": "Property"},
    ],
    # KPI: Kawasan Peruntukan Industri (Industrial Zone)
    "KPI": [
        {"code": "10791", "title_en": "Food Processing Plant", "title_id": "Industri Makanan & Minuman", "pma_open": True, "category_en": "Industry"},
        {"code": "13101", "title_en": "Textile / Garment Factory", "title_id": "Industri Tekstil", "pma_open": True, "category_en": "Industry"},
        {"code": "32901", "title_en": "Handicraft / Artisan Manufacturing", "title_id": "Kerajinan Tangan", "pma_open": True, "category_en": "Industry"},
        {"code": "38211", "title_en": "Waste Management / Recycling", "title_id": "Pengelolaan Limbah", "pma_open": True, "category_en": "Industry"},
    ],
    # KT: Perkantoran (Office Zone)
    "KT": [
        {"code": "74901", "title_en": "Business Consulting Office", "title_id": "Kantor Konsultan", "pma_open": True, "category_en": "Services"},
        {"code": "74120", "title_en": "Design / Architecture Studio", "title_id": "Studio Desain & Arsitektur", "pma_open": True, "category_en": "Creative"},
        {"code": "62010", "title_en": "Software / IT Company", "title_id": "Perusahaan IT & Software", "pma_open": True, "category_en": "Technology"},
        {"code": "69200", "title_en": "Accounting / Financial Services", "title_id": "Akuntansi & Keuangan", "pma_open": True, "category_en": "Finance"},
    ],
    # SPU-1: Sarana Pelayanan Umum Skala Kota (Public Facilities - City)
    "SPU-1": [
        {"code": "85499", "title_en": "International School / University", "title_id": "Sekolah Internasional", "pma_open": True, "category_en": "Education"},
        {"code": "86101", "title_en": "Private Hospital / Clinic", "title_id": "Rumah Sakit & Klinik", "pma_open": True, "category_en": "Healthcare"},
    ],
}

# Zones where business is NOT allowed (protected/infrastructure)
_RESTRICTED_ZONES = {"HL", "PS", "CB", "LS", "EM", "BA", "BJ", "HK", "RTH-2", "RTH-3", "RTH-4", "KS-4", "IK-1", "P-1", "P-2", "P-3", "P-4", "PL-3", "PL-4", "PTL"}

# Human-readable zone descriptions for non-specialists
_ZONE_DESCRIPTIONS: dict[str, str] = {
    "K-1": "City-scale commercial hub — ideal for large retail, hotels, offices",
    "K-2": "District commercial area — restaurants, shops, services",
    "K-3": "Neighborhood commercial strip — cafés, small shops, studios",
    "C-1": "High-density mixed-use — hotels, residences, offices combined",
    "C-2": "Medium mixed-use — villas, cafés, wellness businesses",
    "R-2": "High-density residential — limited commercial (homestay, small spa)",
    "R-3": "Medium residential — villa rentals, property investment",
    "R-4": "Low-density residential — luxury villas, land investment",
    "KPI": "Industrial zone — manufacturing, food processing, craft",
    "KT": "Office zone — consulting, tech, finance, professional services",
    "SPU-1": "Public facilities — schools, hospitals, civic uses",
    "HL": "Protected forest — no commercial activity permitted",
    "PS": "Riparian buffer zone — no commercial activity permitted",
    "CB": "Cultural heritage zone — strictly regulated",
    "LS": "Spiritual & local wisdom zone — no commercial activity",
    "EM": "Mangrove ecosystem — protected, no development",
    "BA": "Water body — no development permitted",
    "BJ": "Road infrastructure — no commercial activity",
    "RTH-2": "City park — public green space",
    "P-1": "Agricultural land — crop farming only",
}


def _enrich_zone(zone_code: str) -> dict[str, Any]:
    """Return business opportunities and description for a given zone code."""
    businesses = _ZONE_KBLI_MAP.get(zone_code, [])
    description = _ZONE_DESCRIPTIONS.get(zone_code, "Specialized zone")
    is_restricted = zone_code in _RESTRICTED_ZONES
    return {
        "businesses": businesses,
        "zone_description_en": description,
        "is_restricted": is_restricted,
        "business_count": len(businesses),
    }


@router.get("/zoning")
async def get_zoning(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> dict[str, Any]:
    """
    Return GISTARU zoning data + business opportunities for a given lat/lng.
    Uses PostGIS ST_Contains with a GIST index — typically < 10ms.
    """
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        conn = await asyncpg.connect(db_url)
        try:
            row = await conn.fetchrow(_ZONING_QUERY, lng, lat)
        finally:
            await conn.close()

        if not row:
            logger.info(f"⚠️ [Prime] No zoning match for {lat},{lng}")
            return {
                "status": "outside_coverage",
                "message": "Coordinates outside mapped GISTARU coverage (Kabupaten Badung only).",
                "lat": lat,
                "lng": lng,
            }

        zone_type: str = row["zoning_type"]
        zone_code = zone_type.split(":")[0].strip()
        zone_name = zone_type.split(":", 1)[1].strip() if ":" in zone_type else zone_type

        enrichment = _enrich_zone(zone_code)

        logger.info(f"✅ [Prime] Zoning hit: {zone_type} @ {lat},{lng} ({enrichment['business_count']} businesses)")
        return {
            "status": "found",
            "lat": lat,
            "lng": lng,
            "district": row["district_name"],
            "subdistrict": row["subdistrict_name"],
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "zone_description_en": enrichment["zone_description_en"],
            "is_restricted": enrichment["is_restricted"],
            "businesses": enrichment["businesses"],
            "allowed_kbli": row["allowed_kbli"],
            "avg_price_per_are": float(row["avg_price_per_are"] or 0),
            "risk_score": float(row["risk_score"] or 0),
            "source": "GISTARU/Badung DPUPR",
        }

    except Exception as e:
        logger.error(f"❌ [Prime] Zoning query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "Zoning lookup failed.",
            "lat": lat,
            "lng": lng,
        }
