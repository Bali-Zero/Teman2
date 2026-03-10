"""
Nuzantara Prime — Geospatial Zoning API

Exposes PostGIS spatial queries for the Prime 3D map intelligence layer.
Primary source: BATARA (batara.badungkab.go.id) — official Badung RDTR data.
Fallback: PostGIS local DB (GISTARU import).
"""

import logging
import os
from typing import Any

import asyncpg
import httpx
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

# BATARA official API — Badung DPUPR spatial planning service
_BATARA_API_URL = "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point"

# =============================================================================
# BUSINESS CATEGORY CLASSIFICATION
# Maps activity keywords to investor-friendly category labels
# =============================================================================

# Keywords to skip — generic infrastructure/residential items, not investor-relevant
_SKIP_KEYWORDS = {
    "local resident", "employee", "official residence", "boarding house",
    "single house", "cluster house", "coupled house", "dormitory",
    "septic tank", "wastewater", "irrigation", "cleanwater", "trash",
    "toilet", "parking", "pedestrian", "road", "disability",
}

# Category mapping by keyword presence in activity name
_ACTIVITY_CATEGORIES: list[tuple[list[str], str]] = [
    (["hotel", "resort", "boutique hotel", "villa", "guesthouse", "penginapan", "lodging"], "Hospitality"),
    (["restaurant", "café", "cafe", "food", "beverage", "bar", "bakery", "catering"], "F&B"),
    (["spa", "salon", "wellness", "yoga", "fitness", "gym", "massage"], "Wellness"),
    (["retail", "shop", "store", "boutique", "trade", "perdagangan"], "Retail"),
    (["office", "consulting", "consultant", "agency", "professional service"], "Services"),
    (["real estate", "property", "land", "properti", "development"], "Property"),
    (["software", "it ", "technology", "digital", "programming"], "Technology"),
    (["school", "education", "training", "university", "course"], "Education"),
    (["hospital", "clinic", "healthcare", "medical", "health service"], "Healthcare"),
    (["manufacturing", "factory", "industrial", "processing"], "Industry"),
    (["creative", "design", "art", "studio", "media", "photography"], "Creative"),
]


def _classify_activity(name: str) -> str:
    """Map an activity name to an investor-friendly category."""
    lower = name.lower()
    for keywords, category in _ACTIVITY_CATEGORIES:
        if any(kw in lower for kw in keywords):
            return category
    return "Other"


def _is_investor_relevant(name: str) -> bool:
    """Filter out generic non-investor activities."""
    lower = name.lower()
    return not any(kw in lower for kw in _SKIP_KEYWORDS)


def _rgb_string_to_hex(rgb_str: str) -> str:
    """Convert '250 211 140' → '#fad38c'."""
    try:
        parts = [int(x) for x in rgb_str.replace(",", " ").split()]
        if len(parts) == 3:
            return "#{:02x}{:02x}{:02x}".format(*parts)
    except (ValueError, AttributeError):
        pass
    return "#a0aec0"  # neutral gray fallback


# =============================================================================
# FALLBACK: Zone labels for PostGIS-only path (no BATARA)
# =============================================================================
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

_RESTRICTED_ZONES = {
    "HL", "PS", "CB", "LS", "EM", "BA", "BJ", "HK",
    "RTH-2", "RTH-3", "RTH-4", "KS-4", "IK-1",
    "P-1", "P-2", "P-3", "P-4", "PL-3", "PL-4", "PTL",
}


async def _query_batara(lat: float, lng: float) -> dict[str, Any] | None:
    """
    Query the official BATARA API (Badung DPUPR) for RDTR zoning data.
    Returns enriched zone dict or None if unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                _BATARA_API_URL,
                json={"x": str(lng), "y": str(lat), "informationType": "RDTR"},
                headers={"Accept": "application/json", "Accept-Language": "en"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("status") != 200:
                return None

            geom_list = data.get("data", {}).get("territorials", {}).get("geom", [])
            if not geom_list:
                return None

            geom = geom_list[0]
            zone = geom.get("zone", {})
            if not zone:
                return None

            zone_code: str = zone.get("code", "")
            zone_name: str = zone.get("name", "")
            zone_color_rgb: str = zone.get("color", "")
            zone_definition: str = zone.get("definition", "")
            activities: list[dict[str, Any]] = zone.get("activities", [])

            # Build investor-relevant "allowed" businesses from BATARA activities
            businesses: list[dict[str, Any]] = []
            for act in activities:
                pivot = act.get("pivot", {})
                is_allowed = pivot.get("i", False)  # i = Izin (allowed)
                if not is_allowed:
                    continue
                name = act.get("name", "")
                if not name or not _is_investor_relevant(name):
                    continue
                category = _classify_activity(name)
                businesses.append({
                    "title_en": name,
                    "category_en": category,
                    "pma_open": True,  # shown as default; refined per KBLI in future
                })

            # Limit to top 12 most relevant for UI display
            businesses = businesses[:12]

            hex_color = _rgb_string_to_hex(zone_color_rgb) if zone_color_rgb else None
            is_restricted = zone_code in _RESTRICTED_ZONES

            # Overlay data
            overlays: dict[str, str] = {}
            if geom.get("kkop_1") and geom["kkop_1"] != "Tidak":
                overlays["kkop"] = geom["kkop_1"]
            if geom.get("lp2b_2") == "Ya":
                overlays["lp2b"] = "Protected farmland (LP2B)"
            if geom.get("krb_03") and geom["krb_03"] != "Tidak Ada":
                overlays["tsunami"] = geom["krb_03"]
            if geom.get("cagbud") and geom["cagbud"] != "Tidak Ada":
                overlays["heritage"] = geom["cagbud"]
            if geom.get("teb_05") and geom["teb_05"] != "Tidak Ada":
                overlays["evac_center"] = geom["teb_05"]

            label_info = _ZONE_LABELS.get(zone_code, {"label_en": zone_name, "desc_en": zone_definition[:120] if zone_definition else ""})

            logger.info(f"✅ [Prime/BATARA] {zone_code} '{zone_name}' @ {lat},{lng} — {len(businesses)} businesses")
            return {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"] or zone_definition[:120],
                "zone_color_hex": hex_color,
                "is_restricted": is_restricted,
                "businesses": businesses,
                "business_count": len(businesses),
                "overlays": overlays,
                "source": "BATARA/Badung DPUPR (official)",
            }

    except Exception as exc:
        logger.warning(f"⚠️ [Prime] BATARA query failed ({lat},{lng}): {exc}")
        return None


@router.get("/zoning")
async def get_zoning(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> dict[str, Any]:
    """
    Return official RDTR zoning data + business opportunities for a given lat/lng.
    Primary: BATARA API (live Badung DPUPR data).
    Fallback: PostGIS local DB (GISTARU import, Badung only).
    """
    # --- PRIMARY: BATARA live API ---
    batara = await _query_batara(lat, lng)
    if batara:
        return {
            "status": "found",
            "lat": lat,
            "lng": lng,
            **batara,
        }

    # --- FALLBACK: PostGIS local DB ---
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
                "message": "Coordinates outside mapped Badung RDTR coverage.",
                "lat": lat,
                "lng": lng,
            }

        zone_type: str = row["zoning_type"]
        zone_code = zone_type.split(":")[0].strip()
        zone_name = zone_type.split(":", 1)[1].strip() if ":" in zone_type else zone_type

        label_info = _ZONE_LABELS.get(zone_code, {"label_en": zone_name, "desc_en": "Contact local authorities for details"})
        is_restricted = zone_code in _RESTRICTED_ZONES

        logger.info(f"✅ [Prime/PostGIS] Zoning hit: {zone_type} @ {lat},{lng}")
        return {
            "status": "found",
            "lat": lat,
            "lng": lng,
            "district": row["district_name"],
            "subdistrict": row["subdistrict_name"],
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_label_en": label_info["label_en"],
            "zone_description_en": label_info["desc_en"],
            "zone_color_hex": None,
            "zone_type": zone_type,
            "is_restricted": is_restricted,
            "businesses": [],
            "business_count": 0,
            "overlays": {},
            "avg_price_per_are": float(row["avg_price_per_are"] or 0),
            "risk_score": float(row["risk_score"] or 0),
            "source": "PostGIS/GISTARU (local cache)",
        }

    except Exception as e:
        logger.error(f"❌ [Prime] Zoning query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": "Zoning lookup failed.",
            "lat": lat,
            "lng": lng,
        }
