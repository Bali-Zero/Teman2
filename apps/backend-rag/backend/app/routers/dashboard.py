"""
ZANTARA - Interactive Dashboard Router

Provides endpoints for the Streamlit-based interactive zoning map:
- KBLI validation with KBLIEye deterministic audit
- Client geolocation for map overlay
- Compliance risk zones
- Analytics logging for map interactions
- Dashboard statistics and summary
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ======================
# 1. KBLI Validation
# ======================


@router.post("/validate-property")
async def validate_property(
    location: str,
    kbli_code: str,
    is_pma: bool = True,
    skala: Optional[str] = None,
) -> dict[str, Any]:
    """
    Validate KBLI code using KBLIEye deterministic audit engine.

    Args:
        location: Region/city where business operates (e.g., "Bali", "Jakarta")
        kbli_code: Indonesian business classification code (5-digit, can be 2020 or 2025)
        is_pma: True if foreign investor (PMA), False if local
        skala: Enterprise scale ("Mikro", "Kecil", "Menengah", "Besar"), defaults to "Besar"

    Returns:
        dict: Audit result with state (APPROVED|RESTRICTED|WARNING|REJECTED), 
              compliance details, and licensing info
    """
    try:
        # Lazy import KBLIEye
        from backend.app.routers.kbli_notebook import KBLIEye

        eye = KBLIEye()
        result = eye.get_decision(
            code=kbli_code,
            is_pma=is_pma,
            location=location,
            skala=skala,
        )

        logger.info(
            f"KBLI validation: {kbli_code} @ {location} (PMA={is_pma}) → {result.get('audit', {}).get('state')}"
        )
        return result

    except Exception as e:
        logger.error(f"KBLI validation failed: {kbli_code}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "KBLI validation failed", "message": str(e)},
        )


# ======================
# 2. Client Geolocation
# ======================


@router.get("/clients/geo")
async def get_clients_geolocation(request: Request) -> dict[str, Any]:
    """
    Retrieve all CRM clients with geolocation for map overlay.

    Returns clients with:
    - ID, name, email, phone
    - Latitude/longitude (if available from address)
    - Status (active, inactive, prospect, archived)
    - Primary practices count

    Returns:
        dict: {clients: [{id, name, lat, lon, status, practices_count}, ...]}
    """
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")

        async with db_pool.acquire() as conn:
            # Fetch clients with basic geolocation (naive — from address field)
            # TODO: Integrate with Google Maps API for real geocoding
            clients = await conn.fetch(
                """
                SELECT
                    c.id,
                    c.name,
                    c.email,
                    c.phone,
                    c.status,
                    c.nationality,
                    COALESCE(c.latitude, -8.6705) as lat,
                    COALESCE(c.longitude, 115.2126) as lon,
                    COUNT(p.id)::INTEGER as practices_count
                FROM crm_clients c
                LEFT JOIN crm_practices p ON p.client_id = c.id AND p.status != 'archived'
                WHERE c.status IN ('active', 'inactive', 'prospect')
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT 500
            """
            )

            return {
                "status": "ok",
                "clients": [
                    {
                        "id": str(row["id"]),
                        "name": row["name"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "status": row["status"],
                        "nationality": row["nationality"],
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "practices_count": row["practices_count"],
                    }
                    for row in clients
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to fetch client geolocation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch clients", "message": str(e)},
        )


# ======================
# 3. Compliance Risk Zones
# ======================


@router.get("/compliance/risk-zones")
async def get_compliance_risk_zones(
    region: str = "Bali",
) -> dict[str, Any]:
    """
    Get compliance risk zones for a region.

    Returns geozones classified by compliance risk level:
    - HIGH: Restricted sectors (TERTUTUP KBLI codes)
    - MEDIUM: Conditional sectors (TERBATAS KBLI codes)
    - LOW: Open sectors (TERBUKA KBLI codes)

    Args:
        region: Region to query (default: "Bali")

    Returns:
        dict: {zones: [{name, risk_level, kbli_codes}, ...]}
    """
    try:
        # For now, return static zone definitions
        # TODO: Query actual KBLI data from Qdrant/PostgreSQL

        risk_definitions = {
            "HIGH": {
                "label": "Restricted Sectors (TERTUTUP)",
                "color": "#dc2626",
                "meaning": "Foreign investment (PMA) prohibited",
                "example_codes": ["51111", "51112", "6411"],  # Falconry, airlines, legal
            },
            "MEDIUM": {
                "label": "Conditional Sectors (TERBATAS)",
                "color": "#f59e0b",
                "meaning": "Foreign investment allowed with conditions",
                "example_codes": ["4711", "50301", "6831"],  # Retail, postal, law enforcement
            },
            "LOW": {
                "label": "Open Sectors (TERBUKA)",
                "color": "#10b981",
                "meaning": "Foreign investment unrestricted",
                "example_codes": ["4532", "5520", "6209"],  # Hospitality, accommodation
            },
        }

        return {
            "status": "ok",
            "region": region,
            "risk_zones": risk_definitions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to fetch risk zones: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch risk zones", "message": str(e)},
        )


# ======================
# 4. Analytics Logging
# ======================


@router.post("/analytics/log-lookup")
async def log_lookup(
    request: Request,
    user_email: str,
    property_code: str,
    kbli_code: str,
    location: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Log a map interaction (KBLI lookup) for analytics.

    Tracks:
    - User email
    - Property/zone code being queried
    - KBLI code entered
    - Location
    - Timestamp
    - Optional notes

    Returns:
        dict: {logged: true, id: uuid}
    """
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analytics_map_lookups
                (user_email, property_code, kbli_code, location, notes, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                user_email,
                property_code,
                kbli_code,
                location,
                notes,
                datetime.now(timezone.utc),
            )

        logger.info(
            f"Map lookup logged: {user_email} → {kbli_code} @ {property_code} ({location})"
        )

        return {
            "status": "ok",
            "logged": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to log lookup: {e}", exc_info=True)
        # Don't fail the request — analytics is non-critical
        return {
            "status": "warning",
            "logged": False,
            "error": str(e),
        }


# ======================
# 5. Dashboard Statistics
# ======================


@router.get("/stats")
async def get_dashboard_stats(request: Request) -> dict[str, Any]:
    """
    Get dashboard-level statistics for summary display.

    Returns:
    - Total clients and active practices
    - KBLI validation distribution (APPROVED/RESTRICTED/REJECTED)
    - Risk zone summary (count of HIGH/MEDIUM/LOW zones)
    - Recent map activity

    Returns:
        dict: {clients_total, practices_active, kbli_audit_dist, ...}
    """
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if not db_pool:
            raise HTTPException(status_code=503, detail="Database not available")

        async with db_pool.acquire() as conn:
            # Clients summary
            clients_total = await conn.fetchval(
                "SELECT COUNT(*) FROM crm_clients WHERE status IN ('active', 'inactive', 'prospect')"
            )

            clients_active = await conn.fetchval(
                "SELECT COUNT(*) FROM crm_clients WHERE status = 'active'"
            )

            # Practices summary
            practices_active = await conn.fetchval(
                "SELECT COUNT(*) FROM crm_practices WHERE status IN ('active', 'pending', 'submitted', 'waiting_documents')"
            )

            practices_completed = await conn.fetchval(
                "SELECT COUNT(*) FROM crm_practices WHERE status = 'completed'"
            )

            # Recent lookups (last 24h)
            recent_lookups = await conn.fetchval(
                """
                SELECT COUNT(*) FROM analytics_map_lookups
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """
            )

            # Practice status distribution
            practice_dist = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM crm_practices
                GROUP BY status
                ORDER BY count DESC
            """
            )

            return {
                "status": "ok",
                "summary": {
                    "clients_total": clients_total or 0,
                    "clients_active": clients_active or 0,
                    "practices_active": practices_active or 0,
                    "practices_completed": practices_completed or 0,
                },
                "activity": {
                    "map_lookups_24h": recent_lookups or 0,
                },
                "practice_distribution": [
                    {"status": row["status"], "count": row["count"]} for row in practice_dist
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch stats", "message": str(e)},
        )
