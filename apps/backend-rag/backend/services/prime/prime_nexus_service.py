"""
Prime Nexus Service — Unified geospatial intelligence for Nuzantara.

Extracts shared logic from prime.py and dashboard.py into a single service
with a 3-layer resolution pipeline:
  Layer 1: resolve(lat, lng)  — spatial zone resolution (target < 50ms cache / < 2s cold)
  Layer 2: analyze(lat, lng)  — investment analysis with scoring (target < 3s)
  Layer 3: intelligence(bounds) — CRM overlay within bounding box (target < 3s)

Decisions:
  D1: Shared service, NOT merged router — routers stay as thin wrappers with fallback
  D2: Redis cache with geohash keys (not floating-point lat/lng)
  D3: Circuit breaker on BATARA/GISTARU (3 failures → skip 5min)
"""

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import asyncpg
import httpx

from backend.services.kbli_eye import KBLIEye

logger = logging.getLogger(__name__)

# =============================================================================
# GEOHASH — lightweight implementation (no external dependency)
# Precision 8 ≈ 38m x 19m, Precision 6 ≈ 1.2km x 0.6km
# =============================================================================
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode_geohash(lat: float, lng: float, precision: int = 8) -> str:
    """Encode lat/lng to geohash string at given precision."""
    lat_range = (-90.0, 90.0)
    lng_range = (-180.0, 180.0)
    bits = [16, 8, 4, 2, 1]
    hash_chars: list[str] = []
    ch = 0
    bit = 0
    is_lng = True

    while len(hash_chars) < precision:
        if is_lng:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng >= mid:
                ch |= bits[bit]
                lng_range = (mid, lng_range[1])
            else:
                lng_range = (lng_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                ch |= bits[bit]
                lat_range = (mid, lat_range[1])
            else:
                lat_range = (lat_range[0], mid)
        is_lng = not is_lng
        if bit < 4:
            bit += 1
        else:
            hash_chars.append(_BASE32[ch])
            ch = 0
            bit = 0

    return "".join(hash_chars)


# =============================================================================
# BUILDING CODES — loaded once from JSON
# =============================================================================
_BUILDING_CODES_PATH = (
    Path(__file__).parent.parent.parent / "data" / "master_building_codes_complete.json"
)
try:
    with open(_BUILDING_CODES_PATH, encoding="utf-8") as _f:
        _BUILDING_CODES: dict[str, dict[str, str]] = json.load(_f)
    logger.info("✅ [PrimeNexus] Loaded building codes for %d zone types", len(_BUILDING_CODES))
except Exception as _e:
    _BUILDING_CODES = {}
    logger.warning("⚠️ [PrimeNexus] Could not load building codes: %s", _e)


def parse_tb_to_meters(tb_str: str | None) -> float | None:
    """Parse TB height strings like '15 Meter', '4 Meter', '8m' → float meters."""
    if not tb_str or tb_str.strip().upper() == "N/A":
        return None
    import re
    m = re.match(r"(\d+(?:[.,]\d+)?)", tb_str.strip())
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def calculate_building_yield(zone_code: str) -> dict[str, Any] | None:
    """Return building limit summary for a zone code."""
    data = _BUILDING_CODES.get(zone_code)
    if not data:
        return None

    def _parse_pct(val: str) -> float:
        return float(val.replace(",", ".").replace("%", "").strip())

    try:
        return {
            "zone_name_id": data.get("name", ""),
            "kdb_pct": _parse_pct(data.get("KDB", "0")),
            "klb_ratio": _parse_pct(data.get("KLB", "0")),
            "kdh_pct": _parse_pct(data.get("KDH", "0")),
            "ktb_pct": _parse_pct(data.get("KTB", "0")),
            "height_limit": data.get("TB", "—"),
            "max_height_meters": parse_tb_to_meters(data.get("TB")),
            "setback": data.get("GSB", "—"),
            "notes": data.get("note", ""),
        }
    except Exception as exc:
        logger.warning("⚠️ [PrimeNexus] Building codes parse error for %s: %s", zone_code, exc)
        return None


# =============================================================================
# ZONE LABELS + COLORS + RESTRICTED SETS
# =============================================================================
ZONE_LABELS: dict[str, dict[str, str]] = {
    "K-1": {"label_en": "City Commercial Zone", "desc_en": "Large-scale commerce — shopping centers, hotels, offices"},
    "K-2": {"label_en": "District Commercial Zone", "desc_en": "Mid-scale commerce — restaurants, retail, professional services"},
    "K-3": {"label_en": "Neighborhood Commercial Zone", "desc_en": "Small-scale commerce — cafés, boutiques, studios, wellness"},
    "C-1": {"label_en": "High-Density Mixed-Use Zone", "desc_en": "Hotels + residences + offices in the same area"},
    "C-2": {"label_en": "Medium Mixed-Use Zone", "desc_en": "Villas, cafés, and wellness businesses side by side"},
    "W": {"label_en": "Tourism Zone", "desc_en": "Hotels, resorts, restaurants, entertainment — tourism focus"},
    "W-1": {"label_en": "Tourism Zone (Type 1)", "desc_en": "Primary tourism area — resorts and large hotels"},
    "W-2": {"label_en": "Tourism Zone (Type 2)", "desc_en": "Secondary tourism area — boutique stays, restaurants"},
    "R-2": {"label_en": "High-Density Residential", "desc_en": "Dense housing — limited commercial activity permitted"},
    "R-3": {"label_en": "Medium-Density Residential", "desc_en": "Suburban housing — villa rentals and homestays possible"},
    "R-4": {"label_en": "Low-Density Residential", "desc_en": "Spacious housing — luxury villas and land investment"},
    "KPI": {"label_en": "Industrial Zone", "desc_en": "Manufacturing, food processing, craft production"},
    "KT": {"label_en": "Office / Business Park Zone", "desc_en": "Professional offices — consulting, tech, finance"},
    "SPU-1": {"label_en": "City Public Facility Zone", "desc_en": "Major public services — hospitals, universities"},
    "SPU-2": {"label_en": "District Public Facility", "desc_en": "District services — clinics, schools"},
    "SPU-3": {"label_en": "Village Public Facility", "desc_en": "Local services — community centers, worship"},
    "SPU-4": {"label_en": "Neighborhood Facility", "desc_en": "Smallest-scale public facilities"},
    "P-1": {"label_en": "Crop Farming Zone", "desc_en": "Protected agricultural land — no development permitted"},
    "P-2": {"label_en": "Horticulture Zone", "desc_en": "Fruit & vegetable farming — no development"},
    "P-3": {"label_en": "Plantation Zone", "desc_en": "Estate crops — no development"},
    "P-4": {"label_en": "Livestock Zone", "desc_en": "Animal husbandry — no development"},
    "HL": {"label_en": "Protected Forest", "desc_en": "Conservation forest — strictly no development"},
    "PS": {"label_en": "Riparian Buffer Zone", "desc_en": "Riverbank protection — no development"},
    "SS": {"label_en": "River Buffer Zone", "desc_en": "Streamside protection — no development"},
    "SP": {"label_en": "Coastal Buffer Zone", "desc_en": "Beachfront protection — no development"},
    "CB": {"label_en": "Cultural Heritage Zone", "desc_en": "Historical & cultural protection — strictly regulated"},
    "LS": {"label_en": "Spiritual & Sacred Zone", "desc_en": "Balinese sacred sites — no commercial activity"},
    "EM": {"label_en": "Mangrove Ecosystem", "desc_en": "Mangrove forest — protected, no development"},
    "TWA": {"label_en": "Nature Tourism Reserve", "desc_en": "Wildlife area — restricted access"},
    "THR": {"label_en": "City Forest Park", "desc_en": "Protected urban forest"},
    "KS-4": {"label_en": "Forest Reserve Park", "desc_en": "Protected nature reserve"},
    "BA": {"label_en": "Water Body", "desc_en": "River, lake, or sea — no development"},
    "BJ": {"label_en": "Road Infrastructure", "desc_en": "Public road right-of-way"},
    "TR": {"label_en": "Transportation Zone", "desc_en": "Airports, ports, terminals"},
    "RTH-2": {"label_en": "City Park", "desc_en": "Public green space — parks and gardens"},
    "RTH-3": {"label_en": "District Park", "desc_en": "Neighborhood green space"},
    "RTH-4": {"label_en": "Village Park", "desc_en": "Local green space"},
    "RTH-5": {"label_en": "Block Park", "desc_en": "Small local green space"},
    "RTH-7": {"label_en": "Cemetery", "desc_en": "Public cemetery"},
    "RTH-8": {"label_en": "Green Corridor", "desc_en": "Roadside or canal green strip"},
    "RTNH": {"label_en": "Non-Green Open Space", "desc_en": "Plazas, parking, paved open areas"},
    "HK": {"label_en": "Defense & Security Zone", "desc_en": "Military / government security area"},
    "PL-3": {"label_en": "Water Treatment Facility", "desc_en": "Public infrastructure — no development"},
    "PL-4": {"label_en": "Wastewater Facility", "desc_en": "Public infrastructure — no development"},
    "PTL": {"label_en": "Power Generation Zone", "desc_en": "Energy infrastructure — no development"},
    "IK-1": {"label_en": "Capture Fishery Zone", "desc_en": "Coastal fishing zone — no land development"},
}

RESTRICTED_ZONES = {
    "HL", "PS", "CB", "LS", "EM", "BA", "BJ", "HK",
    "RTH-2", "RTH-3", "RTH-4", "KS-4", "IK-1",
    "P-1", "P-2", "P-3", "P-4", "PL-3", "PL-4", "PTL",
}

ZONE_COLORS_MAP: dict[str, str] = {
    "K-1": "#E8472A", "K-2": "#E8472A", "K-3": "#E8472A",
    "C-1": "#F0826E", "C-2": "#F0826E",
    "W": "#FFA5FF", "W-1": "#FFA5FF", "W-2": "#FF85F5",
    "R-2": "#FF7D00", "R-3": "#FF9D30", "R-4": "#FFB860",
    "P-1": "#C8C83C", "P-2": "#D4D44A", "P-3": "#C8C83C", "P-4": "#BEB82E",
    "KT": "#A855F7", "KPI": "#690000",
    "SPU-1": "#D4845A", "SPU-2": "#D4845A", "SPU-3": "#D4845A", "SPU-4": "#D4845A",
    "HL": "#224027", "KS-4": "#224027", "THR": "#224027", "TWA": "#224027",
    "EM": "#2D966E", "PS": "#05D7D7", "SS": "#05D7D7", "SP": "#05D7D7",
    "LS": "#F59E0B", "CB": "#B45309",
    "RTH-2": "#3BA062", "RTH-3": "#3BA062", "RTH-4": "#3BA062",
    "RTH-5": "#3BA062", "RTH-7": "#6B7280", "RTH-8": "#3BA062",
    "RTNH": "#9CA3AF", "BA": "#97DBF2", "BJ": "#9CA3AF", "TR": "#6B7280",
    "HK": "#9B00FF", "PL-3": "#6B7280", "PL-4": "#6B7280", "PTL": "#6B7280",
    "IK-1": "#507DD2",
}

# =============================================================================
# ACTIVITY CLASSIFICATION (extracted from prime.py)
# =============================================================================
_SKIP_PATTERNS = [
    "local resident", "employee", "official residence", "boarding house",
    "single house", "cluster house", "coupled house", "dormitory", "townhouse",
    "septic tank", "wastewater", "irrigation", "cleanwater", "trash can",
    "toilet facility", "parking area", "pedestrian lane", "disability access",
    "loading unloading", "road network", "road complete", "bike lane",
    "public road access", "pavement area", "lot area", "building height",
    "minimum gsb", "minimum kdh", "maximum kdb", "maximum klb", "maximum ktb",
    "road dimension", "road equipment", "trash", "zone_requirement",
    "car trading", "car spare parts", "motorcycle trade", "motorcycle maintenance",
    "wholesale trade of fishery", "wholesale of motor vehicle",
    "wholesale trade of food", "wholesale of household",
    "wholesale of machinery", "wholesale of building material",
    "wholesale of agricultural", "wholesale of fuel",
    "village government", "government service", "public service office",
    "fire station", "police", "military", "cemetery", "funeral",
    "religious", "worship", "mosque", "temple", "church",
    "television broadcasting",
]

_ACTIVITY_CATEGORIES: list[tuple[list[str], str]] = [
    (["hotel", "resort", "villa", "guesthouse", "penginapan", "lodging (≥", "lodging (<"], "Hospitality"),
    (["restaurant", "café", "cafe", " bar ", "bakery", "catering", "food court",
      "food, beverage, and tobacco trade in shop", "trade of various goods in a store"], "F&B"),
    (["spa ", "beauty salon", "beauty center", "beauty treatment",
      "wellness center", "yoga", "fitness center", "gym", "massage"], "Wellness"),
    (["boutique ", "retail of", "specialty store", "fashion", "jewelry",
      "artisan craft", "souvenir", "art gallery", "gallery"], "Retail"),
    (["consulting", "consultant", "law firm", "notary", "accounting firm",
      "financial advisor", "professional service"], "Services"),
    (["real estate", "property development", "land development",
      "co-working space", "serviced apartment"], "Property"),
    (["software", "information technology", "it service", "digital",
      "programming", "data center", "startup"], "Technology"),
    (["school", "international school", "university", "college",
      "training center", "language course", "vocational"], "Education"),
    (["hospital", "clinic", "medical center", "dental",
      "healthcare facility", "pharmaceutical"], "Healthcare"),
    (["food processing", "garment", "handicraft", "artisan manufacturing",
      "waste management", "recycling"], "Industry"),
    (["design studio", "creative agency", "photography studio",
      "film production", "music studio", "architecture"], "Creative"),
    (["restaurant and café", "café and restaurant", "coffee shop",
      "juice bar", "fine dining", "bistro", "lounge"], "F&B"),
]


def classify_activity(name: str) -> str:
    """Map an activity name to an investor-friendly category."""
    lower = name.lower()
    for keywords, category in _ACTIVITY_CATEGORIES:
        if any(kw in lower for kw in keywords):
            return category
    return "Other"


def is_investor_relevant(name: str) -> bool:
    """Filter out non-investor-relevant activities."""
    lower = name.lower()
    if any(pat in lower for pat in _SKIP_PATTERNS):
        return False
    if lower.startswith("wholesale") and "fuel" not in lower:
        return False
    infra_kw = ["road network", "road dimension", "pavement", "minimum jb", "minimum jbs", "minimum gsb"]
    return not any(kw in lower for kw in infra_kw)


def rgb_string_to_hex(rgb_str: str) -> str:
    """Convert '250 211 140' → '#fad38c'."""
    try:
        parts = [int(x) for x in rgb_str.replace(",", " ").split()]
        if len(parts) == 3:
            return "#{:02x}{:02x}{:02x}".format(*parts)
    except (ValueError, AttributeError):
        pass
    return "#6B7280"


# =============================================================================
# ZONE-KBLI COMPATIBILITY (extracted from dashboard.py)
# =============================================================================
NON_BUILDABLE_ZONES: set[str] = {
    "BA", "BJ", "SS", "SP", "LS", "P-1", "P-2",
    "RTH-1", "RTH-2", "RTH-4", "RTH-7", "RTNH",
    "PL-1", "PL-3", "PL-4",
}

_ZONE_KBLI_IDEAL: dict[str, set[str]] = {
    "55": {"W-", "C-"}, "56": {"K-", "C-"}, "47": {"K-", "C-"},
    "68": {"R-", "K-", "C-"}, "70": {"KT", "K-", "C-"},
    "62": {"KT", "K-", "C-"}, "77": {"K-", "C-"},
    "79": {"W-", "K-", "C-"}, "96": {"W-", "K-", "C-"},
    "90": {"W-", "C-", "SPU"}, "91": {"W-", "SPU", "C-"},
    "85": {"SPU", "C-"}, "93": {"W-", "SPU", "C-"},
}

_ZONE_KBLI_TOLERATED: dict[str, set[str]] = {
    "55": {"R-"}, "56": {"W-"}, "47": {"R-"},
}

_ZONE_KBLI_ACCEPTABLE: dict[str, set[str]] = {
    "55": {"K-"}, "56": {"R-"}, "68": {"W-"}, "77": {"W-"}, "79": {"R-"},
}

_NIGHTLIFE_CODES: set[str] = {"56301", "56302"}
_NIGHTLIFE_IDEAL_ZONES: set[str] = {"K-", "W-", "C-"}
_NIGHTLIFE_PENALTY_ZONES: set[str] = {"R-"}


def _zone_matches_prefix(zone_code: str, prefixes: set[str]) -> bool:
    return any(zone_code.startswith(p) for p in prefixes)


def calculate_zone_kbli_fit(zone_code: str | None, kbli_code: str | None) -> tuple[int, str]:
    """Zone-KBLI compatibility score (0-20) + tier label."""
    if not zone_code or not kbli_code:
        return 12, "unknown"
    prefix = kbli_code[:2]
    if zone_code in NON_BUILDABLE_ZONES:
        return 0, "incompatible"
    if kbli_code in _NIGHTLIFE_CODES:
        if _zone_matches_prefix(zone_code, _NIGHTLIFE_IDEAL_ZONES):
            return 20, "ideal"
        if _zone_matches_prefix(zone_code, _NIGHTLIFE_PENALTY_ZONES):
            return 2, "poor"
        return 8, "tolerated"
    ideal = _ZONE_KBLI_IDEAL.get(prefix)
    if ideal and _zone_matches_prefix(zone_code, ideal):
        return 20, "ideal"
    acceptable = _ZONE_KBLI_ACCEPTABLE.get(prefix)
    if acceptable and _zone_matches_prefix(zone_code, acceptable):
        return 12, "acceptable"
    tolerated = _ZONE_KBLI_TOLERATED.get(prefix)
    if tolerated and _zone_matches_prefix(zone_code, tolerated):
        return 8, "tolerated"
    return 4, "poor"


def calculate_investment_score(
    zone_data: dict[str, Any] | None,
    kbli_state: str | None,
    kbli_code: str | None,
    roi_data: dict[str, Any] | None,
    geo_data: dict[str, Any] | None,
    oss_risk: str | None = None,
) -> dict[str, Any]:
    """3-Layer investment scoring engine. Extracted from dashboard.py."""
    zone_code = zone_data.get("code") if zone_data else None
    overlays = zone_data.get("overlays", {}) if zone_data else {}
    zone_source = zone_data.get("source", "") if zone_data else ""

    # Layer 1: Hard Blocks
    hard_blocks: list[str] = []
    if kbli_state == "REJECTED":
        hard_blocks.append("KBLI chiuso a PMA (Perpres 10/2021)")
    if zone_code and zone_code in NON_BUILDABLE_ZONES:
        hard_blocks.append(f"Zona {zone_code} non edificabile")
    if overlays.get("LP2B_2") or overlays.get("lp2b_2"):
        hard_blocks.append("Terreno agricolo protetto (LP2B)")
    if zone_data and zone_source == "unavailable":
        hard_blocks.append("Nessun dato zona disponibile")

    klb_raw = zone_data.get("klb", "N/A") if zone_data else "N/A"
    klb_val: float | None = None
    if klb_raw and klb_raw != "N/A":
        with contextlib.suppress(ValueError, TypeError):
            klb_val = float(str(klb_raw).replace(",", "."))
    if klb_val is not None and klb_val < 0.05:
        hard_blocks.append(f"KLB {klb_raw} — costruibilità quasi nulla")

    if overlays.get("KKOP_1"):
        tb_raw = zone_data.get("tb", "N/A") if zone_data else "N/A"
        tb_meters: float | None = None
        with contextlib.suppress(ValueError, TypeError, IndexError):
            tb_meters = float(str(tb_raw).split()[0].replace(",", "."))
        if tb_meters is not None and tb_meters <= 4.0:
            hard_blocks.append(f"KKOP + TB {tb_raw} — altezza edificio troppo limitata")

    if hard_blocks:
        return {
            "verdict": "RED", "can_invest": False, "score": 0,
            "breakdown": {}, "modifiers": [], "hard_blocks": hard_blocks,
        }

    # Layer 2: Composite Score (0-100)
    breakdown: dict[str, dict[str, Any]] = {}

    roi_val: float | None = None
    if roi_data and not roi_data.get("error"):
        roi_val = roi_data.get("golden_strategy", {}).get("roi")
    roi_score: int | None = None
    if roi_val is not None:
        roi_score = 30 if roi_val >= 12 else 22 if roi_val >= 8 else 12 if roi_val >= 4 else 0
    breakdown["roi"] = {"score": roi_score, "max": 30, "value": roi_val}

    zone_kbli_raw, zone_kbli_tier = calculate_zone_kbli_fit(zone_code, kbli_code)
    zone_kbli_score: int | None = round(zone_kbli_raw * 15 / 20)
    breakdown["zone_kbli_fit"] = {"score": zone_kbli_score, "max": 15, "tier": zone_kbli_tier}

    klb_score: int | None = None
    if klb_val is not None:
        klb_score = 10 if klb_val >= 2.0 else 8 if klb_val >= 1.2 else 5 if klb_val >= 0.6 else 2 if klb_val >= 0.2 else 0
    breakdown["building_capacity"] = {"score": klb_score, "max": 10, "klb": klb_val}

    bey_val: float | None = None
    if roi_data and not roi_data.get("error"):
        bey_val = roi_data.get("golden_strategy", {}).get("bey")
    bey_score: int | None = None
    if bey_val is not None:
        bey_score = 15 if bey_val <= 5 else 12 if bey_val <= 8 else 6 if bey_val <= 12 else 0
    breakdown["break_even"] = {"score": bey_score, "max": 15, "value": bey_val}

    flood = geo_data.get("flood_risk") if geo_data else None
    flood_score = {"safe": 10, "check": 5, "high": 0}.get(str(flood), 7)
    breakdown["flood_risk"] = {"score": flood_score, "max": 10, "value": flood}

    density_1km = geo_data.get("densita_1km") if geo_data else None
    if density_1km is not None:
        market_score = 10 if 30 <= density_1km <= 70 else 6 if density_1km < 30 else 3
    else:
        market_score = 5
    breakdown["market"] = {"score": market_score, "max": 10, "value": density_1km}

    if kbli_state == "APPROVED":
        reg_base = 10
    elif kbli_state == "WARNING":
        reg_base = 5
    elif kbli_state is None:
        reg_base = 7
    else:
        reg_base = 0
    oss_penalty = 3 if oss_risk == "Tinggi" else 2 if oss_risk == "Menengah Tinggi" else 0
    reg_score = max(0, reg_base - oss_penalty)
    breakdown["regulatory"] = {"score": reg_score, "max": 10, "state": kbli_state, "oss_risk": oss_risk}

    ws = geo_data.get("walk_score") if geo_data else None
    ws_score = 5 if ws is not None and ws >= 65 else 3 if ws is not None and ws >= 35 else 1 if ws is not None else 2
    breakdown["amenity"] = {"score": ws_score, "max": 5, "value": ws}

    _all_scores = [roi_score, zone_kbli_score, klb_score, bey_score, flood_score, market_score, reg_score, ws_score]
    _all_maxes = [30, 15, 10, 15, 10, 10, 10, 5]
    earned = sum(s for s in _all_scores if s is not None)
    available = sum(m for s, m in zip(_all_scores, _all_maxes, strict=True) if s is not None)
    score = round(earned / available * 100) if available > 0 else 0

    # Layer 3: Contextual Modifiers
    modifiers: list[str] = []
    _excluded = []
    if roi_score is None:
        _excluded.append("ROI")
    if klb_score is None:
        _excluded.append("KLB")
    if bey_score is None:
        _excluded.append("Break-Even")
    if _excluded:
        modifiers.append(f"Esclusi dal calcolo: {', '.join(_excluded)} (dati mancanti)")

    _OVERLAY_PENALTIES: dict[str, tuple[int, str]] = {
        "KKOP_1": (12, "Zona Keselamatan Operasi Penerbangan — altezza edifici limitata"),
        "SEMPDN": (8, "Sempadan pantai/sungai — fascia protetta, costruzione limitata"),
        "KRB_03": (7, "Kawasan Rawan Bencana — zona rischio disastri naturali"),
        "RESAIR": (6, "Resapan Air — zona ricarica acquiferi, impermeabilizzazione limitata"),
        "TEB_05": (5, "Zona Taman Hutan — restrizioni ambientali"),
        "CAGBUD": (5, "Cagar Budaya — vincoli patrimonio culturale"),
        "HANKAM": (10, "Zona Pertahanan/Keamanan — area militare/sicurezza"),
    }
    overlay_penalty_total = 0
    for ov_key, ov_val in overlays.items():
        if ov_val and ov_key in _OVERLAY_PENALTIES:
            penalty, desc = _OVERLAY_PENALTIES[ov_key]
            overlay_penalty_total += penalty
            modifiers.append(f"-{penalty}: {desc}")
    if overlay_penalty_total > 0:
        score -= min(overlay_penalty_total, 25)

    if zone_kbli_tier == "tolerated":
        modifiers.append("⚠️ Gray zone: attività comune ma non normativamente ideale. Verificare IMB/PBG.")
    if zone_code and zone_code.startswith("W-2") and kbli_code and kbli_code.startswith("55"):
        tb_raw = zone_data.get("tb", "N/A") if zone_data else "N/A"
        modifiers.append(f"⚠️ W-2: villa limitata a 8m/2 piani (hotel fino a 15m/4 piani). TB: {tb_raw}")
        score -= 3

    sea_view = geo_data.get("sea_view", False) if geo_data else False
    if sea_view and score >= 55:
        score += 5
        modifiers.append("+5: potenziale premium vista mare")

    gistaru_cap = zone_source == "gistaru_rdtr"
    if gistaru_cap:
        modifiers.append("CAP: dati zona da GISTARU (parametri KDB/KLB mancanti)")

    score = max(0, min(100, score))

    if gistaru_cap and score >= 65:
        verdict = "YELLOW"
    elif score >= 65:
        verdict = "GREEN"
    elif score >= 35:
        verdict = "YELLOW"
    else:
        verdict = "RED"

    return {
        "verdict": verdict, "can_invest": verdict != "RED", "score": score,
        "breakdown": breakdown, "modifiers": modifiers, "hard_blocks": [],
    }


# =============================================================================
# BATARA + GISTARU API CONSTANTS
# =============================================================================
_BATARA_API_URL = "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point"
_BATARA_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://app.batara.badungkab.go.id/",
    "Origin": "https://app.batara.badungkab.go.id",
    "User-Agent": "Mozilla/5.0",
}

GISTARU_PROXY = "https://gistaru-proxy.atrbpn.go.id/proxy.ashx?"
GISTARU_RDTR_API = "https://gistaru.atrbpn.go.id/rdtrinteraktif/api/interactive"
GISTARU_MAPSERVER_BASE = "https://gistaru.atrbpn.go.id/arcgis/rest/services/060_RDTR_PROVINSI_BALI"
GISTARU_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gistaru.atrbpn.go.id/"}


# =============================================================================
# PrimeNexusService
# =============================================================================
class PrimeNexusService:
    """Unified geospatial intelligence service with circuit breaker.

    IMPORTANT: Use a single instance per app lifecycle (via app.state).
    The persistent HTTP client (_http_client) MUST be closed on shutdown.
    """

    def __init__(self, cache_service: Any = None, db_pool: asyncpg.Pool | None = None) -> None:
        self._cache = cache_service
        self._db_pool = db_pool
        self._kbli_eye: KBLIEye | None = None
        # Persistent HTTP client (Golden Rule #10: never create per-request)
        self._http_client: httpx.AsyncClient | None = None

        # Circuit breaker state
        self._batara_failures = 0
        self._batara_skip_until: float = 0.0
        self._gistaru_failures = 0
        self._gistaru_skip_until: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=12.0)
        return self._http_client

    async def close(self) -> None:
        """Close persistent HTTP client. Call in app lifespan shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.close()
            self._http_client = None

    def _get_kbli_eye(self) -> KBLIEye:
        if self._kbli_eye is None:
            self._kbli_eye = KBLIEye()
        return self._kbli_eye

    # ── Circuit Breaker Helpers ──────────────────────────────────────
    def _should_skip_batara(self) -> bool:
        if self._batara_failures >= 3 and time.time() < self._batara_skip_until:
            return True
        if time.time() >= self._batara_skip_until:
            self._batara_failures = 0
        return False

    def _record_batara_failure(self) -> None:
        self._batara_failures += 1
        if self._batara_failures >= 3:
            self._batara_skip_until = time.time() + 300  # skip 5 min
            logger.warning("⚡ [PrimeNexus] BATARA circuit breaker OPEN (3 failures, skip 5min)")

    def _record_batara_success(self) -> None:
        self._batara_failures = 0

    def _should_skip_gistaru(self) -> bool:
        if self._gistaru_failures >= 3 and time.time() < self._gistaru_skip_until:
            return True
        if time.time() >= self._gistaru_skip_until:
            self._gistaru_failures = 0
        return False

    def _record_gistaru_failure(self) -> None:
        self._gistaru_failures += 1
        if self._gistaru_failures >= 3:
            self._gistaru_skip_until = time.time() + 300
            logger.warning("⚡ [PrimeNexus] GISTARU circuit breaker OPEN (3 failures, skip 5min)")

    def _record_gistaru_success(self) -> None:
        self._gistaru_failures = 0

    # ── Layer 1: Spatial Resolution ──────────────────────────────────
    async def resolve(self, lat: float, lng: float) -> dict[str, Any]:
        """
        Resolve zoning data for a point. Pipeline: Redis → BATARA → GISTARU → PostGIS.
        Returns standardized zone resolution dict.
        """
        # 1. Check Redis cache (geohash key)
        gh = encode_geohash(lat, lng, precision=8)
        cache_key = f"prime:zone:gh:{gh}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.debug("[PrimeNexus] Cache HIT for %s", cache_key)
                    result = cached if isinstance(cached, dict) else json.loads(cached)
                    result["cache_hit"] = True
                    return result
            except Exception as exc:
                logger.debug("[PrimeNexus] Cache get failed: %s", exc)

        # 2. BATARA API (primary, Badung regency)
        batara_result = None
        if not self._should_skip_batara():
            batara_result = await self._query_batara(lat, lng)

        if batara_result:
            response = self._build_resolve_response(lat, lng, batara_result, "batara_live", 1.0)
            await self._cache_zone(cache_key, response)
            return response

        # 3. GISTARU fallback (non-Badung areas)
        gistaru_result = None
        if not self._should_skip_gistaru():
            gistaru_result = await self._query_gistaru(lat, lng)

        if gistaru_result:
            response = self._build_resolve_response_from_gistaru(lat, lng, gistaru_result)
            await self._cache_zone(cache_key, response)
            return response

        # 4. PostGIS fallback (ultimate)
        postgis_result = await self._query_postgis(lat, lng)
        if postgis_result:
            response = self._build_resolve_response_from_postgis(lat, lng, postgis_result)
            await self._cache_zone(cache_key, response)
            return response

        return {
            "status": "outside_coverage",
            "lat": lat, "lng": lng,
            "zone": None,
            "cache_hit": False,
            "message": "Coordinates outside mapped RDTR coverage.",
        }

    # ── BATARA query ─────────────────────────────────────────────────
    async def _query_batara(self, lat: float, lng: float) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            resp = await client.post(
                _BATARA_API_URL,
                json={"x": str(lng), "y": str(lat), "informationType": "RDTR"},
                headers={"Accept": "application/json", "Accept-Language": "en"},
                timeout=8.0,
            )
            if resp.status_code != 200:
                self._record_batara_failure()
                return None
            data = resp.json()
            if data.get("status") != 200:
                self._record_batara_failure()
                return None

            geom_list = data.get("data", {}).get("territorials", {}).get("geom", [])
            if not geom_list:
                self._record_batara_failure()
                return None

            self._record_batara_success()
            geom = geom_list[0]
            zone = geom.get("zone", {})
            if not zone:
                return None

            zone_code = zone.get("code", "")
            zone_name = zone.get("name", "")
            zone_color_rgb = zone.get("color", "")
            zone_definition = zone.get("definition", "")
            activities = zone.get("activities", [])

            businesses = self._extract_businesses(activities)
            hex_color = rgb_string_to_hex(zone_color_rgb) if zone_color_rgb else None

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

            reqs = zone.get("zone_intensity_requirements", [])
            req_data = reqs[0] if reqs else {}
            location_data = geom.get("location", {})

            label_info = ZONE_LABELS.get(
                zone_code,
                {"label_en": zone_name, "desc_en": zone_definition[:120] if zone_definition else ""},
            )
            building_codes = calculate_building_yield(zone_code)

            logger.info(
                "✅ [PrimeNexus/BATARA] %s '%s' @ %s,%s — %d businesses",
                zone_code, zone_name, lat, lng, len(businesses),
            )
            return {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"] or zone_definition[:120],
                "zone_color_hex": hex_color,
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "businesses": businesses,
                "business_count": len(businesses),
                "overlays": overlays,
                "building_codes": building_codes,
                "kdb": req_data.get("maximum_kdb", "N/A"),
                "klb": req_data.get("maximum_klb", "N/A"),
                "kdh": req_data.get("mininum_kdh", "N/A"),
                "tb": req_data.get("old_building_height", "N/A"),
                "gsb": req_data.get("old_minimum_gsb", "N/A"),
                "desa": location_data.get("name", "N/A"),
            }
        except Exception as exc:
            logger.warning("⚠️ [PrimeNexus] BATARA query failed (%s,%s): %s", lat, lng, exc)
            self._record_batara_failure()
            return None

    # ── GISTARU query ────────────────────────────────────────────────
    async def _query_gistaru(self, lat: float, lng: float) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            cities_resp = await client.get(
                f"{GISTARU_RDTR_API}/cities/51", headers=GISTARU_HEADERS, timeout=30.0,
            )
            cities_resp.raise_for_status()
            cities_body = cities_resp.json()
            cities = cities_body.get("data", cities_body) if isinstance(cities_body, dict) else cities_body

            for city in cities:
                city_id = city.get("id")
                if not city_id:
                    continue
                rdtr_resp = await client.get(
                    f"{GISTARU_RDTR_API}/rdtr/{city_id}", headers=GISTARU_HEADERS,
                )
                if rdtr_resp.status_code != 200:
                    continue
                rdtr_body = rdtr_resp.json()
                rdtr_list = rdtr_body.get("data", rdtr_body) if isinstance(rdtr_body, dict) else rdtr_body
                if not isinstance(rdtr_list, list):
                    continue

                for rdtr in rdtr_list:
                    mapserver_path = rdtr.get("url_mapserver", "")
                    if not mapserver_path:
                        continue
                    qs = urlencode({
                        "geometry": f"{lng},{lat}",
                        "geometryType": "esriGeometryPoint",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "*", "returnGeometry": "false", "f": "json",
                    })
                    arcgis_base = "https://gistaru.atrbpn.go.id/arcgis/rest/services"
                    proxied = f"{GISTARU_PROXY}{arcgis_base}/{mapserver_path}/0/query?{qs}"
                    try:
                        qr = await client.get(proxied, headers=GISTARU_HEADERS, timeout=10)
                    except httpx.TimeoutException:
                        continue
                    if qr.status_code != 200:
                        continue
                    features = qr.json().get("features", [])
                    if not features:
                        continue

                    self._record_gistaru_success()
                    attrs = features[0].get("attributes", {})
                    city_name = city.get("kota_atau_kabupaten", "")
                    return {
                        "source": "gistaru_rdtr",
                        "code": attrs.get("KODZON", attrs.get("KODSZN", "N/A")),
                        "sub_zone": attrs.get("KODSZN", ""),
                        "name": attrs.get("NAMZON", attrs.get("NAMOBJ", "N/A")),
                        "sub_name": attrs.get("NAMSZN", ""),
                        "desa": attrs.get("WADMKD", "N/A"),
                        "kecamatan": attrs.get("WADMKC", ""),
                        "kabupaten": attrs.get("WADMKK", "") or city_name,
                        "kdb": "N/A", "klb": "N/A", "kdh": "N/A", "tb": "N/A", "gsb": "N/A",
                        "overlays": {
                            k: attrs.get(k)
                            for k in ("KKOP_1", "LP2B_2", "KRB_03", "TEB_05", "CAGBUD", "RESAIR", "SEMPDN", "HANKAM")
                            if attrs.get(k) and attrs.get(k) != "Tidak Ada"
                        },
                    }
        except Exception as exc:
            logger.warning("⚠️ [PrimeNexus] GISTARU query failed: %s", exc)
            self._record_gistaru_failure()
        return None

    # ── PostGIS query ────────────────────────────────────────────────
    async def _query_postgis(self, lat: float, lng: float) -> asyncpg.Record | None:
        pool = self._db_pool
        if not pool:
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return None
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    return await conn.fetchrow(
                        "SELECT district_name, subdistrict_name, zoning_type, allowed_kbli, "
                        "avg_price_per_are, risk_score FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                finally:
                    await conn.close()
            except Exception as exc:
                logger.warning("[PrimeNexus] PostGIS fallback failed: %s", exc)
                return None
        else:
            try:
                async with pool.acquire() as conn:
                    return await conn.fetchrow(
                        "SELECT district_name, subdistrict_name, zoning_type, allowed_kbli, "
                        "avg_price_per_are, risk_score FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
            except Exception as exc:
                logger.warning("[PrimeNexus] PostGIS pool query failed: %s", exc)
                return None

    # ── Price query ──────────────────────────────────────────────────
    async def query_price(self, lat: float, lng: float) -> float | None:
        """Lightweight PostGIS lookup for avg_price_per_are."""
        pool = self._db_pool
        if not pool:
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return None
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    row = await conn.fetchrow(
                        "SELECT avg_price_per_are FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                finally:
                    await conn.close()
                if row and row["avg_price_per_are"]:
                    return float(row["avg_price_per_are"])
            except Exception as exc:
                logger.debug("[PrimeNexus] Price lookup skipped: %s", exc)
        else:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT avg_price_per_are FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                    if row and row["avg_price_per_are"]:
                        return float(row["avg_price_per_are"])
            except Exception as exc:
                logger.debug("[PrimeNexus] Price lookup skipped: %s", exc)
        return None

    # ── Business extraction ──────────────────────────────────────────
    def _extract_businesses(self, activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority_cats = {"Hospitality", "F&B", "Wellness", "Creative"}
        first_pass: list[dict[str, Any]] = []
        second_pass: list[dict[str, Any]] = []
        seen_categories: dict[str, int] = {}

        for act in activities:
            pivot = act.get("pivot", {})
            if not pivot.get("i", False):
                continue
            name = act.get("name", "")
            if not name or not is_investor_relevant(name):
                continue
            category = classify_activity(name)
            if category == "Other":
                continue
            entry = {"title_en": name, "category_en": category, "pma_open": True}
            if category in priority_cats:
                first_pass.append(entry)
            else:
                second_pass.append(entry)

        merged: list[dict[str, Any]] = []
        for entry in first_pass + second_pass:
            cat = entry["category_en"]
            if seen_categories.get(cat, 0) >= 2:
                continue
            seen_categories[cat] = seen_categories.get(cat, 0) + 1
            merged.append(entry)
        return merged[:10]

    # ── Response builders ────────────────────────────────────────────
    def _build_resolve_response(
        self, lat: float, lng: float, batara: dict[str, Any], source: str, confidence: float,
    ) -> dict[str, Any]:
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": batara["zone_code"],
                "zone_name": batara["zone_name"],
                "zone_label_en": batara["zone_label_en"],
                "zone_description_en": batara["zone_description_en"],
                "zone_color_hex": batara.get("zone_color_hex"),
                "is_restricted": batara.get("is_restricted", False),
                "allowed_activities": [b["title_en"] for b in batara.get("businesses", [])],
                "restrictions": [],
                "overlays": batara.get("overlays", {}),
                "building_codes": batara.get("building_codes"),
                "source": source,
                "confidence": confidence,
            },
            "cache_hit": False,
            # Backward compat fields (flat, for prime.py wrapper)
            **{k: batara.get(k) for k in (
                "zone_code", "zone_name", "zone_label_en", "zone_description_en",
                "zone_color_hex", "is_restricted", "businesses", "business_count",
                "overlays", "building_codes", "kdb", "klb", "kdh", "tb", "gsb", "desa",
            )},
            "source": "BATARA/Badung DPUPR (official)",
        }

    def _build_resolve_response_from_gistaru(
        self, lat: float, lng: float, gistaru: dict[str, Any],
    ) -> dict[str, Any]:
        zone_code = gistaru.get("code", "N/A")
        label_info = ZONE_LABELS.get(
            zone_code, {"label_en": gistaru.get("name", ""), "desc_en": ""},
        )
        building_codes = calculate_building_yield(zone_code)
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": zone_code,
                "zone_name": gistaru.get("name", ""),
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"],
                "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "allowed_activities": [],
                "restrictions": [],
                "overlays": gistaru.get("overlays", {}),
                "building_codes": building_codes,
                "source": "gistaru_rdtr",
                "confidence": 0.7,
            },
            "cache_hit": False,
            # Backward compat
            "zone_code": zone_code,
            "zone_name": gistaru.get("name", ""),
            "zone_label_en": label_info["label_en"],
            "zone_description_en": label_info["desc_en"],
            "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
            "is_restricted": zone_code in RESTRICTED_ZONES,
            "businesses": [],
            "business_count": 0,
            "overlays": gistaru.get("overlays", {}),
            "building_codes": building_codes,
            "district": gistaru.get("kabupaten", ""),
            "subdistrict": gistaru.get("desa", ""),
            "source": "GISTARU/ATR-BPN (fallback)",
        }

    def _build_resolve_response_from_postgis(
        self, lat: float, lng: float, row: asyncpg.Record,
    ) -> dict[str, Any]:
        zone_type: str = row["zoning_type"]
        zone_code = zone_type.split(":")[0].strip()
        zone_name = zone_type.split(":", 1)[1].strip() if ":" in zone_type else zone_type
        label_info = ZONE_LABELS.get(
            zone_code, {"label_en": zone_name, "desc_en": "Contact local authorities for details"},
        )
        building_codes = calculate_building_yield(zone_code)
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"],
                "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "allowed_activities": [],
                "restrictions": [],
                "overlays": {},
                "building_codes": building_codes,
                "source": "postgis_cache",
                "confidence": 0.5,
            },
            "cache_hit": False,
            # Backward compat
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_label_en": label_info["label_en"],
            "zone_description_en": label_info["desc_en"],
            "zone_color_hex": None,
            "zone_type": zone_type,
            "is_restricted": zone_code in RESTRICTED_ZONES,
            "businesses": [],
            "business_count": 0,
            "overlays": {},
            "building_codes": building_codes,
            "avg_price_per_are": float(row["avg_price_per_are"] or 0),
            "risk_score": float(row["risk_score"] or 0),
            "district": row["district_name"],
            "subdistrict": row["subdistrict_name"],
            "source": "PostGIS/GISTARU (local cache)",
        }

    # ── Layer 2: Investment Analysis ────────────────────────────────
    async def analyze(
        self,
        lat: float,
        lng: float,
        kbli_code: str | None = None,
        is_pma: bool = True,
        land_size_m2: float | None = None,
        price_idr: float | None = None,
        investor_profile: dict[str, Any] | None = None,
        geo_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Full investment analysis: resolve zone → KBLIEye → scoring → intel.
        Target: < 3s.
        """
        # Check analyze cache
        gh6 = encode_geohash(lat, lng, precision=6)
        cache_key = f"prime:analyze:{gh6}:{kbli_code or 'none'}:{is_pma}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    result = cached if isinstance(cached, dict) else json.loads(cached)
                    result["cache_hit"] = True
                    return result
            except Exception:
                pass

        # Step 1: Resolve zone
        resolve_result = await self.resolve(lat, lng)
        zone_data: dict[str, Any] | None = None
        zone_code: str | None = None

        if resolve_result.get("status") == "found":
            zone = resolve_result.get("zone", {})
            zone_code = resolve_result.get("zone_code") or (zone.get("zone_code") if zone else None)
            source = resolve_result.get("source", "")
            zone_source = zone.get("source", source) if zone else source

            zone_data = {
                "code": zone_code,
                "name": resolve_result.get("zone_name", ""),
                "source": zone_source,
                "desa": resolve_result.get("desa", resolve_result.get("subdistrict", "")),
                "kecamatan": resolve_result.get("district", ""),
                "kdb": resolve_result.get("kdb", "N/A"),
                "klb": resolve_result.get("klb", "N/A"),
                "kdh": resolve_result.get("kdh", "N/A"),
                "tb": resolve_result.get("tb", "N/A"),
                "gsb": resolve_result.get("gsb", "N/A"),
                "overlays": resolve_result.get("overlays", {}),
            }

        # Step 2: KBLIEye compliance (if kbli_code provided)
        kbli_result: dict[str, Any] | None = None
        kbli_state: str | None = None
        kbli_oss_risk: str | None = None

        if kbli_code:
            try:
                eye = self._get_kbli_eye()
                kd = eye.get_decision(code=kbli_code, is_pma=is_pma, location="Bali")
                audit = kd.get("audit", kd)
                kbli_state = audit.get("state", kd.get("state", "UNKNOWN"))
                kbli_oss_risk = audit.get("oss_risk") or None
                pma_logic = kd.get("pma_logic", {})
                kbli_result = {
                    "code": kd.get("kbli_2025", kbli_code),
                    "title": kd.get("title", ""),
                    "state": kbli_state,
                    "reason": audit.get("reason_code", ""),
                    "oss_risk": audit.get("oss_risk", ""),
                    "max_foreign_ownership": pma_logic.get("max_foreign_ownership", 0),
                }
            except Exception as e:
                kbli_result = {"code": kbli_code, "state": "ERROR", "error": str(e)}
                logger.warning("[PrimeNexus] KBLIEye failed: %s", e)

        # Step 3: ROI calculation (if land/price provided)
        roi_data: dict[str, Any] | None = None
        if zone_code and land_size_m2 and price_idr:
            roi_url = os.environ.get("ROI_CALCULATOR_URL", "http://localhost:8001/calculator")
            try:
                client = await self._get_client()
                roi_resp = await client.post(roi_url, json={
                    "land_size_m2": land_size_m2,
                    "price_total_idr": price_idr,
                    "zone_code": zone_code,
                }, timeout=10.0)
                roi_resp.raise_for_status()
                rd = roi_resp.json()
                roi_data = {
                    "golden_strategy": rd.get("golden_strategy", {}),
                    "urbanistica": rd.get("urbanistica", {}),
                    "total_investment_idr": rd.get("total_investment_idr"),
                }
            except Exception as e:
                roi_data = {"error": str(e)}

        # Step 4: Scoring engine
        scoring = calculate_investment_score(
            zone_data=zone_data,
            kbli_state=kbli_state,
            kbli_code=kbli_code,
            roi_data=roi_data,
            geo_data=geo_data,
            oss_risk=kbli_oss_risk,
        )

        # Step 5: Intel articles (best-effort)
        intel_articles: list[dict[str, Any]] = []
        if zone_code:
            subdistrict = zone_data.get("desa", "Bali") if zone_data else "Bali"
            intel_articles = await self._search_intel(zone_code, subdistrict)

        # Build verdict
        verdict_label = scoring["verdict"]
        risk_map = {"GREEN": "LOW", "YELLOW": "MEDIUM", "RED": "HIGH"}

        result: dict[str, Any] = {
            "status": "analyzed",
            "coordinates": {"lat": lat, "lng": lng},
            "zone": zone_data,
            "kbli": kbli_result,
            "roi": roi_data,
            "verdict": {
                "can_invest": scoring["can_invest"],
                "risk_level": risk_map.get(verdict_label, "UNKNOWN"),
                "score": scoring["score"],
                "label": verdict_label,
                "breakdown": scoring["breakdown"],
                "modifiers": scoring["modifiers"],
                "hard_blocks": scoring["hard_blocks"],
            },
            "opportunities": resolve_result.get("businesses", []),
            "intel_articles": intel_articles,
            "cache_hit": False,
        }

        # Cache result
        if self._cache:
            try:
                cache_data = {k: v for k, v in result.items() if k != "cache_hit"}
                await self._cache.set(cache_key, json.dumps(cache_data, default=str), ttl=14400)
            except Exception:
                pass

        logger.info(
            "[PrimeNexus] analyze: verdict=%s score=%d zone=%s kbli=%s",
            verdict_label, scoring["score"], zone_code, kbli_code,
        )
        return result

    # ── Intel search (Qdrant balizero_news) ──────────────────────────
    async def _search_intel(
        self, zone_code: str, subdistrict: str, limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Semantic search for investment-relevant articles near the zone."""
        try:
            qdrant_url = os.environ.get("QDRANT_URL", "")
            qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")
            if not qdrant_url:
                return []

            from backend.core.embeddings import create_embeddings_generator

            query_text = f"Bali {subdistrict} zone {zone_code} investment regulation property news"
            embedder = create_embeddings_generator(api_key=os.environ.get("OPENAI_API_KEY"))
            embedding = await embedder.generate_single_embedding(query_text)

            search_url = f"{qdrant_url.rstrip('/')}/collections/balizero_news/points/search"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if qdrant_api_key:
                headers["api-key"] = qdrant_api_key

            client = await self._get_client()
            resp = await client.post(
                search_url,
                json={"vector": embedding, "limit": limit * 2, "with_payload": True},
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()

            articles: list[dict[str, Any]] = []
            for hit in data.get("result", []):
                score = hit.get("score", 0.0)
                if score < 0.45:
                    continue
                payload = hit.get("payload", {})
                title = payload.get("title", "")
                source_url = payload.get("source_url", "")
                if not title or not source_url:
                    continue
                articles.append({
                    "title": title,
                    "source_url": source_url,
                    "category": payload.get("category", ""),
                    "source_name": payload.get("source_name", ""),
                    "published_at": payload.get("published_at", ""),
                    "relevance_score": round(score, 3),
                })
                if len(articles) >= limit:
                    break
            return articles
        except Exception as exc:
            logger.debug("[PrimeNexus] Intel search skipped: %s", exc)
            return []

    # ── Layer 3: CRM Intelligence Overlay ───────────────────────────
    async def intelligence(
        self,
        sw_lat: float, sw_lng: float,
        ne_lat: float, ne_lng: float,
        include_clients: bool = True,
        include_companies: bool = True,
        include_practices: bool = True,
        max_features: int = 2000,
    ) -> dict[str, Any]:
        """
        Query geocoded entities within a bounding box for CRM/INTEL overlay.
        Returns GeoJSON FeatureCollection with client/company/practice markers.
        Target: < 3s. Requires auth (called from CRM/INTEL modes).
        """
        features: list[dict[str, Any]] = []
        stats: dict[str, int] = {"clients": 0, "companies": 0, "practices": 0}

        pool = self._db_pool
        if not pool:
            # No pool injected — fallback to single connection (no leak)
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return {"type": "FeatureCollection", "features": [], "stats": stats}
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    return await self._intelligence_query(conn, sw_lat, sw_lng, ne_lat, ne_lng,
                                                          include_clients, include_companies, max_features, features, stats)
                finally:
                    await conn.close()
            except Exception as exc:
                logger.warning("[PrimeNexus] Intelligence fallback failed: %s", exc)
                return {"type": "FeatureCollection", "features": [], "stats": stats}

        try:
            async with pool.acquire() as conn:
                return await self._intelligence_query(
                    conn, sw_lat, sw_lng, ne_lat, ne_lng,
                    include_clients, include_companies, max_features, features, stats,
                )
        except Exception as exc:
            logger.warning("[PrimeNexus] Intelligence query failed: %s", exc)

        return {"type": "FeatureCollection", "features": [], "stats": stats}

    async def _intelligence_query(
        self,
        conn: asyncpg.Connection,
        sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
        include_clients: bool, include_companies: bool,
        max_features: int,
        features: list[dict[str, Any]], stats: dict[str, int],
    ) -> dict[str, Any]:
        """Execute intelligence queries against a connection."""
        if include_companies and len(features) < max_features:
            rows = await conn.fetch("""
                SELECT c.id, c.company_name, c.company_type, c.kbli_code,
                       c.status, c.rdtr_zone_code,
                       ST_Y(c.geo_point) as lat, ST_X(c.geo_point) as lng
                FROM companies c
                WHERE c.geo_point IS NOT NULL
                  AND ST_Contains(ST_MakeEnvelope($1, $2, $3, $4, 4326), c.geo_point)
                LIMIT $5
            """, sw_lng, sw_lat, ne_lng, ne_lat, max_features - len(features))
            for row in rows:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                    "properties": {
                        "entity_type": "company", "entity_id": row["id"],
                        "name": row["company_name"], "company_type": row["company_type"],
                        "kbli_code": row["kbli_code"], "status": row["status"],
                        "zone_code": row["rdtr_zone_code"],
                    },
                })
            stats["companies"] = len(rows)

        if include_clients and len(features) < max_features:
            rows = await conn.fetch("""
                SELECT c.id, c.full_name, c.status, c.nationality, c.rdtr_zone_code,
                       ST_Y(c.geo_point) as lat, ST_X(c.geo_point) as lng
                FROM clients c
                WHERE c.geo_point IS NOT NULL AND c.status = 'active'
                  AND ST_Contains(ST_MakeEnvelope($1, $2, $3, $4, 4326), c.geo_point)
                LIMIT $5
            """, sw_lng, sw_lat, ne_lng, ne_lat, max_features - len(features))
            for row in rows:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                    "properties": {
                        "entity_type": "client", "entity_id": row["id"],
                        "name": row["full_name"], "status": row["status"],
                        "nationality": row["nationality"], "zone_code": row["rdtr_zone_code"],
                    },
                })
            stats["clients"] = len(rows)

        return {"type": "FeatureCollection", "features": features[:max_features], "stats": stats}

    # ── Layer 4: Competitor Density ─────────────────────────────────

    # Saturation thresholds per zone-type prefix
    _SATURATION_THRESHOLDS: dict[str, int] = {
        "K": 100, "W": 50, "C": 80, "R": 20, "SPU": 60, "KT": 50,
    }

    # 2-digit KBLI sector labels
    _KBLI_2DIGIT_LABELS: dict[str, str] = {
        "10": "Food Manufacturing", "11": "Beverages", "41": "Construction",
        "46": "Wholesale Trade", "47": "Retail Trade", "49": "Transport",
        "55": "Accommodation", "56": "F&B Services", "58": "Publishing",
        "62": "Software/IT", "63": "Information Services", "68": "Real Estate",
        "70": "Management Consulting", "71": "Architecture/Engineering",
        "72": "Scientific R&D", "73": "Advertising/Marketing",
        "74": "Professional Services", "79": "Travel Agencies",
        "82": "Business Support", "85": "Education", "86": "Health Services",
        "90": "Creative/Arts", "93": "Sports/Recreation", "96": "Personal Services",
    }

    async def density(self, zone_code: str) -> dict[str, Any]:
        """Layer 4: Business density and competitor saturation for a zone."""
        cache_key = f"prime:density:{zone_code}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        by_kbli: dict[str, int] = {}
        total = 0

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT LEFT(kbli_code, 2) AS sector, COUNT(*) AS cnt
                        FROM companies
                        WHERE rdtr_zone_code = $1
                          AND kbli_code IS NOT NULL
                          AND kbli_code != ''
                        GROUP BY LEFT(kbli_code, 2)
                        ORDER BY cnt DESC
                        """,
                        zone_code,
                    )
                    for row in rows:
                        sector = row["sector"]
                        cnt = row["cnt"]
                        by_kbli[sector] = cnt
                        total += cnt
            except Exception as exc:
                logger.warning("[PrimeNexus] Density query failed: %s", exc)

        # Compute saturation index
        prefix = zone_code.split("-")[0] if "-" in zone_code else zone_code
        threshold = self._SATURATION_THRESHOLDS.get(prefix, 40)
        saturation = min(1.0, total / threshold) if threshold > 0 else 0.0
        saturation_label = "HIGH" if saturation > 0.7 else "MEDIUM" if saturation > 0.3 else "LOW"

        by_kbli_labels = {k: self._KBLI_2DIGIT_LABELS.get(k, f"Sector {k}") for k in by_kbli}

        result = {
            "zone_code": zone_code,
            "total_companies": total,
            "by_kbli": by_kbli,
            "by_kbli_labels": by_kbli_labels,
            "saturation_index": round(saturation, 2),
            "saturation_label": saturation_label,
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=21600)

        return result

    # ── Layer 5: Predictive Zone Score ─────────────────────────────

    async def predict_zone(self, zone_code: str) -> dict[str, Any]:
        """Layer 5: 3-signal trend analysis for a zone."""
        cache_key = f"prime:predict:{zone_code}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        factors: list[dict[str, Any]] = []
        trend_score = 0

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    # Signal 1: Rejection trend (6m vs prior 6m)
                    rej_rows = await conn.fetch(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE p.created_at >= NOW() - INTERVAL '6 months') AS recent,
                            COUNT(*) FILTER (WHERE p.created_at >= NOW() - INTERVAL '12 months'
                                             AND p.created_at < NOW() - INTERVAL '6 months') AS prior
                        FROM practices p
                        JOIN clients cl ON cl.id = p.client_id
                        WHERE cl.rdtr_zone_code = $1
                          AND p.status IN ('rejected', 'cancelled')
                        """,
                        zone_code,
                    )
                    if rej_rows:
                        recent_rej = rej_rows[0]["recent"] or 0
                        prior_rej = rej_rows[0]["prior"] or 0
                        if recent_rej > prior_rej + 2:
                            trend_score -= 1
                            factors.append({"signal": "rejections", "direction": "worse",
                                           "detail": f"{recent_rej} vs {prior_rej} prior period"})
                        elif recent_rej < prior_rej:
                            trend_score += 1
                            factors.append({"signal": "rejections", "direction": "better",
                                           "detail": f"{recent_rej} vs {prior_rej} prior period"})
                        else:
                            factors.append({"signal": "rejections", "direction": "stable",
                                           "detail": f"{recent_rej} recent, {prior_rej} prior"})

                    # Signal 2: Expiry density (practices expiring within 90 days)
                    exp_rows = await conn.fetch(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM practices p
                        JOIN clients cl ON cl.id = p.client_id
                        WHERE cl.rdtr_zone_code = $1
                          AND p.expiry_date IS NOT NULL
                          AND p.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
                          AND p.status NOT IN ('completed', 'archived')
                        """,
                        zone_code,
                    )
                    expiring = exp_rows[0]["cnt"] if exp_rows else 0
                    if expiring > 5:
                        trend_score -= 1
                        factors.append({"signal": "expiring_practices", "direction": "worse",
                                       "detail": f"{expiring} expiring within 90 days"})
                    else:
                        factors.append({"signal": "expiring_practices", "direction": "stable",
                                       "detail": f"{expiring} expiring within 90 days"})

                    # Signal 3: Activity momentum (new companies 3m vs prior 3m)
                    act_rows = await conn.fetch(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '3 months') AS recent,
                            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '6 months'
                                             AND created_at < NOW() - INTERVAL '3 months') AS prior
                        FROM companies
                        WHERE rdtr_zone_code = $1
                        """,
                        zone_code,
                    )
                    if act_rows:
                        recent_act = act_rows[0]["recent"] or 0
                        prior_act = act_rows[0]["prior"] or 0
                        if recent_act > prior_act + 2:
                            trend_score += 1
                            factors.append({"signal": "new_companies", "direction": "better",
                                           "detail": f"{recent_act} vs {prior_act} prior period"})
                        elif recent_act < prior_act - 2:
                            trend_score -= 1
                            factors.append({"signal": "new_companies", "direction": "worse",
                                           "detail": f"{recent_act} vs {prior_act} prior period"})
                        else:
                            factors.append({"signal": "new_companies", "direction": "stable",
                                           "detail": f"{recent_act} recent, {prior_act} prior"})
            except Exception as exc:
                logger.warning("[PrimeNexus] Predict query failed: %s", exc)

        trend = "improving" if trend_score >= 1 else "declining" if trend_score <= -1 else "stable"

        # Predict label shift
        current_label = "GREEN"  # default assumption
        predicted_label = current_label
        if trend == "declining":
            predicted_label = "YELLOW" if current_label == "GREEN" else "RED"
        elif trend == "improving":
            predicted_label = "GREEN" if current_label == "YELLOW" else current_label

        result = {
            "zone_code": zone_code,
            "trend": trend,
            "trend_score": trend_score,
            "predicted_label": predicted_label,
            "factors": factors,
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=43200)

        return result

    # ── Layer 6: Temporal Intelligence ──────────────────────────────

    _PERIOD_MAP: dict[str, str] = {
        "1m": "1 month", "3m": "3 months", "6m": "6 months", "12m": "12 months",
    }
    _GRANULARITY_MAP: dict[str, str] = {
        "daily": "day", "weekly": "week", "monthly": "month",
    }

    async def temporal(
        self, zone_code: str, period: str = "6m", granularity: str = "weekly",
    ) -> dict[str, Any]:
        """Layer 6: Temporal activity analysis for a zone."""
        cache_key = f"prime:temporal:{zone_code}:{period}:{granularity}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        interval = self._PERIOD_MAP.get(period, "6 months")
        trunc = self._GRANULARITY_MAP.get(granularity, "week")
        buckets: list[dict[str, Any]] = []

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        f"""
                        WITH practice_buckets AS (
                            SELECT date_trunc('{trunc}', p.created_at) AS bucket,
                                   COUNT(*) AS practices
                            FROM practices p
                            JOIN clients cl ON cl.id = p.client_id
                            WHERE cl.rdtr_zone_code = $1
                              AND p.created_at >= NOW() - INTERVAL '{interval}'
                            GROUP BY bucket
                        ),
                        company_buckets AS (
                            SELECT date_trunc('{trunc}', created_at) AS bucket,
                                   COUNT(*) AS companies
                            FROM companies
                            WHERE rdtr_zone_code = $1
                              AND created_at >= NOW() - INTERVAL '{interval}'
                            GROUP BY bucket
                        )
                        SELECT COALESCE(p.bucket, c.bucket) AS bucket,
                               COALESCE(p.practices, 0) AS practices,
                               COALESCE(c.companies, 0) AS companies
                        FROM practice_buckets p
                        FULL OUTER JOIN company_buckets c ON p.bucket = c.bucket
                        ORDER BY bucket
                        """,
                        zone_code,
                    )
                    for row in rows:
                        practices = row["practices"]
                        companies = row["companies"]
                        buckets.append({
                            "date": row["bucket"].isoformat()[:10] if row["bucket"] else None,
                            "practices": practices,
                            "companies": companies,
                            "activity_score": practices + companies,
                        })
            except Exception as exc:
                logger.warning("[PrimeNexus] Temporal query failed: %s", exc)

        trend = "stable"
        if len(buckets) >= 2:
            mid = len(buckets) // 2
            first_half = sum(b["activity_score"] for b in buckets[:mid])
            second_half = sum(b["activity_score"] for b in buckets[mid:])
            if second_half > first_half * 1.3:
                trend = "increasing"
            elif second_half < first_half * 0.7:
                trend = "decreasing"

        result = {
            "zone_code": zone_code,
            "period": period,
            "granularity": granularity,
            "buckets": buckets,
            "trend": trend,
            "total_activity": sum(b["activity_score"] for b in buckets),
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=3600)

        return result

    # ── Layer 7: Live Regulation Feed ────────────────────────────────

    async def regulations(self, zone_code: str, limit: int = 10) -> dict[str, Any]:
        """Layer 7: Regulation feed for a zone from news_items + Qdrant."""
        regulations: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        zone_label = ZONE_LABELS.get(zone_code, {}).get("label_en", zone_code)

        # Source 1: SQL news_items
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, title, summary, category, ai_sentiment, published_at, source_url
                        FROM news_items
                        WHERE status = 'approved'
                          AND category IN ('immigration', 'business', 'tax', 'property', 'legal')
                          AND (
                            title ILIKE '%' || $1 || '%'
                            OR summary ILIKE '%' || $1 || '%'
                            OR title ILIKE '%' || $2 || '%'
                            OR summary ILIKE '%' || $2 || '%'
                          )
                        ORDER BY published_at DESC NULLS LAST
                        LIMIT $3
                        """,
                        zone_code, zone_label, limit,
                    )
                    for row in rows:
                        title = row["title"] or ""
                        norm = title.lower().strip()
                        if norm in seen_titles:
                            continue
                        seen_titles.add(norm)
                        regulations.append({
                            "title": title,
                            "summary": (row["summary"] or "")[:200],
                            "category": row["category"] or "",
                            "sentiment": row["ai_sentiment"] or "neutral",
                            "published_at": row["published_at"].isoformat() if row["published_at"] else "",
                            "source_url": row["source_url"] or "",
                            "source": "database",
                        })
            except Exception as exc:
                logger.warning("[PrimeNexus] Regulations SQL query failed: %s", exc)

        # Source 2: Qdrant semantic search (reuse _search_intel)
        try:
            qdrant_articles = await self._search_intel(zone_code, zone_label, limit=limit)
            for art in qdrant_articles:
                norm = art.get("title", "").lower().strip()
                if norm in seen_titles:
                    continue
                seen_titles.add(norm)
                regulations.append({
                    "title": art.get("title", ""),
                    "summary": "",
                    "category": art.get("category", ""),
                    "sentiment": "neutral",
                    "published_at": art.get("published_at", ""),
                    "source_url": art.get("source_url", ""),
                    "source": "qdrant",
                })
        except Exception as exc:
            logger.debug("[PrimeNexus] Regulations Qdrant failed: %s", exc)

        # Sort by published_at desc, cap at limit
        regulations.sort(key=lambda r: r.get("published_at", ""), reverse=True)
        regulations = regulations[:limit]

        return {
            "zone_code": zone_code,
            "regulations": regulations,
            "total_found": len(regulations),
        }

    # ── Layer 8: Proposals (Deal Flow) ─────────────────────────────

    async def create_proposal(
        self,
        lat: float,
        lng: float,
        zone_code: str,
        zone_name: str | None = None,
        kbli_code: str | None = None,
        verdict_label: str | None = None,
        verdict_score: int | None = None,
        analysis_snapshot: dict[str, Any] | None = None,
        investor_name: str | None = None,
        investor_email: str | None = None,
        investor_nationality: str | None = None,
    ) -> dict[str, Any]:
        """Create a shareable investment proposal."""
        import secrets
        token = secrets.token_urlsafe(32)

        if not self._db_pool:
            return {"error": "Database unavailable", "token": None}

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO prime_proposals (
                        token, lat, lng, zone_code, zone_name, kbli_code,
                        verdict_label, verdict_score, analysis_snapshot,
                        investor_name, investor_email, investor_nationality
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    RETURNING id, token, created_at, expires_at
                    """,
                    token, lat, lng, zone_code, zone_name, kbli_code,
                    verdict_label, verdict_score,
                    json.dumps(analysis_snapshot or {}, default=str),
                    investor_name, investor_email, investor_nationality,
                )
                return {
                    "id": row["id"],
                    "token": row["token"],
                    "created_at": row["created_at"].isoformat(),
                    "expires_at": row["expires_at"].isoformat(),
                    "status": "draft",
                }
        except Exception as exc:
            logger.error("[PrimeNexus] Create proposal failed: %s", exc)
            return {"error": str(exc), "token": None}

    async def get_proposal(self, token: str) -> dict[str, Any] | None:
        """Retrieve a proposal by token (public access)."""
        if not self._db_pool:
            return None

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, token, lat, lng, zone_code, zone_name, kbli_code,
                           verdict_label, verdict_score, analysis_snapshot, pricing_snapshot,
                           investor_name, investor_email, investor_nationality,
                           status, created_at, expires_at, viewed_at
                    FROM prime_proposals
                    WHERE token = $1
                    """,
                    token,
                )
                if not row:
                    return None

                # Check expiry
                from datetime import datetime, timezone
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return {"error": "expired", "expired_at": row["expires_at"].isoformat()}

                # Mark as viewed on first access
                if not row["viewed_at"]:
                    await conn.execute(
                        "UPDATE prime_proposals SET viewed_at = NOW(), status = 'viewed' WHERE id = $1",
                        row["id"],
                    )

                analysis = row["analysis_snapshot"]
                if isinstance(analysis, str):
                    analysis = json.loads(analysis)

                return {
                    "id": row["id"],
                    "token": row["token"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "zone_code": row["zone_code"],
                    "zone_name": row["zone_name"],
                    "kbli_code": row["kbli_code"],
                    "verdict_label": row["verdict_label"],
                    "verdict_score": row["verdict_score"],
                    "analysis": analysis,
                    "investor_name": row["investor_name"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                }
        except Exception as exc:
            logger.error("[PrimeNexus] Get proposal failed: %s", exc)
            return None

    # ── Layer 9: Portfolio Advisor ──────────────────────────────────

    async def portfolio(self, client_id: int) -> dict[str, Any]:
        """Layer 9: Aggregate portfolio view with health scoring and risk concentration."""
        entities: list[dict[str, Any]] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        if not self._db_pool:
            return {"client_id": client_id, "entities": [], "risk_concentration": {},
                    "suggestions": [], "overall_health": 0.0}

        try:
            async with self._db_pool.acquire() as conn:
                # Get companies for this client
                companies = await conn.fetch(
                    """
                    SELECT c.id, c.company_name, c.kbli_code, c.rdtr_zone_code,
                           ST_Y(c.geo_point::geometry) AS lat, ST_X(c.geo_point::geometry) AS lng,
                           c.status
                    FROM companies c
                    WHERE c.client_id = $1 AND c.geo_point IS NOT NULL
                    """,
                    client_id,
                )
                for comp in companies:
                    health = 1.0
                    issues: list[str] = []
                    zone = comp["rdtr_zone_code"]
                    if zone and zone in RESTRICTED_ZONES:
                        health -= 0.3
                        issues.append(f"Zone {zone} is restricted")
                    entities.append({
                        "type": "company", "id": comp["id"],
                        "name": comp["company_name"] or f"Company #{comp['id']}",
                        "zone_code": zone, "kbli_code": comp["kbli_code"],
                        "lat": comp["lat"], "lng": comp["lng"],
                        "status": comp["status"],
                        "health_score": round(max(0, health), 2),
                        "issues": issues,
                    })

                # Get practices with expiry
                practices = await conn.fetch(
                    """
                    SELECT p.id, p.practice_type_code, p.status, p.expiry_date,
                           p.notes
                    FROM practices p
                    WHERE p.client_id = $1 AND p.status NOT IN ('archived', 'completed')
                    ORDER BY p.expiry_date ASC NULLS LAST
                    LIMIT 20
                    """,
                    client_id,
                )
                for prac in practices:
                    days_until_expiry = None
                    health = 1.0
                    issues_p: list[str] = []
                    if prac["expiry_date"]:
                        from datetime import date
                        delta = prac["expiry_date"] - date.today()
                        days_until_expiry = delta.days
                        if days_until_expiry < 0:
                            health -= 0.5
                            issues_p.append("Expired")
                        elif days_until_expiry < 30:
                            health -= 0.3
                            issues_p.append(f"Expires in {days_until_expiry} days")
                            suggestions.append(f"Renew {prac['practice_type_code']} (expires in {days_until_expiry}d)")
                        elif days_until_expiry < 90:
                            health -= 0.1
                            issues_p.append(f"Expires in {days_until_expiry} days")
                    entities.append({
                        "type": "practice", "id": prac["id"],
                        "name": prac["practice_type_code"] or f"Practice #{prac['id']}",
                        "status": prac["status"],
                        "expiry_date": prac["expiry_date"].isoformat() if prac["expiry_date"] else None,
                        "days_until_expiry": days_until_expiry,
                        "health_score": round(max(0, health), 2),
                        "issues": issues_p,
                    })

        except Exception as exc:
            logger.warning("[PrimeNexus] Portfolio query failed: %s", exc)

        # Risk concentration
        from collections import Counter
        zone_counts = Counter(e.get("zone_code") for e in entities if e.get("zone_code"))
        kbli_counts = Counter(
            (e.get("kbli_code") or "")[:2] for e in entities
            if e.get("kbli_code") and e["type"] == "company"
        )

        zone_total = sum(zone_counts.values()) or 1
        zone_concentration = {z: round(c / zone_total, 2) for z, c in zone_counts.most_common(5)}
        kbli_total = sum(kbli_counts.values()) or 1
        kbli_concentration = {k: round(c / kbli_total, 2) for k, c in kbli_counts.most_common(5)}

        for zone, pct in zone_concentration.items():
            if pct > 0.8:
                warnings.append(f"{int(pct * 100)}% of companies in zone {zone} — consider diversifying")

        # Overall health
        health_scores = [e.get("health_score", 0.5) for e in entities]
        overall = round(sum(health_scores) / len(health_scores), 2) if health_scores else 0.0

        return {
            "client_id": client_id,
            "entities": entities,
            "risk_concentration": {
                "by_zone": zone_concentration,
                "by_kbli": kbli_concentration,
                "warnings": warnings,
            },
            "suggestions": suggestions,
            "overall_health": overall,
        }

    # ── Cache write ──────────────────────────────────────────────────
    async def _cache_zone(self, key: str, data: dict[str, Any]) -> None:
        if not self._cache:
            return
        try:
            cache_data = {k: v for k, v in data.items() if k != "cache_hit"}
            await self._cache.set(key, json.dumps(cache_data, default=str), ttl=86400)
        except Exception as exc:
            logger.debug("[PrimeNexus] Cache set failed: %s", exc)
