"""
Nuzantara Prime — Geospatial Zoning API

Exposes PostGIS spatial queries for the Prime 3D map intelligence layer.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db

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
    WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
    ORDER BY risk_score DESC
    LIMIT 1
"""


@router.get("/zoning")
async def get_zoning(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return GISTARU zoning data for a given lat/lng coordinate.
    Uses PostGIS ST_Contains with a GIST index — typically < 10ms.
    """
    try:
        from sqlalchemy import text

        result = await db.execute(
            text(_ZONING_QUERY),
            {"lat": lat, "lng": lng},
        )
        row = result.mappings().first()

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

        logger.info(f"✅ [Prime] Zoning hit: {zone_type} @ {lat},{lng}")
        return {
            "status": "found",
            "lat": lat,
            "lng": lng,
            "district": row["district_name"],
            "subdistrict": row["subdistrict_name"],
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_type": zone_type,
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
