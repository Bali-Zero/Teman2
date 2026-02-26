"""
Dashboard Router - KBLI-Zoning Integration for Streamlit dashboard.

Provides 6 endpoints for property validation, client geo data,
risk zones, analytics logging, aggregate stats, and unified investment analysis.
"""

import logging
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


# ── BATARA / ROI constants ────────────────────────────────────────────

BATARA_URL = "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point"
BATARA_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://app.batara.badungkab.go.id/",
    "Origin": "https://app.batara.badungkab.go.id",
    "User-Agent": "Mozilla/5.0",
}
ROI_CALCULATOR_URL = "http://localhost:8001/calculator"

# ── GISTARU RDTR Interaktif (ATR/BPN national) — fallback for non-Badung ──
GISTARU_PROXY = "https://gistaru-proxy.atrbpn.go.id/proxy.ashx?"
GISTARU_RDTR_API = "https://gistaru.atrbpn.go.id/rdtrinteraktif/api/interactive"
# MapServer services per kabupaten (discovered Feb 2026)
GISTARU_MAPSERVER_BASE = (
    "https://gistaru.atrbpn.go.id/arcgis/rest/services"
    "/060_RDTR_PROVINSI_BALI"
)
GISTARU_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gistaru.atrbpn.go.id/"}


# ── GISTARU fallback: spatial query via ArcGIS proxy ─────────────────


async def _gistaru_rdtr_lookup(
    lat: float, lon: float
) -> dict[str, Any] | None:
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
            cities = cities_body.get("data", cities_body) if isinstance(cities_body, dict) else cities_body
            logger.info("GISTARU: %d kabupaten found", len(cities) if isinstance(cities, list) else 0)

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
                    logger.debug("GISTARU: rdtr list failed for %s (HTTP %d)", city_name, rdtr_resp.status_code)
                    continue

                # API wraps response in {status, message, data}
                rdtr_body = rdtr_resp.json()
                rdtr_list = rdtr_body.get("data", rdtr_body) if isinstance(rdtr_body, dict) else rdtr_body
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
                    qs = urlencode({
                        "geometry": f"{lon},{lat}",
                        "geometryType": "esriGeometryPoint",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "*",
                        "returnGeometry": "false",
                        "f": "json",
                    })
                    inner_url = f"{arcgis_base}/{mapserver_path}/0/query?{qs}"
                    proxied = f"{GISTARU_PROXY}{inner_url}"
                    try:
                        qr = await client.get(
                            proxied, headers=GISTARU_HEADERS,
                            timeout=10,
                        )
                    except httpx.TimeoutException:
                        logger.debug("GISTARU: timeout querying %s", rdtr.get("rtr", ""))
                        continue
                    if qr.status_code != 200:
                        logger.debug("GISTARU: query %s returned HTTP %d", rdtr.get("rtr", ""), qr.status_code)
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
                                "KKOP_1", "LP2B_2", "KRB_03", "TEB_05",
                                "CAGBUD", "RESAIR", "SEMPDN", "HANKAM",
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
    qs = urlencode({
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    })
    inner_url = (
        f"{GISTARU_MAPSERVER_BASE}/{service_path}/MapServer/0/query?{qs}"
    )
    proxied = f"{GISTARU_PROXY}{inner_url}"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                proxied, headers=GISTARU_HEADERS,
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
                        "KKOP_1", "LP2B_2", "KRB_03", "TEB_05",
                        "CAGBUD", "RESAIR", "SEMPDN", "HANKAM",
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
        req.kbli_code, req.is_pma, req.location, state,
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
            result.get("code"), result.get("name"),
            result.get("desa"), result.get("kabupaten"),
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
                req.user_email, req.kbli_code,
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
            total_clients: int = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE status = 'active'"
            ) or 0

            total_practices: int = await conn.fetchval(
                """
                SELECT COUNT(*) FROM practices
                WHERE status NOT IN ('cancelled', 'archived')
                """
            ) or 0

            # Map lookups in last 24h (graceful if table doesn't exist yet)
            map_lookups_24h: int = 0
            try:
                map_lookups_24h = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM analytics_map_lookups
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    """
                ) or 0
            except Exception:
                pass  # Table may not exist yet

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
                    zone_code, zone_data["name"], zone_data["desa"],
                )
    except Exception as e:
        logger.warning("Investment analysis: BATARA failed: %s", e)

    # ── A2) GISTARU RDTR fallback (when BATARA fails or no data) ─────
    if not batara_success:
        logger.info(
            "Investment analysis: trying GISTARU RDTR fallback for %s,%s",
            req.lat, req.lon,
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
                req.lat, req.lon,
            )

    # ── B) KBLIEye → Compliance PMA ───────────────────────────────────
    kbli_state: str | None = None
    if req.kbli_code:
        try:
            eye = _get_kbli_eye()
            kd = eye.get_decision(
                code=req.kbli_code, is_pma=req.is_pma, location="Bali",
            )
            audit = kd.get("audit", kd)
            kbli_state = audit.get("state", kd.get("state", "UNKNOWN"))
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
                "Investment analysis: KBLI %s → %s", req.kbli_code, kbli_state,
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
                    "Investment analysis: ROI calculated for zone %s", zone_code,
                )
        except Exception as e:
            result["roi"] = {"error": str(e)}
            logger.warning("Investment analysis: ROI calculator failed: %s", e)

    # ── Verdict ───────────────────────────────────────────────────────
    can_invest = kbli_state != "REJECTED" if kbli_state else True
    # Check overlay constraints from GISTARU (if available)
    overlays = zone_data.get("overlays", {}) if zone_data else {}
    has_overlay_warning = bool(overlays)

    if kbli_state == "REJECTED" or has_overlay_warning:
        risk_level = "HIGH"
    elif kbli_state == "WARNING" or (
        result.get("roi", {}).get("golden_strategy", {}).get("roi", 100) < 8
    ):
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Build summary from collected data
    parts: list[str] = []
    if zone_code and zone_data:
        loc = zone_data.get("desa", "")
        if zone_data.get("kecamatan"):
            loc = f"{loc}, {zone_data['kecamatan']}"
        source_tag = f" [{zone_data.get('source', '')}]"
        parts.append(f"Zona {zone_data.get('code', '?')} {loc}{source_tag}")
    if overlays:
        parts.append(f"⚠️ {len(overlays)} overlay attivi: {', '.join(overlays.keys())}")
    if result.get("kbli"):
        k = result["kbli"]
        parts.append(
            f"KBLI {k.get('code', '?')} {k.get('title', '')} "
            f"{k.get('state', '?')} per {'PMA' if req.is_pma else 'locale'}"
        )
    roi_gs = result.get("roi", {}).get("golden_strategy", {})
    if roi_gs.get("roi"):
        parts.append(
            f"ROI stimato {roi_gs['roi']:.1f}%, break-even {roi_gs.get('bey', '?')} anni"
        )

    result["verdict"] = {
        "can_invest": can_invest,
        "risk_level": risk_level,
        "summary": " — ".join(parts) if parts else "Dati insufficienti per un verdetto completo.",
    }

    logger.info(
        "Investment analysis complete: verdict=%s risk=%s",
        can_invest, risk_level,
    )
    return result
