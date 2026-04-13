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

from backend.core.cache import invalidate_cache

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
    return await service.resolve(req.lat, req.lng)


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
    return await service.analyze(
        lat=req.lat,
        lng=req.lng,
        kbli_code=req.kbli_code,
        is_pma=req.is_pma,
        land_size_m2=req.land_size_m2,
        price_idr=req.price_idr,
        investor_profile=req.investor_profile.model_dump() if req.investor_profile else None,
        geo_data=req.geo_data,
    )


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


# ── Layer 4: Competitor Density ──────────────────────────────────────


@router.get("/density")
async def zone_density(
    request: Request,
    zone_code: str = Query(..., min_length=1, description="RDTR zone code"),
) -> dict[str, Any]:
    """
    Business density and competitor saturation for a zoning area.

    Returns KBLI sector breakdown and saturation index (0-1).
    Public endpoint — no authentication required.
    """
    service = _get_service(request)
    return await service.density(zone_code=zone_code)


# ── Layer 5: Predictive Zone Score ───────────────────────────────────


@router.get("/predict")
async def predict_zone_score(
    request: Request,
    zone_code: str = Query(..., min_length=1, description="RDTR zone code"),
) -> dict[str, Any]:
    """
    Predict zone investment trend based on 3 signals.

    Returns trend direction (improving/stable/declining) and predicted label shift.
    Public endpoint — no authentication required.
    """
    service = _get_service(request)
    return await service.predict_zone(zone_code=zone_code)


# ── Layer 6: Temporal Intelligence ───────────────────────────────────


@router.get("/temporal")
async def temporal_intelligence(
    request: Request,
    zone_code: str = Query(..., min_length=1),
    period: str = Query("6m", pattern="^(1m|3m|6m|12m)$"),
    granularity: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
) -> dict[str, Any]:
    """
    Temporal activity analysis for a zoning area.

    Returns time-bucketed practice and company activity with trend direction.
    Requires authentication (admin only).
    """
    service = _get_service(request)
    return await service.temporal(
        zone_code=zone_code, period=period, granularity=granularity,
    )


# ── Layer 7: Regulation Feed ─────────────────────────────────────────


@router.get("/regulations")
async def regulation_feed(
    request: Request,
    zone_code: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """
    Live regulation feed for a zoning area from news_items + Qdrant.

    Returns recent regulatory articles relevant to the zone.
    Public endpoint — no authentication required.
    """
    service = _get_service(request)
    return await service.regulations(zone_code=zone_code, limit=limit)


# ── Layer 8: Proposals (Deal Flow) ───────────────────────────────────


class CreateProposalRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    zone_code: str
    zone_name: str | None = None
    kbli_code: str | None = None
    verdict_label: str | None = None
    verdict_score: int | None = None
    analysis_snapshot: dict[str, Any] | None = None
    investor_name: str | None = None
    investor_email: str | None = None
    investor_nationality: str | None = None


@router.post("/proposal")
async def create_proposal(req: CreateProposalRequest, request: Request) -> dict[str, Any]:
    """
    Create a shareable investment proposal from Prime analysis.

    Requires admin authentication. Returns a token for public sharing.
    """
    service = _get_service(request)
    result = await service.create_proposal(
        lat=req.lat, lng=req.lng, zone_code=req.zone_code,
        zone_name=req.zone_name, kbli_code=req.kbli_code,
        verdict_label=req.verdict_label, verdict_score=req.verdict_score,
        analysis_snapshot=req.analysis_snapshot,
        investor_name=req.investor_name, investor_email=req.investor_email,
        investor_nationality=req.investor_nationality,
    )
    await invalidate_cache("zantara:prime_proposals:*")
    return result


@router.get("/proposal/{token}")
async def get_proposal(token: str, request: Request) -> dict[str, Any]:
    """
    Retrieve an investment proposal by token.

    Public endpoint — token-based access, no authentication required.
    """
    service = _get_service(request)
    result = await service.get_proposal(token)
    if not result:
        return {"error": "not_found"}
    return result


# ── Layer 9: Portfolio Advisor ────────────────────────────────────────


@router.get("/portfolio")
async def portfolio_advisor(
    request: Request,
    client_id: int = Query(..., ge=1),
) -> dict[str, Any]:
    """
    Portfolio health and risk concentration for a client's entities.

    Returns all geocoded companies + active practices with health scores.
    Requires authentication.
    """
    service = _get_service(request)
    return await service.portfolio(client_id=client_id)


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
            "density": "active",
            "predict": "active",
            "temporal": "active",
            "regulations": "active",
            "proposals": "active",
            "portfolio": "active",
        },
    }
