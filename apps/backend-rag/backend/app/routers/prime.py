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

# Human-readable zone labels and descriptions for non-specialists
# label_en: short plain-English name shown next to the zone code in the UI
_ZONE_LABELS: dict[str, dict[str, str]] = {
    "K-1": {"label_en": "City Commercial Zone",        "desc_en": "Large-scale commerce — shopping centers, hotels, offices"},
    "K-2": {"label_en": "District Commercial Zone",    "desc_en": "Mid-scale commerce — restaurants, retail, professional services"},
    "K-3": {"label_en": "Neighborhood Commercial Zone","desc_en": "Small-scale commerce — cafés, boutiques, studios, wellness"},
    "C-1": {"label_en": "High-Density Mixed-Use Zone", "desc_en": "Hotels + residences + offices in the same area"},
    "C-2": {"label_en": "Medium Mixed-Use Zone",       "desc_en": "Villas, cafés, and wellness businesses side by side"},
    "W":   {"label_en": "Tourism Zone",                "desc_en": "Hotels, resorts, restaurants, entertainment — tourism focus"},
    "W-1": {"label_en": "Tourism Zone (Type 1)",       "desc_en": "Primary tourism area — resorts and large hotels"},
    "W-2": {"label_en": "Tourism Zone (Type 2)",       "desc_en": "Secondary tourism area — boutique stays, restaurants"},
    "R-2": {"label_en": "High-Density Residential",    "desc_en": "Dense housing — limited commercial activity permitted"},
    "R-3": {"label_en": "Medium-Density Residential",  "desc_en": "Suburban housing — villa rentals and homestays possible"},
    "R-4": {"label_en": "Low-Density Residential",     "desc_en": "Spacious housing — luxury villas and land investment"},
    "KPI": {"label_en": "Industrial Zone",             "desc_en": "Manufacturing, food processing, craft production"},
    "KT":  {"label_en": "Office / Business Park Zone", "desc_en": "Professional offices — consulting, tech, finance"},
    "SPU-1": {"label_en": "City Public Facility Zone", "desc_en": "Major public services — hospitals, universities"},
    "SPU-2": {"label_en": "District Public Facility",  "desc_en": "District services — clinics, schools"},
    "SPU-3": {"label_en": "Village Public Facility",   "desc_en": "Local services — community centers, worship"},
    "SPU-4": {"label_en": "Neighborhood Facility",     "desc_en": "Smallest-scale public facilities"},
    "P-1": {"label_en": "Crop Farming Zone",           "desc_en": "Protected agricultural land — no development permitted"},
    "P-2": {"label_en": "Horticulture Zone",           "desc_en": "Fruit & vegetable farming — no development"},
    "P-3": {"label_en": "Plantation Zone",             "desc_en": "Estate crops — no development"},
    "P-4": {"label_en": "Livestock Zone",              "desc_en": "Animal husbandry — no development"},
    "HL":  {"label_en": "Protected Forest",            "desc_en": "⛔ Conservation forest — strictly no development"},
    "PS":  {"label_en": "Riparian Buffer Zone",        "desc_en": "⛔ Riverbank protection — no development"},
    "SS":  {"label_en": "River Buffer Zone",           "desc_en": "⛔ Streamside protection — no development"},
    "SP":  {"label_en": "Coastal Buffer Zone",         "desc_en": "⛔ Beachfront protection — no development"},
    "CB":  {"label_en": "Cultural Heritage Zone",      "desc_en": "⛔ Historical & cultural protection — strictly regulated"},
    "LS":  {"label_en": "Spiritual & Sacred Zone",     "desc_en": "⛔ Balinese sacred sites — no commercial activity"},
    "EM":  {"label_en": "Mangrove Ecosystem",          "desc_en": "⛔ Mangrove forest — protected, no development"},
    "TWA": {"label_en": "Nature Tourism Reserve",      "desc_en": "⛔ Wildlife area — restricted access"},
    "THR": {"label_en": "City Forest Park",            "desc_en": "⛔ Protected urban forest"},
    "KS-4":{"label_en": "Forest Reserve Park",        "desc_en": "⛔ Protected nature reserve"},
    "BA":  {"label_en": "Water Body",                  "desc_en": "⛔ River, lake, or sea — no development"},
    "BJ":  {"label_en": "Road Infrastructure",         "desc_en": "⛔ Public road right-of-way"},
    "TR":  {"label_en": "Transportation Zone",         "desc_en": "Airports, ports, terminals"},
    "RTH-2": {"label_en": "City Park",                 "desc_en": "Public green space — parks and gardens"},
    "RTH-3": {"label_en": "District Park",             "desc_en": "Neighborhood green space"},
    "RTH-4": {"label_en": "Village Park",              "desc_en": "Local green space"},
    "RTH-5": {"label_en": "Block Park",                "desc_en": "Small local green space"},
    "RTH-7": {"label_en": "Cemetery",                  "desc_en": "Public cemetery"},
    "RTH-8": {"label_en": "Green Corridor",            "desc_en": "Roadside or canal green strip"},
    "RTNH": {"label_en": "Non-Green Open Space",       "desc_en": "Plazas, parking, paved open areas"},
    "HK":  {"label_en": "Defense & Security Zone",    "desc_en": "Military / government security area"},
    "PL-3":{"label_en": "Water Treatment Facility",   "desc_en": "Public infrastructure — no development"},
    "PL-4":{"label_en": "Wastewater Facility",        "desc_en": "Public infrastructure — no development"},
    "PTL": {"label_en": "Power Generation Zone",      "desc_en": "Energy infrastructure — no development"},
    "IK-1":{"label_en": "Capture Fishery Zone",       "desc_en": "Coastal fishing zone — no land development"},
}

# Backward-compat alias
_ZONE_DESCRIPTIONS: dict[str, str] = {k: v["desc_en"] for k, v in _ZONE_LABELS.items()}


def _enrich_zone(zone_code: str) -> dict[str, Any]:
    """Return business opportunities, label, and description for a given zone code."""
    businesses = _ZONE_KBLI_MAP.get(zone_code, [])
    label_info = _ZONE_LABELS.get(zone_code, {"label_en": "Specialized Zone", "desc_en": "Contact local authorities for details"})
    is_restricted = zone_code in _RESTRICTED_ZONES
    return {
        "businesses": businesses,
        "zone_label_en": label_info["label_en"],
        "zone_description_en": label_info["desc_en"],
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
            "zone_label_en": enrichment["zone_label_en"],
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
