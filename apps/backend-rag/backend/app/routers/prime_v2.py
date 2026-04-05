"""
Prime Nexus v2 Router — Layered Geospatial Intelligence API.

Layer 1: POST /resolve  — spatial zone resolution (< 50ms cache / < 2s cold)
Layer 2: POST /analyze  — investment analysis with scoring (< 3s)  [Sprint 2]
Layer 3: GET  /intelligence — CRM overlay in bounding box (< 3s)   [Sprint 4]
"""

import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime/v2", tags=["prime-nexus"])


# ── Request/Response Models ──────────────────────────────────────────


class SpatialResolveRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")


class ZoneResolution(BaseModel):
    zone_code: str
    zone_name: str
    zone_label_en: str
    zone_description_en: str
    zone_color_hex: str | None = None
    is_restricted: bool = False
    allowed_activities: list[str] = []
    restrictions: list[str] = []
    overlays: dict[str, str] = {}
    building_codes: dict[str, Any] | None = None
    source: str  # "batara_live"|"gistaru_rdtr"|"postgis_cache"|"redis_cache"
    confidence: float  # 1.0 BATARA, 0.7 GISTARU, 0.5 PostGIS


class SpatialResolveResponse(BaseModel):
    status: str  # "found"|"outside_coverage"|"error"
    lat: float
    lng: float
    zone: ZoneResolution | None = None
    cache_hit: bool = False


class InvestorProfile(BaseModel):
    nationality: str | None = None
    budget_usd: float | None = None
    business_type: str | None = None


class BusinessAnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    kbli_code: str | None = None
    is_pma: bool = True
    land_size_m2: float | None = None
    price_idr: float | None = None
    investor_profile: InvestorProfile | None = None
    geo_data: dict[str, Any] | None = None


# ── Service initialization via app.state ─────────────────────────────


def _get_service(request: Request) -> Any:
    """Get PrimeNexusService from app.state. Creates lazily on first call.

    Uses app.state to avoid global singleton race conditions with multiple workers.
    The service's HTTP client should be closed in the app lifespan shutdown.
    """
    service = getattr(request.app.state, "prime_nexus_service", None)
    if service is not None:
        return service

    from backend.services.prime.prime_nexus_service import PrimeNexusService

    cache_service = getattr(request.app.state, "cache_service", None)
    db_pool = getattr(request.app.state, "db_pool", None)
    service = PrimeNexusService(cache_service=cache_service, db_pool=db_pool)
    request.app.state.prime_nexus_service = service
    logger.info("✅ [PrimeNexus] Service initialized (cache=%s, pool=%s)",
                cache_service is not None, db_pool is not None)
    return service


# ── Layer 1: Spatial Resolution ──────────────────────────────────────


@router.post("/resolve")
async def resolve_zone(req: SpatialResolveRequest, request: Request) -> dict[str, Any]:
    """
    Resolve RDTR zoning data for a geographic point.

    Pipeline: Redis cache → BATARA API → GISTARU fallback → PostGIS.
    Returns zone code, allowed activities, building codes, overlays.

    Public endpoint — no authentication required.
    """
    service = _get_service(request)
    result = await service.resolve(req.lat, req.lng)
    return result


# ── Layer 2: Investment Analysis ──────────────────────────────────────


@router.post("/analyze")
async def analyze_investment(req: BusinessAnalyzeRequest, request: Request) -> dict[str, Any]:
    """
    Full investment analysis for a geographic point.

    Pipeline: resolve zone → KBLIEye compliance → scoring engine → intel search.
    Returns verdict (GREEN/YELLOW/RED), score breakdown, opportunities, intel articles.

    Public endpoint — rate limited to 10 req/min per IP.
    """
    service = _get_service(request)
    result = await service.analyze(
        lat=req.lat,
        lng=req.lng,
        kbli_code=req.kbli_code,
        is_pma=req.is_pma,
        land_size_m2=req.land_size_m2,
        price_idr=req.price_idr,
        investor_profile=req.investor_profile.model_dump() if req.investor_profile else None,
        geo_data=req.geo_data,
    )
    return result


# ── Layer 3: CRM Intelligence Overlay ────────────────────────────────


@router.get("/intelligence")
async def intelligence_overlay(
    request: Request,
    sw_lat: float = Query(..., ge=-90, le=90),
    sw_lng: float = Query(..., ge=-180, le=180),
    ne_lat: float = Query(..., ge=-90, le=90),
    ne_lng: float = Query(..., ge=-180, le=180),
) -> dict[str, Any]:
    """
    CRM intelligence overlay: geocoded clients/companies within a map bounding box.

    Returns GeoJSON FeatureCollection with entity markers, capped at 2000 features.
    Requires authentication (nz_access_token) — not in public paths.
    """
    service = _get_service(request)
    return await service.intelligence(
        sw_lat=sw_lat, sw_lng=sw_lng,
        ne_lat=ne_lat, ne_lng=ne_lng,
    )


# ── Health check ─────────────────────────────────────────────────────


@router.get("/health")
async def prime_nexus_health() -> dict[str, Any]:
    """Check Prime Nexus service status."""
    return {
        "status": "healthy",
        "service": "prime_nexus_v2",
        "layers": {
            "resolve": "active",
            "analyze": "active",
            "intelligence": "active",
        },
    }
