"""Prime Nexus — Geo primitives (geohash, zone labels/colors, building codes)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

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
except (OSError, json.JSONDecodeError) as _e:
    _BUILDING_CODES = {}
    logger.warning("⚠️ [PrimeNexus] Could not load building codes: %s", _e)
except Exception as _e:
    _BUILDING_CODES = {}
    logger.exception("⚠️ [PrimeNexus] Unexpected error loading building codes")


def parse_tb_to_meters(tb_str: str | None) -> float | None:
    """Parse TB height strings like '15 Meter', '4 Meter', '8m' → float meters."""
    if not tb_str or tb_str.strip().upper() == "N/A":
        return None
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
    except (ValueError, TypeError, AttributeError) as exc:
        logger.warning("⚠️ [PrimeNexus] Building codes parse error for %s: %s", zone_code, exc)
        return None
    except Exception:
        logger.exception("⚠️ [PrimeNexus] Unexpected error parsing building codes for %s", zone_code)
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
# ZONE-KBLI COMPATIBILITY — non-buildable set (shared with property_service)
# =============================================================================
NON_BUILDABLE_ZONES: set[str] = {
    "BA", "BJ", "SS", "SP", "LS", "P-1", "P-2",
    "RTH-1", "RTH-2", "RTH-4", "RTH-7", "RTNH",
    "PL-1", "PL-3", "PL-4",
}


def rgb_string_to_hex(rgb_str: str) -> str:
    """Convert '250 211 140' → '#fad38c'."""
    try:
        parts = [int(x) for x in rgb_str.replace(",", " ").split()]
        if len(parts) == 3:
            return "#{:02x}{:02x}{:02x}".format(*parts)
    except (ValueError, AttributeError):
        pass
    return "#6B7280"


def _zone_matches_prefix(zone_code: str, prefixes: set[str]) -> bool:
    return any(zone_code.startswith(p) for p in prefixes)
