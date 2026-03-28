"""
Dashboard Router - KBLI-Zoning Integration for Streamlit dashboard.

Provides 6 endpoints for property validation, client geo data,
risk zones, analytics logging, aggregate stats, and unified investment analysis.
"""

import contextlib
import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.kbli_eye import KBLIEye

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard/map", tags=["dashboard"])

# Singleton KBLIEye instance (CPU-only, deterministic — no async needed)
_kbli_eye: KBLIEye | None = None


def _get_kbli_eye() -> KBLIEye:
    global _kbli_eye
    if _kbli_eye is None:
        _kbli_eye = KBLIEye()
        logger.info("KBLIEye singleton initialized for dashboard")
    return _kbli_eye


# ── Request Models ────────────────────────────────────────────────────


class ValidatePropertyRequest(BaseModel):
    kbli_code: str
    is_pma: bool = True
    location: str = "Bali"
    skala: str | None = None


class LogLookupRequest(BaseModel):
    user_email: str
    property_code: str | None = None
    kbli_code: str | None = None
    location: str | None = None
    notes: str | None = None


class AnalyzeInvestmentRequest(BaseModel):
    lat: float
    lon: float
    kbli_code: str | None = None
    is_pma: bool = True
    land_size_m2: float | None = None
    price_idr: float | None = None
    # Optional geo data from Streamlit (pre-computed by frontend)
    geo_data: dict[str, Any] | None = None


# ── Investment Scoring Engine (3-Layer) ──────────────────────────────

# Zones where commercial building is essentially impossible
# BA=Bandara, BJ=Jalan, SS=Sungai, SP=Sumber Air, LS=Laut
# P-1=Perlindungan, PL-*=Perairan, RTH-*=Ruang Terbuka Hijau
NON_BUILDABLE_ZONES: set[str] = {
    "BA",
    "BJ",
    "SS",
    "SP",
    "LS",
    "P-1",
    "P-2",
    "RTH-1",
    "RTH-2",
    "RTH-4",
    "RTH-7",
    "RTNH",
    "PL-1",
    "PL-3",
    "PL-4",
}

# Zone-KBLI compatibility — maps KBLI prefix/category to ideal zone families
# Key = first 2 digits of KBLI code, Value = set of zone prefixes that are ideal
#
# 3 tiers: IDEAL (20pt) → TOLERATED (8pt) → ACCEPTABLE (12pt) → POOR (4pt)
# TOLERATED = gray zone (normativamente discutibile ma pratica comune, es. R-3 Canggu)
_ZONE_KBLI_IDEAL: dict[str, set[str]] = {
    # Accommodation (55xxx) → Tourism, Mixed (NOT residential — villa in R-3 is gray zone)
    "55": {"W-", "C-"},
    # Food & Beverage (56xxx) → Commercial, Mixed
    "56": {"K-", "C-"},
    # Retail (47xxx) → Commercial, Mixed
    "47": {"K-", "C-"},
    # Real Estate (68xxx) → Residential, Commercial, Mixed
    "68": {"R-", "K-", "C-"},
    # Offices / Consulting (70xxx) → Office, Commercial, Mixed
    "70": {"KT", "K-", "C-"},
    # IT / Software (62xxx) → Office, Commercial, Mixed
    "62": {"KT", "K-", "C-"},
    # Rental services (77xxx) → Commercial, Mixed
    "77": {"K-", "C-"},
    # Travel agencies (79xxx) → Tourism, Commercial, Mixed
    "79": {"W-", "K-", "C-"},
    # Spa / Wellness (96xxx) → Tourism, Commercial, Mixed
    "96": {"W-", "K-", "C-"},
    # Arts / Entertainment (90xxx) → Tourism, Mixed, Public Facility
    "90": {"W-", "C-", "SPU"},
    # Museums / Heritage (91xxx) → Tourism, Public Facility, Mixed
    "91": {"W-", "SPU", "C-"},
    # Education (85xxx) → Public Facility, Mixed
    "85": {"SPU", "C-"},
    # Recreation (93xxx) → Tourism, Public Facility
    "93": {"W-", "SPU", "C-"},
}

# TOLERATED = gray zone — normativamente discutibile ma pratica comune.
# Score: 8/20 (tra acceptable e poor). Segnala al cliente che serve attenzione.
# Esempio: villa (55) in R-3 a Canggu — migliaia di casi ma non è "ideale".
_ZONE_KBLI_TOLERATED: dict[str, set[str]] = {
    "55": {"R-"},  # Villa/hotel in zona residenziale (gray zone Canggu)
    "56": {"W-"},  # Restaurant in tourism zone (common but needs permit)
    "47": {"R-"},  # Retail in residential (warung/minimarket)
}

# ACCEPTABLE = non ideale ma legalmente fattibile con permessi extra.
# Score: 12/20
_ZONE_KBLI_ACCEPTABLE: dict[str, set[str]] = {
    "55": {"K-"},  # Accommodation in commercial = acceptable
    "56": {"R-"},  # Restaurant in residential = acceptable with permit
    "68": {"W-"},  # Real estate in tourism = acceptable
    "77": {"W-"},  # Rental in tourism = acceptable
    "79": {"R-"},  # Travel agency in residential = acceptable
}


def _zone_matches_prefix(zone_code: str, prefixes: set[str]) -> bool:
    """Check if zone_code starts with any of the given prefixes."""
    return any(zone_code.startswith(p) for p in prefixes)


# ── Nightlife override (5-digit codes that diverge from their 2-digit prefix) ──
# Bar (56301) and nightclub (56302) need W-/K- zones. In R- zones they cause
# noise/traffic issues and rarely get permits. Override the generic "56" logic.
_NIGHTLIFE_CODES: set[str] = {"56301", "56302"}
_NIGHTLIFE_IDEAL_ZONES: set[str] = {"K-", "W-", "C-"}
_NIGHTLIFE_PENALTY_ZONES: set[str] = {"R-"}  # Residential = poor fit for nightlife


def _calculate_zone_kbli_fit(
    zone_code: str | None,
    kbli_code: str | None,
) -> tuple[int, str]:
    """
    Zone-KBLI compatibility score (0-20) + tier label.
    20 = ideal, 12 = acceptable, 8 = tolerated (gray zone), 4 = poor, 0 = incompatible.

    Returns (score, tier) where tier is one of:
    "ideal", "acceptable", "tolerated", "poor", "incompatible", "unknown"
    """
    if not zone_code or not kbli_code:
        return 12, "unknown"  # Unknown = acceptable default

    prefix = kbli_code[:2]

    # Non-buildable zone → incompatible with any business
    if zone_code in NON_BUILDABLE_ZONES:
        return 0, "incompatible"

    # Nightlife override — bar/nightclub (56301, 56302) have stricter zone needs
    if kbli_code in _NIGHTLIFE_CODES:
        if _zone_matches_prefix(zone_code, _NIGHTLIFE_IDEAL_ZONES):
            return 20, "ideal"
        if _zone_matches_prefix(zone_code, _NIGHTLIFE_PENALTY_ZONES):
            return 2, "poor"  # Nightlife in residential = very poor fit
        return 8, "tolerated"

    # Check ideal match (20pt)
    ideal = _ZONE_KBLI_IDEAL.get(prefix)
    if ideal and _zone_matches_prefix(zone_code, ideal):
        return 20, "ideal"

    # Check acceptable match (12pt)
    acceptable = _ZONE_KBLI_ACCEPTABLE.get(prefix)
    if acceptable and _zone_matches_prefix(zone_code, acceptable):
        return 12, "acceptable"

    # Check tolerated / gray zone (8pt)
    tolerated = _ZONE_KBLI_TOLERATED.get(prefix)
    if tolerated and _zone_matches_prefix(zone_code, tolerated):
        return 8, "tolerated"

    # Unknown KBLI prefix but buildable zone → poor fit (benefit of doubt)
    return 4, "poor"


def calculate_investment_score(
    zone_data: dict[str, Any] | None,
    kbli_state: str | None,
    kbli_code: str | None,
    roi_data: dict[str, Any] | None,
    geo_data: dict[str, Any] | None,
    oss_risk: str | None = None,
) -> dict[str, Any]:
    """
    3-Layer investment scoring engine.

    Layer 1: Hard blocks (binary RED)
    Layer 2: Composite score 0-100 (GREEN ≥65, YELLOW 35-64, RED <35)
    Layer 3: Contextual modifiers
    """
    zone_code = zone_data.get("code") if zone_data else None
    overlays = zone_data.get("overlays", {}) if zone_data else {}
    zone_source = zone_data.get("source", "") if zone_data else ""

    # ── Layer 1: Hard Blocks ──────────────────────────────────────
    hard_blocks: list[str] = []

    if kbli_state == "REJECTED":
        hard_blocks.append("KBLI chiuso a PMA (Perpres 10/2021)")

    if zone_code and zone_code in NON_BUILDABLE_ZONES:
        hard_blocks.append(f"Zona {zone_code} non edificabile")

    if overlays.get("LP2B_2") or overlays.get("lp2b_2"):
        hard_blocks.append("Terreno agricolo protetto (LP2B)")

    if zone_data and zone_source == "unavailable":
        hard_blocks.append("Nessun dato zona disponibile")

    # Parse KLB to check if buildable
    klb_raw = zone_data.get("klb", "N/A") if zone_data else "N/A"
    klb_val: float | None = None
    if klb_raw and klb_raw != "N/A":
        with contextlib.suppress(ValueError, TypeError):
            klb_val = float(str(klb_raw).replace(",", "."))
    if klb_val is not None and klb_val < 0.05:
        hard_blocks.append(f"KLB {klb_raw} — costruibilità quasi nulla")

    # KKOP with very low building height = effectively unbuildable for multi-story
    if overlays.get("KKOP_1"):
        tb_raw = zone_data.get("tb", "N/A") if zone_data else "N/A"
        tb_meters: float | None = None
        with contextlib.suppress(ValueError, TypeError, IndexError):
            tb_meters = float(str(tb_raw).split()[0].replace(",", "."))
        if tb_meters is not None and tb_meters <= 4.0:
            hard_blocks.append(f"KKOP + TB {tb_raw} — altezza edificio troppo limitata")

    if hard_blocks:
        return {
            "verdict": "RED",
            "can_invest": False,
            "score": 0,
            "breakdown": {},
            "modifiers": [],
            "hard_blocks": hard_blocks,
        }

    # ── Layer 2: Composite Score (0-100) ──────────────────────────
    # Factors with None score are excluded from total and max.
    # Final score = (sum of available scores / sum of available max) * 100
    breakdown: dict[str, dict[str, Any]] = {}

    # 2a. ROI Quality (30 points)
    roi_val: float | None = None
    if roi_data and not roi_data.get("error"):
        gs = roi_data.get("golden_strategy", {})
        roi_val = gs.get("roi")

    if roi_val is not None:
        if roi_val >= 12:
            roi_score: int | None = 30
        elif roi_val >= 8:
            roi_score = 22
        elif roi_val >= 4:
            roi_score = 12
        else:
            roi_score = 0
    else:
        roi_score = None  # No data = exclude from scoring
    breakdown["roi"] = {"score": roi_score, "max": 30, "value": roi_val}

    # 2b. Zone-KBLI Compatibility (15 points, scaled from 0-20 internal)
    zone_kbli_raw, zone_kbli_tier = _calculate_zone_kbli_fit(zone_code, kbli_code)
    # Scale from 0-20 internal to 0-15 display
    zone_kbli_score: int | None = round(zone_kbli_raw * 15 / 20)
    breakdown["zone_kbli_fit"] = {
        "score": zone_kbli_score,
        "max": 15,
        "tier": zone_kbli_tier,
    }

    # 2c. Building Capacity — KLB factor (10 points)
    # KLB (Koefisien Lantai Bangunan) determines buildable m² = land × KLB.
    # Higher KLB = more floors/density = better ROI potential.
    # Only available from BATARA (not GISTARU).
    if klb_val is not None:
        if klb_val >= 2.0:
            klb_score: int | None = 10  # High density (K-1, K-3)
        elif klb_val >= 1.2:
            klb_score = 8  # Good density (R-3, W-2)
        elif klb_val >= 0.6:
            klb_score = 5  # Low density (R-4, some W-)
        elif klb_val >= 0.2:
            klb_score = 2  # Very limited
        else:
            klb_score = 0  # Near-zero (hard block catches < 0.05)
    else:
        klb_score = None  # No KLB data (GISTARU) = exclude from scoring
    breakdown["building_capacity"] = {"score": klb_score, "max": 10, "klb": klb_val}

    # 2d. Break-Even Years (15 points)
    bey_val: float | None = None
    if roi_data and not roi_data.get("error"):
        bey_val = roi_data.get("golden_strategy", {}).get("bey")

    if bey_val is not None:
        if bey_val <= 5:
            bey_score: int | None = 15
        elif bey_val <= 8:
            bey_score = 12
        elif bey_val <= 12:
            bey_score = 6
        else:
            bey_score = 0
    else:
        bey_score = None  # No data = exclude from scoring
    breakdown["break_even"] = {"score": bey_score, "max": 15, "value": bey_val}

    # 2d. Flood Risk (10 points)
    flood = geo_data.get("flood_risk") if geo_data else None
    if flood == "safe":
        flood_score = 10
    elif flood == "check":
        flood_score = 5
    elif flood == "high":
        flood_score = 0
    else:
        flood_score = 7  # Unknown = slight caution
    breakdown["flood_risk"] = {"score": flood_score, "max": 10, "value": flood}

    # 2e. Market Validation — tourism density 1km (10 points)
    density_1km = geo_data.get("densita_1km") if geo_data else None
    if density_1km is not None:
        if 30 <= density_1km <= 70:
            market_score = 10  # Active sweet spot
        elif density_1km < 30:
            market_score = 6  # Low competition
        else:
            market_score = 3  # Saturated
    else:
        market_score = 5  # Unknown
    breakdown["market"] = {"score": market_score, "max": 10, "value": density_1km}

    # 2g. Regulatory Risk — KBLI state + OSS risk category (10 points)
    # Base score from KBLI compliance state
    if kbli_state == "APPROVED":
        reg_base = 10
    elif kbli_state == "WARNING":
        reg_base = 5
    elif kbli_state is None:
        reg_base = 7  # No KBLI provided = neutral
    else:
        reg_base = 0

    # OSS risk category modifier:
    # Tinggi = AMDAL required (expensive, slow) → -3
    # Menengah Tinggi = UKL/UPL required → -2
    # Menengah Rendah = standard NIB → 0
    # Rendah = auto-approval in OSS → 0
    oss_penalty = 0
    if oss_risk == "Tinggi":
        oss_penalty = 3
    elif oss_risk == "Menengah Tinggi":
        oss_penalty = 2

    reg_score = max(0, reg_base - oss_penalty)
    breakdown["regulatory"] = {
        "score": reg_score,
        "max": 10,
        "state": kbli_state,
        "oss_risk": oss_risk,
    }

    # 2g. Amenity Access — Walk Score (5 points)
    ws = geo_data.get("walk_score") if geo_data else None
    if ws is not None:
        if ws >= 65:
            ws_score = 5
        elif ws >= 35:
            ws_score = 3
        else:
            ws_score = 1
    else:
        ws_score = 2  # Unknown
    breakdown["amenity"] = {"score": ws_score, "max": 5, "value": ws}

    # ── Normalize score: exclude None factors, scale to 0-100 ─────
    # 8 factors: ROI(30) + Zone-KBLI(15) + KLB(10) + BEY(15) + Flood(10) +
    #            Market(10) + Regulatory(10) + Amenity(5) = 105 max
    _all_scores = [
        roi_score,
        zone_kbli_score,
        klb_score,
        bey_score,
        flood_score,
        market_score,
        reg_score,
        ws_score,
    ]
    _all_maxes = [30, 15, 10, 15, 10, 10, 10, 5]

    earned = sum(s for s in _all_scores if s is not None)
    available = sum(m for s, m in zip(_all_scores, _all_maxes, strict=True) if s is not None)
    score = round(earned / available * 100) if available > 0 else 0

    # Track which factors were excluded
    _excluded = []
    if roi_score is None:
        _excluded.append("ROI")
    if klb_score is None:
        _excluded.append("KLB")
    if bey_score is None:
        _excluded.append("Break-Even")

    # ── Layer 3: Contextual Modifiers ─────────────────────────────
    modifiers: list[str] = []

    if _excluded:
        modifiers.append(f"Esclusi dal calcolo: {', '.join(_excluded)} (dati mancanti)")

    # Weighted overlay penalties (each overlay has different impact)
    _OVERLAY_PENALTIES: dict[str, tuple[int, str]] = {
        # LP2B is already a hard block in Layer 1, but partial overlap still penalizes
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
        # Cap total overlay penalty at -25 to prevent total score annihilation
        overlay_penalty_total = min(overlay_penalty_total, 25)
        score -= overlay_penalty_total

    # Gray zone warning — when KBLI-zone compatibility is "tolerated"
    # This means the activity is common in practice but normativamente discutibile.
    # Example: villa (55) in R-3 Canggu — thousands of cases, not technically "ideal".
    if zone_kbli_tier == "tolerated":
        modifiers.append(
            "⚠️ Gray zone: attività comune in questa zona ma non normativamente ideale. "
            "Verificare IMB/PBG specifico per conferma."
        )

    # W-2 villa height cap warning
    # In W-2 (tourism zone), villas are capped at 8m/2 floors while hotels
    # can build 15m/4 floors. If KBLI suggests villa (55xxx), warn about limit.
    if zone_code and zone_code.startswith("W-2") and kbli_code and kbli_code.startswith("55"):
        tb_raw = zone_data.get("tb", "N/A") if zone_data else "N/A"
        modifiers.append(
            f"⚠️ W-2: villa limitata a 8m/2 piani (hotel fino a 15m/4 piani). TB zona: {tb_raw}"
        )
        score -= 3  # Minor penalty for height limitation

    # Sea view premium
    sea_view = geo_data.get("sea_view", False) if geo_data else False
    if sea_view and score >= 55:
        score += 5
        modifiers.append("+5: potenziale premium vista mare")

    # GISTARU = incomplete data → cap at YELLOW
    gistaru_cap = False
    if zone_source == "gistaru_rdtr":
        gistaru_cap = True
        modifiers.append("CAP: dati zona da GISTARU (parametri KDB/KLB mancanti)")

    score = max(0, min(100, score))

    # ── Verdict ───────────────────────────────────────────────────
    if gistaru_cap and score >= 65:
        verdict = "YELLOW"  # Cap to YELLOW when missing zone parameters
    elif score >= 65:
        verdict = "GREEN"
    elif score >= 35:
        verdict = "YELLOW"
    else:
        verdict = "RED"

    can_invest = verdict != "RED"

    return {
        "verdict": verdict,
        "can_invest": can_invest,
        "score": score,
        "breakdown": breakdown,
        "modifiers": modifiers,
        "hard_blocks": [],
    }


# ── BATARA / ROI constants ────────────────────────────────────────────

BATARA_URL = "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point"
BATARA_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://app.batara.badungkab.go.id/",
    "Origin": "https://app.batara.badungkab.go.id",
    "User-Agent": "Mozilla/5.0",
}
ROI_CALCULATOR_URL = os.getenv("ROI_CALCULATOR_URL", "http://localhost:8001/calculator")

# ── GISTARU RDTR Interaktif (ATR/BPN national) — fallback for non-Badung ──
GISTARU_PROXY = "https://gistaru-proxy.atrbpn.go.id/proxy.ashx?"
GISTARU_RDTR_API = "https://gistaru.atrbpn.go.id/rdtrinteraktif/api/interactive"
# MapServer services per kabupaten (discovered Feb 2026)
GISTARU_MAPSERVER_BASE = "https://gistaru.atrbpn.go.id/arcgis/rest/services/060_RDTR_PROVINSI_BALI"
GISTARU_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gistaru.atrbpn.go.id/"}


# ── GISTARU fallback: spatial query via ArcGIS proxy ─────────────────


async def _gistaru_rdtr_lookup(lat: float, lon: float) -> dict[str, Any] | None:
    """
    Query GISTARU RDTR Interaktif ArcGIS MapServer for zone at given point.

    Tries all RDTR services for Bali via the proxy endpoint.
    Returns zone dict or None if no data found.
    """
    # Step 1: Get list of RDTR services for Bali
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get Bali kabupaten list (province_id=51 for Bali)
            cities_resp = await client.get(
                f"{GISTARU_RDTR_API}/cities/51",
                headers=GISTARU_HEADERS,
            )
            cities_resp.raise_for_status()
            # API wraps response in {status, message, data}
            cities_body = cities_resp.json()
            cities = (
                cities_body.get("data", cities_body)
                if isinstance(cities_body, dict)
                else cities_body
            )
            logger.info(
                "GISTARU: %d kabupaten found", len(cities) if isinstance(cities, list) else 0
            )

            # For each kabupaten, get RDTR list and try spatial query
            for city in cities:
                city_id = city.get("id")
                city_name = city.get("kota_atau_kabupaten", "")
                if not city_id:
                    continue

                rdtr_resp = await client.get(
                    f"{GISTARU_RDTR_API}/rdtr/{city_id}",
                    headers=GISTARU_HEADERS,
                )
                if rdtr_resp.status_code != 200:
                    logger.debug(
                        "GISTARU: rdtr list failed for %s (HTTP %d)",
                        city_name,
                        rdtr_resp.status_code,
                    )
                    continue

                # API wraps response in {status, message, data}
                rdtr_body = rdtr_resp.json()
                rdtr_list = (
                    rdtr_body.get("data", rdtr_body) if isinstance(rdtr_body, dict) else rdtr_body
                )
                if not isinstance(rdtr_list, list):
                    continue

                logger.debug("GISTARU: %s has %d RDTR", city_name, len(rdtr_list))
                for rdtr in rdtr_list:
                    # Field is "url_mapserver" (not "service_url")
                    # Value is relative: "060_RDTR_.../MapServer"
                    mapserver_path = rdtr.get("url_mapserver", "")
                    if not mapserver_path:
                        continue

                    # Build full ArcGIS URL from base + relative path
                    arcgis_base = "https://gistaru.atrbpn.go.id/arcgis/rest/services"
                    # Params MUST be embedded in inner URL before proxy prefix
                    # (proxy.ashx? uses everything after ? as the target URL)
                    qs = urlencode(
                        {
                            "geometry": f"{lon},{lat}",
                            "geometryType": "esriGeometryPoint",
                            "spatialRel": "esriSpatialRelIntersects",
                            "outFields": "*",
                            "returnGeometry": "false",
                            "f": "json",
                        }
                    )
                    inner_url = f"{arcgis_base}/{mapserver_path}/0/query?{qs}"
                    proxied = f"{GISTARU_PROXY}{inner_url}"
                    try:
                        qr = await client.get(
                            proxied,
                            headers=GISTARU_HEADERS,
                            timeout=10,
                        )
                    except httpx.TimeoutException:
                        logger.debug("GISTARU: timeout querying %s", rdtr.get("rtr", ""))
                        continue
                    if qr.status_code != 200:
                        logger.debug(
                            "GISTARU: query %s returned HTTP %d",
                            rdtr.get("rtr", ""),
                            qr.status_code,
                        )
                        continue

                    qdata = qr.json()
                    features = qdata.get("features", [])
                    if not features:
                        continue

                    # Found a match
                    attrs = features[0].get("attributes", {})
                    return {
                        "source": "gistaru_rdtr",
                        "code": attrs.get("KODZON", attrs.get("KODSZN", "N/A")),
                        "sub_zone": attrs.get("KODSZN", ""),
                        "name": attrs.get("NAMZON", attrs.get("NAMOBJ", "N/A")),
                        "sub_name": attrs.get("NAMSZN", ""),
                        "desa": attrs.get("WADMKD", "N/A"),
                        "kecamatan": attrs.get("WADMKC", ""),
                        "kabupaten": attrs.get("WADMKK", "") or city_name,
                        "rdtr_name": rdtr.get("rtr", ""),
                        "kdb": "N/A",  # GISTARU RDTR has no KDB/KLB
                        "klb": "N/A",
                        "kdh": "N/A",
                        "tb": "N/A",
                        "gsb": "N/A",
                        "overlays": {
                            k: attrs.get(k)
                            for k in (
                                "KKOP_1",
                                "LP2B_2",
                                "KRB_03",
                                "TEB_05",
                                "CAGBUD",
                                "RESAIR",
                                "SEMPDN",
                                "HANKAM",
                            )
                            if attrs.get(k) and attrs.get(k) != "Tidak Ada"
                        },
                    }

    except Exception as e:
        logger.warning("GISTARU RDTR lookup failed: %s", e)

    return None


async def _gistaru_rdtr_direct_query(
    lat: float, lon: float, service_path: str
) -> dict[str, Any] | None:
    """
    Direct spatial query to a known GISTARU MapServer service.
    Faster than _gistaru_rdtr_lookup since it skips service discovery.
    """
    qs = urlencode(
        {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    inner_url = f"{GISTARU_MAPSERVER_BASE}/{service_path}/MapServer/0/query?{qs}"
    proxied = f"{GISTARU_PROXY}{inner_url}"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                proxied,
                headers=GISTARU_HEADERS,
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if not features:
                return None

            attrs = features[0].get("attributes", {})
            return {
                "source": "gistaru_rdtr",
                "code": attrs.get("KODZON", attrs.get("KODSZN", "N/A")),
                "sub_zone": attrs.get("KODSZN", ""),
                "name": attrs.get("NAMZON", attrs.get("NAMOBJ", "N/A")),
                "sub_name": attrs.get("NAMSZN", ""),
                "desa": attrs.get("WADMKD", "N/A"),
                "kecamatan": attrs.get("WADMKC", ""),
                "kabupaten": attrs.get("WADMKK", ""),
                "kdb": "N/A",
                "klb": "N/A",
                "kdh": "N/A",
                "tb": "N/A",
                "gsb": "N/A",
                "overlays": {
                    k: attrs.get(k)
                    for k in (
                        "KKOP_1",
                        "LP2B_2",
                        "KRB_03",
                        "TEB_05",
                        "CAGBUD",
                        "RESAIR",
                        "SEMPDN",
                        "HANKAM",
                    )
                    if attrs.get(k) and attrs.get(k) != "Tidak Ada"
                },
            }
    except Exception as e:
        logger.warning("GISTARU direct query failed for %s: %s", service_path, e)
        return None


# ── Endpoint 1: Validate Property ─────────────────────────────────────


@router.post("/validate-property")
async def validate_property(req: ValidatePropertyRequest) -> dict[str, Any]:
    """
    KBLI compliance check for a property/business activity.
    Returns APPROVED / WARNING / REJECTED with structured audit data.
    """
    eye = _get_kbli_eye()
    result = eye.get_decision(
        code=req.kbli_code,
        is_pma=req.is_pma,
        location=req.location,
    )
    state = result.get("audit", {}).get("state", result.get("state", "UNKNOWN"))
    logger.info(
        "KBLI validation: code=%s is_pma=%s location=%s -> %s",
        req.kbli_code,
        req.is_pma,
        req.location,
        state,
    )
    return result


# ── Endpoint 1b: GISTARU Zone Lookup ─────────────────────────────────


class GistaruLookupRequest(BaseModel):
    lat: float
    lon: float


@router.post("/gistaru-zone")
async def gistaru_zone_lookup(req: GistaruLookupRequest) -> dict[str, Any]:
    """
    GISTARU RDTR zone lookup for any point in Bali.
    Fallback data source when BATARA is unavailable (non-Badung areas).
    Returns zone classification + overlay constraints (no KDB/KLB).
    """
    result = await _gistaru_rdtr_lookup(req.lat, req.lon)
    if result:
        logger.info(
            "GISTARU zone lookup: %s (%s) at %s, %s",
            result.get("code"),
            result.get("name"),
            result.get("desa"),
            result.get("kabupaten"),
        )
        return {"found": True, **result}

    logger.info("GISTARU zone lookup: no data for %s,%s", req.lat, req.lon)
    return {"found": False, "source": "gistaru_rdtr", "code": "NO_DATA"}


# ── Endpoint 2: Client Geo Data ────────────────────────────────────────


@router.get("/clients/geo")
async def get_clients_geo(request: Request) -> dict[str, Any]:
    """
    Returns active clients with address info for CRM map layer.
    Uses asyncpg pool from app state.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard clients/geo: db_pool not available")
        return {"clients": [], "error": "Database pool not available"}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, email, phone, status, address
                FROM clients
                WHERE status = 'active'
                ORDER BY full_name
                LIMIT 500
                """
            )
            clients: list[dict[str, Any]] = [
                {
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "status": row["status"],
                    "address": row["address"],
                }
                for row in rows
            ]
            logger.info("Dashboard clients/geo: returned %d clients", len(clients))
            return {"clients": clients, "total": len(clients)}
    except Exception as e:
        logger.error("Dashboard clients/geo failed: %s", e, exc_info=True)
        return {"clients": [], "error": str(e)}


# ── Endpoint 3: Risk Zones ─────────────────────────────────────────────


@router.get("/compliance/risk-zones")
async def get_risk_zones() -> dict[str, list[dict[str, Any]]]:
    """
    Static/deterministic risk zone definitions for map coloring.
    Based on KBLI PMA restrictions from PP 28/2025 and Perpres 10/2021.
    """
    return {
        "zones": [
            {
                "level": "HIGH",
                "color": "#dc3545",
                "description": "KBLI con restrizioni PMA — riservati UMKM o chiusi a investimento straniero",
                "example_kbli_codes": ["47111", "47191", "56101"],
                "criteria": "pma_status != TERBUKA (Perpres 10/2021 DNI list)",
            },
            {
                "level": "MEDIUM",
                "color": "#fd7e14",
                "description": "KBLI aperto PMA ma con warning — limiti investimento, approvazioni extra, restrizioni Bali 2026",
                "example_kbli_codes": ["55111", "56301", "68110"],
                "criteria": "Risiko Rendah/Menengah Rendah in Bali (Lettera Governatore 28 Gen 2026)",
            },
            {
                "level": "LOW",
                "color": "#198754",
                "description": "KBLI completamente aperto a PMA — nessuna restrizione speciale",
                "example_kbli_codes": ["55203", "62011", "70201"],
                "criteria": "pma_status == TERBUKA, no location-specific restrictions",
            },
        ]
    }


# ── Endpoint 4: Log Analytics Lookup ───────────────────────────────────


@router.post("/analytics/log-lookup")
async def log_lookup(req: LogLookupRequest, request: Request) -> dict[str, Any]:
    """
    Log a map lookup event for analytics tracking.
    Creates the analytics table on first use (idempotent).
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard analytics/log: db_pool not available")
        return {"logged": False, "error": "Database pool not available"}

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_map_lookups (
                    id SERIAL PRIMARY KEY,
                    user_email TEXT,
                    property_code TEXT,
                    kbli_code TEXT,
                    location TEXT,
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO analytics_map_lookups
                    (user_email, property_code, kbli_code, location, notes)
                VALUES ($1, $2, $3, $4, $5)
                """,
                req.user_email,
                req.property_code,
                req.kbli_code,
                req.location,
                req.notes,
            )
            logger.info(
                "Dashboard analytics logged: user=%s kbli=%s",
                req.user_email,
                req.kbli_code,
            )
            return {"logged": True}
    except Exception as e:
        logger.error("Dashboard analytics/log failed: %s", e, exc_info=True)
        return {"logged": False, "error": str(e)}


# ── Endpoint 5: Aggregate Stats ────────────────────────────────────────


@router.get("/stats")
async def get_stats(request: Request) -> dict[str, Any]:
    """Aggregate stats for the sidebar dashboard widgets."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard stats: db_pool not available")
        return {
            "total_clients": 0,
            "total_practices": 0,
            "map_lookups_24h": 0,
            "error": "Database pool not available",
        }

    try:
        async with pool.acquire() as conn:
            total_clients: int = (
                await conn.fetchval("SELECT COUNT(*) FROM clients WHERE status = 'active'") or 0
            )

            total_practices: int = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM practices
                WHERE status NOT IN ('cancelled', 'archived')
                """
                )
                or 0
            )

            # Map lookups in last 24h (graceful if table doesn't exist yet)
            map_lookups_24h: int = 0
            with contextlib.suppress(Exception):
                map_lookups_24h = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM analytics_map_lookups
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    """
                    )
                    or 0
                )

            return {
                "total_clients": total_clients,
                "total_practices": total_practices,
                "map_lookups_24h": map_lookups_24h,
            }
    except Exception as e:
        logger.error("Dashboard stats failed: %s", e, exc_info=True)
        return {
            "total_clients": 0,
            "total_practices": 0,
            "map_lookups_24h": 0,
            "error": str(e),
        }


# ── Endpoint 6: Unified Investment Analysis ───────────────────────────


@router.post("/analyze-investment")
async def analyze_investment(req: AnalyzeInvestmentRequest) -> dict[str, Any]:
    """
    Unified investment analysis: BATARA zone + KBLI compliance + ROI projection
    in a single call. The killer endpoint.
    """
    result: dict[str, Any] = {
        "coordinates": {"lat": req.lat, "lon": req.lon},
        "zone": None,
        "kbli": None,
        "roi": None,
        "verdict": None,
    }

    # ── A) BATARA → Zona RDTR (primary) → GISTARU fallback ────────────
    zone_code: str | None = None
    zone_data: dict[str, Any] = {}
    batara_success = False
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            batara_resp = await client.post(
                BATARA_URL,
                json={"x": req.lon, "y": req.lat, "informationType": "RDTR"},
                headers=BATARA_HEADERS,
            )
            batara_resp.raise_for_status()
            bd = batara_resp.json().get("data", {})
            geom_list = bd.get("territorials", {}).get("geom", [])

            if geom_list:
                geom0 = geom_list[0]
                zone = geom0.get("zone", {})
                location = geom0.get("location", {})
                reqs = zone.get("zone_intensity_requirements", [])
                req_data = reqs[0] if reqs else {}

                zone_code = zone.get("code")
                zone_data = {
                    "source": "batara_live",
                    "code": zone_code or "N/A",
                    "name": zone.get("name", "N/A"),
                    "desa": location.get("name", "N/A"),
                    "kdb": req_data.get("maximum_kdb", "N/A"),
                    "klb": req_data.get("maximum_klb", "N/A"),
                    "kdh": req_data.get("mininum_kdh", "N/A"),  # BATARA typo
                    "tb": req_data.get("old_building_height", "N/A"),
                    "gsb": req_data.get("old_minimum_gsb", "N/A"),
                }
                result["zone"] = zone_data
                batara_success = True
                logger.info(
                    "Investment analysis: BATARA returned zone %s (%s) at %s",
                    zone_code,
                    zone_data["name"],
                    zone_data["desa"],
                )
    except Exception as e:
        logger.warning("Investment analysis: BATARA failed: %s", e)

    # ── A2) GISTARU RDTR fallback (when BATARA fails or no data) ─────
    if not batara_success:
        logger.info(
            "Investment analysis: trying GISTARU RDTR fallback for %s,%s",
            req.lat,
            req.lon,
        )
        gistaru_result = await _gistaru_rdtr_lookup(req.lat, req.lon)
        if gistaru_result:
            zone_code = gistaru_result.get("code")
            zone_data = gistaru_result
            result["zone"] = gistaru_result
            logger.info(
                "Investment analysis: GISTARU returned zone %s (%s) at %s",
                zone_code,
                gistaru_result.get("name"),
                gistaru_result.get("desa"),
            )
        else:
            result["zone"] = {"source": "unavailable", "code": "NO_DATA"}
            logger.warning(
                "Investment analysis: no zone data from BATARA or GISTARU for %s,%s",
                req.lat,
                req.lon,
            )

    # ── B) KBLIEye → Compliance PMA ───────────────────────────────────
    kbli_state: str | None = None
    kbli_oss_risk: str | None = None
    if req.kbli_code:
        try:
            eye = _get_kbli_eye()
            kd = eye.get_decision(
                code=req.kbli_code,
                is_pma=req.is_pma,
                location="Bali",
            )
            audit = kd.get("audit", kd)
            kbli_state = audit.get("state", kd.get("state", "UNKNOWN"))
            kbli_oss_risk = audit.get("oss_risk") or None
            pma_logic = kd.get("pma_logic", {})

            result["kbli"] = {
                "code": kd.get("kbli_2025", req.kbli_code),
                "title": kd.get("title", ""),
                "state": kbli_state,
                "reason": audit.get("reason_code", ""),
                "oss_risk": audit.get("oss_risk", ""),
                "max_foreign_ownership": pma_logic.get("max_foreign_ownership", 0),
            }
            logger.info(
                "Investment analysis: KBLI %s → %s",
                req.kbli_code,
                kbli_state,
            )
        except Exception as e:
            result["kbli"] = {
                "code": req.kbli_code,
                "state": "ERROR",
                "error": str(e),
            }
            logger.error("Investment analysis: KBLIEye failed: %s", e)

    # ── C) ROI Calculator → Rendimento ────────────────────────────────
    if zone_code and req.land_size_m2 and req.price_idr:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                roi_resp = await client.post(
                    ROI_CALCULATOR_URL,
                    json={
                        "land_size_m2": req.land_size_m2,
                        "price_total_idr": req.price_idr,
                        "zone_code": zone_code,
                    },
                )
                roi_resp.raise_for_status()
                roi_data = roi_resp.json()
                result["roi"] = {
                    "golden_strategy": roi_data.get("golden_strategy", {}),
                    "urbanistica": roi_data.get("urbanistica", {}),
                    "total_investment_idr": roi_data.get("total_investment_idr"),
                }
                logger.info(
                    "Investment analysis: ROI calculated for zone %s",
                    zone_code,
                )
        except Exception as e:
            result["roi"] = {"error": str(e)}
            logger.warning("Investment analysis: ROI calculator failed: %s", e)

    # ── Scoring Engine (3-Layer) ──────────────────────────────────────
    scoring = calculate_investment_score(
        zone_data=zone_data if zone_data else None,
        kbli_state=kbli_state,
        kbli_code=req.kbli_code,
        roi_data=result.get("roi"),
        geo_data=req.geo_data,
        oss_risk=kbli_oss_risk,
    )

    verdict_label = scoring["verdict"]
    can_invest = scoring["can_invest"]
    inv_score = scoring["score"]

    # Map verdict to risk_level for backward compatibility
    risk_map = {"GREEN": "LOW", "YELLOW": "MEDIUM", "RED": "HIGH"}
    risk_level = risk_map.get(verdict_label, "UNKNOWN")

    # Build human-readable summary
    overlays = zone_data.get("overlays", {}) if zone_data else {}
    parts: list[str] = []
    if zone_code and zone_data:
        loc = zone_data.get("desa", "")
        if zone_data.get("kecamatan"):
            loc = f"{loc}, {zone_data['kecamatan']}"
        parts.append(f"Zona {zone_data.get('code', '?')} {loc}")
    if scoring["hard_blocks"]:
        for hb in scoring["hard_blocks"]:
            parts.append(f"🚫 {hb}")
    if overlays:
        parts.append(f"⚠️ {len(overlays)} overlay: {', '.join(overlays.keys())}")
    if result.get("kbli"):
        k = result["kbli"]
        parts.append(
            f"KBLI {k.get('code', '?')} {k.get('title', '')} "
            f"{k.get('state', '?')} per {'PMA' if req.is_pma else 'locale'}"
        )
    roi_gs = result.get("roi", {}).get("golden_strategy", {})
    if roi_gs.get("roi"):
        parts.append(f"ROI stimato {roi_gs['roi']:.1f}%, break-even {roi_gs.get('bey', '?')} anni")

    result["verdict"] = {
        "can_invest": can_invest,
        "risk_level": risk_level,
        "score": inv_score,
        "breakdown": scoring["breakdown"],
        "modifiers": scoring["modifiers"],
        "hard_blocks": scoring["hard_blocks"],
        "summary": " — ".join(parts) if parts else "Dati insufficienti per un verdetto completo.",
    }

    logger.info(
        "Investment analysis: verdict=%s score=%d risk=%s hard_blocks=%d",
        verdict_label,
        inv_score,
        risk_level,
        len(scoring["hard_blocks"]),
    )
    return result
