"""
Nuzantara Prime — Geospatial Zoning API

Exposes PostGIS spatial queries for the Prime 3D map intelligence layer.
Primary source: BATARA (batara.badungkab.go.id) — official Badung RDTR data.
Fallback: PostGIS local DB (GISTARU import).
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from fastapi import APIRouter, Query

from backend.core.embeddings import create_embeddings_generator
from backend.services.rag.hybrid_search import HybridSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime", tags=["prime"])

# Patterns for extracting zone codes from text
_ZONE_CODE_PATTERN = re.compile(r"\b([RTHWPKSB]-\d+)\b", re.IGNORECASE)


@router.get("/search-kbli")
async def search_kbli(q: str = Query(..., min_length=2)) -> dict[str, Any]:
    """
    Search for allowed zones for a business type using RAG logic.
    Returns a list of matching zone codes.
    """
    try:
        search_service = HybridSearchService()

        # Search legal documents for business activity + zone mapping
        results = await search_service.search_hybrid(
            query=f"zonasi peruntukan bisnis {q}",
            collection="legal_unified_hybrid_hybrid",
            limit=5,
            alpha=0.5,
        )

        matching_zones = set()
        for res in results:
            text = res.get("text", "")
            matches = _ZONE_CODE_PATTERN.findall(text)
            for m in matches:
                matching_zones.add(m.upper())

        # Fallback: if searching for "Hotel" or "Villa", add common tourism zones
        q_lower = q.lower()
        if any(x in q_lower for x in ["hotel", "villa", "pariwisata", "resort"]):
            matching_zones.add("W-1")
            matching_zones.add("W-2")
        elif any(
            x in q_lower
            for x in ["gym", "fitness", "toko", "shop", "commercial", "restoran", "restaurant"]
        ):
            matching_zones.add("K-1")
            matching_zones.add("K-2")
            matching_zones.add("K-3")

        logger.info(f"🔍 [Prime/KBLI] Search for '{q}' returned zones: {list(matching_zones)}")
        return {"query": q, "matching_zone_codes": list(matching_zones), "status": "success"}
    except Exception as e:
        logger.error(f"❌ [Prime/KBLI] Search failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "matching_zone_codes": []}


# =============================================================================
# BUILDING CODES — loaded once at import time from JSON
# =============================================================================
_BUILDING_CODES_PATH = (
    Path(__file__).parent.parent.parent / "data" / "master_building_codes_complete.json"
)
try:
    with open(_BUILDING_CODES_PATH, encoding="utf-8") as _f:
        _BUILDING_CODES: dict[str, dict[str, str]] = json.load(_f)
    logger.info(f"✅ [Prime] Loaded building codes for {len(_BUILDING_CODES)} zone types")
except Exception as _e:
    _BUILDING_CODES = {}
    logger.warning(f"⚠️ [Prime] Could not load building codes: {_e}")


def _calculate_building_yield(zone_code: str) -> dict[str, Any] | None:
    """Return building limit summary for a zone code (KDB, KLB, KDH, TB, GSB)."""
    data = _BUILDING_CODES.get(zone_code)
    if not data:
        return None

    # KLB uses Indonesian comma decimal ("1,8") — normalise to dot
    def _parse_pct(val: str) -> float:
        return float(val.replace(",", ".").replace("%", "").strip())

    try:
        return {
            "zone_name_id": data.get("name", ""),
            "kdb_pct": _parse_pct(data.get("KDB", "0")),  # max building coverage %
            "klb_ratio": _parse_pct(data.get("KLB", "0")),  # floor area ratio
            "kdh_pct": _parse_pct(data.get("KDH", "0")),  # min green area %
            "ktb_pct": _parse_pct(data.get("KTB", "0")),  # basement coverage %
            "height_limit": data.get("TB", "—"),  # max height (string, e.g. "15 Meter")
            "setback": data.get("GSB", "—"),  # building setback
            "notes": data.get("note", ""),
        }
    except Exception as exc:
        logger.warning(f"⚠️ [Prime] Building codes parse error for {zone_code}: {exc}")
        return None


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

# Separate lightweight query used when BATARA handles zoning but we still want price
_PRICE_QUERY = """
    SELECT avg_price_per_are
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

# Activities to skip — non investor-relevant (residential, infrastructure, local-only)
# Uses word-boundary matching: "road" won't match "abroad"
_SKIP_PATTERNS = [
    "local resident",
    "employee",
    "official residence",
    "boarding house",
    "single house",
    "cluster house",
    "coupled house",
    "dormitory",
    "townhouse",
    "septic tank",
    "wastewater",
    "irrigation",
    "cleanwater",
    "trash can",
    "toilet facility",
    "parking area",
    "pedestrian lane",
    "disability access",
    "loading unloading",
    "road network",
    "road complete",
    "bike lane",
    "public road access",
    "pavement area",
    "lot area",
    "building height",
    "minimum gsb",
    "minimum kdh",
    "maximum kdb",
    "maximum klb",
    "maximum ktb",
    "road dimension",
    "road equipment",
    "trash",
    "zone_requirement",
    "car trading",
    "car spare parts",
    "motorcycle trade",
    "motorcycle maintenance",
    "wholesale trade of fishery",
    "wholesale of motor vehicle",
    "wholesale trade of food",
    "wholesale of household",
    "wholesale of machinery",
    "wholesale of building material",
    "wholesale of agricultural",
    "wholesale of fuel",
    "village government",
    "government service",
    "public service office",
    "fire station",
    "police",
    "military",
    "cemetery",
    "funeral",
    "religious",
    "worship",
    "mosque",
    "temple",
    "church",
    "television broadcasting",  # not relevant for most investors
]

# Investor-relevant category mapping — use word-boundary checks to avoid false matches
# e.g. "spa" must not match "spare parts"
_ACTIVITY_CATEGORIES: list[tuple[list[str], str]] = [
    (
        ["hotel", "resort", "villa", "guesthouse", "penginapan", "lodging (≥", "lodging (<"],
        "Hospitality",
    ),
    (
        [
            "restaurant",
            "café",
            "cafe",
            " bar ",
            "bakery",
            "catering",
            "food court",
            "food, beverage, and tobacco trade in shop",
            "trade of various goods in a store",
        ],
        "F&B",
    ),
    (
        [
            "spa ",
            "beauty salon",
            "beauty center",
            "beauty treatment",
            "wellness center",
            "yoga",
            "fitness center",
            "gym",
            "massage",
        ],
        "Wellness",
    ),
    (
        [
            "boutique ",
            "retail of",
            "specialty store",
            "fashion",
            "jewelry",
            "artisan craft",
            "souvenir",
            "art gallery",
            "gallery",
        ],
        "Retail",
    ),
    (
        [
            "consulting",
            "consultant",
            "law firm",
            "notary",
            "accounting firm",
            "financial advisor",
            "professional service",
        ],
        "Services",
    ),
    (
        [
            "real estate",
            "property development",
            "land development",
            "co-working space",
            "serviced apartment",
        ],
        "Property",
    ),
    (
        [
            "software",
            "information technology",
            "it service",
            "digital",
            "programming",
            "data center",
            "startup",
        ],
        "Technology",
    ),
    (
        [
            "school",
            "international school",
            "university",
            "college",
            "training center",
            "language course",
            "vocational",
        ],
        "Education",
    ),
    (
        ["hospital", "clinic", "medical center", "dental", "healthcare facility", "pharmaceutical"],
        "Healthcare",
    ),
    (
        [
            "food processing",
            "garment",
            "handicraft",
            "artisan manufacturing",
            "waste management",
            "recycling",
        ],
        "Industry",
    ),
    (
        [
            "design studio",
            "creative agency",
            "photography studio",
            "film production",
            "music studio",
            "architecture",
        ],
        "Creative",
    ),
    (
        [
            "restaurant and café",
            "café and restaurant",
            "coffee shop",
            "juice bar",
            "fine dining",
            "bistro",
            "lounge",
        ],
        "F&B",
    ),
]


def _classify_activity(name: str) -> str:
    """Map an activity name to an investor-friendly category."""
    lower = name.lower()
    for keywords, category in _ACTIVITY_CATEGORIES:
        if any(kw in lower for kw in keywords):
            return category
    return "Other"


def _is_investor_relevant(name: str) -> bool:
    """Filter out non-investor-relevant activities using skip patterns."""
    lower = name.lower()
    # Skip anything matching our blocklist
    if any(pat in lower for pat in _SKIP_PATTERNS):
        return False
    # Skip pure wholesale/trade that's not consumer-facing
    if lower.startswith("wholesale") and "fuel" not in lower:
        return False
    # Skip construction/infrastructure specifics
    infra_kw = [
        "road network",
        "road dimension",
        "pavement",
        "minimum jb",
        "minimum jbs",
        "minimum gsb",
    ]
    return not any(kw in lower for kw in infra_kw)


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
    "K-1": {
        "label_en": "City Commercial Zone",
        "desc_en": "Large-scale commerce — shopping centers, hotels, offices",
    },
    "K-2": {
        "label_en": "District Commercial Zone",
        "desc_en": "Mid-scale commerce — restaurants, retail, professional services",
    },
    "K-3": {
        "label_en": "Neighborhood Commercial Zone",
        "desc_en": "Small-scale commerce — cafés, boutiques, studios, wellness",
    },
    "C-1": {
        "label_en": "High-Density Mixed-Use Zone",
        "desc_en": "Hotels + residences + offices in the same area",
    },
    "C-2": {
        "label_en": "Medium Mixed-Use Zone",
        "desc_en": "Villas, cafés, and wellness businesses side by side",
    },
    "W": {
        "label_en": "Tourism Zone",
        "desc_en": "Hotels, resorts, restaurants, entertainment — tourism focus",
    },
    "W-1": {
        "label_en": "Tourism Zone (Type 1)",
        "desc_en": "Primary tourism area — resorts and large hotels",
    },
    "W-2": {
        "label_en": "Tourism Zone (Type 2)",
        "desc_en": "Secondary tourism area — boutique stays, restaurants",
    },
    "R-2": {
        "label_en": "High-Density Residential",
        "desc_en": "Dense housing — limited commercial activity permitted",
    },
    "R-3": {
        "label_en": "Medium-Density Residential",
        "desc_en": "Suburban housing — villa rentals and homestays possible",
    },
    "R-4": {
        "label_en": "Low-Density Residential",
        "desc_en": "Spacious housing — luxury villas and land investment",
    },
    "KPI": {
        "label_en": "Industrial Zone",
        "desc_en": "Manufacturing, food processing, craft production",
    },
    "KT": {
        "label_en": "Office / Business Park Zone",
        "desc_en": "Professional offices — consulting, tech, finance",
    },
    "SPU-1": {
        "label_en": "City Public Facility Zone",
        "desc_en": "Major public services — hospitals, universities",
    },
    "SPU-2": {
        "label_en": "District Public Facility",
        "desc_en": "District services — clinics, schools",
    },
    "SPU-3": {
        "label_en": "Village Public Facility",
        "desc_en": "Local services — community centers, worship",
    },
    "SPU-4": {"label_en": "Neighborhood Facility", "desc_en": "Smallest-scale public facilities"},
    "P-1": {
        "label_en": "Crop Farming Zone",
        "desc_en": "Protected agricultural land — no development permitted",
    },
    "P-2": {
        "label_en": "Horticulture Zone",
        "desc_en": "Fruit & vegetable farming — no development",
    },
    "P-3": {"label_en": "Plantation Zone", "desc_en": "Estate crops — no development"},
    "P-4": {"label_en": "Livestock Zone", "desc_en": "Animal husbandry — no development"},
    "HL": {
        "label_en": "Protected Forest",
        "desc_en": "⛔ Conservation forest — strictly no development",
    },
    "PS": {
        "label_en": "Riparian Buffer Zone",
        "desc_en": "⛔ Riverbank protection — no development",
    },
    "SS": {"label_en": "River Buffer Zone", "desc_en": "⛔ Streamside protection — no development"},
    "SP": {
        "label_en": "Coastal Buffer Zone",
        "desc_en": "⛔ Beachfront protection — no development",
    },
    "CB": {
        "label_en": "Cultural Heritage Zone",
        "desc_en": "⛔ Historical & cultural protection — strictly regulated",
    },
    "LS": {
        "label_en": "Spiritual & Sacred Zone",
        "desc_en": "⛔ Balinese sacred sites — no commercial activity",
    },
    "EM": {
        "label_en": "Mangrove Ecosystem",
        "desc_en": "⛔ Mangrove forest — protected, no development",
    },
    "TWA": {
        "label_en": "Nature Tourism Reserve",
        "desc_en": "⛔ Wildlife area — restricted access",
    },
    "THR": {"label_en": "City Forest Park", "desc_en": "⛔ Protected urban forest"},
    "KS-4": {"label_en": "Forest Reserve Park", "desc_en": "⛔ Protected nature reserve"},
    "BA": {"label_en": "Water Body", "desc_en": "⛔ River, lake, or sea — no development"},
    "BJ": {"label_en": "Road Infrastructure", "desc_en": "⛔ Public road right-of-way"},
    "TR": {"label_en": "Transportation Zone", "desc_en": "Airports, ports, terminals"},
    "RTH-2": {"label_en": "City Park", "desc_en": "Public green space — parks and gardens"},
    "RTH-3": {"label_en": "District Park", "desc_en": "Neighborhood green space"},
    "RTH-4": {"label_en": "Village Park", "desc_en": "Local green space"},
    "RTH-5": {"label_en": "Block Park", "desc_en": "Small local green space"},
    "RTH-7": {"label_en": "Cemetery", "desc_en": "Public cemetery"},
    "RTH-8": {"label_en": "Green Corridor", "desc_en": "Roadside or canal green strip"},
    "RTNH": {"label_en": "Non-Green Open Space", "desc_en": "Plazas, parking, paved open areas"},
    "HK": {"label_en": "Defense & Security Zone", "desc_en": "Military / government security area"},
    "PL-3": {
        "label_en": "Water Treatment Facility",
        "desc_en": "Public infrastructure — no development",
    },
    "PL-4": {
        "label_en": "Wastewater Facility",
        "desc_en": "Public infrastructure — no development",
    },
    "PTL": {
        "label_en": "Power Generation Zone",
        "desc_en": "Energy infrastructure — no development",
    },
    "IK-1": {
        "label_en": "Capture Fishery Zone",
        "desc_en": "Coastal fishing zone — no land development",
    },
}

_RESTRICTED_ZONES = {
    "HL",
    "PS",
    "CB",
    "LS",
    "EM",
    "BA",
    "BJ",
    "HK",
    "RTH-2",
    "RTH-3",
    "RTH-4",
    "KS-4",
    "IK-1",
    "P-1",
    "P-2",
    "P-3",
    "P-4",
    "PL-3",
    "PL-4",
    "PTL",
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
            # Two passes: priority items first (hospitality/F&B/wellness), then others
            priority_cats = {"Hospitality", "F&B", "Wellness", "Creative"}
            first_pass: list[dict[str, Any]] = []
            second_pass: list[dict[str, Any]] = []
            seen_categories: dict[str, int] = {}

            for act in activities:
                pivot = act.get("pivot", {})
                if not pivot.get("i", False):  # i = Izin (allowed)
                    continue
                name = act.get("name", "")
                if not name or not _is_investor_relevant(name):
                    continue
                category = _classify_activity(name)
                if category == "Other":
                    continue
                entry = {"title_en": name, "category_en": category, "pma_open": True}
                if category in priority_cats:
                    first_pass.append(entry)
                else:
                    second_pass.append(entry)

            # Merge: priority first, then others; cap each category at 2
            merged: list[dict[str, Any]] = []
            for entry in first_pass + second_pass:
                cat = entry["category_en"]
                if seen_categories.get(cat, 0) >= 2:
                    continue
                seen_categories[cat] = seen_categories.get(cat, 0) + 1
                merged.append(entry)

            businesses = merged[:10]

            hex_color = _rgb_string_to_hex(zone_color_rgb) if zone_color_rgb else None
            is_restricted = zone_code in _RESTRICTED_ZONES

            # Overlay data
            overlays: dict[str, str] = {}
            kkop_val = geom.get("kkop_1", "")
            if kkop_val and "tidak" not in kkop_val.lower():
                overlays["kkop"] = kkop_val
            if geom.get("lp2b_2") == "Ya":
                overlays["lp2b"] = "Protected farmland (LP2B)"
            if geom.get("krb_03") and geom["krb_03"] != "Tidak Ada":
                overlays["tsunami"] = geom["krb_03"]
            if geom.get("cagbud") and geom["cagbud"] != "Tidak Ada":
                overlays["heritage"] = geom["cagbud"]
            teb_val = geom.get("teb_05", "")
            if teb_val and "tidak" not in teb_val.lower():
                overlays["evac_center"] = teb_val

            label_info = _ZONE_LABELS.get(
                zone_code,
                {
                    "label_en": zone_name,
                    "desc_en": zone_definition[:120] if zone_definition else "",
                },
            )
            building_codes = _calculate_building_yield(zone_code)

            logger.info(
                f"✅ [Prime/BATARA] {zone_code} '{zone_name}' @ {lat},{lng} — {len(businesses)} businesses"
            )
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
                "building_codes": building_codes,
                "source": "BATARA/Badung DPUPR (official)",
            }

    except Exception as exc:
        logger.warning(f"⚠️ [Prime] BATARA query failed ({lat},{lng}): {exc}")
        return None


async def _query_price(lat: float, lng: float) -> float | None:
    """Lightweight PostGIS lookup — returns avg_price_per_are or None."""
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = await asyncpg.connect(db_url)
        try:
            row = await conn.fetchrow(_PRICE_QUERY, lng, lat)
        finally:
            await conn.close()
        if row and row["avg_price_per_are"]:
            return float(row["avg_price_per_are"])
    except Exception as exc:
        logger.debug(f"[Prime] Price lookup skipped: {exc}")
    return None


# =============================================================================
# INTEL SEARCH — semantic search against balizero_news Qdrant collection
# =============================================================================
_INTEL_COLLECTION = "balizero_news"

# Module-level embedder (lazy-init on first call, reused thereafter)
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = create_embeddings_generator(api_key=os.environ.get("OPENAI_API_KEY"))
    return _embedder


async def _search_local_intel(
    zone_code: str,
    subdistrict: str,
    category: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """
    Semantic search in balizero_news Qdrant collection for articles
    relevant to the clicked zone and location.
    Uses the Qdrant HTTP API directly to preserve full payload fields.
    Returns up to `limit` articles with title, source_url, category, published_at.
    """
    try:
        qdrant_url = os.environ.get("QDRANT_URL", "")
        qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")
        if not qdrant_url:
            return []

        # Build a natural-language query describing what investor would search for
        query_parts = [f"Bali {subdistrict} zone {zone_code}"]
        if category:
            query_parts.append(category.lower())
        query_parts.append("investment regulation property news")
        query_text = " ".join(query_parts)

        embedder = _get_embedder()
        embedding = await embedder.generate_single_embedding(query_text)

        search_url = f"{qdrant_url.rstrip('/')}/collections/{_INTEL_COLLECTION}/points/search"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if qdrant_api_key:
            headers["api-key"] = qdrant_api_key

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                search_url,
                json={"vector": embedding, "limit": limit * 2, "with_payload": True},
                headers=headers,
            )
            if resp.status_code != 200:
                logger.debug(f"[Prime] Intel search HTTP {resp.status_code}")
                return []
            data = resp.json()

        MIN_SCORE = 0.45
        articles: list[dict[str, Any]] = []
        for hit in data.get("result", []):
            score = hit.get("score", 0.0)
            if score < MIN_SCORE:
                continue
            payload = hit.get("payload", {})
            title = payload.get("title", "")
            source_url = payload.get("source_url", "")
            if not title or not source_url:
                continue
            articles.append(
                {
                    "title": title,
                    "source_url": source_url,
                    "category": payload.get("category", ""),
                    "source_name": payload.get("source_name", ""),
                    "published_at": payload.get("published_at", ""),
                    "relevance_score": round(score, 3),
                }
            )
            if len(articles) >= limit:
                break

        logger.info(
            f"[Prime/Intel] {len(articles)} articles found for {zone_code} in {subdistrict}"
        )
        return articles

    except Exception as exc:
        logger.warning(f"[Prime] Intel search skipped: {exc}")
        return []


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
    # --- PRIMARY: BATARA live API + parallel price lookup ---
    batara, price = await asyncio.gather(
        _query_batara(lat, lng),
        _query_price(lat, lng),
    )
    if batara:
        result: dict[str, Any] = {"status": "found", "lat": lat, "lng": lng, **batara}
        if price:
            result["avg_price_per_are"] = price
        # Intel search: use zone_code + area name in parallel (best-effort, non-blocking)
        zone_code_val = batara.get("zone_code", "")
        subdistrict_val = batara.get("zone_name", "Bali")
        intel_articles = await _search_local_intel(zone_code_val, subdistrict_val)
        if intel_articles:
            result["intel_articles"] = intel_articles
        return result

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

        label_info = _ZONE_LABELS.get(
            zone_code, {"label_en": zone_name, "desc_en": "Contact local authorities for details"}
        )
        is_restricted = zone_code in _RESTRICTED_ZONES
        building_codes = _calculate_building_yield(zone_code)

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
            "building_codes": building_codes,
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


# =============================================================================
# ZONE COLORS — GeoJSON for frontend polygon overlay
# In-memory cache: zones don't change, no need to re-query per request.
# =============================================================================

_ZONES_GEOJSON_CACHE: dict[str, Any] | None = None

_ZONE_COLORS_MAP: dict[str, str] = {
    "K-1": "#E8472A",
    "K-2": "#E8472A",
    "K-3": "#E8472A",
    "C-1": "#F0826E",
    "C-2": "#F0826E",
    "W": "#FFA5FF",
    "W-1": "#FFA5FF",
    "W-2": "#FF85F5",
    "R-2": "#FF7D00",
    "R-3": "#FF9D30",
    "R-4": "#FFB860",
    "P-1": "#C8C83C",
    "P-2": "#D4D44A",
    "P-3": "#C8C83C",
    "P-4": "#BEB82E",
    "KT": "#A855F7",
    "KPI": "#690000",
    "SPU-1": "#D4845A",
    "SPU-2": "#D4845A",
    "SPU-3": "#D4845A",
    "SPU-4": "#D4845A",
    "HL": "#224027",
    "KS-4": "#224027",
    "THR": "#224027",
    "TWA": "#224027",
    "EM": "#2D966E",
    "PS": "#05D7D7",
    "SS": "#05D7D7",
    "SP": "#05D7D7",
    "LS": "#F59E0B",
    "CB": "#B45309",
    "RTH-2": "#3BA062",
    "RTH-3": "#3BA062",
    "RTH-4": "#3BA062",
    "RTH-5": "#3BA062",
    "RTH-7": "#6B7280",
    "RTH-8": "#3BA062",
    "RTNH": "#9CA3AF",
    "BA": "#97DBF2",
    "BJ": "#9CA3AF",
    "TR": "#6B7280",
    "HK": "#9B00FF",
    "PL-3": "#6B7280",
    "PL-4": "#6B7280",
    "PTL": "#6B7280",
    "IK-1": "#507DD2",
}

_ZONES_GEOJSON_QUERY = """
    SELECT
        ST_AsGeoJSON(ST_Simplify(l.boundary, 0.0001)) AS geometry,
        l.zoning_type,
        l.kodszn,
        m.max_floors,
        m.max_height_meters,
        m.kdb as master_kdb
    FROM bali_zoning_layers l
    LEFT JOIN master_building_codes m ON l.kodszn = m.kodszn AND l.district_name = m.district_name
    WHERE l.boundary IS NOT NULL
"""


@router.get("/zones-geojson")
async def get_zones_geojson() -> dict[str, Any]:
    """
    Return a GeoJSON FeatureCollection of all zoning polygons with their
    official colors. Simplified (tolerance 0.0001) for fast frontend rendering.
    Result is cached in-memory after first load.
    """
    global _ZONES_GEOJSON_CACHE
    if _ZONES_GEOJSON_CACHE is not None:
        return _ZONES_GEOJSON_CACHE

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return {"type": "FeatureCollection", "features": []}

    try:
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(_ZONES_GEOJSON_QUERY)
        finally:
            await conn.close()

        features: list[dict[str, Any]] = []
        for row in rows:
            geom_str = row["geometry"]
            if not geom_str:
                continue
            try:
                geom = json.loads(geom_str)
            except Exception:
                continue

            zone_type: str = row["zoning_type"] or ""
            zone_code = row["kodszn"] or zone_type.split(":")[0].strip()
            color = _ZONE_COLORS_MAP.get(zone_code, "#6B7280")

            # 3D parameters
            max_floors = row["max_floors"]
            max_height = float(row["max_height_meters"]) if row["max_height_meters"] else 15.0
            kdb = float(row["master_kdb"]) if row["master_kdb"] else 50.0

            features.append(
                {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "zone_code": zone_code,
                        "zone_type": zone_type,
                        "color": color,
                        "max_floors": max_floors,
                        "max_height_meters": max_height,
                        "kdb": kdb,
                    },
                }
            )

        result: dict[str, Any] = {"type": "FeatureCollection", "features": features}
        _ZONES_GEOJSON_CACHE = result
        logger.info(f"✅ [Prime/GeoJSON] Loaded {len(features)} zone polygons (cached)")
        return result

    except Exception as e:
        logger.error(f"❌ [Prime/GeoJSON] Failed to load zones: {e}", exc_info=True)
        return {"type": "FeatureCollection", "features": []}
