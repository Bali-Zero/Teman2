"""Prime Nexus — Activity classification + zone-KBLI fit + investment scoring."""

from __future__ import annotations

import contextlib
from typing import Any

from backend.services.prime.geo_service import NON_BUILDABLE_ZONES, _zone_matches_prefix

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


# =============================================================================
# ZONE-KBLI COMPATIBILITY (extracted from dashboard.py)
# =============================================================================
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

    # Risk score: prefer numeric risk_score (0-1), fallback to string flood_risk
    risk_val = geo_data.get("risk_score") if geo_data else None
    flood = geo_data.get("flood_risk") if geo_data else None
    if risk_val is not None:
        risk_points = 10 if risk_val < 0.2 else 8 if risk_val < 0.4 else 5 if risk_val < 0.6 else 2 if risk_val < 0.8 else 0
    elif flood is not None:
        risk_points = {"safe": 10, "check": 5, "high": 0}.get(str(flood), 7)
    else:
        risk_points = 7
    breakdown["risk"] = {"score": risk_points, "max": 10, "value": risk_val, "flood_risk": flood}

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

    _all_scores = [roi_score, zone_kbli_score, klb_score, bey_score, risk_points, market_score, reg_score, ws_score]
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

    # Sea distance modifiers (replaces boolean sea_view)
    sea_dist = geo_data.get("sea_distance_m") if geo_data else None
    sea_view = geo_data.get("sea_view", False) if geo_data else False
    if sea_dist is not None:
        if sea_dist < 200:
            score += 5
            modifiers.append(f"+5: premium prossimità mare ({sea_dist:.0f}m dalla costa)")
            score -= 3
            modifiers.append("-3: rischio tsunami (< 200m dalla costa)")
        elif sea_dist < 1000:
            score += 3
            modifiers.append(f"+3: zona costiera ({sea_dist:.0f}m dalla costa)")
    elif sea_view and score >= 55:
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
